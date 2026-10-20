# Handling Multiple Tasks

Copy the following pipeline into a new module in the main project directory:

```py title="multiple_tasks.py"
from sdag import pipeline, script


@pipeline
def many_tasks():
    say_hello()
    say_hello()
    say_hello()


@many_tasks.task(script)
def say_hello():
    print("hello world!")
```

You can view the graph of this pipeline in the terminal via `sdag view`:

```sh
sdag view many_tasks
```

which should print something like:

```
                    ╭──────╮
                    │_root_│
                    ╰──────╯
                        │
                        │
     ┌──────────────────└──────────────────┐
     ▼                  ▼                  ▼
┌─────────┐        ┌─────────┐        ┌─────────┐
│say_hello│        │say_hello│        │say_hello│
└─────────┘        └─────────┘        └─────────┘
```

As these tasks do not depend on each other, they are scheduled at the same time. You can confirm this by running the pipeline:

```sh
sdag run many_tasks --local
```

You can use positional arguments to signal graph edges. Let's add a second pipeline to the same `many_tasks.py` module:

```py title="multiple_tasks.py"
import asyncio

@pipeline
def dependent_tasks():
    t1 = first()
    t2 = first()
    second(t1, t2)


@dependent_tasks.task(script)
def first():
    print("I run first!")


@dependent_tasks.task(script)
async def second():
    await asyncio.sleep(1)
    print("I run second!")
```

Notice async tasks are supported: in such cases sdag will start the event loop for you. `sdag view dependent_tasks` will now print:

```
       ╭──────╮
       │_root_│
       ╰──────╯
           │
           │
   ┌───────└──────┐
   ▼              ▼
┌─────┐        ┌─────┐
│first│        │first│
└─────┘        └─────┘
   │              │
   │              │
   └───────┌──────┘
           ▼
       ┌──────┐
       │second│
       └──────┘
```

Which means that `second` will only run if both `first` tasks successfully complete. This example can be run via:

```sh
sdag run dependent_tasks --local
```

!!! info
    Check out the [Slurm](./hello_world_slurm.md) section to run this example on Slurm.
