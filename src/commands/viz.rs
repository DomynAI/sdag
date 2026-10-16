// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use graphs_tui::{RenderOptions, render_mermaid_to_tui};
use log;

pub fn view_pipeline(mermaid: &str) {
    log::debug!("\n{mermaid}");

    let result =
        render_mermaid_to_tui(mermaid, RenderOptions::default()).expect("Failed to print DAG");
    println!("{}", result.output);
}
