// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::{context::Ctx, scheduler};
use crate::model::dag_setup;
use crate::settings::{self, Cfg};
use crate::store::checkpoint_validation::CheckpointValidator;
use crate::store::state;
use crate::store::workdirs::{self, DirPaths};
use std::path::PathBuf;
use std::time::Duration;

#[allow(clippy::too_many_arguments)]
pub fn run(
    pipeline_path: &str,
    max_concurrency: usize,
    time_between_polls: u64,
    slurm_grace_period: usize,
    max_concurrent_runs: usize,
    log_level: &str,
    fail_fast: bool,
    cache_lock: bool,
) {
    let pipeline_path = PathBuf::from(pipeline_path);
    let dag = state::read_dag(&pipeline_path).expect("Failed to read DAG");
    dag_setup::validate_dag(&dag.nodes).expect("Failed pipeline validation");
    log::info!(
        "Running pipeline '{}' with hash '{}'",
        dag.meta.pipeline_name,
        dag.meta.hash
    );

    let (meta, mut nodes) = (dag.meta, dag.nodes);
    nodes.sort_by_key(|n| n.get_uid());

    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    let paths = DirPaths::new(&homedir, &meta.pipeline_name, &meta.hash);
    let cfg = Cfg {
        homedir,
        dagdir: paths.dagdir,
        cachedir: paths.cachedir,
        local_cachedir: paths.local_cachedir,
        dag_code_hash: meta.code_hash.to_string(),
        timestamp: settings::get_timestamp(),
        grace_period: slurm_grace_period,
        max_dagdirs: max_concurrent_runs,
        max_concurrency,
        sleep_time: Duration::from_secs(time_between_polls),
        log_level: log_level.to_string(),
        fail_fast,
        cache_lock,
    };

    dag_setup::add_children(&mut nodes);
    dag_setup::compute_positions(&mut nodes).expect("Failed to compute positions");
    workdirs::create_dir_structure(&cfg, &nodes).expect("Failed to create dagdir");
    if let Err(e) = state::copy_dag_in_dagdir(&pipeline_path, &cfg.dagdir) {
        log::error!("Failed to copy DAG into the DAG directory - {e}");
    }

    let mut ctx = Ctx::new(&nodes).unwrap();
    scheduler::scheduling_loop(&nodes, &mut ctx, &cfg, &meta);
}

#[allow(clippy::too_many_arguments)]
pub fn restart_run(
    name: &str,
    hash: &str,
    max_concurrency: usize,
    time_between_polls: u64,
    retry: bool,
    log_level: &str,
    fail_fast: bool,
    cache_lock: bool,
) {
    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    let Some(path) = workdirs::find_pipeline_folder(&homedir, name, hash) else {
        log::warn!("No '{}' pipeline runs found for hash '{}'", name, hash);
        return;
    };

    let ckpt = state::read_chekpoint(&path).expect("Failed to read checkpoint");
    let meta = ckpt.meta.into_owned();
    let nodes = ckpt.nodes.into_owned();
    let mut cfg = ckpt.cfg.into_owned();
    let node_ctxs = ckpt.node_ctxs.into_owned();
    let mut ctx = Ctx::from_checkpoint(node_ctxs);

    cfg.max_concurrency = max_concurrency;
    cfg.sleep_time = Duration::from_secs(time_between_polls);
    cfg.log_level = log_level.to_string();
    cfg.fail_fast = fail_fast;
    cfg.cache_lock = cache_lock;

    ctx.mark_all_local_running_jobs_as_failed(&nodes, &cfg);
    if retry {
        log::info!("Retry enabled by user");
        ctx.reset_all_statuses();
    }
    ctx.restore_running_cacheable(&nodes, &cfg);

    log::info!("Start checkpoint validation");
    let validator = CheckpointValidator { cfg: &cfg };
    validator
        .validate_checkpoint(&nodes, &ctx)
        .expect("Failed checkpoint validation");
    log::info!("Checkpoint successfully validated");
    dag_setup::validate_dag(&nodes).expect("Failed pipeline validation");

    scheduler::scheduling_loop(&nodes, &mut ctx, &cfg, &meta);
}
