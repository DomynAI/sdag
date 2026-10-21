# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""sdag models."""

import sys

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PrivateAttr,
    model_validator,
)

from sdag.constants import POSIX_ENV_VARIABLES
from sdag.exceptions import POSIXOverrideError
from sdag.scripts import ScriptUnion
from sdag.types import CacheOptions, Commands, ExecMode, Scope


class ArtifactSig:
    """Used to mark artifacts."""


T = TypeVar("T", bound=str | Path)
Artifact = Annotated[T, ArtifactSig]
"""Artifact.

Artifacts are used to signal that some assets are being
written. It is possible to use either Artifact[str] or
Artifact[Path], they are automatically cast.
"""


class Kwarg(BaseModel):
    """Task input kwarg.

    Attributes:
        key (str): Key.
        value (Any): Value.
    """

    key: str
    value: Any


class ArtifactEdge(BaseModel):
    """Artifact edge.

    Attributes:
        name (str): Artifact name.
        path (Path): Artifact path.
    """

    name: str
    path: Path


class LogicalParent(BaseModel):
    """Logical parent kind.

    Attributes:
        kind (Literal["logical"]): Kind.
    """

    kind: Literal["logical"] = "logical"


class OutputParent(BaseModel):
    """Output edge.

    Attributes:
        kind (Literal["outout"]): Kind.
        key (str): Field name.
    """

    kind: Literal["output"] = "output"
    key: str


class ArtifactParent(BaseModel):
    """Artifact edge.

    Attributes:
        kind (Literal["artifact"]): Artifact kind.
        key (str): Artifact key.
        name (str): Artifact name.
        path (str): Artifact path.
    """

    kind: Literal["artifact"] = "artifact"
    key: str
    name: str
    path: Path


class BranchParent(BaseModel):
    """Branch edge.

    Attributes:
        kind (Literal["branch"]): Kind.
        branch (bool): Branch.
    """

    kind: Literal["branch"] = "branch"
    branch: bool


class TaskOutput(BaseModel):
    """Output of a task.

    Attributes:
        output (Any): Task output.
        artifacts (list[ArtifactEdge]): Output artifacts.
    """

    output: Any
    artifacts: list[ArtifactEdge]


ParentKindUnion = Annotated[
    LogicalParent | OutputParent | ArtifactParent | BranchParent,
    Field(discriminator="kind"),
]
"""Parent types."""


class Parent(BaseModel):
    """Edge in the graph.

    Attributes:
        uid (int): Parent type.
        kind (str): Edge type.
    """

    uid: int
    kind: ParentKindUnion


class ArtifactContainer:
    """Artifact wrapper.

    Hack to pass the node to the child alongside
    artifacts.

    Attributes:
        key (str): Artifact key.
        path (str): Artifact path.
        node (Node): Parent node.
    """

    def __init__(self, key: str, path: Path, node: "TaskNode | OneOfNode"):
        """Initialize the artifact container.

        Args:
            key (str): Artifact key.
            path (str): Artifact path.
            node (Node): Parent node.
        """
        self.key = key
        self.path = path
        self.node = node


class BaseNode(BaseModel):
    """Node base class.

    Attributes:
        parents (list[Parent]): Parents.
        uid (int): Unique id.
        root_uid (int): Pipeline root unique id (added
            during compilation. Defaults to -1.
        pipeline_name (str): Pipeline name, added during
            compilation. Defaults to ''.
    """

    parents: list[Parent] = Field(default_factory=list)
    uid: int
    root_uid: int = -1
    pipeline_name: str = ""

    def add_logical_edge(self, parent_uid: int) -> None:
        """Add a child->parent logical edge.

        It is a logical dependence, no data exchanged.

        Args:
            parent_uid (int): Parent uid.
        """
        parent = Parent(uid=parent_uid, kind=LogicalParent())
        self.parents.append(parent)

    def add_branch_edge(self, parent_uid: int, branch: bool) -> None:
        """Add a child -> parent branch edge.

        The child depends on one of the branches of an IfNode.

        Args:
            parent_uid (int): Parent uid.
            branch (bool): Branch the child depends on.
        """
        parent = Parent(uid=parent_uid, kind=BranchParent(branch=branch))
        self.parents.append(parent)


class SlurmOverride(BaseModel):
    """Override Slurm arguments.

    They must be set following the Slurm conventions.

    Attributes:
        job_name: (str | None): Job name. Defaults to None.
        nodes: (int | None): Number of nodes. Defaults to None.
        partition: (str | None): Partition. Defaults to None.
        qos: (str | None) = qos. Defaults to None.
        gpus_per_node: (int | None): GPUs per node. Defaults to None.
        tasks_per_node: (int | None): Tasks per node.
            Defaults to None.
        output: (str | None): stdout. Defaults to None.
        error: (str | None): stderr. Defaults to None.
        account: (str | None): Account. Defaults to None.
        cpus_per_task (int | None): CPUs per task. Defaults to None.
        mem: (str | None): Memory. Defaults to None.
        time: (str | None): Wall time. Defaults to None.
    """

    job_name: str | None = Field(alias="job-name", default=None)
    nodes: NonNegativeInt | None = None
    partition: str | None = None
    qos: str | None = None
    gpus_per_node: NonNegativeInt | None = Field(
        alias="gpus-per-node", default=None
    )
    tasks_per_node: NonNegativeInt | None = Field(
        alias="tasks-per-node", default=None
    )
    output: str | None = None
    error: str | None = None
    account: str | None = None
    cpus_per_task: NonNegativeInt | None = Field(
        alias="cpus-per-task", default=None
    )
    mem: str | None = None
    time: str | None = None

    model_config = ConfigDict(
        extra="forbid", validate_by_alias=True, serialize_by_alias=True
    )

    def override_from(self, other: Self) -> None:  # noqa: C901
        """Override slurm configs from another set.

        Args:
            other (Self): Slurm configurations overriding
                the current ones in place.
        """
        if other.job_name is not None:
            self.job_name = other.job_name

        if other.nodes is not None:
            self.nodes = other.nodes

        if other.partition is not None:
            self.partition = other.partition

        if other.qos is not None:
            self.qos = other.qos

        if other.gpus_per_node is not None:
            self.gpus_per_node = other.gpus_per_node

        if other.tasks_per_node is not None:
            self.tasks_per_node = other.tasks_per_node

        if other.output is not None:
            self.output = other.output

        if other.error is not None:
            self.error = other.error

        if other.account is not None:
            self.account = other.account

        if other.cpus_per_task is not None:
            self.cpus_per_task = other.cpus_per_task

        if other.mem is not None:
            self.mem = other.mem

        if other.time is not None:
            self.time = other.time

    def override_if_not_set(self, other: Self) -> None:  # noqa: C901
        """Override slurm configs if missing.

        Args:
            other (Self): Slurm configurations overriding
                the current ones in place if not set.
        """
        if self.job_name is None and other.job_name is not None:
            self.job_name = other.job_name

        if self.nodes is None and other.nodes is not None:
            self.nodes = other.nodes

        if self.partition is None and other.partition is not None:
            self.partition = other.partition

        if self.qos is None and other.qos is not None:
            self.qos = other.qos

        if self.gpus_per_node is None and other.gpus_per_node is not None:
            self.gpus_per_node = other.gpus_per_node

        if self.tasks_per_node is None and other.tasks_per_node is not None:
            self.tasks_per_node = other.tasks_per_node

        if self.output is None and other.output is not None:
            self.output = other.output

        if self.error is None and other.error is not None:
            self.error = other.error

        if self.account is None and other.account is not None:
            self.account = other.account

        if self.cpus_per_task is None and other.cpus_per_task is not None:
            self.cpus_per_task = other.cpus_per_task

        if self.mem is None and other.mem is not None:
            self.mem = other.mem

        if self.time is None and other.time is not None:
            self.time = other.time


class TaskNode(BaseNode):
    """Task.

    Attributes:
        kind (Literal["task"]): Kind.
        parents (list[Parent]): Edges.
        fn_name (str): Function name.
        scope (Scope): Task scope.
        name (str): Task name, linked to caching.
        cache (CacheOptions): Caching options.
        cache_ignore (list[str]): list of fields ignored
            during cache validation.
        cache_size (int): Cache size. Ignore if caching is disabled.
            set to 0 to allow for infinite cache size. Defaults
            to 1.
        code_hash (str): Task source code hash.
        mode (ExecMode): Wrap a Python function or
            an external script.
        cmd (Commands): Command used to launch the script.
        retries (int): Retries.
        each (str | None): If not null, it's the key of
            the array field. Defaults to None.
        njobs (int): Number of jobs if it defines an
            array. Defaults to 1.
        script (ScriptUnion): Script path or content.
        tags (list[str]): Task tags.
        kwargs (list[Kwarg]): Input kwargs.
        envs (dict[str, Any]): Environment variables. They
            will be set in the task as strings.
        slurm (SlurmOverride): Override Slurm resources.
        output_artifacts (list[ArtifactEdge]): Artifacts.
        _artifact_containers (dict[str, ArtifactContainer]):
            Used to add edges to the graph.
    """

    kind: Literal["task"] = "task"
    parents: list[Parent] = Field(default_factory=list)
    fn_name: str
    name: str
    cache: CacheOptions
    scope: Scope
    cache_ignore: list[str] = Field(default_factory=list)
    cache_size: int = 1
    code_hash: str
    mode: ExecMode
    cmd: Commands
    retries: int
    each: str | None = None
    njobs: int = 1
    script: ScriptUnion
    tags: list[str] = Field(default_factory=list)
    kwargs: list[Kwarg] = Field(default_factory=list)
    envs: dict[str, Any] = Field(default_factory=dict)
    slurm: SlurmOverride = Field(default_factory=SlurmOverride)
    output_artifacts: list[ArtifactEdge] = Field(
        default_factory=list, alias="artifacts"
    )
    _artifact_containers: dict[str, ArtifactContainer] = PrivateAttr(
        default_factory=dict
    )
    model_config = ConfigDict(
        extra="forbid", serialize_by_alias=True, validate_by_alias=True
    )

    @property
    def artifacts(self) -> dict[str, ArtifactContainer]:
        """Get the artifacts.

        Returns:
            dict[str, ArtifactContainer]: Artifacts.
        """
        return self._artifact_containers

    def register_artifact(self, key: str, path: Path) -> None:
        """Register an artifact.

        Args:
            key (str): Artifact key.
            path (Path): Artifact path.
        """
        self.output_artifacts.append(ArtifactEdge(name=key, path=path))
        self._artifact_containers[key] = ArtifactContainer(key, path, self)

    def add_output_edge(self, parent_uid, key: str) -> None:
        """Add a child->parent output edge.

        Child will read the parent output.

        Args:
            parent_uid (int): Parent uid.
            key (str): parent output key in the child input kwargs.
        """
        parent = Parent(uid=parent_uid, kind=OutputParent(key=key))
        self.parents.append(parent)

    def add_artifact_edge(
        self, parent_uid: int, key: str, name: str, path: Path
    ) -> None:
        """Add a child->parent artifact edge.

        The child will use an artifact produced by the parent.

        Args:
            parent_uid (int): Parent uid.
            key (str): Artifact key in the child input kwargs.
            name (str): Artifact name.
            path (Path): Artifact path.
        """
        parent = Parent(
            uid=parent_uid,
            kind=ArtifactParent(key=key, name=name, path=path),
        )
        self.parents.append(parent)

    def add_kwarg(self, kwarg: Kwarg) -> None:
        """Add a static kwarg.

        Args:
            kwarg (Kwarg): Kwarg to be added.

        Raises:
            POSIXOverrideError: Task is external and variable is a
                common POSIX variable.
        """
        if self.mode == "ext" and kwarg.key.upper() in POSIX_ENV_VARIABLES:
            raise POSIXOverrideError(task_name=self.name, key=kwarg.key)
        self.kwargs.append(kwarg)


class RootNode(BaseNode):
    """Root node.

    Attributes:
        kind (Literal["root"]): Kind.
        root_uid: Same as uid.
    """

    kind: Literal["root"] = "root"
    root_uid: int = Field(alias="uid", default=-1)


class BranchNode(BaseNode):
    """Branch node.

    Attributes:
        kind (Literal["branch"]): Kind.
    """

    kind: Literal["branch"] = "branch"


class OneOfNode(BaseNode):
    """OneOf node.

    Attributes:
        kind (Literal["one_of"]): Kind.
        name (str): Node name.
        output_artifacts (list[ArtifactEdge]): Artifact edge.
        _artifact_containers (dict[str, ArtifactContainer]):
            Used to make artifact edges.
    """

    kind: Literal["one_of"] = "one_of"
    name: str
    output_artifacts: list[ArtifactEdge] = Field(
        default_factory=list, serialization_alias="artifacts"
    )
    _artifact_containers: dict[str, ArtifactContainer] = PrivateAttr(
        default_factory=dict
    )

    @property
    def artifacts(self) -> dict[str, ArtifactContainer]:
        """Get the artifacts.

        Returns:
            dict[str, ArtifactContainer]: Artifacts.
        """
        return self._artifact_containers

    def add_logical_edge(self, parent_uid: int) -> None:
        """Add a child->parent logical edge.

        It is a logical dependence, no data exchanged.

        Args:
            parent_uid (int): Parent uid.
        """
        parent = Parent(uid=parent_uid, kind=LogicalParent())
        self.parents.append(parent)

    def resolve_artifacts(self, *nodes: "TaskNode | Self | EndNode") -> None:
        """Register an artifact.

        Args:
            *nodes: TaskNode | Self: OneOf parent nodes.
        """
        if not nodes:
            return

        if not all(isinstance(node, (TaskNode, OneOfNode)) for node in nodes):
            return

        keys = set(nodes[0].artifacts)
        for node in nodes[1:]:
            keys = keys.intersection(set(node.artifacts))

        for key in keys:
            path = nodes[0].artifacts[key].path  # type: ignore
            for node in nodes[1:]:
                if node.artifacts[key].path != path:  # type: ignore
                    break
            else:
                self._register_artifact(key, path)

    def _register_artifact(self, key: str, path: Path) -> None:
        """Register an artifact.

        Args:
            key (str): Artifact key.
            path (Path): Artifact path.
        """
        self.output_artifacts.append(ArtifactEdge(name=key, path=path))
        self._artifact_containers[key] = ArtifactContainer(key, path, self)


class EndNode(BaseNode):
    """End node.

    Attributes:
        kind (Literal["end"]): Kind.
        _artifact_container (dict[str, dict[str, ArtifactContainer]]):
            Used to make artifact edges.
    """

    kind: Literal["end"] = "end"
    _artifact_container: dict[str, dict[str, ArtifactContainer]] = PrivateAttr(
        default_factory=dict
    )

    @property
    def artifacts(self) -> dict[str, dict[str, ArtifactContainer]]:
        """Artifacts.

        Returns:
            dict[str, dict[str, ArtifactContainer]]: Artifacts.
        """
        return self._artifact_container

    def join_artifacts(self, node: TaskNode | OneOfNode) -> None:
        """Join all artifacts of the pipeline.

        Args:
            node (TaskNode | OneOfNode): Node.
        """
        self._artifact_container[node.name] = node.artifacts


NodeUnion = Annotated[
    TaskNode | RootNode | EndNode | BranchNode | OneOfNode,
    Field(discriminator="kind"),
]
"""Node union."""


class DAGMeta(BaseModel):
    """DAG metadata.

    Attributes:
        pipeline_name (str): Pipeline name.
        timestamp (str): Timestamp.
        import_path (str): Import path.
        code_hash (str): Hash of all modules imported. It
            is added after pipeline compilation.
        kwargs (dict[str, Any]): Pipeline input kwargs.
        extra (str): Extra metadata.
    """

    pipeline_name: str
    timestamp: str = Field(default_factory=datetime.now().isoformat)
    import_path: str = ""
    code_hash: str = ""
    kwargs: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def set_path_to_pipeline_name_if_missing(self) -> Self:
        """Set the import path to the pipeline name if null.

        Returns:
            Self: Metadata.
        """
        if not self.import_path:
            self.import_path = self.pipeline_name
        return self


class DAG(BaseModel):
    """Compiled pipeline.

    Attributes:
        meta (DAGMeta): DAG metadata.
        nodes (list[NodeUnion]): Nodes.
    """

    meta: DAGMeta
    nodes: list[NodeUnion] = Field(default_factory=list)


@dataclass
class ClosedClause:
    """A closed If/Elif/Else clause, kept so the next Elif/Else can chain.

    Attributes:
        branch_uid (int): Uid of the BranchNode this clause evaluated.
        next_edge_value (bool): Branch edge value a following Elif/Else
            must depend on to run.
        terminal (bool): True once an Else has closed the chain, so no
            further Elif/Else may follow.
    """

    branch_uid: int
    next_edge_value: bool
    terminal: bool = False


@dataclass
class TraceScope:
    """Branch scope.

    Attributes:
        parent (Self | None): Enclosing scope. None for the
            pipeline's root scope. Defaults to None.
        anchor (tuple[int, bool] | None): (branch_uid, branch_value)
            branch edge on every node registered while active.
            None outside of branches. Defaults to None.
        last_clause (ClosedClause | None): Last branch closed
            directly in this scope, used by the next Elif/Else
            to chain onto it. Defaults to None.
    """

    parent: Self | None = None
    anchor: tuple[int, bool] | None = None
    last_clause: ClosedClause | None = None


class CompiledDAG(BaseModel):
    """Pipeline being compiled.

    Attributes:
        dag (DAG): DAG.
        root (RootNode): Root node.
        end (EndNode): End node.
        scope (TraceScope): Lexical scope currently active while
            tracing this pipeline's body.
    """

    dag: DAG
    root: RootNode
    end: EndNode
    scope: TraceScope = Field(default_factory=TraceScope)


class Each:
    """Signal job arrays.

    Attributes:
        collection (list[Any] | TaskNode): Inner keyword
            argument.
    """

    def __init__(self, collection: list[Any] | TaskNode):
        """Initialize the array collection.

        Args:
            collection (list[Any] | TaskNode): Inner collection.
                It can be either a static or dynamic list.
        """
        self.collection = collection
