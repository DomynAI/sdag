# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from sdag.mod_hashing import ModuleHasher


class TestModuleHasher:
    @pytest.fixture
    def hasher(self) -> ModuleHasher:
        """Hasher.

        Returns:
            ModuleHasher: Hasher.
        """
        return ModuleHasher()

    def test_venv_is_in_excluded_paths(self, hasher: ModuleHasher) -> None:
        """Check the venv is excluded.

        Args:
            hasher (ModuleHasher): Hasher.
        """
        venv = Path(".venv").resolve()
        assert any(venv.is_relative_to(p) for p in hasher._excluded)

    def test_sdag_code_is_not_excluded(self, hasher: ModuleHasher) -> None:
        """Internal code must not be excluded.

        Args:
            hasher (ModuleHasher): Hasher.
        """
        sdag_pkg = Path("python/sdag").resolve()
        assert all(not p.is_relative_to(sdag_pkg) for p in hasher._excluded)

    def test_internal_modules_are_in_root(self, hasher: ModuleHasher) -> None:
        """Check all internal modules are in the cwd.

        Args:
            hasher (ModuleHasher): Hasher.
        """
        internal_modules = hasher._find_internal_modules()
        cwd = Path.cwd().resolve()
        assert all(p.is_relative_to(cwd) for p in internal_modules)

    def test_empty_string_return_when_no_modules_are_found(
        self, hasher: ModuleHasher
    ) -> None:
        """An empty string must be returned if no modules are found.

        Args:
            hasher (ModuleHasher): Hasher.
        """
        assert hasher._compute_hash(internal_modules=[]) == ""

    def test_hashes_are_reproducible(self, hasher: ModuleHasher) -> None:
        """Hashes must be reproducible.

        Args:
            hasher (ModuleHasher): Hasher.
        """
        hash1 = hasher.hash_modules()
        hash2 = hasher.hash_modules()
        assert hash1 == hash2
