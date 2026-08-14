//! Inspectable data-curation reports over typed projections.

use crate::models::{MemoryClass, MemoryRecord};
use crate::store::{ImmutableRecordError, JsonlMemoryStore};
use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::CURATION_REPORT_SCHEMA;
use serde_json::{Value, json};

#[derive(Debug, Clone, PartialEq)]
pub struct CurationReport {
    pub source_count: usize,
    pub negative_count: usize,
    pub proposal_count: usize,
    pub accepted_proposals: usize,
    pub challenged_proposals: usize,
    pub superseded_proposals: usize,
    pub relation_count: usize,
    pub artifact_references: usize,
    pub unresolved_contradictions: usize,
    pub orphan_references: usize,
    pub export_digest: String,
    pub deleted: usize,
}

impl CurationReport {
    pub fn to_value(&self) -> Value {
        json!({
            "schema": CURATION_REPORT_SCHEMA,
            "source_count": self.source_count,
            "negative_count": self.negative_count,
            "proposal_count": self.proposal_count,
            "accepted_proposals": self.accepted_proposals,
            "challenged_proposals": self.challenged_proposals,
            "superseded_proposals": self.superseded_proposals,
            "relation_count": self.relation_count,
            "artifact_references": self.artifact_references,
            "unresolved_contradictions": self.unresolved_contradictions,
            "orphan_references": self.orphan_references,
            "export_digest": self.export_digest,
            "deleted": self.deleted,
        })
    }
}

pub fn curate(store: &JsonlMemoryStore) -> Result<CurationReport, ImmutableRecordError> {
    let sources = store.iter_records(None);
    let known: std::collections::BTreeSet<&str> =
        sources.iter().map(|item| item.record_id.as_str()).collect();
    let negative_count = sources
        .iter()
        .filter(|record| record.memory_class == MemoryClass::Negative)
        .count();
    let proposals = store.proposals();
    let mut accepted = 0usize;
    let mut challenged = 0usize;
    let mut superseded = 0usize;
    for event in store.lifecycle_events() {
        match event.status.as_str() {
            "accepted" => accepted += 1,
            "challenged" => challenged += 1,
            "superseded" => superseded += 1,
            _ => {}
        }
    }
    let relations = store.relation_projection();
    let mut unresolved_contradictions = 0usize;
    let mut orphan_references = 0usize;
    for record in &sources {
        if let Some(targets) = record.relations.get("contradicts") {
            for target in targets {
                if !known.contains(target.as_str()) {
                    unresolved_contradictions += 1;
                    orphan_references += 1;
                }
            }
        }
        for source in &record.source_ids {
            if !known.contains(source.as_str()) {
                orphan_references += 1;
            }
        }
    }
    let artifact_references = sources
        .iter()
        .filter(|item| item.evidence_identity.is_some())
        .count();
    let export = store.export_jsonl()?;
    Ok(CurationReport {
        source_count: sources.len(),
        negative_count,
        proposal_count: proposals.len(),
        accepted_proposals: accepted,
        challenged_proposals: challenged,
        superseded_proposals: superseded,
        relation_count: relations.len(),
        artifact_references,
        unresolved_contradictions,
        orphan_references,
        export_digest: format!("sha256:{}", hex_sha256(export.as_bytes())),
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
