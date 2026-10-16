# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Types."""

from typing import Literal

ExecMode = Literal["wrap", "ext"]
"""Available execution modes."""

Commands = Literal["bash", "sbatch"]
"""Available commands."""

Scope = Literal["local", "global"]
"""Task scopes."""

CacheOptions = Literal["none", "output", "io", "task", "project"]
"""Cache options."""
