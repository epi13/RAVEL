//! Development-only matched-compute observations and fail-closed evaluation.

use crate::adaptation::ConstraintReport;
use crate::policy::{FrozenRavel06Policy, load_frozen_policy_from_root};
use ravel_contracts::Q20;
use ravel_contracts::reason::RejectionReason;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::Path;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum MatchedComputeError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Policy(#[from] crate::policy::PolicyError),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MatchedComputeObservation {
    pub candidate_training_evaluations: i64,
    pub matched_training_evaluations: i64,
    pub ratio_q20: i64,
    pub maximum_ratio_q20: i64,
    pub reference_available: bool,
    pub threshold_identity: String,
    pub comparator_identity: String,
    pub partition_identity: String,
}

impl MatchedComputeObservation {
    pub fn from_value(value: &Value) -> Result<Self, MatchedComputeError> {
        let count = |name: &str| -> Result<i64, MatchedComputeError> {
            let result = value.get(name).and_then(Value::as_i64).ok_or_else(|| {
                MatchedComputeError::Invalid(format!("matched-compute field {name} is malformed"))
            })?;
            if result < 0 {
                return Err(MatchedComputeError::Invalid(format!(
                    "matched-compute field {name} is malformed"
                )));
            }
            Ok(result)
        };
        let require_str = |name: &str| -> Result<String, MatchedComputeError> {
            value
                .get(name)
                .and_then(Value::as_str)
                .filter(|item| !item.is_empty())
                .map(str::to_string)
                .ok_or_else(|| {
                    MatchedComputeError::Invalid(format!(
                        "matched-compute {name} identity is malformed"
                    ))
                })
        };
        let result = Self {
            candidate_training_evaluations: count("candidate_training_evaluations")?,
            matched_training_evaluations: count("matched_training_evaluations")?,
            ratio_q20: count("ratio_q20")?,
            maximum_ratio_q20: count("maximum_ratio_q20")?,
            reference_available: value
                .get("reference_available")
                .and_then(Value::as_bool)
                .ok_or_else(|| {
                    MatchedComputeError::Invalid("matched-compute availability is malformed".into())
                })?,
            threshold_identity: require_str("threshold_identity")?,
            comparator_identity: require_str("comparator_identity")?,
            partition_identity: require_str("partition_identity")?,
        };
        let expected = if result.matched_training_evaluations == 0 {
            0
        } else {
            result.candidate_training_evaluations * Q20 / result.matched_training_evaluations
        };
        if result.ratio_q20 != expected {
            return Err(MatchedComputeError::Invalid(
                "matched-compute ratio does not reconstruct from raw counts".into(),
            ));
        }
        Ok(result)
    }

    pub fn evaluate(
        &self,
        policy: &FrozenRavel06Policy,
    ) -> Result<ConstraintReport, MatchedComputeError> {
        let mut reasons = Vec::new();
        if self.threshold_identity != policy.threshold_identity()? {
            reasons.push(RejectionReason::THRESHOLD_IDENTITY_MISMATCH.into());
        }
        if !self.reference_available || self.matched_training_evaluations == 0 {
            reasons.push(RejectionReason::MATCHED_COMPUTE_REFERENCE_UNAVAILABLE.into());
        }
        if self.maximum_ratio_q20 != policy.maximum_compute_ratio_q20 {
            reasons.push(RejectionReason::THRESHOLD_IDENTITY_MISMATCH.into());
        }
        if self.ratio_q20 > policy.maximum_compute_ratio_q20 {
            reasons.push(RejectionReason::MATCHED_COMPUTE_RATIO.into());
        }
        Ok(ConstraintReport {
            passed: reasons.is_empty(),
            rejection_reasons: reasons,
        })
    }

    pub fn evaluate_from_root(&self, root: &Path) -> Result<ConstraintReport, MatchedComputeError> {
        let policy = load_frozen_policy_from_root(root)?;
        self.evaluate(&policy)
    }
}
