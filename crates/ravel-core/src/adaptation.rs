//! Retention-constrained adaptation transactions.

use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::reason::RejectionReason;
use ravel_contracts::status::TransactionStatus;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AdaptationError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RawObservation {
    pub adaptation_objective: f64,
    pub base_accuracy: f64,
    pub representation_score: f64,
    pub original_prediction_degradation: f64,
    pub transition_support_losses: i64,
    pub expert_count: i64,
    pub births: i64,
    pub retirements: i64,
    pub replay_records: i64,
    pub update_passes: i64,
    pub compute_evaluations: i64,
    pub matched_compute_evaluations: i64,
    #[serde(default)]
    pub retention_accuracy: Option<f64>,
    #[serde(default)]
    pub retention_accuracy_delta_from_base: Option<f64>,
}

impl RawObservation {
    pub fn validate(&self) -> Result<(), AdaptationError> {
        for (name, value) in [
            ("adaptation_objective", self.adaptation_objective),
            ("base_accuracy", self.base_accuracy),
            ("representation_score", self.representation_score),
            (
                "original_prediction_degradation",
                self.original_prediction_degradation,
            ),
        ] {
            require_finite(value, name)?;
        }
        if let Some(value) = self.retention_accuracy {
            require_finite(value, "retention_accuracy")?;
        }
        if let Some(value) = self.retention_accuracy_delta_from_base {
            require_finite(value, "retention_accuracy_delta_from_base")?;
        }
        for (name, value) in [
            ("transition_support_losses", self.transition_support_losses),
            ("expert_count", self.expert_count),
            ("births", self.births),
            ("retirements", self.retirements),
            ("replay_records", self.replay_records),
            ("update_passes", self.update_passes),
            ("compute_evaluations", self.compute_evaluations),
            (
                "matched_compute_evaluations",
                self.matched_compute_evaluations,
            ),
        ] {
            require_nonnegative(value, name)?;
        }
        Ok(())
    }

    pub fn to_value(&self) -> Value {
        json!({
            "adaptation_objective": self.adaptation_objective,
            "base_accuracy": self.base_accuracy,
            "representation_score": self.representation_score,
            "original_prediction_degradation": self.original_prediction_degradation,
            "transition_support_losses": self.transition_support_losses,
            "expert_count": self.expert_count,
            "births": self.births,
            "retirements": self.retirements,
            "replay_records": self.replay_records,
            "update_passes": self.update_passes,
            "compute_evaluations": self.compute_evaluations,
            "matched_compute_evaluations": self.matched_compute_evaluations,
            "retention_accuracy": self.retention_accuracy,
            "retention_accuracy_delta_from_base": self.retention_accuracy_delta_from_base,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RetentionConstraintPolicy {
    pub adaptation_improvement_epsilon: f64,
    pub base_accuracy_floor: f64,
    pub representation_floor: f64,
    pub original_prediction_degradation_bound: f64,
    pub maximum_transition_support_losses: i64,
    pub maximum_experts: i64,
    pub maximum_births: i64,
    pub maximum_retirements: i64,
    pub maximum_replay_records: i64,
    pub maximum_update_passes: i64,
    pub maximum_compute_evaluations: Option<i64>,
    pub maximum_compute_ratio: f64,
    #[serde(default)]
    pub retention_accuracy_floor: Option<f64>,
    #[serde(default)]
    pub retention_loss_floor: Option<f64>,
    #[serde(default)]
    pub exact_replay_records: Option<i64>,
}

impl RetentionConstraintPolicy {
    pub fn validate(&self) -> Result<(), AdaptationError> {
        for (name, value) in [
            (
                "adaptation_improvement_epsilon",
                self.adaptation_improvement_epsilon,
            ),
            ("base_accuracy_floor", self.base_accuracy_floor),
            ("representation_floor", self.representation_floor),
            (
                "original_prediction_degradation_bound",
                self.original_prediction_degradation_bound,
            ),
            ("maximum_compute_ratio", self.maximum_compute_ratio),
        ] {
            let finite = require_finite(value, name)?;
            if finite < 0.0 {
                return Err(AdaptationError::Invalid(format!(
                    "{name} must be non-negative"
                )));
            }
        }
        for (name, value) in [
            (
                "maximum_transition_support_losses",
                self.maximum_transition_support_losses,
            ),
            ("maximum_experts", self.maximum_experts),
            ("maximum_births", self.maximum_births),
            ("maximum_retirements", self.maximum_retirements),
            ("maximum_replay_records", self.maximum_replay_records),
            ("maximum_update_passes", self.maximum_update_passes),
        ] {
            require_nonnegative(value, name)?;
        }
        if let Some(value) = self.maximum_compute_evaluations {
            require_nonnegative(value, "maximum_compute_evaluations")?;
        }
        if let Some(value) = self.exact_replay_records {
            require_nonnegative(value, "exact_replay_records")?;
        }
        if let Some(value) = self.retention_accuracy_floor {
            require_finite(value, "retention_accuracy_floor")?;
            if value < 0.0 {
                return Err(AdaptationError::Invalid(
                    "retention_accuracy_floor must be non-negative".into(),
                ));
            }
        }
        if let Some(value) = self.retention_loss_floor {
            require_finite(value, "retention_loss_floor")?;
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConstraintReport {
    pub passed: bool,
    pub rejection_reasons: Vec<String>,
}

impl ConstraintReport {
    pub fn to_value(&self) -> Value {
        json!({
            "passed": self.passed,
            "rejection_reasons": self.rejection_reasons,
        })
    }
}

pub fn evaluate_constraints(
    previous: &RawObservation,
    proposed: &RawObservation,
    policy: &RetentionConstraintPolicy,
) -> Result<ConstraintReport, AdaptationError> {
    previous.validate()?;
    proposed.validate()?;
    policy.validate()?;
    let mut reasons = Vec::new();
    if proposed.adaptation_objective - previous.adaptation_objective
        < policy.adaptation_improvement_epsilon
    {
        reasons.push(RejectionReason::ADAPTATION_IMPROVEMENT_BELOW_EPSILON.into());
    }
    if proposed.base_accuracy < policy.base_accuracy_floor {
        reasons.push(RejectionReason::BASE_ACCURACY_FLOOR.into());
    }
    if proposed.representation_score < policy.representation_floor {
        reasons.push(RejectionReason::REPRESENTATION_FLOOR.into());
    }
    if proposed.original_prediction_degradation > policy.original_prediction_degradation_bound {
        reasons.push(RejectionReason::ORIGINAL_PREDICTION_DEGRADATION_BOUND.into());
    }
    if let (Some(floor), Some(value)) =
        (policy.retention_accuracy_floor, proposed.retention_accuracy)
        && value < floor
    {
        reasons.push(RejectionReason::RETENTION_ACCURACY_FLOOR.into());
    }
    if let (Some(floor), Some(value)) = (
        policy.retention_loss_floor,
        proposed.retention_accuracy_delta_from_base,
    ) && value < floor
    {
        reasons.push(RejectionReason::RETENTION_LOSS_FLOOR.into());
    }
    if proposed.transition_support_losses > policy.maximum_transition_support_losses {
        reasons.push(RejectionReason::TRANSITION_SUPPORT_PRESERVATION.into());
    }
    if proposed.expert_count > policy.maximum_experts {
        reasons.push(RejectionReason::EXPERT_CAPACITY_BUDGET.into());
    }
    if proposed.births > policy.maximum_births {
        reasons.push(RejectionReason::BIRTH_BUDGET.into());
    }
    if proposed.retirements > policy.maximum_retirements {
        reasons.push(RejectionReason::RETIREMENT_BUDGET.into());
    }
    if let Some(exact) = policy.exact_replay_records {
        if proposed.replay_records != exact {
            reasons.push(RejectionReason::REPLAY_BUDGET.into());
        }
    } else if proposed.replay_records > policy.maximum_replay_records {
        reasons.push(RejectionReason::REPLAY_BUDGET.into());
    }
    if proposed.update_passes > policy.maximum_update_passes {
        reasons.push(RejectionReason::UPDATE_PASS_BUDGET.into());
    }
    if let Some(maximum) = policy.maximum_compute_evaluations
        && proposed.compute_evaluations > maximum
    {
        reasons.push(RejectionReason::COMPUTE_BUDGET.into());
    }
    if proposed.matched_compute_evaluations == 0 {
        reasons.push(RejectionReason::MATCHED_COMPUTE_REFERENCE_UNAVAILABLE.into());
    } else if (proposed.compute_evaluations as f64) / (proposed.matched_compute_evaluations as f64)
        > policy.maximum_compute_ratio
    {
        reasons.push(RejectionReason::MATCHED_COMPUTE_RATIO.into());
    }
    Ok(ConstraintReport {
        passed: reasons.is_empty(),
        rejection_reasons: reasons,
    })
}

#[derive(Debug, Clone, PartialEq)]
pub struct AdaptationTransaction {
    pub status: TransactionStatus,
    pub state_before: Vec<u8>,
    pub state_after: Vec<u8>,
    pub observation: RawObservation,
    pub report: ConstraintReport,
    pub checkpoint_before_sha256: String,
    pub checkpoint_after_sha256: String,
}

impl AdaptationTransaction {
    pub fn rolled_back_byte_identical(&self) -> bool {
        self.status == TransactionStatus::Rejected && self.state_before == self.state_after
    }

    pub fn to_value(&self) -> Value {
        json!({
            "status": self.status.as_str(),
            "state_before_sha256": self.checkpoint_before_sha256,
            "state_after_sha256": self.checkpoint_after_sha256,
            "observation": self.observation.to_value(),
            "constraints": self.report.to_value(),
            "rolled_back_byte_identical": self.rolled_back_byte_identical(),
        })
    }
}

pub fn run_transaction(
    previous_state: &[u8],
    previous_observation: &RawObservation,
    candidate_state: &[u8],
    proposed_observation: RawObservation,
    policy: &RetentionConstraintPolicy,
) -> Result<AdaptationTransaction, AdaptationError> {
    let report = evaluate_constraints(previous_observation, &proposed_observation, policy)?;
    let before = previous_state.to_vec();
    let after = if report.passed {
        candidate_state.to_vec()
    } else {
        before.clone()
    };
    let status = if report.passed {
        TransactionStatus::Accepted
    } else {
        TransactionStatus::Rejected
    };
    Ok(AdaptationTransaction {
        status,
        checkpoint_before_sha256: hex_sha256(&before),
        checkpoint_after_sha256: hex_sha256(&after),
        state_before: before,
        state_after: after,
        observation: proposed_observation,
        report,
    })
}

pub fn canonical_transaction_json(
    transaction: &AdaptationTransaction,
) -> Result<String, AdaptationError> {
    Ok(canonical_json(&transaction.to_value())?)
}

fn require_finite(value: f64, name: &str) -> Result<f64, AdaptationError> {
    if !value.is_finite() {
        return Err(AdaptationError::Invalid(format!("{name} must be finite")));
    }
    Ok(value)
}

fn require_nonnegative(value: i64, name: &str) -> Result<i64, AdaptationError> {
    if value < 0 {
        return Err(AdaptationError::Invalid(format!(
            "{name} must be non-negative"
        )));
    }
    Ok(value)
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    fn observation() -> RawObservation {
        RawObservation {
            adaptation_objective: 10.0,
            base_accuracy: 0.95,
            representation_score: 0.90,
            original_prediction_degradation: 0.25,
            transition_support_losses: 0,
            expert_count: 70,
            births: 2,
            retirements: 1,
            replay_records: 256,
            update_passes: 1,
            compute_evaluations: 100,
            matched_compute_evaluations: 100,
            retention_accuracy: None,
            retention_accuracy_delta_from_base: None,
        }
    }

    fn policy() -> RetentionConstraintPolicy {
        RetentionConstraintPolicy {
            adaptation_improvement_epsilon: 0.05,
            base_accuracy_floor: 0.85,
            representation_floor: 0.80,
            original_prediction_degradation_bound: 1.0,
            maximum_transition_support_losses: 0,
            maximum_experts: 80,
            maximum_births: 16,
            maximum_retirements: 4,
            maximum_replay_records: 256,
            maximum_update_passes: 2,
            maximum_compute_evaluations: Some(110),
            maximum_compute_ratio: 1.10,
            retention_accuracy_floor: None,
            retention_loss_floor: None,
            exact_replay_records: None,
        }
    }

    #[test]
    fn all_constraints_accept_and_commit_candidate_bytes() {
        let mut proposed = observation();
        proposed.adaptation_objective = 10.10;
        let transaction = run_transaction(
            b"checkpoint-before",
            &observation(),
            b"checkpoint-before-candidate",
            proposed,
            &policy(),
        )
        .expect("transaction");
        assert_eq!(transaction.status, TransactionStatus::Accepted);
        assert_eq!(transaction.state_after, b"checkpoint-before-candidate");
        assert!(transaction.report.rejection_reasons.is_empty());
    }

    #[test]
    fn each_hard_constraint_has_a_distinct_reason() {
        #[allow(clippy::type_complexity)]
        let cases: [(&str, fn(&mut RawObservation)); 12] = [
            (
                RejectionReason::ADAPTATION_IMPROVEMENT_BELOW_EPSILON,
                |item| {
                    item.adaptation_objective = 10.01;
                },
            ),
            (RejectionReason::BASE_ACCURACY_FLOOR, |item| {
                item.base_accuracy = 0.84;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::REPRESENTATION_FLOOR, |item| {
                item.representation_score = 0.79;
                item.adaptation_objective = 10.10;
            }),
            (
                RejectionReason::ORIGINAL_PREDICTION_DEGRADATION_BOUND,
                |item| {
                    item.original_prediction_degradation = 1.01;
                    item.adaptation_objective = 10.10;
                },
            ),
            (RejectionReason::TRANSITION_SUPPORT_PRESERVATION, |item| {
                item.transition_support_losses = 1;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::EXPERT_CAPACITY_BUDGET, |item| {
                item.expert_count = 81;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::BIRTH_BUDGET, |item| {
                item.births = 17;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::RETIREMENT_BUDGET, |item| {
                item.retirements = 5;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::REPLAY_BUDGET, |item| {
                item.replay_records = 257;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::UPDATE_PASS_BUDGET, |item| {
                item.update_passes = 3;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::COMPUTE_BUDGET, |item| {
                item.compute_evaluations = 111;
                item.adaptation_objective = 10.10;
            }),
            (RejectionReason::MATCHED_COMPUTE_RATIO, |item| {
                item.compute_evaluations = 111;
                item.matched_compute_evaluations = 100;
                item.adaptation_objective = 10.10;
            }),
        ];
        for (reason, mutate) in cases {
            let mut proposed = observation();
            mutate(&mut proposed);
            let report =
                evaluate_constraints(&observation(), &proposed, &policy()).expect("report");
            assert!(
                report.rejection_reasons.iter().any(|item| item == reason),
                "{reason} missing from {:?}",
                report.rejection_reasons
            );
            let transaction = run_transaction(
                b"prior",
                &observation(),
                b"prior-must-not-commit",
                proposed,
                &policy(),
            )
            .expect("transaction");
            assert_eq!(transaction.status, TransactionStatus::Rejected, "{reason}");
            assert!(transaction.rolled_back_byte_identical(), "{reason}");
            assert_eq!(
                transaction.checkpoint_before_sha256, transaction.checkpoint_after_sha256,
                "{reason}"
            );
        }
    }

    #[test]
    fn strong_adaptation_cannot_compensate_for_retention_failure() {
        let mut proposed = observation();
        proposed.adaptation_objective = 1000.0;
        proposed.base_accuracy = 0.1;
        let report = evaluate_constraints(&observation(), &proposed, &policy()).expect("report");
        assert!(!report.passed);
        assert_eq!(
            report.rejection_reasons,
            vec![RejectionReason::BASE_ACCURACY_FLOOR]
        );
    }
}
