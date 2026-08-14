//! Retention rules and advisory recommendations. RAVEL cannot delete evidence.

use crate::consolidation::{ConsolidationPolicy, MemoryConsolidator};
use crate::models::{ConsolidationProposal, MemoryClass, MemoryError, MemoryRecord};
use crate::store::JsonlMemoryStore;
use ravel_contracts::schema::RETENTION_POLICY_SCHEMA;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

#[derive(Debug, Clone, PartialEq)]
pub struct RetentionPolicy {
    pub retain_negative: bool,
    pub allow_delete: bool,
    pub compact_without_delete: bool,
}

impl Default for RetentionPolicy {
    fn default() -> Self {
        Self {
            retain_negative: true,
            allow_delete: false,
            compact_without_delete: true,
        }
    }
}

impl RetentionPolicy {
    pub fn validate(&self) -> Result<(), MemoryError> {
        if self.allow_delete {
            return Err(MemoryError::Invalid(
                "source memory deletion is not permitted".into(),
            ));
        }
        if !self.retain_negative {
            return Err(MemoryError::Invalid(
                "negative memory must remain retrievable".into(),
            ));
        }
        if !self.compact_without_delete {
            return Err(MemoryError::Invalid(
                "compaction must create summaries without deleting sources".into(),
            ));
        }
        Ok(())
    }

    pub fn to_value(&self) -> Value {
        json!({
            "schema": RETENTION_POLICY_SCHEMA,
            "retain_negative": self.retain_negative,
            "allow_delete": self.allow_delete,
            "compact_without_delete": self.compact_without_delete,
            "authority_to_delete": "none",
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RetentionClass {
    Hot,
    Warm,
    Cold,
    Archive,
    Pinned,
    Regenerable,
    CompactionCandidate,
    GovernedRetention,
    DoNotDelete,
}

impl RetentionClass {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Hot => "hot",
            Self::Warm => "warm",
            Self::Cold => "cold",
            Self::Archive => "archive",
            Self::Pinned => "pinned",
            Self::Regenerable => "regenerable",
            Self::CompactionCandidate => "compaction_candidate",
            Self::GovernedRetention => "governed_retention",
            Self::DoNotDelete => "do_not_delete",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Reconstructability {
    Deterministic,
    ReproducibleWithVariance,
    Partial,
    ExternalDependency,
    NotReconstructable,
    Unknown,
}

impl Reconstructability {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Deterministic => "deterministic",
            Self::ReproducibleWithVariance => "reproducible_with_variance",
            Self::Partial => "partial",
            Self::ExternalDependency => "external_dependency",
            Self::NotReconstructable => "not_reconstructable",
            Self::Unknown => "unknown",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RetentionAdvisory {
    pub subject_id: String,
    pub recommendation: RetentionClass,
    pub reason_codes: Vec<String>,
    pub dependent_record_ids: Vec<String>,
    pub supporting_record_ids: Vec<String>,
    pub contradicting_record_ids: Vec<String>,
    pub reconstructability: Reconstructability,
    pub authority_to_delete: String,
}

impl RetentionAdvisory {
    pub fn to_value(&self) -> Value {
        json!({
            "subject_id": self.subject_id,
            "recommendation": self.recommendation.as_str(),
            "reason_codes": self.reason_codes,
            "dependent_record_ids": self.dependent_record_ids,
            "supporting_record_ids": self.supporting_record_ids,
            "contradicting_record_ids": self.contradicting_record_ids,
            "reconstructability": self.reconstructability.as_str(),
            "authority_to_delete": self.authority_to_delete,
        })
    }
}

pub fn compact(
    records: Vec<MemoryRecord>,
    created_at: &str,
    policy: &RetentionPolicy,
    consolidation: ConsolidationPolicy,
) -> Result<Vec<ConsolidationProposal>, MemoryError> {
    policy.validate()?;
    MemoryConsolidator::new(consolidation)?.propose(records, created_at)
}

pub fn advise_retention(store: &JsonlMemoryStore) -> Vec<RetentionAdvisory> {
    let relations = store.relation_projection();
    store
        .iter_records(None)
        .into_iter()
        .map(|record| {
            let dependents: Vec<String> = relations
                .iter()
                .filter(|(_, _, target)| target == &record.record_id)
                .map(|(source, _, _)| source.clone())
                .collect();
            let contradictions: Vec<String> = record
                .relations
                .get("contradicts")
                .cloned()
                .unwrap_or_default();
            let (recommendation, reason_codes, reconstructability) =
                if record.memory_class == MemoryClass::Negative {
                    (
                        RetentionClass::DoNotDelete,
                        vec!["negative_memory_must_remain_retrievable".into()],
                        Reconstructability::Unknown,
                    )
                } else if !dependents.is_empty() {
                    (
                        RetentionClass::Pinned,
                        vec!["has_dependent_records".into()],
                        Reconstructability::Partial,
                    )
                } else if record.authority_class.rank() >= 2 {
                    (
                        RetentionClass::GovernedRetention,
                        vec!["governed_or_protected_authority".into()],
                        Reconstructability::Unknown,
                    )
                } else {
                    (
                        RetentionClass::Warm,
                        vec!["advisory_source_without_deletion_authority".into()],
                        Reconstructability::Unknown,
                    )
                };
            RetentionAdvisory {
                subject_id: record.record_id.clone(),
                recommendation,
                reason_codes,
                dependent_record_ids: dependents,
                supporting_record_ids: record.source_ids.clone(),
                contradicting_record_ids: contradictions,
                reconstructability,
                authority_to_delete: "none".into(),
            }
        })
        .collect()
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;
    use crate::models::MemoryClass;
    use crate::store::JsonlMemoryStore;
    use std::collections::BTreeMap;

    #[test]
    fn negative_records_are_do_not_delete() {
        let directory = std::env::temp_dir().join(format!("ravel-ret-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).expect("dir");
        let mut store = JsonlMemoryStore::open(directory.join("memory.jsonl")).expect("open");
        let mut scope = BTreeMap::new();
        scope.insert("partition".into(), "dev".into());
        let record = crate::models::MemoryRecord::new(
            "memory:neg",
            MemoryClass::Negative,
            "CUDA execution fails with an out of memory error.",
            scope,
            "t0",
            "test",
        )
        .expect("record");
        store.insert_record(record).expect("insert");
        let advice = advise_retention(&store);
        assert_eq!(advice[0].recommendation, RetentionClass::DoNotDelete);
        assert_eq!(advice[0].authority_to_delete, "none");
        let _ = std::fs::remove_dir_all(&directory);
    }
}
