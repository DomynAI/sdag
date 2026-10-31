# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any

import pytest
from sdag.models import DAG, DAGMeta, SlurmOverride, TaskNode
from sdag.pyproj import (
    DetachOptions,
    Pyproj,
    apply_pyproj_configs,
    apply_pyproj_to_task,
    get_pyproj,
)
from sdag.scripts import ScriptPath


def test_parse_pyproject(tmp_path: Path) -> None:
    """Check pyproject is parsed correctly.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """[tool.sdag]
    dagdir = "path/to/dagdir"
    compiled-dagdir = "path/to/compiled"
    prepend-compiled-dagdir = true
    log-level = "debug"
    slurm-grace-period = 50
    max-concurrent-runs = 2
    local = true
    extra-dagdirs = ["sdag.extras"]
    container = "image.sif"
    container-runtime = "apptainer"
    container-binds = ["some/path"]
    container-options = ["--nv"]

    [tool.sdag.envs]
    ENV="value"

    [tool.sdag.detach]
    job-name = "detached"

    [[tool.sdag.tags]]
    tag = "online"
    local = false
    envs = {"ENV" = "another_value"}
    container = "tag.sif"
    container-runtime = "singularity"
    container-binds = ["other/path"]
    container-options = ["--nv"]
    """
    pyproj_path = tmp_path / "pyproject.toml"
    # so we don't read the main one by accident
    sdag_toml_path = tmp_path / "missing.toml"
    with pyproj_path.open("w") as f:
        f.write(content)

    pyproj = get_pyproj(
        pyproj_path=str(pyproj_path), sdag_toml_path=str(sdag_toml_path)
    )
    assert pyproj.dagdir == "path/to/dagdir"
    assert pyproj.compiled_dagdir == "path/to/compiled"
    assert pyproj.prepend_compiled_dagdir
    assert pyproj.local
    assert pyproj.log_level == "debug"
    assert pyproj.slurm_grace_period == 50
    assert pyproj.max_concurrent_runs == 2
    assert pyproj.container == "image.sif"
    assert pyproj.container_runtime == "apptainer"
    assert pyproj.container_binds == ["some/path"]
    assert pyproj.container_options == ["--nv"]
    assert pyproj.envs == {"ENV": "value"}
    assert pyproj.detach.job_name == "detached"
    assert pyproj.extra_dagdirs == ["sdag.extras"]
    assert pyproj.tags[0].tag == "online"
    assert not pyproj.tags[0].local
    assert pyproj.tags[0].envs == {"ENV": "another_value"}
    assert pyproj.tags[0].container == "tag.sif"
    assert pyproj.tags[0].container_runtime == "singularity"
    assert pyproj.tags[0].container_binds == ["other/path"]
    assert pyproj.tags[0].container_options == ["--nv"]


def test_parse_pyproject_invalid_tags(tmp_path: Path) -> None:
    """Tags must be formatted as lists with [[..]]

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """[tool.sdag.tags]
    tag = "online"
    local = true
    """
    path = tmp_path / "pyproject.toml"
    with path.open("w") as f:
        f.write(content)

    with pytest.raises(ValueError, match="valid list"):
        get_pyproj(str(path))


def test_parse_pyproject_no_tag_name(tmp_path: Path) -> None:
    """Tags must always contain the tag name.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """[[tool.sdag.tags]]
    local = true
    """
    path = tmp_path / "pyproject.toml"
    with path.open("w") as f:
        f.write(content)

    with pytest.raises(ValueError, match="type=missing"):
        get_pyproj(str(path))


def test_wrong_extra_dagdirs_are_blocked(tmp_path: Path) -> None:
    """Extras must be import strings.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """[[tool.sdag.tags]]
    extra-dagdirs = ["some/path"]
    """
    path = tmp_path / "pyproject.toml"
    with path.open("w") as f:
        f.write(content)

    with pytest.raises(ValueError, match="some/path"):
        get_pyproj(str(path))


def test_parse_pyproject_tag_is_not_obj(tmp_path: Path) -> None:
    """Tags must be objects.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = r"tool = {sdag = {tags = [2, 3, 4]}}"
    path = tmp_path / "pyproject.toml"
    with path.open("w") as f:
        f.write(content)

    with pytest.raises(ValueError, match="Input should be a valid dictionary"):
        get_pyproj(str(path))


def test_block_duplicate_tags(tmp_path: Path) -> None:
    """Check duplicate tag settings are blocked.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """[[tool.sdag.tags]]
    tag = "online"

    [[tool.sdag.tags]]
    tag = "small"

    [[tool.sdag.tags]]
    tag = "online"

    [[tool.sdag.tags]]
    tag = "small"

    [[tool.sdag.tags]]
    tag = "large"
    """
    path = tmp_path / "pyproject.toml"
    with path.open("w") as f:
        f.write(content)

    with pytest.raises(ValueError, match="online, small"):
        get_pyproj(str(path))


def test_parse_sdag_toml(tmp_path: Path) -> None:
    """Check the sdag.toml is parsed correctly.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """dagdir = "path/to/dagdir"
    compiled-dagdir = "path/to/compiled"
    prepend-compiled-dagdir = true
    log-level = "debug"
    slurm-grace-period = 50
    max-concurrent-runs = 2
    local = true
    extra-dagdirs = ["sdag.extras"]
    container = "image.sif"
    container-runtime = "apptainer"
    container-binds = ["some/path"]
    container-options = ["--nv"]

    [envs]
    ENV="value"

    [detach]
    job-name = "detached"

    [[tags]]
    tag = "online"
    local = false
    envs = {"ENV" = "another_value"}
    container = "tag.sif"
    container-runtime = "singularity"
    container-binds = ["other/path"]
    container-options = ["--nv"]
    """
    sdag_toml_path = tmp_path / ".sdag.toml"
    with sdag_toml_path.open("w") as f:
        f.write(content)

    missing_pyproj_path = tmp_path / "missing.toml"
    pyproj = get_pyproj(
        pyproj_path=str(missing_pyproj_path),
        sdag_toml_path=str(sdag_toml_path),
    )

    assert pyproj.dagdir == "path/to/dagdir"
    assert pyproj.compiled_dagdir == "path/to/compiled"
    assert pyproj.prepend_compiled_dagdir
    assert pyproj.local
    assert pyproj.log_level == "debug"
    assert pyproj.slurm_grace_period == 50
    assert pyproj.max_concurrent_runs == 2
    assert pyproj.container == "image.sif"
    assert pyproj.container_runtime == "apptainer"
    assert pyproj.container_binds == ["some/path"]
    assert pyproj.container_options == ["--nv"]
    assert pyproj.detach.job_name == "detached"
    assert pyproj.extra_dagdirs == ["sdag.extras"]
    assert pyproj.tags[0].tag == "online"
    assert not pyproj.tags[0].local
    assert pyproj.tags[0].envs == {"ENV": "another_value"}
    assert pyproj.tags[0].container == "tag.sif"
    assert pyproj.tags[0].container_runtime == "singularity"
    assert pyproj.tags[0].container_binds == ["other/path"]
    assert pyproj.tags[0].container_options == ["--nv"]


def test_join_pyproj_and_sdag_toml(tmp_path: Path) -> None:
    """Check pyproj and sdag.toml are merged correctly.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    pyproj_content = """[tool.sdag]
    dagdir = "path/to/dagdir"
    compiled-dagdir = "path/to/compiled"
    prepend-compiled-dagdir = true
    slurm-grace-period = 20
    local = true
    extra-dagdirs = ["sdag.pyproj", "sdag.common"]
    container = "pyproj.sif"
    container-binds = ["a/b", "a/c"]
    container-options = ["--nv"]

    [tool.sdag.envs]
    ENV = "value"
    OVERWRITTEN = "pyporj_value"

    [tool.sdag.detach]
    job-name = "detached"
    partition = "some-partition"

    [[tool.sdag.tags]]
    tag = "online"
    local = false
    container-runtime = "singularity"
    container = "overwritten.sif"

    [tool.sdag.tags.envs]
    PYPROJ_TAG_ENV = "pyproj_tag_value"
    SDAG_TAG_ENV = "pyproj_tag_value"


    [[tool.sdag.tags]]
    tag = "large"
    local = true
    envs = {"LARGE_ENV" = "large_value"}
    container-binds = ["a/b"]
    """

    sdag_toml_content = """compiled-dagdir = "path-alt"
    prepend-compiled-dagdir = false
    log-level = "debug"
    local = true
    extra-dagdirs = ["sdag.common", "sdag.sdag_toml"]
    container = "sdag.sif"
    container-runtime = "apptainer"
    container-binds = ["a/b", "a/d"]
    container-options = ["--writable-tmpfs"]

    [envs]
    ANOTHER_ENV = "another_value"
    OVERWRITTEN = "sdag_value"

    [detach]
    job-name = "overwritten"
    qos = "some-qos"

    [[tags]]
    tag = "online"
    local = true
    envs = {"SDAG_TAG_ENV" = "sdag_tag_value"}
    container-binds = ["a/b", "a/d"]
    container = "online.sif"
    container-runtime = "apptainer"

    [[tags]]
    tag = "small"
    local = true
    envs = {"SMALL_ENV" = "small_value"}
    container-options = ["--nv"]
    """

    pyproj_path = tmp_path / "pyproj.toml"
    with pyproj_path.open("w") as f:
        f.write(pyproj_content)

    sdag_toml_path = tmp_path / "sdag.toml"
    with sdag_toml_path.open("w") as f:
        f.write(sdag_toml_content)

    pyproj = get_pyproj(
        pyproj_path=str(pyproj_path), sdag_toml_path=str(sdag_toml_path)
    )
    pyproj.tags.sort(key=lambda t: t.tag)

    assert pyproj.dagdir == "path/to/dagdir"
    assert pyproj.compiled_dagdir == "path-alt"
    assert not pyproj.prepend_compiled_dagdir
    assert pyproj.local
    assert pyproj.log_level == "debug"
    assert pyproj.slurm_grace_period == 20
    assert pyproj.envs == {
        "ENV": "value",
        "ANOTHER_ENV": "another_value",
        "OVERWRITTEN": "sdag_value",
    }
    assert pyproj.container == "sdag.sif"
    assert pyproj.container_runtime == "apptainer"
    assert sorted(pyproj.container_binds) == ["a/b", "a/c", "a/d"]
    assert sorted(pyproj.container_options) == ["--nv", "--writable-tmpfs"]

    assert pyproj.tags[0].tag == "large"
    assert pyproj.tags[0].local
    assert pyproj.tags[0].envs == {"LARGE_ENV": "large_value"}
    assert pyproj.tags[0].container_binds == ["a/b"]
    assert pyproj.tags[1].tag == "online"
    assert pyproj.tags[1].local
    assert pyproj.tags[1].container_runtime == "apptainer"
    assert pyproj.tags[1].container == "online.sif"
    assert pyproj.tags[1].container_binds == ["a/b", "a/d"]
    assert pyproj.tags[1].envs == {
        "SDAG_TAG_ENV": "sdag_tag_value",
        "PYPROJ_TAG_ENV": "pyproj_tag_value",
    }
    assert pyproj.tags[2].tag == "small"
    assert pyproj.tags[2].local
    assert pyproj.tags[2].envs == {"SMALL_ENV": "small_value"}
    assert pyproj.tags[2].container_options == ["--nv"]
    assert pyproj.detach.job_name == "overwritten"
    assert pyproj.detach.partition == "some-partition"
    assert pyproj.detach.qos == "some-qos"
    assert sorted(pyproj.extra_dagdirs) == [
        "sdag.common",
        "sdag.pyproj",
        "sdag.sdag_toml",
    ]


def test_join_pyproj_detach_survives(tmp_path: Path) -> None:
    """Check detach settings explicitly set survive.

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    pyproj_content = """[tool.sdag]
    account = "pyproj-account"

    [tool.sdag.detach]
    job-name = "detach-job"
    partition = "detach-partition"
    """

    sdag_toml_content = """partition = "sdag-partition"
    qos = "sdag-qos"

    [detach]
    nodes = 2
    """

    pyproj_path = tmp_path / "pyproj.toml"
    with pyproj_path.open("w") as f:
        f.write(pyproj_content)

    sdag_toml_path = tmp_path / "sdag.toml"
    with sdag_toml_path.open("w") as f:
        f.write(sdag_toml_content)

    pyproj = get_pyproj(
        pyproj_path=str(pyproj_path), sdag_toml_path=str(sdag_toml_path)
    )

    assert pyproj.detach.job_name == "detach-job"
    assert pyproj.detach.account == "pyproj-account"
    assert pyproj.detach.partition == "detach-partition"
    assert pyproj.detach.qos == "sdag-qos"
    assert pyproj.detach.nodes == 2
    assert pyproj.detach.output is None


@pytest.mark.parametrize(
    argnames=("pyproj_dict", "cmd"),
    argvalues=[
        # task + null -> task
        ({}, "sbatch"),
        # task + global -> global
        ({"local": True}, "bash"),
        # task + global + null -> global
        ({"local": True, "tags": [{"tag": "TAG1"}]}, "bash"),
        # task + global + TAG1 -> TAG1
        (
            {
                "local": False,
                "tags": [{"tag": "TAG1", "local": True}],
            },
            "bash",
        ),
        # task + global + TAG1 + TAG2 -> TAG2
        (
            {
                "local": False,
                "tags": [
                    {"tag": "TAG1", "local": False},
                    {"tag": "TAG2", "local": True},
                ],
            },
            "bash",
        ),
    ],
)
def test_apply_pyproj_configs(pyproj_dict: dict[str, Any], cmd: str) -> None:
    """Check override priorities are respected.

    Args:
        pyproj_dict (dict[str, Any]): Pyproj dictionary.
        cmd (str): Expected task command.
    """
    pyproj = Pyproj.model_validate(pyproj_dict)
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        tags=["TAG1", "TAG2"],
        script=ScriptPath(path=Path("task.sh")),
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])

    apply_pyproj_configs(dag, pyproj)
    assert dag.nodes[0].kind == "task"
    assert dag.nodes[0].cmd == cmd


def test_override_script_path() -> None:
    """Check The script path is overwritten."""
    pyproj = Pyproj.model_validate(
        {"tags": [{"tag": "TAG1", "script-path": "tag.sh"}]}
    )
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        tags=["TAG1"],
        script=ScriptPath(path=Path("task.sh")),
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])

    apply_pyproj_configs(dag, pyproj)
    assert dag.nodes[0].kind == "task"
    assert dag.nodes[0].script == ScriptPath(path=Path("tag.sh"))


def test_override_all_slurm_cmds() -> None:
    """Check slurm commands are overwritten."""
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        tags=[],
        script=ScriptPath(path=Path()),
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])
    pyproj_dict = {
        "job-name": "job",
        "nodes": 2,
        "partition": "partiton",
        "qos": "qos",
        "gpus-per-node": 4,
        "ntasks-per-node": 3,
        "output": "out",
        "error": "err",
        "account": "acc",
        "cpus-per-task": 1,
        "mem": "1GB",
        "time": "00:01:00",
    }

    pyproj = Pyproj.model_validate(pyproj_dict)
    apply_pyproj_configs(dag, pyproj)

    assert task.slurm.model_dump(exclude_none=True) == pyproj_dict


def test_hardcoded_slurm_settings_are_preserved() -> None:
    """Check hardcoded sbatch options are not overwritten."""
    pyproj_options = {
        "job-name": "job",
        "nodes": 2,
        "partition": "partiton",
        "qos": "qos",
        "gpus-per-node": 2,
        "ntasks-per-node": 2,
        "output": "out",
        "error": "err",
        "account": "acc",
        "cpus-per-task": 2,
        "mem": "2GB",
        "time": "00:02:00",
    }
    hardcoded_options = {
        "job-name": "job-hard",
        "nodes": 1,
        "partition": "partiton-hard",
        "qos": "qos-hard",
        "gpus-per-node": 1,
        "ntasks-per-node": 1,
        "output": "out-hard",
        "error": "err-hard",
        "account": "acc-hard",
        "cpus-per-task": 1,
        "mem": "1GB",
        "time": "00:01:00",
    }
    pyproj = Pyproj.model_validate(pyproj_options)
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        script=ScriptPath(path=Path()),
        slurm=SlurmOverride.model_validate(hardcoded_options),
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])
    apply_pyproj_configs(dag, pyproj)

    assert dag.nodes[0].kind == "task"
    assert (
        dag.nodes[0].slurm.model_dump(exclude_none=True) == hardcoded_options
    )


def test_slurm_override_priority() -> None:
    """Check priorities are respected."""
    pyproj_options = {
        "nodes": 2,
        "job-name": "job",
    }
    hardcoded_options = {
        "nodes": 1,
        "qos": "qos-hard",
    }
    pyproj = Pyproj.model_validate(pyproj_options)
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        script=ScriptPath(path=Path()),
        slurm=SlurmOverride.model_validate(hardcoded_options),
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])
    apply_pyproj_configs(dag, pyproj)

    assert dag.nodes[0].kind == "task"
    assert dag.nodes[0].slurm.job_name == "job"
    assert dag.nodes[0].slurm.nodes == 1
    assert dag.nodes[0].slurm.qos == "qos-hard"


def test_override_environment_variables() -> None:
    """Check environment variables are correctly overwritten.

    The correct priority is: hardcoded > tag > pyproj.
    """
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        tags=["TAG2"],
        script=ScriptPath(path=Path()),
        envs={"ENV_TASK": "task_value", "HARDCODED": "task_value"},
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])

    pyproj_dict = {
        "envs": {
            "OVERWRITTEN_PYPROJ": "pyproj_value",
            "OVERWRITTEN_TAG": "pyproj_value",
            "ENV_PYPROJ": "pyproj_value",
            "HARDCODED": "pyproj_value",
        },
        "tags": [
            {
                "tag": "TAG2",
                "envs": {
                    "OVERWRITTEN_TAG": "tag_value",
                    "ENV_TAG": "tag_value",
                    "HARDCODED": "tag_value",
                },
            }
        ],
    }

    pyproj = Pyproj.model_validate(pyproj_dict)
    apply_pyproj_configs(dag, pyproj)

    assert task.envs["OVERWRITTEN_TAG"] == "tag_value"
    assert task.envs["OVERWRITTEN_PYPROJ"] == "pyproj_value"
    assert task.envs["ENV_TASK"] == "task_value"
    assert task.envs["ENV_PYPROJ"] == "pyproj_value"
    assert task.envs["ENV_TAG"] == "tag_value"
    assert task.envs["HARDCODED"] == "task_value"


def test_override_slurm_from_tag() -> None:
    """Check slurm commands are overwritten by tags."""
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        tags=["TAG2"],
        script=ScriptPath(path=Path()),
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])
    pyproj_dict = {
        "job-name": "job-1",
        "nodes": 1,
        "partition": "partiton-1",
        "qos": "qos-1",
        "gpus-per-node": 1,
        "ntasks-per-node": 1,
        # output intentionally skipped
        "error": "err-1",
        "account": "acc-1",
        "cpus-per-task": 1,
        "mem": "1GB",
        "time": "00:01:00",
        "tags": [
            {
                "tag": "TAG2",
                "job-name": "job-2",
                "nodes": 2,
                "partition": "partiton-2",
                "qos": "qos-2",
                "gpus-per-node": 2,
                "ntasks-per-node": 2,
                "output": "out-2",
                "error": "err-2",
                "account": "acc-2",
                "cpus-per-task": 2,
                "mem": "2GB",
                "time": "00:02:00",
            }
        ],
    }

    pyproj = Pyproj.model_validate(pyproj_dict)
    apply_pyproj_configs(dag, pyproj)

    tag_slurm = pyproj_dict["tags"][0].copy()
    tag_slurm.pop("tag")

    assert task.slurm.model_dump(exclude_none=True) == tag_slurm


def test_join_args_into_detach(tmp_path: Path) -> None:
    pyproj_content = """[tool.sdag]
        account = "account-name"
        partition = "partition-name"
        qos = "qos-name"
        time = "1-00:00:00"

        [tool.sdag.detach]
        job-name = "detach"
        qos = "special-qos"
        """

    pyproj_path = tmp_path / "pyproject.toml"
    # so we don't read the main one by accident
    sdag_toml_path = tmp_path / "missing.toml"
    with pyproj_path.open("w") as f:
        f.write(pyproj_content)

    pyproj = get_pyproj(
        pyproj_path=str(pyproj_path), sdag_toml_path=str(sdag_toml_path)
    )

    assert pyproj.detach.job_name == "detach"

    assert pyproj.detach.account == "account-name"
    assert pyproj.detach.partition == "partition-name"
    assert pyproj.detach.qos == "special-qos"
    assert pyproj.detach.time == "1-00:00:00"


class TestDetachOptions:
    """Test the job detaching options."""

    def test_get_detached_args(self) -> None:
        """Check detached args are correctly retrieved."""
        detach = DetachOptions.model_validate({"job-name": "detach"})
        assert detach.get_detached_args() == [
            "--cpus-per-task",
            "1",
            "--error",
            r"logs/sdag/sdag_%x.%j.err",
            "--job-name",
            "detach",
            "--nodes",
            "1",
            "--ntasks-per-node",
            "1",
            "--output",
            r"logs/sdag/sdag_%x.%j.out",
        ]


def test_apply_pyproj_to_task() -> None:
    """Check priorities are respected."""
    task = TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="sbatch",
        scope="local",
        retries=0,
        tags=["online", "gpu"],
        envs={"KEY1": "task_value"},
        script=ScriptPath(path=Path()),
        slurm=SlurmOverride(output="output_task.out"),
        container_binds=["path/task"],
        container_options=["--nv"],
    )

    pyproj = Pyproj.model_validate(
        {
            "nodes": 1,
            "container-runtime": "singularity",
            "output": "output_pyproj.out",
            "envs": {"KEY1": "pyproj_value"},
            "tags": [
                {
                    "tag": "online",
                    "local": True,
                    "nodes": 2,
                    "error": "error_tag.err",
                    "container-binds": ["path/online"],
                    "container-options": ["--writable-tmpfs"],
                },
                {
                    "tag": "gpu",
                    "nodes": 3,
                    "container-runtime": "apptainer",
                    "script-path": Path("gpu-script.sh"),
                    "container-binds": ["path/task"],
                },
            ],
        }
    )

    apply_pyproj_to_task(task, pyproj)
    assert task.cmd == "bash"
    assert task.slurm.nodes == 3
    assert task.slurm.output == "output_task.out"
    assert task.slurm.error == "error_tag.err"
    assert task.envs == {"KEY1": "task_value"}
    assert task.container_runtime == "apptainer"
    assert task.container_binds == ["path/online", "path/task"]
    assert task.container_options == ["--writable-tmpfs", "--nv"]
    assert task.script.kind == "script_path"
    assert task.script.path == Path("gpu-script.sh")
