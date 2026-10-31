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

from pydantic import (
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

from sdag.models import DAG, SlurmOverride, TaskNode
from sdag.scripts import ScriptPath
from sdag.types import ContainerRuntime


class DetachOptions(SlurmOverride):
    """Detached sdag command options."""

    def get_detached_args(self) -> list[str]:
        """Get the slurm detach args.

        Returns:
            list[str]: Args used by sbatch to submit the
                detached job.
        """
        args: list[str] = []
        defaults = {
            "job-name": "sdag",
            "nodes": 1,
            "ntasks-per-node": 1,
            "cpus-per-task": 1,
            "output": r"logs/sdag/sdag_%x.%j.out",
            "error": r"logs/sdag/sdag_%x.%j.err",
        }
        dumped = self.model_dump(exclude_none=True)
        dumped = defaults | dumped
        for key, value in sorted(dumped.items()):
            args.append(f"--{key}")
            args.append(f"{value}")
        return args


class TaskConfig(SlurmOverride):
    """Task configurations.

    Configurations applied to all tasks.

    Attributes:
        local (bool): Set to True to run all tasks as local
            bash processes. Defaults to False.
        script_path (Path | None): Change the task script with
            a custom one. Defaults to None.
        container (str): Container path. Defaults to "".
        container_runtime (ContainerRuntime): Container runtime.
        container_binds (list[str]): Directories binded to the
            container.
        container_options (list[str]): Container options.
        envs (dict[str, str]): Environment variables set by the
            scheduler.
    """

    local: bool = False
    script_path: Path | None = Field(alias="script-path", default=None)
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

    def get_overwritten_by(self, other: Self) -> None:
        """Override values from another object.

        Args:
            other (Self): Overriding configurations.
        """
        if other.local:
            self.local = other.local
        if other.script_path is not None:
            self.script_path = other.script_path
        if other.container:
            self.container = other.container
        if other.container_runtime:
            self.container_runtime = other.container_runtime
        if other.container_binds:
            self.container_binds.extend(other.container_binds)
            self.container_binds = list(dict.fromkeys(self.container_binds))
        if other.container_options:
            self.container_options.extend(other.container_options)
        other.override_slurm(self)
        self.envs |= other.envs

    def apply_to_task(self, task: TaskNode) -> None:
        """Apply the configurations to a task.

        Hardcoded task configurations have higher priority. The only
        exceptions are `local` as it is meant for debugging and
        script_path (as tasks without a script are not allowed).

        Args:
            task (TaskNode): Task.
        """
        if self.local:
            task.cmd = "bash"
        if self.script_path is not None:
            task.script = ScriptPath(path=self.script_path)
        if not task.container and self.container:
            task.container = self.container
        if not task.container_runtime and self.container_runtime:
            task.container_runtime = self.container_runtime
        if self.container_binds:
            task.container_binds = self.container_binds + task.container_binds
            task.container_binds = list(dict.fromkeys(task.container_binds))
        if self.container_options:
            # If duplicated singularity keeps the last one
            task.container_options = (
                self.container_options + task.container_options
            )
        self.override_slurm_if_not_set(task.slurm)  # type: ignore
        task.envs = self.envs | task.envs


class SDAGTag(TaskConfig):
    """Tag configurations.

    Attributes:
        tag (str): Tag name.
    """

    tag: str


class Pyproj(TaskConfig):
    """pyproject.toml configs.

    Attributes:
        dagdir (str): DAG directory.
        compiled_dagdir (str): Compiled DAG directory.
        prepend_compiled_dagdir (bool): Add the compiled pipeline
            dir automatically if the directory has not been
            specified.
        time_between_polls (int): Time between successive Slurm polls
            in seconds. Defaults to 5.
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
        extra_dagdirs (list[str]): Import strings of additional dagirs
            to import. Useful to use pipelines implemented in
            dependencies.
    """

    dagdir: str = Field(default=".")
    compiled_dagdir: str = Field(
        alias="compiled-dagdir", default="./compiled-pipelines"
    )
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
    extra_dagdirs: list[str] = Field(
        alias="extra-dagdirs", default_factory=list
    )
    tags: list[SDAGTag] = Field(default_factory=list)
    _tagmap: dict[str, SDAGTag] = PrivateAttr(default_factory=dict)
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
    def spot_duplicate_tags(self) -> Self:
        """Check if duplicate tag configurations are present.

        Raises:
            ValueError: Duplicate tag configs are found.

        Returns:
            Self: pyproj untouched.
        """
        seen = set()
        duplicates = set()
        for tag in self.tags:
            if tag.tag in seen:
                duplicates.add(tag.tag)
            else:
                seen.add(tag.tag)

        if duplicates:
            names = ", ".join(sorted(duplicates))
            msg = f"Found duplicate tag configurations for tags '{names}'"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def fill_tagmap(self) -> Self:
        """Fill the tagmap.

        Returns:
            Self: Pyproj.
        """
        for tag in self.tags:
            self._tagmap[tag.tag] = tag
        return self

    @property
    def tagmap(self) -> dict[str, SDAGTag]:
        """Tag name -> tag map.

        Returns:
            dict[str, SDAGTag]: Map.
        """
        return self._tagmap

    def join_cli_args(self, args: Namespace) -> None:
        """Join the user preferences into the pyproject.

        Args:
            args (Namespace): Parsed CLI args.
        """
        argdict = args.__dict__

        if argdict.get("log_level"):
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

    def get_overwritten_by(self, other: Self) -> None:  # type: ignore
        """Have other settings overriding the present ones.

        Args:
            other (Self): Overriding settings.
        """
        non_task_fields = {
            "dagdir",
            "compiled_dagdir",
            "prepend_compiled_dagdir",
            "log_level",
            "time_between_polls",
            "max_concurrency",
            "slurm_grace_period",
            "max_concurrent_runs",
            "fail_fast",
            "cache_lock",
        }

        for field in non_task_fields:
            if field in other.model_fields_set:
                setattr(self, field, getattr(other, field))

        self.extra_dagdirs.extend(other.extra_dagdirs)
        self.extra_dagdirs = list(dict.fromkeys(self.extra_dagdirs))
        other.detach.override_slurm(self.detach)
        self._get_tags_overwritten(other)
        super().get_overwritten_by(other)

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

    def _get_tags_overwritten(self: Self, other: Self) -> None:
        """Join tags together.

        Args:
            self (Self): Overwritten settings.
            other (Self): Overriding settings.
        """
        tagmap = other.tagmap | self.tagmap
        for name, tag in self.tagmap.items():
            if name in other.tagmap:
                tag.get_overwritten_by(other.tagmap[name])
        self._tagmap = tagmap
        self.tags = list(self._tagmap.values())


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
    pyproj = Pyproj.model_validate(pyproj_dict)
    sdag_toml = Pyproj.model_validate(sdag_toml_dict)
    pyproj.get_overwritten_by(sdag_toml)
    pyproj.join_args_into_detach()
    return pyproj


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
    cfg = TaskConfig()
    cfg.get_overwritten_by(pyproj)
    for tag_name in task.tags:
        tag = pyproj.tagmap.get(tag_name)
        if tag is not None:
            cfg.get_overwritten_by(tag)
    cfg.apply_to_task(task)


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
