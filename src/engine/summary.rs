// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0
//! Create the summary table out of the nodemap.

use crate::engine::context::Ctx;
use crate::model::nodes::Node;
use tabled::{
    Table, Tabled,
    settings::{Alignment, Style, object::Columns},
};

use crate::model::status::Status;

/// Print the recap table
///
/// It contains the number of tasks ended in each state
pub fn print_recap(nodes: &[Node], ctx: &Ctx) {
    let table = get_final_recap_table(nodes, ctx);
    log::info!("Final recap:\n{}", table)
}

/// Print the summary table
pub fn print_summary(nodes: &[Node], ctx: &Ctx, pipeline_name: &str, hash: &str) {
    let table = get_summary_table(nodes, ctx);
    log::info!(
        "Pipeline '{}' with hash '{}' - Summary:\n{}",
        pipeline_name,
        hash,
        table
    )
}

pub fn get_styled_table<I, T>(records: I) -> Table
where
    I: IntoIterator<Item = T>,
    T: Tabled,
{
    let mut table = Table::new(records);
    table.with(Style::modern());
    table.modify(Columns::first(), Alignment::right());
    table
}

/// Summary table.
#[derive(Tabled)]
struct Summary<'a> {
    /// Node unique id.
    uid: usize,
    /// Task name.
    task: &'a str,
    /// Pipeline
    pipeline: &'a str,
    /// Node status.
    status: &'a Status,
    /// Command or Array
    cmd: String,
    /// Number of tries.
    try_num: usize,
}

/// Build and return the summary table.
fn get_summary_table(nodes: &[Node], ctx: &Ctx) -> Table {
    let mut records = Vec::new();
    for node in nodes {
        if let Node::Task(task) = &node {
            let node_ctx = &ctx.nodes[task.uid];
            if task.each.is_none() || node_ctx.jobs.is_empty() {
                records.push(Summary {
                    uid: task.uid,
                    task: &task.name,
                    pipeline: &task.pipeline_name,
                    cmd: task.cmd.to_string(),
                    status: &node_ctx.status,
                    try_num: node_ctx.try_num,
                });
                continue;
            }
            for (i, job) in node_ctx.jobs.iter().enumerate() {
                records.push(Summary {
                    uid: task.uid,
                    task: &task.name,
                    pipeline: &task.pipeline_name,
                    cmd: format!("array (id={i})"),
                    status: &job.status,
                    try_num: node_ctx.try_num,
                });
            }
        }
    }

    records.sort_by_key(|record| (record.status.log_priority(), record.uid));
    get_styled_table(records)
}

/// Summary table.
#[derive(Tabled)]
struct FinalRecap<'a> {
    /// Task status.
    status: &'a str,
    /// Number of tasks ended in status.
    ntasks: &'a u32,
}

/// Get the recap table
fn get_final_recap_table(nodes: &[Node], ctx: &Ctx) -> Table {
    let mut ncompleted = 0;
    let mut nskipped = 0;
    let mut nfailed = 0;
    let mut npending = 0;
    let mut nrunning = 0;
    let mut nnot_submitted = 0;

    for node in nodes {
        if let Node::Task(task) = &node {
            let status = &ctx.nodes[task.uid].status;
            match &status {
                Status::Completed(_) => ncompleted += 1,
                Status::Skipped => nskipped += 1,
                Status::Failed(_) => {
                    log::warn!("Task '{}' failed", task.uid);
                    nfailed += 1
                }
                Status::Pending(_) => {
                    log::error!("Found running task '{}'", task.uid);
                    npending += 1
                }
                Status::Running(_) => {
                    log::warn!("Found running task '{}'", task.uid);
                    nrunning += 1
                }
                Status::NotSubmitted | Status::ReadyForSubmission => {
                    log::warn!("Task '{}' has not been submitted", task.uid);
                    nnot_submitted += 1
                }
            }
        }
    }

    let records = vec![
        FinalRecap {
            status: "Completed",
            ntasks: &ncompleted,
        },
        FinalRecap {
            status: "Skipped",
            ntasks: &nskipped,
        },
        FinalRecap {
            status: "Failed",
            ntasks: &nfailed,
        },
        FinalRecap {
            status: "Pending",
            ntasks: &npending,
        },
        FinalRecap {
            status: "Running",
            ntasks: &nrunning,
        },
        FinalRecap {
            status: "Not submitted",
            ntasks: &nnot_submitted,
        },
    ];
    get_styled_table(records)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::context::JobArray;
    use crate::model::nodes::Task;
    use crate::model::status::{Completed, Failed, JobType};
    use tabled::assert::assert_table;

    fn get_nodes() -> Vec<Node> {
        let task0 = Task {
            name: "name".into(),
            pipeline_name: "pipeline_name".into(),
            ..Default::default()
        };

        let mut task1 = task0.clone();
        let mut task2 = task0.clone();
        let mut task3 = task0.clone();
        let mut task4 = task0.clone();

        task2.uid = 2;
        task1.uid = 1;
        task3.uid = 3;
        task4.uid = 4;

        vec![
            Node::Task(task0),
            Node::Task(task1),
            Node::Task(task2),
            Node::Task(task3),
            Node::Task(task4),
        ]
    }

    fn get_ctx(nodes: &[Node]) -> Ctx {
        let mut ctx = Ctx::new(nodes).unwrap();
        ctx.nodes[0].try_num = 0;
        ctx.nodes[1].try_num = 1;
        ctx.nodes[2].try_num = 2;
        ctx.nodes[3].try_num = 3;
        ctx.nodes[4].try_num = 4;
        ctx.nodes[0].status = Status::Completed(Completed::Job(JobType::Slurm("123".into())));
        ctx.nodes[1].status = Status::Failed(Failed::Generic);
        ctx.nodes[2].status = Status::Pending(JobType::Slurm("234".into()));
        ctx.nodes[3].status = Status::NotSubmitted;
        ctx.nodes[4].status = Status::Running(JobType::Slurm("456".into()));
        ctx
    }

    #[test]
    fn test_get_summary_table() {
        let nodes = get_nodes();
        let ctx = get_ctx(&nodes);
        let table = get_summary_table(&nodes, &ctx);
        assert_table!(table,
        "┌─────┬──────┬───────────────┬────────────────────────┬──────┬─────────┐"
        "│ uid │ task │ pipeline      │ status                 │ cmd  │ try_num │"
        "├─────┼──────┼───────────────┼────────────────────────┼──────┼─────────┤"
        "│   3 │ name │ pipeline_name │ Not Submitted          │ bash │ 3       │"
        "├─────┼──────┼───────────────┼────────────────────────┼──────┼─────────┤"
        "│   0 │ name │ pipeline_name │ Completed (job_id=123) │ bash │ 0       │"
        "├─────┼──────┼───────────────┼────────────────────────┼──────┼─────────┤"
        "│   1 │ name │ pipeline_name │ Failed                 │ bash │ 1       │"
        "├─────┼──────┼───────────────┼────────────────────────┼──────┼─────────┤"
        "│   2 │ name │ pipeline_name │ Pending (job_id=234)   │ bash │ 2       │"
        "├─────┼──────┼───────────────┼────────────────────────┼──────┼─────────┤"
        "│   4 │ name │ pipeline_name │ Running (job_id=456)   │ bash │ 4       │"
        "└─────┴──────┴───────────────┴────────────────────────┴──────┴─────────┘"
        );
    }

    #[test]
    fn test_get_summary_table_with_array() {
        let task0 = Task {
            name: "name".into(),
            pipeline_name: "pipeline_name".into(),
            ..Default::default()
        };

        let mut task1 = task0.clone();
        task1.uid = 1;
        task1.each = Some("items".into());

        let nodes = vec![Node::Task(task0), Node::Task(task1)];
        let mut ctx = Ctx::new(&nodes).unwrap();
        ctx.nodes[0].status = Status::NotSubmitted;
        ctx.nodes[1].status = Status::Running(JobType::Slurm("456".into()));
        ctx.nodes[1].jobs = vec![
            JobArray {
                nmiss: 0,
                status: Status::Running(JobType::Slurm("456".into())),
            },
            JobArray {
                nmiss: 0,
                status: Status::Failed(Failed::Job(JobType::Slurm("456".into()))),
            },
        ];
        let table = get_summary_table(&nodes, &ctx);
        assert_table!(table,
        "┌─────┬──────┬───────────────┬──────────────────────┬──────────────┬─────────┐"
        "│ uid │ task │ pipeline      │ status               │ cmd          │ try_num │"
        "├─────┼──────┼───────────────┼──────────────────────┼──────────────┼─────────┤"
        "│   0 │ name │ pipeline_name │ Not Submitted        │ bash         │ 0       │"
        "├─────┼──────┼───────────────┼──────────────────────┼──────────────┼─────────┤"
        "│   1 │ name │ pipeline_name │ Failed (job_id=456)  │ array (id=1) │ 0       │"
        "├─────┼──────┼───────────────┼──────────────────────┼──────────────┼─────────┤"
        "│   1 │ name │ pipeline_name │ Running (job_id=456) │ array (id=0) │ 0       │"
        "└─────┴──────┴───────────────┴──────────────────────┴──────────────┴─────────┘"
        );
    }

    #[test]
    fn test_get_final_recap_table() {
        let nodes = get_nodes();
        let ctx = get_ctx(&nodes);
        let table = get_final_recap_table(&nodes, &ctx);
        assert_table!(table,
        "┌───────────────┬────────┐"
        "│        status │ ntasks │"
        "├───────────────┼────────┤"
        "│     Completed │ 1      │"
        "├───────────────┼────────┤"
        "│       Skipped │ 0      │"
        "├───────────────┼────────┤"
        "│        Failed │ 1      │"
        "├───────────────┼────────┤"
        "│       Pending │ 1      │"
        "├───────────────┼────────┤"
        "│       Running │ 1      │"
        "├───────────────┼────────┤"
        "│ Not submitted │ 1      │"
        "└───────────────┴────────┘"
        );
    }
}
