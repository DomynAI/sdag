# Unit Testing

Testing tasks is very easy. Decorated tasks have `fn` attribute that holds a reference to the decorated function. This reference can be used to call tasks directly.
You need to install [pytest](https://docs.pytest.org/en/stable/) tu run this example. Create a `test/` folder inside the main project directory and add a `test_tasks.py` module inside it containing the following code:

```py title="test_tasks.py"
from pathlib import Path

from sdag import Artifact, script, task


@task(script)
def task_with_input(a: int):
    return a + 1


@task(script)
def task_with_artifact(output_path: Artifact[Path]):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.touch()


def test_task_output() -> None:
    assert task_with_input.fn(1) == 2


def test_artifact_exists(tmp_path: Path) -> None:
    output_path = tmp_path / "artifact.txt"
    task_with_artifact.fn(output_path)
    assert output_path.is_file()
```

Simply run `pytest` to execute both tests and check they succeed.