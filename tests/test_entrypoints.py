# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import os
import sys
from pathlib import Path

import pytest
from sdag.entrypoints import cli, sdag_execute


@pytest.mark.parametrize(argnames="argv", argvalues=[["sdag"], ["sdag", "-j"]])
def test_weird_arguments_are_blocked(
    argv: list[str], capsys: pytest.CaptureFixture
):
    sys.argv = argv
    with pytest.raises(SystemExit) as exc:
        cli()

    assert exc.value.code == 2
    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize(
    argnames="argv",
    argvalues=[
        ["sdag", "-h"],
        ["sdag", "--version"],
        ["sdag", "compile", "-h"],
        ["sdag", "run", "-h"],
        ["sdag", "restart", "-h"],
        ["sdag", "kill", "-h"],
        ["sdag", "prune", "-h"],
        ["sdag", "runtask", "-h"],
        ["sdag", "view", "-h"],
        ["sdag", "list", "-h"],
        ["sdag", "describe", "-h"],
        ["sdag", "status", "-h"],
    ],
)
def test_all_commands_are_reachable(argv: list[str]) -> None:
    sys.argv = argv
    with pytest.raises(SystemExit) as exc_info:
        cli()

    assert exc_info.value.code == 0


def test_task_execution(tmp_path: Path) -> None:
    from sdag import task

    @task("path/to/script.sh")
    def foo(): ...

    path = tmp_path / "0"
    path.mkdir(parents=True, exist_ok=True)
    input_file_path = path / "input.json"
    with input_file_path.open("w") as fin:
        fin.write(r"{}")

    os.environ["SDAG_PIPELINE_DIR"] = str(tmp_path)
    os.environ["SDAG_PIPELINE_NAME"] = "dag"
    os.environ["SDAG_SUBPIPELINE_NAME"] = "dag"
    os.environ["SDAG_IMPORT_PATH"] = "dag"
    os.environ["SDAG_INPUT_KWARGS"] = r"{}"
    os.environ["SDAG_UID"] = "0"
    os.environ["SDAG_TASK_NAME"] = "foo"
    os.environ["SDAG_TASK_FN"] = "foo"
    os.environ["SDAG_TRY_NUM"] = "1"
    os.environ["SDAG_LOG_LEVEL"] = "info"

    sdag_execute()
