// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::Ctx;
use crate::engine::summary;
use crate::settings;
use crate::store::{state, workdirs};

pub fn print_status(pipeline_name: &str, pipeline_hash: &str) -> Result<(), String> {
    let homedir =
        settings::find_homedir().map_err(|e| format!("Failed to find the home directory: {e}"))?;
    let Some(path) = workdirs::find_pipeline_folder(&homedir, pipeline_name, pipeline_hash) else {
        let msg = format!(
            "No '{}' pipeline runs found with hash '{}'",
            pipeline_name, pipeline_hash
        );
        return Err(msg);
    };

    let ckpt =
        state::read_chekpoint(&path).map_err(|e| format!("Failed to read checkpoint - {e}"))?;
    let meta = ckpt.meta.into_owned();
    let nodes = ckpt.nodes.into_owned();
    let node_ctxs = ckpt.node_ctxs.into_owned();
    let ctx = Ctx::from_checkpoint(&nodes, node_ctxs);

    summary::print_summary(&nodes, &ctx, pipeline_name, &meta.hash);
    Ok(())
}
