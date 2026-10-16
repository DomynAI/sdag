// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use env_logger::Env;

use chrono::Local;
use log;
use serde::{Deserialize, Serialize};
use std::env;
use std::path::PathBuf;
use std::time::Duration;

pub fn get_timestamp() -> String {
    format!("{}", Local::now().format("%Y-%m-%dT%H:%M:%S"))
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
pub struct Cfg {
    pub homedir: PathBuf,
    pub dagdir: PathBuf,
    pub cachedir: PathBuf,
    pub dag_code_hash: String,
    pub local_cachedir: PathBuf,
    pub timestamp: String,
    pub grace_period: usize,
    pub max_dagdirs: usize,
    pub max_concurrency: usize,
    pub sleep_time: Duration,
    pub log_level: String,
    pub fail_fast: bool,
}

/// Configure logging.
pub fn configure_logging(log_level: &str) {
    let env = Env::default()
        .filter_or("SDAG_LOG_LEVEL", log_level)
        .write_style_or("SDAG_LOG_STYLE", "always");

    match env_logger::try_init_from_env(env) {
        Ok(_) => log::debug!("Logging configured"),
        Err(e) => {
            log::debug!("Logging already configured - {e}");
        }
    }
}

/// Find the home directory.
pub fn find_homedir() -> Result<PathBuf, String> {
    let path = match env::var("SDAG_HOME") {
        Ok(val) => PathBuf::from(val),
        Err(_) => {
            let path = env::home_dir().ok_or(String::from(
                "Failed to identify a home directory, please Set the \
            'SDAG_HOME' environment variable explicitely.",
            ))?;
            path
        }
    };
    Ok(path.join(".sdag"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn set_sdag_home() -> PathBuf {
        let path = "./a/path";
        unsafe {
            env::set_var("SDAG_HOME", path);
        }
        PathBuf::from(path)
    }

    /// The home directory is correctly identified.
    #[test]
    fn find_home() {
        let home = set_sdag_home();
        let home_dir = find_homedir().unwrap();
        assert_eq!(home_dir, PathBuf::from(home).join(".sdag"));
    }
}
