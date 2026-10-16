# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

def run(
    pipeline_path: str,
    max_concurrency: int,
    time_between_polls: int,
    log_level: str,
    slurm_grace_period: int,
    max_concurrent_runs: int,
    fail_fast: bool,
) -> None: ...
def restart_run(
    pipeline_name: str,
    pipeline_hash: str,
    max_concurrency: int,
    time_between_polls: int,
    log_level: str,
    retry: bool,
    fail_fast: bool,
) -> None: ...
def kill_run(
    pipeline_name: str, pipeline_hash: str, log_level: str
) -> None: ...
def prune_cache(
    task_name: str,
    pipeline_name: str | None,
    allow_full_prune: bool,
    log_level: str,
) -> None: ...
def view_pipeline(mermaid: str, log_level: str) -> None: ...
def run_single_task(
    task_serialized: str,
    log_level: str,
    time_between_polls: int,
    slurm_grace_period: int,
    max_concurrent_runs: int,
) -> None: ...
def print_pipeline_list(names: list[str], paths: list[str]) -> None: ...
def print_runs(pipeline_name: str, log_level: str) -> None: ...
def describe_pipeline(pipeline_path: str, log_level: str) -> None: ...
def print_status(
    pipeline_name: str, pipeline_hash: str, log_level: str
) -> None: ...
