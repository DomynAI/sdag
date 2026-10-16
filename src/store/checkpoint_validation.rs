// SPDX-FileCopyrightText: 2026 Domyn
// SPDX-License-Identifier: Apache-2.0

use std::path::{Path, PathBuf};

use crate::engine::context::Ctx;
use crate::model::nodes::Node;
use crate::settings::Cfg;
use crate::store::workdirs::FileNames;

pub struct CheckpointValidator<'a> {
    pub cfg: &'a Cfg,
}

impl<'a> CheckpointValidator<'a> {
    pub fn validate_checkpoint(&self, nodes: &[Node], ctx: &Ctx) -> Result<(), String> {
        self.check_workdirs_exist()?;
        for node in nodes {
            self.check_node_input_meta_output(node, ctx)?;
        }

        Ok(())
    }

    fn check_node_input_meta_output(&self, node: &Node, ctx: &Ctx) -> Result<(), String> {
        match node {
            Node::Task(task) => {
                let status = &ctx.nodes[task.uid].status;
                let path = self.get_node_dir(task.uid);
                if status.is_running() | status.is_completed() {
                    self.check_meta(&path)?;
                    self.check_input(&path)?;
                }
                if status.is_completed() {
                    self.check_output(&path)?;
                }
                Ok(())
            }
            Node::OneOf(oneof) => {
                let status = &ctx.nodes[oneof.uid].status;
                if status.is_completed() {
                    let path = self.get_node_dir(oneof.uid);
                    self.check_meta(&path)?;
                    self.check_input(&path)?;
                    self.check_output(&path)?;
                }
                Ok(())
            }
            Node::Branch(_) | Node::Root(_) | Node::End(_) => Ok(()),
        }
    }

    fn check_workdirs_exist(&self) -> Result<(), String> {
        if !self.cfg.homedir.is_dir() {
            let msg = format!(
                "Home directory '{}' does not exist",
                self.cfg.homedir.to_string_lossy()
            );
            return Err(msg);
        }

        if !self.cfg.cachedir.is_dir() {
            let msg = format!(
                "Caching directory '{}' does not exist",
                self.cfg.cachedir.to_string_lossy()
            );
            return Err(msg);
        }

        if !self.cfg.local_cachedir.is_dir() {
            let msg = format!(
                "Local caching directory '{}' does not exist",
                self.cfg.local_cachedir.to_string_lossy()
            );
            return Err(msg);
        }

        if !self.cfg.dagdir.is_dir() {
            let msg = format!(
                "DAG working directory directory '{}' does not exist",
                self.cfg.dagdir.to_string_lossy()
            );
            return Err(msg);
        }

        Ok(())
    }

    fn check_input(&self, path: &Path) -> Result<(), String> {
        let input_path = path.join(FileNames::Input.as_str());
        if !input_path.is_file() {
            let msg = format!("Input file '{}' not found", input_path.to_string_lossy());
            return Err(msg);
        }
        Ok(())
    }

    fn check_meta(&self, path: &Path) -> Result<(), String> {
        let meta_path = path.join(FileNames::Meta.as_str());
        if !meta_path.is_file() {
            let msg = format!("Metadata file '{}' not found", meta_path.to_string_lossy());
            return Err(msg);
        }
        Ok(())
    }

    fn check_output(&self, path: &Path) -> Result<(), String> {
        let output_path = path.join(FileNames::Output.as_str());
        if !output_path.is_file() {
            let msg = format!("Output file '{}' not found", output_path.to_string_lossy());
            return Err(msg);
        }
        Ok(())
    }

    fn get_node_dir(&self, uid: usize) -> PathBuf {
        self.cfg.dagdir.join(uid.to_string())
    }
}

#[cfg(test)]
mod tests {
    use crate::model::nodes::{OneOf, Root, Task};
    use crate::model::status::{Completed, JobType, Status};

    use super::*;
    use std::env;
    use std::fs;
    use uuid::Uuid;

    pub struct DirCreator {
        pub homedir: PathBuf,
        pub cachedir: PathBuf,
        pub local_cachedir: PathBuf,
        pub dagdir: PathBuf,
    }
    impl DirCreator {
        pub fn new(dag_name: &str, hash: &str) -> Self {
            let homedir = env::temp_dir().join(Uuid::new_v4().to_string());
            let cachedir = homedir.join(".cache").join("global");
            let local_cachedir = homedir.join(".cache").join("local");
            let dagdir = homedir.join(dag_name).join(hash);
            Self {
                homedir,
                cachedir,
                local_cachedir,
                dagdir,
            }
        }

        pub fn create_cachedir(&self) {
            fs::create_dir_all(&self.cachedir).unwrap();
        }

        pub fn create_local_cachedir(&self) {
            fs::create_dir_all(&self.local_cachedir).unwrap();
        }

        pub fn create_dagdir(&self) {
            fs::create_dir_all(&self.dagdir).unwrap();
        }

        pub fn create_nodedir(&self, node_uid: usize) {
            let uid = node_uid.to_string();
            let nodedir = self.dagdir.join(&uid);
            fs::create_dir_all(&nodedir).unwrap();
        }

        pub fn create_meta_file(&self, node_uid: usize) {
            self.create_nodedir(node_uid);
            let uid = node_uid.to_string();
            let meta_fname = FileNames::Meta.as_str();
            let meta_file = self.dagdir.join(&uid).join(meta_fname);
            fs::write(meta_file, "{}").unwrap();
        }

        pub fn create_input_file(&self, node_uid: usize) {
            self.create_nodedir(node_uid);
            let uid = node_uid.to_string();
            let input_fname = FileNames::Input.as_str();
            let input_file = self.dagdir.join(&uid).join(input_fname);
            fs::write(input_file, "{}").unwrap();
        }

        pub fn create_output_file(&self, node_uid: usize) {
            self.create_nodedir(node_uid);
            let uid = node_uid.to_string();
            let output_fname = FileNames::Output.as_str();
            let output_file = self.dagdir.join(&uid).join(output_fname);
            fs::write(output_file, "{}").unwrap();
        }
    }

    fn get_cfg(dir_creator: &DirCreator) -> Cfg {
        let mut cfg = Cfg::default();
        cfg.homedir = dir_creator.homedir.clone();
        cfg.dagdir = dir_creator.dagdir.clone();
        cfg.cachedir = dir_creator.cachedir.clone();
        cfg.local_cachedir = dir_creator.local_cachedir.clone();
        cfg
    }

    fn get_nodes(dag_name: &str) -> Vec<Node> {
        let root = Root {
            uid: 0,
            pipeline_name: dag_name.to_string(),
            parents: vec![],
            children: vec![],
        };
        let oneof = OneOf {
            uid: 2,
            pipeline_name: dag_name.to_string(),
            parents: vec![],
            children: vec![],
            artifacts: vec![],
        };
        let mut task = Task::default();
        task.uid = 1;
        task.pipeline_name = dag_name.to_string();
        vec![Node::Root(root), Node::Task(task), Node::OneOf(oneof)]
    }

    fn get_ctx(nodes: &[Node]) -> Ctx {
        Ctx::new(nodes).unwrap()
    }

    fn get_objects(dag_name: &str, hash: &str) -> (DirCreator, Vec<Node>, Ctx, Cfg) {
        let creator = DirCreator::new(dag_name, hash);
        let nodes = get_nodes(dag_name);
        let ctx = get_ctx(&nodes);
        let cfg = get_cfg(&creator);
        (creator, nodes, ctx, cfg)
    }

    #[test]
    #[should_panic]
    fn test_missing_homedir() {
        let (_, nodes, ctx, cfg) = get_objects("dag", "xyz");
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_missing_cachedir() {
        let (creator, nodes, ctx, cfg) = get_objects("dag", "xyz");
        creator.create_local_cachedir();
        creator.create_meta_file(1);

        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_missing_local_cachedir() {
        let (creator, nodes, ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_meta_file(1);

        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn test_missing_dagdir() {
        let (creator, nodes, ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();

        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    fn validate_correct_not_submitted() {
        let (creator, nodes, ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_dagdir();

        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn validate_running_job_missing_input() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_meta_file(1);

        ctx.nodes[1].status = Status::Running(JobType::Slurm("123".into()));
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn validate_running_job_missing_meta() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_input_file(1);

        ctx.nodes[1].status = Status::Running(JobType::Slurm("123".into()));
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    fn validate_running_job() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_meta_file(1);
        creator.create_input_file(1);

        ctx.nodes[1].status = Status::Running(JobType::Slurm("123".into()));
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn validate_completed_oneof_missing_meta() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_meta_file(1);
        creator.create_input_file(2);
        creator.create_output_file(2);

        ctx.nodes[2].status = Status::Completed(Completed::Generic);
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn validate_completed_oneof_missing_input() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_meta_file(1);
        creator.create_meta_file(2);
        creator.create_output_file(2);

        ctx.nodes[2].status = Status::Completed(Completed::Generic);
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    #[should_panic]
    fn validate_completed_oneof_missing_output() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_meta_file(1);
        creator.create_meta_file(2);
        creator.create_input_file(2);

        ctx.nodes[2].status = Status::Completed(Completed::Generic);
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }

    #[test]
    fn validate_completed_oneof() {
        let (creator, nodes, mut ctx, cfg) = get_objects("dag", "xyz");
        creator.create_cachedir();
        creator.create_local_cachedir();
        creator.create_meta_file(1);
        creator.create_meta_file(2);
        creator.create_input_file(2);
        creator.create_output_file(2);

        ctx.nodes[2].status = Status::Completed(Completed::Generic);
        let validator = CheckpointValidator { cfg: &cfg };
        validator.validate_checkpoint(&nodes, &ctx).unwrap();
    }
}
