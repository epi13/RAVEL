//! Scoped execution experience records for advisory RAVEL memory.

use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::status::EvidenceStatus;
use ravel_memory::{MemoryClass, MemoryError, MemoryRecord};
use serde_json::{Map, Value, json};
use std::collections::BTreeMap;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ExperienceError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Memory(#[from] MemoryError),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
}

#[derive(Debug, Clone, PartialEq)]
pub struct ExperienceRecord {
    pub candidate_id: String,
    pub context_identity: String,
    pub task_environment: String,
    pub requested_strategy: String,
    pub provider_id: String,
    pub verifier_id: String,
    pub raw_result: Map<String, Value>,
    pub formal_disposition: Option<EvidenceStatus>,
    pub adaptation_decision: Option<String>,
    pub rejection_reason: Option<String>,
    pub checkpoint_before: Option<String>,
    pub checkpoint_after: Option<String>,
    pub resource_observations: Map<String, Value>,
    pub provenance: BTreeMap<String, String>,
    pub applicability_scope: BTreeMap<String, String>,
    pub execution_identity: Option<String>,
}

impl ExperienceRecord {
    pub fn validate(&self) -> Result<(), ExperienceError> {
        if self.candidate_id.is_empty()
            || self.context_identity.is_empty()
            || self.task_environment.is_empty()
        {
            return Err(ExperienceError::Invalid(
                "candidate, context, and task identities are required".into(),
            ));
        }
        Ok(())
    }

    pub fn negative(&self) -> bool {
        matches!(
            self.formal_disposition,
            Some(EvidenceStatus::Fail | EvidenceStatus::Unknown)
        ) || self.adaptation_decision.as_deref() == Some("rejected")
    }

    pub fn record_id(&self) -> String {
        match &self.execution_identity {
            Some(identity) => format!(
                "experience:{}:{}:{identity}",
                self.candidate_id, self.context_identity
            ),
            None => format!("experience:{}:{}", self.candidate_id, self.context_identity),
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn from_development_transaction(
        candidate_id: &str,
        context_identity: &str,
        task_environment: &str,
        provider_id: &str,
        transaction: &Value,
        matched_compute: Option<&Value>,
        partition_identity: &str,
        provenance: BTreeMap<String, String>,
    ) -> Result<Self, ExperienceError> {
        let committed = transaction
            .get("committed")
            .and_then(Value::as_bool)
            .ok_or_else(|| {
                ExperienceError::Invalid(
                    "development transaction committed flag is malformed".into(),
                )
            })?;
        let mut raw_result = Map::new();
        raw_result.insert("transaction".into(), transaction.clone());
        if let Some(matched) = matched_compute {
            raw_result.insert("matched_compute".into(), matched.clone());
        }
        let execution_identity =
            hex_sha256(canonical_json(&Value::Object(raw_result.clone()))?.as_bytes())
                .chars()
                .take(24)
                .collect();
        let record = Self {
            candidate_id: candidate_id.to_string(),
            context_identity: context_identity.to_string(),
            task_environment: task_environment.to_string(),
            requested_strategy: "retention-constrained-adaptation".into(),
            provider_id: provider_id.to_string(),
            verifier_id: "development-raw-observation".into(),
            raw_result,
            formal_disposition: Some(EvidenceStatus::Unknown),
            adaptation_decision: Some(if committed { "accepted" } else { "rejected" }.into()),
            rejection_reason: if committed {
                None
            } else {
                transaction
                    .get("rejection_reason")
                    .and_then(Value::as_str)
                    .map(str::to_string)
            },
            checkpoint_before: None,
            checkpoint_after: None,
            resource_observations: Map::new(),
            provenance,
            applicability_scope: BTreeMap::from([(
                "partition".into(),
                partition_identity.to_string(),
            )]),
            execution_identity: Some(execution_identity),
        };
        record.validate()?;
        Ok(record)
    }

    pub fn from_fabric_observation(
        observation: &Value,
        partition_identity: &str,
    ) -> Result<Self, ExperienceError> {
        for key in ["candidate_identity", "workload_identity", "fabric_outcome"] {
            if !observation
                .get(key)
                .and_then(Value::as_str)
                .is_some_and(|item| !item.is_empty())
            {
                return Err(ExperienceError::Invalid(
                    "Fabric observation identity or outcome is malformed".into(),
                ));
            }
        }
        let candidate_id = observation["candidate_identity"]
            .as_str()
            .unwrap_or_default();
        let workload_identity = observation["workload_identity"]
            .as_str()
            .unwrap_or_default();
        let provider_id = observation
            .get("provider_identity")
            .and_then(Value::as_str)
            .filter(|item| !item.is_empty())
            .unwrap_or("unknown-provider");
        let mut references = Map::new();
        for key in [
            "workload_identity",
            "candidate_binding_identity",
            "request_identity",
            "worker_identity",
            "fabric_record_identity",
            "receipt_identity",
            "bundle_identity",
            "bundle_archive_identity",
            "fabric_manifest_identity",
            "challenge_identity",
            "replay_identity",
        ] {
            if let Some(value) = observation.get(key).and_then(Value::as_str) {
                references.insert(key.to_string(), Value::String(value.to_string()));
            }
        }
        let reason_codes = observation
            .get("reason_codes")
            .cloned()
            .unwrap_or_else(|| json!([]));
        let raw_result = Map::from_iter([
            ("fabric_reference".into(), Value::Object(references.clone())),
            (
                "fabric_outcome".into(),
                observation["fabric_outcome"].clone(),
            ),
            ("reason_codes".into(), reason_codes),
            (
                "semantics".into(),
                json!("development observation; not evaluator authority"),
            ),
        ]);
        let receipt = references
            .get("receipt_identity")
            .and_then(Value::as_str)
            .map(str::to_string);
        let fabric_record = references
            .get("fabric_record_identity")
            .and_then(Value::as_str)
            .map(str::to_string);
        let execution_identity = receipt
            .clone()
            .or(fabric_record.clone())
            .unwrap_or_else(|| workload_identity.to_string());
        let mut provenance = BTreeMap::new();
        provenance.insert(
            "fabric_record_identity".into(),
            fabric_record.unwrap_or_default(),
        );
        provenance.insert("receipt_identity".into(), receipt.unwrap_or_default());
        provenance.insert(
            "bundle_identity".into(),
            references
                .get("bundle_identity")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string(),
        );
        let mut scope = BTreeMap::new();
        scope.insert("partition".into(), partition_identity.to_string());
        scope.insert("visibility".into(), "development-visible".into());
        scope.insert("authority".into(), "development-only".into());
        scope.insert(
            "worker".into(),
            references
                .get("worker_identity")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .to_string(),
        );
        let resource_observations = observation
            .get("resource_observations")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default();
        let record = Self {
            candidate_id: candidate_id.to_string(),
            context_identity: workload_identity.to_string(),
            task_environment: "mncs-fabric".into(),
            requested_strategy: "fabric-development-execution".into(),
            provider_id: provider_id.to_string(),
            verifier_id: "fabric-execution-observation".into(),
            raw_result,
            formal_disposition: Some(EvidenceStatus::Unknown),
            adaptation_decision: None,
            rejection_reason: None,
            checkpoint_before: None,
            checkpoint_after: None,
            resource_observations,
            provenance,
            applicability_scope: scope,
            execution_identity: Some(execution_identity),
        };
        record.validate()?;
        Ok(record)
    }

    pub fn to_memory_record(&self, created_at: &str) -> Result<MemoryRecord, ExperienceError> {
        self.validate()?;
        let mut scope = self.applicability_scope.clone();
        scope.insert("candidate".into(), self.candidate_id.clone());
        scope.insert("context".into(), self.context_identity.clone());
        let disposition = self
            .formal_disposition
            .map(|item| item.as_str().to_string())
            .unwrap_or_else(|| "unadjudicated".into());
        let statement = format!(
            "{} on {} returned {disposition} via {}.",
            self.requested_strategy, self.task_environment, self.provider_id
        );
        let mut record = MemoryRecord::new(
            self.record_id(),
            if self.negative() {
                MemoryClass::Negative
            } else {
                MemoryClass::Episodic
            },
            statement,
            scope,
            created_at,
            "ravel-experience",
        )?;
        if self.negative() {
            record.relations.insert("contradicts".into(), Vec::new());
        }
        record.tags = vec![
            self.task_environment.clone(),
            self.requested_strategy.clone(),
            self.verifier_id.clone(),
        ];
        record.metadata = Map::from_iter([
            ("raw_result".into(), Value::Object(self.raw_result.clone())),
            (
                "adaptation_decision".into(),
                match &self.adaptation_decision {
                    Some(value) => Value::String(value.clone()),
                    None => Value::Null,
                },
            ),
            (
                "rejection_reason".into(),
                match &self.rejection_reason {
                    Some(value) => Value::String(value.clone()),
                    None => Value::Null,
                },
            ),
            (
                "resource_observations".into(),
                Value::Object(self.resource_observations.clone()),
            ),
        ]);
        record.evidence_identity = self.provenance.get("evidence_identity").cloned();
        record.experience_identity = Some(self.record_id());
        Ok(record)
    }
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn unknown_and_rejected_experience_becomes_negative_memory() {
        let experience = ExperienceRecord {
            candidate_id: "ravel-0.6-candidate-001".into(),
            context_identity: "toy-a".into(),
            task_environment: "toy-environment".into(),
            requested_strategy: "sequential-cpu".into(),
            provider_id: "fake-provider".into(),
            verifier_id: "forge-verifier".into(),
            raw_result: Map::from_iter([("oom".into(), json!(true))]),
            formal_disposition: Some(EvidenceStatus::Unknown),
            adaptation_decision: Some("rejected".into()),
            rejection_reason: Some("compute_budget".into()),
            checkpoint_before: None,
            checkpoint_after: None,
            resource_observations: Map::new(),
            provenance: BTreeMap::new(),
            applicability_scope: BTreeMap::from([("hardware".into(), "cpu-only".into())]),
            execution_identity: None,
        };
        let record = experience
            .to_memory_record("2026-08-08T00:00:00Z")
            .expect("memory");
        assert_eq!(record.memory_class, MemoryClass::Negative);
        assert_eq!(
            record.experience_identity.as_deref(),
            Some(experience.record_id().as_str())
        );
        assert!(record.statement.contains("UNKNOWN"));
    }

    #[test]
    fn fabric_pass_is_retained_as_advisory_unknown() {
        let observation = json!({
            "candidate_identity": "ravel-0.6-candidate-001",
            "workload_identity": "ravel-fabric-workload-demo",
            "fabric_outcome": "PASS",
            "provider_identity": "ravel-toy-branching/1",
            "receipt_identity": "sha256:receipt",
            "fabric_record_identity": "sha256:record",
            "bundle_identity": "sha256:bundle",
            "worker_identity": "local-a",
        });
        let experience = ExperienceRecord::from_fabric_observation(
            &observation,
            "ravel-0.6-development-adaptation-v1",
        )
        .expect("fabric");
        assert_eq!(experience.formal_disposition, Some(EvidenceStatus::Unknown));
        assert!(experience.negative());
        assert_eq!(experience.task_environment, "mncs-fabric");
        let record = experience
            .to_memory_record("2026-08-08T00:00:00Z")
            .expect("memory");
        assert_eq!(record.memory_class, MemoryClass::Negative);
        assert_eq!(
            experience
                .applicability_scope
                .get("authority")
                .map(String::as_str),
            Some("development-only")
        );
        assert_eq!(
            record.scope.get("authority").map(String::as_str),
            Some("development-only")
        );
    }
}
