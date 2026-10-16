from pathlib import Path

from sdag import Artifact, pipeline, script


@pipeline
def cached():
    """DAG with cached and non-cached tasks."""
    t = cached_task(a="world")
    non_cached_task(t)


@cached.task(script, cache="io")
def cached_task(a: str):
    """Cacheable task.

    Args:
        a (str): Cached input value.
    """
    print(f"I only run once. The value of a is {a}")


@cached.task(script)
def non_cached_task():
    """Task without caching."""
    print("I run every time")


@pipeline
def name_change():
    """Cached tasks with different names."""
    a_task(value=1)
    t = a_task(value=2)
    t.name = "another_task"


@name_change.task(script, cache="io")
def a_task(value: int):
    """Cacheable task."""
    print(f"value: {value}")


@pipeline
def dag_with_artifact():
    """DAG with artifact."""
    t = create_file(path="artifact.txt")
    print_path(input_path=t.artifacts["path"])


@dag_with_artifact.task(script, cache="io")
def create_file(path: Artifact[Path]):
    """Create an artifact."""
    path.touch()


@dag_with_artifact.task(script, cache="io")
def print_path(input_path: str):
    """Print the input path."""
    print(f"The input path is {input_path}")
