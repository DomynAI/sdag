# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Task I/O management."""

import inspect
import json
import logging
from pathlib import Path
from typing import Any

from sdag.commands import compile_and_return_dag, get_task
from sdag.compiler import master
from sdag.exceptions import DAGNotFoundError, InconsistentArraySettingsError
from sdag.models import ArtifactEdge, TaskOutput
from sdag.wrappers import Task, is_artifact, validate_kwargs

logger = logging.getLogger(__name__)


def _get_already_imported_task(
    task_name: str, subpipeline_name: str
) -> Task | None:
    """Get an already imported task.

    Args:
        task_name (str): Task name.
        subpipeline_name (str): Pipeline containing the task.

    Returns:
        Task | None: If the task is not found, None is returned.
    """
    if subpipeline_name in master.pipelines:
        pipeline = master.pipelines[subpipeline_name]
        if task_name in pipeline.tasks:
            return pipeline.tasks[task_name]

    if task_name in master.tasks:
        return master.tasks[task_name]

    return None


def _try_get_task(task_name: str, pipeline_name: str) -> Task | None:
    """Try to import tasks suppressing errors.

    Args:
        task_name (str): Task name.
        pipeline_name (str): Pipeline name.

    Returns:
        Task | None: Task name. If the task is not found, errors are
            suppressed and none is returned.
    """
    try:
        return get_task(task_name, pipeline_name)
    except DAGNotFoundError:
        return None


def find_and_import_task(
    task_name: str,
    pipeline_name: str,
    subpipeline_name: str,
    import_path: str,
    input_kwargs: str,
) -> Task:
    """Sufficiently clever way to import tasks.

    1. Check if the pipeline/task is already imported
    2. import the pipeline with the import path
    3. Try to import the subpipeline from its name
    4. Compile the pipeline to import the subtask

    Args:
        task_name (str): Task name.
        pipeline_name (str): Pipeline name.
        subpipeline_name (str): Subpipeline name.
        import_path (str): Pipeline import path.
        input_kwargs (str): Input kwargs used to compile
            the pipeline serialized as a JSON string.
            Useful to recompile the pipeline.

    Returns:
        Task: Imported task.
    """
    logger.debug("Checking if the task is already imported")
    target_task = _get_already_imported_task(task_name, subpipeline_name)
    if target_task is not None:
        return target_task

    if pipeline_name == subpipeline_name:
        logger.debug("Task is not in an inner pipeline")
        target_task = _try_get_task(task_name, import_path)
        if target_task is not None:
            return target_task

    logger.debug("Trying to directly import the subpipeline")
    target_task = _try_get_task(task_name, subpipeline_name)
    if target_task is not None:
        return target_task

    logger.info(
        "Pipeline '%s' not found (might have been dynamically"
        " imported). Trying to compile the pipeline to find it",
        subpipeline_name,
    )

    kwargs = json.loads(input_kwargs)
    compile_and_return_dag(
        path=import_path, extra_metadata=None, input_kwargs=kwargs
    )
    target_task = _get_already_imported_task(task_name, subpipeline_name)
    if target_task is None:
        msg = f"Task '{task_name}' of pipeline '{subpipeline_name}' not found"
        raise DAGNotFoundError(msg) from None

    return target_task


class IOHandler:
    """Manage I/O.

    Attributes:
        uid (int): Task uid.
        _pipeline_fname: DAG filename.
        _output_fname: Node output filename as specified in the
            scheduler.
        _input_fname: Node output filename as specified in the
            scheduler.
        _shard_fname: Sharded input filename as specified in the
            scheduler.
    """

    def __init__(
        self,
        uid: int,
        pipeline_dir: Path,
        shard_path: Path | None,
        task_id: int | None,
        each_key: str | None,
    ):
        """Initialize the I/O handler.

        Args:
            uid (int): Task unique UID.
            pipeline_dir (Path): Pipeline working directory.
            shard_path (Path | None): Shard path.
            task_id (int | None): Array task id.
            each_key (str | None): Sharded field in the array.
        """
        self.uid = uid
        self.pipeline_dir = pipeline_dir
        self.shard_path = shard_path
        self.task_id = task_id
        self.each_key = each_key
        self._pipeline_fname = "pipeline.json"
        self._output_fname = "output.json"
        self._input_fname = "input.json"
        self._shard_fname = "shard.json"

    def get_input(self, sig: inspect.Signature) -> dict[str, Any]:
        """Read the input data.

        It's written by the scheduler in the node directory.

        Args:
            sig (inspect.Signature): Task signature used to
                validate the input values.

        Returns:
            dict[str, Any]: Task input kwargs.
        """
        input_data = self._load_input()
        validate_kwargs(sig, input_data)
        return input_data

    def get_array_input(
        self,
        sig: inspect.Signature,
    ) -> dict[str, Any]:
        """Read the array shard input data.

        It's written by the scheduler in the node directory.

        Args:
            sig (inspect.Signature): Task signature used to
                validate the input values.

        Returns:
            dict[str, Any]: Task input kwargs.
        """
        if (
            self.shard_path is None
            or self.each_key is None
            or self.task_id is None
        ):
            raise InconsistentArraySettingsError(
                shard_path=self.shard_path,
                task_id=self.task_id,
                each=self.each_key,
            )

        input_data = self._load_input()
        path = self.shard_path / f"{self.task_id}" / self._shard_fname
        with path.open() as f:
            shard_data: dict[str, Any] = json.load(f)
        input_data[self.each_key] = shard_data

        validate_kwargs(sig, input_data)
        return input_data

    def get_artifacts(
        self, sig: inspect.Signature, input_kwargs: dict[str, Any]
    ) -> dict[str, ArtifactEdge]:
        """Build artifacts for execution.

        Args:
            sig (inspect.Signature): Task function signature.
            input_kwargs (dict[str, Any]): Input data. Those
                corresponding to artifacts will be turned into
                paths.

        Returns:
            dict[str, ArtifactEdge]: Artifact keys and artifacts.
                They will be merged with the input_kwargs.
        """
        artifacts: dict[str, ArtifactEdge] = {}
        for key, param in sig.parameters.items():
            if is_artifact(param):
                path = input_kwargs.get(key, "")
                artifacts[key] = ArtifactEdge(name=key, path=Path(path))
        return artifacts

    def serialize_output(
        self, output: Any, artifacts: dict[str, ArtifactEdge]
    ) -> None:
        """Serialize the output as JSON.

        Args:
            output (Any): Node output.
            artifacts (dict[str, ArtifactEdge]): Output artifacts.
        """
        artifact_list = list(artifacts.values())
        task_output = TaskOutput(output=output, artifacts=artifact_list)
        data = task_output.model_dump_json()
        output_path = self.pipeline_dir / f"{self.uid}" / self._output_fname

        with output_path.open("w") as f:
            f.write(data)

    def serialize_array_output(
        self, output: Any, artifacts: dict[str, ArtifactEdge]
    ) -> None:
        """Serialize a shard of output as JSON.

        Args:
            output (Any): Node output.
            artifacts (dict[str, ArtifactEdge]): Output artifacts.
        """
        if (
            self.shard_path is None
            or self.each_key is None
            or self.task_id is None
        ):
            raise InconsistentArraySettingsError(
                shard_path=self.shard_path,
                task_id=self.task_id,
                each=self.each_key,
            )

        artifact_list = list(artifacts.values())
        task_output = TaskOutput(output=output, artifacts=artifact_list)
        data = task_output.model_dump_json()
        output_path = self.shard_path / f"{self.task_id}" / self._output_fname

        with output_path.open("w") as f:
            f.write(data)

    def cast_values(
        self, sig: inspect.Signature, input_kwargs: dict[str, Any]
    ) -> None:
        """Automatically cast to Path if required.

        Args:
            sig (inspect.Signature): Task signature.
            input_kwargs (dict[str, Any]): Input arguments.
        """
        for key, param in sig.parameters.items():
            if param.annotation is Path or (
                is_artifact(param) and param.annotation.__origin__ is Path
            ):
                input_kwargs[key] = Path(input_kwargs[key])

    def serialize_artifacts(self, artifacts: dict[str, ArtifactEdge]) -> str:
        """Serialize artifacts as string for logging.

        Args:
            artifacts (dict[str, ArtifactEdge]): Artifacts.

        Returns:
            str: Serialized artifacts.
        """
        if not artifacts:
            return "{}"

        return "\n".join(
            artifact.model_dump_json(indent=4)
            for artifact in artifacts.values()
        )

    def _load_input(self) -> dict[str, Any]:
        """Load input without validation.

        Returns:
            dict[str, Any]: Loaded input
        """
        input_path = self.pipeline_dir / f"{self.uid}" / self._input_fname
        with input_path.open() as f:
            return json.load(f)
