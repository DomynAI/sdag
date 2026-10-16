"""Test the examples in the docs."""

import os
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest


def _get_table(output: bytes) -> str:
    """Get the final recap table.

    Args:
        output (bytes): stderr.

    Returns:
        str: Output table.
    """
    log_lines = output.decode("utf-8").split("\n")
    table_lines = [line.strip() for line in log_lines[-16:-1]]
    return "\n".join(table_lines)


def _describe_pipeline(pipeline_name: str) -> str:
    """Run `sdag describe`.

    Args:
        pipeline_name (str): Pipeline name.

    Returns:
        str: stdout.
    """
    stdout = subprocess.check_output(
        ["sdag", "describe", pipeline_name], timeout=15
    )
    return stdout.decode("utf-8").strip()


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


@pytest.fixture
def set_base_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None]:
    """Safely set the artifact base directory.

    Args:
        tmp_path (Path): Temporary path fixture.
        monkeypatch (pytest.MonkeyPatch): Patcher.

    Yields:
        Generator[None]: Drops `SDAG_BASE_PATH` at the end of the test.
    """
    base_dir = tmp_path / "artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SDAG_BASE_PATH", str(base_dir))
    yield
    monkeypatch.delenv("SDAG_BASE_PATH")


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_hello_world():
    """Test the ehllo world pipeline."""
    output = subprocess.check_output(
        ["sdag", "run", "hello_world", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 1      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_many_tasks():
    """Test the multiple task pipeline."""
    output = subprocess.check_output(
        ["sdag", "run", "many_tasks", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 3      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_dependent_tasks():
    """Test the dependent task pipeline."""
    output = subprocess.check_output(
        ["sdag", "run", "dependent_tasks", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 3      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_output_use():
    """Test the output use pipeline."""
    output = subprocess.check_output(
        ["sdag", "run", "output_use", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 2      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_dag_with_input():
    """Test the pipeline with input values."""
    output = subprocess.check_output(
        [
            "sdag",
            "run",
            "dag_with_input",
            "-t",
            "1",
            "--local",
            "--",
            "--input-path",
            "a/path",
        ],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 1      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_external_dag():
    """Test the pipeline with external task."""
    output = subprocess.check_output(
        ["sdag", "run", "external_dag", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 1      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_local_dag():
    """Test the pipeline with local task."""
    output = subprocess.check_output(
        ["sdag", "run", "local_dag", "-t", "1"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 1      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_failure():
    """Test the pipeline with a failing task."""
    output = subprocess.check_output(
        ["sdag", "run", "failure", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 0      │
├───────────────┼────────┤
│       Skipped │ 1      │
├───────────────┼────────┤
│        Failed │ 1      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_control_flow():
    """Test the if/elif/else pipeline."""
    output = subprocess.check_output(
        ["sdag", "run", "control_flow", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 3      │
├───────────────┼────────┤
│       Skipped │ 2      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_oneof():
    """Test the oneof pipeline."""
    output = subprocess.check_output(
        ["sdag", "run", "oneof_example", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 3      │
├───────────────┼────────┤
│       Skipped │ 1      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_outer_pipeline():
    """Test the nested pipelines."""
    output = subprocess.check_output(
        ["sdag", "run", "outer_pipeline", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 2      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_task_calling_task():
    """Test the pipeline with a nested task call."""
    output = subprocess.check_output(
        ["sdag", "run", "task_calling_task", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 1      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_cached():
    """Test the pipeline with a cached task."""
    output = subprocess.check_output(
        ["sdag", "run", "cached", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 2      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()

    describe_table = _describe_pipeline("cached")
    expected_describe_table = """
┌─────┬─────────────────┬──────────┬────────┬───────────┬────────────────┐
│ uid │ name            │ pipeline │ cached │ artifacts │ kwargs         │
├─────┼─────────────────┼──────────┼────────┼───────────┼────────────────┤
│     │                 │          │        │           │ {              │
│   2 │ cached_task     │ cached   │ true   │           │   "a": "world" │
│     │                 │          │        │           │ }              │
├─────┼─────────────────┼──────────┼────────┼───────────┼────────────────┤
│   3 │ non_cached_task │ cached   │ false  │           │ {}             │
└─────┴─────────────────┴──────────┴────────┴───────────┴────────────────┘
"""

    assert describe_table == expected_describe_table.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_name_change():
    """Test a pipeline with cached tasks having different names."""
    output = subprocess.check_output(
        ["sdag", "run", "name_change", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 2      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()

    describe_table = _describe_pipeline("name_change")
    expected_describe_table = """
┌─────┬──────────────┬─────────────┬────────┬───────────┬──────────────┐
│ uid │ name         │ pipeline    │ cached │ artifacts │ kwargs       │
├─────┼──────────────┼─────────────┼────────┼───────────┼──────────────┤
│     │              │             │        │           │ {            │
│   2 │ a_task       │ name_change │ true   │           │   "value": 1 │
│     │              │             │        │           │ }            │
├─────┼──────────────┼─────────────┼────────┼───────────┼──────────────┤
│     │              │             │        │           │ {            │
│   3 │ another_task │ name_change │ true   │           │   "value": 2 │
│     │              │             │        │           │ }            │
└─────┴──────────────┴─────────────┴────────┴───────────┴──────────────┘
"""

    assert describe_table == expected_describe_table.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
@pytest.mark.usefixtures("set_base_path")
def test_dag_with_artifact():
    """Test the pipeline with a cacheable artifact."""
    output = subprocess.check_output(
        ["sdag", "run", "dag_with_artifact", "-t", "1", "--local"],
        stderr=subprocess.STDOUT,
        timeout=15,
        env=os.environ,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 2      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()

    describe_table = _describe_pipeline("dag_with_artifact")

    base_dir = os.environ["SDAG_BASE_PATH"]
    artifact_path = f"{base_dir}/artifact.txt"

    quotes_and_spaces = 8
    nspaces = " " * (len(artifact_path) + quotes_and_spaces)
    nlines = "─" * (len(artifact_path) + quotes_and_spaces)

    expected_describe_table = f"""
┌─────┬─────────────┬───────────────────┬────────┬───────────┬────────────{nlines}┐
│ uid │ name        │ pipeline          │ cached │ artifacts │ kwargs     {nspaces}│
├─────┼─────────────┼───────────────────┼────────┼───────────┼────────────{nlines}┤
│     │             │                   │        │           │ {{          {nspaces}│
│   2 │ create_file │ dag_with_artifact │ true   │ path      │   "path": "{artifact_path}"       │
│     │             │                   │        │           │ }}          {nspaces}│
├─────┼─────────────┼───────────────────┼────────┼───────────┼────────────{nlines}┤
│     │             │                   │        │           │ {{          {nspaces}│
│   3 │ print_path  │ dag_with_artifact │ true   │           │   "input_path": "{artifact_path}" │
│     │             │                   │        │           │ }}          {nspaces}│
└─────┴─────────────┴───────────────────┴────────┴───────────┴────────────{nlines}┘
"""  # noqa: E501

    assert describe_table == expected_describe_table.strip()


@pytest.mark.slow
@pytest.mark.usefixtures("set_home")
def test_batch_processing():
    """Test the local batch processing pipeline."""
    output = subprocess.check_output(
        [
            "sdag",
            "run",
            "process_in_batches",
            "-t",
            "1",
            "--local",
            "--input-path",
            "input",
            "--base-output",
            "output",
        ],
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    final_table = _get_table(output)
    expected = """
┌───────────────┬────────┐
│        status │ ntasks │
├───────────────┼────────┤
│     Completed │ 3      │
├───────────────┼────────┤
│       Skipped │ 0      │
├───────────────┼────────┤
│        Failed │ 0      │
├───────────────┼────────┤
│       Pending │ 0      │
├───────────────┼────────┤
│       Running │ 0      │
├───────────────┼────────┤
│ Not submitted │ 0      │
└───────────────┴────────┘
"""

    assert final_table == expected.strip()
