# Entrypoint Customization

So far, `sdag-execute` has always been used to run tasks. There are a few reasons to modify the task entrypoint, one of them being logging customization. sdag configures its own logger when running tasks. By default, everything is logged to stderr so that it can be easily captured by Slurm and written in the `error` file. To modify logging and in general to wrap the task call with some custom logic, you need to create an entrypoint for the sdag task execution. Create an `entrypoint.py` module and paste the following code:

```py  title="entrypoint.py"
from sdag import sdag_execute


if __name__ == "__main__":
    sdag_execute(configure_logger=False)
```

It is now possible to create a `submit.sh` file with a call to this module:

```sh  title="submit.sh"
#!/bin/bash
#SBATCH --account=<account-name>
#SBATCH --partition=<partition-name>
#SBATCH --qos=<qos-name>
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:00:30

python path/to/entrypoint.py
```

In this way, `entrypoint.py` becomes the entry point of every task and the call can be wrapped in custom logic. The `configure_logger` option can be set to `False` to disable the default logging configuration.