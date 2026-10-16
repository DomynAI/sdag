# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""sdag entrypoints."""

import logging

from sdag.discovery import add_cwd_to_path
from sdag.settings import configure_logging

logger = logging.getLogger(__name__)


def cli():
    """CLI entrypoint."""
    from sdag.detach import detach_command
    from sdag.exceptions import CLIError
    from sdag.parser import ExtraArgumentParser, ParserBuilder

    add_cwd_to_path()
    parser = (
        ParserBuilder()
        .add_version()
        .add_compile_subparser()
        .add_run_subparser()
        .add_restart_subparser()
        .add_retry_subparser()
        .add_kill_subparser()
        .add_prune_subparser()
        .add_runtask_subparser()
        .add_view_subparser()
        .add_list_subparser()
        .add_describe_subparser()
        .add_status_subparser()
        .get_parser()
    )

    args, extras = parser.parse_known_args()
    extra_parser = ExtraArgumentParser()
    extra_args = extra_parser.parse(extras)
    if "log_level" not in args or "fn" not in args:
        raise CLIError

    if args.__dict__.get("detach", False):
        detach_command()
        return

    args.fn(args, extra_args)


def sdag_execute(configure_logger: bool = True) -> None:  # noqa: FBT002
    """Task entry point.

    This is the function called by script to run wrapping tasks.
    It is also possible to use the `sdag-execute` command.

    Args:
        configure_logger (bool): Whether to configure the default
            logger. Defaults to True.
    """
    import asyncio
    import inspect
    import json
    from time import perf_counter

    from sdag.io import IOHandler, find_and_import_task
    from sdag.settings import get_cached_settings

    add_cwd_to_path()
    start = perf_counter()
    settings = get_cached_settings()

    if configure_logger:
        configure_logging(settings.sdag_log_level)

    logger.info(
        "Task: '%s'\nFunction: '%s'\nNode: '%s'"
        "\nPipeline: '%s'\nTry number: '%s'",
        settings.sdag_task_name,
        settings.sdag_task_fn,
        settings.sdag_uid,
        settings.sdag_subpipeline_name,
        settings.sdag_try_num,
    )

    if settings.is_job_array():
        logger.info(
            "Starting job '%s' of array across field '%s'."
            " Shards are collected in '%s'.",
            settings.slurm_array_task_id,
            settings.sdag_each_key,
            settings.sdag_shard_path,
        )

    handler = IOHandler(
        uid=settings.sdag_uid,
        pipeline_dir=settings.sdag_pipeline_dir,
        shard_path=settings.sdag_shard_path,
        task_id=settings.slurm_array_task_id,
        each_key=settings.sdag_each_key,
    )

    task = find_and_import_task(
        task_name=settings.sdag_task_fn,
        pipeline_name=settings.sdag_pipeline_name,
        subpipeline_name=settings.sdag_subpipeline_name,
        import_path=settings.sdag_import_path,
        input_kwargs=settings.sdag_input_kwargs,
    )
    logger.info("Found task '%s'", task.name)
    sig = inspect.signature(task.fn)
    if settings.is_job_array():
        input_kwargs = handler.get_array_input(sig)
    else:
        input_kwargs = handler.get_input(sig)

    logger.info("Input values:\n%s", json.dumps(input_kwargs, indent=4))
    artifacts = handler.get_artifacts(sig, input_kwargs)
    logger.info("Artifacts:\n%s", handler.serialize_artifacts(artifacts))

    handler.cast_values(sig, input_kwargs)
    logger.info("Starting task execution")

    if inspect.iscoroutinefunction(task.fn):
        output = asyncio.run(task.fn(**input_kwargs))
    else:
        output = task.fn(**input_kwargs)

    logger.info("Output values:\n%s", json.dumps(output, indent=4))

    if settings.is_job_array():
        handler.serialize_array_output(output, artifacts)
    else:
        handler.serialize_output(output, artifacts)

    end = perf_counter()
    logger.info(
        "Task '%s' completed. Elapsed time: %s s",
        settings.sdag_task_name,
        round(end - start, 2),
    )
