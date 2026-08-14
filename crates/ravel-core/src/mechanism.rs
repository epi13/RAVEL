//! State surface that deliberately excludes evaluators and authority.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum MechanismError {
    #[error("mechanism counters must be non-negative")]
    NegativeCounter,
    #[error("expert lineage must be unique")]
    DuplicateLineage,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExpertState {
    pub lineage: String,
    pub labels: Vec<i64>,
    pub supported_actions: Vec<i64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MechanismState {
    pub experts: Vec<ExpertState>,
    #[serde(default)]
    pub epoch: i64,
    #[serde(default)]
    pub births: i64,
    #[serde(default)]
    pub retirements: i64,
}

impl MechanismState {
    pub fn validate(&self) -> Result<(), MechanismError> {
        if self.epoch < 0 || self.births < 0 || self.retirements < 0 {
            return Err(MechanismError::NegativeCounter);
        }
        let lineages: HashSet<&str> = self
            .experts
            .iter()
            .map(|item| item.lineage.as_str())
            .collect();
        if lineages.len() != self.experts.len() {
            return Err(MechanismError::DuplicateLineage);
        }
        Ok(())
    }

    pub fn proposed(
        &self,
        experts: Vec<ExpertState>,
        births: i64,
        retirements: i64,
    ) -> Result<Self, MechanismError> {
        let next = Self {
            experts,
            epoch: self.epoch + 1,
            births: self.births + births,
            retirements: self.retirements + retirements,
        };
        next.validate()?;
        Ok(next)
    }
}
