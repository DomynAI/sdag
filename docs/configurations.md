# Configurations

This section presents the configurations available in sdag.

## pyproject.toml

Configurations must be set under `[tool.sdag]`. Here are the available options:

| Option                       | Default value          | Description |
|------------------------------|------------------------|-------------|
| dagdir                       | "."                    | Path where pipelines are searched. |
| compiled-dagdir              | "./compiled-pipelines" | Compiled pipeline destination path. |
| local                        | false                  | If true, compile all tasks as local bash processes |
| script-path                  | None                   | Set a unique script for all tasks, thus overriding the ones in decorators |
| prepend-compiled-dagdir      | true                   | Prepend the `compiled-dagdir` so you can write `sdag run dag.json` instead of `sdag run ./compiled-pipelines/dag.json` |
| log-level                    | "info"                 | Compiler, scheduler, and task log level |
| time-between-polls           | 5                      | Time between successive scheduler Slurm polls (seconds) |
| max-concurrency              | 0                      | Maximum number of tasks running at the same time. Set to zero to allow any number of tasks to run at the same time |
| slurm-grace-period           | 60                     | Maximum number of times a task can be missing from the Slurm output without considering it as failed. |
| max-concurrent-runs          | 20                     | Maximum number of runs of the same pipeline kept by sdag. Set to 0 to keep all runs. |
| fail-fast                    | false                  | If true, kill the scheduler and all running jobs if any task fails. |
| cache-lock                   | true                   | If true, block the submission of cacheable tasks if a matching one is already running. |
| envs                         | {}                     | Environment variables available to every task |
| detach                       | Check out [Detaching Commands](advanced/detaching.md) for details | Sbatch options for detached jobs. |
| extra-dagdirs                | []                     | Import strings in the form 'path.to.module' of extra packages pipelines are searched into. Useful to import pipelines from dependencies. |
| container                    | ""                     | Path to the container used for all tasks of the project. |
| container-runtime            | "singularity"          | Container technology. |
| container-binds              | []                     | Paths bound to all containerized tasks. |
| container-options            | []                     | Options applied to all containerized tasks. |

In the `pyproject.toml` file you can also set a number of sbatch options that will override those set in scripts:

| Option           | Description |
|------------------|-------------|
| job-name         | Job name |
| account          | Account name |
| partition        | Partition |
| qos              | Quality of Service |
| nodes            | Number of nodes |
| nodelist         | Request a specific list of nodes |
| exclude          | Node exclusion list |
| output           | stdout file path |
| error            | stderr file path |
| mem              | Requested memory |
| time             | Wall time |
| mail-type | Notify on state change: BEGIN, END, FAIL or ALL |
| mail-user | User e-mail |
| gres | generic resources |
| gres-flags | gres flags |
| tmp | Temporary disk |
| ntasks | Number of tasks |
| ntasks-per-node | Number of tasks per node |
| cpus-per-task    | Number of CPUs per task |
| ntasks-per-core | Number of tasks per core |
| mem-per-cpu | Real memory per allocated CPU |
| ntasks-per-socket | Number of tasks to invoke on each socket |
| threads-per-core | Number of threads per core |
| sockets-per-node | Number of sockets per node |
| cores-per-socket | Number of cores per socket |
| gpus | Number of GPUs |
| gpus-per-node    | Number of GPUs per node |
| gpus-per-socket | Number of GPUs per socket |
| gpus-per-task | Number of GPUs per task |
| mem-per-gpu | Real memory required per allocated GPU |
| cpus-per-gpu | Number of CPUs per allocated GPU |


Check out the official [documentation](https://slurm.schedmd.com/sbatch.html) for details. All these options are ignored if a task is marked as local.

## .sdag.toml

If available, this file must be located in the main project directory. It has the exact same schema as `pyproject.toml`. However, configurations must not be placed under `[tool.sdag]`.

=== "`pyproject.toml`"

    ```toml
    [tool.sdag]
    dagdir = "my_package/workflows"
    max-concurrency = 10

    [tool.sdag.envs]
    ENV_NAME = "env_value"

    [tool.sdag.detach]
    cpus-per-task = 5

    [[tool.sdag.tags]]
    tag = "online"
    local = true
    ```

=== "`.sdag.toml`"

    ```toml
    dagdir = "my_package/workflows"
    max-concurrency = 10

    [envs]
    ENV_NAME = "env_value"

    [detach]
    cpus-per-task = 5

    [[tags]]
    tag = "online"
    local = true
    ```

All configurations set in the `.sdag.toml` have higher priority than those in `pyproject.toml` and they will override them when conflicting.
`.sdag.toml` is often ignored from git (although nothing prevents you from committing it if you find it useful) and treated somewhat like a `.env` to set things you might not want to push to a remote repo (like the Slurm `account` or `qos`). You can also use it to define machine-specific configurations that must override the default ones to transparently adapt the codebase to different clusters.

## Tags

Tags can be used to specify custom configurations for groups of tasks. Tags can be added to tasks via the `tags` argument of the `@task` or `@<pipeline-name>.task` decorator:

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
    local = true

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
    local = true

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

Tags have higher priority than `pyproject.toml`/`.sdag.toml` global configurations. Whenever a task is assigned more than one tag, such configurations are applied in the same order they are provided. When tags conflict, the later one wins. Tags can be used to customize the behavior of groups of tasks. For example, some supercomputers have dedicated queues for jobs requiring internet access while others only allow outbound connections on login nodes. Tags can be used to enforce such policies. Moreover, tags specified in the `.sdag.toml` file are joined with those in `pyproject.toml`. So, different `.sdag.toml` files can be used to make pipelines run transparently across different machines without changing the source code. Tags currently allow one to customize:

- `local`: To run all relevant tasks as local bash processes.
- `script-path`: Used to change the execution script for selected tasks.
- `envs`: Used to set additional environment variables.
- All Slurm settings available in `pyproject.toml`.
- The container configurations `container`, `container-runtime`, `container-binds`, and `container-options`.

## Priorities

To make sdag flexible enough, settings can be set at many different levels and follow clear priority rules when they conflict. Lists are combined across levels, with higher priorities appended last. Environment variables are merged key by key, with higher priorities winning.

| Priority    | Source |
|-------------|--------|
| 1 (highest) | CLI arguments |
| 2           | Values set in task decorators or as node overrides |
| 3           | Tags (`.sdag.toml` > `pyproject.toml`) |
| 4           | Global settings (`.sdag.toml` > `pyproject.toml`) |
| 5           | `#SBATCH` lines in custom scripts |

**Custom scripts**

`#SBATCH` directives in custom scripts have the lowest priority.

**Global settings**

Global settings in `pyproject.toml` like `account` or `cpus-per-task` have higher priority than the sbatch directives in custom scripts. When joined with `.sdag.toml`, scalars from `.sdag.toml` win, lists are combined, and envs merged.

**Tags**

Tags have higher priority than global configurations. When `pyproject.toml` is joined with `.sdag.toml`, the behavior is similar to the global setting one.

**Hardcoded values**

Values hardcoded in task decorators have higher priority than those in tags. These fields can also be [overwritten](advanced/override.md) by single nodes in the graph at compile time. There are two notable exceptions to this rule: `local` and `script-path`. These are switches that always apply, because their purpose is to override how tasks run.

**CLI arguments**

CLI arguments have the highest priority. This means options like `--local` or `--log-level` always prevail over any other setting.

## Environment variables

Most environment variables are managed by the scheduler, so users don't really have to think about them. However, a few environment variables can be set to modify the default behavior:

| Environment variable   | Description |
|------------------------|-------------|
| `SDAG_HOME`            | Path of the sdag working directory. It's `~` by default. Inside it, a `.sdag` directory is created. |
| `SDAG_BASE_PATH`       | Base path of all artifacts. If set, it's automatically prepended to all artifacts if defined through relative paths.        |
