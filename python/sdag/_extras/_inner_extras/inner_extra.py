"""This pipeline is imported via imported_dagdirs.

Used for testing nested imported pipelines.
"""

from sdag import pipeline, script


@pipeline
def inner_extra():
    """Extra pipeline."""
    does_nothing()


@inner_extra.task(script)
def does_nothing():
    """Stage doing nothing."""
