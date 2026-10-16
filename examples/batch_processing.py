from pathlib import Path

from sdag import Artifact, each, pipeline, script


@pipeline
def process_in_batches(input_path: str, base_output: str):
    """Process dataset splits as separate jobs.

    Args:
        input_path (str): Input path.
        base_output (str): Output path.
    """
    for split in ["split1", "split2", "split3"]:
        output_path = Path(base_output) / split
        t = process_split(
            input_path=input_path, split=split, output_path=output_path
        )
        t.name = f"process-{split}"


@process_in_batches.task(script, cache="io")
def process_split(input_path: Path, split: str, output_path: Artifact[Path]):
    """Process a split.

    Args:
        input_path (Path): Input path.
        split (str): Split name.
        output_path (Artifact[Path]): Output path.
    """
    print(
        f"processing '{split}' in '{input_path}' and saving"
        f" it to {output_path}"
    )


@pipeline
def job_array():
    """Job array."""
    shards = ["a", "b", "c"]
    t = process_shards(items=each(shards))
    gather(items=t)


@job_array.task(script, njobs=2)
def process_shards(items: list[str]) -> list[str]:
    """A job in the array.

    Args:
        items (list[str]): Processed shards.

    Returns:
        list[str]: Shards.
    """
    return items


@job_array.task(script, cmd="bash")
def gather(items: list[list[str]]) -> None:
    """Gather the processed shards.

    Args:
        items (list[list[str]]): Processed shards. Here
            items = [["a", "b"], ["c"]].
    """
    print(f"collected items: {items}")
