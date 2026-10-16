# External and Local Tasks

## External tasks

Many times, tasks are just regular Python functions wrapped by sdag. However, you might also want to run Bash scripts, executables, or perhaps a piece of code unrelated to the sdag project. Tasks can be marked as external to inform sdag they do not wrap a Python function. Copy the following pipeline into a new module in the main project directory:

```py title="external_local_tasks.py"
from sdag import Script, pipeline


@pipeline
def external_dag():
    external_task(input_data="world")


@external_dag.task(Script("echo $INPUT_DATA"), mode="ext")
def external_task(input_data: str): ...
```

You can either write a separate bash script and insert its path into the decorator or use the `Script` object to embed its content into the module. Here, the Python function is only used to define the graph node and it's not actually called by the scheduler. Uppercased input values are set as environment variables by sdag, so you can use them inside the external script. You can run this example through:

```sh
sdag run external_dag --local
```

!!! warning
    Input arguments like `path` or `user` might cause troubles as they would override the corresponding `PATH` and `USER` environment variables. For this reason, a compile-time error is thrown when the input variables of external tasks might override POSIX environment variables. The obvious solution is to use safer names like `input_path` instead of `path`.

## Local tasks

Differently from other libraries, in sdag you don't specify a runner for the whole pipeline. Local and Slurm tasks can be freely mixed in the same workflow. This choice has been made to avoid spinning Slurm jobs that may stay in queue forever just to perform small operations that could be easily executed locally. Add a new pipeline to `external_local_tasks.py`:

```py title="external_local_tasks.py"
from sdag import script


@pipeline
def local_dag():
    local_task()


@local_dag.task(script, cmd="bash")
def local_task():
    print("I run locally!")
```

`cmd="bash"` is used to specify that the task must run as a nonblocking, local process instead of a Slurm job. This pipeline can now executed with:

```sh
sdag run local_dag
```

Under the hood, the `--local` option used in many other examples simply sets `cmd="bash"` to all tasks, thus forcing them to run as local processes.

!!! info
    Check out the [Slurm](./hello_world_slurm.md) section to run this example on Slurm.

