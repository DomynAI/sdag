# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import sys

import pytest
from sdag.detach import _filter_out_detach


@pytest.mark.parametrize(
    argnames="args",
    argvalues=[
        ["sdag", "run", "hello", "--detach"],
        ["sdag", "--detach", "run", "hello"],
    ],
)
def test_filter_out_detach(args: list[str]) -> None:
    """Check --detach is filtered out correctly.

    Args:
        args (list[str]): CLI args.
    """
    sys.argv = args
    filtered = _filter_out_detach()
    assert filtered == ["sdag", "run", "hello"]
