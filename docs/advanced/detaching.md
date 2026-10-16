# Detaching Commands

On public supercomputers, jobs running on login nodes usually have limited resources and wall time. The Rust scheduler of sdag is intentionally lightweight so it can typically survive many hours on login nodes without being killed. If the SSH connection goes down, `sdag restart` can be used to safely restart the scheduler and pick the execution from where it left off.

Nevertheless, for long workflows across large graphs it may be better to just submit the scheduler as a Slurm job on a compute node. This can be achieved by adding the `--detach` option to the CLI command. For example:

```sh
sdag run <pipeline-name> --detach
```

will compile and start the scheduler as a separate Slurm job. By default, these commands are executed on 1 CPU (`nodes = 1`, `tasks-per-node = 1`, and `cpus-per-task = 1`) and inherit `account`, `partition`, and `qos` from `pyproject.toml`/`.sdag.toml` config files. stdout and stderr are written in a `./logs/sdag` folder. The default behavior can be modified through the `[tool.sdag.detach]` options in the `pyproject.toml`. Check out the [Configuration](../configurations.md) section for details.

When the detached scheduler starts, you can use:

```sh
sdag status <pipeline-name>
```

to print the status table of the last checkpoint without checking the scheduler logs manually.