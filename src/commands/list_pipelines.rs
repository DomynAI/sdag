// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0
//! Create the summary table out of the nodemap.

use crate::engine::summary::get_styled_table;
use crate::settings;
use crate::store::workdirs;
use chrono::{DateTime, Local};
use std::error::Error;
use std::iter::zip;
use tabled::Tabled;

pub fn print_pipelines(names: &[String], paths: &[String]) {
    let mut records = Vec::with_capacity(names.len());
    for (name, path) in zip(names, paths) {
        records.push(PipelineList { name, path });
    }
    let table = get_styled_table(records);
    println!("{table}");
}

pub fn print_runs(name: &str) -> Result<(), Box<dyn Error>> {
    let homedir = settings::find_homedir().expect("Failed to find the home directory");
    let dagdir = homedir.join("pipelines").join(name);
    let dirs = workdirs::get_subfolder_creation_dates(&dagdir)?;

    let mut records = Vec::with_capacity(dirs.len());
    for (path, systime) in dirs.into_iter() {
        let dt_utc: DateTime<Local> = systime.into();
        let Some(hash) = path.file_name() else {
            let path_str = path.to_string_lossy();
            let msg = format!("Failed to identify hash for path {}", path_str);
            return Err(msg.into());
        };

        records.push(RunList {
            hash: hash.to_string_lossy().into(),
            timestamp: dt_utc,
        });
    }

    let table = get_styled_table(records);
    println!("{table}");
    Ok(())
}

/// Summary table.
#[derive(Tabled)]
struct PipelineList<'a> {
    /// Task status.
    name: &'a str,
    /// Number of tasks ended in status.
    path: &'a str,
}

/// Summary table.
#[derive(Tabled)]
struct RunList {
    /// Task status.
    hash: String,
    /// Number of tasks ended in status.
    timestamp: DateTime<Local>,
}
