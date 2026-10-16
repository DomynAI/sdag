from sdag import pipeline, script


@pipeline
def failure():
    """Pipeline that will always fail."""
    t = failed_task()
    will_never_run(t)


@failure.task(script, retries=2)
def failed_task():
    """Failed task."""
    msg = "Failing..."
    raise ValueError(msg)


@failure.task(script)
def will_never_run():
    """This will never run."""
    print("You will never see this message")
