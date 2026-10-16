<div align="center">

<picture>
  <source srcset="docs/assets/sdag-logo-white.svg" media="(prefers-color-scheme: dark)">
  <source srcset="docs/assets/sdag-logo-black.svg" media="(prefers-color-scheme: light)">
  <img src="docs/assets/sdag-logo-black.svg" alt="sdag" height="100">
</picture>

DAGs for Slurm.

[![License - Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-blue)](https://igeniusai.github.io/sdag/)
[![CI](https://github.com/igeniusai/sdag/actions/workflows/ci.yaml/badge.svg)](https://github.com/igeniusai/sdag/actions/workflows/ci.yaml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14%20%7C%203.15-brightgreen)](https://github.com/igeniusai/sdag/blob/main/pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://github.com/microsoft/pyright)

| | |
|---|---|
| ✅ **DAG management:** Organize your workflows in clean DAGs | ✅ **Caching:** Completed jobs won't run again |
| ✅ **Code first API:** Familiar Python API equipped with a Rust scheduler | ✅ **Failure recovery:** Handle errors and retries |
| ✅ **Visualization:** View workflows and details directly in the terminal | ✅ **Control flow:** Adapt your pipelines dynamically |
| ✅ **CLI:** Manage all pipelines from a unique entrypoint | ✅ **Local or Slurm:** Run on your laptop or scale across a Slurm cluster |

</div>

## Why sdag

Historically, managing interdependent jobs on Slurm clusters has been tough. While in the Cloud tools like [AirFlow](https://airflow.apache.org/) and [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/) are available, their deployment in air-gapped HPC environments is usually very challenging as internet connection and tools like Docker or Kubernetes are not available. Therefore, teams often resort to relying on custom Bash scripts and makefiles, which quickly become large and hard to maintain as the project complexity grows.

sdag tries to fill this gap by providing a typed, code-first API. Its design loosely follows the one of Kubeflow, so it will feel natural if you already worked with it. However, it's way lighter! So it can easily run on HPC infra. Tasks are compiled down to a graph and executed by a Rust-based scheduler.

## Installation

sdag is not available on pypi yet (it's coming soon!). If you manage dependencies with [uv](https://docs.astral.sh/uv/), you can directly install sdag from GitHub:

```sh
uv add "sdag @ git+https://github.com/igeniusai/sdag"
```

You can also install sdag as a tool to gain global access to it:

```sh
uv tool install "sdag @ git+https://github.com/igeniusai/sdag"
```

To install sdag with pip, first clone the GitHub repository:

```sh
git clone https://github.com/igeniusai/sdag.git
```

and then install sdag:

```sh
pip install path/to/sdag
```

If you face issues in the process, you likely have to install [Rust](https://rust-lang.org/tools/install/) or update it to a more recent version via:

```sh
rustup update
```

## Getting started

Paste the following code into a module in the main project directory:

```py
from sdag import pipeline, script


@pipeline
def hello_world() -> None:
    say_hello(name="sdag")


@hello_world.task(script)
def say_hello(name: str) -> None:
    print(f"hello from {name}")
```

To run the `hello_world` pipeline locally, execute:

```sh
sdag run hello_world --local
```

Check out the official [documentation](https://igeniusai.github.io/sdag/) for a detailed description of the features offered by sdag.

## Building from source and running tests

After cloning the repository, run:

```sh
uv sync --all-groups
```

to build the environment and:

```sh
source .venv/bin/activate
```

to activate it. Execute:

```sh
pytest
```

to run the the quick Python test suite and:

```sh
pytest --runslow
```

to run every Python test. Rust tests can be executed through:

```sh
cargo test
```

## Building the docs

Execute:

```sh
mkdocs serve
````

to build and serve the documentation. The server will be running at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
