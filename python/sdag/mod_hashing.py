# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import logging
import site
import sys
import sysconfig
from pathlib import Path

logger = logging.getLogger(__name__)


class ModuleHasher:
    """Hash modules.

    Attributes:
        _excluded (list[Path]): Paths that must be excluded. They
            include stuff like builtins, third-party libraries etc.
        _cwd (Path): Current working directory.
    """

    def __init__(self) -> None:
        """Initialize the module hasher."""
        self._excluded = self._get_excluded_paths()
        self._cwd = Path.cwd().resolve()

    def hash_modules(self) -> str:
        """Hash internal modules.

        Returns:
            str: Computed hash. If no modules are found,
                an empty string is returned.
        """
        logger.info("Start module hashing")
        internal_modules = self._find_internal_modules()
        return self._compute_hash(internal_modules)

    def _find_internal_modules(self) -> list[Path]:
        """Find all internal modules.

        Returns:
            list[Path]: Internal modules. They will be read
                and their content hashed.
        """
        internal_modules: list[Path] = []
        for m in list(sys.modules.values()):
            module_file = getattr(m, "__file__", None)
            if module_file:
                path = Path(module_file).resolve()
                if path.is_file() and self._is_module_internal(path):
                    internal_modules.append(path)

        return internal_modules

    def _compute_hash(self, internal_modules: list[Path]) -> str:
        """Hash the content of all internal modules.

        They are sorted to enforce reproducibility.

        Args:
            internal_modules (list[Path]): Modules to be hashed.

        Returns:
            str: Hash.
        """
        import hashlib

        if not internal_modules:
            logger.warning("No internal modules found")
            return ""

        h = hashlib.sha256()
        for p in sorted(internal_modules):
            path_str = str(p)
            content = p.read_bytes()
            h.update(path_str.encode("utf-8"))
            h.update(content)
        return h.hexdigest()

    def _is_module_internal(self, module_path: Path) -> bool:
        """Check if a module is internal and thus must be hashed.

        Only Python modules in the cwd are considered.

        Args:
            module_path (Path): Module path to be checked.

        Returns:
            bool: True if the module is internal.
        """
        if module_path.suffix != ".py":
            return False

        if not module_path.is_relative_to(self._cwd):
            return False

        for excluded_path in self._excluded:
            if module_path.is_relative_to(excluded_path):
                return False
        return True

    def _get_excluded_paths(self) -> list[Path]:
        """Get the excluded path list.

        These are paths to builtin, 3rd party tools, etc.

        Returns:
            list[Path]: Excluded paths.
        """
        sysconfig_paths = sysconfig.get_paths()
        site_pkgs = site.getsitepackages()
        usersite_pkgs = site.getusersitepackages()
        paths = [
            *site_pkgs,
            usersite_pkgs,
            sysconfig_paths["stdlib"],
            sysconfig_paths["platstdlib"],
        ]

        if sys.prefix != sys.base_prefix:
            paths.append(sys.prefix)

        return [Path(p).resolve() for p in paths]
