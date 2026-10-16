# Nested Calls

Add the following pipeline to a new module in the main project directory:

```py title="nested.py"
from pathlib import Path

from sdag import Artifact, pipeline, script, task


@pipeline
def outer_pipeline():
    t = inner_pipeline()
    global_task(path=t.artifacts["global_task"]["path"])


@pipeline
def inner_pipeline():
    global_task(path="./artifact.txt")


@task(script)
def global_task(path: Artifact[Path]):
    path.touch()
```


First of all, as you can see `global_task` is decorated with the `@task` instead of the `@<pipeline-name>.task` one. These tasks are not scoped to a single pipeline: every pipeline can import and use them. Their cache is also visible to all pipelines. In the example, one outer pipeline calls another pipeline and a global task equipped with an artifact. The node returned by a pipeline is special as it has access to all artifacts of its tasks. They can be accessed through the `artifacts` attribute by specifying both task and artifact name.

You can run:

```sh
sdag run outer_pipeline --local
```

to execute this example. When working with many nested pipelines, visualizations in the terminal quickly become crowded. You can use the `--squeeze` argument to collapse all inner pipelines into a unique node:

```sh
sdag view outer_pipeline --squeeze
```

Calling a task from another task is also easy. Copy the following snippet into the same module:

```py title="nested.py"
@pipeline
def task_calling_task():
    outer_task()


@task_calling_task.task(script)
def outer_task():
    result = inner_task.fn(a=1)
    print(f"1 + 1 = {result}")


@task_calling_task.task(script)
def inner_task(a: int):
    return a + 1
```

Tasks have a `fn` attribute pointing to the decorated function. This reference can be used to directly call the function. Keep in mind that in this case `inner_task` does not spawn as a separate job. It is instead called as a normal function inside the `outer_task` process. You can run this example through:

```sh
sdag run task_calling_task --local
```

!!! info
    Check out the [Slurm](../user_guide/hello_world_slurm.md) section to run this example on Slurm.