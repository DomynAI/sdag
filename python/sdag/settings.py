# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Settings."""

import logging
import sys
from functools import lru_cache
from pathlib import Path

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from strenum import StrEnum
    from typing_extensions import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings

from sdag.exceptions import InconsistentArraySettingsError


class Settings(BaseSettings):
    """Env variables set by the scheduler.

    Attributes:
        sdag_pipeline_dir (str): Pipeline directory.
        sdag_pipeline_name (str): Pipeline name.
        sdag_subpipeline_name (str): Task pipeline name.
            If there are no nested pipeline, it is equal
            to the pipeline name.
        sdag_import_path (str): Import path used to compile
            the pipeline.
        sdag_input_kwargs (str): Pipeline input kwargs
            JSON string. Useful to recompile the pipeline.
        sdag_uid (str): Node unique id.
        sdag_task_fn (str): Task function name.
        sdag_task_name (str): Task name, by default it's equal to
            the task name.
        sdag_each_key (str | None): If set, it's the sharded key in
            job arrays.
        sdag_shard_path (str | None): If set, it's the shard path in
            job arrays.
        slurm_array_task_id (str | None): If set, it's the task id
            in job arrays.
        sdag_try_num (int): Number of times the task has been executed.
    """

    sdag_pipeline_dir: Path
    sdag_pipeline_name: str
    sdag_subpipeline_name: str
    sdag_import_path: str
    sdag_input_kwargs: str
    sdag_uid: int
    sdag_task_name: str
    sdag_task_fn: str
    sdag_try_num: int
    sdag_log_level: str
    sdag_shard_path: Path | None = None
    sdag_each_key: str | None = None
    slurm_array_task_id: int | None = None

    @model_validator(mode="after")
    def shard_paths_and_task_id_must_be_consistent(self) -> Self:
        """Both must be either set or null.

        Returns:
            Self: Settings.
        """
        shard_path, task_id, each = (
            self.sdag_shard_path,
            self.slurm_array_task_id,
            self.sdag_each_key,
        )
        shard_ok = shard_path is not None and bool(shard_path)
        task_id_ok = task_id is not None
        each_ok = each is not None and bool(each)
        if shard_ok != task_id_ok or task_id_ok != each_ok:
            raise InconsistentArraySettingsError(shard_path, task_id, each)

        return self

    def is_job_array(self) -> bool:
        """Check if the job is part of an array.

        Returns:
            bool: True if the job is part of a job array.
        """
        shard_path, task_id, each = (
            self.sdag_shard_path,
            self.slurm_array_task_id,
            self.sdag_each_key,
        )
        shard_ok = shard_path is not None and bool(shard_path)
        task_id_ok = task_id is not None
        each_ok = each is not None and bool(each)

        return shard_ok and task_id_ok and each_ok


@lru_cache
def get_cached_settings() -> Settings:
    """Get the SDAG environment variables.

    Returns:
        Settings: Parsed environment variables.
    """
    return Settings()  # type: ignore


class CompileSettings(BaseSettings):
    """Compilation environment variables.

    Attributes:
        sdag_home (str): sdag home directory. Defaults to '~'.
        sdag_base_path (Path | None): Base path. Defaults to None.
    """

    sdag_home: str = "~"
    sdag_base_path: Path | None = None


@lru_cache
def get_compile_settings() -> CompileSettings:
    """Get cached compilation settings.

    Returns:
        CompileSettings: Cached compilation settings.
    """
    return CompileSettings()


class LogColor(StrEnum):
    """Logging colors matching with env_logger."""

    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    RESET = "\033[0m"


class EnvLoggerFormatter(logging.Formatter):
    """Formatter mimicking env_logger.

    Attributes:
        _crop (dict[str, str]): Used to crop log levels as
            env_logger does.
        _colors (dict[str, str]): Logging level colors.
    """

    def __init__(self):
        """Initialize the log formatter."""
        self._crop = {"WARNING": "WARN", "CRITICAL": "CRIT"}
        self._colors = {
            "DEBUG": LogColor.BLUE,
            "INFO": LogColor.GREEN,
            "WARN": LogColor.YELLOW,
            "ERROR": LogColor.RED,
            "CRIT": LogColor.RED,
        }
        fmt = "[%(asctime)s %(levelname)-5s %(name)s] %(message)s"
        super().__init__(fmt=fmt, datefmt="%Y-%m-%dT%H:%M:%SZ")

    def format(self, record: logging.LogRecord) -> str:
        """Format a record.

        Args:
            record (logging.LogRecord): Raw record.

        Returns:
            str: Formatted record.
        """
        record.levelname = self._format_levelname(record.levelname)
        return super().format(record)

    def _format_levelname(self, levelname: str) -> str:
        """Format the level name like env_logger does.

        The level name is cropped or padded to 5 characters
        and colored.

        Args:
            levelname (str): Levelname.

        Returns:
            str: Formatted levelname.
        """
        name = self._crop.get(levelname, levelname)
        color = self._colors.get(name, "INFO")
        return f"{color}{name:<5}{LogColor.RESET}"


def configure_logging(log_level: str) -> None:
    """Simple logging configuration.

    Everything is streamed to the stderr.

    Args:
        log_level (str): Logging level.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(EnvLoggerFormatter())
    logging.basicConfig(level=log_level.upper(), handlers=[handler])
