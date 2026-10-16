// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::{Ctx, NodeCtx};
use crate::engine::submission::jobs::{submit_local_blocking, submit_slurm};
use crate::model::nodes::{Node, Task};
use crate::model::schemas::{Cmd, DAGMeta};
use crate::settings::{self, Cfg};
use crate::store::workdirs::{self, DirPaths};
use log;
use serde_json::{self, Value};
use std::collections::HashMap;
use std::time::Duration;
use uuid::Uuid;

pub fn run_task(
    task_serialized: &str,
    slurm_grace_period: usize,
    max_concurrent_runs: usize,
    time_between_polls: u64,
    log_level: &str,
) {
    let task: Task = serde_json::from_str(task_serialized).expect("Failed to parse task");
    let meta = DAGMeta {
        pipeline_name: task.pipeline_name.clone(),
        hash: get_runtask_hash(&task.name),
        code_hash: String::new(),
        timestamp: settings::get_timestamp(),
        extra: Value::Null,
        import_path: task.pipeline_name.clone(),
        kwargs: HashMap::new(),
    };

    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    let paths = DirPaths::new(&homedir, &meta.pipeline_name, &meta.hash);
    let cfg = Cfg {
        homedir,
        dagdir: paths.dagdir,
        cachedir: paths.cachedir,
        dag_code_hash: meta.code_hash.clone(),
        local_cachedir: paths.local_cachedir,
        timestamp: settings::get_timestamp(),
        grace_period: slurm_grace_period,
        max_dagdirs: max_concurrent_runs,
        sleep_time: Duration::from_secs(time_between_polls),
        log_level: log_level.to_string(),
        max_concurrency: 1,
        fail_fast: false,
    };

    let nodes = vec![Node::Task(task.clone())];
    let mut ctx = Ctx::new(&nodes).expect("Failed to create context from task");
    workdirs::create_dir_structure(&cfg, &nodes).expect("Failed to create directories");
    submit_job(&task, &cfg, &meta, &mut ctx.nodes[0]);
}

fn submit_job(task: &Task, cfg: &Cfg, meta: &DAGMeta, node_ctx: &mut NodeCtx) {
    node_ctx.try_num = 1;
    match &task.cmd {
        Cmd::Sbatch => match submit_slurm(task, cfg, meta, node_ctx) {
            Ok(job_id) => log::info!("Submitted job '{job_id}'"),
            Err(e) => log::error!("Job submission failed - {e}"),
        },
        Cmd::Bash => match submit_local_blocking(task, 1, cfg, meta) {
            Ok(output) => {
                if !output.status.success() {
                    log::error!("Job terminated with non-zero exit status");
                } else {
                    log::info!("Job successfully completed.");
                }
            }
            Err(e) => log::error!("Job failed - {e}"),
        },
    }
}

fn get_runtask_hash(task_name: &str) -> String {
    let long_hash = Uuid::new_v4().to_string();
    let short_hash: String = long_hash.chars().take(8).collect();
    format!("{}-{}", task_name, short_hash)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_runtask_hash() {
        let task_name = "name".into();
        let runtask_hash = get_runtask_hash(task_name);
        // name + - + <8-letter-hash>
        assert_eq!(runtask_hash.chars().count(), 13);
    }
}
