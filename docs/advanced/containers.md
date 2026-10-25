# Containers

Docker is often not available on HPC systems and the main container technology is typically [Singularity](https://docs.sylabs.io/guides/latest/user-guide/)/[Apptainer](https://apptainer.org/), which sdag supports out of the box. This section shows how to build a containerized project suitable for air-gapped HPC environments.

!!! info
    To follow along with the example you need to install [uv](https://docs.astral.sh/uv/) and [Singularity](https://docs.sylabs.io/guides/latest/user-guide/quick_start.html).

## Setting up the project

Create a new project named `container-proj` equipped with Python 3.14 and cd into it:

```sh
uv init --package --python=3.14 container-proj
cd container-proj
```

Sync the environment and activate it:

```sh
uv sync
source .venv/bin/activate
```

Now install [sdag](../installation.md) and [Numpy](https://numpy.org/):

```sh
uv add "sdag @ git+https://github.com/DomynAI/sdag"
uv add numpy
```

Add the following configuration to the `pyproject.toml` file as suggested in [Structuring Larger Projects](../advanced/larger_projects.md) to tell sdag where pipelines are located:

```toml title="pyproject.toml"
[tool.sdag]
dagdir = "src/container_proj/workflows"
```

Create the `workflows` directory in `src/container-proj`, an empty `__init__.py` file inside it to fully qualify `workflows` as a Python package, and a `container.py` module that will contain the pipeline code:

```sh
mkdir src/container_proj/workflows
touch src/container_proj/workflows/__init__.py
touch src/container_proj/workflows/container.py
```

The project tree should look like this:

```
container-proj
├── pyproject.toml
├── README.md
├── src
│   └── container_proj
│       ├── __init__.py
│       └── workflows
│           ├── __init__.py
│           └── container.py
└── uv.lock
```

## Defining the pipeline

Add the following pipeline to `container.py`:

```py title="container.py"
from sdag import pipeline, script


@pipeline
def container():
    create_array()


@container.task(script, container="container-proj.sif")
def create_array():
    import numpy as np

    print(np.array([1, 2, 3]))
```

Notice the import statement is conveniently placed inside the task function. sdag never runs tasks at compile time. Numpy is added to the project just to record the dependency for the image build, it is not needed to compile the pipeline. At runtime, the sdag scheduler starts the task execution inside the container, where dependencies are available.

Containers can be configured in the task decorator. The container path is specified in the `container` field. If your system supports Apptainer, set `container_runtime="apptainer"`. The `container_options` field can be used to specify a list of options applied at the container startup. `container_binds` can be used to bind additional directories to the container. sdag always binds:

- its own `.sdag` working directory.
- `SDAG_BASE_PATH` if set.
- The current working directory.
- The closest existing parent directory of each output artifact.

Here is an example of task using all these fields:

```py
@container.task(
    script,
    container="/path/to/container.sif",
    container_runtime="apptainer",
    container_options=["--nv", "--writable-tmpfs"],
    container_binds=["/mnt/path"],
)
def task_using_gpus(): ...
```

These options can be [overwritten](./override.md) by each node in the graph, set globally in the `pyproject.toml` file, or configured for groups of tasks through tags.

## Building the container and running the pipeline

Create a `container-proj.def` definition file in the main project directory:

``` title="container-proj.def"
Bootstrap: docker
From: python:3.14-slim-bookworm

%files
    pyproject.toml /opt/container-proj/pyproject.toml
    uv.lock /opt/container-proj/uv.lock
    README.md /opt/container-proj/README.md
    src /opt/container-proj/src

%post
    # Install essential tools
    apt-get update
    apt-get install -y build-essential git ca-certificates

    # Install uv
    pip install --no-cache-dir uv

    # Sync the project
    cd /opt/container-proj
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
        uv sync --frozen --no-editable --no-cache

%environment
    export PATH=/opt/container-proj/.venv/bin:$PATH
    export VIRTUAL_ENV=/opt/container-proj/.venv

%test
    # Check dependencies are installed
    python -c "import numpy, sdag"
```

and build the container via:

```sh
sudo singularity build container-proj.sif container-proj.def
```

Because sdag adds `container-proj/src` to the `PYTHONPATH`, you can freely modify the code without rebuilding the container as long as you don't introduce new dependencies.

To run the pipeline, install sdag as a [tool](https://docs.astral.sh/uv/concepts/tools/) to access its CLI:

```sh
sdag run container --local
```

!!! info
    Check out the [Slurm](../user_guide/hello_world_slurm.md) section to run this example on Slurm.

## Containerizing custom scripts

The `script` object provided by sdag is simply:

```sh title=script
#!/bin/bash
${SDAG_LAUNCHER} sdag-execute
```

The `SDAG_LAUNCHER` environment variable is set by the scheduler and carries everything you need to fire the task. If the task is containerized with Singularity, `SDAG_LAUNCHER` provides the full `singularity exec --bind /some/path ...` command required to start the application. In custom scripts, you can leverage this variable to tune the execution. For example, the following command:

```sh
${SDAG_LAUNCHER} ray start --head
```

starts a [Ray](https://docs.ray.io/en/latest/ray-overview/getting-started.html) head node using the task container if Ray is installed. Because `SDAG_LAUNCHER` is set to an empty string by default, the previous command also works for non-containerized tasks. If you need a finer control, the sdag scheduler also sets the following environment variables:

- `SDAG_CONTAINER`: Container path.
- `SDAG_CONTAINER_RUNTIME`: Container runtime (singularity or apptainer).
- `SDAG_CONTAINER_BINDS`: Bind commands.
- `SDAG_CONTAINER_OPTIONS`: User-selected container options.
