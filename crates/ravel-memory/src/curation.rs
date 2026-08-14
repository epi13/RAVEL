//! Inspectable data-curation reports over append-only stores.

use crate::models::MemoryRecord;
use crate::store::{ImmutableRecordError, JsonlMemoryStore};
use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::CURATION_REPORT_SCHEMA;
use serde_json::{Value, json};

#[derive(Debug, Clone, PartialEq)]
pub struct CurationReport {
    pub source_count: usize,
    pub proposal_count: usize,
    pub relation_count: usize,
    pub export_digest: String,
    pub retained_negative: usize,
    pub deleted: usize,
}

impl CurationReport {
    pub fn to_value(&self) -> Value {
        json!({
            "schema": CURATION_REPORT_SCHEMA,
            "source_count": self.source_count,
            "proposal_count": self.proposal_count,
            "relation_count": self.relation_count,
            "export_digest": self.export_digest,
            "retained_negative": self.retained_negative,
            "deleted": self.deleted,
        })
    }
}

pub fn curate(store: &JsonlMemoryStore) -> Result<CurationReport, ImmutableRecordError> {
    let sources = store.iter_records(None);
    let retained_negative = sources
        .iter()
        .filter(|record| record.memory_class == crate::models::MemoryClass::Negative)
        .count();
    let export = store.export_jsonl()?;
    let relations = store.relation_projection();
    Ok(CurationReport {
        source_count: sources.len(),
        proposal_count: export
            .lines()
            .filter(|line| line.contains("\"proposal_id\""))
            .count(),
        relation_count: relations.len(),
        export_digest: format!("sha256:{}", hex_sha256(export.as_bytes())),
        retained_negative,
        deleted: 0,
    })
}

pub fn curated_export(records: &[MemoryRecord]) -> Result<String, ImmutableRecordError> {
    let mut lines = Vec::new();
    for record in records {
        lines.push(canonical_json(&record.to_value()).map_err(crate::models::MemoryError::from)?);
    }
    if lines.is_empty() {
        Ok(String::new())
    } else {
        Ok(format!("{}\n", lines.join("\n")))
    }
}
