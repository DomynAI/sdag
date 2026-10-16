// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::banner;
use crate::commands::kill;
use crate::engine::context::Ctx;
use crate::engine::polling::{LocalPoller, Poller, SlurmPoller};
use crate::engine::submission::Submitter;
use crate::engine::summary;
use crate::engine::visitors::NodeVisitor;
use crate::model::nodes::Node;
use crate::model::schemas::DAGMeta;
use crate::model::{dag_setup, status};
use crate::settings::Cfg;
use crate::store::state;
use ctrlc;
use std::sync::mpsc;
use std::sync::mpsc::Sender;
use std::sync::{Mutex, Once};

static CTRLC_TX: Mutex<Option<Sender<()>>> = Mutex::new(None);
static ONCE: Once = Once::new();

fn install_ctrlc_handler() {
    ONCE.call_once(|| {
        ctrlc::set_handler(|| {
            if let Ok(guard) = CTRLC_TX.lock()
                && let Some(tx) = guard.as_ref()
            {
                let _ = tx.send(());
            }
        })
        .expect("Error setting Ctrl-C handler");
    });
}

pub fn scheduling_loop(nodes: &[Node], ctx: &mut Ctx, cfg: &Cfg, meta: &DAGMeta) {
    banner::log_banner();
    log::info!(
        "Start scheduling pipeline '{}' with hash '{}'",
        meta.pipeline_name,
        meta.hash
    );
    state::rm_kill_file_if_present(&cfg.dagdir);

    let mut visitor = NodeVisitor { nodes, cfg };
    let mut submitter = Submitter::new(cfg, meta);
    let mut slurm_poller = SlurmPoller { cfg };
    let mut local_poller = LocalPoller { cfg };

    let root_uid = dag_setup::find_root_node(nodes).expect("Failed to find the root node");
    ctx.updated.push_back(root_uid);

    let (tx, rx) = mpsc::channel();
    install_ctrlc_handler();
    *CTRLC_TX.lock().expect("Ctrl-C mutex poisoned") = Some(tx);

    while !state::is_scheduler_killed(&cfg.dagdir) {
        slurm_poller.poll(nodes, ctx);
        local_poller.poll(nodes, ctx);
        visitor.visit(ctx);
        submitter.submit(nodes, ctx);
        if ctx.must_checkpoint {
            let res = state::save_checkpoint(cfg, meta, nodes, ctx);
            if let Err(e) = res {
                log::error!("Failed to save checkpoint: {e}");
            };
            ctx.must_checkpoint = false;
        }

        summary::print_summary(nodes, ctx, &meta.pipeline_name, &meta.hash);
        if status::is_simulation_completed(&ctx.nodes) {
            log::info!("Simulation completed");
            break;
        }

        if cfg.fail_fast && status::any_node_failed(&ctx.nodes) {
            let _ = state::create_kill_file(&cfg.dagdir)
                .map_err(|e| log::error!("Failed to create kill file - {e}"));
            break;
        }

        if rx.recv_timeout(cfg.sleep_time).is_ok() {
            print!("\nScheduler stopped, do you wanna kill all running jobs? (y/N) ");
            let choice: String = text_io::read!("{}");
            if choice == "y" {
                let _ = state::create_kill_file(&cfg.dagdir)
                    .map_err(|e| log::error!("Failed to create kill file - {e}"));
            }
            break;
        }
    }

    if state::is_scheduler_killed(&cfg.dagdir) {
        log::info!("Killing all jobs");
        kill::kill_jobs(ctx);
    }

    let _ = state::save_checkpoint(cfg, meta, nodes, ctx);
    summary::print_recap(nodes, ctx);

    *CTRLC_TX.lock().expect("Ctrl-C mutex poisoned") = None;
}
