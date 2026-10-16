# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest
from sdag.commands import (
    compile_pipeline,
    describe_pipeline,
    kill_pipeline,
    list_pipelines,
    print_status,
    prune_cache,
    restart_run,
    run_pipeline,
    run_task,
    view_pipeline,
)
from sdag.parser import ExtraArgumentParser, ParserBuilder


class TestExtraArgumentParser:
    """Test the extra argument parser."""

    @pytest.mark.parametrize(
        argnames=("extras", "kwargs"),
        argvalues=[
            # Empty
            ([], {}),
            # --key=value case
            (["--cfg=test"], {"cfg": "test"}),
            # --key value case
            (["--cfg", "test"], {"cfg": "test"}),
            # Parse to int
            (["--cfg", "1"], {"cfg": 1}),
            # Parse scientific notation
            (["--cfg", "1e4"], {"cfg": 10_000}),
            # Parse to float
            (["--cfg", "1.2"], {"cfg": 1.2}),
            # Parse to bool
            (["--cfg", "true"], {"cfg": True}),
            # Store flag as bool
            (["--cfg"], {"cfg": True}),
            # Replace dashes with underscores
            (
                ["--an-input", "--input-data=test-with-dash"],
                {"an_input": True, "input_data": "test-with-dash"},
            ),
            # Multiple extras
            (
                ["--cfg1", "test", "--cfg2=test", "--default"],
                {"cfg1": "test", "cfg2": "test", "default": True},
            ),
            # -- is ignored
            (["--", "--cfg=test"], {"cfg": "test"}),
        ],
    )
    def test_parse_extra(
        self, extras: list[str], kwargs: dict[str, Any]
    ) -> None:
        """Test the extra argument parser.

        Args:
            extras (list[str]): Extra arguments parsed via `parse_known_args`.
            kwargs (dict[str, Any]): Parsed kwargs.
        """
        parser = ExtraArgumentParser()
        assert parser.parse(extras) == kwargs


class TestParaserBuilder:
    @pytest.fixture
    def builder(self) -> ParserBuilder:
        return ParserBuilder()

    def test_compile(self, builder: ParserBuilder) -> None:
        parser = builder.add_compile_subparser().get_parser()
        args = parser.parse_args(
            [
                "compile",
                "target",
                "-d",
                "a/path",
                "-n",
                "output.json",
                "-l",
                "debug",
            ]
        )

        assert args.dst_dir == "a/path"
        assert args.name == "output.json"
        assert args.log_level == "debug"
        assert args.pipeline == "target"
        assert args.fn is compile_pipeline

    def test_run(self, builder: ParserBuilder) -> None:
        parser = builder.add_run_subparser().get_parser()
        args = parser.parse_args(
            [
                "run",
                "target",
                "-d",
                "a/path",
                "-n",
                "output.json",
                "-l",
                "debug",
                "--local",
                "--time-between-polls",
                "7",
                "-m",
                "5",
            ]
        )

        assert args.dst_dir == "a/path"
        assert args.name == "output.json"
        assert args.log_level == "debug"
        assert args.pipeline == "target"
        assert args.time_between_polls == 7
        assert args.max_concurrency == 5
        assert args.local
        assert args.fn is run_pipeline

    def test_restart(self, builder: ParserBuilder) -> None:
        parser = builder.add_restart_subparser().get_parser()
        args = parser.parse_args(
            [
                "restart",
                "target",
                "--hash",
                "xyz",
                "-l",
                "debug",
                "--time-between-polls",
                "7",
                "-m",
                "5",
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline == "target"
        assert args.hash == "xyz"
        assert args.time_between_polls == 7
        assert args.max_concurrency == 5
        assert args.fn is restart_run

    def test_kill(self, builder: ParserBuilder) -> None:
        parser = builder.add_kill_subparser().get_parser()
        args = parser.parse_args(
            [
                "kill",
                "target",
                "--hash",
                "xyz",
                "-l",
                "debug",
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline == "target"
        assert args.hash == "xyz"
        assert args.fn is kill_pipeline

    def test_prune(self, builder: ParserBuilder) -> None:
        parser = builder.add_prune_subparser().get_parser()
        args = parser.parse_args(
            [
                "prune",
                "task1",
                "task2",
                "-p",
                "pipeline",
                "-l",
                "debug",
                "-e",
                r'{"a": 1}',
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline == "pipeline"
        assert args.task == ["task1", "task2"]
        assert args.extra_metadata == r'{"a": 1}'
        assert args.fn is prune_cache

    def test_view(self, builder: ParserBuilder) -> None:
        parser = builder.add_view_subparser().get_parser()
        args = parser.parse_args(
            [
                "view",
                "pipeline",
                "--squeeze",
                "-l",
                "debug",
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline == "pipeline"
        assert args.squeeze
        assert args.fn is view_pipeline

    def test_runtask(self, builder: ParserBuilder) -> None:
        parser = builder.add_runtask_subparser().get_parser()
        args = parser.parse_args(
            [
                "runtask",
                "task",
                "pipeline",
                "--local",
                "-l",
                "debug",
            ]
        )

        assert args.log_level == "debug"
        assert args.task == "task"
        assert args.pipeline == "pipeline"
        assert args.local
        assert args.fn is run_task

    def test_list(self, builder: ParserBuilder) -> None:
        parser = builder.add_list_subparser().get_parser()
        args = parser.parse_args(
            [
                "list",
                "-l",
                "debug",
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline is None
        assert args.fn is list_pipelines

    def test_describe(self, builder: ParserBuilder) -> None:
        parser = builder.add_describe_subparser().get_parser()
        args = parser.parse_args(
            [
                "describe",
                "path.to.module:pipeline",
                "-d",
                "a/path",
                "-n",
                "output.json",
                "-l",
                "debug",
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline == "path.to.module:pipeline"
        assert args.dst_dir == "a/path"
        assert args.name == "output.json"
        assert args.fn is describe_pipeline

    def test_status(self, builder: ParserBuilder) -> None:
        parser = builder.add_status_subparser().get_parser()
        args = parser.parse_args(
            [
                "status",
                "dag",
                "--hash",
                "xyz",
                "-l",
                "debug",
            ]
        )

        assert args.log_level == "debug"
        assert args.pipeline == "dag"
        assert args.hash == "xyz"
        assert args.fn is print_status
