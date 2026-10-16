// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
mod banner;
mod commands;
mod engine;
mod model;
mod settings;
mod store;

#[pymodule]
mod core {
    use super::*;

    #[pyfunction]
    #[pyo3(signature = (
        pipeline_path: "str",
        max_concurrency: "int",
        time_between_polls: "int",
        log_level: "str",
        slurm_grace_period: "int",
        max_concurrent_runs: "int",
        fail_fast: "bool",
    ) -> "None")]
    pub fn run(
        pipeline_path: &str,
        max_concurrency: usize,
        time_between_polls: u64,
        log_level: &str,
        slurm_grace_period: usize,
        max_concurrent_runs: usize,
        fail_fast: bool,
    ) {
        settings::configure_logging(log_level);
        commands::run(
            pipeline_path,
            max_concurrency,
            time_between_polls,
            slurm_grace_period,
            max_concurrent_runs,
            log_level,
            fail_fast,
        )
    }

    #[pyfunction]
    #[pyo3(signature =(
        pipeline_name: "str",
        pipeline_hash: "str",
        max_concurrency:"int",
        time_between_polls:"int",
        log_level: "str",
        retry: "bool",
        fail_fast: "bool",
    ) -> "None")]
    pub fn restart_run(
        pipeline_name: &str,
        pipeline_hash: &str,
        max_concurrency: usize,
        time_between_polls: u64,
        log_level: &str,
        retry: bool,
        fail_fast: bool,
    ) {
        settings::configure_logging(log_level);
        commands::restart_run(
            pipeline_name,
            pipeline_hash,
            max_concurrency,
            time_between_polls,
            retry,
            log_level,
            fail_fast,
        );
    }

    #[pyfunction]
    #[pyo3(signature=(
        pipeline_name: "str",
        pipeline_hash: "str",
        log_level: "str",
    ) -> "None")]
    pub fn kill_run(pipeline_name: &str, pipeline_hash: &str, log_level: &str) {
        settings::configure_logging(log_level);
        commands::create_kill_lock(pipeline_name, pipeline_hash);
    }

    #[pyfunction]
    #[pyo3(signature=(
        task_name: "str",
        pipeline_name: "str | None",
        allow_full_prune: "bool",
        log_level: "str"
    ) -> "None")]
    pub fn prune_cache(
        task_name: &str,
        pipeline_name: Option<&str>,
        allow_full_prune: bool,
        log_level: &str,
    ) {
        settings::configure_logging(log_level);
        commands::prune_cache(task_name, pipeline_name, allow_full_prune);
    }

    #[pyfunction]
    #[pyo3(signature=(
        mermaid: "str",
        log_level: "str",
    ) -> "None")]
    pub fn view_pipeline(mermaid: &str, log_level: &str) {
        settings::configure_logging(log_level);
        commands::view_pipeline(mermaid);
    }

    #[pyfunction]
    #[pyo3(signature=(
        task_serialized: "str",
        log_level: "str",
        time_between_polls: "int",
        slurm_grace_period: "int",
        max_concurrent_runs: "int",
    ) -> "None")]
    pub fn run_single_task(
        task_serialized: &str,
        log_level: &str,
        time_between_polls: u64,
        slurm_grace_period: usize,
        max_concurrent_runs: usize,
    ) {
        settings::configure_logging(log_level);
        commands::run_task(
            task_serialized,
            slurm_grace_period,
            max_concurrent_runs,
            time_between_polls,
            log_level,
        );
    }

    #[pyfunction]
    #[pyo3(signature=(
        names: "list[str]",
        paths: "list[str]",
    ) -> "None")]
    pub fn print_pipeline_list(names: Vec<String>, paths: Vec<String>) {
        commands::print_pipelines(&names, &paths);
    }

    #[pyfunction]
    #[pyo3(signature=(
        pipeline_name: "str",
        log_level: "str",
    ) -> "None")]
    pub fn print_runs(pipeline_name: &str, log_level: &str) {
        settings::configure_logging(log_level);
        if let Err(e) = commands::print_runs(pipeline_name) {
            log::error!("Failed to retrieve data - {e}");
        }
    }

    #[pyfunction]
    #[pyo3(signature = (
        pipeline_path: "str",
        log_level: "str",
    ) -> "None")]
    pub fn describe_pipeline(pipeline_path: &str, log_level: &str) {
        settings::configure_logging(log_level);
        commands::describe_pipeline(pipeline_path)
    }

    #[pyfunction]
    #[pyo3(signature=(
        pipeline_name: "str",
        pipeline_hash: "str",
        log_level: "str",
    ) -> "None")]
    pub fn print_status(pipeline_name: &str, pipeline_hash: &str, log_level: &str) {
        settings::configure_logging(log_level);
        if let Err(e) = commands::print_status(pipeline_name, pipeline_hash) {
            log::error!("Failed to print status - {e}");
        }
    }
}
