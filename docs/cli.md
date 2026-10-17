# The sdag CLI

This section lists the commands available in the sdag CLI.

!!! info
    Some commands provide optional arguments like `--log-level` or `--local`. CLI options have the highest priority and they always override other settings.

### `list`

List pipelines or the most recent runs of a specific pipeline.

- List all available pipelines: `sdag list`
- List all runs of a pipeline: `sdag list pipeline_name`

### `compile`

Compile a pipeline and save its JSON representation. Through its arguments, it is possible to modify the destination folder and the file names. All pipeline input values must be passed as CLI extra arguments.

- Compile a pipeline from the import string: `sdag compile path.to.module:pipeline_name`
- Compile a pipeline from its name: `sdag compile pipeline_name`
- Compile a pipeline to `path/to/destination/custom-name.json`: `sdag compile pipeline_name -d path/to/destination -n custom-name`
- Compile a pipeline and set all tasks as local: `sdag compile pipeline_name --local`

### `run`

Run a compiled pipeline. If called with the import string or the pipeline name, the pipeline is compiled on-the-fly before execution.

- Run a pipeline from the compiled JSON: `sdag run path/to/compiled_pipeline.json`
- Compile and run a pipeline from its name: `sdag run pipeline_name`
- Compile and run a pipeline from its name as a separate Slurm job: `sdag run pipeline_name --detach`

### `runtask`

Run a specific task of a pipeline. All task input values must be passed as CLI extra arguments.

- Run a task `sdag runtask task_name pipeline_name`
- Run a task with input arguments: `sdag runtask task_name pipeline_name -- --input-value=5`

### `restart`

Restart the scheduler from where it left off when it was killed.

- Restart the last run: `sdag restart pipeline_name`
- Restart a specific run: `sdag restart pipeline_name --hash xxx`
- Restart the last run as a separate Slurm job: `sdag restart pipeline_name --detach`

### `retry`

Reset all failed and skipped task before restarting the run. it's virtually equivalent to `sdag restart` if no tasks failed or were skipped.

- Retry the last run: `sdag retry pipeline_name`
- Retry a specific run: `sdag retry pipeline_name --hash xxx`
- Retry the last run as a separate Slurm job: `sdag retry pipeline_name --detach`

### `kill`

Kill a running pipeline and the scheduler.

- Kill the running pipeline: `sdag kill pipeline_name`
- Kill a specific run: `sdag kill pipeline_name --hash xxx`

### `describe`

Print information about the tasks of a pipeline. The table will display things like task names, input arguments, artifacts, and whether they are cached or not.

- Describe a compiled pipeline: `sdag describe path/to/compiled_pipeline.json`
- Compile and describe a pipeline from the import string: `sdag describe path.to.module:pipeline_name`
- Compiled and describe a pipeline from its name: `sdag describe pipeline_name`

### `prune`

Prune the cache of tasks and pipelines.

- Prune the cache of a global task: `sdag prune task_name`
- Prune the cache of multiple tasks of a pipeline: `sdag prune task1 task2 -p pipeline_name`
- Prune the cache of a task and all its dependencies: `sdag prune task1 -p pipeline_name --cascade`
- Prune the cache of a pipeline: `sdag prune -p pipeline_name`
- Prune the whole sdag cache: `sdag prune all`

### `view`

Print the pipeline graph in the terminal.

- Print the graph of a compiled pipeline: `sdag view path/to/compiled_pipeline.json`
- Compile and print the the pipeline graph in the terminal: `sdag view pipeline_name`

### `status`

Print the status table of the last checkpoint.

- Print the checkpoint of the last run: `sdag status pipeline_name`
- Print the checkpoint of a specific run: `sdag status pipeline_name --hash xxx`