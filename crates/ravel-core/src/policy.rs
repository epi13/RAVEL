//! Validated, immutable policy extraction for the RAVEL 0.6 development epoch.

use crate::repository::discover_repository_root;
use ravel_contracts::Q20;
use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::{
    EXPECTED_05_PREREGISTRATION_SHA256, EXPECTED_06_PREREGISTRATION_SHA256,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::fs;
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum PolicyError {
    #[error("{0}")]
    Invalid(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FrozenRavel06Policy {
    pub preregistration_id: String,
    pub preregistration_sha256: String,
    pub inherited_05_preregistration_sha256: String,
    pub adaptation_epsilon_q20: i64,
    pub base_accuracy_floor_q20: i64,
    pub retention_accuracy_floor_q20: i64,
    pub retention_loss_floor_q20: i64,
    pub prediction_degradation_bound_q20: i64,
    pub maximum_transition_support_losses: i64,
    pub maximum_experts: i64,
    pub maximum_births: i64,
    pub maximum_retirements: i64,
    pub replay_records: i64,
    pub maximum_update_passes: i64,
    pub maximum_compute_evaluations: Option<i64>,
    pub maximum_compute_ratio_q20: i64,
    pub maximum_candidate_identities: i64,
    pub representation_floor_mode: String,
}

impl FrozenRavel06Policy {
    pub fn contract_value(&self) -> Value {
        json!({
            "preregistration_id": self.preregistration_id,
            "preregistration_sha256": self.preregistration_sha256,
            "inherited_05_preregistration_sha256": self.inherited_05_preregistration_sha256,
            "adaptation_epsilon_q20": self.adaptation_epsilon_q20,
            "base_accuracy_floor_q20": self.base_accuracy_floor_q20,
            "retention_accuracy_floor_q20": self.retention_accuracy_floor_q20,
            "retention_loss_floor_q20": self.retention_loss_floor_q20,
            "prediction_degradation_bound_q20": self.prediction_degradation_bound_q20,
            "maximum_transition_support_losses": self.maximum_transition_support_losses,
            "maximum_experts": self.maximum_experts,
            "maximum_births": self.maximum_births,
            "maximum_retirements": self.maximum_retirements,
            "replay_records": self.replay_records,
            "maximum_update_passes": self.maximum_update_passes,
            "maximum_compute_evaluations": self.maximum_compute_evaluations,
            "maximum_compute_ratio_q20": self.maximum_compute_ratio_q20,
            "maximum_candidate_identities": self.maximum_candidate_identities,
            "representation_floor_mode": self.representation_floor_mode,
        })
    }

    pub fn threshold_identity(&self) -> Result<String, PolicyError> {
        let digest = hex_sha256(&canonical_json(&self.contract_value())?.into_bytes());
        Ok(format!("ravel-0.6-frozen-policy/{digest}"))
    }

    pub fn to_value(&self) -> Result<Value, PolicyError> {
        let mut value = self.contract_value();
        if let Some(object) = value.as_object_mut() {
            object.insert(
                "threshold_identity".into(),
                Value::String(self.threshold_identity()?),
            );
        }
        Ok(value)
    }
}

pub fn load_frozen_policy_from_paths(
    preregistration_path: &Path,
    inherited_05_path: &Path,
) -> Result<FrozenRavel06Policy, PolicyError> {
    let preregistration_bytes = fs::read(preregistration_path)?;
    let preregistration_sha = hex_sha256(&preregistration_bytes);
    if preregistration_sha != EXPECTED_06_PREREGISTRATION_SHA256 {
        return Err(PolicyError::Invalid(format!(
            "RAVEL 0.6 preregistration identity mismatch: expected {EXPECTED_06_PREREGISTRATION_SHA256}, got {preregistration_sha}"
        )));
    }
    let inherited_bytes = fs::read(inherited_05_path)?;
    let inherited_sha = hex_sha256(&inherited_bytes);
    if inherited_sha != EXPECTED_05_PREREGISTRATION_SHA256 {
        return Err(PolicyError::Invalid(format!(
            "inherited RAVEL 0.5 policy identity mismatch: expected {EXPECTED_05_PREREGISTRATION_SHA256}, got {inherited_sha}"
        )));
    }
    let prereg: Value = serde_json::from_slice(&preregistration_bytes)?;
    let inherited: Value = serde_json::from_slice(&inherited_bytes)?;
    if prereg.get("status").and_then(Value::as_str) != Some("PREREGISTERED_BEFORE_IMPLEMENTATION") {
        return Err(PolicyError::Invalid(
            "RAVEL 0.6 preregistration status is not frozen".into(),
        ));
    }
    if prereg.get("normative_for_epoch") != Some(&Value::Bool(true)) {
        return Err(PolicyError::Invalid(
            "RAVEL 0.6 preregistration is not normative for its epoch".into(),
        ));
    }
    let mechanism = required_object(&prereg, "mechanism")?;
    let budget = required_nested_object(mechanism, "budget")?;
    let hard_gates = required_object(&prereg, "hard_gates")?;
    let common = required_array(hard_gates, "common")?;
    let mut gates = serde_json::Map::new();
    for gate in common {
        if let Some(gate_id) = gate.get("gate_id").and_then(Value::as_str) {
            gates.insert(gate_id.to_string(), gate.clone());
        }
    }
    for gate_id in [
        "base_holdout_accuracy",
        "base_holdout_retention",
        "retention_loss_floor",
        "old_prediction_retention",
        "transition_unique_support",
        "matched_compute_budget",
    ] {
        if !gates.contains_key(gate_id) {
            return Err(PolicyError::Invalid(format!(
                "frozen common gate is missing: {gate_id}"
            )));
        }
    }
    let inherited_constants = required_object(&inherited, "mechanism_constants")?;
    let inherited_epsilon = inherited_constants
        .get("topology_objective_min_q20")
        .and_then(Value::as_i64)
        .filter(|value| *value >= 0)
        .ok_or_else(|| {
            PolicyError::Invalid("frozen 0.5 inherited objective epsilon is malformed".into())
        })?;
    Ok(FrozenRavel06Policy {
        preregistration_id: required_str(&prereg, "preregistration_id")?,
        preregistration_sha256: preregistration_sha,
        inherited_05_preregistration_sha256: inherited_sha,
        adaptation_epsilon_q20: inherited_epsilon,
        base_accuracy_floor_q20: q20_from_gate(&gates, "base_holdout_accuracy", "ge")?,
        retention_accuracy_floor_q20: q20_from_gate(&gates, "base_holdout_retention", "ge")?,
        retention_loss_floor_q20: q20_from_gate(&gates, "retention_loss_floor", "ge")?,
        prediction_degradation_bound_q20: q20_from_gate(&gates, "old_prediction_retention", "le")?,
        maximum_transition_support_losses: q20_from_gate(
            &gates,
            "transition_unique_support",
            "eq",
        )?,
        maximum_experts: required_i64(budget, "maximum_experts")?,
        maximum_births: required_i64(budget, "maximum_births_per_trial")?,
        maximum_retirements: required_i64(budget, "maximum_retirements_per_trial")?,
        replay_records: required_i64(budget, "replay_records")?,
        maximum_update_passes: required_i64(budget, "maximum_objective_tested_update_passes")?,
        maximum_compute_evaluations: None,
        maximum_compute_ratio_q20: q20_from_gate(&gates, "matched_compute_budget", "le")?,
        maximum_candidate_identities: required_i64(budget, "maximum_candidate_identities")?,
        representation_floor_mode: "non_decreasing_from_previous_checkpoint".into(),
    })
}

pub fn load_frozen_policy() -> Result<FrozenRavel06Policy, PolicyError> {
    let root = discover_repository_root().ok_or_else(|| {
        PolicyError::Invalid("RAVEL repository root could not be discovered".into())
    })?;
    load_frozen_policy_from_root(&root)
}

pub fn load_frozen_policy_from_root(root: &Path) -> Result<FrozenRavel06Policy, PolicyError> {
    load_frozen_policy_from_paths(
        &root.join("ravel_versions/0.6/ravel-0.6-preregistration.json"),
        &root.join("ravel_versions/0.5/ravel-0.5-preregistration.json"),
    )
}

pub fn default_policy_paths(root: &Path) -> (PathBuf, PathBuf) {
    (
        root.join("ravel_versions/0.6/ravel-0.6-preregistration.json"),
        root.join("ravel_versions/0.5/ravel-0.5-preregistration.json"),
    )
}

pub fn policy_c_header(policy: &FrozenRavel06Policy) -> Result<String, PolicyError> {
    let maximum_compute = match policy.maximum_compute_evaluations {
        None => "UINT64_MAX".to_string(),
        Some(value) => format!("UINT64_C({value})"),
    };
    Ok([
        "/* generated from frozen RAVEL 0.6 policy; do not edit */".to_string(),
        format!(
            "#define RAVEL06_THRESHOLD_IDENTITY \"{}\"",
            policy.threshold_identity()?
        ),
        format!(
            "#define RAVEL06_OBJECTIVE_EPSILON_Q20 UINT64_C({})",
            policy.adaptation_epsilon_q20
        ),
        format!(
            "#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_C({})",
            policy.base_accuracy_floor_q20
        ),
        format!(
            "#define RAVEL06_RETENTION_ACCURACY_FLOOR_Q20 UINT64_C({})",
            policy.retention_accuracy_floor_q20
        ),
        format!(
            "#define RAVEL06_RETENTION_LOSS_FLOOR_Q20 INT64_C({})",
            policy.retention_loss_floor_q20
        ),
        format!(
            "#define RAVEL06_PREDICTION_DEGRADATION_BOUND_Q20 UINT64_C({})",
            policy.prediction_degradation_bound_q20
        ),
        format!(
            "#define RAVEL06_MAX_TRANSITION_SUPPORT_LOSSES {}u",
            policy.maximum_transition_support_losses
        ),
        format!("#define RAVEL06_MAX_EXPERTS {}u", policy.maximum_experts),
        format!("#define RAVEL06_MAX_BIRTHS {}u", policy.maximum_births),
        format!(
            "#define RAVEL06_MAX_RETIREMENTS {}u",
            policy.maximum_retirements
        ),
        format!("#define RAVEL06_REPLAY_RECORDS {}u", policy.replay_records),
        format!(
            "#define RAVEL06_MAX_UPDATE_PASSES {}u",
            policy.maximum_update_passes
        ),
        format!("#define RAVEL06_MAX_COMPUTE_EVALUATIONS {maximum_compute}"),
        format!(
            "#define RAVEL06_MAX_COMPUTE_RATIO_Q20 UINT64_C({})",
            policy.maximum_compute_ratio_q20
        ),
    ]
    .join("\n"))
}

fn required_object<'a>(
    value: &'a Value,
    key: &str,
) -> Result<&'a serde_json::Map<String, Value>, PolicyError> {
    value
        .get(key)
        .and_then(Value::as_object)
        .ok_or_else(|| PolicyError::Invalid(format!("frozen policy field is missing: {key}")))
}

fn required_nested_object<'a>(
    value: &'a serde_json::Map<String, Value>,
    key: &str,
) -> Result<&'a serde_json::Map<String, Value>, PolicyError> {
    value
        .get(key)
        .and_then(Value::as_object)
        .ok_or_else(|| PolicyError::Invalid(format!("frozen policy field is missing: {key}")))
}

fn required_array<'a>(
    value: &'a serde_json::Map<String, Value>,
    key: &str,
) -> Result<&'a Vec<Value>, PolicyError> {
    value
        .get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| PolicyError::Invalid(format!("frozen policy field is missing: {key}")))
}

fn required_str(value: &Value, key: &str) -> Result<String, PolicyError> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| PolicyError::Invalid(format!("frozen policy field is missing: {key}")))
}

fn required_i64(value: &serde_json::Map<String, Value>, key: &str) -> Result<i64, PolicyError> {
    value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| PolicyError::Invalid(format!("frozen policy field is missing: {key}")))
}

fn q20_from_gate(
    gates: &serde_json::Map<String, Value>,
    gate_id: &str,
    operator: &str,
) -> Result<i64, PolicyError> {
    let gate = gates
        .get(gate_id)
        .ok_or_else(|| PolicyError::Invalid(format!("frozen common gate is missing: {gate_id}")))?;
    if gate.get("operator").and_then(Value::as_str) != Some(operator) {
        return Err(PolicyError::Invalid(format!(
            "frozen gate {gate_id} has unexpected operator/value"
        )));
    }
    let value = gate.get("value").ok_or_else(|| {
        PolicyError::Invalid(format!(
            "frozen gate {gate_id} has unexpected operator/value"
        ))
    })?;
    if value.is_boolean() {
        return Err(PolicyError::Invalid(format!(
            "frozen gate {gate_id} has unexpected operator/value"
        )));
    }
    let text = match value {
        Value::Number(number) => number.to_string(),
        _ => {
            return Err(PolicyError::Invalid(format!(
                "frozen gate {gate_id} has unexpected operator/value"
            )));
        }
    };
    q20_from_decimal_str(&text).map_err(|_| {
        PolicyError::Invalid(format!(
            "frozen gate {gate_id} has unexpected operator/value"
        ))
    })
}

/// Python `Decimal(text) * Q20` with `ROUND_HALF_UP` (half away from zero).
pub fn q20_from_decimal_str(text: &str) -> Result<i64, PolicyError> {
    let trimmed = text.trim();
    let (negative, rest) = if let Some(rest) = trimmed.strip_prefix('-') {
        (true, rest)
    } else {
        (false, trimmed.trim_start_matches('+'))
    };
    let (int_part, frac_part) = match rest.split_once('.') {
        Some((left, right)) => (left, right),
        None => (rest, ""),
    };
    if int_part.is_empty() || !int_part.chars().all(|ch| ch.is_ascii_digit()) {
        return Err(PolicyError::Invalid("malformed decimal".into()));
    }
    if !frac_part.chars().all(|ch| ch.is_ascii_digit()) {
        return Err(PolicyError::Invalid("malformed decimal".into()));
    }
    let integer: i128 = if int_part.is_empty() {
        0
    } else {
        int_part
            .parse()
            .map_err(|_| PolicyError::Invalid("malformed decimal".into()))?
    };
    let frac_len = frac_part.len() as u32;
    let denom = 10i128.pow(frac_len);
    let frac: i128 = if frac_part.is_empty() {
        0
    } else {
        frac_part
            .parse()
            .map_err(|_| PolicyError::Invalid("malformed decimal".into()))?
    };
    let numer = integer * denom + frac;
    let product = numer * i128::from(Q20);
    let quotient = product / denom;
    let remainder = product % denom;
    let mut rounded = quotient;
    if remainder * 2 >= denom {
        rounded += 1;
    }
    let signed = if negative { -rounded } else { rounded };
    i64::try_from(signed).map_err(|_| PolicyError::Invalid("q20 overflow".into()))
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn q20_matches_python_decimal_half_up() {
        assert_eq!(q20_from_decimal_str("0.85").expect("q20"), 891290);
        assert_eq!(q20_from_decimal_str("0.9").expect("q20"), 943718);
        assert_eq!(q20_from_decimal_str("-0.1").expect("q20"), -104858);
        assert_eq!(q20_from_decimal_str("1.0").expect("q20"), 1_048_576);
        assert_eq!(q20_from_decimal_str("1.1").expect("q20"), 1_153_434);
    }

    #[test]
    fn frozen_policy_identity_is_stable() {
        let Some(root) = discover_repository_root() else {
            return;
        };
        let policy = load_frozen_policy_from_root(&root).expect("policy");
        assert_eq!(policy.base_accuracy_floor_q20, 891290);
        assert_eq!(policy.retention_accuracy_floor_q20, 943718);
        assert_eq!(policy.retention_loss_floor_q20, -104858);
        assert_eq!(policy.maximum_update_passes, 2);
        assert_eq!(policy.replay_records, 256);
        assert_eq!(policy.maximum_compute_ratio_q20, 1_153_434);
        assert_eq!(policy.maximum_compute_evaluations, None);
        assert_eq!(
            policy.threshold_identity().expect("identity"),
            "ravel-0.6-frozen-policy/a318e03739a6d25bce63117cbf26e19f42b77d07621d26a807052ea97719acc6"
        );
        assert!(
            policy_c_header(&policy)
                .expect("header")
                .contains(&policy.threshold_identity().expect("identity"))
        );
    }
}
