# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import logging

from sdag.models import DAG, CacheableTask, NodeUnion

logger = logging.getLogger(__name__)


def find_all_cacheable_tasks(dag: DAG) -> list[CacheableTask]:
    """Find tasks with caching enabled.

    Args:
        dag (DAG): DAG.
        scope (Literal["local", "global"]): Task scope.

    Returns:
        list[CacheableTask]: Info about tasks with caching
            enabled.
    """
    tasks: list[CacheableTask] = []
    for node in dag.nodes:
        if node.kind == "task" and node.cache != "none":
            cacheable = CacheableTask(
                name=node.name, pipeline=node.pipeline_name, scope=node.scope
            )
            tasks.append(cacheable)

    return tasks


def find_matching_cacheable_tasks(
    dag: DAG, tasks: list[str]
) -> list[CacheableTask]:
    """."""
    all_tasks = find_all_cacheable_tasks(dag)
    return [task for task in all_tasks if task.name in set(tasks)]


def find_all_cascade_cacheable_tasks(
    dag: DAG, tasks: list[str]
) -> list[CacheableTask]:
    """Find all cacheable tasks in cascade mode.

    Args:
        dag (DAG): DAG.
        tasks (list[str]): Tasks.

    Returns:
        list[CacheableTask]: Tasks.
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
    cacheable_tasks: list[CacheableTask] = []
    for uid in sorted(visited):
        node = _nodes[uid]
        if node.kind == "task" and node.cache != "none":
            key = node.name, node.pipeline_name
            if key not in seen:
                seen.add(key)
                task = CacheableTask(
                    name=node.name,
                    pipeline=node.pipeline_name,
                    scope=node.scope,
                )
                cacheable_tasks.append(task)

    return cacheable_tasks
