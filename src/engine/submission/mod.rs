// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

pub mod cache_lock;
pub mod caching;
pub mod inline;
pub mod jobs;
use crate::engine::context::{Ctx, Job};
use crate::model::nodes::{Node, Task};
use crate::model::schemas::{Cmd, DAGMeta};
use crate::model::status::{Completed, Failed, JobType, Status};
use crate::settings::Cfg;
use crate::store::workdirs;
use std::cmp::Reverse;
use std::error::Error;

use std::collections::VecDeque;

pub fn handle_retries(task: &Task, ctx: &mut Ctx, failure: Failed, cfg: &Cfg) {
    if task.cache.is_enabled() {
        cache_lock::unlock_cacheable_task(task, ctx, cfg);
    }
    let try_num = &ctx.nodes[task.uid].try_num;
    if *try_num > task.retries {
        log::error!(
            "Task '{}': Maximum number of retries '{}' reached, marking as failed.",
            task.uid,
            task.retries
        );
        ctx.set_status(task.uid, Status::Failed(failure));
        ctx.updated.push(Reverse((task.position, task.uid)));
        return;
    }
    log::warn!(
        "Task '{}' failed, scheduling retry '{}/{}'.",
        task.uid,
        try_num,
        task.retries,
    );
    ctx.set_status_for_retry(task.uid);
    ctx.jobs.push_back(Job::Task(task.uid));
}

pub struct Submitter<'a> {
    pub cfg: &'a Cfg,
    pub meta: &'a DAGMeta,
    pub held_jobs: VecDeque<Job>,
}

impl<'a> Submitter<'a> {
    pub fn new(cfg: &'a Cfg, meta: &'a DAGMeta) -> Self {
        Self {
            cfg,
            meta,
            held_jobs: VecDeque::new(),
        }
    }

    pub fn submit(&mut self, nodes: &[Node], ctx: &mut Ctx) {
        while let Some(job) = self.held_jobs.pop_front() {
            ctx.jobs.push_front(job);
        }

        while let Some(job) = ctx.jobs.pop_front() {
            match job {
                Job::Task(uid) => {
                    if let Node::Task(task) = &nodes[uid] {
                        self.handle_task_submission(task, ctx)
                    }
                }
                Job::ValidateCache(uid, already_checked) => {
                    if let Node::Task(task) = &nodes[uid] {
                        self.handle_cache_validation(task, ctx, &already_checked);
                    }
                }
            }
        }
    }

    fn handle_task_submission(&mut self, task: &Task, ctx: &mut Ctx) {
        let nrunning = ctx.nrunning();
        if self.cfg.max_concurrency != 0 && nrunning >= self.cfg.max_concurrency {
            log::info!(
                "Holding back task '{}' as the number of running \
                jobs '{}' has reached the max concurrency '{}'",
                task.uid,
                nrunning,
                self.cfg.max_concurrency
            );
            self.held_jobs.push_back(Job::Task(task.uid));
            return;
        }

        if let Some(uid) = cache_lock::find_running_duplicate(task, ctx, self.cfg) {
            log::info!(
                "Holding back task '{}': waiting for matching task '{uid}'",
                task.uid
            );
            self.held_jobs
                .push_back(Job::ValidateCache(task.uid, false));
            return;
        }

        ctx.nodes[task.uid].try_num += 1;
        let res = match &task.cmd {
            Cmd::Sbatch => self.submit_slurm(task, ctx),
            Cmd::Bash => self.submit_local(task, ctx),
        };

        if let Err(e) = res {
            log::error!("Task '{}': submission failed - {e}", task.uid);
            let failure = Failed::Generic;
            handle_retries(task, ctx, failure, self.cfg);
        }

        if task.cache.is_enabled() && ctx.nodes[task.uid].status.is_running() {
            log::debug!("Task {} marked as running cacheable", task.uid);
            let cache_path = workdirs::get_task_cache_path(task, self.cfg);
            let running = ctx.running_cacheable.entry(cache_path).or_default();
            running.push(task.uid);
        }
    }

    fn submit_local(&mut self, task: &Task, ctx: &mut Ctx) -> Result<(), Box<dyn Error>> {
        let try_num = ctx.nodes[task.uid].try_num;
        let child = jobs::submit_local(task, try_num, self.cfg, self.meta)?;
        let pid = child.id();

        log::info!("Task '{}': Submitted process with pid '{}'", task.uid, pid);
        ctx.local_jobs.push((task.uid, child));
        ctx.set_status(task.uid, Status::Running(JobType::Local(pid)));

        Ok(())
    }

    fn submit_slurm(&mut self, task: &Task, ctx: &mut Ctx) -> Result<(), Box<dyn Error>> {
        let node_ctx = &mut ctx.nodes[task.uid];
        let job_id = jobs::submit_slurm(task, self.cfg, self.meta, node_ctx)?;
        log::info!("Task '{}': Submitted job_id '{}'", task.uid, job_id);
        ctx.slurm_jobs.push((task.uid, job_id.to_string()));
        ctx.set_status(task.uid, Status::Pending(JobType::Slurm(job_id)));

        Ok(())
    }

    fn handle_cache_validation(&mut self, task: &Task, ctx: &mut Ctx, already_checked: &bool) {
        log::info!("checking task {} cache", task.uid);
        if !already_checked && caching::submit_validate_cache(task, self.cfg) {
            ctx.set_status(task.uid, Status::Completed(Completed::Cached));
            ctx.updated.push(Reverse((task.position, task.uid)));
            return;
        }
        ctx.set_status(task.uid, Status::ReadyForSubmission);
        ctx.jobs.push_back(Job::Task(task.uid));
    }
}
