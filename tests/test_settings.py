# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import pytest
from sdag.settings import EnvLoggerFormatter, configure_logging


def test_configure_logging() -> None:
    """Check nothing weird shows up."""
    configure_logging(log_level="info")


class TestEnvLoggerFormatter:
    @pytest.fixture
    def formatter(self) -> EnvLoggerFormatter:
        """Log formatter.

        Returns:
            EnvLoggerFormatter: Log formatter.
        """
        return EnvLoggerFormatter()

    @pytest.mark.parametrize(
        argnames=("levelname", "formatted"),
        argvalues=[
            ("DEBUG", "\033[34mDEBUG\033[0m"),
            ("INFO", "\033[32mINFO \033[0m"),
            ("WARNING", "\033[33mWARN \033[0m"),
            ("ERROR", "\033[31mERROR\033[0m"),
        ],
    )
    def test_format_logname(
        self, levelname: str, formatted: str, formatter: EnvLoggerFormatter
    ) -> None:
        """Check the log formatter works as expected.

        Args:
            levelname (str): Level name ('DEBUG' etc).
            formatted (str): Expected formatted level name.
            formatter (EnvLoggerFormatter): Log formatter.
        """
        assert formatter._format_levelname(levelname) == formatted
