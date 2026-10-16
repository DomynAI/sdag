from sdag import pipeline, script


@pipeline
def hello_world():
    """Hello world in sdag."""
    say_hello(name="sdag")


@hello_world.task(script)
def say_hello(name: str):
    """Say hello!"""
    print(f"hello from {name}")
