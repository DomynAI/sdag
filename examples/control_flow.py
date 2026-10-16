from sdag import Elif, Else, If, oneof, pipeline, script


@pipeline
def control_flow():
    """DAG with if/elif/else."""
    with If(condition1()):
        option1()
    with Elif(condition2()):
        option2()
    with Else():
        option3()


@control_flow.task(script)
def condition1() -> bool:
    """Evaluates to False."""
    return False


@control_flow.task(script)
def condition2() -> bool:
    """Evaluates to True."""
    return True


@control_flow.task(script)
def option1():
    """Option 1."""
    print("Option 1 selected")


@control_flow.task(script)
def option2():
    """Option 2."""
    print("Option 2 selected")


@control_flow.task(script)
def option3():
    """Option 3."""
    print("Option 3 selected")


@pipeline
def oneof_example():
    """OneOf with if/else."""
    with If(condition()):
        t1 = first_alternative()
    with Else():
        t2 = second_alternative()
    t = oneof(t1, t2)
    final_task(t)


@oneof_example.task(script)
def condition() -> bool:
    """Evaluates to False."""
    return False


@oneof_example.task(script)
def first_alternative():
    """First alternative."""
    print("alternative 1 selected")


@oneof_example.task(script)
def second_alternative():
    """Second alternative."""
    print("alternative 2 selected")


@oneof_example.task(script)
def final_task():
    """Final task after the oneof."""
    print("final task")
