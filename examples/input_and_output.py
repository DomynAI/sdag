from pathlib import Path

from sdag import pipeline, script


@pipeline
def output_use():
    """Pipeline with tasks using input and output values."""
    t = return_output()
    take_input(world=t)


@output_use.task(script)
def return_output():
    """Task returning an output."""
    return "world"


@output_use.task(script)
def take_input(world: str):
    """Task taking an input."""
    print(f"Hello, {world}!")


@pipeline
def dag_with_input(input_path):
    """Pipeline with input value."""
    use_input_path(input_path=input_path)


@dag_with_input.task(script)
def use_input_path(input_path: Path):
    """Task casting to Path."""
    print(f"Input path: '{input_path}'; type: {type(input_path)}")
