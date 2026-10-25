# Tags

Tags can be used to specify custom configurations for groups of tasks. Tags can be added to tasks via the `tags` argument of the `@task`or `@<pipeline-name>.task` decorator:

```py
from sdag import script, task

@task(script, tags=["online", "small", "custom", "gpu"])
def some_task(): ...
```

The corresponding configurations can be set either in the `pyproject.toml` under `[[tool.sdag.tags]]` or in the `.sdag.toml` file under `[[tags]]`:


=== "`pyproject.toml`"
    ```toml
    [[tool.sdag.tags]]
    tag = "online"
    cmd = "bash"

    [[tool.sdag.tags]]
    tag = "small"
    cpus-per-task = 1

    [[tool.sdag.tags]]
    tag = "custom"
    script-path = "a/custom/script.sh"
    envs = {"ENV_NAME" = "value"}

    [[tool.sdag.tags]]
    tag = "gpu"
    container = "gpu-container.sif"
    container-options = ["--nv"]
    ```

=== "`.sdag.toml`"
    ```toml
    [[tags]]
    tag = "online"
    cmd = "bash"

    [[tags]]
    tag = "small"
    cpus-per-task = 1

    [[tags]]
    tag = "custom"
    script-path = "a/custom/script.sh"
    envs = {"ENV_NAME" = "value"}

    [[tags]]
    tag = "gpu"
    container = "gpu-container.sif"
    container-options = ["--nv"]
    ```

Tags have higher priority than `pyproject.toml`/`.sdag.toml` global configurations. Whenever a task is assigned more than one tag, such configurations are applied in the same order they are provided. Tags can be used to customize the behavior of groups of tasks. For example, some supercomputers have dedicated queues for jobs requiring internet access while others only allow outbound connections on login nodes. Tags can be used to enforce such policies. Moreover, tags specified in the `.sdag.toml` file override those in the `pyproject.toml`. So, different `.sdag.toml` files can be used to make pipelines run transparently across different machines without changing the source code. Tags currently allow one to customize:

- `local`: To run all relevant tasks as local bash processes.
- `script-path`: Used to change the execution script for selected tasks.
- `envs`: Used to set additional environment variables
- All Slurm settings available in `pyproject.toml`.
- The container configurations `container`, `container-runtime`, `container-binds`, and `container-options`.