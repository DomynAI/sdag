# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Settings."""

import sys
from argparse import Namespace
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    from typing import Self

    import tomllib
else:
    import tomli as tomllib
    from typing_extensions import Self

from pydantic import ConfigDict, Field, NonNegativeInt, model_validator

from sdag.models import DAG, SlurmOverride, TaskNode
from sdag.scripts import ScriptPath
from sdag.types import ContainerRuntime, HasContainerSettings


class SDAGTag(SlurmOverride):
    """Tag configurations.

    User are allowed to override slurm variables,
    command, and script path.

    Attributes:
        tag (str): Tag name.
        local (bool): If True, set the command to 'bash'.
        script_path (Path | None): Script path.
        envs (dict[str, str]): Environment variables
            added to all relevant tasks.
    """

    tag: str
    local: bool = False
    script_path: Path | None = None
    container: str = ""
    container_runtime: ContainerRuntime | None = Field(
        alias="container-runtime", default=None
    )
    container_binds: list[str] = Field(
        alias="container-binds", default_factory=list
    )
    container_options: list[str] = Field(
        alias="container-options", default_factory=list
    )
    envs: dict[str, str] = Field(default_factory=dict)
    model_config = ConfigDict(
        extra="forbid", validate_by_alias=True, serialize_by_alias=True
    )


class DetachOptions(SlurmOverride):
    """Detached sdag command options.

    Attributes:
        job_name (str | None): Slurm job name. Defaults to 'sdag'.
        nodes (str | None): Number of nodes. Defaults to 1.
        tasks_per_node (str | None): Number of tasks per node.
            Defaults to 1.
        cpus_per_task (str | None): Number of CPUs per task.
            Defaults to 1.
        output (str | None): Slurm stdout. Defaults to
            'logs/sdag/sdag_%x.%j.out'.
        error (str | None): Slurm stderr. Defaults to
            'logs/sdag/sdag_%x.%j.err'.
    """

    job_name: str | None = Field(alias="job-name", default="sdag")
    nodes: NonNegativeInt | None = 1
    tasks_per_node: NonNegativeInt | None = Field(
        alias="tasks-per-node", default=1
    )
    cpus_per_task: NonNegativeInt | None = Field(
        alias="cpus-per-task", default=1
    )
    output: str | None = r"logs/sdag/sdag_%x.%j.out"
    error: str | None = r"logs/sdag/sdag_%x.%j.err"
    model_config = ConfigDict(
        extra="forbid", validate_by_alias=True, serialize_by_alias=True
    )

    def get_detached_args(self) -> list[str]:
        """Get the slurm detach args.

        Returns:
            list[str]: Args used by sbatch to submit the
                detached job.
        """
        args: list[str] = []
        dumped = self.model_dump(exclude_none=True)
        for key, value in dumped.items():
            args.append(f"--{key}")
            args.append(f"{value}")
        return args


class Pyproj(SlurmOverride):
    """pyproject.toml configs.

    Attributes:
        dagdir (str): DAG directory.
        compiled_dagdir (str): Compiled DAG directory.
        prepend_compiled_dagdir (bool): Add the compiled pipeline
            dir automatically if the directory has not been
            specified.
        time_between_polls (int): Time between successive Slurm polls
            in seconds. Defaults to 5.
        local (bool): If True, set the command to 'bash'.
        log_level (Literal["debug", "info", "warning", "error"]):
            Logging level.
        max_concurrency (int): Maximum number of tasks executed
            at the same time.
        slurm_grace_period (int): Number of turns a task can be missing
            from the response without being considered as failed.
            Defaults to 60.
        detach (DetachOptions): Detached command options. They are
            ignored if the command is not detached.
        fail_fast (bool): Kill the scheduler and all running tasks if
            any of them fails. Defaults to False.
        cache_lock (bool): Block the submission of cacheable tasks if
            another matching one is already running. Defaults to True.
        envs (dict[str, str]): Environment variables added to all tasks.
            They have higher priority with respect to the ones set inside
            pipelines.
        extra_dagdirs (list[str]): Import strings of additional dagirs
            to import. Useful to use pipelines implemented in
            dependencies.
    """

    dagdir: str = Field(default=".")
    compiled_dagdir: str = Field(
        alias="compiled-dagdir", default="./compiled-pipelines"
    )
    local: bool = False
    prepend_compiled_dagdir: bool = Field(
        alias="prepend-compiled-dagdir", default=True
    )
    log_level: Literal["debug", "info", "warning", "error"] = Field(
        alias="log-level", default="info"
    )
    time_between_polls: int = Field(
        alias="time-between-polls", default=5, ge=0
    )
    max_concurrency: int = Field(alias="max-concurrency", default=0, ge=0)
    slurm_grace_period: int = Field(
        alias="slurm-grace-period", default=60, ge=0
    )
    max_concurrent_runs: int = Field(
        alias="max-concurrent-runs", default=20, ge=0
    )
    fail_fast: bool = Field(alias="fail-fast", default=False)
    detach: DetachOptions = Field(default_factory=DetachOptions)
    cache_lock: bool = Field(alias="cache-lock", default=True)
    container: str = ""
    container_runtime: ContainerRuntime | None = Field(
        alias="container-runtime", default=None
    )
    container_binds: list[str] = Field(
        alias="container-binds", default_factory=list
    )
    container_options: list[str] = Field(
        alias="container-options", default_factory=list
    )
    envs: dict[str, str] = Field(default_factory=dict)
    extra_dagdirs: list[str] = Field(
        alias="extra-dagdirs", default_factory=list
    )
    tags: list[SDAGTag] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="forbid", validate_by_alias=True, serialize_by_alias=True
    )

    @model_validator(mode="after")
    def check_imported_dagdirs_are_not_paths(self) -> Self:
        """Check imported dagdirs are valid import paths.

        Raises:
            ImportDagdirPathError: The dagdir is not an import
                string but a path.

        Returns:
            Self: Pyproj.
        """
        for dagdir in self.extra_dagdirs:
            if "/" in dagdir:
                msg = (
                    f"Imported dagir '{dagdir}' is not a valid import string."
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def join_args_into_detach(self) -> Self:
        """Override detach args with the pyproj ones.

        account, partition, qos, and time are overwritten with the
        default values in the pyproj.

        Returns:
            Self: pyproj.
        """
        if self.detach.account is None:
            self.detach.account = self.account

        if self.detach.partition is None:
            self.detach.partition = self.partition

        if self.detach.qos is None:
            self.detach.qos = self.qos

        if self.detach.time is None:
            self.detach.time = self.time

        return self

    def join_cli_args(self, args: Namespace) -> None:
        """Join the user preferences into the pyproject.

        Args:
            args (Namespace): Parsed CLI args.
        """
        argdict = args.__dict__

        if argdict.get("log_level") is not None:
            self.log_level = args.log_level

        if argdict.get("time_between_polls") is not None:
            self.time_between_polls = args.time_between_polls

        if argdict.get("max_concurrency") is not None:
            self.max_concurrency = args.max_concurrency

        if argdict.get("compiled_dagdir") is not None:
            self.compiled_dagdir = args.compiled_dagdir

        if argdict.get("fail_fast"):
            self.fail_fast = True

        if argdict.get("local"):
            self.local = True
            for tag in self.tags:
                tag.local = True


@lru_cache(maxsize=1)
def get_pyproj(
    pyproj_path: str = "pyproject.toml", sdag_toml_path: str = ".sdag.toml"
) -> Pyproj:
    """Get configurations.

    Args:
        pyproj_path (str, optional): pyproject.toml path. Defaults
            to "pyproject.toml".
        sdag_toml_path (str, optional): sdag.toml path. Defaults
            to ".sdag.toml".

    Returns:
        Pyproj: Parsed configurations. User settings have not been
            added.
    """
    pyproj_dict = _load_toml(pyproj_path).get("tool", {}).get("sdag", {})
    sdag_toml_dict = _load_toml(sdag_toml_path)
    joined_dict = _join_configs(pyproj_dict, sdag_toml_dict)

    return Pyproj.model_validate(joined_dict, by_alias=True)


def apply_pyproj_configs(dag: DAG, pyproj: Pyproj) -> None:
    """Apply pyproject settings to all tasks.

    Args:
        dag (DAG): Compiled DAG.
        pyproj (Pyproj): Parsed pyproject.toml.
    """
    for task in dag.nodes:
        if task.kind == "task":
            apply_pyproj_to_task(task, pyproj)
            task.set_envs()


def apply_pyproj_to_task(task: TaskNode, pyproj: Pyproj) -> None:
    """Apply pyproject settings to a task.

    Args:
        task (TaskNode): Task node.
        pyproj (Pyproj): Parsed pyproject.
    """
    if pyproj.local:
        task.cmd = "bash"
    _apply_container_settings(task, pyproj)
    task.slurm.override_if_not_set(pyproj)
    task.envs |= pyproj.envs
    for tag in pyproj.tags:
        if tag.tag in task.tags:
            _apply_tag_configs(task, tag)


def _apply_tag_configs(task: TaskNode, tag: SDAGTag) -> None:
    """Override the configs from the tag ones.

    Args:
        task (TaskNode): Task.
        tag (SDAGTag): tag configurations of the task.
    """
    if tag.local:
        task.cmd = "bash"
    if tag.script_path is not None:
        task.script = ScriptPath(path=tag.script_path)
    task.envs |= tag.envs
    _apply_container_settings(task, tag)
    task.slurm.override_from(tag)


def _apply_container_settings(
    task: TaskNode, obj: HasContainerSettings
) -> None:
    """Apply the container settings to the task.

    Args:
        task (TaskNode): Task modified in place.
        obj (HasContainerSettings): Object containing higher-priority
            container settings.
    """
    if obj.container:
        task.container = obj.container
    if obj.container_runtime is not None:
        task.container_runtime = obj.container_runtime
    if obj.container_binds:
        task.container_binds.extend(obj.container_binds)
        task.container_binds = list(dict.fromkeys(task.container_binds))
    if obj.container_options:
        task.container_options.extend(obj.container_options)


def _load_toml(path: str | Path) -> dict[str, Any]:
    """Load a toml file.

    Args:
        path (str | Path): Toml file path.

    Returns:
        dict[str, Any]: Loaded toml. If the file is missing,
            an empty dict is returned.
    """
    toml_path = Path(path)
    if not toml_path.is_file():
        return {}

    with toml_path.open("rb") as f:
        return tomllib.load(f)


def _join_configs(
    pyproj_dict: dict[str, Any], sdag_toml_dict: dict[str, Any]
) -> dict[str, Any]:
    """Join configurations.

    Things that must be done:
    1. join configuration dicts
    2. join environment variables
    3. override tags
    4. join detach
    5. replace extras if set

    Args:
        pyproj_dict (dict[str, Any]): Loaded pyproject.toml.
        sdag_toml_dict (dict[str, Any]): Loaded sdag.toml.

    Raises:
        TypeError: Tag configs are not lists.

    Returns:
        dict[str, Any]: Joined configurations.
    """
    pyproj_envs = pyproj_dict.get("envs", {})
    sdag_envs = sdag_toml_dict.get("envs", {})
    pyproj_tags = pyproj_dict.get("tags", [])
    sdag_toml_tags = sdag_toml_dict.get("tags", [])
    pyproj_detach = pyproj_dict.get("detach", {})
    sdag_toml_detach = sdag_toml_dict.get("detach", {})
    pyproj_extras = pyproj_dict.get("extra-dagdirs", [])
    sdag_toml_extras = sdag_toml_dict.get("extra-dagdirs", [])
    pyproj_binds = pyproj_dict.get("container-binds", [])
    sdag_toml_binds = sdag_toml_dict.get("container-binds", [])
    pyproj_options = pyproj_dict.get("container-options", [])
    sdag_toml_options = sdag_toml_dict.get("container-options", [])

    if not isinstance(pyproj_tags, list) or not isinstance(
        sdag_toml_tags, list
    ):
        msg = "Tag settings must be valid lists"
        raise TypeError(msg)

    pyproj_tag_dict = _get_tag_dict(pyproj_tags)
    sdag_toml_tag_dict = _get_tag_dict(sdag_toml_tags)
    tag_dict = pyproj_tag_dict | sdag_toml_tag_dict
    configs = pyproj_dict | sdag_toml_dict
    pyproj_extras.extend(sdag_toml_extras)
    pyproj_binds.extend(sdag_toml_binds)
    pyproj_options.extend(sdag_toml_options)
    configs["envs"] = pyproj_envs | sdag_envs
    configs["tags"] = list(tag_dict.values())
    configs["detach"] = pyproj_detach | sdag_toml_detach
    configs["extra-dagdirs"] = list(dict.fromkeys(pyproj_extras))
    configs["container-binds"] = list(dict.fromkeys(pyproj_binds))
    configs["container-options"] = pyproj_options

    return configs


def _get_tag_dict(tags: list) -> dict:
    """Get a dictionary mapping tag names to tags.

    Args:
        tags (list): Tag configurations.

    Raises:
        TypeError: Tag configurations are not dictionaries.
        ValueError: Tag has no name.

    Returns:
        dict: tag name -> tag config map
    """
    tag_dict: dict[Any, dict[Any, Any]] = {}
    for tag in tags:
        if not isinstance(tag, dict):
            msg = f"Tags must be valid dictionaries. Invalid tag: '{tag}'"
            raise TypeError(msg)

        tag_name = tag.get("tag")
        if not tag_name:
            msg = f"Tags must have a valid name. Invalid tag: '{tag}'"
            raise ValueError(msg)

        tag_dict[tag_name] = tag

    return tag_dict
