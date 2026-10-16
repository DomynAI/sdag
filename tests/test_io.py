# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from sdag.exceptions import KwargNotFoundError
from sdag.io import IOHandler
from sdag.models import Artifact, ArtifactEdge


class TestIOHandler:
    @pytest.fixture
    def handler(self, tmp_path: Path) -> IOHandler:
        return IOHandler(
            uid=0,
            pipeline_dir=tmp_path / "pipeline",
            shard_path=None,
            task_id=None,
            each_key=None,
        )

    @pytest.mark.parametrize(
        argnames="output",
        argvalues=[None, True, "test", 1, [1, 2, 3], {"a": 1}],
    )
    def test_output_serialization(
        self, output: Any, handler: IOHandler
    ) -> None:
        """Check the output serialization in JSON.

        Args:
            output (Any): Output.
            handler (IOManager): I/O manager.
        """
        path = handler.pipeline_dir / f"{handler.uid}"
        path.mkdir(parents=True, exist_ok=True)

        handler.serialize_output(output, artifacts={})

        with (path / handler._output_fname).open() as f:
            data = json.load(f)

        assert data == {"output": output, "artifacts": []}

    def test_get_input(self, handler: IOHandler) -> None:
        """Test the input value retrieval.

        Args:
            handler (IOManager): I/O manager.
        """

        def foo(a: Any) -> None: ...

        path = handler.pipeline_dir / f"{handler.uid}"
        path.mkdir(parents=True, exist_ok=True)
        input_data = {"a": True}
        with (path / handler._input_fname).open("w") as f:
            json.dump(input_data, f)

        sig = inspect.signature(foo)
        input_retrieved = handler.get_input(sig)
        assert input_data == input_retrieved

    def test_input_not_in_signature(self, handler: IOHandler) -> None:
        """The input key is not in the function signature.

        Args:
            handler (IOManager): I/O manager.
        """

        def foo() -> None: ...

        path = handler.pipeline_dir / f"{handler.uid}"
        path.mkdir(parents=True, exist_ok=True)
        input_data = {"a": True}
        with (path / handler._input_fname).open("w") as f:
            json.dump(input_data, f)

        sig = inspect.signature(foo)
        with pytest.raises(KwargNotFoundError):
            handler.get_input(sig)

    def test_input_kwargs(self, handler: IOHandler) -> None:
        """Test the input kwargs.

        The input key is not in the function signature but the function
        contains input kwargs, no error is thrown.

        Args:
            handler (IOManager): I/O manager.
        """

        def foo(**kwargs) -> None: ...

        path = handler.pipeline_dir / f"{handler.uid}"
        path.mkdir(parents=True, exist_ok=True)
        input_data = {"a": True}
        with (path / handler._input_fname).open("w") as f:
            json.dump(input_data, f)

        sig = inspect.signature(foo)
        handler.get_input(sig)

    def test_serialize_artifacts(self, handler: IOHandler) -> None:
        artifacts = {
            "a": ArtifactEdge(name="name", path=Path("path/to/artifact"))
        }
        expected = """{
    "name": "name",
    "path": "path/to/artifact"
}"""

        assert handler.serialize_artifacts(artifacts) == expected

    def test_cast_values(self, handler: IOHandler) -> None:
        def foo(a: Path, b: Artifact[Path], c: Artifact[str], d: Artifact): ...

        sig = inspect.signature(foo)
        kwargs = {"a": "a/path", "b": "b/path", "c": "c/path", "d": "d/path"}

        handler.cast_values(sig, kwargs)

        assert kwargs["a"] == Path("a/path")
        assert kwargs["b"] == Path("b/path")
        assert kwargs["c"] == "c/path"
        assert kwargs["d"] == "d/path"

    def test_get_artifacts(self, handler: IOHandler) -> None:
        def foo(a: Path, b: Artifact[Path], c: Artifact[str], d: Artifact): ...

        sig = inspect.signature(foo)
        kwargs = {"a": "a/path", "b": "b/path", "c": "c/path", "d": "d/path"}

        artifacts = handler.get_artifacts(sig, kwargs)
        expected = {
            "b": ArtifactEdge(name="b", path=Path("b/path")),
            "c": ArtifactEdge(name="c", path=Path("c/path")),
            "d": ArtifactEdge(name="d", path=Path("d/path")),
        }

        assert artifacts == expected
