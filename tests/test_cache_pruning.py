# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from sdag.cache_pruning import (
    find_all_cacheable_tasks,
    find_cascade_cacheable_tasks,
    find_matching_cacheable_tasks,
)
from sdag.models import DAG, DAGMeta, LogicalParent, Parent, TaskNode
from sdag.scripts import ScriptPath


@pytest.fixture(scope="module")
def dag() -> DAG:
    """DAG to test cacheable task retrieval.

    It has dependent tasks and tasks with the
    same name.

    Returns:
        DAG: DAG.
    """
    return DAG(
        meta=DAGMeta(pipeline_name="dag"),
        nodes=[
            TaskNode(
                uid=0,
                fn_name="t0",
                name="t0",
                pipeline_name="self",
                cache="io",
                scope="local",
                code_hash="abc",
                mode="wrap",
                cmd="bash",
                retries=0,
                script=ScriptPath(path=Path("script.sh")),
            ),
            TaskNode(
                uid=1,
                fn_name="t1",
                name="t1",
                pipeline_name="self",
                cache="none",
                scope="local",
                code_hash="abc",
                mode="wrap",
                cmd="bash",
                retries=0,
                script=ScriptPath(path=Path("script.sh")),
            ),
            TaskNode(
                uid=2,
                fn_name="t2",
                name="t2",
                pipeline_name="self",
                cache="task",
                scope="local",
                code_hash="abc",
                mode="wrap",
                cmd="bash",
                retries=0,
                script=ScriptPath(path=Path("script.sh")),
                parents=[Parent(uid=0, kind=LogicalParent())],
            ),
            TaskNode(
                uid=3,
                fn_name="t3",
                name="t0",
                pipeline_name="other",
                cache="project",
                scope="local",
                code_hash="abc",
                mode="wrap",
                cmd="bash",
                retries=0,
                script=ScriptPath(path=Path("script.sh")),
                parents=[
                    Parent(uid=2, kind=LogicalParent()),
                    Parent(uid=1, kind=LogicalParent()),
                ],
            ),
        ],
    )


def test_find_all_cacheable_tasks(dag: DAG) -> None:
    """Identify all cacheable tasks.

    Args:
        dag (DAG): _description_
    """
    tasks_json = find_all_cacheable_tasks(dag)
    names: list[tuple[str, str]] = []
    for task_json in tasks_json:
        task = TaskNode.model_validate_json(task_json)
        names.append((task.name, task.pipeline_name))

    assert sorted(names) == [("t0", "other"), ("t0", "self"), ("t2", "self")]


@pytest.mark.parametrize(
    argnames=("tasks", "found"),
    argvalues=[
        (["t0"], [("t0", "other"), ("t0", "self")]),
        (["t1"], []),
        (["t2"], [("t2", "self")]),
        (["t1", "t2"], [("t2", "self")]),
        (["t0", "t2"], [("t0", "other"), ("t0", "self"), ("t2", "self")]),
    ],
)
def test_find_all_matching_cacheable_tasks(
    tasks: list[str], found: list[tuple[str, str]], dag: DAG
) -> None:
    """Find all matching cacheable tasks.

    Args:
        tasks (list[str]): User-selected task names.
        found (list[tuple[str, str]]): Expected tasks found in the
            form (task_name, pipeline_name).
        dag (DAG): DAG.
    """
    tasks_json = find_matching_cacheable_tasks(dag, tasks)
    names: list[tuple[str, str]] = []
    for task_json in tasks_json:
        task = TaskNode.model_validate_json(task_json)
        names.append((task.name, task.pipeline_name))

    assert sorted(names) == found


@pytest.mark.parametrize(
    argnames=("tasks", "found"),
    argvalues=[
        (["t0"], [("t0", "other"), ("t0", "self"), ("t2", "self")]),
        (["t1"], [("t0", "other")]),
        (["t2"], [("t0", "other"), ("t2", "self")]),
        (["t1", "t2"], [("t0", "other"), ("t2", "self")]),
        (["t0", "t2"], [("t0", "other"), ("t0", "self"), ("t2", "self")]),
    ],
)
def test_find_cascade_cacheable_tasks(
    tasks: list[str], found: list[tuple[str, str]], dag: DAG
) -> None:
    """Find all matching cacheable tasks in cascade mode.

    Args:
        tasks (list[str]): User-selected task names.
        found (list[tuple[str, str]]): Expected tasks found in the
            form (task_name, pipeline_name).
        dag (DAG): DAG.
    """
    tasks_json = find_cascade_cacheable_tasks(dag, tasks)
    names: list[tuple[str, str]] = []
    for task_json in tasks_json:
        task = TaskNode.model_validate_json(task_json)
        names.append((task.name, task.pipeline_name))

    assert sorted(names) == found
