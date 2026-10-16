# Overview

Welcome to the sdag documentation! sdag is a Python library for defining workflows that can run locally or across HPC clusters. It offers features like dynamic branching, caching, failure recovery, artifact tracking, and more.

## Why sdag

Historically, managing interdependent jobs on Slurm clusters has been tough. While in the Cloud tools like [AirFlow](https://airflow.apache.org/) and [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/) are available, their deployment in air-gapped HPC environments is usually very challenging as internet connection and tools like Docker or Kubernetes are not available. Therefore, teams often resort to relying on custom Bash scripts and makefiles, which quickly become large and hard to maintain as the project complexity grows.

sdag tries to fill this gap by providing a typed, code-first API. Its design loosely follows the one of Kubeflow but it's way lighter so it can easily run on HPC infra. Tasks are compiled down to a graph and executed by a Rust-based scheduler. This design choice decouples compilation from execution and provides a unique entry point for all tasks.