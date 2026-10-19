from sdag import pipeline, script


@pipeline
def cache_lock():
    """Simple example to test cache locking.

    This pipeline shows how cache locking works.
    Only two tasks will run here, one with a=1
    and the other a=2. The other ones will wait
    and then get cached.
    """
    lock_cache(a=1)
    lock_cache(a=1)
    lock_cache(a=1)
    lock_cache(a=1)
    lock_cache(a=2)
    lock_cache(a=2)


@cache_lock.task(script, cache="io", cache_size=2)
def lock_cache(a: int) -> None:
    """Wait without doing much.

    Args:
        a (int): input value.
    """
    import time

    print(a)
    time.sleep(7)
