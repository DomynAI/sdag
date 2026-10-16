# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from sdag.exceptions import POSIXOverrideError
from sdag.models import EndNode, Kwarg, TaskNode
from sdag.scripts import ScriptPath


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
