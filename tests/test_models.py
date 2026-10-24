# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from sdag.exceptions import POSIXOverrideError
from sdag.models import ArtifactEdge, EndNode, Kwarg, TaskNode
from sdag.scripts import ScriptPath
from sdag.settings import get_compile_settings
from test_e2e import set_home  # noqa: F401


@pytest.fixture
def task() -> TaskNode:
    return TaskNode(
        uid=0,
        name="task_name",
        fn_name="task_fn",
        cache="none",
        code_hash="xyz",
        mode="ext",
        cmd="bash",
        scope="global",
        retries=0,
        script=ScriptPath(path=Path()),
    )


def test_endnode_artifact_join(task: TaskNode) -> None:
    task.register_artifact(key="a", path=Path("a/path"))
    end = EndNode(uid=1)
    end.join_artifacts(task)
    assert end.artifacts["task_name"] == task.artifacts


@pytest.mark.parametrize(
    argnames="key", argvalues=["path", "user", "shell", "home"]
)
def test_external_task_with_posix_variable_validation(
    key: str, task: TaskNode
) -> None:
    with pytest.raises(POSIXOverrideError):
        task.add_kwarg(Kwarg(key=key, value="a/path"))


@pytest.mark.usefixtures("set_home")
def test_bind_dirs(task: TaskNode, tmp_path: Path) -> None:
    """Check artifacts and sdag dirs are binded correctly.

    Args:
        task (TaskNode): Task.
        tmp_path (Path): Temporary path fixture.
    """
    get_compile_settings.cache_clear()
    task.output_artifacts = [ArtifactEdge(name="a", path=Path("a/b"))]
    task.container_binds = ["a/b", "a/c"]
    bind_dirs = task._resolve_bind_dirs()
    print(
        sorted(
            [
                str(tmp_path / ".sdag"),
                str(Path.cwd()),
                str(Path("a/b").resolve()),
                str(Path("a/c").resolve()),
            ]
        )
    )
    assert bind_dirs == sorted(
        [
            str(tmp_path / ".sdag"),
            str(Path.cwd()),
            str(Path("a/b").resolve()),
            str(Path("a/c").resolve()),
        ]
    )


@pytest.mark.parametrize(
    argnames=("container", "launcher"),
    argvalues=[
        ("", ""),
        ("sdag.sif", "singularity exec --bind path --nv sdag.sif"),
    ],
)
def test_resolve_launcher(
    container: str, launcher: str, task: TaskNode
) -> None:
    """Check the launcher is resolved correctly.

    Args:
        container (str): Container name.
        launcher (str): Expected launcher string.
        task (TaskNode): Task node.
    """
    task.container = container
    task.container_runtime = "singularity"
    binds = "--bind path"
    options = "--nv"
    assert task._resolve_launcher(binds, options) == launcher


@pytest.mark.usefixtures("set_home")
def test_set_envs(task: TaskNode, tmp_path: Path) -> None:
    """Check container envs are correctly set.

    Args:
        task (TaskNode): Task node.
        tmp_path (Path): Temporary path fixture.
    """
    get_compile_settings.cache_clear()

    task.container = "sdag.sif"
    task.container_runtime = "apptainer"
    task.container_binds = ["a/b"]
    task.container_options = ["--nv"]

    task.set_envs()

    bind_list = sorted(
        [
            str(tmp_path / ".sdag"),
            str(Path.cwd()),
            str(Path("a/b").resolve()),
        ]
    )
    binds = " ".join(f"--bind={bind}" for bind in bind_list)
    options = "--nv"
    container = str(Path("sdag.sif").resolve())
    launcher = f"apptainer exec {binds} {options} {container}"

    assert task.envs["SDAG_CONTAINER"] == container
    assert task.envs["SDAG_CONTAINER_RUNTIME"] == "apptainer"
    assert task.envs["SDAG_CONTAINER_OPTIONS"] == options
    assert task.envs["SDAG_CONTAINER_BINDS"] == binds
    assert task.envs["SDAG_LAUNCHER"] == launcher


def test_expand_user_ro_singularity_bind(task: TaskNode) -> None:
    """Check user-selected binds with ~ and : are handled.

    Args:
        task (TaskNode): Task.
    """
    bind = "~/x:/mnt:ro"
    expanded = task._expand_user_singularity_bind(bind)
    home = Path("~").expanduser().resolve()

    assert expanded == f"{home}/x:/mnt:ro"


def test_expand_standard_singularity_bind(task: TaskNode) -> None:
    """Check user-selected relative binds are correctly handled.

    Args:
        task (TaskNode): Task.
    """
    bind = "data/x"
    expanded = task._expand_user_singularity_bind(bind)
    base = Path().expanduser().resolve()

    assert expanded == f"{base}/data/x"


def test_expand_src_dst_singularity_bind(task: TaskNode) -> None:
    """Check user-selected src:/mnt binds are correctly handled.

    Args:
        task (TaskNode): Task.
    """
    bind = "src:/mnt"
    expanded = task._expand_user_singularity_bind(bind)
    base = Path().expanduser().resolve()

    assert expanded == f"{base}/src:/mnt"


def test_expand_absolute_singularity_bind(
    task: TaskNode, tmp_path: Path
) -> None:
    """Check user-selected absolute binds are correctly handled.

    Args:
        task (TaskNode): Task.
        tmp_path (Path): Temporary path fixture.
    """
    bind = str(tmp_path.resolve())
    expanded = task._expand_user_singularity_bind(bind)
    assert expanded == bind
