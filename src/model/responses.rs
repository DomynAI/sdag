// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Deserializer, Serialize};

fn default_task_id() -> usize {
    0
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SacctTaskId {
    pub set: bool,
    #[serde(default = "default_task_id")]
    pub number: usize,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SacctArray {
    pub task_id: SacctTaskId,
    #[serde(deserialize_with = "job_id_as_string")]
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SacctState {
    pub current: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SacctJob {
    #[serde(deserialize_with = "job_id_as_string")]
    pub job_id: String,
    pub state: SacctState,
    pub array: SacctArray,
}

impl SacctJob {
    pub fn get_job_id(&self) -> &str {
        if self.array.task_id.set {
            &self.array.job_id
        } else {
            &self.job_id
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SacctResponse {
    pub jobs: Vec<SacctJob>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SqueueArrayTaskId {
    #[serde(default = "default_task_id")]
    pub number: usize,
    pub set: bool,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SqueueJob {
    #[serde(deserialize_with = "job_id_as_string")]
    pub job_id: String,
    pub job_state: Vec<String>,
    pub array_task_id: SqueueArrayTaskId,
    #[serde(default)]
    pub array_task_string: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SqueueResponse {
    pub jobs: Vec<SqueueJob>,
}

fn job_id_as_string<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: Deserializer<'de>,
{
    let n = serde_json::Number::deserialize(deserializer)?;
    Ok(n.to_string())
}
