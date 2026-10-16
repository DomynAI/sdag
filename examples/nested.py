from pathlib import Path

from sdag import Artifact, pipeline, script, task


@pipeline
def outer_pipeline():
    """Pipeline calling an inner pipeline."""
    t = inner_pipeline()
    global_task(path=t.artifacts["global_task"]["path"])


@pipeline
def inner_pipeline():
    """Called by the outer one."""
    global_task(path="./artifact.txt")


@task(script)
def global_task(path: Artifact[Path]):
    """Global task."""
    path.touch()


@pipeline
def task_calling_task():
    """Pipeline with a task calling another one."""
    outer_task()


@task_calling_task.task(script)
def outer_task():
    """Task calling another task."""
    result = inner_task.fn(a=1)
    print(f"1 + 1 = {result}")


@task_calling_task.task(script)
def inner_task(a: int):
    """Inner task."""
    return a + 1
