// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use crate::engine::context::NodeCtx;
use crate::model::schemas::Parent;
use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum JobType {
    Slurm(String),
    Local(u32),
}

impl fmt::Display for JobType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let repr = match self {
            Self::Slurm(job_id) => format!("job_id={job_id}"),
            Self::Local(pid) => format!("pid={pid}"),
        };
        write!(f, "{repr}")
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum Completed {
    Cached,
    Branch(bool),
    Generic,
    OneOf(usize),
    Job(JobType),
}

impl fmt::Display for Completed {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let repr = match self {
            Self::Generic => String::from("Completed"),
            Self::Branch(branch) => format!("Completed ({branch})"),
            Self::OneOf(uid) => format!("Completed ({uid})"),
            Self::Job(job_type) => format!("Completed ({job_type})"),
            Self::Cached => String::from("Completed (cached)"),
        };
        write!(f, "{repr}")
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum Failed {
    Job(JobType),
    Generic,
    FailedToContact(JobType),
}

impl fmt::Display for Failed {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let repr = match self {
            Self::Generic => String::from("Failed"),
            Self::Job(job_type) => format!("Failed ({job_type})"),
            Self::FailedToContact(job_type) => format!("Failed to contact ({job_type})"),
        };
        write!(f, "{repr}")
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum Status {
    /// Node not submitted yet.
    NotSubmitted,
    /// Node ready for submission.
    ReadyForSubmission,
    /// Node submitted but not running
    Pending(JobType),
    /// Task is running (contains the Slurm jobid).
    Running(JobType),
    /// Node completed.
    Completed(Completed),
    /// Node skipped (e.g., because of a branch).
    Skipped,
    /// Node execution failed.
    Failed(Failed),
}

impl Default for Status {
    fn default() -> Self {
        Self::NotSubmitted
    }
}

impl Status {
    pub fn is_final(&self) -> bool {
        matches!(self, Self::Completed(_) | Self::Failed(_) | Self::Skipped)
    }

    pub fn is_running(&self) -> bool {
        matches!(self, Self::Pending(_) | Self::Running(_))
    }

    pub fn is_completed(&self) -> bool {
        matches!(self, Self::Completed(_))
    }

    pub fn has_not_been_submitted(&self) -> bool {
        matches!(self, Self::NotSubmitted | Self::ReadyForSubmission)
    }

    pub fn log_priority(&self) -> u16 {
        match self {
            Status::NotSubmitted => 0,
            Status::ReadyForSubmission => 1,
            Status::Skipped => 2,
            Status::Completed(_) => 3,
            Status::Failed(_) => 4,
            Status::Pending(_) => 5,
            Status::Running(_) => 6,
        }
    }
}

impl fmt::Display for Status {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let repr = match self {
            Self::NotSubmitted => String::from("Not Submitted"),
            Self::ReadyForSubmission => String::from("Ready for Submission"),
            Self::Pending(job_type) => format!("Pending ({job_type})"),
            Self::Running(job_type) => format!("Running ({job_type})"),
            Self::Completed(completed) => completed.to_string(),
            Self::Skipped => String::from("Skipped"),
            Self::Failed(failed) => failed.to_string(),
        };
        write!(f, "{repr}")
    }
}

pub fn is_simulation_completed(nodes: &[NodeCtx]) -> bool {
    nodes.iter().all(|s| s.status.is_final())
}

/// Verify that all parent have completed successfully.
pub fn all_parents_completed(parent_statuses: &[&Status]) -> bool {
    parent_statuses
        .iter()
        .all(|x| matches!(**x, Status::Completed { .. }))
}

pub fn some_parents_failed_or_skipped(parent_statuses: &[&Status]) -> bool {
    parent_statuses
        .iter()
        .any(|x| matches!(**x, Status::Skipped | Status::Failed(_)))
}

pub fn any_node_failed(nodes: &[NodeCtx]) -> bool {
    for node in nodes {
        if matches!(node.status, Status::Failed(_)) {
            return true;
        }
        if node
            .jobs
            .iter()
            .any(|j| matches!(j.status, Status::Failed(_)))
        {
            return true;
        }
    }
    false
}

/// Check if every parent has failed or has been skipped.
pub fn all_parents_failed_or_skipped(parent_statuses: &[&Status]) -> bool {
    parent_statuses
        .iter()
        .all(|x| matches!(**x, Status::Failed(_)) | matches!(**x, Status::Skipped))
}

pub fn find_completed_parent(parents: &[Parent], nodes: &[NodeCtx]) -> Option<usize> {
    for parent in parents {
        if matches!(nodes[parent.uid].status, Status::Completed(_)) {
            return Some(parent.uid);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::context::JobArray;
    use crate::model::schemas::ParentKind;

    #[test]
    fn test_all_completed() {
        let s0 = Status::Completed(Completed::Cached);
        let s1 = Status::Completed(Completed::Generic);
        let s2 = Status::Completed(Completed::Job(JobType::Slurm("123".into())));
        let statuses = vec![&s0, &s1, &s2];

        assert!(all_parents_completed(&statuses));
        assert!(!some_parents_failed_or_skipped(&statuses));
        assert!(!all_parents_failed_or_skipped(&statuses));
    }

    #[test]
    fn test_one_skipped() {
        let s0 = Status::Completed(Completed::Cached);
        let s1 = Status::Skipped;
        let s2 = Status::Completed(Completed::Job(JobType::Slurm("123".into())));
        let statuses = vec![&s0, &s1, &s2];

        assert!(!all_parents_completed(&statuses));
        assert!(some_parents_failed_or_skipped(&statuses));
        assert!(!all_parents_failed_or_skipped(&statuses));
    }

    #[test]
    fn test_all_failed_or_skipped() {
        let s0 = Status::Failed(Failed::Generic);
        let s1 = Status::Skipped;
        let s2 = Status::Failed(Failed::Job(JobType::Slurm("123".into())));
        let statuses = vec![&s0, &s1, &s2];

        assert!(!all_parents_completed(&statuses));
        assert!(some_parents_failed_or_skipped(&statuses));
        assert!(all_parents_failed_or_skipped(&statuses));
    }

    #[test]
    fn test_find_completed_parent_no_parents() {
        let parents = vec![];
        let statuses = vec![];
        assert!(find_completed_parent(&parents, &statuses).is_none())
    }

    #[test]
    fn test_find_completed_parent() {
        let parents = vec![
            Parent {
                uid: 0,
                kind: ParentKind::Logical,
            },
            Parent {
                uid: 2,
                kind: ParentKind::Logical,
            },
        ];

        let mut node_ctxs = vec![NodeCtx::default(); 3];
        node_ctxs[0].status = Status::Completed(Completed::Cached);
        node_ctxs[1].status = Status::Skipped;
        node_ctxs[2].status = Status::Failed(Failed::Generic);
        assert_eq!(find_completed_parent(&parents, &node_ctxs).unwrap(), 0);
    }

    #[test]
    fn test_completed_parent_not_found() {
        let parents = vec![
            Parent {
                uid: 1,
                kind: ParentKind::Logical,
            },
            Parent {
                uid: 2,
                kind: ParentKind::Logical,
            },
        ];

        let mut node_ctxs = vec![NodeCtx::default(); 3];
        node_ctxs[0].status = Status::Completed(Completed::Cached);
        node_ctxs[1].status = Status::Skipped;
        node_ctxs[2].status = Status::Failed(Failed::Generic);

        assert!(find_completed_parent(&parents, &node_ctxs).is_none());
    }

    #[test]
    fn check_simulation_is_completed() {
        let mut node_ctxs = vec![NodeCtx::default(); 3];
        node_ctxs[0].status = Status::Completed(Completed::Generic);
        node_ctxs[1].status = Status::Failed(Failed::Generic);
        node_ctxs[2].status = Status::Skipped;

        assert!(is_simulation_completed(&node_ctxs))
    }

    #[test]
    fn check_simulation_is_not_completed() {
        let mut node_ctxs = vec![NodeCtx::default(); 3];
        node_ctxs[0].status = Status::Running(JobType::Slurm("123".into()));
        node_ctxs[1].status = Status::Failed(Failed::Generic);
        node_ctxs[2].status = Status::Skipped;
        assert!(!is_simulation_completed(&node_ctxs))
    }

    #[test]
    fn test_job_in_array_failed() {
        let mut nodes = vec![NodeCtx::default(); 1];
        nodes[0].status = Status::Running(JobType::Slurm("123".into()));
        nodes[0].jobs = vec![
            JobArray {
                nmiss: 0,
                status: Status::Running(JobType::Slurm("123".into())),
            },
            JobArray {
                nmiss: 0,
                status: Status::Failed(Failed::Job(JobType::Slurm("123".into()))),
            },
        ];

        assert!(any_node_failed(&nodes))
    }
    #[test]
    fn test_job_failed() {
        let mut nodes = vec![NodeCtx::default(); 1];
        nodes[0].status = Status::Failed(Failed::Job(JobType::Slurm("123".into())));
        nodes[0].jobs = vec![JobArray {
            nmiss: 0,
            status: Status::Failed(Failed::Job(JobType::Slurm("123".into()))),
        }];

        assert!(any_node_failed(&nodes))
    }
}
