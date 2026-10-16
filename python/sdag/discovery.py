# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

"""Pipeline discovery and lazy import.

Pipelines are discovered via AST parsing, so
we don't have to explicitely import files.
"""

import ast
import importlib
import logging
import sys
from pathlib import Path

from sdag.compiler import master
from sdag.exceptions import DAGNotFoundError
from sdag.pyproj import Pyproj, get_pyproj
from sdag.wrappers import Pipeline

logger = logging.getLogger(__name__)


def add_cwd_to_path() -> None:
    """Add the cwd to the path.

    Useful for path.to.module:dag imports.
    """
    cwd = Path.cwd()
    sys.path.insert(0, str(cwd))


def find_pipeline_by_name(name: str) -> Pipeline:
    """Import a pipeline from its name.

    Args:
        name (str): If the name is provided, the
            pipeline is discovered and imported. If the
            input path in the form `path.to.module:pipeline`
            is used, discovery is skipped and the pipeline is
            imported directly.

    Raises:
        DAGNotFoundError: The DAG is not found in the path.

    Returns:
        Pipeline: Imported pipeline.
    """
    splits = name.split(":")
    pipeline_name = splits[-1]
    if pipeline_name in master.pipelines:
        return master.pipelines[pipeline_name]

    if ":" in name:
        module_path = "".join(splits[:-1])
    else:
        module_path = _find_module_path(pipeline_name)

    logger.info(
        "Importing pipeline '%s' from module '%s'", pipeline_name, module_path
    )
    try:
        module = importlib.import_module(module_path)
        pipeline = getattr(module, pipeline_name)
    except (ImportError, AttributeError) as exc:
        msg = f"Pipeline '{name}' not found"
        raise DAGNotFoundError(msg) from exc

    return pipeline


def find_all_pipelines() -> dict[str, str]:
    """Find all importable pipelines.

    Returns:
        dict[str, str]: Pipeline names and paths.
    """
    pyproj = get_pyproj()
    dagdir = _get_dagdir(pyproj)
    extra_dagdirs = _get_extra_dagdirs(pyproj)
    pipelines = find_all_pipelines_in_tree(dagdir)
    for extra_dagdir in extra_dagdirs:
        path = _import_extra_dagdir_and_get_path(extra_dagdir)
        if path is not None:
            imported_pipelines = find_all_pipelines_in_tree(path)
            pipelines = imported_pipelines | pipelines

    return pipelines


def find_all_pipelines_in_tree(dagdir: str) -> dict[str, str]:
    """Parse the ast to find pipelines.

    Returns:
        dict[str, str]: Pipeline names and paths.
    """
    pipelines: dict[str, str] = {}
    for path in Path(dagdir).rglob("**/*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for d in node.decorator_list:
                    name = _extract_decorator_name(d)
                    if name == "pipeline":
                        pipelines[node.name] = str(path)
    return pipelines


def _import_extra_dagdir_and_get_path(extra_dagdir: str) -> str | None:
    """Import an extra dagdir and get its path.

    Args:
        extra_dagdir (str): _description_

    Returns:
        str | None: _description_
    """
    try:
        m = importlib.import_module(extra_dagdir)
    except ImportError:
        logger.exception("Failed to import dagdir '%s'", extra_dagdir)
        return None

    if m.__file__ is None:
        return None

    # __file__ is the __init__.py of the package
    path = Path(m.__file__)
    if path.is_file():
        return str(path.parent)

    return m.__file__


def get_importable_module_path(path: Path) -> str:
    """Turn a module path into its import string.

    Args:
        path (Path): Module path.

    Returns:
        str: Import string.
    """
    file_path = path.resolve()
    root = _detect_root(file_path)
    root = root.resolve()

    logger.debug("Detected root: '%s'", root)
    relative = file_path.relative_to(root)
    parts = relative.with_suffix("").parts

    return ".".join(parts)


def _find_module_path(name: str) -> str:
    """Find the pipeline module from the name.

    Args:
        name (str): Pipeline name.

    Raises:
        DAGNotFoundError: The module is not found.

    Returns:
        str: MOdule path.
    """
    pyproj = get_pyproj()
    dagdir = _get_dagdir(pyproj)
    extra_dagdirs = _get_extra_dagdirs(pyproj)
    path = _find_pipeline_path(name, dagdir)
    if path is not None:
        return get_importable_module_path(path)

    for extra_dagdir in extra_dagdirs:
        base_path = _import_extra_dagdir_and_get_path(extra_dagdir)
        if base_path is not None:
            path = _find_pipeline_path(name, base_path)
            if path:
                return _find_extra_pipeline_import_path(
                    extra_dagdir, base_path, path
                )

    msg = f"Module for pipeline '{name}' not found"
    raise DAGNotFoundError(msg)


def _find_pipeline_path(name: str, dagdir: str) -> Path | None:
    """Find the pipeline path inside the DAG directory.

    Args:
        name (str): Pipeline name.
        dagdir (str): DAG directory.

    Returns:
        Path | None: Pipeline path. Returns None if the pipeline
            is not found.
    """
    for path in Path(dagdir).rglob("**/*.py"):
        try:
            if _is_pipeline_in_tree(path, name):
                return path
        except Exception as exc:  # noqa: BLE001, PERF203
            logger.warning("Failed to parse '%s': %s", path, exc)

    return None


def _is_pipeline_in_tree(path: Path, name: str) -> bool:
    """Check if the pipeline decorator is found in the tree.

    Args:
        path (Path): Module path.
        name (str): Pipeline name.

    Returns:
        bool: True if the pipeline is found.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name != name:
                continue
            for d in node.decorator_list:
                dec_name = _extract_decorator_name(d)
                if dec_name == "pipeline":
                    return True
    return False


def _extract_decorator_name(d: ast.expr) -> str | None:
    """Extract the name of a decorator.

    Args:
        d (ast.expr): AST expression containing the decorator.

    Returns:
        str | None: Decorator name. If not found, None is returned.
    """
    if isinstance(d, ast.Name):
        return d.id
    if isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
        return d.func.id
    return None


def _detect_root(file_path: Path) -> Path:
    """Walk up the directory tree to find the right sys.path root.

    - src layout:  …/src/ is the root if it exists in the chain.
    - flat layout: the topmost directory that still has an __init__.py
        (i.e. the package root), or the file's own directory
        if it's a standalone script.
    """
    init = "__init__.py"
    for parent in file_path.parents:
        if parent.name == "src" and not (parent / init).exists():
            return parent

    candidate = file_path.parent
    while (candidate / init).exists():
        candidate = candidate.parent

    return candidate


def _find_extra_pipeline_import_path(
    extra_dagdir: str, base_path: str | Path, path: str | Path
) -> str:
    """Find the extra pipeline import path.

    Args:
        extra_dagdir (str): Extra dagdir import string.
        base_path (str | Path): Extra dagdir path.
        path (str | Path): Pipeline module path.

    Returns:
        str: Pipeline module import string.
    """
    rel_path = Path(path).relative_to(base_path)
    rel_import_string = str(rel_path.parent).replace("/", ".")
    # otherwise top-level dag strings would be <extra-dagdir>..module
    rel_import = f".{rel_import_string}" if rel_import_string != "." else ""
    return f"{extra_dagdir}{rel_import}.{rel_path.stem}"


def _get_dagdir(pyproj: Pyproj) -> str:
    """Get the dagdir.

    It's kept separate so it's easy to patch.

    Args:
        pyproj (Pyproj): Parsed pyproject.

    Returns:
        str: dagdir.
    """
    return pyproj.dagdir


def _get_extra_dagdirs(pyproj: Pyproj) -> list[str]:
    """Get extra dagdirs.

    It's kept separate so it's easy to patch.

    Args:
        pyproj (Pyproj): Parsed pyproject.

    Returns:
        list[str]: dagdir.
    """
    return pyproj.extra_dagdirs
