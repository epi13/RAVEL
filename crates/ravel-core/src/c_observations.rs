//! Portable parser/evaluator for candidate-001 C transaction observations.

use crate::adaptation::{
    ConstraintReport, RawObservation, RetentionConstraintPolicy, evaluate_constraints,
};
use crate::matched_compute::MatchedComputeObservation;
use crate::policy::FrozenRavel06Policy;
use ravel_contracts::Q20;
use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum CObservationError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Adaptation(#[from] crate::adaptation::AdaptationError),
    #[error(transparent)]
    Policy(#[from] crate::policy::PolicyError),
}

#[derive(Debug, Clone, PartialEq)]
pub struct CTransactionObservation {
    pub previous: RawObservation,
    pub proposed: RawObservation,
    pub committed: bool,
    pub threshold_identity: String,
    pub matched_compute_reference_available: bool,
    pub rejection_reason: String,
    pub failed_constraint_mask: i64,
    pub rollback_byte_identical: bool,
}

impl CTransactionObservation {
    pub fn from_value(value: &Value) -> Result<Self, CObservationError> {
        let raw = value.get("raw").and_then(Value::as_object).ok_or_else(|| {
            CObservationError::Invalid("C transaction raw observation is missing".into())
        })?;
        let q20 = |name: &str| -> Result<f64, CObservationError> {
            let number = raw.get(name).and_then(Value::as_i64).ok_or_else(|| {
                CObservationError::Invalid(format!("{name} must be a non-negative integer"))
            })?;
            if number < 0 {
                return Err(CObservationError::Invalid(format!(
                    "{name} must be a non-negative integer"
                )));
            }
            Ok(number as f64 / Q20 as f64)
        };
        let count = |name: &str| -> Result<i64, CObservationError> {
            let number = raw.get(name).and_then(Value::as_i64).ok_or_else(|| {
                CObservationError::Invalid(format!("{name} must be a non-negative integer"))
            })?;
            if number < 0 {
                return Err(CObservationError::Invalid(format!(
                    "{name} must be a non-negative integer"
                )));
            }
            Ok(number)
        };
        let before_representation = q20("representation_before_q20")?;
        let after_representation = q20("representation_after_q20")?;
        let retention_delta = raw
            .get("retention_accuracy_delta_q20")
            .and_then(Value::as_i64)
            .ok_or_else(|| {
                CObservationError::Invalid("retention_accuracy_delta_q20 is malformed".into())
            })?;
        let previous = RawObservation {
            adaptation_objective: q20("objective_before_q20")?,
            base_accuracy: q20("base_accuracy_before_q20")?,
            representation_score: 1.0 / (1.0 + before_representation),
            original_prediction_degradation: 0.0,
            transition_support_losses: 0,
            expert_count: count("expert_count")?,
            births: 0,
            retirements: 0,
            replay_records: 0,
            update_passes: 0,
            compute_evaluations: 0,
            matched_compute_evaluations: 0,
            retention_accuracy: Some(q20("retention_accuracy_before_q20")?),
            retention_accuracy_delta_from_base: Some(0.0),
        };
        let before_prediction = q20("prediction_rmse_before_q20")?;
        let after_prediction = q20("prediction_rmse_after_q20")?;
        let proposed = RawObservation {
            adaptation_objective: q20("objective_after_q20")?,
            base_accuracy: q20("base_accuracy_after_q20")?,
            representation_score: 1.0 / (1.0 + after_representation),
            original_prediction_degradation: (after_prediction - before_prediction).max(0.0),
            transition_support_losses: count("transition_support_losses")?,
            expert_count: count("expert_count")?,
            births: count("births")?,
            retirements: count("retirements")?,
            replay_records: count("replay_records")?,
            update_passes: count("update_passes")?,
            compute_evaluations: count("compute_evaluations")?,
            matched_compute_evaluations: count("matched_compute_evaluations")?,
            retention_accuracy: Some(q20("retention_accuracy_after_q20")?),
            retention_accuracy_delta_from_base: Some(retention_delta as f64 / Q20 as f64),
        };
        let committed = value
            .get("committed")
            .and_then(Value::as_bool)
            .ok_or_else(|| {
                CObservationError::Invalid(
                    "C transaction disposition fields must be boolean".into(),
                )
            })?;
        let rollback = value
            .get("rollback_byte_identical")
            .and_then(Value::as_bool)
            .ok_or_else(|| {
                CObservationError::Invalid(
                    "C transaction disposition fields must be boolean".into(),
                )
            })?;
        let threshold_identity = value
            .get("threshold_identity")
            .and_then(Value::as_str)
            .filter(|item| !item.is_empty())
            .ok_or_else(|| {
                CObservationError::Invalid("C transaction threshold identity is malformed".into())
            })?
            .to_string();
        let matched_compute_reference_available = raw
            .get("matched_compute_reference_available")
            .and_then(Value::as_bool)
            .ok_or_else(|| {
                CObservationError::Invalid(
                    "C transaction compute-reference flag is malformed".into(),
                )
            })?;
        let reason = value
            .get("rejection_reason")
            .and_then(Value::as_str)
            .ok_or_else(|| {
                CObservationError::Invalid("C transaction reason fields are malformed".into())
            })?
            .to_string();
        let mask = value
            .get("failed_constraint_mask")
            .and_then(Value::as_i64)
            .filter(|item| *item >= 0)
            .ok_or_else(|| {
                CObservationError::Invalid("C transaction reason fields are malformed".into())
            })?;
        Ok(Self {
            previous,
            proposed,
            committed,
            threshold_identity,
            matched_compute_reference_available,
            rejection_reason: reason,
            failed_constraint_mask: mask,
            rollback_byte_identical: rollback,
        })
    }

    pub fn evaluate(
        &self,
        policy: &FrozenRavel06Policy,
        matched_compute: Option<&MatchedComputeObservation>,
    ) -> Result<ConstraintReport, CObservationError> {
        if self.threshold_identity != policy.threshold_identity()? {
            return Ok(ConstraintReport {
                passed: false,
                rejection_reasons: vec!["threshold_identity_mismatch".into()],
            });
        }
        let constraint_policy = RetentionConstraintPolicy {
            adaptation_improvement_epsilon: policy.adaptation_epsilon_q20 as f64 / Q20 as f64,
            base_accuracy_floor: policy.base_accuracy_floor_q20 as f64 / Q20 as f64,
            representation_floor: self.previous.representation_score,
            original_prediction_degradation_bound: policy.prediction_degradation_bound_q20 as f64
                / Q20 as f64,
            maximum_transition_support_losses: policy.maximum_transition_support_losses,
            maximum_experts: policy.maximum_experts,
            maximum_births: policy.maximum_births,
            maximum_retirements: policy.maximum_retirements,
            maximum_replay_records: policy.replay_records,
            maximum_update_passes: policy.maximum_update_passes,
            maximum_compute_evaluations: policy.maximum_compute_evaluations,
            maximum_compute_ratio: policy.maximum_compute_ratio_q20 as f64 / Q20 as f64,
            retention_accuracy_floor: Some(policy.retention_accuracy_floor_q20 as f64 / Q20 as f64),
            retention_loss_floor: Some(policy.retention_loss_floor_q20 as f64 / Q20 as f64),
            exact_replay_records: Some(policy.replay_records),
        };
        let mut proposed = self.proposed.clone();
        if let Some(matched) = matched_compute {
            proposed.compute_evaluations = matched.candidate_training_evaluations;
            proposed.matched_compute_evaluations = matched.matched_training_evaluations;
        }
        Ok(evaluate_constraints(
            &self.previous,
            &proposed,
            &constraint_policy,
        )?)
    }
}
