# Control Flow

## Branches

The pipeline structure can be dynamically altered based on the output of other tasks. Add the following pipeline to a new module
in the main project directory:

```py title="control_flow.py"
from sdag import Elif, Else, If, pipeline, script


@pipeline
def control_flow():
    with If(condition1()):
        option1()
    with Elif(condition2()):
        option2()
    with Else():
        option3()


@control_flow.task(script)
def condition1() -> bool:
    return False


@control_flow.task(script)
def condition2() -> bool:
    return True


@control_flow.task(script)
def option1():
    print("Option 1 selected")


@control_flow.task(script)
def option2():
    print("Option 2 selected")


@control_flow.task(script)
def option3():
    print("Option 3 selected")
```


`condition1` and `condition2` are tasks that **must** return a Boolean value. Run:

```sh
sdag run control_flow --local
```

to execute the example. The expected flow is:

1. `condition1` is executed and returns `False`.
2. Because the output is `False`, `option1` is skipped and `condition2` is evaluated.
3. The output of `condition2` is `True`, so `option2` is executed while `option3` is skipped.


## OneOf

One might expect the following snippet to work as expected:

```py
@pipeline
def dag():
    with If(condition1()):
        t = option1()
    with Else():
        t = option2()
    final_task(t)
```

Unfortunately, it's not! `t` in the example will always refer to `option2`. The `oneof` node is inspired by Kubeflow and it can be used to reference tasks running on separate branches. Add the following snippet to the same `control_flow.py` module:

```py title="control_flow.py"
from sdag import oneof


@pipeline
def oneof_example():
    with If(condition()):
        t1 = first_alternative()
    with Else():
        t2 = second_alternative()
    t = oneof(t1, t2)
    final_task(t)


@oneof_example.task(script)
def condition() -> bool:
    return False


@oneof_example.task(script)
def first_alternative():
    print("alternative 1 selected")


@oneof_example.task(script)
def second_alternative():
    print("alternative 2 selected")


@oneof_example.task(script)
def final_task():
    print("final task")
```

Here, `final_task` will only run if at least one between `first_alternative` and `second_alternative` executes successfully. You can run the example through:

```sh
sdag run oneof_example --local
```

You can also use `oneof` when multiple concurrent tasks are executed. It will become the first task of the pool that completes the execution without errors.

```py
@pipeline
def dag():
    t_fail = will_fail()
    t_slow = slow_task()
    t_fast = fast_task()

    # Likely equal to t_fast
    first_to_complete = oneof(t_fail, t_slow, t_fast)
```

!!! info
    Check out the [Slurm](./hello_world_slurm.md) section to run this example on Slurm.
