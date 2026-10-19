# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""End-to-end tests."""

import json
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from sdag.entrypoints import cli


@pytest.fixture
def set_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None]:
    """Safely set the home directory.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.

    Yields:
        Generator[None]: Drops `SDAG_HOME` at the end of the test.
    """
    monkeypatch.setenv("SDAG_HOME", str(tmp_path))
    yield
    monkeypatch.delenv("SDAG_HOME")


@pytest.mark.usefixtures("set_home")
def test_prune_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test the cache pruning of a task named 'all'.

    Corner case: If a global task named 'all' exists, the
    global cache must not be deleted.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """
    cache_path = tmp_path / ".sdag" / ".cache"
    cached_task_path = cache_path / "global" / "all"
    cached_task_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("sys.argv", ["sdag", "prune", "all"])

    cli()

    assert not cached_task_path.exists()
    assert cache_path.exists()


@pytest.mark.usefixtures("set_home")
def test_prune_entire_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test the cache pruning of a task named 'all'.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """
    cache_path = tmp_path / ".sdag" / ".cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("sys.argv", ["sdag", "prune", "all"])

    cli()

    assert not cache_path.exists()


@pytest.mark.usefixtures("set_home")
def test_prune_cache_from_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test the cache pruning.

    The pipeline has a global cached task and a local one. The global
    task has two caches: one that matches the input (hash 'xyz') and
    another one that doesnt (hash 'abc'). The cache pruning must delete
    the local cache and the matching global one while leaving 'abc'
    intact.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """

    pipeline_path = tmp_path / "pipeline.json"

    pipeline = {
        "meta": {
            "pipeline_name": "test_prune_cache_from_json",
            "timestamp": "2025-12-30T11:30:46.343072",
            "code_hash": "asdf234",
            "extra": {},
            "kwargs": {},
            "import_path": "path.to.pipeline:fn",
        },
        "nodes": [
            {
                "uid": 0,
                "pipeline_name": "test_prune_cache_from_json",
                "kind": "root",
            },
            {
                "uid": 1,
                "kind": "task",
                "fn_name": "task",
                "name": "task_global",
                "scope": "global",
                "pipeline_name": "test_prune_cache_from_json",
                "cache": "io",
                "code_hash": "xyz",
                "mode": "ext",
                "cmd": "bash",
                "retries": 0,
                "script": {"kind": "script_path", "path": "script.sh"},
                "kwargs": [{"key": "k", "value": "v"}],
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 0,
                    }
                ],
                "artifacts": [],
            },
            {
                "uid": 2,
                "kind": "task",
                "scope": "local",
                "fn_name": "task",
                "name": "task_local",
                "pipeline_name": "test_prune_cache_from_json",
                "cache": "io",
                "code_hash": "abc",
                "mode": "ext",
                "cmd": "bash",
                "retries": 0,
                "script": {"kind": "script_path", "path": "script.sh"},
                "kwargs": [{"key": "k", "value": "v"}],
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 0,
                    }
                ],
                "artifacts": [],
            },
            {
                "uid": 2,
                "pipeline_name": "dag",
                "kind": "end",
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 1,
                    },
                    {
                        "kind": {"kind": "logical"},
                        "uid": 2,
                    },
                ],
            },
        ],
    }

    with pipeline_path.open("w") as f:
        json.dump(pipeline, f)

    cache_path = tmp_path / ".sdag" / ".cache"

    input_data = {"k": "v"}
    output_data = {"output": None, "artifacts": []}

    global_cache_path = cache_path / "global" / "task_global" / "xyz"
    global_cache_path.mkdir(parents=True, exist_ok=True)
    with (global_cache_path / "input.json").open("w") as f:
        json.dump(input_data, f)
    with (global_cache_path / "output.json").open("w") as f:
        json.dump(output_data, f)

    local_cache_path = (
        cache_path
        / "local"
        / "test_prune_cache_from_json"
        / "task_local"
        / "xyz"
    )
    local_cache_path.mkdir(parents=True, exist_ok=True)
    with (local_cache_path / "input.json").open("w") as f:
        json.dump(input_data, f)
    with (local_cache_path / "output.json").open("w") as f:
        json.dump(output_data, f)

    # This global cache doesn't match and it must survive
    global_no_match_path = cache_path / "global" / "task_global" / "abc"
    global_no_match_path.mkdir(parents=True, exist_ok=True)
    with (global_no_match_path / "input.json").open("w") as f:
        json.dump({"k": "different-value"}, f)
    with (global_no_match_path / "output.json").open("w") as f:
        json.dump(output_data, f)

    monkeypatch.setattr(
        "sys.argv", ["sdag", "prune", "-p", str(pipeline_path)]
    )

    cli()

    assert cache_path.exists()
    assert not local_cache_path.exists()
    assert not global_cache_path.exists()
    assert global_no_match_path.exists()


@pytest.mark.usefixtures("set_home")
def test_kill_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the job killing.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """
    pipeline_name = "pipeline"
    pipeline_hash = "xyz"
    pipeline_path = (
        tmp_path / ".sdag" / "pipelines" / pipeline_name / pipeline_hash
    )
    pipeline_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "sys.argv", ["sdag", "kill", pipeline_name, "--hash", pipeline_hash]
    )
    cli()
    assert pipeline_path.joinpath("kill.lock").is_file()


@pytest.mark.usefixtures("set_home")
def test_run_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the pipeline execution.

    The only stage is local and external, it creates a
    file named 'target.txt'.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """
    target_path = tmp_path / "target.txt"
    script_path = tmp_path / "submit.sh"
    pipeline_path = tmp_path / "pipeline.json"

    with script_path.open("w") as f:
        f.write(f"touch {target_path}")

    pipeline = {
        "meta": {
            "hash": "xyz",
            "code_hash": "asdf234",
            "pipeline_name": "test_run_pipeline",
            "timestamp": "2025-12-30T11:30:46.343072",
            "extra": {},
            "import_path": "path.to.pipeline:fn",
            "kwargs": {},
        },
        "nodes": [
            {"uid": 0, "pipeline_name": "dag", "kind": "root"},
            {
                "uid": 1,
                "kind": "task",
                "fn_name": "task",
                "name": "task",
                "pipeline_name": "dag",
                "cache": "none",
                "code_hash": "abc",
                "cache_size": 1,
                "mode": "ext",
                "cmd": "bash",
                "scope": "global",
                "try_num": 1,
                "retries": 0,
                "script": {"kind": "script_path", "path": str(script_path)},
                "kwargs": [{"key": "k", "value": "v"}],
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 0,
                    }
                ],
                "artifacts": [],
                "njobs": 1,
            },
            {
                "uid": 2,
                "pipeline_name": "dag",
                "kind": "end",
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 1,
                    }
                ],
            },
        ],
    }

    with pipeline_path.open("w") as f:
        json.dump(pipeline, f)

    monkeypatch.setattr(
        "sys.argv",
        ["sdag", "run", f"{pipeline_path}", "-t", "0"],
    )
    cli()

    assert (
        tmp_path
        / ".sdag"
        / "pipelines"
        / "test_run_pipeline"
        / "xyz"
        / "1"
        / "output.json"
    ).exists()
    assert target_path.exists()


@pytest.mark.usefixtures("set_home")
def test_run_pipeline_with_global_caching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test pipeline execution and task caching.

    This also verifies the task name is used instead
    of fname.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """
    script_path = tmp_path / "submit.sh"
    pipeline_path = tmp_path / "pipeline.json"

    with script_path.open("w") as f:
        f.write("echo hello")

    pipeline = {
        "meta": {
            "pipeline_name": "test_run_pipeline_with_global_caching",
            "timestamp": "2025-12-30T11:30:46.343072",
            "code_hash": "asdf234",
            "extra": {},
            "kwargs": {},
            "import_path": "path.to.pipeline:fn",
        },
        "nodes": [
            {
                "uid": 0,
                "pipeline_name": "test_prune_cache_from_json",
                "kind": "root",
            },
            {
                "uid": 1,
                "kind": "task",
                "fn_name": "task",
                "name": "task",
                "pipeline_name": "test_prune_cache_from_json",
                "scope": "global",
                "cache": "io",
                "cache_size": 1,
                "code_hash": "abc",
                "mode": "ext",
                "cmd": "bash",
                "retries": 0,
                "script": {"kind": "script_path", "path": str(script_path)},
                "kwargs": [{"key": "k", "value": "v"}],
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 0,
                    }
                ],
                "artifacts": [],
                "njobs": 1,
            },
            {
                "uid": 2,
                "pipeline_name": "test_prune_cache_from_json",
                "kind": "end",
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 1,
                    }
                ],
            },
        ],
    }

    with pipeline_path.open("w") as f:
        json.dump(pipeline, f)

    monkeypatch.setattr(
        "sys.argv",
        ["sdag", "run", f"{pipeline_path}", "-t", "0"],
    )
    cli()

    base_cache_path = tmp_path / ".sdag" / ".cache" / "global" / "task"
    cache_dir = next(base_cache_path.iterdir())
    assert (cache_dir / "output.json").exists()
    assert (cache_dir / "input.json").exists()
    assert (cache_dir / "meta.json").exists()


@pytest.mark.usefixtures("set_home")
def test_run_pipeline_with_local_caching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test pipeline execution and task caching.

    This also verifies the task name is used instead
    of fname.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.
    """
    script_path = tmp_path / "submit.sh"
    pipeline_path = tmp_path / "pipeline.json"

    with script_path.open("w") as f:
        f.write("echo hello")

    pipeline = {
        "meta": {
            "pipeline_name": "test_run_pipeline_with_local_caching",
            "timestamp": "2025-12-30T11:30:46.343072",
            "code_hash": "asdf234",
            "extra": {},
            "kwargs": {},
            "import_path": "path.to.pipeline:fn",
        },
        "nodes": [
            {"uid": 0, "pipeline_name": "dag", "kind": "root"},
            {
                "uid": 1,
                "kind": "task",
                "fn_name": "task",
                "name": "task",
                "pipeline_name": "dag",
                "scope": "local",
                "cache": "io",
                "cache_size": 1,
                "code_hash": "abc",
                "mode": "ext",
                "cmd": "bash",
                "try_num": 1,
                "retries": 0,
                "script": {"kind": "script_path", "path": str(script_path)},
                "kwargs": [{"key": "k", "value": "v"}],
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 0,
                    }
                ],
                "artifacts": [],
                "njobs": 1,
            },
            {
                "uid": 2,
                "pipeline_name": "dag",
                "kind": "end",
                "parents": [
                    {
                        "kind": {"kind": "logical"},
                        "uid": 1,
                    }
                ],
            },
        ],
    }

    with pipeline_path.open("w") as f:
        json.dump(pipeline, f)

    monkeypatch.setattr(
        "sys.argv",
        ["sdag", "run", f"{pipeline_path}", "-t", "0"],
    )
    cli()

    base_cache_local_path = (
        tmp_path / ".sdag" / ".cache" / "local" / "dag" / "task"
    )
    cache_local_dir = next(base_cache_local_path.iterdir())
    assert (cache_local_dir / "output.json").exists()
    assert (cache_local_dir / "input.json").exists()
    assert (cache_local_dir / "meta.json").exists()


@pytest.mark.usefixtures("set_home")
def test_print_pipeline_status(tmp_path: Path) -> None:
    """Test the status table is printed.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    base_path = tmp_path / ".sdag"
    pipeline_hash = "4696fc62bc92"
    pipeline_dir = base_path / "pipelines" / "hello_world" / pipeline_hash

    checkpoint = {
        "cfg": {
            "homedir": f"{base_path}",
            "dagdir": f"{pipeline_dir}",
            "cachedir": f"{base_path}/.cache/global",
            "local_cachedir": f"{base_path}/.cache/local",
            "timestamp": "2026-09-29T08:11:09",
            "grace_period": 60,
            "max_dagdirs": 20,
            "max_concurrency": 0,
            "sleep_time": {"secs": 1, "nanos": 0},
            "log_level": "info",
            "dag_code_hash": "asdf234",
            "fail_fast": False,
            "cache_lock": False,
        },
        "meta": {
            "pipeline_name": "hello_world",
            "hash": "4696fc62bc92",
            "code_hash": "asdf234",
            "timestamp": "2026-09-29T08:11:09.663064",
            "extra": {},
            "import_path": "hello_world",
            "kwargs": {},
        },
        "nodes": [
            {
                "kind": "root",
                "uid": 0,
                "pipeline_name": "hello_world",
                "parents": [],
                "children": [2],
            },
            {
                "kind": "end",
                "uid": 1,
                "pipeline_name": "hello_world",
                "parents": [{"uid": 2, "kind": {"kind": "logical"}}],
                "children": [],
                "artifacts": [],
            },
            {
                "kind": "task",
                "uid": 2,
                "parents": [{"uid": 0, "kind": {"kind": "logical"}}],
                "fn_name": "say_hello",
                "name": "say_hello",
                "pipeline_name": "hello_world",
                "cache": "none",
                "code_hash": "xyz",
                "scope": "local",
                "cache_size": 1,
                "cache_ignore": [],
                "mode": "wrap",
                "cmd": "bash",
                "retries": 0,
                "script": {"kind": "script_path", "path": "scripts/submit.sh"},
                "envs": {},
                "slurm": {
                    "job-name": None,
                    "nodes": None,
                    "partition": "partition",
                    "qos": "qos1",
                    "gpus-per-node": None,
                    "ntasks-per-node": None,
                    "output": None,
                    "error": None,
                    "account": None,
                    "cpus-per-task": None,
                    "mem": None,
                    "time": None,
                },
                "kwargs": [{"key": "name", "value": "sdag"}],
                "tags": [],
                "artifacts": [],
                "children": [1],
                "njobs": 1,
            },
        ],
        "node_ctxs": [
            {
                "status": {"Completed": "Generic"},
                "try_num": 0,
                "jobs": [],
            },
            {
                "status": {"Completed": "Generic"},
                "try_num": 0,
                "jobs": [],
            },
            {
                "status": {"Completed": {"Job": {"Local": 6972}}},
                "try_num": 1,
                "jobs": [
                    {
                        "nmiss": 0,
                        "status": {"Completed": {"Job": {"Local": 6972}}},
                    }
                ],
            },
        ],
    }

    pipeline_dir.mkdir(parents=True, exist_ok=True)
    with (pipeline_dir / "checkpoint.json").open("w") as f:
        json.dump(checkpoint, f)

    output = subprocess.run(
        [
            "sdag",
            "status",
            "hello_world",
            "--hash",
            pipeline_hash,
            "-l",
            "info",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    stderr = output.stderr.decode("utf-8")
    lines = [line.strip() for line in stderr.split("\n") if line]
    table = "\n".join(lines[-5:])

    expected_table = r"""
┌─────┬───────────┬─────────────┬──────────────────────┬──────┬─────────┐
│ uid │ task      │ pipeline    │ status               │ cmd  │ try_num │
├─────┼───────────┼─────────────┼──────────────────────┼──────┼─────────┤
│   2 │ say_hello │ hello_world │ Completed (pid=6972) │ bash │ 1       │
└─────┴───────────┴─────────────┴──────────────────────┴──────┴─────────┘
"""

    assert table == expected_table.strip()
