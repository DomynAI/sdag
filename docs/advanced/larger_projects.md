# Structuring Larger Projects

When working with larger projects made of many pipelines, it is convenient to set the directory sdag searches pipelines into explicitly. Both [flat and src layouts](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) are supported. The only important point is to add `__init__.py` files to all subfolders in the tree to let sdag treat them as regular, importable packages.

This examples takes advantage of the `hello.py` module created in the [first example](../user_guide/hello_world.md):

```py title="hello.py"
from sdag import pipeline, script


@pipeline
def hello_world():
    say_hello(name="sdag")


@hello_world.task(script)
def say_hello(name: str):
    print(f"hello from {name}")
```

## Flat layout

Create a `<my-package>/workflows` directory and an empty `__init__.py` module inside it. Now, copy the `hello.py` module from the previous example in the `workflows/` folder. Finally, copy the following snippet inside the `pyproject.toml` file:

```toml title="pyproject.toml"
[tool.sdag]
dagdir = "<my_package>/workflows"
```

Your project tree should look like this:

``` title="flat layout"
<my-package>
├── pyproject.toml
└── <my_package>
    ├── __init__.py
    └── workflows
        ├── __init__.py    <- Don't forget to add this
        └── hello.py       <- hello_world pipeline
```

## src layout

Create a `src/<my-package>/workflows` directory and an empty `__init__.py` module inside it. Now copy the `hello.py` module from the previous example in the `workflows/` folder. Finally, copy the following snippet inside the `pyproject.toml` file:

```toml title="pyproject.toml"
[tool.sdag]
dagdir = "src/<my_package>/workflows"
```

Your project tree should look like this:

``` title="src layout"
<my-package>
├── pyproject.toml
└── src
    └── <my_package>
        ├── __init__.py
        └── workflows
            ├── __init__.py    <- Don't forget to add this
            └── hello.py       <- hello_world pipeline
```

### Importing and running pipelines

Now that everything is set up, you can list the available pipelines:

```sh
sdag list
```

you should see the `hello_world` pipeline available. You can run the pipeline through:

```sh
sdag run hello_world --local
```

If you don't like to specify `--local` every time, add the following setting to the `pyproject.toml`:

```toml title="pyproject.toml"
[tool.sdag]
dagdir = "<flat-or-src-layout>/workflows"
cmd = "bash"
```

So that every task will be executed locally with bash.