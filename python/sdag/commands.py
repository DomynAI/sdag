# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""CLI commands.

Commands executed through the CLI. It's the point
of contact between the Python API and the Rust core.
"""

import json
import logging
from argparse import Namespace
from pathlib import Path
from typing import Any

import sdag.core as core
from sdag.cache_pruning import (
    find_all_cacheable_tasks,
    find_cascade_cacheable_tasks,
    find_matching_cacheable_tasks,
)
from sdag.compiler import master
from sdag.discovery import find_all_pipelines, find_pipeline_by_name
from sdag.exceptions import DAGNotFoundError, ExtraCLIArgsError
from sdag.models import DAG, Kwarg, TaskNode
from sdag.pyproj import apply_pyproj_configs, apply_pyproj_to_task, get_pyproj
from sdag.settings import configure_logging
from sdag.wrappers import Task

logger = logging.getLogger(__name__)


def compile_and_return_dag(
    path: str, extra_metadata: Any, input_kwargs: dict[str, Any]
) -> DAG:
    """Compile a pipeline.

    Args:
        path (str): Pipeline name or import string.
        extra_metadata (Any): Extra metadata that will
            be attached to the pipeline.
        input_kwargs (dict[str, Any]): Pipeline input kwargs.

    Returns:
        DAG: Compiled graph.
    """
    logger.info("Compiling pipeline '%s'", path)
    pipeline = find_pipeline_by_name(path)
    dag = pipeline.compile(path, **input_kwargs)
    dag.meta.code_hash = pipeline.compute_code_hash()
    dag.meta.kwargs |= input_kwargs
    if extra_metadata is not None:
        dag.meta.extra = json.loads(extra_metadata)

    cfg = get_pyproj()
    apply_pyproj_configs(dag, cfg)

    logger.info("Compiled pipeline '%s'", path)

    return dag


def _find_compiled_path(path: str) -> Path:
    """Find the JSON file path.

    The pyproject settings are used if the path is relative.

    Args:
        path (str): JSON file path.

    Returns:
        Path: Path used to read the compiled pipeline.
    """
    if "/" in path:
        return Path(path)
    pyproj = get_pyproj()
    if not pyproj.prepend_compiled_dagdir:
        return Path(path)
    return Path(pyproj.compiled_dagdir) / path


def _parse_compiled_pipeline(path: str) -> DAG:
    """Parse a compiled JSON.

    Args:
        path (str): User-selected path.

    Returns:
        DAG: Parsed pipeline.
    """
    compiled_path = _find_compiled_path(path)
    with compiled_path.open() as f:
        data = json.load(f)
    return DAG.model_validate(data, by_alias=True)


def _get_dag_from_name_import_or_json(
    path: str, extra_metadata: Any, input_kwargs: dict[str, Any]
) -> DAG:
    """Flexible way to import a pipeline.

    Args:
        path (str): Pipeline name or import string or JSON path.
        extra_metadata (Any): Extra metadata, only relevant if
            the pipeline is not read from a JSON.
        input_kwargs (dict[str, Any]): Pipeline input kwargs,
            only relevant if the pipeline is not read from
            a JSON.

    Returns:
        DAG: Parsed or compiled pipeline.
    """
    if path.endswith(".json"):
        dag = _parse_compiled_pipeline(path)
        cfg = get_pyproj()
        apply_pyproj_configs(dag, cfg)
        return dag

    return compile_and_return_dag(
        path=path, extra_metadata=extra_metadata, input_kwargs=input_kwargs
    )


def get_task(name: str, pipeline_name: str) -> Task:
    """Import a task.

    Args:
        name (str): Task name.
        pipeline_name (str): Name of the pipeline using the task.

    Raises:
        DAGNotFoundError: The task cannot be found.

    Returns:
        Task: Task.
    """
    pipeline = find_pipeline_by_name(pipeline_name)
    if name in pipeline.tasks:
        return pipeline.tasks[name]
    if name in master.tasks:
        return master.tasks[name]

    msg = f"Task '{name}' of pipeline '{pipeline_name}' not found"
    raise DAGNotFoundError(msg)


def compile_pipeline(args: Namespace, extras: dict[str, Any]) -> Path:
    """Compile a pipeline.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra args turned into input kwargs.

    Returns:
        Path: Path where the compiled JSON has been saved.
    """
    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    dag = compile_and_return_dag(
        path=args.pipeline,
        extra_metadata=args.extra_metadata,
        input_kwargs=extras,
    )

    dag_json = dag.model_dump_json(indent=4, warnings="none", by_alias=True)
    dst_path = Path(pyproj.compiled_dagdir)
    dst_path.mkdir(parents=True, exist_ok=True)
    dag_name = dag.meta.pipeline_name
    dst_name = args.name if args.name is not None else dag_name
    dst_path = dst_path / f"{dst_name}.json"

    logger.info("Saving pipeline to '%s'", dst_path)
    with dst_path.open("w") as f:
        f.write(dag_json)

    return dst_path


def run_pipeline(args: Namespace, extras: dict[str, Any]) -> None:
    """Run a pipeline.

    Args:
        args (Namespace): Parsed arguments.
        extras (dict[str, Any]): Extra arguments only used
            if the pipeline must be compiled.
    """
    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    if args.pipeline.endswith(".json"):
        path = _find_compiled_path(args.pipeline)
    else:
        path = compile_pipeline(args, extras)

    core.run(
        pipeline_path=str(path),
        max_concurrency=pyproj.max_concurrency,
        time_between_polls=pyproj.time_between_polls,
        log_level=pyproj.log_level,
        slurm_grace_period=pyproj.slurm_grace_period,
        max_concurrent_runs=pyproj.max_concurrent_runs,
        fail_fast=pyproj.fail_fast,
        cache_lock=pyproj.cache_lock,
    )


def restart_run(args: Namespace, extras: dict[str, Any]) -> None:
    """Restart a run.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra args (not allowed).

    Raises:
        ExtraCLIArgsError: Extra argument used.
    """
    if extras:
        raise ExtraCLIArgsError(extras)

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    pipeline_name = args.pipeline
    if args.pipeline.endswith(".json"):
        dag = _parse_compiled_pipeline(args.pipeline)
        pipeline_name = dag.meta.pipeline_name

    core.restart_run(
        pipeline_name=pipeline_name,
        pipeline_hash=args.hash,
        max_concurrency=pyproj.max_concurrency,
        time_between_polls=pyproj.time_between_polls,
        log_level=pyproj.log_level,
        retry=False,
        fail_fast=pyproj.fail_fast,
        cache_lock=pyproj.cache_lock,
    )


def retry_run(args: Namespace, extras: dict[str, Any]) -> None:
    """Retry a run.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra args (not allowed).

    Raises:
        ExtraCLIArgsError: Extra argument used.
    """
    if extras:
        raise ExtraCLIArgsError(extras)

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    pipeline_name = args.pipeline
    if args.pipeline.endswith(".json"):
        dag = _parse_compiled_pipeline(args.pipeline)
        pipeline_name = dag.meta.pipeline_name

    core.restart_run(
        pipeline_name=pipeline_name,
        pipeline_hash=args.hash,
        max_concurrency=pyproj.max_concurrency,
        time_between_polls=pyproj.time_between_polls,
        log_level=pyproj.log_level,
        retry=True,
        fail_fast=pyproj.fail_fast,
        cache_lock=pyproj.cache_lock,
    )


def kill_pipeline(args: Namespace, extras: dict[str, Any]) -> None:
    """Kill a pipeline.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra args (not allowed).

    Raises:
        ExtraCLIArgsError: Extra argument used.
    """
    if extras:
        raise ExtraCLIArgsError(extras)

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    pipeline_name = args.pipeline
    if args.pipeline.endswith(".json"):
        dag = _parse_compiled_pipeline(args.pipeline)
        pipeline_name = dag.meta.pipeline_name

    core.kill_run(
        pipeline_name=pipeline_name,
        pipeline_hash=args.hash,
        log_level=pyproj.log_level,
    )


def prune_cache(args: Namespace, extras: dict[str, Any]) -> None:
    """Prune the cache of tasks or pipelines.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra args (not allowed).

    Raises:
        ExtraCLIArgsError: Extra argument used.
    """
    if args.pipeline is None and not args.tasks:
        raise ExtraCLIArgsError(extras)

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    if args.pipeline is None:
        core.prune_cache(
            tasks=args.tasks,
            pipeline_name=args.pipeline,
            log_level=pyproj.log_level,
        )
        return

    dag = _get_dag_from_name_import_or_json(
        path=args.pipeline,
        extra_metadata=args.extra_metadata,
        input_kwargs=extras,
    )
    if not args.tasks:
        tasks = find_all_cacheable_tasks(dag)
    elif args.cascade:
        tasks = find_cascade_cacheable_tasks(dag, args.tasks)
    else:
        tasks = find_matching_cacheable_tasks(dag, args.tasks)

    core.prune_cache(
        tasks=tasks,
        pipeline_name=dag.meta.pipeline_name,
        log_level=pyproj.log_level,
    )


def view_pipeline(args: Namespace, extras: dict[str, Any]) -> None:
    """Visualize a pipeline in the terminal.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra arguments only used
            if the pipeline is not read from JSON.
    """
    from sdag.visualization import MermaidGenerator

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    dag = _get_dag_from_name_import_or_json(
        path=args.pipeline,
        extra_metadata=args.extra_metadata,
        input_kwargs=extras,
    )

    mermaid_gen = MermaidGenerator(squeeze=args.squeeze)
    mermaid = mermaid_gen.generate_mermaid_string(dag)
    core.view_pipeline(mermaid=mermaid, log_level=pyproj.log_level)


def run_task(args: Namespace, extras: dict[str, Any]) -> None:
    """Run a single task without starting the scheduler.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra arguments used for compilation.
    """
    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    task = get_task(name=args.task, pipeline_name=args.pipeline)
    task = TaskNode(
        uid=0,
        root_uid=-1,
        name=task.name,
        pipeline_name=args.pipeline,
        fn_name=task.fn.__name__,
        cache=task.cache,
        code_hash=task.code_hash,
        mode=task.mode,
        cmd=task.cmd,
        scope=task.scope,
        retries=0,
        script=task.script,
        kwargs=[Kwarg(key=k, value=v) for k, v in extras.items()],
    )

    pyproj = get_pyproj()
    apply_pyproj_to_task(task, pyproj)
    task_serialized = task.model_dump_json(warnings="none", by_alias=True)
    core.run_single_task(
        task_serialized,
        log_level=pyproj.log_level,
        time_between_polls=pyproj.time_between_polls,
        slurm_grace_period=pyproj.slurm_grace_period,
        max_concurrent_runs=pyproj.max_concurrent_runs,
    )


def list_pipelines(args: Namespace, extras: dict[str, Any]) -> None:
    """List pipelines and runs.

    By default, pipelines are listed. If the pipeline name is
    specified, then run hashes are listed.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra arguments (not allowed)

    Raises:
        ExtraCLIArgsError: Extra argument used.
    """
    if extras:
        raise ExtraCLIArgsError(extras)

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    if args.pipeline is not None:
        core.print_runs(
            pipeline_name=args.pipeline, log_level=pyproj.log_level
        )
        return

    dags = find_all_pipelines()
    sorted_dags = sorted(dags.items(), key=lambda kv: kv[0])
    names = [name for name, _ in sorted_dags]
    paths = [path for _, path in sorted_dags]

    core.print_pipeline_list(names, paths)


def describe_pipeline(args: Namespace, extras: dict[str, Any]) -> None:
    """Describe a pipeline arguments, caching, and artifacts.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra arguments used for compiling.
    """
    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)

    if args.pipeline.endswith(".json"):
        path = _find_compiled_path(args.pipeline)
    else:
        path = compile_pipeline(args, extras)

    core.describe_pipeline(str(path), log_level=pyproj.log_level)


def print_status(args: Namespace, extras: dict[str, Any]) -> None:
    """Describe a pipeline arguments, caching, and artifacts.

    Args:
        args (Namespace): Parsed args.
        extras (dict[str, Any]): Extra arguments used for compiling.
    """
    if extras:
        raise ExtraCLIArgsError(extras)

    pyproj = get_pyproj()
    pyproj.join_cli_args(args)
    configure_logging(pyproj.log_level)
    core.print_status(
        args.pipeline, pipeline_hash=args.hash, log_level=pyproj.log_level
    )
