# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
import sdag.discovery
from sdag.discovery import (
    _detect_root,
    _find_module_path,
    _find_pipeline_path,
    find_all_pipelines,
    get_importable_module_path,
)
from sdag.exceptions import DAGNotFoundError


def test_detect_root_src_layout(tmp_path: Path) -> None:
    init = tmp_path / "pkg" / "src" / "pkg" / "__init__.py"
    sub_init = init.parent / "subpkg" / "__init__.py"
    sub_init.parent.mkdir(parents=True, exist_ok=True)
    init.touch(exist_ok=True)
    sub_init.touch(exist_ok=True)
    root = _detect_root(sub_init)

    assert root == tmp_path / "pkg" / "src"


def test_detect_root_flat_layout(tmp_path: Path) -> None:
    init = tmp_path / "pkg" / "pkg" / "__init__.py"
    sub_init = init.parent / "subpkg" / "__init__.py"
    sub_init.parent.mkdir(parents=True, exist_ok=True)
    init.touch(exist_ok=True)
    sub_init.touch(exist_ok=True)
    root = _detect_root(sub_init)

    assert root == tmp_path / "pkg"


def test_detect_root_single_script(tmp_path: Path) -> None:
    script = tmp_path / "pkg" / "script.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.touch(exist_ok=True)
    root = _detect_root(script)

    assert root == tmp_path / "pkg"


def testget_importable_module_path_single_script(tmp_path: Path) -> None:
    script = tmp_path / "pkg" / "script.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.touch(exist_ok=True)
    path = get_importable_module_path(script)

    assert path == "script"


def testget_importable_module_path_src_layout(tmp_path: Path) -> None:
    script = tmp_path / "pkg" / "src" / "pkg" / "subpkg" / "script.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.touch(exist_ok=True)
    (script.parent / "__init__.py").touch(exist_ok=True)
    (script.parent.parent / "__init__.py").touch(exist_ok=True)
    path = get_importable_module_path(script)

    assert path == "pkg.subpkg.script"


def testget_importable_module_path_flat_layout(tmp_path: Path) -> None:
    script = tmp_path / "pkg" / "pkg" / "subpkg" / "script.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.touch(exist_ok=True)
    (script.parent / "__init__.py").touch(exist_ok=True)
    (script.parent.parent / "__init__.py").touch(exist_ok=True)
    path = get_importable_module_path(script)

    assert path == "pkg.subpkg.script"


def _create_target_structure(base_path: Path) -> Path:
    content = """from sdag import pipeline, task


@task("script.sh")
def global_task(): ...


@pipeline
def target_pipeline():
    global_task()
    local_task()

@target_pipeline.task("script.sh")
def local_task(): ...
"""

    disturbing_content = """from sdag import pipeline, task


@pipeline
def non_target_pipeline():
    local_task()

@non_target_pipeline.task("script.sh")
def local_task(): ...
"""

    script = base_path / "pkg" / "src" / "pkg" / "subpkg" / "script.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    (script.parent / "__init__.py").touch(exist_ok=True)
    (script.parent.parent / "__init__.py").touch(exist_ok=True)

    with script.open("w") as fscript:
        fscript.write(content)

    for letter in "abcdef":
        fname = f"{letter}.py"
        with (script.parent / fname).open("w") as fscript:
            fscript.write(disturbing_content)
        with (script.parent.parent / fname).open("w") as fscript:
            fscript.write(disturbing_content)

    return script


def test_find_pipeline_path(tmp_path: Path) -> None:
    target_path = _create_target_structure(base_path=tmp_path)
    dag_dir = str(tmp_path / "pkg")
    pipeline_path = _find_pipeline_path(
        name="target_pipeline", dag_dir=dag_dir
    )

    assert pipeline_path == target_path


def test_do_not_find_pipeline_path(tmp_path: Path) -> None:
    _create_target_structure(base_path=tmp_path)
    dag_dir = str(tmp_path / "pkg")
    pipeline_path = _find_pipeline_path(name="missing", dag_dir=dag_dir)

    assert pipeline_path is None


def test_find_module_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sdag.discovery, "_find_dag_dir", lambda: str(tmp_path / "pkg")
    )

    _create_target_structure(base_path=tmp_path)
    module_path = _find_module_path(name="target_pipeline")

    assert module_path == "pkg.subpkg.script"


def test_do_not_find_module_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sdag.discovery, "_find_dag_dir", lambda: str(tmp_path / "pkg")
    )

    _create_target_structure(base_path=tmp_path)
    with pytest.raises(DAGNotFoundError):
        _find_module_path(name="missing")


def test_find_all_pipelines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sdag.discovery, "_find_dag_dir", lambda: str(tmp_path / "pkg")
    )

    content12 = """from sdag import pipeline, task


@task("script.sh")
def global_task(): ...

@pipeline
def target_pipeline1():
    global_task()
    local_task()

@pipeline
def target_pipeline2():
    global_task()
    local_task()

@target_pipeline1.task("script.sh")
def local_task(): ...

@target_pipeline2.task("script.sh")
def local_task(): ...
"""

    content3 = """from sdag import pipeline, task


@task("script.sh")
def global_task(): ...

@pipeline
def target_pipeline3():
    global_task()
    local_task()

@target_pipeline3.task("script.sh")
def local_task(): ...
"""

    script12 = tmp_path / "pkg" / "src" / "pkg" / "subpkg" / "script12.py"
    script3 = tmp_path / "pkg" / "src" / "pkg" / "script3.py"

    script12.parent.mkdir(parents=True, exist_ok=True)
    (script12.parent / "__init__.py").touch(exist_ok=True)
    (script3.parent / "__init__.py").touch(exist_ok=True)

    with script12.open("w") as fscript:
        fscript.write(content12)

    with script3.open("w") as fscript:
        fscript.write(content3)

    pipelines = find_all_pipelines()
    assert pipelines == {
        "target_pipeline1": str(script12),
        "target_pipeline2": str(script12),
        "target_pipeline3": str(script3),
    }
