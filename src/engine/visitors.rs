// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::{Ctx, Job, NodeCtx};
use crate::engine::submission::{caching, inline};
use crate::model::nodes::{Branch, Children, End, Node, OneOf, ProvideStatus, Root, Task};
use crate::model::schemas::Parent;
use crate::model::status::{
    Completed, Failed, Status, all_parents_completed, all_parents_failed_or_skipped,
    find_completed_parent, some_parents_failed_or_skipped,
};
use crate::settings::Cfg;

use std::collections::{HashSet, VecDeque};

pub trait Visitor<T> {
    fn visit_root(&mut self, node: &Root, ctx: &mut Ctx) -> T;
    fn visit_end(&mut self, node: &End, ctx: &mut Ctx) -> T;
    fn visit_branch(&mut self, node: &Branch, ctx: &mut Ctx) -> T;
    fn visit_task(&mut self, node: &Task, ctx: &mut Ctx) -> T;
    fn visit_oneof(&mut self, node: &OneOf, ctx: &mut Ctx) -> T;
    fn propagate(&self, node: &Node, queue: &mut VecDeque<usize>, visited: &HashSet<usize>) {
        for child_uid in node.children() {
            if !visited.contains(child_uid) {
                queue.push_back(*child_uid);
            }
        }
    }
}

pub struct NodeVisitor<'a, 'b> {
    pub nodes: &'a [Node],
    pub cfg: &'b Cfg,
}

impl<'a, 'b> Visitor<()> for NodeVisitor<'a, 'b> {
    fn visit_root(&mut self, node: &Root, ctx: &mut Ctx) {
        let parent_statuses = self.get_parent_statuses(&node.parents, &ctx.nodes);
        if all_parents_completed(&parent_statuses) {
            ctx.set_status(node.uid, Status::Completed(Completed::Generic));
        } else if some_parents_failed_or_skipped(&parent_statuses) {
            ctx.set_status(node.uid, Status::Skipped);
        }
    }

    fn visit_end(&mut self, node: &End, ctx: &mut Ctx) {
        let parent_statuses = self.get_parent_statuses(&node.parents, &ctx.nodes);
        if all_parents_completed(&parent_statuses) {
            ctx.set_status(node.uid, Status::Completed(Completed::Generic));
        } else if parent_statuses.iter().all(|s| s.is_final()) {
            ctx.set_status(node.uid, Status::Skipped);
        }
    }

    fn visit_branch(&mut self, node: &Branch, ctx: &mut Ctx) {
        let parent_statuses = self.get_parent_statuses(&node.parents, &ctx.nodes);
        if all_parents_completed(&parent_statuses) {
            let status = match inline::submit_branch(node, &self.cfg) {
                Ok(choice) => Status::Completed(Completed::Branch(choice)),
                Err(_) => Status::Failed(Failed::Generic),
            };
            ctx.set_status(node.uid, status);
        } else if some_parents_failed_or_skipped(&parent_statuses) {
            ctx.set_status(node.uid, Status::Skipped);
        }
    }

    fn visit_task(&mut self, node: &Task, ctx: &mut Ctx) {
        let status = &ctx.nodes[node.uid].status;
        match status {
            Status::Pending(_)
            | Status::Running(_)
            | Status::Completed(_)
            | Status::Failed(_)
            | Status::Skipped => {
                return;
            }
            Status::ReadyForSubmission => {
                ctx.jobs.push_back(Job::Task(node.uid));
            }
            Status::NotSubmitted => self.visit_not_submitted_task(node, ctx),
        }
    }

    fn visit_oneof(&mut self, node: &OneOf, ctx: &mut Ctx) {
        let parent_statuses = self.get_parent_statuses(&node.parents, &ctx.nodes);
        if let Some(uid) = find_completed_parent(&node.parents, &ctx.nodes) {
            let status = match inline::submit_oneof(node, uid, &self.cfg) {
                Ok(_) => Status::Completed(Completed::OneOf(uid)),
                Err(e) => {
                    log::error!("Node {}: OneOf failed - {e}", node.uid);
                    Status::Failed(Failed::Generic)
                }
            };
            ctx.set_status(node.uid, status);
        } else if all_parents_failed_or_skipped(&parent_statuses) {
            ctx.set_status(node.uid, Status::Skipped);
        }
    }
}

impl<'a, 'b> NodeVisitor<'a, 'b> {
    pub fn visit(&mut self, ctx: &mut Ctx) {
        let mut visited = HashSet::new();
        while let Some(uid) = ctx.updated.pop_front() {
            if !visited.insert(uid) {
                continue;
            }
            let node = &self.nodes[uid];
            let status = &ctx.nodes[uid].status;
            if !status.is_final() {
                match node {
                    Node::Root(node) => self.visit_root(&node, ctx),
                    Node::End(node) => self.visit_end(&node, ctx),
                    Node::Branch(node) => self.visit_branch(&node, ctx),
                    Node::OneOf(node) => self.visit_oneof(&node, ctx),
                    Node::Task(node) => self.visit_task(&node, ctx),
                }
            }
            self.propagate(node, &mut ctx.updated, &mut visited);
        }
    }

    fn get_parent_statuses<'c>(&self, parents: &[Parent], nodes: &'c [NodeCtx]) -> Vec<&'c Status> {
        parents
            .iter()
            .map(|parent| {
                (
                    &self.nodes[parent.uid],
                    &nodes[parent.uid].status,
                    &parent.kind,
                )
            })
            .map(|(node, status, kind)| node.provide_status(status, kind))
            .collect()
    }

    fn visit_not_submitted_task(&self, task: &Task, ctx: &mut Ctx) {
        let parent_statuses = self.get_parent_statuses(&task.parents, &ctx.nodes);
        if all_parents_completed(&parent_statuses) {
            ctx.set_status(task.uid, Status::ReadyForSubmission);
            if task.cache.is_enabled() {
                if caching::submit_validate_cache(task, &self.cfg) {
                    ctx.set_status(task.uid, Status::Completed(Completed::Cached));
                    return;
                }
                ctx.jobs.push_back(Job::ValidateCache(task.uid, true));
                return;
            }
            ctx.jobs.push_back(Job::Task(task.uid));
        } else if some_parents_failed_or_skipped(&parent_statuses) {
            log::debug!("Task '{}' is skipped", task.uid);
            ctx.set_status(task.uid, Status::Skipped);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::schemas::{Cache, ParentKind, TaskOutput};
    use crate::model::status::{Failed, JobType};
    use crate::store::workdirs::{DirPaths, FileNames};
    use serde_json::Value;
    use std::env;
    use std::fs;
    use std::path::PathBuf;
    use uuid::Uuid;

    fn get_tmp_dir() -> PathBuf {
        let path = env::temp_dir().join(Uuid::new_v4().to_string());
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn get_cfg() -> Cfg {
        let homedir = get_tmp_dir();
        let paths = DirPaths::new(&homedir, "pipeline", "xxx");
        let mut cfg = Cfg::default();
        cfg.homedir = homedir;
        cfg.dagdir = paths.dagdir;
        cfg.cachedir = paths.cachedir;
        cfg.local_cachedir = paths.local_cachedir;
        cfg
    }

    fn get_ctx(nodes: &[Node]) -> Ctx {
        Ctx::new(nodes).unwrap()
    }

    fn get_root(uid: usize) -> Root {
        Root {
            uid,
            pipeline_name: "pipeline".into(),
            parents: vec![],
            children: vec![],
        }
    }

    fn get_end(uid: usize) -> End {
        End {
            uid,
            pipeline_name: "pipeline".into(),
            parents: vec![],
            children: vec![],
            artifacts: vec![],
        }
    }

    fn get_branch(
        uid: usize,
        parent_uid: usize,
        true_branch: usize,
        false_branch: usize,
    ) -> Branch {
        Branch {
            uid,
            pipeline_name: "pipeline".into(),
            parents: vec![Parent {
                uid: parent_uid,
                kind: ParentKind::Output {
                    key: "choice".into(),
                },
            }],
            children: vec![true_branch, false_branch],
            artifacts: vec![],
        }
    }

    fn get_parent(uid: usize) -> Parent {
        Parent {
            uid,
            kind: ParentKind::Logical,
        }
    }

    fn get_branch_parent(uid: usize, branch: bool) -> Parent {
        Parent {
            uid,
            kind: ParentKind::Branch { branch },
        }
    }

    fn get_oneof(uid: usize, parent1: usize, parent2: usize) -> OneOf {
        OneOf {
            uid,
            pipeline_name: "pipeline".into(),
            parents: vec![get_parent(parent1), get_parent(parent2)],
            children: vec![],
            artifacts: vec![],
        }
    }

    fn get_task(uid: usize) -> Task {
        let mut task = Task::default();
        task.uid = uid;
        task
    }

    #[test]
    fn test_visit_root_completed() {
        let cfg = get_cfg();
        let root = get_root(0);
        let nodes = [Node::Root(root)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(0);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Completed(Completed::Generic)
        ))
    }

    #[test]
    fn test_visit_root_skipped() {
        let cfg = get_cfg();
        let root1 = get_root(0);
        let mut root2 = get_root(1);
        root2.parents.push(get_parent(0));
        let nodes = [Node::Root(root1), Node::Root(root2)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(1);
        ctx.nodes[0].status = Status::Failed(Failed::Generic);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[1].status, Status::Skipped))
    }

    #[test]
    fn test_visit_end_completed() {
        let cfg = get_cfg();
        let end = get_end(0);
        let nodes = [Node::End(end)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(0);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Completed(Completed::Generic)
        ))
    }

    #[test]
    fn test_visit_end_skipped() {
        let cfg = get_cfg();
        let root = get_root(0);
        let mut end = get_end(1);
        end.parents.push(get_parent(0));
        let nodes = [Node::Root(root), Node::End(end)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(1);
        ctx.nodes[0].status = Status::Failed(Failed::Generic);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[1].status, Status::Skipped))
    }

    #[test]
    fn test_visit_end_not_submitted() {
        let cfg = get_cfg();
        let root = get_root(0);
        let root2 = get_root(1);
        let mut end = get_end(2);
        end.parents.push(get_parent(0));
        end.parents.push(get_parent(1));
        let nodes = [Node::Root(root), Node::Root(root2), Node::End(end)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Failed(Failed::Generic);
        ctx.nodes[1].status = Status::Running(JobType::Slurm("123".into()));

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[2].status, Status::NotSubmitted))
    }

    #[test]
    fn test_visit_end_skipped_mixed() {
        let cfg = get_cfg();
        let root = get_root(0);
        let root2 = get_root(1);
        let mut end = get_end(2);
        end.parents.push(get_parent(0));
        end.parents.push(get_parent(1));
        let nodes = [Node::Root(root), Node::Root(root2), Node::End(end)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Failed(Failed::Generic);
        ctx.nodes[1].status = Status::Completed(Completed::Generic);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[2].status, Status::Skipped))
    }

    #[test]
    fn test_visit_branch_completed() {
        let cfg = get_cfg();
        let root = get_root(0);

        let mut end1 = get_end(2);
        end1.parents.push(Parent {
            uid: 1,
            kind: ParentKind::Branch { branch: true },
        });

        let mut end2 = get_end(3);
        end2.parents.push(Parent {
            uid: 1,
            kind: ParentKind::Branch { branch: false },
        });

        let branch = get_branch(1, 0, 2, 3);
        let nodes = [
            Node::Root(root),
            Node::Branch(branch),
            Node::End(end1),
            Node::End(end2),
        ];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(1);
        ctx.nodes[0].status = Status::Completed(Completed::Generic);

        let output = TaskOutput {
            output: Value::Bool(true),
            artifacts: Vec::new(),
        };
        let output_str = serde_json::to_string(&output).unwrap();
        let src_dir = cfg.dagdir.join("0");
        fs::create_dir_all(&src_dir).unwrap();
        fs::write(src_dir.join(FileNames::Output.as_str()), output_str).unwrap();

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(
            ctx.nodes[1].status,
            Status::Completed(Completed::Branch(true))
        ));
        assert!(matches!(ctx.nodes[2].status, Status::Completed(_)));
        assert!(matches!(ctx.nodes[3].status, Status::Skipped));
    }

    #[test]
    fn test_visit_branch_skipped() {
        let cfg = get_cfg();
        let root = get_root(0);
        let mut end1 = get_end(2);
        let mut end2 = get_end(3);
        let branch = get_branch(1, 0, 2, 3);

        end1.parents.push(get_branch_parent(1, true));
        end2.parents.push(get_branch_parent(1, false));

        let nodes = [
            Node::Root(root),
            Node::Branch(branch),
            Node::End(end1),
            Node::End(end2),
        ];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(1);
        ctx.nodes[0].status = Status::Failed(Failed::Generic);
        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[1].status, Status::Skipped));
        assert!(matches!(ctx.nodes[2].status, Status::Skipped));
        assert!(matches!(ctx.nodes[3].status, Status::Skipped));
    }

    #[test]
    fn test_visit_branch_already_completed() {
        let cfg = get_cfg();
        let root = get_root(0);
        let mut end2 = get_end(3);
        let mut end1 = get_end(2);
        let branch = get_branch(1, 0, 2, 3);

        end1.parents.push(get_branch_parent(1, true));
        end2.parents.push(get_branch_parent(1, false));

        let nodes = [
            Node::Root(root),
            Node::Branch(branch),
            Node::End(end1),
            Node::End(end2),
        ];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(1);
        ctx.nodes[0].status = Status::Completed(Completed::Generic);
        ctx.nodes[1].status = Status::Completed(Completed::Branch(true));

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(
            ctx.nodes[2].status,
            Status::Completed(Completed::Generic)
        ));
        assert!(matches!(ctx.nodes[3].status, Status::Skipped));
    }

    #[test]
    fn test_visit_oneof_completed() {
        let cfg = get_cfg();
        let root1 = get_root(0);
        let root2 = get_root(1);
        let mut oneof = get_oneof(2, 0, 1);

        oneof.parents.push(get_parent(0));
        oneof.parents.push(get_parent(1));

        let nodes = [Node::Root(root1), Node::Root(root2), Node::OneOf(oneof)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Completed(Completed::Generic);
        ctx.nodes[1].status = Status::Failed(Failed::Generic);

        let src_dir = cfg.dagdir.join("0");
        let dst_dir = cfg.dagdir.join("2");
        fs::create_dir_all(&src_dir).unwrap();
        fs::create_dir_all(&dst_dir).unwrap();
        fs::write(src_dir.join(FileNames::Input.as_str()), "").unwrap();
        fs::write(src_dir.join(FileNames::Output.as_str()), "").unwrap();
        fs::write(src_dir.join(FileNames::Meta.as_str()), "").unwrap();

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);
        assert!(matches!(
            ctx.nodes[2].status,
            Status::Completed(Completed::OneOf(0))
        ));
    }

    #[test]
    fn test_oneof_skipped() {
        let cfg = get_cfg();
        let root1 = get_root(0);
        let root2 = get_root(1);
        let mut oneof = get_oneof(2, 0, 1);

        oneof.parents.push(get_parent(0));
        oneof.parents.push(get_parent(1));

        let nodes = [Node::Root(root1), Node::Root(root2), Node::OneOf(oneof)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Skipped;
        ctx.nodes[1].status = Status::Failed(Failed::Generic);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);
        assert!(matches!(ctx.nodes[2].status, Status::Skipped));
    }

    #[test]
    fn test_visit_task_skipped() {
        let cfg = get_cfg();
        let root1 = get_root(0);
        let root2 = get_root(1);
        let mut task = get_task(2);

        task.parents.push(get_parent(0));
        task.parents.push(get_parent(1));

        let nodes = [Node::Root(root1), Node::Root(root2), Node::Task(task)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Completed(Completed::Generic);
        ctx.nodes[1].status = Status::Failed(Failed::Generic);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[2].status, Status::Skipped));
        assert_eq!(ctx.jobs.len(), 0);
    }

    #[test]
    fn test_visit_task_ready() {
        let cfg = get_cfg();
        let root1 = get_root(0);
        let root2 = get_root(1);
        let mut task = get_task(2);

        task.parents.push(get_parent(0));
        task.parents.push(get_parent(1));

        let nodes = [Node::Root(root1), Node::Root(root2), Node::Task(task)];

        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Completed(Completed::Generic);
        ctx.nodes[1].status = Status::Completed(Completed::Cached);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        assert!(matches!(ctx.nodes[2].status, Status::ReadyForSubmission));

        let job = ctx.jobs.pop_front().unwrap();
        assert!(matches!(job, Job::Task(2)));
    }

    #[test]
    fn test_visit_task_cache() {
        let cfg = get_cfg();
        let root1 = get_root(0);
        let root2 = get_root(1);
        let mut task = get_task(2);

        task.parents.push(get_parent(0));
        task.parents.push(get_parent(1));
        task.cache = Cache::Io;

        let nodes = [Node::Root(root1), Node::Root(root2), Node::Task(task)];
        let mut ctx = get_ctx(&nodes);
        ctx.updated.push_back(2);
        ctx.nodes[0].status = Status::Completed(Completed::Generic);
        ctx.nodes[1].status = Status::Completed(Completed::Cached);

        let mut visitor = NodeVisitor {
            nodes: &nodes,
            cfg: &cfg,
        };
        visitor.visit(&mut ctx);

        let job = ctx.jobs.pop_front().unwrap();
        assert!(matches!(job, Job::ValidateCache(2, true)));
    }
}
