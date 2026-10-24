# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Types."""

from typing import Literal, Protocol

ExecMode = Literal["wrap", "ext"]
"""Available execution modes."""

Commands = Literal["bash", "sbatch"]
"""Available commands."""

Scope = Literal["local", "global"]
"""Task scopes."""

CacheOptions = Literal["none", "output", "io", "task", "project"]
"""Cache options."""

ContainerRuntime = Literal["singularity", "apptainer"]
"""Supported runtimes."""


class HasContainerSettings(Protocol):
    """Objects having container settings.

    They can be either tasks, pyprojs, or tags.

    Attributes:
        container: (str): Container path.
        container_runtime: (ContainerRuntime | None):
            Container runtime.
        container_binds: (list[str]): Container binds.
        container_options: (list[str]): Container options.
    """

    container: str
    container_runtime: ContainerRuntime | None
    container_binds: list[str]
    container_options: list[str]
