// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::submission;
use crate::model::nodes::Node;
use crate::model::status::{Failed, JobType, Status};
use log;
use serde::{Deserialize, Serialize};
use std::collections::{HashSet, VecDeque};
use std::process::Child;

#[derive(Debug, Clone)]
pub enum Job {
    Task(usize),
    ValidateCache(usize, bool),
}

#[derive(Debug, Default, Clone, Serialize, Deserialize, PartialEq)]
pub struct JobArray {
    pub nmiss: usize,
    pub status: Status,
}

#[derive(Debug, Default, Clone, Serialize, Deserialize, PartialEq)]
pub struct NodeCtx {
    pub try_num: usize,
    pub status: Status,
    pub jobs: Vec<JobArray>,
}

impl NodeCtx {
    pub fn reset_status(&mut self) {
        for job in &mut self.jobs {
            if let Status::Failed(_) | Status::Skipped = job.status {
                job.status = Status::ReadyForSubmission;
                job.nmiss = 0;
            }
        }
        self.status = Status::ReadyForSubmission;
    }
}

#[derive(Debug, Default)]
pub struct Ctx {
    pub updated: VecDeque<usize>,
    pub jobs: VecDeque<Job>,
    pub local_jobs: Vec<(usize, Child)>,
    pub slurm_jobs: Vec<(usize, String)>,
    pub running_cacheable: HashSet<String>,
    pub must_checkpoint: bool,
    pub nodes: Vec<NodeCtx>,
}
impl Ctx {
    pub fn new(nodes: &[Node]) -> Result<Self, String> {
        let nnodes = nodes.len();
        let min = nodes.iter().map(|n| n.get_uid()).min();
        let max = nodes.iter().map(|n| n.get_uid()).max();
        let Some(min_uid) = min else {
            return Err("Failed to compute min uid".to_string());
        };
        let Some(max_uid) = max else {
            return Err("Failed to compute max uid".to_string());
        };
        if min_uid != 0 || max_uid != nnodes - 1 {
            let err = format!(
                "Min uid '{}', max uid '{}', and number of nodes '{}' do not correspond.",
                min_uid, max_uid, nnodes
            );
            return Err(err);
        };

        Ok(Self {
            updated: VecDeque::new(),
            jobs: VecDeque::new(),
            running_cacheable: HashSet::new(),
            local_jobs: Vec::new(),
            slurm_jobs: Vec::new(),
            must_checkpoint: true,
            nodes: vec![NodeCtx::default(); nnodes],
        })
    }

    pub fn from_checkpoint(nodes: &[Node], node_ctxs: Vec<NodeCtx>) -> Self {
        let mut ctx = Self {
            nodes: node_ctxs,
            updated: VecDeque::new(),
            jobs: VecDeque::new(),
            running_cacheable: HashSet::new(),
            local_jobs: Vec::new(),
            slurm_jobs: Vec::new(),
            must_checkpoint: false,
        };
        ctx.mark_all_local_running_jobs_as_failed(nodes);
        ctx.collect_running_slurm_jobs();
        ctx
    }

    pub fn nrunning(&self) -> usize {
        self.slurm_jobs.len() + self.local_jobs.len()
    }

    pub fn set_status(&mut self, uid: usize, status: Status) {
        self.nodes[uid].status = status;
        self.must_checkpoint = true;
    }

    pub fn set_status_deep(&mut self, uid: usize, status: Status) {
        for job in &mut self.nodes[uid].jobs {
            job.status = status.clone();
        }
        self.nodes[uid].status = status;
        self.must_checkpoint = true;
    }

    pub fn set_status_for_retry(&mut self, uid: usize) {
        let node = &mut self.nodes[uid];
        node.reset_status();
        self.must_checkpoint = true
    }

    pub fn reset_all_statuses(&mut self) {
        for node in &mut self.nodes {
            if let Status::Failed(_) | Status::Skipped = node.status {
                node.reset_status();
                node.try_num = 0;
            }
        }
        self.must_checkpoint = true
    }

    fn mark_all_local_running_jobs_as_failed(&mut self, nodes: &[Node]) {
        for node in nodes {
            if let Node::Task(task) = node
                && let Status::Running(JobType::Local(pid)) = self.nodes[task.uid].status
            {
                log::warn!("Marking running local task {} as failed.", task.uid);
                let failure = Failed::Job(JobType::Local(pid));
                submission::handle_retries(task, self, failure);
            }
        }
    }

    fn collect_running_slurm_jobs(&mut self) {
        for (uid, node) in self.nodes.iter().enumerate() {
            {
                if let Status::Pending(JobType::Slurm(job_id))
                | Status::Running(JobType::Slurm(job_id)) = &node.status
                {
                    log::debug!("Task {}: Collecting Slurm Job id '{job_id}'", uid);
                    self.slurm_jobs.push((uid, job_id.to_string()));
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::nodes::Task;
    use crate::model::schemas::Cmd;

    fn get_tasks() -> Vec<Task> {
        let task0 = Task::default();
        let mut task1 = Task::default();
        let mut task2 = Task::default();
        task1.uid = 1;
        task2.uid = 2;
        task1.cmd = Cmd::Sbatch;
        task2.cmd = Cmd::Sbatch;

        vec![task0, task1, task2]
    }

    fn get_nodes(tasks: Vec<Task>) -> Vec<Node> {
        tasks.into_iter().map(|t| Node::Task(t)).collect()
    }

    #[test]
    #[should_panic]
    fn fail_min_uid_check() {
        let mut tasks = get_tasks();
        tasks[0].uid = 1;
        let nodes = get_nodes(tasks);
        Ctx::new(&nodes).unwrap();
    }

    #[test]
    #[should_panic]
    fn fail_max_uid_check() {
        let mut tasks = get_tasks();
        tasks[2].uid = 3;
        let nodes = get_nodes(tasks);
        Ctx::new(&nodes).unwrap();
    }

    #[test]
    fn test_checkpoint_load() {
        let tasks = get_tasks();
        let nodes = get_nodes(tasks);

        let mut node_ctxs = vec![NodeCtx::default(); 3];
        node_ctxs[0].try_num = 1;
        node_ctxs[1].try_num = 1;
        node_ctxs[2].try_num = 1;
        node_ctxs[0].status = Status::Running(JobType::Local(123));
        node_ctxs[1].status = Status::Running(JobType::Slurm("123".into()));
        node_ctxs[2].status = Status::Pending(JobType::Slurm("456".into()));

        let ctx = Ctx::from_checkpoint(&nodes, node_ctxs);
        assert!(matches!(ctx.nodes[0].status, Status::Failed(_)));
        assert_eq!(ctx.slurm_jobs.len(), 2);
    }
}
