# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""sdag version read from Cargo.toml."""

from importlib.metadata import version

__version__ = version("sdag")
"""sdag version."""
