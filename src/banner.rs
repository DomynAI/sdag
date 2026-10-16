// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use log;

pub fn log_banner() {
    let banner = r#"
  _____ _____          _____
 / ____|  __ \   /\   / ____|
| (___ | |  | | /  \ | |  __
 \___ \| |  | |/ /\ \| | |_ |
 ____) | |__| / ____ \ |__| |
|_____/|_____/_/    \_\_____|"#;
    let version = env!("CARGO_PKG_VERSION");
    log::info!("\n\x1b[32m{banner}\x1b[0m v{version}\n");
}
