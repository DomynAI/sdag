# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from sdag.models import DAG, Artifact, EndNode, LogicalParent, Parent
from sdag.visualization import DAGViewer, MermaidGenerator
from sdag.wrappers import Else, If, pipeline, task


@pytest.fixture(autouse=True)
def reset_master():
    from sdag.compiler import master

    master._reset()


@pytest.fixture
def nested() -> DAG:
    @task("path/to/script.sh")
    def my_task(): ...

    @pipeline
    def inner():
        my_task()

    @pipeline
    def outer():
        inner()

    return outer.compile()


@pytest.fixture
def branch() -> DAG:
    @task("path/to/script.sh")
    def task1(): ...

    @task("path/to/script.sh")
    def expr(): ...

    @pipeline
    def dag():
        with If(expr()):
            task1()
        with Else():
            task1()

    return dag.compile()


@pytest.fixture
def artifact() -> DAG:
    @pipeline
    def dag_artifact():
        task = task_with_artifact(a="artifact/path")
        task_taking_artifact(b=task.artifacts["a"])

    @dag_artifact.task("path/to/script.sh")
    def task_with_artifact(a: Artifact[str]): ...

    @dag_artifact.task("path/to/script.sh")
    def task_taking_artifact(b: str): ...

    return dag_artifact.compile()


class TestMermaidGenerator:
    @pytest.fixture
    def mermaid_gen(self) -> MermaidGenerator:
        return MermaidGenerator(squeeze=False)

    def test_is_terminal(self, mermaid_gen: MermaidGenerator) -> None:
        node = EndNode(uid=2, root_uid=0)
        assert mermaid_gen._is_terminal(node)
        node.root_uid = 1
        assert not mermaid_gen._is_terminal(node)

    @pytest.mark.parametrize(
        argnames=("squeeze", "root_uid", "name"),
        argvalues=[
            (False, 0, "2(_end_)"),
            (True, 1, "1_pipeline[pipeline]"),
            (True, 0, "2(_end_)"),
        ],
    )
    def test_get_name(
        self,
        squeeze: bool,
        root_uid: int,
        name: str,
        mermaid_gen: MermaidGenerator,
    ) -> None:
        node = EndNode(uid=2, root_uid=root_uid, pipeline_name="pipeline")
        mermaid_gen.squeeze = squeeze
        assert mermaid_gen._get_name(node) == name

    def test_squeeze(self, nested: DAG, mermaid_gen: MermaidGenerator) -> None:
        mermaid_gen.squeeze = True
        mermaid = mermaid_gen.generate_mermaid_string(nested)
        expected = """flowchart TB
0(_root_) --> 2_inner[inner]"""
        assert mermaid == expected

    def test_branch(self, branch: DAG, mermaid_gen: MermaidGenerator) -> None:
        mermaid = mermaid_gen.generate_mermaid_string(branch)
        expected = """flowchart TB
0(_root_) --> 2[expr]
2[expr] -->|output| 3{T/F}
3{T/F} -->|T| 4[task1]
3{T/F} -->|F| 5[task1]"""
        assert mermaid == expected

    def test_artifact(
        self, artifact: DAG, mermaid_gen: MermaidGenerator
    ) -> None:
        mermaid = mermaid_gen.generate_mermaid_string(artifact)
        expected = """flowchart TB
0(_root_) --> 2[task_with_artifact]
2[task_with_artifact] -->|a| 3[task_taking_artifact]"""
        assert mermaid == expected


class TestDagViewer:
    @pytest.fixture
    def viewer(self) -> DAGViewer:
        return DAGViewer()

    def test_is_terminal(self, viewer: DAGViewer) -> None:
        node = EndNode(uid=2, root_uid=0, pipeline_name="pipeline")
        assert viewer._is_terminal(node)
        node.root_uid = 1
        assert not viewer._is_terminal(node)

    @pytest.mark.parametrize(
        argnames=("squeeze", "root_uid", "uid"),
        argvalues=[
            (False, 1, 2),
            (True, 0, 2),
            (True, 1, 1),
        ],
    )
    def test_get_uid(
        self, squeeze: bool, root_uid: int, uid: int, viewer: DAGViewer
    ) -> None:
        node = EndNode(uid=2, root_uid=root_uid, pipeline_name="pipeline")
        viewer.squeeze = squeeze
        assert viewer._get_uid(node) == uid

    def test_get_viznode(self, viewer: DAGViewer) -> None:
        node = EndNode(uid=0, root_uid=1, pipeline_name="pipeline")
        viznode = viewer._get_viznode(node, uid=3)
        assert viznode.id == 3
        assert viznode.caption == ""
        assert viznode.color.as_hex() == viewer.end_color.lower()  # type: ignore
        assert viznode.size == viewer.end_size

    def test_get_viznode_squeeze(self, viewer: DAGViewer) -> None:
        node = EndNode(uid=0, root_uid=1, pipeline_name="pipeline")
        viewer.squeeze = True
        viznode = viewer._get_viznode(node, uid=3)
        assert viznode.id == 3
        assert viznode.caption == "pipeline"
        assert viznode.color.as_hex() == viewer.pipeline_color.lower()  # type: ignore
        assert viznode.size == viewer.pipeline_size

    def test_get_edge(self, viewer: DAGViewer) -> None:
        relationship = viewer._get_edge(
            source_uid=0,
            target_uid=1,
            parent=Parent(uid=0, kind=LogicalParent()),
        )
        assert relationship.source == 0
        assert relationship.target == 1
        assert relationship.caption_size == viewer.caption_size
        assert relationship.caption == ""

    def test_artifact(
        self, artifact: DAG, viewer: DAGViewer, tmp_path: Path
    ) -> None:
        from IPython.display import HTML

        path = tmp_path / "artifact-pipeline.json"
        dag_json = artifact.model_dump_json(by_alias=True)
        with path.open("w") as fout:
            fout.write(dag_json)

        vg = viewer.view(str(path))
        assert isinstance(vg, HTML)
