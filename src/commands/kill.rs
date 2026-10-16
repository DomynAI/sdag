// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::Ctx;
use crate::model::status::{Failed, JobType, Status};
use crate::settings;
use crate::store::{state, workdirs};
use log;
use std::collections::HashMap;
use std::io;
use std::process::{Child, Command, Stdio};

pub fn create_kill_lock(name: &str, hash: &str) {
    log::info!("Killing pipeline '{name}' with hash '{hash}'");
    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    let Some(dagdir) = workdirs::find_pipeline_folder(&homedir, name, hash) else {
        log::warn!("No '{}' pipeline runs found for hash '{}'", name, hash);
        return;
    };

    log::debug!(
        "Pipeline {name}; Directory identified: '{}'",
        dagdir.to_string_lossy()
    );

    match state::create_kill_file(&dagdir) {
        Ok(_) => log::info!("Pipeline '{name}', hash '{hash}': Kill signal emitted"),
        Err(e) => log::error!(
            "Pipeline '{name}', hash '{hash}': Failed \
            to create kill file - {e}"
        ),
    }
}

pub fn kill_jobs(ctx: &mut Ctx) {
    if let Err(e) = kill_slurm_jobs(ctx) {
        log::error!("Failed to kill slurm jobs - {e}");
    };

    kill_local_jobs(ctx);
}

fn kill_local_jobs(ctx: &mut Ctx) {
    let mut killed_statuses: HashMap<usize, Status> = HashMap::new();
    for (uid, child) in &mut ctx.local_jobs {
        let job_type = JobType::Local(child.id());
        killed_statuses.insert(*uid, Status::Failed(Failed::Job(job_type)));
        match kill_process_group(child) {
            Ok(_) => log::info!("Task '{uid}': Killed process group {}", child.id()),
            Err(e) => log::error!(
                "Task '{uid}': Failed to kill process group {} - {e}",
                child.id()
            ),
        }
    }
    for (uid, killed_status) in killed_statuses.into_iter() {
        ctx.set_status(uid, killed_status);
    }
}

/// Kills the whole process group of child, not just its own PID.
fn kill_process_group(child: &mut Child) -> io::Result<()> {
    let pgid = child.id() as i32;
    // - used to only reach its tree
    if unsafe { libc::kill(-pgid, libc::SIGKILL) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

fn kill_slurm_jobs(ctx: &mut Ctx) -> Result<(), String> {
    if ctx.slurm_jobs.len() == 0 {
        log::info!("No running Slurm jobs found");
        return Ok(());
    }

    let mut cmd = Command::new("scancel");
    for (uid, job_id) in &ctx.slurm_jobs {
        log::info!("Task '{}': Killing job {}", uid, job_id);
        cmd.arg(job_id);
    }

    let output = cmd
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .output()
        .map_err(|e| format!("Failed to run scancel - {e}"))?;

    if !output.status.success() {
        return Err("Failed to cancel Slurm jobs".into());
    }

    let killed: Vec<(usize, String)> = ctx.slurm_jobs.drain(..).collect();
    for (uid, job_id) in killed {
        let job_type = JobType::Slurm(job_id.clone());
        ctx.set_status(uid, Status::Failed(Failed::Job(job_type)));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use crate::engine::context::NodeCtx;
    use std::collections::{HashSet, VecDeque};
    use std::os::unix::process::CommandExt;

    use super::*;
    #[test]
    fn test_job_kill() {
        let child = Command::new("sleep")
            .arg("5")
            .process_group(0)
            .spawn()
            .unwrap();
        let node_ctx = NodeCtx {
            status: Status::Running(JobType::Local(child.id())),
            try_num: 1,
            jobs: vec![],
        };
        let mut ctx = Ctx {
            updated: VecDeque::new(),
            nodes: vec![node_ctx],
            jobs: VecDeque::new(),
            local_jobs: vec![(0, child)],
            slurm_jobs: Vec::new(),
            running_cacheable: HashSet::new(),
            must_checkpoint: false,
        };

        kill_jobs(&mut ctx);

        let exit_status = ctx.local_jobs[0].1.wait().unwrap();
        assert!(!exit_status.success())
    }
}
