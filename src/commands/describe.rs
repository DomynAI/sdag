// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::submission::caching;
use crate::model::nodes::{Node, Task};
use crate::model::schemas::{Artifact, ParentKind};
use crate::settings::{self, Cfg};
use crate::store::state;
use crate::store::workdirs::DirPaths;
use serde_json::{self, Value};
use std::collections::HashMap;
use std::path::PathBuf;

use crate::engine::summary::get_styled_table;
use tabled::{
    Tabled,
    settings::{Alignment, object::Segment},
};

#[derive(Tabled)]
struct TaskDescription<'a> {
    uid: usize,
    /// Task status.
    name: &'a str,
    /// Task pipeline.
    pipeline: &'a str,
    /// Cached
    cached: bool,
    /// Artifacts
    artifacts: String,
    /// Input kwargs
    kwargs: String,
}

pub fn describe_pipeline(pipeline_path: &str) {
    let pipeline_path = PathBuf::from(pipeline_path);
    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    let dag = state::read_dag(&pipeline_path).expect("Failed to read DAG");
    let paths = DirPaths::new(&homedir, &dag.meta.pipeline_name, &dag.meta.hash);
    let mut cfg = Cfg::default();
    cfg.dagdir = paths.dagdir;
    cfg.cachedir = paths.cachedir;
    cfg.local_cachedir = paths.local_cachedir;
    cfg.dag_code_hash = dag.meta.code_hash.to_string();

    let mut descriptions = vec![];
    for node in &dag.nodes {
        if let Node::Task(task) = node {
            let description = get_description(&task, &cfg);
            descriptions.push(description);
        }
    }
    let mut table = get_styled_table(descriptions);
    table.modify(Segment::all(), Alignment::center_vertical());
    println!("{table}");
}

fn get_description<'a>(task: &'a Task, cfg: &Cfg) -> TaskDescription<'a> {
    let input_kwargs = state::get_static_input(&task.kwargs, &task.parents);
    let kwargs =
        serde_json::to_string_pretty(&input_kwargs).unwrap_or("[failed to parse]".to_string());
    let cached = check_caching(&task, &cfg, &input_kwargs);
    let artifacts = get_artifacts(&task.artifacts);

    TaskDescription {
        uid: task.uid,
        name: &task.name,
        pipeline: &task.pipeline_name,
        cached,
        artifacts,
        kwargs,
    }
}

fn check_caching(task: &Task, cfg: &Cfg, input: &HashMap<String, Value>) -> bool {
    if !task.cache.is_enabled() {
        return false;
    }

    if is_task_dynamic(task) {
        log::warn!("Cache of dynamic task '{}' cannot be checked", task.uid);
        return false;
    }

    if let Some(path) = caching::validate_cache(input, task, cfg) {
        log::debug!("Task {} matches '{}'", task.uid, path.to_string_lossy());
        return true;
    }

    false
}

fn is_task_dynamic(task: &Task) -> bool {
    task.parents
        .iter()
        .any(|p| matches!(p.kind, ParentKind::Output { .. }))
}

fn get_artifacts(artifacts: &[Artifact]) -> String {
    artifacts
        .iter()
        .map(|a| a.name.to_string())
        .collect::<Vec<_>>()
        .join(", ")
}
