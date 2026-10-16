// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::{JobArray, NodeCtx};
use crate::model::nodes::Task;
use crate::model::schemas::{Cmd, DAGMeta, ExecMode, Script, SlurmOverride, TaskMeta};
use crate::model::status::Status;
use crate::settings::Cfg;
use crate::store::{state, workdirs::FileNames};
use log;
use serde_json::Value;
use std::collections::HashMap;
use std::error::Error;
use std::io;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Output, Stdio};

pub fn submit_slurm(
    task: &Task,
    cfg: &Cfg,
    meta: &DAGMeta,
    node_ctx: &mut NodeCtx,
) -> Result<String, Box<dyn Error>> {
    if let Some(each) = &task.each {
        submit_slurm_job_array(each, task, cfg, meta, node_ctx)
    } else {
        submit_single_slurm_job(task, cfg, meta, node_ctx)
    }
}

pub fn submit_slurm_job_array(
    each: &str,
    task: &Task,
    cfg: &Cfg,
    meta: &DAGMeta,
    node_ctx: &mut NodeCtx,
) -> Result<String, Box<dyn Error>> {
    let mut input = state::read_input_from_parents(task, &cfg.dagdir)?;
    save_input(&input, task, cfg)?;
    save_meta(task, cfg)?;

    let base_path = cfg.dagdir.join(task.uid.to_string()).join(".shards");
    if node_ctx.jobs.is_empty() {
        let njobs = shard_input(&mut input, each, task, &base_path)?;
        node_ctx.jobs = vec![JobArray::default(); njobs];
    }

    let mut cmd = build_command(task, node_ctx.try_num, cfg, meta, &input, &task.envs)?;
    let (output, error) = find_output_and_error_paths(
        &task.slurm,
        &meta.pipeline_name,
        &task.pipeline_name,
        &cfg.timestamp,
        true,
    );
    state::create_output_and_error_log_dirs(&output, &error);
    override_sbatch(&mut cmd, &task.slurm, &task.name, &output, &error);
    set_array_variables(&mut cmd, &base_path, task, node_ctx, cfg)?;
    let output = cmd.output()?;
    if let Ok(stderr) = String::from_utf8(output.stderr)
        && !stderr.is_empty()
    {
        log::error!("Task '{}' submission:\n{stderr}", task.uid);
    }

    let stdout = String::from_utf8(output.stdout)?;
    log::info!("Task '{}':\n{stdout}", task.uid);
    if !output.status.success() {
        log::error!("Task '{}' returned non-zero exit status", task.uid);
        return Err("non-zero exit status".into());
    }

    let job_id = find_submitted_job_id(&stdout).ok_or("Job id not found")?;
    Ok(job_id)
}

pub fn submit_single_slurm_job(
    task: &Task,
    cfg: &Cfg,
    meta: &DAGMeta,
    node_ctx: &mut NodeCtx,
) -> Result<String, Box<dyn Error>> {
    if node_ctx.try_num == 1 {
        node_ctx.jobs = vec![JobArray::default()];
    }
    let input = state::read_input_from_parents(task, &cfg.dagdir)?;
    let mut cmd = build_command(task, node_ctx.try_num, cfg, meta, &input, &task.envs)?;
    save_input(&input, task, cfg)?;
    save_meta(task, cfg)?;
    let (output, error) = find_output_and_error_paths(
        &task.slurm,
        &meta.pipeline_name,
        &task.pipeline_name,
        &cfg.timestamp,
        false,
    );
    state::create_output_and_error_log_dirs(&output, &error);
    override_sbatch(&mut cmd, &task.slurm, &task.name, &output, &error);
    set_script_path(&mut cmd, task, cfg)?;
    let output = cmd.output()?;

    if let Ok(stderr) = String::from_utf8(output.stderr)
        && !stderr.is_empty()
    {
        log::error!("Task '{}' submission:\n{stderr}", task.uid);
    }

    let stdout = String::from_utf8(output.stdout)?;
    log::info!("Task '{}':\n{stdout}", task.uid);
    if !output.status.success() {
        log::error!("Task '{}' returned non-zero exit status", task.uid);
        return Err("non-zero exit status".into());
    }

    let job_id = find_submitted_job_id(&stdout).ok_or("Job id not found")?;
    Ok(job_id)
}

fn shard_input(
    input: &mut HashMap<String, Value>,
    each: &str,
    task: &Task,
    base_path: &Path,
) -> Result<usize, String> {
    let each_field = input.remove(each);
    let Some(Value::Array(arr)) = each_field else {
        let msg = format!("Task {}: Array field '{each}' not found in input", task.uid);
        return Err(msg);
    };

    let nitems = arr.len();
    let njobs = task.njobs.min(nitems);
    if njobs == 0 {
        let msg = format!(
            "Task {}: The number of jobs for array field '{each}' is 0",
            task.uid
        );
        return Err(msg);
    }

    let (div, rem) = (nitems / njobs, nitems % njobs);
    for job_id in 0..njobs {
        let start = job_id * div + job_id.min(rem);
        let end = start + div + usize::from(job_id < rem);
        let shard = &arr[start..end];
        state::save_shard(shard, base_path, job_id)
            .map_err(|e| format!("Task {}: Failed to save shard - {e}", task.uid))?;
    }
    Ok(njobs)
}

pub fn submit_local(
    task: &Task,
    try_num: usize,
    cfg: &Cfg,
    meta: &DAGMeta,
) -> Result<Child, Box<dyn Error>> {
    log::info!("Submitting local task '{}'", task.uid);
    let input = state::read_input_from_parents(task, &cfg.dagdir)?;
    let mut cmd = build_command(task, try_num, cfg, meta, &input, &task.envs)?;
    set_script_path(&mut cmd, task, cfg)?;
    save_input(&input, task, cfg)?;
    save_meta(task, cfg)?;

    cmd.process_group(0)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| e.into())
}

pub fn submit_local_blocking(
    task: &Task,
    try_num: usize,
    cfg: &Cfg,
    meta: &DAGMeta,
) -> Result<Output, Box<dyn Error>> {
    log::info!("Submitting local task '{}'", task.uid);
    let input = state::read_input_from_parents(task, &cfg.dagdir)?;
    let mut cmd = build_command(task, try_num, cfg, meta, &input, &task.envs)?;
    set_script_path(&mut cmd, task, cfg)?;
    save_input(&input, task, cfg)?;
    save_meta(task, cfg)?;

    cmd.stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .output()
        .map_err(|e| e.into())
}

fn build_command(
    task: &Task,
    try_num: usize,
    cfg: &Cfg,
    meta: &DAGMeta,
    input: &HashMap<String, Value>,
    envs: &HashMap<String, Value>,
) -> io::Result<Command> {
    let input_kwargs = serde_json::to_string(&meta.kwargs)?;
    let mut cmd = Command::new(task.cmd.to_string());
    if let Cmd::Sbatch = task.cmd {
        cmd.arg("--parsable");
    }

    for (env_name, env_val) in envs.iter() {
        cmd.env(env_name, convert_env_to_string(env_val));
    }

    if let ExecMode::Ext = task.mode {
        set_input_as_envs(&mut cmd, input);
    }

    cmd.env("SDAG_TRY_NUM", try_num.to_string())
        .env("SDAG_PIPELINE_DIR", &cfg.dagdir)
        .env("SDAG_PIPELINE_NAME", &meta.pipeline_name)
        .env("SDAG_INPUT_KWARGS", &input_kwargs)
        .env("SDAG_SUBPIPELINE_NAME", &task.pipeline_name)
        .env("SDAG_IMPORT_PATH", &meta.import_path)
        .env("SDAG_UID", task.uid.to_string())
        .env("SDAG_TASK_FN", &task.fn_name)
        .env("SDAG_TASK_NAME", &task.name)
        .env("SDAG_LOG_LEVEL", &cfg.log_level);

    Ok(cmd)
}

fn save_input(input: &HashMap<String, Value>, task: &Task, cfg: &Cfg) -> io::Result<()> {
    let filename = FileNames::Input.as_str();
    let dir = task.uid.to_string();
    let path = cfg.dagdir.join(dir).join(filename);
    state::save_input(input, &path)
}

fn save_meta(task: &Task, cfg: &Cfg) -> io::Result<()> {
    let meta = TaskMeta {
        fn_name: task.fn_name.to_string(),
        name: task.name.to_string(),
        code_hash: task.code_hash.to_string(),
        dag_code_hash: cfg.dag_code_hash.to_string(),
    };

    let filename = FileNames::Meta.as_str();
    let dir = task.uid.to_string();
    let path = cfg.dagdir.join(dir).join(filename);
    log::debug!(
        "Writing task '{}' metadata in {}",
        task.uid,
        path.to_string_lossy()
    );

    state::save_meta(&meta, &path)
}

fn override_sbatch(
    cmd: &mut Command,
    slurm: &SlurmOverride,
    name: &str,
    output: &str,
    error: &str,
) {
    cmd.arg(format!("--error={error}"));
    cmd.arg(format!("--output={output}"));

    let mut job_name = name;
    if let Some(user_job_name) = &slurm.job_name {
        job_name = user_job_name;
    }
    cmd.arg(format!("--job-name={job_name}"));

    if let Some(nodes) = &slurm.nodes {
        cmd.arg(format!("--nodes={nodes}"));
    }
    if let Some(partition) = &slurm.partition {
        cmd.arg(format!("--partition={partition}"));
    }
    if let Some(qos) = &slurm.qos {
        cmd.arg(format!("--qos={qos}"));
    }
    if let Some(gpus_per_node) = &slurm.gpus_per_node {
        cmd.arg(format!("--gpus-per-node={gpus_per_node}"));
    }
    if let Some(ntasks_per_node) = &slurm.ntasks_per_node {
        cmd.arg(format!("--ntasks-per-node={ntasks_per_node}"));
    }
    if let Some(account) = &slurm.account {
        cmd.arg(format!("--account={account}"));
    }
    if let Some(cpus_per_task) = &slurm.cpus_per_task {
        cmd.arg(format!("--cpus-per-task={cpus_per_task}"));
    }
    if let Some(mem) = &slurm.mem {
        cmd.arg(format!("--mem={mem}"));
    }
    if let Some(time) = &slurm.time {
        cmd.arg(format!("--time={time}"));
    }
}

fn find_output_and_error_paths(
    slurm: &SlurmOverride,
    pipeline: &str,
    subpipeline: &str,
    timestamp: &str,
    is_array: bool,
) -> (String, String) {
    let base = format!("./logs/{pipeline}/{timestamp}/{subpipeline}");
    let stem = if is_array { "%x.%A_%a" } else { "%x.%j" };
    let mut output = format!("{base}/{stem}.out");
    if let Some(user_output) = &slurm.output {
        output = user_output.to_string()
    };

    let mut error = format!("{base}/{stem}.err");
    if let Some(user_error) = &slurm.error {
        error = user_error.to_string();
    }

    (output, error)
}

fn set_script_path(cmd: &mut Command, task: &Task, cfg: &Cfg) -> Result<(), String> {
    let path = match &task.script {
        Script::Script(script) => {
            let filename = FileNames::Script.as_str();
            let dir = task.uid.to_string();
            let path = cfg.dagdir.join(dir).join(filename);
            state::save_script(&script.content, &path)
                .map_err(|e| format!("Failed to save script: {e}"))?;
            path
        }
        Script::ScriptPath(script_path) => PathBuf::from(&script_path.path),
    };

    if !path.is_file() {
        let msg = format!("Script '{}' does not exist", task.uid);
        return Err(msg);
    }

    cmd.arg(&path);
    Ok(())
}

fn set_input_as_envs(cmd: &mut Command, input: &HashMap<String, Value>) {
    for (key, value) in input.iter() {
        let val = convert_env_to_string(value);
        let upper_key = key.to_uppercase();
        cmd.env(upper_key, val);
    }
}

fn convert_env_to_string(value: &Value) -> String {
    match value {
        Value::Null => String::new(),
        Value::String(v) => v.to_string(),
        _ => value.to_string(),
    }
}

fn find_submitted_job_id(output: &str) -> Option<String> {
    output.split(";").map(|s| s.trim().to_string()).next()
}

fn set_array_variables(
    cmd: &mut Command,
    base_path: &Path,
    task: &Task,
    node_ctx: &NodeCtx,
    cfg: &Cfg,
) -> Result<(), String> {
    let ids = find_ids_to_be_submitted(&node_ctx.jobs);
    if ids.is_empty() {
        let msg = format!(
            "Task {}: No task ids found during array submission",
            task.uid
        );
        return Err(msg);
    }

    let Some(each) = &task.each else {
        let msg = format!("Task {}: each field not defined for array", task.uid);
        return Err(msg);
    };

    let array_option = if cfg.max_concurrency > 0 {
        format!("--array={ids}%{}", cfg.max_concurrency)
    } else {
        format!("--array={ids}")
    };

    cmd.arg(&array_option);
    cmd.env("SDAG_SHARD_PATH", base_path);
    cmd.env("SDAG_EACH_KEY", each);
    set_script_path(cmd, task, cfg)
}

fn find_ids_to_be_submitted(jobs: &[JobArray]) -> String {
    let mut task_ids = Vec::new();
    for (i, job) in jobs.iter().enumerate() {
        if matches!(job.status, Status::NotSubmitted)
            | matches!(job.status, Status::ReadyForSubmission)
        {
            task_ids.push(i.to_string());
        }
    }
    let to_be_submitted = task_ids.join(",");
    log::info!("Array ids to be submitted: '{to_be_submitted}'",);
    to_be_submitted
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::schemas::{ScriptContent, ScriptPath};
    use crate::store::workdirs::DirPaths;
    use serde_json::json;
    use std::env;
    use std::fs;
    use std::path::PathBuf;
    use uuid::Uuid;

    fn get_tmp_dir() -> PathBuf {
        let path = env::temp_dir().join(Uuid::new_v4().to_string());
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn get_meta() -> DAGMeta {
        DAGMeta {
            pipeline_name: "pipe".into(),
            hash: "xxx".into(),
            code_hash: "".into(),
            timestamp: "1920-01-01T09:20:20".into(),
            extra: Value::Null,
            import_path: String::new(),
            kwargs: HashMap::new(),
        }
    }

    fn get_cfg() -> Cfg {
        let homedir = get_tmp_dir();
        let meta = get_meta();
        let paths = DirPaths::new(&homedir, &meta.pipeline_name, &meta.hash);
        Cfg {
            dagdir: paths.dagdir,
            cachedir: paths.cachedir,
            local_cachedir: paths.local_cachedir,
            ..Default::default()
        }
    }

    fn get_task() -> Task {
        Task {
            script: Script::Script(ScriptContent {
                content: "echo hello".into(),
            }),
            envs: HashMap::from([("VAR".into(), Value::Bool(true))]),
            ..Default::default()
        }
    }

    #[test]
    fn save_script() {
        let mut cmd = Command::new("ls");
        let task = get_task();
        let cfg = get_cfg();
        let task_dir = cfg.dagdir.join(task.uid.to_string());
        fs::create_dir_all(&task_dir).unwrap();
        set_script_path(&mut cmd, &task, &cfg).unwrap();

        let script_path = task_dir.join(FileNames::Script.as_str());
        assert!(script_path.is_file())
    }

    #[test]
    #[should_panic]
    fn try_set_nonexistent_script_path() {
        let mut cmd = Command::new("ls");
        let mut task = get_task();
        task.script = Script::ScriptPath(ScriptPath {
            path: "bad.something".into(),
        });

        let cfg = get_cfg();
        set_script_path(&mut cmd, &task, &cfg).unwrap();
    }

    #[test]
    fn parse_job_output() {
        let output = "1234";
        let job_id = find_submitted_job_id(output).unwrap();
        assert_eq!(job_id, "1234");
    }

    #[test]
    fn parse_job_output_with_cluster() {
        let output = "   1234   ;cluster_name";
        let job_id = find_submitted_job_id(output).unwrap();
        assert_eq!(job_id, "1234");
    }

    #[test]
    fn test_save_input() {
        let input = HashMap::from([("a".to_string(), Value::Null)]);
        let task = get_task();
        let cfg = get_cfg();
        let task_dir = cfg.dagdir.join(task.uid.to_string());
        fs::create_dir_all(&task_dir).unwrap();
        save_input(&input, &task, &cfg).unwrap();

        let input_path = task_dir.join(FileNames::Input.as_str());
        assert!(input_path.exists());
    }

    #[test]
    fn test_submit_local() {
        let meta = get_meta();
        let mut task = get_task();
        task.script = Script::Script(ScriptContent {
            content: "true".into(),
        });
        let cfg = get_cfg();
        let task_dir = cfg.dagdir.join(task.uid.to_string());
        fs::create_dir_all(&task_dir).unwrap();

        let mut child = submit_local(&task, 1, &cfg, &meta).unwrap();
        let status = child.wait().unwrap();
        assert!(status.success());
    }

    #[test]
    fn test_submit_local_blocking() {
        let meta = get_meta();
        let mut task = get_task();
        task.script = Script::Script(ScriptContent {
            content: "true".into(),
        });
        let cfg = get_cfg();
        let task_dir = cfg.dagdir.join(task.uid.to_string());
        fs::create_dir_all(&task_dir).unwrap();

        let output = submit_local_blocking(&task, 1, &cfg, &meta).unwrap();
        assert!(output.status.success());
    }

    #[test]
    fn find_default_log_paths() {
        let slurm = SlurmOverride::default();
        let (output, error) =
            find_output_and_error_paths(&slurm, "pipe", "subpipe", "1900-01-01", false);

        assert_eq!(output, "./logs/pipe/1900-01-01/subpipe/%x.%j.out");
        assert_eq!(error, "./logs/pipe/1900-01-01/subpipe/%x.%j.err");
    }

    #[test]
    fn find_custom_log_paths() {
        let slurm = SlurmOverride {
            output: Some("output.out".into()),
            error: Some("error.err".into()),
            ..Default::default()
        };

        let (output, error) =
            find_output_and_error_paths(&slurm, "pipe", "subpipe", "1900-01-01", false);

        assert_eq!(output, "output.out");
        assert_eq!(error, "error.err");
    }

    #[test]
    #[should_panic]
    fn test_shard_input_without_each() {
        let task = Task {
            each: Some("items".into()),
            ..Default::default()
        };
        let mut input = HashMap::new();
        let base_path = get_tmp_dir();
        shard_input(&mut input, "items", &task, &base_path).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_shard_each_is_not_array() {
        let task = Task {
            each: Some("items".into()),
            ..Default::default()
        };
        let mut input = HashMap::from([("items".into(), "not-array".into())]);
        let base_path = get_tmp_dir();
        shard_input(&mut input, "items", &task, &base_path).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_each_size_is_zero() {
        let task = Task {
            each: Some("items".into()),
            ..Default::default()
        };
        let mut input = HashMap::from([("items".into(), Value::Array(vec![]))]);
        let base_path = get_tmp_dir();
        shard_input(&mut input, "items", &task, &base_path).unwrap();
    }

    #[test]
    fn test_shard_input() {
        let task = Task {
            each: Some("items".into()),
            njobs: 2,
            ..Default::default()
        };
        let mut input = HashMap::from([("items".into(), json!(["1", "2", "3"]))]);
        let base_path = get_tmp_dir();
        let njobs = shard_input(&mut input, "items", &task, &base_path).unwrap();

        let shard0_path = base_path.join("0").join("shard.json");
        let shard1_path = base_path.join("1").join("shard.json");
        let shard_0: Value =
            serde_json::from_str(&fs::read_to_string(&shard0_path).unwrap()).unwrap();
        let shard_1: Value =
            serde_json::from_str(&fs::read_to_string(&shard1_path).unwrap()).unwrap();

        assert_eq!(njobs, 2);
        assert_eq!(shard_0.as_array().unwrap().len(), 2);
        assert_eq!(shard_1.as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_shard_number_goes_down_to_one() {
        let task = Task {
            each: Some("items".into()),
            njobs: 2,
            ..Default::default()
        };
        let mut input = HashMap::from([("items".into(), json!(["1"]))]);
        let base_path = get_tmp_dir();
        let njobs = shard_input(&mut input, "items", &task, &base_path).unwrap();

        let shard0_path = base_path.join("0").join("shard.json");
        let shard_0: Value =
            serde_json::from_str(&fs::read_to_string(&shard0_path).unwrap()).unwrap();

        assert_eq!(njobs, 1);
        assert_eq!(shard_0.as_array().unwrap().len(), 1);
    }
}
