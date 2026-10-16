// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use crate::model::schemas::{
    Artifact, Cache, Cmd, ExecMode, Kwarg, Parent, ParentKind, Scope, Script, SlurmOverride,
};
use crate::model::status::{Completed, Status};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub trait Children {
    fn children(&self) -> &[usize];
}

pub trait Parents {
    fn parents(&self) -> Vec<usize>;
}

pub trait ProvideStatus {
    fn provide_status<'b>(&self, status: &'b Status, kind: &ParentKind) -> &'b Status;
}

#[allow(clippy::large_enum_variant)]
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Node {
    Root(Root),
    End(End),
    Task(Task),
    Branch(Branch),
    OneOf(OneOf),
}

impl Node {
    pub fn get_uid(&self) -> usize {
        match self {
            Self::Root(n) => n.uid,
            Self::End(n) => n.uid,
            Self::OneOf(n) => n.uid,
            Self::Task(n) => n.uid,
            Self::Branch(n) => n.uid,
        }
    }

    pub fn set_children(&mut self, children: Vec<usize>) {
        match self {
            Node::Root(n) => n.children = children,
            Node::End(n) => n.children = children,
            Node::OneOf(n) => n.children = children,
            Node::Task(n) => n.children = children,
            Node::Branch(n) => n.children = children,
        }
    }
}

impl Children for Node {
    fn children(&self) -> &[usize] {
        match self {
            Self::Root(n) => n.children(),
            Self::End(n) => n.children(),
            Self::OneOf(n) => n.children(),
            Self::Task(n) => n.children(),
            Self::Branch(n) => n.children(),
        }
    }
}

impl Parents for Node {
    fn parents(&self) -> Vec<usize> {
        match self {
            Self::Root(n) => n.parents(),
            Self::End(n) => n.parents(),
            Self::OneOf(n) => n.parents(),
            Self::Task(n) => n.parents(),
            Self::Branch(n) => n.parents(),
        }
    }
}

impl ProvideStatus for Node {
    fn provide_status<'b>(&self, status: &'b Status, kind: &ParentKind) -> &'b Status {
        match self {
            Self::Root(n) => n.provide_status(status, kind),
            Self::End(n) => n.provide_status(status, kind),
            Self::OneOf(n) => n.provide_status(status, kind),
            Self::Task(n) => n.provide_status(status, kind),
            Self::Branch(n) => n.provide_status(status, kind),
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
pub struct Task {
    // Node unique id.
    pub uid: usize,
    /// Node parents.
    #[serde(default = "Vec::new")]
    pub parents: Vec<Parent>,
    /// Task function name.
    pub fn_name: String,
    /// Task name. By default it's equal to the function name
    pub name: String,
    // pipeline name
    pub pipeline_name: String,
    /// Caching.
    pub cache: Cache,
    /// Task code hash
    pub code_hash: String,
    /// Local or global task
    pub scope: Scope,
    /// Local caching.
    pub cache_size: usize,
    /// Fields excluded by caching
    #[serde(default = "Vec::new")]
    pub cache_ignore: Vec<String>,
    /// Execution mode
    pub mode: ExecMode,
    /// Command used
    pub cmd: Cmd,
    /// Argument to be split across jobs
    pub each: Option<String>,
    /// Number of jobs in the array
    pub njobs: usize,
    /// Number of retries.
    pub retries: usize,
    /// script path.
    pub script: Script,
    /// Environemnt variables to be set.
    #[serde(default = "HashMap::new")]
    pub envs: HashMap<String, Value>,
    /// Slurm override
    #[serde(default = "SlurmOverride::default")]
    pub slurm: SlurmOverride,
    /// Static input kwargs.
    #[serde(default = "Vec::new")]
    pub kwargs: Vec<Kwarg>,
    /// Task tags.
    #[serde(default = "Vec::new")]
    pub tags: Vec<String>,
    // Output artifacts.
    pub artifacts: Vec<Artifact>,
    // Output artifacts.
    #[serde(default = "Vec::new")]
    pub children: Vec<usize>,
}

impl Task {
    pub fn is_array(&self) -> bool {
        self.each.is_some()
    }
}

impl Children for Task {
    fn children(&self) -> &[usize] {
        &self.children
    }
}

impl Parents for Task {
    fn parents(&self) -> Vec<usize> {
        self.parents.iter().map(|p| p.uid).collect()
    }
}

impl ProvideStatus for Task {
    fn provide_status<'b>(&self, status: &'b Status, _kind: &ParentKind) -> &'b Status {
        status
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Root {
    // Node unique id.
    pub uid: usize,
    // Pipeline name
    pub pipeline_name: String,
    /// Node parents.
    #[serde(default = "Vec::new")]
    pub parents: Vec<Parent>,
    #[serde(default = "Vec::new")]
    pub children: Vec<usize>,
}

impl Children for Root {
    fn children(&self) -> &[usize] {
        &self.children
    }
}

impl Parents for Root {
    fn parents(&self) -> Vec<usize> {
        self.parents.iter().map(|p| p.uid).collect()
    }
}

impl ProvideStatus for Root {
    fn provide_status<'b>(&self, status: &'b Status, _kind: &ParentKind) -> &'b Status {
        status
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct End {
    // Node unique id.
    pub uid: usize,
    pub pipeline_name: String,
    /// Node parents.
    #[serde(default = "Vec::new")]
    pub parents: Vec<Parent>,
    #[serde(default = "Vec::new")]
    pub children: Vec<usize>,
    #[serde(default = "Vec::new")]
    pub artifacts: Vec<Artifact>,
}

impl Children for End {
    fn children(&self) -> &[usize] {
        &self.children
    }
}

impl Parents for End {
    fn parents(&self) -> Vec<usize> {
        self.parents.iter().map(|p| p.uid).collect()
    }
}

impl ProvideStatus for End {
    fn provide_status<'b>(&self, status: &'b Status, _kind: &ParentKind) -> &'b Status {
        status
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Branch {
    // Node unique id.
    pub uid: usize,
    pub pipeline_name: String,
    /// Node parents.
    pub parents: Vec<Parent>,
    #[serde(default = "Vec::new")]
    pub children: Vec<usize>,
    #[serde(default = "Vec::new")]
    pub artifacts: Vec<Artifact>,
}

impl Children for Branch {
    fn children(&self) -> &[usize] {
        &self.children
    }
}

impl Parents for Branch {
    fn parents(&self) -> Vec<usize> {
        self.parents.iter().map(|p| p.uid).collect()
    }
}

impl ProvideStatus for Branch {
    fn provide_status<'b>(&self, status: &'b Status, kind: &ParentKind) -> &'b Status {
        if let Status::Completed(Completed::Branch(selected_branch)) = status
            && let ParentKind::Branch { branch } = &kind
            && branch != selected_branch
        {
            return &Status::Skipped;
        }
        status
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct OneOf {
    // Node unique id.
    pub uid: usize,
    pub pipeline_name: String,
    /// Node parents.
    #[serde(default = "Vec::new")]
    pub parents: Vec<Parent>,
    #[serde(default = "Vec::new")]
    pub children: Vec<usize>,
    #[serde(default = "Vec::new")]
    pub artifacts: Vec<Artifact>,
}

impl Children for OneOf {
    fn children(&self) -> &[usize] {
        &self.children
    }
}

impl Parents for OneOf {
    fn parents(&self) -> Vec<usize> {
        self.parents.iter().map(|p| p.uid).collect()
    }
}

impl ProvideStatus for OneOf {
    fn provide_status<'b>(&self, status: &'b Status, _kind: &ParentKind) -> &'b Status {
        status
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_completed_branch() {
        let status = Status::Completed(Completed::Branch(true));
        let node = Branch {
            uid: 0,
            pipeline_name: "pipeline".into(),
            parents: vec![],
            children: vec![3, 4, 2],
            artifacts: vec![],
        };

        let true_kind = ParentKind::Branch { branch: true };
        assert!(matches!(
            node.provide_status(&status, &true_kind),
            Status::Completed(_)
        ));
        let false_kind = ParentKind::Branch { branch: false };
        assert!(matches!(
            node.provide_status(&status, &false_kind),
            Status::Skipped
        ));
    }
}
