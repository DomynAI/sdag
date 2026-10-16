# Running Pipelines on Slurm

Let's consider the pipeline of the previous [Section](./hello_world.md):

```py title="hello.py"
from sdag import pipeline, script


@pipeline
def hello_world():
    say_hello(name="sdag")


@hello_world.task(script)
def say_hello(name: str):
    print(f"hello from {name}")
```

So, far, the the `--local` option is used to run tasks locally. There are several ways to let it Run on Slurm.


=== "Custom scripts"
    Create a `submit.sh` [sbatch](https://slurm.schedmd.com/sbatch.html) script in the main project directory and paste the following content:

    ```sh title="submit.sh"
    #!/bin/bash
    #SBATCH --account=<account-name>
    #SBATCH --partition=<partition-name>
    #SBATCH --qos=<qos-name>
    #SBATCH --nodes=1
    #SBATCH --tasks-per-node=1
    #SBATCH --cpus-per-task=1
    #SBATCH --time=00:00:30

    sdag-execute
    ```

    Now, add the script path to the task decorator:

    ```py title="hello.py"
    @hello_world.task("submit.sh")
    def say_hello(name: str):
        print(f"hello from {name}")
    ```

    Bringing custom sbatch scripts is a very flexible approach for jobs that require some preparation before execution (like spinning up a [Ray](https://www.ray.io/) cluster) and for [external tasks](./external_tasks.md).

=== "Global configurations"
    Add the following configurations to your `pyproject.toml` file:

    ```toml title="pyproject.toml"
    [tool.sdag]
    account="<account-name>"
    partition="<partition-name>"
    qos="<qos-name>"
    nodes=1
    cpus-per-task=1
    time="00:02:00"
    ```

    These configurations will be applied globally to all tasks. Check out the [Configuration](../configurations.md) section for details and the [Tags](../advanced/tags.md) section for configuring groups of tasks.

=== "Node override"
    Modify the pipeline as follows:

    ```py title="hello.py"
    @pipeline
    def hello_world():
        t = say_hello(name="sdag")
        t.slurm.account = <account-name>
        t.slurm.partition = <partition-name>
        t.slurm.qos = <qos-name>
        t.slurm.nodes = 1
        t.slurm.tasks_per_node = 1
        t.slurm.cpus_per_task = 1
        t.slurm.time = "00:00:30"
    ```

    This approach works best for fine tuning some configurations for specific nodes. Check out the [Override](../advanced/override.md) section for details.

!!!info
    `job-name`, `output`, and `error` are intentionally missing here as sdag overrides them by default.

`<account-name>`, `<partition-name>`, and `<qos-name>` in the examples are the Slurm account, partition, and quality of service you have access to.
These approaches can also be used in combination with each other: The account name can be set at the project level, custom scripts are used to prepare the execution of specific jobs and single nodes might override their own wall time. When in conflict, the priority is: node overrides > global settings > sbatch scripts.

Now that the configurations are set, the pipeline can be run on Slurm via:

```sh
sdag run hello_world
```

By default, task logs are written in a `logs/` folder created in the main project directory.
