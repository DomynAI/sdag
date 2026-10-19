# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any

import pytest
from sdag.models import DAG, DAGMeta, SlurmOverride, TaskNode
from sdag.pyproj import DetachOptions, Pyproj, apply_pyproj_configs, get_pyproj
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

    [tool.sdag.envs]
    ENV="value"

    [tool.sdag.detach]
    job-name = "detached"

    [[tool.sdag.tags]]
    tag = "online"
    local = false
    envs = {"ENV" = "another_value"}
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
    assert pyproj.envs == {"ENV": "value"}
    assert pyproj.tags[0].tag == "online"
    assert not pyproj.tags[0].local
    assert pyproj.tags[0].envs == {"ENV": "another_value"}
    assert pyproj.detach.job_name == "detached"
    assert pyproj.extra_dagdirs == ["sdag.extras"]


def test_parse_pyproject_invalid_tags(tmp_path: Path) -> None:
    """Tags must be formatted as lists with [[..]]

    Args:
        tmp_path (Path): Temporary path fixture.
    """
    content = """[tool.sdag.tags]
    tag = "online"
    cmd = "sbatch"
    """
    path = tmp_path / "pyproject.toml"
    with path.open("w") as f:
        f.write(content)

    with pytest.raises(TypeError, match="list"):
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

    with pytest.raises(ValueError, match="name"):
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

    with pytest.raises(TypeError, match="dictionaries"):
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

    [envs]
    ENV="value"

    [detach]
    job-name = "detached"

    [[tags]]
    tag = "online"
    local = false
    envs = {"ENV" = "another_value"}
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
    assert pyproj.tags[0].tag == "online"
    assert not pyproj.tags[0].local
    assert pyproj.detach.job_name == "detached"
    assert pyproj.extra_dagdirs == ["sdag.extras"]


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

    [tool.sdag.envs]
    ENV = "value"
    OVERWRITTEN = "pyporj_value"

    [tool.sdag.detach]
    job-name = "detached"
    partition = "some-partition"

    [[tool.sdag.tags]]
    tag = "online"
    local = false
    envs = {"PYPROJ_TAG_ENV" = "pyproj_tag_value"}

    [[tool.sdag.tags]]
    tag = "large"
    local = true
    envs = {"LARGE_ENV" = "large_value"}
    """

    sdag_toml_content = """compiled-dagdir = "path-alt"
    prepend-compiled-dagdir = false
    log-level = "debug"
    local = true
    extra-dagdirs = ["sdag.common", "sdag.sdag_toml"]

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

    [[tags]]
    tag = "small"
    local = true
    envs = {"SMALL_ENV" = "small_value"}
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

    assert pyproj.tags[0].tag == "large"
    assert pyproj.tags[0].local
    assert pyproj.tags[0].envs == {"LARGE_ENV": "large_value"}
    assert pyproj.tags[1].tag == "online"
    assert pyproj.tags[1].local
    assert pyproj.tags[1].envs == {"SDAG_TAG_ENV": "sdag_tag_value"}
    assert pyproj.tags[2].tag == "small"
    assert pyproj.tags[2].local
    assert pyproj.tags[2].envs == {"SMALL_ENV": "small_value"}
    assert pyproj.detach.job_name == "overwritten"
    assert pyproj.detach.partition == "some-partition"
    assert pyproj.detach.qos == "some-qos"
    assert sorted(pyproj.extra_dagdirs) == [
        "sdag.common",
        "sdag.pyproj",
        "sdag.sdag_toml",
    ]


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
        {"tags": [{"tag": "TAG1", "script_path": "tag.sh"}]}
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

    assert task.slurm.model_dump() == pyproj_dict


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
    assert dag.nodes[0].slurm.model_dump() == hardcoded_options


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
    """Check environment variables are correctly overwritten."""
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
        envs={
            "ENV_TASK": "task_value",
            "OVERWRITTEN_PYPROJ": "task_value",
            "OVERWRITTEN_TAG": "task_value",
        },
    )
    dag = DAG(meta=DAGMeta(pipeline_name="pipe"), nodes=[task])

    pyproj_dict = {
        "envs": {
            "OVERWRITTEN_PYPROJ": "pyproj_value",
            "OVERWRITTEN_TAG": "pyproj_value",
            "ENV_PYPROJ": "pyproj_value",
        },
        "tags": [
            {
                "tag": "TAG2",
                "envs": {
                    "OVERWRITTEN_TAG": "tag_value",
                    "ENV_TAG": "tag_value",
                },
            }
        ],
    }

    pyproj = Pyproj.model_validate(pyproj_dict)
    apply_pyproj_configs(dag, pyproj)

    assert task.envs == {
        "OVERWRITTEN_TAG": "tag_value",
        "OVERWRITTEN_PYPROJ": "pyproj_value",
        "ENV_TASK": "task_value",
        "ENV_PYPROJ": "pyproj_value",
        "ENV_TAG": "tag_value",
    }


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

    assert task.slurm.model_dump() == tag_slurm


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
        detach = DetachOptions.model_validate(
            {
                "job-name": "detach",
                "nodes": None,
                "ntasks-per-node": None,
                "cpus-per-task": None,
                "output": None,
                "error": None,
            }
        )
        assert detach.get_detached_args() == ["--job-name", "detach"]
