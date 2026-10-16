# Handling Multiple Runs of the Same Pipeline

One does not often deals with multiple concurrent runs of the same pipeline. In fact, calling the same pipeline multiple times with different arguments typically involves writing a bash script that must be maintained, which is exactly what sdag tries to avoid. A better approach would be to define an outer pipeline that calls the inner pipelines multiple times.

Nevertheless, it's still possible to run, kill, and restart multiple runs of the same pipeline. The maximum number of pipelines that can be handled at the same time can be specified by the `max-concurrent-runs` configuration in the `pyproject.toml` Once that number is reached, the oldest runs are deleted to make room for the new ones. When compiled, each JSON file is assigned a unique hash that is then used to univocally reference that run. The same hash is also periodically printed in the scheduler logs:

```
2026-09-21T19:06:35Z INFO  core::engine::summary] Pipeline 'hello_world' with hash '121a42773f77941c' - Summary:
```

You can use `sdag list <pipeline-name>` to view hashes and timestamps of all the available runs. `sdag restart`, `sdag retry`, and `sdag kill` accept an optional `--hash` argument to restart or kill specific runs. By default, the target becomes the most recent one.