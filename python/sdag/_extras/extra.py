"""This pipeline is imported via imported_dagdirs.

Used for testing imported pipelines.
"""

from sdag import pipeline, script


@pipeline
def extra():
    """Extra pipeline."""
    does_nothing()


@extra.task(script)
def does_nothing():
    """Stage doing nothing."""
