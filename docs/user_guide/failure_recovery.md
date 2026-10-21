# Failure Recovery

Failures are unfortunately very common in HPC. In the context of sdag, the two most common failures that can happen are:

1. The sdag scheduler gets killed
2. Tasks fail for whatever reason

## Scheduler failures

The scheduler checkpoints its status. So, in case of failures it can be restarted from where it left off. To restart the scheduler, run:

```sh
sdag restart <pipeline-name>
```

Once restarted, it gets from Slurm the status of the supposedly running jobs to update the graph state. However, all previously running local jobs (that get killed if the scheduler goes down) are marked as failed.

## Task failures

Add the following pipeline to a new module in the main project directory:


```py title="failure_recovery.py"
from sdag import pipeline, script


@pipeline
def failure():
    t = failed_task()
    will_never_run(t)


@failure.task(script)
def failed_task():
    raise ValueError("Failing...")


@failure.task(script)
def will_never_run():
    print("You will never see this message")
```

Run:

```sh
sdag run failure --local
```

to execute the pipeline. As expected, `failed_task` fails and all dependent nodes are skipped. If you fix the bug and the graph structure doesn't change, you can retry the run and see if it completes successfully:

```sh
sdag retry failure
```

`retry` will reset all failed and skipped tasks before continuing the run. If no tasks failed or get skipped, then `sdag retry` is virtually identical to the `sdag restart` command of the previous section. You can also set the number of retries for a task. Modify `failed_task` as follows:

```py hl_lines="1"
@failure.task(script, retries=2)
def failed_task():
    raise ValueError("Failing...")
```

And run the pipeline again:

```sh
sdag run failure --local
```

You will see that the execution of `failed_task` is retried two times before marking it as failed definitively.

!!! info
    Check out the [Slurm](./hello_world_slurm.md) section to run this example on Slurm.