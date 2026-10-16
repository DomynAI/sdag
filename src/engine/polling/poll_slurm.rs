// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::{Ctx, JobArray, NodeCtx};
use crate::engine::polling::Poller;
use crate::engine::submission::{self, caching, inline};
use crate::model::nodes::{Node, Task};
use crate::model::responses::{SacctResponse, SqueueJob, SqueueResponse};
use crate::model::schemas::ExecMode;
use crate::model::status::{Completed, Failed, JobType, Status};
use crate::settings::Cfg;
use log;
use std::collections::HashMap;
use std::error::Error;
use std::process::Command;

pub struct SlurmPoller<'a> {
    pub cfg: &'a Cfg,
}

impl<'a> Poller for SlurmPoller<'a> {
    fn poll(&mut self, nodes: &[Node], ctx: &mut Ctx) {
        if ctx.slurm_jobs.len() == 0 {
            return;
        }
        let job_ids = get_job_ids(&ctx.slurm_jobs);
        let output = get_output_from_slurm(&job_ids);
        let slurm_jobs: Vec<_> = ctx.slurm_jobs.drain(..).collect();
        self.assign_status_to_tasks(output, nodes, &slurm_jobs, ctx);
    }
}

impl<'a> SlurmPoller<'a> {
    fn assign_status_to_tasks(
        &self,
        mut output: HashMap<String, HashMap<usize, Status>>,
        nodes: &[Node],
        jobs: &[(usize, String)],
        ctx: &mut Ctx,
    ) {
        for (uid, job_id) in jobs {
            let Some(node) = ctx.nodes.get_mut(*uid) else {
                continue;
            };
            let Some(statuses) = output.remove(job_id) else {
                for job in node.jobs.iter_mut() {
                    mark_job_missing(job, job_id, self.cfg.grace_period)
                }
                continue;
            };
            self.assign_status_to_inner_jobs(statuses, &mut node.jobs, job_id);
            let status = get_global_status(node, job_id);
            if let Node::Task(task) = &nodes[*uid] {
                self.handle_new_slurm_status(task, status, ctx);
            }
        }
    }

    fn assign_status_to_inner_jobs(
        &self,
        mut statuses: HashMap<usize, Status>,
        jobs: &mut [JobArray],
        job_id: &str,
    ) {
        for (task_id, job) in jobs.iter_mut().enumerate() {
            match statuses.remove(&task_id) {
                Some(status) => {
                    job.nmiss = 0;
                    job.status = status;
                }
                None => mark_job_missing(job, job_id, self.cfg.grace_period),
            }
        }
    }

    fn handle_new_slurm_status(&self, task: &Task, status: Status, ctx: &mut Ctx) {
        match &status {
            Status::Pending(JobType::Slurm(job_id)) => {
                ctx.slurm_jobs.push((task.uid, job_id.to_string()));
                if !matches!(&ctx.nodes[task.uid].status, Status::Pending(_)) {
                    ctx.set_status(task.uid, status);
                }
            }
            Status::Running(JobType::Slurm(job_id)) => {
                ctx.slurm_jobs.push((task.uid, job_id.to_string()));
                if !matches!(&ctx.nodes[task.uid].status, Status::Running(_)) {
                    ctx.set_status(task.uid, status);
                }
            }
            Status::Failed(failure) => {
                log::error!("Task - '{}' failed", task.uid);
                submission::handle_retries(task, ctx, failure.clone())
            }
            Status::Completed(Completed::Job(job_type)) => {
                let job_type = job_type.clone();
                self.handle_completed_task(task, status, job_type, ctx)
            }

            Status::NotSubmitted
            | Status::Skipped
            | Status::ReadyForSubmission
            | Status::Running(_)
            | Status::Pending(_)
            | Status::Completed(_) => {
                log::warn!("Task '{}': status {}", task.uid, status);
                ctx.set_status(task.uid, status);
                ctx.updated.push_back(task.uid);
            }
        }
    }

    fn handle_completed_task(&self, task: &Task, status: Status, job_type: JobType, ctx: &mut Ctx) {
        ctx.set_status(task.uid, status);
        ctx.running_cacheable.remove(&task.name);
        ctx.updated.push_back(task.uid);
        if let Err(e) = self.maybe_save_output(task) {
            log::error!("Task {}: Failed to save output - {e}", task.uid);
            ctx.set_status_deep(task.uid, Status::Failed(Failed::Job(job_type)));
            return;
        }
        if task.cache.is_enabled()
            && let Err(e) = caching::submit_save_cache(task, self.cfg)
        {
            log::error!("Task {}: Failed to save cache - {e}", task.uid);
        }
    }

    fn maybe_save_output(&self, task: &Task) -> Result<(), Box<dyn Error>> {
        if task.is_array() {
            inline::aggregate_array_output(task, &self.cfg)
        } else if let ExecMode::Ext = task.mode {
            inline::submit_save_ext_output(task, &self.cfg).map_err(|e| e.into())
        } else {
            Ok(())
        }
    }
}

fn get_job_ids(jobs: &[(usize, String)]) -> String {
    jobs.iter()
        .map(|x| x.1.as_str())
        .collect::<Vec<&str>>()
        .join(",")
}

fn get_output_from_slurm(job_ids: &str) -> HashMap<String, HashMap<usize, Status>> {
    let mut output = HashMap::new();
    let sacct_result = run_sacct(&job_ids);
    if let Ok(sacct_response) = sacct_result {
        read_sacct_status(sacct_response, &mut output);
    }

    let squeue_result = run_squeue(&job_ids);
    if let Ok(squeue_response) = squeue_result {
        read_squeue_status(squeue_response, &mut output);
    };
    output
}

fn run_sacct(job_ids: &str) -> Result<SacctResponse, Box<dyn Error>> {
    log::debug!("Fetching status from sacct");
    let output = Command::new("sacct")
        .arg("-j")
        .arg(job_ids)
        .arg("--json")
        .output()?;

    let stderr = String::from_utf8(output.stderr);
    if let Ok(msg) = stderr
        && msg.len() > 0
    {
        log::error!("Slurm stderr: {msg}")
    }

    let stdout = String::from_utf8(output.stdout)?;
    let response: SacctResponse = serde_json::from_str(&stdout)?;
    log::debug!("Slurm response:\n{response:?}");
    Ok(response)
}

fn run_squeue(job_ids: &str) -> Result<SqueueResponse, Box<dyn Error>> {
    log::debug!("Fetching status from squeue");
    let output = Command::new("squeue")
        .arg("-j")
        .arg(job_ids)
        .arg("--json")
        .output()?;

    let stderr = String::from_utf8(output.stderr);
    if let Ok(msg) = stderr
        && msg.len() > 0
    {
        log::error!("Slurm stderr: {msg}")
    }

    let stdout = String::from_utf8(output.stdout)?;
    let response: SqueueResponse = serde_json::from_str(&stdout)?;
    log::debug!("squeue response:\n{response:?}");
    Ok(response)
}

fn read_sacct_status(
    sacct_response: SacctResponse,
    output: &mut HashMap<String, HashMap<usize, Status>>,
) {
    for mut job in sacct_response.jobs {
        let job_id = job.get_job_id().to_string();
        if job.state.current.len() < 1 {
            log::warn!("sacct returned no current status for job_id {job_id}");
            continue;
        }
        let status_string = job.state.current.swap_remove(0);
        let status = get_status_from_string(&status_string, &job_id);
        let tasks = output.entry(job_id).or_insert_with(HashMap::new);
        let task_id = job.array.task_id.number;
        tasks.entry(task_id).or_insert(status.clone());
    }
}

fn read_squeue_status(
    squeue_response: SqueueResponse,
    output: &mut HashMap<String, HashMap<usize, Status>>,
) {
    for mut job in squeue_response.jobs {
        if job.job_state.len() < 1 {
            log::debug!("squeue did not return status for job_id {}", job.job_id);
            continue;
        }
        let task_ids = get_squeue_task_ids(&job);
        let job_id = job.job_id;
        let tasks = output.entry(job_id.clone()).or_insert_with(HashMap::new);
        let status_string = job.job_state.swap_remove(0);
        let status = get_status_from_string(&status_string, &job_id);
        for task_id in task_ids {
            tasks.insert(task_id, status.clone());
        }
    }
}

fn get_status_from_string(status_string: &str, job_id: &str) -> Status {
    let job_type = JobType::Slurm(job_id.to_string());
    match status_string {
        "COMPLETED" => Status::Completed(Completed::Job(job_type)),
        "CONFIGURING" | "PENDING" => Status::Pending(job_type),
        "RUNNING" | "COMPLETING" => Status::Running(job_type),
        _ => Status::Failed(Failed::Job(job_type)),
    }
}

fn get_squeue_task_ids(job: &SqueueJob) -> Vec<usize> {
    if job.array_task_id.set || job.array_task_string.len() == 0 {
        vec![job.array_task_id.number]
    } else {
        parse_array_task_string(&job.array_task_string)
    }
}
fn parse_array_task_string(s: &str) -> Vec<usize> {
    try_parse_array_task_string(s).unwrap_or_default()
}

fn try_parse_array_task_string(s: &str) -> Option<Vec<usize>> {
    let s = s.split('%').next()?; // drop the "%max_parallel" throttle
    let mut out = Vec::new();
    for part in s.split(',').filter(|p| !p.is_empty()) {
        let (range, step) = match part.split_once(':') {
            Some((r, st)) => (r, st.parse().ok()?),
            None => (part, 1),
        };
        if step == 0 {
            return None;
        }
        match range.split_once('-') {
            Some((a, b)) => out.extend((a.parse::<usize>().ok()?..=b.parse().ok()?).step_by(step)),
            None => out.push(range.parse().ok()?),
        }
    }
    Some(out)
}

fn mark_job_missing(job: &mut JobArray, job_id: &str, grace_period: usize) {
    log::warn!("Slurm response does not contain a task of job {job_id}");
    job.nmiss += 1;
    if job.nmiss >= grace_period {
        log::error!("Grace period reached, marking as failed");
        let job_type = JobType::Slurm(job_id.to_string());
        job.status = Status::Failed(Failed::Job(job_type));
        // Reset in case of retries
        job.nmiss = 0;
    }
}

fn get_global_status(node: &NodeCtx, job_id: &str) -> Status {
    let statuses: Vec<&Status> = node.jobs.iter().map(|t| &t.status).collect();
    let job = JobType::Slurm(job_id.to_string());
    if some_are_running(&statuses) {
        Status::Running(job)
    } else if all_are_completed(&statuses) {
        Status::Completed(Completed::Job(job))
    } else if all_final_some_failed(&statuses) {
        Status::Failed(Failed::Job(job))
    } else if all_final_some_skipped(&statuses) {
        Status::Skipped
    } else if some_are_final(&statuses) {
        Status::Running(job)
    } else if none_has_been_submitted(&statuses) {
        Status::ReadyForSubmission
    } else if at_most_pending(&statuses) {
        Status::Pending(job)
    } else {
        log::debug!(
            "job_id {job_id} statuses: {statuses:?}, \
            leaving status '{}' as is",
            node.status
        );
        node.status.clone()
    }
}

fn some_are_running(statuses: &[&Status]) -> bool {
    statuses.iter().any(|s| matches!(s, Status::Running(_)))
}

fn some_are_final(statuses: &[&Status]) -> bool {
    statuses.iter().any(|s| s.is_final())
}

fn all_are_completed(statuses: &[&Status]) -> bool {
    statuses.iter().all(|s| matches!(s, Status::Completed(_)))
}

fn all_final_some_failed(statuses: &[&Status]) -> bool {
    let is_final = statuses.iter().all(|s| s.is_final());
    let is_failed = statuses.iter().any(|s| matches!(s, Status::Failed(_)));
    is_final & is_failed
}

fn none_has_been_submitted(statuses: &[&Status]) -> bool {
    statuses.iter().all(|s| s.has_not_been_submitted())
}

fn at_most_pending(statuses: &[&Status]) -> bool {
    statuses
        .iter()
        .all(|s| s.has_not_been_submitted() | matches!(s, Status::Pending(_)))
}

fn all_final_some_skipped(statuses: &[&Status]) -> bool {
    let is_final = statuses.iter().all(|s| s.is_final());
    let is_skip = statuses.iter().any(|s| matches!(s, Status::Skipped));
    is_final & is_skip
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::context::Job;
    use crate::model::responses::{
        SacctArray, SacctJob, SacctState, SacctTaskId, SqueueArrayTaskId, SqueueJob,
    };
    use crate::model::schemas::{Cache, Cmd};
    use crate::store::workdirs::{DirPaths, FileNames};
    use std::collections::HashMap;
    use std::fs;
    use std::path::PathBuf;
    use std::{assert_matches, env};
    use uuid::Uuid;

    fn get_poller(cfg: &Cfg) -> SlurmPoller<'_> {
        SlurmPoller { cfg }
    }

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

    fn get_task(uid: usize) -> Task {
        let mut task = Task::default();
        task.cmd = Cmd::Sbatch;
        task.uid = uid;
        task
    }

    fn get_ctx(nodes: &[Node]) -> Ctx {
        let mut ctx = Ctx::new(nodes).unwrap();
        ctx.nodes[0].try_num = 1;
        ctx.must_checkpoint = false;
        ctx
    }

    #[test]
    fn test_get_status_from_string() {
        assert!(matches!(
            get_status_from_string("COMPLETED", "1"),
            Status::Completed(Completed::Job(_))
        ));
        assert!(matches!(
            get_status_from_string("PENDING", "1"),
            Status::Pending(JobType::Slurm(_))
        ));
        assert!(matches!(
            get_status_from_string("RUNNING", "1"),
            Status::Running(JobType::Slurm(_))
        ));
    }

    #[test]
    fn test_handle_pending_status() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);

        let task = get_task(0);
        let nodes = [Node::Task(task.clone())];
        let mut ctx = get_ctx(&nodes);
        poller.handle_new_slurm_status(
            &task,
            Status::Pending(JobType::Slurm("123".into())),
            &mut ctx,
        );

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Pending(JobType::Slurm(_))
        ));
        assert!(ctx.must_checkpoint);
    }

    #[test]
    fn test_constant_pending_status_does_not_trigger_checkpoint() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);

        let task = get_task(0);
        let nodes = [Node::Task(task.clone())];
        let constant_status = Status::Pending(JobType::Slurm("123".into()));
        let mut ctx = get_ctx(&nodes);
        ctx.nodes[0].status = constant_status.clone();
        poller.handle_new_slurm_status(&task, constant_status, &mut ctx);

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Pending(JobType::Slurm(_))
        ));
        assert!(!ctx.must_checkpoint);
    }

    #[test]
    fn test_constant_running_status_does_not_trigger_checkpoint() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);

        let task = get_task(0);
        let nodes = [Node::Task(task.clone())];
        let constant_status = Status::Running(JobType::Slurm("123".into()));
        let mut ctx = get_ctx(&nodes);
        ctx.nodes[0].status = constant_status.clone();
        poller.handle_new_slurm_status(&task, constant_status, &mut ctx);

        assert!(matches!(
            ctx.nodes[0].status,
            Status::Running(JobType::Slurm(_))
        ));
        assert!(!ctx.must_checkpoint);
    }

    #[test]
    fn test_handle_failed_status() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);

        let task = get_task(0);
        let nodes = [Node::Task(task.clone())];
        let mut ctx = get_ctx(&nodes);
        poller.handle_new_slurm_status(
            &task,
            Status::Failed(Failed::Job(JobType::Slurm("123".into()))),
            &mut ctx,
        );
        println!("{}", ctx.nodes[0].status);
        assert!(matches!(ctx.nodes[0].status, Status::Failed(_)));
        assert!(ctx.must_checkpoint);
    }

    #[test]
    fn test_handle_failed_status_with_retry() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);

        let mut task = get_task(0);
        task.retries = 1;

        let nodes = [Node::Task(task.clone())];
        let mut ctx = get_ctx(&nodes);
        poller.handle_new_slurm_status(
            &task,
            Status::Failed(Failed::Job(JobType::Slurm("123".into()))),
            &mut ctx,
        );

        let job = ctx.jobs.pop_front().unwrap();
        assert!(matches!(job, Job::Task(0)));
        assert!(ctx.must_checkpoint);
    }

    #[test]
    fn test_handle_completed_with_caching() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);
        let mut task = get_task(0);
        task.cache = Cache::Io;

        let nodes = [Node::Task(task.clone())];
        let mut ctx = get_ctx(&nodes);
        let src_dir = cfg.dagdir.join(task.uid.to_string());

        fs::create_dir_all(&src_dir).unwrap();
        fs::write(src_dir.join(FileNames::Input.as_str()), "").unwrap();
        fs::write(src_dir.join(FileNames::Output.as_str()), "").unwrap();
        fs::write(src_dir.join(FileNames::Meta.as_str()), "").unwrap();

        poller.handle_new_slurm_status(
            &task,
            Status::Completed(Completed::Job(JobType::Slurm("123".into()))),
            &mut ctx,
        );

        let cachedir = cfg
            .local_cachedir
            .join(&task.pipeline_name)
            .join(&task.name);

        assert!(cachedir.exists());
        assert!(ctx.must_checkpoint);
    }

    #[test]
    fn test_handle_completed_ext() {
        let cfg = get_cfg();
        let poller = get_poller(&cfg);
        let mut task = get_task(0);
        task.mode = ExecMode::Ext;
        task.cache = Cache::None;

        let nodes = [Node::Task(task.clone())];
        let mut ctx = get_ctx(&nodes);
        let taskdir = cfg.dagdir.join(task.uid.to_string());
        fs::create_dir_all(&taskdir).unwrap();

        poller.handle_new_slurm_status(
            &task,
            Status::Completed(Completed::Job(JobType::Slurm("123".into()))),
            &mut ctx,
        );

        let output = taskdir.join(FileNames::Output.as_str());
        assert!(output.exists());
        assert!(ctx.must_checkpoint);
    }

    #[test]
    fn test_parse_sacct() {
        let response = SacctResponse {
            jobs: vec![
                SacctJob {
                    job_id: "123".into(),
                    state: SacctState {
                        current: vec!["COMPLETED".into(), "???".into()],
                    },
                    array: SacctArray {
                        job_id: "0".into(),
                        task_id: SacctTaskId {
                            set: false,
                            number: 0,
                        },
                    },
                },
                SacctJob {
                    job_id: "456".into(),
                    state: SacctState {
                        current: vec!["FAILED".into()],
                    },
                    array: SacctArray {
                        job_id: "0".into(),
                        task_id: SacctTaskId {
                            set: false,
                            number: 0,
                        },
                    },
                },
                SacctJob {
                    job_id: "789".into(),
                    state: SacctState { current: vec![] },
                    array: SacctArray {
                        job_id: "0".into(),
                        task_id: SacctTaskId {
                            set: false,
                            number: 0,
                        },
                    },
                },
            ],
        };

        let mut output = HashMap::new();
        read_sacct_status(response, &mut output);

        let status_123 = output.get("123").unwrap();
        let status_456 = output.get("456").unwrap();
        let status_789 = output.get("789");
        assert_matches!(status_123[&0], Status::Completed(_));
        assert_matches!(status_456[&0], Status::Failed(_));
        assert_matches!(status_789, None);
    }

    #[test]
    fn test_parse_squeue() {
        let response = SqueueResponse {
            jobs: vec![
                SqueueJob {
                    job_id: "123".into(),
                    job_state: vec!["COMPLETED".into(), "???".into()],
                    array_task_string: "".into(),
                    array_task_id: SqueueArrayTaskId {
                        number: 0,
                        set: false,
                    },
                },
                SqueueJob {
                    job_id: "456".into(),
                    job_state: vec!["FAILED".into()],
                    array_task_string: "".into(),
                    array_task_id: SqueueArrayTaskId {
                        number: 0,
                        set: false,
                    },
                },
                SqueueJob {
                    job_id: "789".into(),
                    job_state: vec![],
                    array_task_string: "".into(),
                    array_task_id: SqueueArrayTaskId {
                        number: 0,
                        set: false,
                    },
                },
            ],
        };

        let mut output = HashMap::new();
        read_squeue_status(response, &mut output);

        let status_123 = output.get("123").unwrap();
        let status_456 = output.get("456").unwrap();
        let status_789 = output.get("789");
        assert_matches!(status_123[&0], Status::Completed(_));
        assert_matches!(status_456[&0], Status::Failed(_));
        assert_matches!(status_789, None);
    }

    #[test]
    fn test_parse_array_string() {
        let s = "1,2-4,6,8-9";
        let v = parse_array_task_string(s);
        assert_eq!(v, vec![1, 2, 3, 4, 6, 8, 9])
    }
    #[test]
    fn test_parse_array_string_with_step() {
        let s = "0,1-6:4";
        let v = parse_array_task_string(s);
        assert_eq!(v, vec![0, 1, 5])
    }

    fn get_node_ctx() -> NodeCtx {
        NodeCtx {
            try_num: 0,
            status: Status::NotSubmitted,
            jobs: vec![JobArray::default(); 2],
        }
    }

    #[test]
    fn test_running_global_status() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::Failed(Failed::Generic);
        node_ctx.jobs[1].status = Status::Running(JobType::Slurm("1".into()));

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::Running(_))
    }

    #[test]
    fn test_completed_global_status() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::Completed(Completed::Cached);
        node_ctx.jobs[1].status = Status::Completed(Completed::Job(JobType::Slurm("1".into())));

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::Completed(_))
    }

    #[test]
    fn test_failed_global_status() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::Completed(Completed::Cached);
        node_ctx.jobs[1].status = Status::Failed(Failed::Generic);

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::Failed(_))
    }

    #[test]
    fn test_skipped_global_status() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::Skipped;
        node_ctx.jobs[1].status = Status::Skipped;

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::Skipped)
    }

    #[test]
    fn test_running_partial_final_global_status() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::Skipped;
        node_ctx.jobs[1].status = Status::NotSubmitted;

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::Running(_))
    }

    #[test]
    fn test_ready_global_status() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::ReadyForSubmission;
        node_ctx.jobs[1].status = Status::NotSubmitted;

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::ReadyForSubmission)
    }

    #[test]
    fn test_at_most_pending() {
        let mut node_ctx = get_node_ctx();
        node_ctx.jobs[0].status = Status::ReadyForSubmission;
        node_ctx.jobs[1].status = Status::Pending(JobType::Slurm("1".into()));

        let status = get_global_status(&node_ctx, "1".into());
        assert_matches!(status, Status::Pending(_))
    }
}
