# Overriding Configurations at Compile Time

When called inside a pipeline, tasks return their corresponding nodes in the graph. These nodes expose most configurations as attributes that can be modified at compile time to override their default values. Here is an example:

```py
from sdag import ScriptPath, pipeline, script


@pipeline
def override():
    t = default_task()
    t.name = "custom_name"
    t.cache = "io"
    t.cache_size = 5
    t.script = ScriptPath(path="script.sh")
    t.cmd = "bash"

    t.envs["HELLO"] = "world"

    t.slurm.job_name = "default_job"
    t.slurm.account = "my-account"
    t.slurm.time = "00:00:30"
    t.slurm.output = "path/to/file.out"


@override.task(script)
def default_task(): ...
```

As you can see, it is possible to:

- Modify properties like name, script, and caching behavior.
- Define environment variables that will be automatically set by the scheduler so you can access them during the task execution.
- Override Slurm configurations set in the execution script. These are ignored if the task runs as a local bash process. When compared with those in `pyproject.toml`, hardcoded Slurm options have higher priority.