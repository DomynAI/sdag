# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import logging

from sdag.models import DAG, NodeUnion, TaskNode

logger = logging.getLogger(__name__)


def find_all_cacheable_tasks(dag: DAG) -> list[str]:
    """Find tasks with caching enabled.

    Args:
        dag (DAG): DAG.

    Returns:
        list[str]: Cacheable task json strings.
    """
    tasks = _find_all_cacheable_tasks(dag)
    return [task.model_dump_json() for task in tasks]


def find_matching_cacheable_tasks(dag: DAG, tasks: list[str]) -> list[str]:
    """Find tasks with caching enabled mathing user choice.

    Args:
        dag (DAG): DAG.
        tasks (list[str]): Tasks selected by the user.

    Returns:
        list[str]: Cacheable task json strings.
    """
    all_tasks = _find_all_cacheable_tasks(dag)
    return [
        task.model_dump_json() for task in all_tasks if task.name in set(tasks)
    ]


def find_cascade_cacheable_tasks(dag: DAG, tasks: list[str]) -> list[str]:
    """Find cacheable tasks in cascade mode.

    Args:
        dag (DAG): DAG.
        tasks (list[str]): Tasks.

    Returns:
        list[str]: Cacheable task json strings.
    """
    children: dict[int, list[int]] = {}
    _nodes: dict[int, NodeUnion] = {}
    found: set[int] = set()

    for node in dag.nodes:
        _nodes[node.uid] = node
        if node.kind == "task" and node.name in tasks:
            found.add(node.uid)
        for parent in node.parents:
            childs = children.setdefault(parent.uid, [])
            childs.append(node.uid)

    visited: set[int] = set()
    to_be_visited = list(found)
    while to_be_visited:
        uid = to_be_visited.pop()
        if uid not in visited:
            visited.add(uid)
            to_be_visited.extend(children.get(uid, []))

    seen: set[tuple[str, str]] = set()
    cacheable_tasks: list[str] = []
    for uid in sorted(visited):
        node = _nodes[uid]
        if node.kind == "task" and node.cache != "none":
            key = node.name, node.pipeline_name
            if key not in seen:
                seen.add(key)
                cacheable_tasks.append(node.model_dump_json())

    return cacheable_tasks


def _find_all_cacheable_tasks(dag: DAG) -> list[TaskNode]:
    """Find tasks with caching enabled.

    Args:
        dag (DAG): DAG.

    Returns:
        list[TaskNode]: Tasks with caching enabled.
    """
    return [
        node
        for node in dag.nodes
        if node.kind == "task" and node.cache != "none"
    ]
