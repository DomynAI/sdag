# Hello World in sdag

After [installing](../installation.md) sdag, copy the following code into a module named `hello.py` in the main project directory:

```py title="hello.py"
from sdag import pipeline, script


@pipeline
def hello_world():
    say_hello(name="sdag")


@hello_world.task(script)
def say_hello(name: str):
    print(f"hello from {name}")
```

There are two main objects in sdag, **pipelines** and **tasks**. Pipelines (marked with the `@pipeline` decorator) are used to represent the structure of the graph that will be executed. Tasks (marked with `@task` or `<pipeline-name>@task` decorators) are jobs scheduled depending on the current state of the graph.  The `script` argument of the task decorator contains the script fired by the scheduler. This pipeline can be compiled with:

```sh
sdag compile hello:hello_world --local
```

Where `hello:hello_world` is the pipeline import string in the form `path.to.module:function`. The previous command generates a `hello_world.json` file, which is saved in a `./compiled-pipelines` folder created by sdag. In many cases, you won't have to specify the full import string as sdag is able to discover pipelines simply by their name:

```sh
sdag compile hello_world --local
```

!!! info
    In more structured codebases it is convenient to explicitly define the base directory pipelines are searched into. Check out the [Structuring Larger Projects](../advanced/larger_projects.md) for details.

To run the compiled pipeline, execute:

```sh
sdag run hello_world.json
```

This command will start the scheduler and execute the `say_hello` task. You should see tables like this one printed in the terminal (the task PID will likely be different):

```
    ┌─────┬───────────┬─────────────┬───────────────────────┬──────┬─────────┐
    │ uid │ task      │ pipeline    │ status                │ cmd  │ try_num │
    ├─────┼───────────┼─────────────┼───────────────────────┼──────┼─────────┤
    │   2 │ say_hello │ hello_world │ Running (pid=3085406) │ bash │ 1       │
    └─────┴───────────┴─────────────┴───────────────────────┴──────┴─────────┘
```

If you instead executed:

```sh
sdag run hello_world --local
```

(thus without pointing to a compiled JSON file), the `hello_world` pipeline would be compiled on-the-fly and then immediately executed. Some sdag commands accept either pipeline names, import strings, or compiled JSON paths. The latter allows one to skip the compilation step. You can check out the [CLI](../cli.md) section for additional information.
