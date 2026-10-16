# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Visualization utils.

For notebook visualizations it is required to install neo4j_viz.
"""

from typing import TYPE_CHECKING, Any, Literal

from sdag.models import DAG, NodeUnion, Parent

if TYPE_CHECKING:
    from IPython.display import HTML
    from neo4j_viz import Node as VizNode
    from neo4j_viz import Relationship


class MermaidGenerator:
    """Generate a mermaid string of the DAG.

    Attributes:
        squeeze (bool): Collapse all inner pipelines into
            a unique node.
    """

    def __init__(self, squeeze: bool):
        """Initialize the mermaid generator.

        Args:
            squeeze (bool): Collapse all inner pipelines into
                a unique node.
        """
        self.squeeze = squeeze

    def generate_mermaid_string(self, dag: DAG) -> str:
        """Generate the mermaid string out of the dag.

        Args:
            dag (DAG): DAG.

        Returns:
            str: Mermaid string.
        """
        nodes = {node.uid: node for node in dag.nodes}
        lines = ["flowchart TB"]
        for node in dag.nodes:
            if self._is_terminal(node):
                continue

            for parent in node.parents:
                parent_node = nodes[parent.uid]
                if self._is_terminal(parent_node):
                    continue

                if self.squeeze and parent_node.root_uid == node.root_uid != 0:
                    continue

                parent_name = self._get_name(parent_node)
                child_name = self._get_name(node)
                edge = self._get_edge(parent)
                line = f"{parent_name} -->{edge} {child_name}"
                lines.append(line)

        return "\n".join(lines)

    def _is_terminal(self, node: NodeUnion) -> bool:
        """Check if the node is terminal.

        Args:
            node (NodeUnion): Node.

        Returns:
            bool: True if the node is terminal.
        """
        return node.kind == "end" and node.root_uid == 0

    def _get_name(self, node: NodeUnion) -> str:
        """Get the node name in the chart.

        Args:
            node (NodeUnion): Node.

        Returns:
            str: Node name.
        """
        if self.squeeze and node.root_uid != 0:
            return (
                f"{node.root_uid}_{node.pipeline_name}[{node.pipeline_name}]"
            )

        match node.kind:
            case "task":
                return f"{node.uid}[{node.name}]"
            case "branch":
                return f"{node.uid}{{T/F}}"
            case "root":
                return f"{node.uid}(_root_)"
            case "end":
                return f"{node.uid}(_end_)"
            case "one_of":
                return f"{node.uid}[oneof]"

    def _get_edge(self, parent: Parent) -> str:
        """Get the edge.

        Args:
            parent (Parent): Parent.

        Returns:
            str: Edge string.
        """
        match parent.kind.kind:
            case "logical":
                return ""
            case "output":
                return "|output|"
            case "branch":
                branch = "T" if parent.kind.branch else "F"  # type: ignore
                return f"|{branch}|"
            case "artifact":
                return f"|{parent.kind.name}|"  # type: ignore


class DAGViewer:
    """DAG viewer.

    Attributes:
        squeeze (bool): Collapse all inner pipelines into
            a unique node.
        task_size (int, optional): Task node size.
        task_color (str, optional): Task color.
        root_size (int, optional): Root node size.
        root_color (str, optional): Root color.
        end_size (int, optional): End node size.
        end_color (str, optional): End color.
        if_size (int, optional): If node size.
        if_color (str, optional): If color.
        oneof_size (int, optional): OneOf node size.
        oneof_color (str, optional): OneOf color.
        pipeline_size (int, optional): Pipeline node size.
        pipeline_color (str, optional): Pipeline color.
        caption_size (Literal[1, 2, 3], optional): Caption size.
    """

    def __init__(
        self,
        squeeze: bool = False,  # noqa: FBT002
        task_size: int = 50,
        task_color: str = "#3E7B7C",
        root_size: int = 15,
        root_color: str = "#F5F7FA",
        end_size: int = 15,
        end_color: str = "#F5F7FA",
        if_size: int = 30,
        if_color: str = "#D4A5A5",
        oneof_size: int = 30,
        oneof_color: str = "#D4A5A5",
        pipeline_size: int = 50,
        pipeline_color: str = "#F0D48D",
        caption_size: Literal[1, 2, 3] = 2,
    ) -> None:
        """Initialize the viewer.

        Args:
            squeeze (bool): Collapse subpipelines into a unique node.
                Defaults to False.
            task_size (int, optional): Task node size. Defaults to 50.
            task_color (str, optional): Task color.
                Defaults to "#3E7B7C".
            root_size (int, optional): Root node size. Defaults to 15.
            root_color (str, optional): Root color. Defaults to "#F5F7FA".
            end_size (int, optional): End node size. Defaults to 15.
            end_color (str, optional): End color. Defaults to "#F5F7FA".
            if_size (int, optional): If node size. Defaults to 30.
            if_color (str, optional): If color. Defaults to "#D4A5A5".
            oneof_size (int, optional): OneOf node size. Defaults to 30.
            oneof_color (str, optional): OneOf color. Defaults to "#D4A5A5".
            pipeline_size (int, optional): Pipeline size (only usable if
                squeeze is enabled). Defaults to 50.
            pipeline_color (str, optional): Pipeline color (only usable if
                squeeze is enabled). Defaults to "#F0D48D".
            caption_size (Literal[1, 2, 3], optional): Caption size.
                Defaults to 2.
        """
        self.squeeze = squeeze
        self.task_size = task_size
        self.task_color = task_color
        self.root_size = root_size
        self.root_color = root_color
        self.end_size = end_size
        self.end_color = end_color
        self.if_size = if_size
        self.if_color = if_color
        self.oneof_size = oneof_size
        self.oneof_color = oneof_color
        self.pipeline_size = pipeline_size
        self.pipeline_color = pipeline_color
        self.caption_size = caption_size

    def view(
        self, path: str, input_kwargs: dict[str, Any] | None = None
    ) -> "HTML":
        """View the DAG graph in a notebook cell.

        Args:
            path (str): Compiled pipeline path.
            input_kwargs (dict[str, Any] | None): Pipeline input kwargs,
                only used if the pipeline is compiled. Defaults to None.

        Returns:
            HTML: IPython HTML graph.
        """
        from neo4j_viz import Layout, VisualizationGraph
        from neo4j_viz import Node as VizNode

        from sdag.commands import _get_dag_from_name_import_or_json

        viz_nodes: list[VizNode] = []
        edges: list[Relationship] = []

        kwargs = input_kwargs if input_kwargs is not None else {}
        dag = _get_dag_from_name_import_or_json(
            path=path, input_kwargs=kwargs, extra_metadata=None
        )
        nodes = {node.uid: node for node in dag.nodes}
        for node in dag.nodes:
            if self._is_terminal(node):
                continue

            uid = self._get_uid(node)
            viz_node = self._get_viznode(node, uid)
            viz_nodes.append(viz_node)

            for parent in node.parents:
                parent_node = nodes[parent.uid]
                if self._is_terminal(parent_node):
                    continue

                if self.squeeze and parent_node.root_uid == node.root_uid != 0:
                    continue

                parent_uid = self._get_uid(parent_node)
                edge = self._get_edge(
                    source_uid=parent_uid, target_uid=uid, parent=parent
                )
                edges.append(edge)

        vg = VisualizationGraph(nodes=viz_nodes, relationships=edges)

        return vg.render(layout=Layout.HIERARCHICAL)

    def _is_terminal(self, node: NodeUnion) -> bool:
        """Check whether the node is terminal.

        Args:
            node (NodeUnion): Node.

        Returns:
            bool: True if the node is terminal.
        """
        return node.kind == "end" and node.root_uid == 0

    def _get_uid(self, node: NodeUnion) -> int:
        """Get the node uid (which might be the root one).

        Args:
            node (NodeUnion): Node.

        Returns:
            int: uid.
        """
        if self.squeeze and node.root_uid != 0:
            uid = node.root_uid
        else:
            uid = node.uid
        return uid

    def _get_viznode(self, node: NodeUnion, uid: int) -> "VizNode":
        """Get a visualization node.

        Args:
            node (NodeUnion): Node.
            uid (int): Node uid.

        Raises:
            ValueError: Unknown node kind.

        Returns:
            VizNode: Visualization node.
        """
        from neo4j_viz import Node as VizNode

        if self.squeeze and node.root_uid != 0:
            color = self.pipeline_color
            size = self.pipeline_size
            caption = node.pipeline_name
        else:
            match node.kind:
                case "task":
                    color = self.task_color
                    size = self.task_size
                    caption = node.name

                case "branch":
                    color = self.if_color
                    size = self.if_size
                    caption = "T/F"

                case "one_of":
                    color = self.oneof_color
                    size = self.oneof_size
                    caption = "one_of"

                case "root":
                    color = self.root_color
                    size = self.root_size
                    caption = ""

                case "end":
                    color = self.end_color
                    size = self.end_size
                    caption = ""

                case _:
                    msg = f"Unknown node type {node.type}"
                    raise ValueError(msg)

        return VizNode(
            id=uid,
            caption=caption,
            size=size,
            color=color,
            caption_size=self.caption_size,
        )  # type: ignore

    def _get_edge(
        self, source_uid: int, target_uid: int, parent: Parent
    ) -> "Relationship":
        """Get the relationship based on the relation type.

        Args:
            source_uid (int): Source node uid.
            target_uid (int): Target node uid.
            parent (Parent): Parent.

        Raises:
            ValueError: Unknown parent type.

        Returns:
            Relationship: Graph edge.
        """
        from neo4j_viz import Relationship

        match parent.kind.kind:
            case "logical":
                caption = ""
            case "output":
                caption = "output"
            case "branch":
                caption = "T" if parent.kind.branch else "F"  # type: ignore
            case "artifact":
                caption = parent.kind.name  # type: ignore
            case _:
                msg = f"Unknown parent kind {parent.kind.kind}"
                raise ValueError(msg)

        return Relationship(
            source=source_uid,  # type: ignore
            target=target_uid,
            caption=caption,
            caption_size=self.caption_size,
        )
