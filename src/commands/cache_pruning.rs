// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::submission::caching;
use crate::model::nodes::Task;
use crate::model::schemas::Scope;
use crate::settings;
use crate::settings::Cfg;
use crate::store::state;
use crate::store::workdirs::{self, DirPaths};
use log;
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::Path;

pub fn prune_cache(tasks: Vec<String>, pipeline_name: Option<&str>) {
    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    if pipeline_name.is_none() && tasks.is_empty() {
        log::error!("No pipelines or tasks specified");
        return;
    }
    if let Some(name) = pipeline_name {
        let tasks = parse_tasks(&tasks);
        delete_pipeline_cache(&tasks, name, &homedir);
    } else {
        delete_global_task_cache(&tasks, &homedir);
    }
}

fn parse_tasks(tasks_json: &[String]) -> Vec<Task> {
    let mut tasks = Vec::new();
    for task_str in tasks_json {
        let task: Task = match serde_json::from_str(task_str) {
            Ok(task) => task,
            Err(e) => {
                log::warn!("Failed to parse '{task_str}'\n{e}, skipping");
                continue;
            }
        };
        tasks.push(task);
    }
    tasks
}

fn delete_global_task_cache(tasks: &[String], homedir: &Path) {
    if tasks.len() == 1 && tasks[0] == "all" && !state::task_global_cache_exists(&tasks[0], homedir)
    {
        log::info!("Deleting the entire sdag cache");
        if let Err(e) = state::delete_cache_dir(homedir) {
            log::error!("Error during cache deletion: {e}");
        }
        return;
    }

    for task in tasks {
        log::info!("Deleting task '{}' global cache", task);
        if let Err(e) = state::clear_global_cache(task, homedir) {
            log::error!("Error during cache deletion: {e}");
        }
    }
}

fn delete_pipeline_cache(tasks: &[Task], pipeline_name: &str, homedir: &Path) {
    for task in tasks {
        log::info!(
            "Removing task '{}' (pipeline '{pipeline_name}') cache",
            task.name
        );
        let res = match task.scope {
            Scope::Local => state::clear_local_cache(&task.name, pipeline_name, homedir),
            Scope::Global => clear_global_cache_of_pipeline(task, pipeline_name, homedir),
        };
        if let Err(e) = res {
            log::error!("Error during cache deletion: {e}");
        }
    }
}

fn clear_global_cache_of_pipeline(
    task: &Task,
    pipeline_name: &str,
    homedir: &Path,
) -> io::Result<()> {
    if !task.cache.is_enabled() {
        return Ok(());
    }
    if task.is_dynamic() {
        log::warn!("Cache of dynamic task '{}' cannot be checked", task.uid);
        return Ok(());
    }

    let cfg = get_mock_cfg(homedir, pipeline_name);
    let input = state::get_static_input(&task.kwargs, &task.parents);
    delete_matching_cache(task, &cfg, &input)
}

fn get_mock_cfg(homedir: &Path, pipeline_name: &str) -> Cfg {
    let paths = DirPaths::new(homedir, pipeline_name, "");
    Cfg {
        dagdir: paths.dagdir,
        cachedir: paths.cachedir,
        local_cachedir: paths.local_cachedir,
        ..Default::default()
    }
}

fn delete_matching_cache(task: &Task, cfg: &Cfg, input: &HashMap<String, Value>) -> io::Result<()> {
    let cache_path = workdirs::get_task_cache_path(task, cfg);
    for entry in fs::read_dir(cache_path)? {
        let path = entry?.path();
        if !path.is_dir() {
            continue;
        }
        if caching::compare_cache_dir(&path, input, task, &cfg.dag_code_hash) {
            log::info!("Deleting matching cache at {}", path.to_string_lossy());
            if let Err(e) = state::delete_matching_cache(&path) {
                log::error!("Error during cache deletion: {e}");
            }
        }
    }
    Ok(())
}
