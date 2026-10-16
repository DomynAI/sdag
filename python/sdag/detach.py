# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Job detaching."""

import logging
import shlex
import subprocess
import sys

from sdag.pyproj import Pyproj, get_pyproj
from sdag.settings import configure_logging

logger = logging.getLogger(__name__)


def detach_command() -> None:
    """Detach an sdag command."""
    pyproj = get_pyproj()
    configure_logging(log_level=pyproj.log_level)

    logger.info("Detaching command 'sdag %s'", " ".join(sys.argv[1:]))
    args = _filter_out_detach()
    _run_detached_command(args, pyproj)


def _run_detached_command(args: list[str], pyproj: Pyproj) -> None:
    """Run the detached command.

    Args:
        args (list[str]): CLI arguments without --detach.
        pyproj (Pyproj): user configurations.
    """
    script = f"""#!/bin/bash\n{shlex.join(args)}"""
    sbatch_args = pyproj.detach.get_detached_args()
    logger.debug("Script:\n%s", script)
    logger.info("Detach args: '%s'", sbatch_args)
    subprocess.run(["sbatch", *sbatch_args], input=script.encode("utf-8"))


def _filter_out_detach() -> list[str]:
    """Filter out --detach from the CLI args.

    So that the detached command runs without detaching again.

    Returns:
        list[str]: Filtered args.
    """
    return [arg for arg in sys.argv if arg != "--detach"]
