// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::model::nodes::{Children, Node, Parents};
use crate::model::schemas::Cmd;
use std::collections::VecDeque;

pub fn find_root_node(nodes: &[Node]) -> Option<usize> {
    for node in nodes {
        if let Node::Root(root) = node
            && root.parents.is_empty()
        {
            return Some(root.uid);
        }
    }

    None
}

pub fn add_children(nodes: &mut [Node]) {
    let mut all_children: Vec<Vec<usize>> = vec![Vec::new(); nodes.len()];
    for node in nodes.iter() {
        let uid = node.get_uid();
        for parent in node.parents() {
            all_children[parent].push(uid);
        }
    }

    for (uid, mut children) in all_children.into_iter().enumerate() {
        children.sort();
        children.dedup();
        nodes[uid].set_children(children);
    }
}

pub fn compute_positions(nodes: &mut [Node]) -> Result<(), String> {
    let mut indegree = vec![0; nodes.len()];
    for node in nodes.iter() {
        for child in node.children() {
            indegree[*child] += 1;
        }
    }

    let mut ready: VecDeque<usize> = (0..nodes.len()).filter(|&uid| indegree[uid] == 0).collect();
    let mut next = 0;
    while let Some(uid) = ready.pop_front() {
        nodes[uid].set_position(next);
        next += 1;
        for child in nodes[uid].children() {
            indegree[*child] -= 1;
            if indegree[*child] == 0 {
                ready.push_back(*child);
            }
        }
    }

    if next != nodes.len() {
        return Err("The pipeline graph contains a cycle".to_string());
    }
    Ok(())
}

pub fn validate_dag(nodes: &[Node]) -> Result<(), String> {
    check_local_jobs_are_not_array(nodes)?;
    Ok(())
}

fn check_local_jobs_are_not_array(nodes: &[Node]) -> Result<(), String> {
    for node in nodes {
        if let Node::Task(task) = node
            && let Cmd::Bash = task.cmd
            && let Some(each) = &task.each
        {
            let msg = format!(
                "Task {} is a local job array across '{each}'. Local \
                job arrays are not supported, use a for loop instead.",
                task.uid
            );
            return Err(msg);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::nodes::{End, Root, Task};
    use crate::model::schemas::{Parent, ParentKind};

    fn get_nodes() -> Vec<Node> {
        let root = Root {
            uid: 0,
            pipeline_name: "pipeline".into(),
            parents: Vec::new(),
            children: Vec::new(),
            position: 0,
        };
        let task = Task {
            uid: 1,
            parents: vec![Parent {
                uid: 0,
                kind: ParentKind::Logical,
            }],
            ..Default::default()
        };

        let end = End {
            uid: 2,
            pipeline_name: "pipeline".into(),
            parents: vec![Parent {
                uid: 1,
                kind: ParentKind::Logical,
            }],
            children: vec![],
            artifacts: vec![],
            position: 0,
        };

        vec![Node::Root(root), Node::Task(task), Node::End(end)]
    }

    #[test]
    fn test_add_children() {
        let mut nodes = get_nodes();
        add_children(&mut nodes);

        let Node::Root(root) = &nodes[0] else {
            panic!();
        };
        assert_eq!(root.children, vec![1]);

        let Node::Task(task) = &nodes[1] else {
            panic!();
        };
        assert_eq!(task.children, vec![2]);

        let Node::End(end) = &nodes[2] else {
            panic!();
        };
        assert_eq!(end.children.len(), 0);
    }

    #[test]
    fn test_find_root() {
        let mut nodes = get_nodes();
        add_children(&mut nodes);
        let root_uid = find_root_node(&nodes).unwrap();
        assert_eq!(root_uid, 0)
    }

    #[test]
    #[should_panic]
    fn local_task_is_array() {
        let mut task0 = Task::default();
        let mut task1 = Task::default();
        task0.cmd = Cmd::Bash;
        task0.each = Some("field".into());
        task1.uid = 1;

        let nodes = vec![Node::Task(task0), Node::Task(task1)];
        validate_dag(&nodes).unwrap();
    }

    #[test]
    fn slurm_task_is_array() {
        let mut task0 = Task::default();
        let mut task1 = Task::default();
        task0.cmd = Cmd::Sbatch;
        task0.each = Some("field".into());
        task1.uid = 1;

        let nodes = vec![Node::Task(task0), Node::Task(task1)];
        validate_dag(&nodes).unwrap();
    }
}
