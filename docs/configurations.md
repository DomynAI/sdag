# Configurations

This section presents the configurations available in sdag.

## pyproject.toml

Configurations must be set under `[tool.sdag]`. Here are the available options:

| Option                       | Default value          | Description |
|------------------------------|------------------------|-------------|
| dagdir                       | "."                    | Path where pipelines are searched. |
| compiled-dagdir              | "./compiled-pipelines" | Compiled pipeline destination path. |
| local                        | false                  | If true, compile all tasks as local bash processes |
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

In the `pyproject.toml` file you can also set a number of Sbatch options that will override those set in scripts or inside pipelines:

| Option           | Description |
|------------------|-------------|
| job-name         | Job name |
| nodes            | Number of nodes |
| account          | Account name |
| partition        | Partition |
| qos              | Quality of Service |
| tasks-per-node  | Number of tasks per node |
| cpus-per-task    | Number of CPUs per task |
| gpus-per-node    | Number of GPUs per node |
| time             | Wall time |
| mem              | Requested memory |
| output           | stdout file path |
| error            | stderr file path |

Check out the official [documentation](https://slurm.schedmd.com/sbatch.html) for details. All these options are ignored if a task is marked as local. The `pyproject.toml` file also allows one to define tag configurations. Check out [Tags](advanced/tags.md) for details.

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

## Environment variables

Most environment variables are managed by the scheduler, so users don't really have to think about them. However, a few environment variables can be set to modify the default behavior:

| Environment variable   | Description |
|------------------------|-------------|
| `SDAG_HOME`            | Path of the sdag working directory. It's `~` by default. Inside it, a `.sdag` directory is created. |
| `SDAG_BASE_PATH`       | Base path of all artifacts. If set, it's automatically prepended to all artifacts if defined through relative paths.        |
