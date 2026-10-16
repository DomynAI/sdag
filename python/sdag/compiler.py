# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Compiler.

It relies on two global objects everyone has
access to, so it is not thread safe.
"""

import logging
from typing import TYPE_CHECKING

from sdag.exceptions import DAGNotSetError, TaskNotUniqueError
from sdag.models import (
    DAG,
    ClosedClause,
    CompiledDAG,
    DAGMeta,
    EndNode,
    NodeUnion,
    RootNode,
    TraceScope,
)

if TYPE_CHECKING:
    from sdag.wrappers import Pipeline, Task

logger = logging.getLogger(__name__)


class SDAG:
    """Master.

    Keeps track of the imported pipelines and tasks.
    An error is raised is two tasks with the same name
    are imported.

    Attributes:
        tasks (dict[str, Task]): Imported (global) tasks.
        pipelines (dict[str, Pipeline]): Imported pipelines.
    """

    def __init__(self):
        """Initialize the master."""
        self.tasks: dict[str, Task] = {}
        self.pipelines: dict[str, Pipeline] = {}

    def add_pipeline(self, pipeline: "Pipeline") -> None:
        """Add a pipeline.

        Args:
            pipeline (Pipeline): Pipeline imported.
        """
        self.pipelines[pipeline.fn.__name__] = pipeline

    def add_task(self, task: "Task") -> None:
        """Add a task.

        Args:
            task (Task): Add a task.

        Raises:
            TaskNotUniqueError: The task is not unique.
        """
        if task.fn.__name__ in self.tasks:
            raise TaskNotUniqueError(name=task.fn.__name__)
        self.tasks[task.fn.__name__] = task

    def _reset(self) -> None:
        self.tasks = {}
        self.pipelines = {}


class DAGCompiler:
    """Compiler.

    It does most of the magic, keeps track of
    the graph and updates it when tasks are
    executed.

    Attributes:
        outer (list[CompiledDAG]): Pipelines being compiled.
        active (CompiledDAG | None): Active pipeline compiled.
        _uid (int): Used to assign monotonically increasing uids.
    """

    def __init__(self):
        """Initialize the compiler."""
        self.outer: list[CompiledDAG] = []
        self.active: CompiledDAG | None = None
        self._uid = 0

    def reset(self) -> None:
        """Reset the compiler state.

        Called before every compiled pipeline.
        """
        self.outer = []
        self.active = None
        self._uid = 0

    def get_uid(self) -> int:
        """Get a new uid.

        Returns:
            int: Unique id.
        """
        uid = self._uid
        self._uid += 1
        return uid

    def register(self, node: NodeUnion) -> None:
        """Register a node in the graph.

        If a branch scope is currently active, the node is given a
        branch edge to it, tying it to that branch's true/false path.

        Args:
            node (NodeUnion): Node.

        Raises:
            DAGNotSetError: Attempting to register a node
                but no pipelines are being compiled.
        """
        if self.active is None:
            raise DAGNotSetError

        if not node.pipeline_name:
            name = self.active.dag.meta.pipeline_name
            node.pipeline_name = name
            node.root_uid = self.active.root.uid

        self.active.dag.nodes.append(node)

        anchor = self.active.scope.anchor
        if anchor is not None:
            node.add_branch_edge(anchor[0], anchor[1])

    @property
    def current_scope(self) -> TraceScope:
        """TraceScope currently active in the pipeline being traced.

        Raises:
            DAGNotSetError: No pipelines are being compiled.

        Returns:
            TraceScope: Current scope.
        """
        if self.active is None:
            raise DAGNotSetError
        return self.active.scope

    def push_scope(self, anchor: tuple[int, bool] | None) -> TraceScope:
        """Enter a new lexical scope, e.g. an If/Elif/Else body.

        Args:
            anchor (tuple[int, bool] | None): (branch_uid, branch_value)
                stamped on every node registered in the new scope.

        Returns:
            TraceScope: The newly active scope.
        """
        scope = TraceScope(parent=self.current_scope, anchor=anchor)
        self.active.scope = scope  # type: ignore
        return scope

    def pop_scope(self) -> TraceScope:
        """Exit the current lexical scope, restoring its parent.

        Raises:
            DAGNotSetError: No pipelines are being compiled, or
                attempting to pop the pipeline's root scope.

        Returns:
            TraceScope: The scope that was just closed.
        """
        closed = self.current_scope
        if closed.parent is None:
            raise DAGNotSetError
        self.active.scope = closed.parent  # type: ignore
        return closed

    def close_clause(
        self,
        branch_uid: int,
        next_edge_value: bool,
        terminal: bool = False,  # noqa: FBT002
    ) -> None:
        """Record a closed branch for the next Elif/Else.

        Args:
            branch_uid (int): Uid of the BranchNode the clause evaluated.
            next_edge_value (bool): Branch edge value a following
                Elif/Else must depend on.
            terminal (bool): True if this clause was an Else, closing
                the chain to further Elif/Else.
        """
        self.current_scope.last_clause = ClosedClause(
            branch_uid=branch_uid,
            next_edge_value=next_edge_value,
            terminal=terminal,
        )

    def set_dag(self, root: RootNode, import_path: str | None = None) -> None:
        """Set a new dag.

        Every time a new pipeline is called.

        Args:
            root (RootNode): Pipeline root node.
            import_path (str | None, optional): Pipeline import path.
                If null, it defaults to the pipeline name.
                Defaults to None.
        """
        name = root.pipeline_name
        import_path = import_path if import_path is not None else name
        dag = DAG(meta=DAGMeta(pipeline_name=name, import_path=import_path))
        end = EndNode(
            uid=self.get_uid(), root_uid=root.uid, pipeline_name=name
        )
        active = CompiledDAG(dag=dag, root=root, end=end)

        if self.active is not None:
            self.outer.append(self.active)

        self.active = active
        self.register(root)

    def get_dag(self) -> tuple[DAG, RootNode, EndNode]:
        """Detach a dag from the compiler.

        Raises:
            DAGNotSetError: No DAGs are set.

        Returns:
            tuple[DAG, RootNode, EndNode]: Graph, root, and endnode.
        """
        if self.active is None:
            raise DAGNotSetError

        dag = self.active.dag
        root = self.active.root
        end = self.active.end
        parent_uids = set()

        for node in dag.nodes:
            if not node.parents and node.uid not in (root.uid, end.uid):
                node.add_logical_edge(root.uid)
            for parent in node.parents:
                parent_uids.add(parent.uid)

        for node in dag.nodes:
            if node.uid not in parent_uids:
                end.add_logical_edge(node.uid)
        self.register(end)

        if self.outer:
            self.active = self.outer.pop()
            self.active.dag.nodes.extend(dag.nodes)

            anchor = self.active.scope.anchor
            if anchor is not None:
                root.add_branch_edge(anchor[0], anchor[1])

        else:
            self.active = None

        return dag, root, end


compiler = DAGCompiler()
"""Compiler."""


master = SDAG()
"""Keeps track of imported pipelines and tasks."""
