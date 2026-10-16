// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::settings;
use crate::store::state;
use log;

pub fn prune_cache(task_name: &str, pipeline_name: Option<&str>, allow_full_prune: bool) {
    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    match pipeline_name {
        Some(name) => {
            if let Err(e) = state::clear_local_cache(task_name, name, &homedir) {
                log::error!(
                    "Failed to remove task '{task_name}' cache from \
                    pipeline '{name}' - {e} "
                );
            }
        }
        None => {
            if let Err(e) = state::clear_global_cache(task_name, allow_full_prune, &homedir) {
                {
                    log::error!("Failed to remove task '{task_name}' global cache - {e}");
                }
            }
        }
    }
}
