// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::model::nodes::Task;
use crate::model::schemas::{Artifact, Cache};
use crate::settings::Cfg;
use crate::store::{state, workdirs};
use log;
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use uuid::Uuid;

pub fn submit_validate_cache(task: &Task, cfg: &Cfg) -> bool {
    if !task.cache.is_enabled() {
        return false;
    }

    log::debug!("Task {}: Validating cache", task.uid);
    let Ok(input) = state::read_input_from_parents(task, &cfg.dagdir) else {
        log::error!("Task {}: Failed to read input data", task.uid);
        return false;
    };

    match validate_cache(&input, task, cfg) {
        None => false,
        Some(path) => {
            let dst_path = cfg.dagdir.join(task.uid.to_string());
            if let Err(e) = state::copy_task_data(&path, &dst_path) {
                log::error!("Task {}: Failed to save cached data - {e}", task.uid);
                return false;
            }
            if let Err(e) = state::touch_cached_task_dir(&path) {
                log::error!("Task {}: Failed to touch cache - {e}", task.uid);
            }
            true
        }
    }
}

pub fn submit_save_cache(task: &Task, cfg: &Cfg) -> io::Result<u64> {
    let src_path = cfg.dagdir.join(task.uid.to_string());
    let base_dst_path = workdirs::get_task_cache_path(task, cfg);
    find_and_save_cache(&src_path, &base_dst_path, task.cache_size)
}

pub fn validate_cache(input: &HashMap<String, Value>, task: &Task, cfg: &Cfg) -> Option<PathBuf> {
    match compare_task_with_cache(&input, task, cfg) {
        Err(e) => {
            log::info!("Task {}: Cache validation failed - {e}", task.uid);
            None
        }
        Ok(None) => {
            log::info!("Task {}: Cached data doesn't match the input", task.uid);
            None
        }
        Ok(Some(path)) => {
            log::info!("Task {}: Cached data matches input", task.uid);
            Some(path)
        }
    }
}

fn compare_task_with_cache(
    input: &HashMap<String, Value>,
    task: &Task,
    cfg: &Cfg,
) -> io::Result<Option<PathBuf>> {
    let cache_path = workdirs::get_task_cache_path(task, cfg);
    for entry in fs::read_dir(cache_path)? {
        let path = entry?.path();
        if !path.is_dir() {
            continue;
        }
        if compare_cache_dir(&path, input, task, &cfg.dag_code_hash) {
            return Ok(Some(path));
        }
    }
    Ok(None)
}

fn compare_cache_dir(
    path: &Path,
    input: &HashMap<String, Value>,
    task: &Task,
    dag_code_hash: &str,
) -> bool {
    match task.cache {
        Cache::None => false,
        Cache::Output => {
            if !is_output_readable(task.uid, &path) {
                return false;
            }
            check_artifacts_exist(task.uid, &task.artifacts)
        }
        Cache::Io => {
            if !is_output_readable(task.uid, &path) {
                return false;
            }
            if !compare_input(task, input, path) {
                return false;
            }
            check_artifacts_exist(task.uid, &task.artifacts)
        }
        Cache::Task => {
            if !is_output_readable(task.uid, &path) {
                return false;
            }
            if !compare_input(task, input, path) {
                return false;
            }
            if !check_artifacts_exist(task.uid, &task.artifacts) {
                return false;
            }
            compare_task_code_hash(task.uid, path, &task.code_hash)
        }
        Cache::Project => {
            if !is_output_readable(task.uid, &path) {
                return false;
            }
            if !compare_input(task, input, path) {
                return false;
            }
            if !check_artifacts_exist(task.uid, &task.artifacts) {
                return false;
            }
            compare_dag_code_hash(task.uid, path, &dag_code_hash)
        }
    }
}

fn is_output_readable(uid: usize, path: &Path) -> bool {
    match state::read_output(path) {
        Err(e) => {
            let path_str = path.to_string_lossy();
            log::warn!("Task {uid}: Cached output '{path_str}' is not readable - {e}");
            false
        }
        Ok(_) => true,
    }
}

fn compare_input(task: &Task, input: &HashMap<String, Value>, path: &Path) -> bool {
    let path_str = path.to_string_lossy();
    let Ok(mut cached_input) = state::read_input(path) else {
        log::warn!(
            "Task {}: Failed to read input from path {path_str}",
            task.uid
        );
        return false;
    };

    replace_cache_ignored_value(&mut cached_input, input, &task.cache_ignore);
    if *input != cached_input {
        log::info!("Cache {path_str} invalidated as input doesn't match the cached one.");
        log::debug!("input:\n{input:?};\ncached input:\n{cached_input:?}");
        return false;
    }
    true
}

fn check_artifacts_exist(uid: usize, artifacts: &[Artifact]) -> bool {
    for artifact in artifacts {
        if !artifact.path.exists() {
            let path_str = artifact.path.to_string_lossy();
            log::info!("Task {uid}: Artifact {path_str} does not exist",);
            return false;
        }
    }
    true
}

fn compare_task_code_hash(uid: usize, path: &Path, code_hash: &str) -> bool {
    let Ok(meta) = state::read_meta(path) else {
        let path_str = path.to_string_lossy();
        log::warn!("Task {uid}: Failed to read metadata from path {path_str}");
        return false;
    };
    if meta.code_hash != code_hash {
        log::debug!(
            "Task {uid}: Hash '{code_hash}' doesn't match with cached '{}'",
            meta.code_hash
        );
        return false;
    }
    true
}

fn compare_dag_code_hash(uid: usize, path: &Path, dag_code_hash: &str) -> bool {
    let Ok(meta) = state::read_meta(path) else {
        let path_str = path.to_string_lossy();
        log::warn!("Task {uid}: Failed to read metadata from path {path_str}");
        return false;
    };

    if meta.dag_code_hash != dag_code_hash {
        log::debug!(
            "Task {uid}: Hash '{dag_code_hash}' doesn't match with cached '{}'",
            meta.code_hash
        );
        return false;
    }
    true
}

fn replace_cache_ignored_value(
    cached_input: &mut HashMap<String, Value>,
    input: &HashMap<String, Value>,
    cache_ignore: &[String],
) {
    for key in cache_ignore {
        if let Some(value) = input.get(key) {
            log::debug!("Inserting excluded cache value {key}");
            cached_input.insert(key.clone(), value.clone());
        }
    }
}

fn find_and_save_cache(
    src_path: &Path,
    base_dst_path: &Path,
    cache_size: usize,
) -> io::Result<u64> {
    let hash = Uuid::new_v4().to_string();
    let dst_path = base_dst_path.join(hash);
    delete_old_cache(base_dst_path, cache_size)?;
    state::copy_task_data(&src_path, &dst_path)
}

fn delete_old_cache(base_dst_path: &Path, cache_size: usize) -> io::Result<()> {
    if !base_dst_path.is_dir() {
        return Ok(());
    }

    let subfolders = workdirs::get_subfolder_creation_dates(base_dst_path)?;
    let nsubfolders = subfolders.len();
    log::debug!("Currenct cache size: '{}'", nsubfolders);

    let ndel = 1 + nsubfolders as i64 - cache_size as i64;
    if cache_size > 0 && ndel > 0 {
        log::debug!("Number of cache folders to be deleted: {}", ndel);
        for (dir, _) in &subfolders[..ndel as usize] {
            log::debug!("Removing '{}'", dir.to_string_lossy());
            fs::remove_dir_all(dir)?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::schemas::{Kwarg, TaskMeta};
    use crate::store::workdirs::{self, DirPaths, FileNames};
    use serde_json::Value;
    use std::env;
    use uuid::Uuid;

    fn get_tmp_dir() -> PathBuf {
        let path = env::temp_dir().join(Uuid::new_v4().to_string());
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn get_cfg(tmp_dir: &Path) -> Cfg {
        let paths = DirPaths::new(tmp_dir, "dag", "hhh");
        let mut cfg = Cfg::default();
        cfg.homedir = tmp_dir.to_path_buf();
        cfg.dagdir = paths.dagdir;
        cfg.cachedir = paths.cachedir;
        cfg.local_cachedir = paths.local_cachedir;
        cfg.dag_code_hash = "abc".into();
        cfg
    }

    fn get_task(tmp_dir: &Path) -> Task {
        let mut task = Task::default();
        let artifact_path = tmp_dir.join("artifact.txt");
        task.name = "name".into();
        task.pipeline_name = "dag".into();
        task.fn_name = "fn_name".into();
        task.artifacts = vec![Artifact {
            name: "artifact".into(),
            path: artifact_path,
        }];
        task.kwargs = vec![
            Kwarg {
                key: "key_true".into(),
                value: Value::Bool(true),
            },
            Kwarg {
                key: "key_false".into(),
                value: Value::Bool(false),
            },
        ];
        task.code_hash = "xyz".into();
        task
    }

    fn get_input() -> HashMap<String, Value> {
        HashMap::from([
            ("key_true".into(), Value::Bool(true)),
            ("key_false".into(), Value::Bool(false)),
        ])
    }

    fn create_input(input: &HashMap<String, Value>, cache_path: &Path) {
        let path = cache_path.join(FileNames::Input.as_str());
        let contents = serde_json::to_string(input).unwrap();
        fs::write(&path, &contents).unwrap();
    }

    fn create_output(cache_path: &Path) {
        let path = cache_path.join(FileNames::Output.as_str());
        let contents = r#"{
            "output": null,
            "artifacts": [
                {
                    "name": "artifact",
                    "path": "some/path"
                }
            ]
        }"#;

        fs::write(&path, contents).unwrap();
    }

    fn create_meta(cache_path: &Path) {
        let path = cache_path.join(FileNames::Meta.as_str());
        let meta = TaskMeta {
            fn_name: "fn_name".into(),
            name: "name".into(),
            code_hash: "xyz".into(),
            dag_code_hash: "abc".into(),
        };
        let contents = serde_json::to_string(&meta).unwrap();
        fs::write(&path, &contents).unwrap();
    }

    fn create_artifact(tmp_dir: &Path) {
        let artifact_path = tmp_dir.join("artifact.txt");
        fs::write(&artifact_path, "").unwrap();
    }

    fn create_and_get_cache_path(task: &Task, cfg: &Cfg) -> PathBuf {
        let base_cache_path = workdirs::get_task_cache_path(task, cfg);
        let cache_path = base_cache_path.join("aaa");
        fs::create_dir_all(&cache_path).unwrap();
        cache_path
    }

    #[test]
    #[should_panic]
    fn test_output_caching_without_artifact() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);

        task.cache = Cache::Output;
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    fn test_output_caching_with_artifact() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);

        task.cache = Cache::Output;
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_io_caching_without_input() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);

        task.cache = Cache::Io;
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_io_caching_with_wrong_input() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let mut input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);

        task.cache = Cache::Io;
        input.insert("key_true".into(), Value::Bool(false));
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    fn test_io_caching() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);

        task.cache = Cache::Io;
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    fn test_io_caching_with_wrong_input_ignored() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let mut input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);

        task.cache = Cache::Io;
        task.cache_ignore = vec!["key_true".into()];
        input.insert("key_true".into(), Value::Bool(false));

        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_task_caching_with_wrong_hash() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);
        create_meta(&cache_path);

        task.cache = Cache::Task;
        task.code_hash = "wrong".into();
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    fn test_task_caching() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);
        create_meta(&cache_path);

        task.cache = Cache::Task;
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_project_caching_with_wrong_hash() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let mut cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);
        create_meta(&cache_path);

        task.cache = Cache::Project;
        cfg.dag_code_hash = "wrong".into();
        validate_cache(&input, &task, &cfg).unwrap();
    }

    #[test]
    fn test_project_caching() {
        let tmp_dir = get_tmp_dir();
        let mut task = get_task(&tmp_dir);
        let cfg = get_cfg(&tmp_dir);
        let input = get_input();
        let cache_path = create_and_get_cache_path(&task, &cfg);
        create_output(&cache_path);
        create_artifact(&tmp_dir);
        create_input(&input, &cache_path);
        create_meta(&cache_path);

        task.cache = Cache::Project;
        validate_cache(&input, &task, &cfg).unwrap();
    }
}
