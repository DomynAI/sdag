// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::Ctx;
use crate::engine::polling::Poller;
use crate::engine::submission::{self, caching, inline};
use crate::model::nodes::{Node, Task};
use crate::model::schemas::ExecMode;
use crate::model::status::{Completed, Failed, JobType, Status};
use crate::settings::Cfg;
use std::process::Child;

pub struct LocalPoller<'a> {
    pub cfg: &'a Cfg,
}

impl<'a> Poller for LocalPoller<'a> {
    fn poll(&mut self, nodes: &[Node], ctx: &mut Ctx) {
        let mut local_jobs = Vec::new();
        while let Some((uid, child)) = ctx.local_jobs.pop() {
            if let Node::Task(task) = &nodes[uid] {
                self.check_status(child, task, ctx, &mut local_jobs);
            }
        }
        ctx.local_jobs = local_jobs;
    }
}

impl<'a> LocalPoller<'a> {
    fn check_status(
        &mut self,
        mut child: Child,
        task: &Task,
        ctx: &mut Ctx,
        local_jobs: &mut Vec<(usize, Child)>,
    ) {
        let uid = task.uid;
        let status = poll_local(&mut child);
        match status {
            Status::Running(_) => {
                log::info!("Local task '{uid}' is running");
                local_jobs.push((uid, child))
            }
            Status::Completed(_) => {
                log::info!("Local task '{uid}' completed");
                ctx.set_status(task.uid, status);
                self.handle_success(task, child.id(), ctx);
            }
            _ => {
                log::error!("Local task '{uid}' failed");
                let failure = Failed::Job(JobType::Local(child.id()));
                submission::handle_retries(task, ctx, failure);
            }
        }
    }

    fn handle_success(&self, task: &Task, pid: u32, ctx: &mut Ctx) {
        ctx.running_cacheable.remove(&task.name);
        ctx.updated.push_back(task.uid);
        if let ExecMode::Ext = task.mode
            && let Err(e) = inline::submit_save_ext_output(task, &self.cfg)
        {
            log::error!("Task {}: Failed to save external output - {e}", task.uid);
            ctx.set_status(task.uid, Status::Failed(Failed::Job(JobType::Local(pid))));
            return;
        }
        if task.cache.is_enabled()
            && let Err(e) = caching::submit_save_cache(task, &self.cfg)
        {
            log::error!("Task {}: Failed to save cache - {e}", task.uid);
        }
    }
}

fn poll_local(child: &mut Child) -> Status {
    let pid = child.id();
    let job_type = JobType::Local(pid);
    match child.try_wait() {
        Ok(Some(status)) => {
            if status.success() {
                log::info!("Local task with pid {} succeeded.", pid);
                Status::Completed(Completed::Job(job_type))
            } else {
                log::error!("Local task with pid {} failed.", pid);
                Status::Failed(Failed::Job(job_type))
            }
        }
        Ok(None) => {
            log::debug!("Local task with pid {} is running.", pid);
            Status::Running(job_type)
        }
        Err(e) => {
            log::error!("Failed to fetch status for local process {} - {e}", pid);
            Status::Failed(Failed::Job(job_type))
        }
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use std::process::Command;

    fn get_task(uid: usize) -> Task {
        let mut task = Task::default();
        task.uid = uid;
        task
    }

    #[test]
    fn test_success_poll() {
        let mut child = Command::new("true").spawn().unwrap();
        child.wait().unwrap();
        let status = poll_local(&mut child);
        assert!(matches!(status, Status::Completed(Completed::Job(_))));
    }

    #[test]
    fn test_poll() {
        let cfg = Cfg::default();
        let nodes = vec![Node::Task(get_task(0))];
        let mut ctx = Ctx::new(&nodes).unwrap();

        ctx.nodes[0].try_num = 1;
        ctx.must_checkpoint = false;

        let mut child = Command::new("true").spawn().unwrap();
        child.wait().unwrap();
        ctx.local_jobs.push((0, child));

        let mut poller = LocalPoller { cfg: &cfg };
        poller.poll(&nodes, &mut ctx);

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Completed(Completed::Job(_))
        ));
        assert!(ctx.must_checkpoint)
    }

    #[test]
    fn test_poll_failed() {
        let cfg = Cfg::default();
        let nodes = vec![Node::Task(get_task(0))];
        let mut ctx = Ctx::new(&nodes).unwrap();
        ctx.nodes[0].try_num = 1;
        ctx.must_checkpoint = false;

        let mut child = Command::new("bash").arg("exit").arg("1").spawn().unwrap();
        child.wait().unwrap();
        ctx.local_jobs.push((0, child));

        let mut poller = LocalPoller { cfg: &cfg };
        poller.poll(&nodes, &mut ctx);

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Failed(Failed::Job(_))
        ));
        assert!(ctx.must_checkpoint)
    }
}
