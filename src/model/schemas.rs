// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::settings::Cfg;
use crate::{engine::context::NodeCtx, model::nodes::Node};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{borrow::Cow, collections::HashMap, fmt, path::PathBuf};
use uuid::Uuid;

fn get_new_dag_hash() -> String {
    let full_uuid = Uuid::new_v4().to_string();
    let idx = full_uuid.char_indices().nth_back(11).unwrap().0;
    full_uuid[idx..].into()
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct DAGMeta {
    pub pipeline_name: String,
    #[serde(default = "get_new_dag_hash")]
    pub hash: String,
    pub code_hash: String,
    pub timestamp: String,
    pub extra: Value,
    pub import_path: String,
    pub kwargs: HashMap<String, Value>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct TaskMeta {
    /// Task function name
    pub fn_name: String,
    /// Task name. By default it's equal to the function name
    pub name: String,
    /// Task function code hash
    pub code_hash: String,
    /// Imported module hash
    pub dag_code_hash: String,
}

/// Task output.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct TaskOutput {
    /// Serialize output value.
    pub output: Value,
    /// Output artifacts.
    #[serde(default = "Vec::new")]
    pub artifacts: Vec<Artifact>,
}

// Task execution mode
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum ExecMode {
    /// Wrap an existing task
    #[serde(rename = "wrap")]
    Wrap,
    /// External script
    #[serde(rename = "ext")]
    Ext,
}

impl Default for ExecMode {
    fn default() -> Self {
        Self::Wrap
    }
}

/// Task static input kwargs.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Kwarg {
    /// Input key in the function signature.
    pub key: String,
    /// Static input value.
    pub value: Value,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum Cmd {
    /// Slurm
    #[serde(rename = "sbatch")]
    Sbatch,
    /// Local execution
    #[serde(rename = "bash")]
    Bash,
}
impl fmt::Display for Cmd {
    /// For getting the command argument
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let cmd = match self {
            Self::Sbatch => "sbatch",
            Self::Bash => "bash",
        };
        write!(f, "{cmd}")
    }
}
impl Default for Cmd {
    fn default() -> Self {
        Self::Bash
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum Scope {
    /// Local task
    #[serde(rename = "local")]
    Local,
    /// Global task
    #[serde(rename = "global")]
    Global,
}
impl Default for Scope {
    fn default() -> Self {
        Self::Local
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct ScriptContent {
    pub content: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct ScriptPath {
    pub path: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Script {
    Script(ScriptContent),
    ScriptPath(ScriptPath),
}
impl Default for Script {
    fn default() -> Self {
        Self::Script(ScriptContent { content: "".into() })
    }
}

/// Artifacts.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Artifact {
    /// Artifact name.
    pub name: String,
    /// Artifact path.
    pub path: PathBuf,
}

/// Parent types.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ParentKind {
    /// No data exchange, the dependence is only logical.
    Logical,
    /// Node takes a parent artifact as input.
    Artifact {
        /// Key in the task function signature.
        key: String,
        /// Artifact name.
        name: String,
        /// Artifact path
        path: PathBuf,
    },
    /// Node takes the parent output as input.
    Output { key: String },
    /// Branch dependence.
    Branch { branch: bool },
}

/// Node parent.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Parent {
    /// Parent UID.
    pub uid: usize,
    /// Relashionship.
    pub kind: ParentKind,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct DAG {
    pub meta: DAGMeta,
    pub nodes: Vec<Node>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Checkpoint<'a> {
    #[serde(borrow)]
    pub cfg: Cow<'a, Cfg>,
    #[serde(borrow)]
    pub meta: Cow<'a, DAGMeta>,
    #[serde(borrow)]
    pub nodes: Cow<'a, [Node]>,
    #[serde(borrow)]
    pub node_ctxs: Cow<'a, [NodeCtx]>,
}
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
#[serde(rename_all = "kebab-case")]
pub struct SlurmOverride {
    pub job_name: Option<String>,
    pub nodes: Option<usize>,
    pub partition: Option<String>,
    pub qos: Option<String>,
    pub gpus_per_node: Option<usize>,
    pub ntasks_per_node: Option<String>,
    pub output: Option<String>,
    pub error: Option<String>,
    pub account: Option<String>,
    pub cpus_per_task: Option<usize>,
    pub mem: Option<String>,
    pub time: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Cache {
    None,
    Output,
    Io,
    Task,
    Project,
}
impl Cache {
    pub fn is_enabled(&self) -> bool {
        match self {
            Self::None => false,
            Self::Output | Self::Io | Self::Task | Self::Project => true,
        }
    }
}

impl Default for Cache {
    fn default() -> Self {
        Self::None
    }
}
impl fmt::Display for Cache {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let cmd = match self {
            Self::None => "none",
            Self::Output => "output",
            Self::Io => "io",
            Self::Task => "task",
            Self::Project => "project",
        };
        write!(f, "{cmd}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verify_hash_length() {
        let hash = get_new_dag_hash();
        assert_eq!(hash.chars().count(), 12);
    }
}
