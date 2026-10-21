# SPDX-FileCopyrightText: 2026 Domyn
# SPDX-License-Identifier: Apache-2.0

from sdag import Artifact, Else, If, oneof, pipeline, script


@pipeline
def complex_oneof():
    """Very complex pipeline.

    Used to test branches and oneof in non-trivial
    scenarios. The expected workflow is:

    - choice evaluates to False, the If branch is skipped
    - choice evaluates to False, the If branch inside the Else
        branch is skipped as well
    - t2else is evaluated
    - t2 (oneof) becomes t2else
    - oneof12 becomes t2
    - read_oneof_artifacts reads the artifact from oneof12
    """
    with If(choice()):
        with If(choice()):
            t1if = taskif(a=1, b="a/path")
        with Else():
            t1else = taskelse(a=2, b="a/path")
        t1 = oneof(t1if, t1else, name="t1")

    with Else():
        with If(choice()):
            t2if = taskif(a=1, b="a/path")
        with Else():
            t2else = taskelse(a=2, b="a/path")
        t2 = oneof(t2if, t2else, name="t2")

    oneof12 = oneof(t1, t2, name="t3")
    read_oneof_artifact(t=oneof12.artifacts["b"])


@complex_oneof.task(script)
def choice():
    return False


@complex_oneof.task(script)
def taskif(a: int, b: Artifact): ...


@complex_oneof.task(script)
def taskelse(a: int, b: Artifact): ...


@complex_oneof.task(script)
def read_oneof_artifact(t: str): ...
