# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import inspect
import os
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from sdag.compiler import compiler, master
from sdag.exceptions import (
    IncorrectElifError,
    IncorrectElseError,
    KwargNotFoundError,
    TaskNotUniqueError,
)
from sdag.models import (
    Artifact,
    ArtifactEdge,
    ArtifactParent,
    BranchParent,
    Kwarg,
    LogicalParent,
    OneOfNode,
    OutputParent,
    Parent,
    RootNode,
    TaskNode,
)
from sdag.scripts import ScriptContent, ScriptPath, script
from sdag.settings import get_compile_settings
from sdag.wrappers import (
    Elif,
    Else,
    If,
    Task,
    is_artifact,
    oneof,
    pipeline,
    task,
    validate_kwargs,
)


@pytest.fixture(autouse=True)
def reset_master():
    master._reset()


class TestKwargValidation:
    """Test the input kwarg validation."""

    @pytest.mark.parametrize(
        argnames=("fn", "kwargs"),
        argvalues=[
            (lambda a: ..., {}),  # noqa: ARG005
            (lambda: ..., {"a": 1}),
            (lambda a, **kw: ..., {}),  # noqa: ARG005
        ],
    )
    def test_fail_kwargs_validation(
        self, fn: Callable[..., None], kwargs: dict[str, Any]
    ) -> None:
        """kwarg validation must fail.

        Args:
            fn (Callable[..., None]): Task function.
            kwargs (dict[str, Any]): Input kwargs.
        """
        sig = inspect.signature(fn)
        with pytest.raises(KwargNotFoundError):
            validate_kwargs(sig, kwargs)

    @pytest.mark.parametrize(
        argnames=("fn", "kwargs"),
        argvalues=[
            (lambda: ..., {}),
            (lambda a: ..., {"a": 1}),  # noqa: ARG005
            (lambda **kw: ..., {"a": 1}),  # noqa: ARG005
            (lambda a=1, **kw: ..., {"a": 1}),  # noqa: ARG005
            (lambda a=1, **kw: ..., {"a": 1, "b": 2}),  # noqa: ARG005
        ],
    )
    def test_succeed_kwargs_validation(
        self, fn: Callable[..., None], kwargs: dict[str, Any]
    ) -> None:
        """kwarg validation must fail.

        Args:
            fn (Callable[..., None]): Task function.
            kwargs (dict[str, Any]): Input kwargs.
        """

        sig = inspect.signature(fn)
        validate_kwargs(sig, kwargs)


@pytest.mark.parametrize(
    argnames=("param", "result"),
    argvalues=[
        ("missing", False),
        ("a", False),
        ("b", True),
        ("c", True),
        ("d", True),
    ],
)
def test_is_artifact(param: str, result: bool) -> None:
    def foo(a: int, b: Artifact, c: Artifact[str], d: Artifact[Path]): ...

    sig = inspect.signature(foo)

    assert is_artifact(sig.parameters.get(param)) == result


def test_oneof() -> None:
    @pipeline
    def dag():
        t1 = test_task()
        t2 = test_task()
        t3 = test_task()
        oneof(t1, t2, t3)

    @dag.task("script.sh")
    def test_task(): ...

    graph = dag.compile()
    oneofnode = graph.nodes[-2]
    assert isinstance(oneofnode, OneOfNode)
    assert oneofnode.parents[0].uid == 2
    assert oneofnode.parents[0].kind.kind == "logical"
    assert oneofnode.parents[1].uid == 3
    assert oneofnode.parents[1].kind.kind == "logical"
    assert oneofnode.parents[2].uid == 4
    assert oneofnode.parents[2].kind.kind == "logical"


class TestIf:
    def test_if(self) -> None:
        @pipeline
        def dag():
            with If(test_task()):
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        graph = dag.compile()
        expnode = graph.nodes[1]
        ifnode = graph.nodes[2]
        tasknode = graph.nodes[3]

        assert tasknode.kind == "task"
        assert ifnode.kind == "branch"
        assert expnode.kind == "task"
        assert ifnode.parents[0].kind.kind == "output"
        assert ifnode.parents[0].uid == expnode.uid
        assert tasknode.parents[0].kind.kind == "branch"
        assert tasknode.parents[0].uid == ifnode.uid
        assert tasknode.parents[0].kind.branch


class TestElIf:
    def test_elif(self) -> None:
        @pipeline
        def dag():
            with If(test_task()):
                test_task()
            with Elif(test_task()):
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        graph = dag.compile()
        expnode1 = graph.nodes[1]
        ifnode = graph.nodes[2]
        tasknode1 = graph.nodes[3]
        expnode2 = graph.nodes[4]
        elifnode = graph.nodes[5]
        tasknode2 = graph.nodes[6]

        assert tasknode1.kind == tasknode2.kind == "task"
        assert ifnode.kind == elifnode.kind == "branch"
        assert expnode1.kind == expnode2.kind == "task"

        assert expnode2.parents[0].uid == ifnode.uid

        assert expnode2.parents[0].kind.kind == "branch"
        assert not expnode2.parents[0].kind.branch
        assert elifnode.parents[0].kind.kind == "output"
        assert elifnode.parents[0].uid == expnode2.uid
        assert tasknode2.parents[0].kind.kind == "branch"
        assert tasknode2.parents[0].uid == elifnode.uid
        assert tasknode2.parents[0].kind.branch

    def test_elif_after_elif_with_intervening_task(self) -> None:
        """An unrelated task between two Elifs must not break the chain."""

        @pipeline
        def dag():
            with If(test_task()):
                test_task()
            with Elif(test_task()):
                test_task()
            test_task()
            with Elif(test_task()):
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        graph = dag.compile()
        firstelif = graph.nodes[5]
        unrelated = graph.nodes[7]
        expnode3 = graph.nodes[8]
        secondelif = graph.nodes[9]
        tasknode3 = graph.nodes[10]

        assert firstelif.kind == secondelif.kind == "branch"
        assert not any(p.kind.kind == "branch" for p in unrelated.parents)

        assert expnode3.parents[0].uid == firstelif.uid
        assert expnode3.parents[0].kind.kind == "branch"
        assert not expnode3.parents[0].kind.branch

        assert secondelif.parents[0].kind.kind == "output"
        assert secondelif.parents[0].uid == expnode3.uid

        assert tasknode3.parents[0].kind.kind == "branch"
        assert tasknode3.parents[0].uid == secondelif.uid
        assert tasknode3.parents[0].kind.branch

    def test_elif_without_if(self) -> None:
        @pipeline
        def dag():
            with Elif(test_task()):
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        with pytest.raises(IncorrectElifError):
            dag.compile()

    def test_elif_inside_if(self) -> None:
        @pipeline
        def dag():
            with If(test_task()):  # noqa: SIM117
                with Elif(test_task()):
                    test_task()

        @dag.task("script.sh")
        def test_task(): ...

        with pytest.raises(IncorrectElifError):
            dag.compile()

    def test_elif_after_if_with_intervening_task(self) -> None:
        """An unrelated task between If and Elif must not break the chain."""

        @pipeline
        def dag():
            with If(test_task()):
                test_task()
            test_task()
            with Elif(test_task()):
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        graph = dag.compile()
        ifnode = graph.nodes[2]
        unrelated = graph.nodes[4]
        expnode2 = graph.nodes[5]
        elifnode = graph.nodes[6]
        tasknode2 = graph.nodes[7]

        assert ifnode.kind == elifnode.kind == "branch"
        assert not any(p.kind.kind == "branch" for p in unrelated.parents)

        assert expnode2.parents[0].uid == ifnode.uid
        assert expnode2.parents[0].kind.kind == "branch"
        assert not expnode2.parents[0].kind.branch

        assert elifnode.parents[0].kind.kind == "output"
        assert elifnode.parents[0].uid == expnode2.uid

        assert tasknode2.parents[0].kind.kind == "branch"
        assert tasknode2.parents[0].uid == elifnode.uid
        assert tasknode2.parents[0].kind.branch

    def test_elif_after_else(self) -> None:
        @pipeline
        def dag():
            with If(test_task()):
                test_task()
            with Else():
                test_task()
            with Elif(test_task()):
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        with pytest.raises(IncorrectElifError):
            dag.compile()


class TestElse:
    def test_else(self) -> None:
        @pipeline
        def dag():
            with If(test_task()):
                test_task()
            with Else():
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        graph = dag.compile()
        expnode = graph.nodes[1]
        ifnode = graph.nodes[2]
        tasknode1 = graph.nodes[3]
        tasknode2 = graph.nodes[4]

        assert ifnode.kind == "branch"
        assert expnode.kind == "task"
        assert tasknode1.kind == tasknode2.kind == "task"
        assert tasknode2.parents[0].kind.kind == "branch"
        assert tasknode2.parents[0].uid == ifnode.uid
        assert not tasknode2.parents[0].kind.branch

    def test_inner_pipelines_in_if(self) -> None:
        """Both sub-pipeline roots get the branch anchor directly.

        Previously, a graph traversal avoided adding a branch edge to
        `root3` since it already depended on `root2`'s output
        transitively. That optimization was removed for simplicity: the
        extra edge below is harmless (redundant, not incorrect), and in
        exchange every node registered in a branch's scope is handled
        by one uniform rule instead of a special-cased traversal.
        """

        @pipeline
        def dag_outer():
            with If(exp()):
                p = dag_inner()
                dag_inner(p)

        @dag_outer.task("submit.sh")
        def exp(): ...

        @pipeline
        def dag_inner(): ...

        graph = dag_outer.compile()
        root1 = graph.nodes[0]
        branch = graph.nodes[2]
        end1 = graph.nodes[7]
        end2 = graph.nodes[4]
        end3 = graph.nodes[6]
        root2 = graph.nodes[3]
        root3 = graph.nodes[5]
        assert root1.kind == root2.kind == root3.kind == "root"
        assert branch.kind == "branch"
        assert end1.kind == end2.kind == end3.kind == "end"
        assert root2.parents == [
            Parent(uid=3, kind=BranchParent(kind="branch", branch=True))
        ]
        assert root3.parents == [
            Parent(uid=5, kind=LogicalParent(kind="logical")),
            Parent(uid=3, kind=BranchParent(kind="branch", branch=True)),
        ]

    def test_else_without_if(self) -> None:
        @pipeline
        def dag():
            with Else():
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        with pytest.raises(IncorrectElseError):
            dag.compile()

    def test_else_inside_if(self) -> None:
        @pipeline
        def dag():
            with If(test_task()):  # noqa: SIM117
                with Else():
                    test_task()

        @dag.task("script.sh")
        def test_task(): ...

        with pytest.raises(IncorrectElseError):
            dag.compile()

    def test_else_after_if_with_intervening_task(self) -> None:
        """An unrelated task between If and Else must not break the chain."""

        @pipeline
        def dag():
            with If(test_task()):
                test_task()
            test_task()
            with Else():
                test_task()

        @dag.task("script.sh")
        def test_task(): ...

        graph = dag.compile()
        ifnode = graph.nodes[2]
        unrelated = graph.nodes[4]
        tasknode2 = graph.nodes[5]

        assert ifnode.kind == "branch"
        assert not any(p.kind.kind == "branch" for p in unrelated.parents)

        assert tasknode2.parents[0].kind.kind == "branch"
        assert tasknode2.parents[0].uid == ifnode.uid
        assert not tasknode2.parents[0].kind.branch


class TestPipeline:
    def test_add_duplicate_task(self) -> None:
        @pipeline
        def dag(): ...

        @dag.task("submit.sh")
        def my_task(): ...

        with pytest.raises(TaskNotUniqueError):

            @dag.task("submit.sh")
            def my_task(): ...

    def test_call(self) -> None:
        @pipeline
        def dag(a: int) -> None:  # noqa: ARG001
            my_task(b="path/artifact")

        @dag.task("script.sh")
        def my_task(b: Artifact[str]): ...

        parent = TaskNode(
            uid=0,
            root_uid=-1,
            name="task",
            pipeline_name="",
            fn_name="task",
            cache="none",
            code_hash="xyz",
            mode="wrap",
            cmd="bash",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path("submit.sh")),
        )

        endnode = dag(parent, a=1)
        assert endnode.kind == "end"

        container = endnode.artifacts["my_task"]["b"]
        assert container.key == "b"
        assert container.node.name == "my_task"
        assert container.path == Path("path/artifact")

    def test_compile(self) -> None:
        @pipeline
        def dag(a: int):  # noqa: ARG001
            task1()

        @dag.task("script.sh")
        def task1(): ...

        graph = dag.compile(import_path="path.to:dag", a=1)
        assert graph.meta.import_path == "path.to:dag"
        assert len(graph.nodes) == 3

    def test_script_signal(self) -> None:
        from sdag.compiler import master

        @task(script)
        def task1(): ...

        assert isinstance(master.tasks["task1"].script, ScriptContent)


class TestTask:
    @pytest.fixture
    def _set_sdag_base_path(self) -> Generator[None]:
        """Safely set the base path.

        Cache and environment variable are safely cleaned up.
        """
        get_compile_settings.cache_clear()
        os.environ["SDAG_BASE_PATH"] = "data"
        yield
        del os.environ["SDAG_BASE_PATH"]
        get_compile_settings.cache_clear()

    def test_add_default_values(self) -> None:
        """Test the default value addition."""

        def fn(a: str, b: int = 5, c: str = "c") -> None: ...

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        sig = inspect.signature(fn)
        kwargs = {"a": "a", "c": "custom_c"}
        test_task._add_default_values(sig, kwargs)

        assert kwargs == {"a": "a", "b": 5, "c": "custom_c"}

    def test_add_kwargs(self) -> None:
        """Test the complete kwarg addition."""

        def fn(a: str, b: Artifact, **kw: Any) -> None:
            """Mocked task function."""

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        kwargs = {"a": "a", "b": "/path", "custom_kw": 10}
        node = TaskNode(
            uid=0,
            fn_name="fn",
            name="fn",
            cache="io",
            code_hash="xyz",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=2,
            script=ScriptPath(path=Path()),
        )

        test_task._add_kwargs(node, kwargs)

        assert node.kwargs == [
            Kwarg(key="a", value="a"),
            Kwarg(key="b", value="/path"),
            Kwarg(key="custom_kw", value=10),
        ]

        assert node.output_artifacts == [
            ArtifactEdge(name="b", path=Path("/path"))
        ]

    @pytest.mark.parametrize(
        argnames=("original", "expected"),
        argvalues=[
            # Relative path, prepend base path
            ("hello.txt", "data/hello.txt"),
            # Absolute path, do not prepend
            ("/hello.txt", "/hello.txt"),
        ],
    )
    @pytest.mark.usefixtures("_set_sdag_base_path")
    def test_prepend_base_path_when_set(
        self,
        original: str,
        expected: str,
    ) -> None:
        """Test the artifact registration with base path.

        Args:
            original (str): Original path.
            expected (str): Expected artifact path.
        """

        def fn(a: Artifact) -> None: ...

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        kwargs = {"a": original}
        sig = inspect.signature(fn)

        test_task._prepend_base_path_if_set(kwargs, sig)
        assert kwargs["a"] == expected

    def test_do_not_prepend_base_path(self) -> None:
        """SDAG home is not set, do not prepend."""

        def fn(a: Artifact) -> None: ...

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        original = "hello.txt"
        kwargs = {"a": original}
        sig = inspect.signature(fn)

        test_task._prepend_base_path_if_set(kwargs, sig)
        assert kwargs["a"] == original

    def test_call(self) -> None:
        """Test the task call."""

        def fn(kwarg: Any, static_input: dict[str, int]) -> None:
            """Mocked task with static and dynamic args."""

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        argnode = RootNode(uid=1)
        kwargnode = RootNode(uid=2)
        static_input = {"a": 1}
        root = RootNode(uid=0, pipeline_name="dag")
        compiler.set_dag(root)
        node = test_task(argnode, kwarg=kwargnode, static_input=static_input)

        assert compiler.active is not None
        assert node in compiler.active.dag.nodes
        assert node.cache == test_task.cache
        assert node.retries == test_task.retries
        assert node.script == test_task.script
        assert node.kwargs == [Kwarg(key="static_input", value={"a": 1})]
        assert sorted(node.parents, key=lambda x: x.uid) == [
            Parent(uid=1, kind=LogicalParent()),
            Parent(uid=2, kind=OutputParent(key="kwarg")),
        ]

    def test_call_artifact(self) -> None:
        """Test the task call."""

        def fn(a: Artifact, b: str) -> None: ...

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        artifact_path = "/path/to/artifact"
        parent = TaskNode(
            uid=1,
            fn_name="fn",
            name="fn",
            cache="io",
            code_hash="xyz",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=2,
            script=ScriptPath(path=Path()),
        )
        parent.register_artifact("artifact", path=Path(artifact_path))
        root = RootNode(uid=0, pipeline_name="dag")
        compiler.set_dag(root)
        node = test_task(a=parent.artifacts["artifact"], b="/path/to/artifact")

        assert compiler.active is not None
        assert node in compiler.active.dag.nodes
        assert node.cache == test_task.cache
        assert node.retries == test_task.retries
        assert node.script == test_task.script
        assert node.kwargs == [Kwarg(key="b", value="/path/to/artifact")]
        assert node.parents == [
            Parent(
                uid=1,
                kind=ArtifactParent(
                    key="a", name="artifact", path=Path(artifact_path)
                ),
            ),
        ]

    def test_code_cache(self) -> None:
        """Check source code hash is computed and cached."""

        def fn(a: int) -> int:
            """Description."""
            return a * 2

        test_task = Task(
            fn=fn,
            name="task",
            mode="wrap",
            cmd="sbatch",
            scope="local",
            retries=0,
            script=ScriptPath(path=Path()),
            cache="none",
            cache_ignore=None,
            cache_size=1,
            tags=[],
            njobs=1,
        )

        code_hash = test_task.code_hash
        cached_code_hash = test_task.code_hash

        assert isinstance(code_hash, str)
        assert code_hash is cached_code_hash

    def test_script_signal(self) -> None:
        from sdag.compiler import master

        @pipeline
        def dag():
            task1()

        @task(script)
        def task1(): ...

        assert isinstance(master.tasks["task1"].script, ScriptContent)
