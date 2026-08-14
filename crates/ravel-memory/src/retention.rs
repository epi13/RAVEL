//! Retention rules for source memory. Compaction never deletes history.

use crate::consolidation::{ConsolidationPolicy, MemoryConsolidator};
use crate::models::{ConsolidationProposal, MemoryError, MemoryRecord};
use ravel_contracts::schema::RETENTION_POLICY_SCHEMA;
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
