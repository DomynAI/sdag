import asyncio

from sdag import pipeline, script


@pipeline
def many_tasks():
    """Many tasks executed in parallel."""
    say_hello()
    say_hello()
    say_hello()


@many_tasks.task(script)
def say_hello():
    """Say hello!"""
    print("hello world!")


@pipeline
def dependent_tasks():
    """First tasks run first."""
    t1 = first()
    t2 = first()
    second(t1, t2)


@dependent_tasks.task(script)
def first():
    """First task."""
    print("I run first!")


@dependent_tasks.task(script)
async def second():
    """Second task, async is supported."""
    await asyncio.sleep(1)
    print("I run second!")
