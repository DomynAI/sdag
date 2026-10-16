# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from sdag.compiler import SDAG, DAGCompiler
from sdag.exceptions import DAGNotSetError, TaskNotUniqueError
from sdag.models import RootNode, TaskNode
from sdag.scripts import ScriptPath


class TestSDAG:
    @pytest.fixture
    def sdag(self) -> SDAG:
        return SDAG()

    def test_add_pipeline(self, sdag: SDAG) -> None:
        from sdag.wrappers import Pipeline

        def foo(): ...

        pipeline = Pipeline(foo)
        sdag.add_pipeline(pipeline)
        assert "foo" in sdag.pipelines

    def test_add_task(self, sdag: SDAG) -> None:
        from sdag.wrappers import Task

        def foo(): ...

        task = Task(
            foo,
            name="task",
            cmd="bash",
            mode="wrap",
            scope="global",
            cache="none",
            cache_ignore=None,
            cache_size=1,
            retries=0,
            script=ScriptPath(path=Path("a/path")),
            tags=[],
            njobs=1,
        )

        sdag.add_task(task)
        assert "foo" in sdag.tasks
        with pytest.raises(TaskNotUniqueError):
            sdag.add_task(task)


class TestDAGCompiler:
    @pytest.fixture
    def compiler(self) -> DAGCompiler:
        return DAGCompiler()

    def test_set_dag(self, compiler: DAGCompiler) -> None:
        root = RootNode(uid=0, pipeline_name="dag")
        compiler.set_dag(root)
        assert compiler.active is not None
        assert compiler.active.dag.meta.pipeline_name == "dag"
        assert compiler.active.dag.nodes[0].kind == "root"
        assert compiler.active.root.kind == "root"
        assert compiler.active.end.kind == "end"

    def test_get_uid(self, compiler: DAGCompiler) -> None:
        for i in range(10):
            assert compiler.get_uid() == i

    def test_reset(self, compiler: DAGCompiler) -> None:
        uid = compiler.get_uid()
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        compiler.reset()

        assert not compiler.outer
        assert compiler.active is None
        assert compiler.get_uid() == uid

    def test_get_dag(self, compiler: DAGCompiler) -> None:
        task = TaskNode(
            uid=5,
            name="task",
            fn_name="task",
            cache="none",
            code_hash="xyz",
            mode="wrap",
            cmd="bash",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
        )
        compiler.reset()
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        compiler.register(task)
        dag, root, end = compiler.get_dag()

        assert task.parents[0].uid == root.uid
        assert end.parents[0].uid == task.uid
        assert compiler.active is None
        assert len(dag.nodes) == 3

    def test_get_dag_with_outer(self, compiler: DAGCompiler) -> None:
        task = TaskNode(
            uid=5,
            name="task",
            fn_name="task",
            cache="none",
            code_hash="xyz",
            mode="wrap",
            cmd="bash",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            tags=[],
        )
        compiler.reset()
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag1")
        compiler.set_dag(root)
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag2")
        compiler.set_dag(root)
        compiler.register(task)
        inner_dag, inner_root, inner_end = compiler.get_dag()

        assert task.parents[0].uid == inner_root.uid
        assert inner_end.parents[0].uid == task.uid
        assert compiler.active is not None
        assert len(inner_dag.nodes) == 3

        dag, root, end = compiler.get_dag()
        assert inner_root.parents[0].uid == root.uid
        assert end.parents[0].uid == inner_end.uid
        assert len(dag.nodes) == 5

    def test_push_scope(self, compiler: DAGCompiler) -> None:
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        root_scope = compiler.current_scope
        scope = compiler.push_scope((3, True))

        assert compiler.current_scope is scope
        assert scope.anchor == (3, True)
        assert scope.parent is root_scope

    def test_pop_scope_restores_parent(self, compiler: DAGCompiler) -> None:
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        root_scope = compiler.current_scope
        compiler.push_scope((3, True))
        closed = compiler.pop_scope()

        assert closed.anchor == (3, True)
        assert compiler.current_scope is root_scope

    def test_pop_scope_cannot_pop_root(self, compiler: DAGCompiler) -> None:
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)

        with pytest.raises(DAGNotSetError):
            compiler.pop_scope()

    def test_register_stamps_active_scope_anchor(
        self, compiler: DAGCompiler
    ) -> None:
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        compiler.push_scope((3, True))
        node = RootNode(uid=5)
        compiler.register(node)

        assert node.parents[0].uid == 3
        assert node.parents[0].kind.kind == "branch"
        assert node.parents[0].kind.branch

    def test_close_clause(self, compiler: DAGCompiler) -> None:
        root = RootNode(uid=compiler.get_uid(), pipeline_name="dag")
        compiler.set_dag(root)
        compiler.close_clause(3, next_edge_value=False)

        clause = compiler.current_scope.last_clause
        assert clause is not None
        assert clause.branch_uid == 3
        assert not clause.next_edge_value
        assert not clause.terminal
