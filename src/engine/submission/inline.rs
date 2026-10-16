// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::model::nodes::{Branch, OneOf, Task};
use crate::model::schemas::{ExecMode, Parent, ParentKind, TaskOutput};
use crate::settings::Cfg;
use crate::store::state;
use serde_json::Value;
use std::error::Error;
use std::path::PathBuf;
use std::{fs, io};

pub fn submit_oneof(oneof: &OneOf, target: usize, cfg: &Cfg) -> io::Result<u64> {
    let src_dir = cfg.dagdir.join(target.to_string());
    let dst_dir = cfg.dagdir.join(oneof.uid.to_string());
    state::copy_task_data(&src_dir, &dst_dir)
}

pub fn submit_save_ext_output(task: &Task, cfg: &Cfg) -> io::Result<()> {
    let path = cfg.dagdir.join(task.uid.to_string());
    let output = TaskOutput {
        output: serde_json::Value::Null,
        artifacts: task.artifacts.clone(),
    };
    state::save_task_output(&path, &output)
}

pub fn submit_branch(branch: &Branch, cfg: &Cfg) -> Result<bool, String> {
    let target = find_branch_target(&branch.parents)?; //branch.parent.uid;
    let path = cfg.dagdir.join(target.to_string());
    let output = state::read_output(&path)
        .map_err(|e| format!("Failed to read task '{target}' output - {e}"))?;
    match output.output {
        Value::Bool(true) => Ok(true),
        Value::Bool(false) => Ok(false),
        _ => {
            let msg = format!("Target {}, output is not Boolean", target);
            Err(msg)
        }
    }
}

pub fn aggregate_array_output(task: &Task, cfg: &Cfg) -> Result<(), Box<dyn Error>> {
    let base_path = cfg.dagdir.join(task.uid.to_string()).join(".shards");
    let mut shard_dirs = Vec::new();
    for entry in fs::read_dir(&base_path)? {
        let path = entry?.path();
        if path.is_dir() {
            shard_dirs.push(path);
        }
    }
    shard_dirs.sort();
    let output = match task.mode {
        ExecMode::Ext => vec![Value::Null; shard_dirs.len()],
        ExecMode::Wrap => read_output_from_shards(&shard_dirs)?,
    };

    let task_output = TaskOutput {
        output: Value::Array(output),
        artifacts: task.artifacts.clone(),
    };
    let path = cfg.dagdir.join(task.uid.to_string());
    state::save_task_output(&path, &task_output).map_err(|e| e.into())
}

fn find_branch_target(parents: &[Parent]) -> Result<usize, String> {
    for parent in parents {
        if let ParentKind::Output { .. } = parent.kind {
            return Ok(parent.uid);
        }
    }

    Err("Failed to identify the target task".into())
}

fn read_output_from_shards(shard_dirs: &[PathBuf]) -> Result<Vec<Value>, String> {
    let mut v = Vec::new();
    for path in shard_dirs {
        let task_output = state::read_output(path).map_err(|e| {
            format!(
                "Failed to read shard from path {} - {e}",
                path.to_string_lossy()
            )
        })?;
        v.push(task_output.output);
    }
    Ok(v)
}
