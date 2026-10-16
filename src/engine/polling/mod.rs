// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::Ctx;
use crate::model::nodes::Node;
mod poll_local;
mod poll_slurm;
pub use poll_local::LocalPoller;
pub use poll_slurm::SlurmPoller;

pub trait Poller {
    fn poll(&mut self, nodes: &[Node], ctx: &mut Ctx);
}
