# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Custom exceptions."""

from pathlib import Path
from typing import Any

from sdag.constants import POSIX_ENV_VARIABLES


class SDAGError(Exception):
    """SDAG exception base class."""


class TaskNotUniqueError(SDAGError):
    """Task name is not unique."""

    def __init__(self, name: str):
        """Raise the error.

        Args:
            name (str): Not unique task name.
        """
        msg = f"Task name '{name}' is not unique."
        super().__init__(msg)


class KwargNotFoundError(SDAGError):
    """Task input kwarg not found."""

    def __init__(self, key: str):
        """Raise the error.

        Args:
            key (str): Input key not found.
        """
        msg = f"Input argument '{key}' not found."
        super().__init__(msg)


class DynamicArtifactError(SDAGError):
    """Dynamic artifacts are not allowed."""

    def __init__(self, key: str):
        """Raise the error.

        Args:
            key (str): Input key not found.
        """
        msg = f"key '{key}': Dynamic artifacts are not allowed."
        super().__init__(msg)


class DAGNotSetError(SDAGError):
    """No DAG is set in the compiler."""

    def __init__(self):
        """Raise the exception."""
        msg = "no pipelines are currently being compiled."
        super().__init__(msg)


class IncorrectElifError(SDAGError):
    """Incorrect Elif expression."""

    def __init__(self):
        """Raise the exception."""
        msg = "Incorrect Elif expression."
        super().__init__(msg)


class IncorrectElseError(SDAGError):
    """Incorrect else expression."""

    def __init__(self):
        """Raise the exception."""
        msg = "Incorrect Else expression."
        super().__init__(msg)


class POSIXOverrideError(SDAGError):
    """External tasks have variables conflicting with POSX."""

    def __init__(self, task_name: str, key: str):
        """Raise the exception.

        Args:
            task_name (str): Task violating the check.
            key (str): Forbidden key used.
        """
        banned = ", ".join(POSIX_ENV_VARIABLES)
        key_up = key.upper()
        msg = (
            f"External task '{task_name}' is trying to set the '{key}'"
            f" keyword argument. Please choose a different name as '{key_up}'"
            " would override a standard POSIX environment variable."
            f" The banned keywords are:\n{banned}"
        )
        super().__init__(msg)


class CLIError(SDAGError):
    """CLI error."""

    def __init__(self):
        """Raise the exception."""
        msg = "Unknown CLI command."
        super().__init__(msg)


class DAGNotFoundError(SDAGError):
    """DAG not found in path."""


class ExtraCLIArgsError(SDAGError):
    """Extra CLI arguments are not allowed."""

    def __init__(self, extra_kwargs: dict[str, Any]):
        """Raise the exception.

        Args:
            extra_kwargs (dict[str, Any]): Extra args used.
        """
        msg = (
            "Extra CLI arguments are not allowed."
            f" Extra arguments used: {extra_kwargs}"
        )
        super().__init__(msg)


class MultipleEachError(SDAGError):
    """Job arrays across multiple axes is not supported."""

    def __init__(self, key: str, old_key: str) -> None:
        """Raise the exception.

        Args:
            key (str): New key of the job array.
            old_key (str): Old key of the job array.
        """
        msg = (
            f"Trying to set a job array across key '{key}' but"
            f" '{old_key}' is already registered. Use a for loop"
            " over the first key to set up grids."
        )
        super().__init__(msg)


class InconsistentArraySettingsError(SDAGError):
    """Job array settings are not consistent.

    Shard path and task id must be either both None or set to a
    valid value.
    """

    def __init__(
        self, shard_path: Path | None, task_id: int | None, each: str | None
    ) -> None:
        """Raise the exception.

        Args:
            shard_path (Path | None): Shard input path.
            task_id (int | None): Slurm array task id.
            each (str | None): Sharded key.
        """
        msg = (
            f"Shard path '{shard_path}', task array {task_id},"
            f" and sharded field '{each}' are not consistent"
        )
        super().__init__(msg)
