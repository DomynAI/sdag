# Batch Processing and Job Arrays

## Batch Processing

Batch processing is one of the most common patterns one faces when dealing with data. There is typically a big dataset to be processed made of several splits (subfolders). These splits can be often processed independently as separate tasks, which helps reducing size and wall time of the job. Pipelines can be set up in this way when processing data in batches with sdag:

```py
from pathlib import Path

from sdag import Artifact, pipeline, script


@pipeline
def process_in_batches(input_path: str, base_output: str):
    for split in ["split1", "split2", "split3"]:
        output_path = Path(base_output) / split
        t = process_split(
            input_path=input_path, split=split, output_path=output_path
        )
        t.name = f"process-{split}"


@process_in_batches.task(script, cache="io")
def process_split(input_path: Path, split: str, output_path: Artifact[Path]):
    print(
        f"processing '{split}' in '{input_path}' and saving"
        f" it to {output_path}"
    )
```

In this way, splits are processed independently from each other. These tasks get custom names for easier traceability in the logs and separate caches. If some splits fail, you can use `sdag retry` to restart only the failed ones. If new splits are added to the dataset, the other ones got cached so they won't be processed again during subsequent runs. You can run this example through:

```sh
sdag run process_in_batches --local --input-path=input --base-output=output
```

## Job Arrays

The approach shown in the previous section is very flexible. However, there is a drawbrack. If the number of splits is too high, many tiny jobs will be created, thus putting significant pressure on the Slurm queuing system. For this reason, only on Slurm it is possible to leverage `each` to orchestrate batch processing with job arrays:

```py
from sdag import each, pipeline, script


@pipeline
def job_array():
    shards = ["a", "b", "c"]
    t = process_shards(items=each(shards))
    gather(items=t)


@job_array.task(script, njobs=2)
def process_shards(items: list[str]) -> list[str]:
    return items


@job_array.task(script, cmd="bash")
def gather(items: list[list[str]]) -> None:
    # items = [["a", "b"], ["c"]]
    print(f"collected items: {items}")
```

`shards` here can also be the output of a task but it must always be a list. Shards are equally split into an array of two jobs (the number of jobs is automatically decreased if the number of items is lower than that). If retries are enabled, Only failed jobs are resubmitted. Other than that, an array mostly behaves like a single task and its cache is also unique. This is in contrast with the previous example, where each split had its own cache. This example only runs on Slurm:

```sh
sdag run job_array
```

!!! warning
    Arrays are mostly treated as single jobs by Slurm and they must be submitted all at once. Therefore, sdag will submit the whole array and limit the number of running jobs to the value selected by the user. This means the total number of running jobs could be higher than the maximum one if other tasks are running. This is usually not an issue as the number of array jobs typically dominates the total number of jobs in a pipeline.