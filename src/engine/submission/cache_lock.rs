// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::Ctx;
use crate::engine::submission::caching;
use crate::model::nodes::Task;
use crate::model::schemas::Cache;
use crate::settings::Cfg;
use crate::store::{state, workdirs};

pub fn unlock_cacheable_task(task: &Task, ctx: &mut Ctx, cfg: &Cfg) {
    let path = workdirs::get_task_cache_path(task, cfg);
    if let Some(running) = ctx.running_cacheable.get_mut(&path) {
        running.retain(|x| *x != task.uid)
    }
}

pub fn lock_cacheable_task(task: &Task, ctx: &mut Ctx, cfg: &Cfg) {
    let path = workdirs::get_task_cache_path(task, cfg);
    let uids = ctx.running_cacheable.entry(path).or_default();
    if !uids.contains(&task.uid) {
        uids.push(task.uid);
    }
}

pub fn find_running_duplicate(task: &Task, ctx: &Ctx, cfg: &Cfg) -> Option<usize> {
    if !cfg.cache_lock || !task.cache.is_enabled() {
        return None;
    }
    let path = workdirs::get_task_cache_path(task, cfg);
    let uids = ctx.running_cacheable.get(&path)?;
    if let Cache::Output = task.cache {
        return uids.first().copied();
    }

    let input = match state::read_input_from_parents(task, &cfg.dagdir) {
        Ok(input) => input,
        Err(e) => {
            log::warn!(
                "Task {}: Failed to read input for cache lock - {e}",
                task.uid
            );
            return None;
        }
    };
    uids.iter().copied().find(
        |&uid| match state::read_input(&cfg.dagdir.join(uid.to_string())) {
            Ok(running) => caching::inputs_match(&input, running, &task.cache_ignore),
            Err(e) => {
                log::debug!("Task {uid}: Failed to read input for cache lock - {e}");
                false
            }
        },
    )
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::*;
    use crate::model::nodes::Node;
    use crate::model::schemas::{Cache, Kwarg};
    use crate::store::workdirs::{FileNames, get_task_cache_path};
    use serde_json::json;
    use std::env;
    use std::path::PathBuf;
    use uuid::Uuid;

    fn get_tmp_dir() -> PathBuf {
        let path = env::temp_dir().join(Uuid::new_v4().to_string());
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn test_lock_cacheable_task() {
        let task = Task {
            uid: 0,
            cache: Cache::Io,
            ..Default::default()
        };
        let nodes = vec![Node::Task(task.clone())];
        let cfg = Cfg {
            dagdir: "/".into(),
            ..Default::default()
        };
        let mut ctx = Ctx::new(&nodes).unwrap();
        let path = get_task_cache_path(&task, &cfg);
        lock_cacheable_task(&task, &mut ctx, &cfg);
        assert!(
            ctx.running_cacheable
                .get(&path)
                .is_some_and(|x| *x == vec![0])
        );
    }

    #[test]
    fn test_unlock_cacheable_task() {
        let task = Task {
            uid: 0,
            cache: Cache::Io,
            ..Default::default()
        };
        let nodes = vec![Node::Task(task.clone())];
        let cfg = Cfg {
            dagdir: "/".into(),
            ..Default::default()
        };
        let mut ctx = Ctx::new(&nodes).unwrap();
        let path = get_task_cache_path(&task, &cfg);
        ctx.running_cacheable.insert(path.clone(), vec![0]);
        unlock_cacheable_task(&task, &mut ctx, &cfg);
        assert!(
            ctx.running_cacheable
                .get(&path)
                .is_some_and(|x| x.is_empty())
        );
    }

    #[test]
    fn test_find_running_duplicate() {
        let task0 = Task {
            uid: 0,
            name: "task".into(),
            cache: Cache::Io,
            kwargs: vec![Kwarg {
                key: "a".into(),
                value: json![1],
            }],
            ..Default::default()
        };
        let task1 = Task {
            uid: 1,
            name: "task".into(),
            cache: Cache::Io,
            kwargs: vec![Kwarg {
                key: "a".into(),
                value: json![1],
            }],
            ..Default::default()
        };
        let nodes = vec![Node::Task(task0.clone()), Node::Task(task1.clone())];
        let tmp_dir = get_tmp_dir();
        let task0_dir = tmp_dir.join("0");
        fs::create_dir_all(&task0_dir).unwrap();
        fs::write(task0_dir.join(FileNames::Input.as_str()), r#"{"a": 1}"#).unwrap();

        let cfg = Cfg {
            dagdir: tmp_dir.clone(),
            cache_lock: true,
            ..Default::default()
        };
        let mut ctx = Ctx::new(&nodes).unwrap();
        let path = get_task_cache_path(&task0, &cfg);
        ctx.running_cacheable.insert(path.clone(), vec![0]);
        let output = find_running_duplicate(&task1, &ctx, &cfg);
        assert!(output.is_some_and(|x| x == 0));
    }

    #[test]
    fn test_find_running_duplicate_no_match() {
        let task0 = Task {
            uid: 0,
            name: "task".into(),
            cache: Cache::Io,
            kwargs: vec![Kwarg {
                key: "a".into(),
                value: json![1],
            }],
            ..Default::default()
        };
        let task1 = Task {
            uid: 1,
            name: "task".into(),
            cache: Cache::Io,
            kwargs: vec![Kwarg {
                // This is different
                key: "a".into(),
                value: json![2],
            }],
            ..Default::default()
        };
        let nodes = vec![Node::Task(task0.clone()), Node::Task(task1.clone())];
        let tmp_dir = get_tmp_dir();
        let task0_dir = tmp_dir.join("0");
        fs::create_dir_all(&task0_dir).unwrap();
        fs::write(task0_dir.join(FileNames::Input.as_str()), r#"{"a": 1}"#).unwrap();

        let cfg = Cfg {
            dagdir: tmp_dir.clone(),
            cache_lock: true,
            ..Default::default()
        };
        let mut ctx = Ctx::new(&nodes).unwrap();
        let path = get_task_cache_path(&task0, &cfg);
        ctx.running_cacheable.insert(path.clone(), vec![0]);
        let output = find_running_duplicate(&task1, &ctx, &cfg);
        assert!(output.is_none());
    }

    #[test]
    fn test_find_running_duplicate_output_match() {
        let task0 = Task {
            uid: 0,
            name: "task".into(),
            cache: Cache::Output,
            kwargs: vec![Kwarg {
                key: "a".into(),
                value: json![1],
            }],
            ..Default::default()
        };
        let task1 = Task {
            uid: 1,
            name: "task".into(),
            cache: Cache::Output,
            kwargs: vec![Kwarg {
                // This is different
                key: "a".into(),
                value: json![2],
            }],
            ..Default::default()
        };
        let nodes = vec![Node::Task(task0.clone()), Node::Task(task1.clone())];
        let tmp_dir = get_tmp_dir();
        let task0_dir = tmp_dir.join("0");
        fs::create_dir_all(&task0_dir).unwrap();
        fs::write(task0_dir.join(FileNames::Input.as_str()), r#"{"a": 1}"#).unwrap();

        let cfg = Cfg {
            dagdir: tmp_dir.clone(),
            cache_lock: true,
            ..Default::default()
        };
        let mut ctx = Ctx::new(&nodes).unwrap();
        let path = get_task_cache_path(&task0, &cfg);
        ctx.running_cacheable.insert(path.clone(), vec![0]);
        let output = find_running_duplicate(&task1, &ctx, &cfg);
        assert!(output.is_some_and(|x| x == 0));
    }
}
