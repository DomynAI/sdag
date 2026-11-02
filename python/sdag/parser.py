# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""sdag parser."""

import json
import sys
from argparse import ArgumentParser, BooleanOptionalAction
from typing import Any

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from sdag._version import __version__
from sdag.commands import (
    compile_pipeline,
    describe_pipeline,
    kill_pipeline,
    list_pipelines,
    print_status,
    prune_cache,
    restart_run,
    retry_run,
    run_pipeline,
    run_task,
    view_pipeline,
)


class ParserBuilder:
    """Build the parser.

    Attributes:
        _parser (ArgumentParser): Main parser.
        _subparsers (_SubParsersAction[ArgumentParser]):
            Subparsers for the different commands.
    """

    def __init__(self):
        """Initialize the parser."""
        self._parser = ArgumentParser(
            description="sdag: DAGs for Slurm.",
            epilog=(
                "Check out https://domynai.github.io/sdag/cli/"
                " for more information."
            ),
        )
        self._subparsers = self._parser.add_subparsers(
            title="commands", metavar="<command>"
        )

    def add_version(self) -> Self:
        """Add versions.

        Returns:
            Self: Parser builder.
        """
        self._parser.add_argument(
            "-v",
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
        )

        return self

    def add_compile_subparser(self) -> Self:
        """Add the compile command.

        Returns:
            Self: Parser builder.
        """
        compile_parser = self._subparsers.add_parser(
            "compile",
            help="Compile a pipeline and save its JSON representation.",
        )

        compile_parser.add_argument(
            "pipeline",
            type=str,
            help=(
                "Pipeline name or import string (e.g., 'path.to:pipeline_fn')."
                " By default, pipelines are searched in './'. You can"
                " modify this behavior by setting an explicit 'dagdir' in"
                " the [tool.sdag] field of pyproject.toml."
            ),
        )

        self._add_compilation_args(compile_parser)
        self._add_log_level(compile_parser)
        self._add_detach(compile_parser)
        compile_parser.set_defaults(fn=compile_pipeline)

        return self

    def add_run_subparser(self) -> Self:
        """Add the run command.

        Returns:
            Self: Parser builder.
        """
        run_parser = self._subparsers.add_parser("run", help="Run a pipeline.")
        run_parser.add_argument(
            "pipeline",
            type=str,
            help=(
                "Pipeline name, import string (e.g., 'path.to:pipeline_fn'),"
                " or compiled JSON path. By default, pipelines are searched"
                " in the main project directory. You can modify this behavior"
                " by setting an explicit 'dagdir' in the [tool.sdag] field of"
                " pyproject.toml. If a compiled JSON path is given,"
                " compilation is skipped."
            ),
        )

        self._add_log_level(run_parser)
        self._add_compilation_args(run_parser)
        self._add_scheduler_args(run_parser)
        self._add_fail_fast_option(run_parser)
        self._add_detach(run_parser)
        run_parser.set_defaults(fn=run_pipeline)

        return self

    def add_restart_subparser(self) -> Self:
        """Add the restart subparser.

        Returns:
            Self: Parser.
        """
        restart_parser = self._subparsers.add_parser(
            "restart", help="Restart the scheduler of a previous run."
        )
        self._add_pipeline_name_and_hash_or_json(restart_parser)
        self._add_log_level(restart_parser)
        self._add_scheduler_args(restart_parser)
        self._add_fail_fast_option(restart_parser)
        self._add_detach(restart_parser)
        restart_parser.set_defaults(fn=restart_run)

        return self

    def add_retry_subparser(self) -> Self:
        """Add the retry subparser.

        Returns:
            Self: Parser.
        """
        restart_parser = self._subparsers.add_parser(
            "retry",
            help=(
                "Reset all failed and skipped tasks and restart a pipeline."
            ),
        )
        self._add_pipeline_name_and_hash_or_json(restart_parser)
        self._add_log_level(restart_parser)
        self._add_scheduler_args(restart_parser)
        self._add_fail_fast_option(restart_parser)
        self._add_detach(restart_parser)
        restart_parser.set_defaults(fn=retry_run)

        return self

    def add_kill_subparser(self) -> Self:
        """Add the pipeline kill command.

        Returns:
            Self: Parser builder.
        """
        kill_parser = self._subparsers.add_parser(
            "kill", help="Terminate a pipeline."
        )

        self._add_pipeline_name_and_hash_or_json(kill_parser)
        self._add_log_level(kill_parser)
        self._add_detach(kill_parser)
        kill_parser.set_defaults(fn=kill_pipeline)

        return self

    def add_prune_subparser(self) -> Self:
        """Add the cache prune command.

        Returns:
            Self: Parser builder.
        """
        prune_parser = self._subparsers.add_parser(
            "prune", help="Delete the cache of tasks or pipelines."
        )
        prune_parser.add_argument(
            "tasks",
            nargs="*",
            type=str,
            help=(
                "Task name(s). Set to 'all' to"
                " delete the entire sdag cache. If not provided, the"
                " cache of the entire pipeline is deleted."
            ),
        )

        prune_parser.add_argument(
            "-p",
            "--pipeline",
            type=str,
            nargs="?",
            help=(
                "Pipeline name, import string (e.g., 'path.to:pipeline_fn'),"
                " or compiled JSON path to skip compilation. If not set, the"
                " global task cache is deleted."
            ),
        )

        prune_parser.add_argument(
            "--cascade",
            action=BooleanOptionalAction,
            default=False,
            help=(
                "Delete the cache of all dependent nodes in the graph."
                " It is only considered if both tasks and pipeline are"
                " specified."
            ),
        )

        self._add_extra_metadata(prune_parser)
        self._add_log_level(prune_parser)
        self._add_detach(prune_parser)

        prune_parser.set_defaults(fn=prune_cache)

        return self

    def add_view_subparser(self) -> Self:
        """Add the view command.

        Returns:
            Self: Parser builder.
        """
        view_parser = self._subparsers.add_parser(
            "view", help="Print a pipeline graph in the terminal."
        )

        view_parser.add_argument(
            "pipeline",
            type=str,
            help=(
                "Pipeline name, import string (e.g., 'path.to:pipeline_fn'),"
                " or compiled JSON path to skip compilation."
            ),
        )

        view_parser.add_argument(
            "--squeeze",
            action=BooleanOptionalAction,
            default=False,
            help="Collapse inner pipelines into a unique node",
        )

        self._add_extra_metadata(view_parser)
        self._add_log_level(view_parser)
        self._add_detach(view_parser)
        view_parser.set_defaults(fn=view_pipeline)

        return self

    def add_runtask_subparser(self) -> Self:
        """Add subparser to run tasks.

        Returns:
            Self: Parser.
        """
        runtask_parser = self._subparsers.add_parser(
            "runtask", help="Run a specific task of a pipeline."
        )

        runtask_parser.add_argument(
            "task",
            type=str,
            help="Task name.",
        )

        runtask_parser.add_argument(
            "pipeline",
            type=str,
            help=(
                "Pipeline name or import string (e.g., 'path.to:pipeline_fn')."
            ),
        )

        self._add_log_level(runtask_parser)
        self._add_local_option(runtask_parser)
        self._add_fail_fast_option(runtask_parser)
        self._add_detach(runtask_parser)
        runtask_parser.set_defaults(fn=run_task)

        return self

    def add_list_subparser(self) -> Self:
        """Add Parser to list pipelines.

        Returns:
            Self: Parser.
        """
        list_parser = self._subparsers.add_parser(
            "list", help="List pipelines or runs."
        )

        list_parser.add_argument(
            "pipeline",
            nargs="?",
            type=str,
            help=(
                "Pipeline name. If set, all the available"
                " runs of this pipeline are shown."
            ),
        )
        self._add_log_level(list_parser)
        self._add_detach(list_parser)
        list_parser.set_defaults(fn=list_pipelines)

        return self

    def add_describe_subparser(self) -> Self:
        """Add the describe parser.

        Returns:
            Self: Parser.
        """
        describe_parser = self._subparsers.add_parser(
            "describe", help="Print information about the tasks of a pipeline."
        )

        describe_parser.add_argument(
            "pipeline",
            type=str,
            help=(
                "Pipeline name, import string (e.g., 'path.to:pipeline_fn'),"
                " or compiled JSON path to skip compilation."
            ),
        )

        self._add_compilation_args(describe_parser)
        self._add_log_level(describe_parser)
        self._add_detach(describe_parser)
        describe_parser.set_defaults(fn=describe_pipeline)

        return self

    def add_status_subparser(self) -> Self:
        """Add the status parser.

        Returns:
            Self: Parser.
        """
        status_parser = self._subparsers.add_parser(
            "status",
            help=(
                "Read the last checkpoint and print the status of all tasks."
            ),
        )
        self._add_pipeline_name_and_hash_or_json(status_parser)
        self._add_log_level(status_parser)
        self._add_detach(status_parser)
        status_parser.set_defaults(fn=print_status)

        return self

    def get_parser(self) -> ArgumentParser:
        """Get the parser.

        Returns:
            ArgumentParser: Parser.
        """
        return self._parser

    def _add_detach(self, parser: ArgumentParser) -> None:
        """Add the detach option to the parser.

        Detached commands run on Slurm.

        Args:
            parser (ArgumentParser): Parser.
        """
        parser.add_argument(
            "--detach",
            action=BooleanOptionalAction,
            default=False,
            help="Run the command as a sbatch job.",
        )

    def _add_log_level(self, subparser: ArgumentParser) -> Self:
        """Add the log level.

        Args:
            subparser (ArgumentParser): Subparser.

        Returns:
            Self: Parser builder.
        """
        subparser.add_argument(
            "-l",
            "--log-level",
            choices=["debug", "info", "warning", "error"],
            default=None,
            help="Log level. Defaults to 'info'.",
        )

        return self

    def _add_pipeline_name_and_hash_or_json(
        self, subparser: ArgumentParser
    ) -> None:
        """Add the pipeline name and hash.

        Args:
            subparser (ArgumentParser): Subparser.
        """
        subparser.add_argument(
            "pipeline",
            type=str,
            help="Pipeline name.",
        )

        subparser.add_argument(
            "--hash",
            type=str,
            default="last",
            help=(
                "Pipeline hash. If equal to 'last', the most recently"
                " created pipeline is considered. Defaults to 'last'."
            ),
        )

    def _add_scheduler_args(self, subparser: ArgumentParser) -> None:
        """Add the scheduler options.

        Args:
            subparser (ArgumentParser): Subparser.
        """
        subparser.add_argument(
            "-t",
            "--time-between-polls",
            type=int,
            default=None,
            help="Time between slurm polls (seconds). Defaults to 5s.",
        )

        subparser.add_argument(
            "-m",
            "--max-concurrency",
            type=int,
            default=None,
            help=(
                "Maximum number of jobs running at the same time."
                "Set to 0 for unlimited concurrency. Defaults to 10."
            ),
        )

    def _add_local_option(self, subparser: ArgumentParser) -> None:
        """Add local flag.

        Args:
            subparser (ArgumentParser): Parser.
        """
        subparser.add_argument(
            "--local",
            action=BooleanOptionalAction,
            default=False,
            help="Compile all task as local, nonblocking child processes.",
        )

    def _add_fail_fast_option(self, subparser: ArgumentParser) -> None:
        """Add the fail fast flag.

        Args:
            subparser (ArgumentParser): Parser.
        """
        subparser.add_argument(
            "--fail-fast",
            action=BooleanOptionalAction,
            default=False,
            help=(
                "Kill the scheduler and all running tasks"
                " if any of them fails."
            ),
        )

    def _add_compilation_args(self, subparser: ArgumentParser) -> None:
        """Add the compilation options.

        Args:
            subparser (ArgumentParser): Subparser.
        """
        subparser.add_argument(
            "-d",
            "--dst-dir",
            type=str,
            default=None,
            help=(
                "Destination directory. Defaults to the 'compiled-dagdir'"
                " setting ('./compiled-pipelines'). It is created if missing."
            ),
        )

        subparser.add_argument(
            "-n",
            "--name",
            type=str,
            default=None,
            help=(
                "Compiled pipeline file name. Defaults to the pipeline name."
                " The '.json' extension is appended automatically."
            ),
        )
        self._add_local_option(subparser)
        self._add_extra_metadata(subparser)

    def _add_extra_metadata(self, subparser: ArgumentParser) -> None:
        """Add extra metadata for the pipeline as a JSON string.

        Args:
            subparser (ArgumentParser): Subparser.
        """
        subparser.add_argument(
            "-e",
            "--extra-metadata",
            type=str,
            default=None,
            help="Extra metadata as a JSON string. Defaults to None.",
        )


class ExtraArgumentParser:
    """Parse the CLI extra arguments.

    These arguments will become the pipline input kwargs. The
    `parse_known_args` method doesn't handle `--key=value` and
    `--key value` automatically, so some care must be taken.

    Keep in mind that values are casted with json.
    """

    def parse(self, extras: list[str]) -> dict[str, Any]:
        """Parse extra arguments.

        Args:
            extras (list[str]): Extra arguments.

        Returns:
            dict[str, Any]: Parsed extra arguments.
        """
        extras = [arg for arg in extras if arg != "--"]
        kwargs: dict[str, Any] = {}
        nextras = len(extras)
        i = 0

        while i < nextras:
            arg = extras[i]
            if arg.startswith("-"):
                if "=" in arg:
                    raw_key, val_str = arg.split("=", 1)
                else:
                    raw_key = arg
                    if i + 1 < nextras and not extras[i + 1].startswith("-"):
                        val_str = extras[i + 1]
                        i += 1
                    else:
                        val_str = "true"

                key = raw_key.lstrip("-").replace("-", "_")
                kwargs[key] = self._maybe_cast_value(val_str)
            i += 1

        return kwargs

    def _maybe_cast_value(self, value: str) -> Any:
        """Try to cast the input value.

        In the future we might use the pipeline type hints.

        Args:
            value (str): Input value.

        Returns:
            Any: Parsed values. In case of parsing errors (e.g., for
                strings) the value is returned as-is.
        """
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
