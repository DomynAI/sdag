from sdag import Script, pipeline, script


@pipeline
def external_dag():
    """DAG with external task."""
    external_task(input_data="world")


@external_dag.task(Script("echo $INPUT_DATA"), mode="ext")
def external_task(input_data: str):
    """External task."""


@pipeline
def local_dag():
    """DAG with local task."""
    local_task()


@local_dag.task(script, cmd="bash")
def local_task():
    """Local DAG."""
    print("I run locally!")
