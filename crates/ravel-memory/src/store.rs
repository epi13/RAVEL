//! File-backed append-only store with Python-compatible retrieval.

use crate::models::{
    ConsolidationProposal, MemoryClass, MemoryError, MemoryRecord, ProposalLifecycleEvent,
};
use ravel_contracts::{canonical_json, digest_canonical};
use serde_json::{Value, json};
use std::collections::{BTreeSet, HashSet};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ImmutableRecordError {
    #[error("record {0:?} already exists with different content")]
    RecordConflict(String),
    #[error("proposal {0:?} already exists with different content")]
    ProposalConflict(String),
    #[error("lifecycle event {0:?} already exists with different content")]
    EventConflict(String),
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Memory(#[from] MemoryError),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone)]
struct StoredRecord {
    record: MemoryRecord,
}

#[derive(Debug, Clone)]
struct StoredProposal {
    proposal: ConsolidationProposal,
}

#[derive(Debug, Clone)]
struct StoredEvent {
    event: ProposalLifecycleEvent,
    digest: String,
}

/// Deterministic JSONL memory store. The on-disk format is a RAVEL contract,
/// not a SQLite compatibility claim.
pub struct JsonlMemoryStore {
    path: PathBuf,
    records: Vec<StoredRecord>,
    proposals: Vec<StoredProposal>,
    events: Vec<StoredEvent>,
}

impl JsonlMemoryStore {
    pub fn open(path: impl AsRef<Path>) -> Result<Self, ImmutableRecordError> {
        let path = path.as_ref().to_path_buf();
        let mut store = Self {
            path,
            records: Vec::new(),
            proposals: Vec::new(),
            events: Vec::new(),
        };
        store.reload()?;
        Ok(store)
    }

    fn reload(&mut self) -> Result<(), ImmutableRecordError> {
        self.records.clear();
        self.proposals.clear();
        self.events.clear();
        if !self.path.exists() {
            return Ok(());
        }
        let file = fs::File::open(&self.path)?;
        for line in BufReader::new(file).lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let value: Value = serde_json::from_str(&line)?;
            match value.get("kind").and_then(Value::as_str) {
                Some("source_record") => {
                    let payload = value.get("payload").ok_or_else(|| {
                        ImmutableRecordError::Invalid("source payload missing".into())
                    })?;
                    self.records.push(StoredRecord {
                        record: MemoryRecord::from_value(payload)?,
                    });
                }
                Some("consolidation_proposal") => {
                    let payload = value.get("payload").ok_or_else(|| {
                        ImmutableRecordError::Invalid("proposal payload missing".into())
                    })?;
                    self.proposals.push(StoredProposal {
                        proposal: proposal_from_value(payload)?,
                    });
                }
                Some("proposal_lifecycle") => {
                    let payload = value.get("payload").ok_or_else(|| {
                        ImmutableRecordError::Invalid("lifecycle payload missing".into())
                    })?;
                    let event = event_from_value(payload)?;
                    let digest = digest_canonical(&event.to_value()).map_err(MemoryError::from)?;
                    self.events.push(StoredEvent { event, digest });
                }
                _ => {
                    return Err(ImmutableRecordError::Invalid(
                        "memory store contains an unknown record kind".into(),
                    ));
                }
            }
        }
        Ok(())
    }

    fn persist(&self) -> Result<(), ImmutableRecordError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&self.path)?;
        let mut sequence = 0u64;
        for item in &self.records {
            sequence += 1;
            let envelope = json!({
                "kind": "source_record",
                "sequence": sequence,
                "payload": item.record.to_value(),
            });
            writeln!(
                file,
                "{}",
                canonical_json(&envelope).map_err(MemoryError::from)?
            )?;
        }
        for item in &self.proposals {
            sequence += 1;
            let envelope = json!({
                "kind": "consolidation_proposal",
                "sequence": sequence,
                "payload": item.proposal.to_value(),
            });
            writeln!(
                file,
                "{}",
                canonical_json(&envelope).map_err(MemoryError::from)?
            )?;
        }
        for item in &self.events {
            sequence += 1;
            let envelope = json!({
                "kind": "proposal_lifecycle",
                "sequence": sequence,
                "payload": item.event.to_value(),
            });
            writeln!(
                file,
                "{}",
                canonical_json(&envelope).map_err(MemoryError::from)?
            )?;
        }
        Ok(())
    }

    pub fn insert_record(&mut self, record: MemoryRecord) -> Result<(), ImmutableRecordError> {
        self.insert_records_atomic(vec![record])
    }

    pub fn insert_records_atomic(
        &mut self,
        records: Vec<MemoryRecord>,
    ) -> Result<(), ImmutableRecordError> {
        for record in &records {
            record.validate()?;
            if let Some(existing) = self
                .records
                .iter()
                .find(|item| item.record.record_id == record.record_id)
                && existing.record.digest()? != record.digest()?
            {
                return Err(ImmutableRecordError::RecordConflict(
                    record.record_id.clone(),
                ));
            }
        }
        for record in records {
            if self
                .records
                .iter()
                .any(|item| item.record.record_id == record.record_id)
            {
                continue;
            }
            self.records.push(StoredRecord { record });
        }
        self.persist()
    }

    pub fn get_record(&self, record_id: &str) -> Option<&MemoryRecord> {
        self.records
            .iter()
            .find(|item| item.record.record_id == record_id)
            .map(|item| &item.record)
    }

    pub fn iter_records(&self, memory_class: Option<MemoryClass>) -> Vec<&MemoryRecord> {
        self.records
            .iter()
            .filter(|item| memory_class.is_none_or(|class| item.record.memory_class == class))
            .map(|item| &item.record)
            .collect()
    }

    pub fn insert_proposal(
        &mut self,
        proposal: ConsolidationProposal,
    ) -> Result<(), ImmutableRecordError> {
        for record_id in &proposal.member_ids {
            if self.get_record(record_id).is_none() {
                return Err(ImmutableRecordError::Invalid(format!(
                    "proposal references missing records: [{record_id:?}]"
                )));
            }
        }
        if let Some(existing) = self
            .proposals
            .iter()
            .find(|item| item.proposal.proposal_id == proposal.proposal_id)
        {
            if existing.proposal.digest()? != proposal.digest()? {
                return Err(ImmutableRecordError::ProposalConflict(
                    proposal.proposal_id.clone(),
                ));
            }
            return Ok(());
        }
        self.proposals.push(StoredProposal { proposal });
        self.persist()
    }

    pub fn insert_proposal_lifecycle(
        &mut self,
        event: ProposalLifecycleEvent,
    ) -> Result<(), ImmutableRecordError> {
        event.validate()?;
        let proposal = self
            .proposals
            .iter()
            .find(|item| item.proposal.proposal_id == event.proposal_id)
            .ok_or_else(|| {
                ImmutableRecordError::Invalid(format!(
                    "proposal does not exist: {}",
                    event.proposal_id
                ))
            })?;
        let mut previous = proposal.proposal.status.as_str();
        if let Some(latest) = self
            .events
            .iter()
            .rev()
            .find(|item| item.event.proposal_id == event.proposal_id)
        {
            previous = latest.event.status.as_str();
        }
        if !allowed_lifecycle(previous).contains(&event.status.as_str()) {
            return Err(ImmutableRecordError::Invalid(format!(
                "invalid proposal lifecycle transition: {previous}->{}",
                event.status
            )));
        }
        let digest = digest_canonical(&event.to_value()).map_err(MemoryError::from)?;
        if let Some(existing) = self
            .events
            .iter()
            .find(|item| item.event.event_id == event.event_id)
        {
            if existing.digest != digest {
                return Err(ImmutableRecordError::EventConflict(event.event_id.clone()));
            }
            return Ok(());
        }
        self.events.push(StoredEvent { event, digest });
        self.persist()
    }

    pub fn search_records(
        &self,
        query: &str,
        memory_class: Option<MemoryClass>,
        include_negative: bool,
    ) -> Vec<(MemoryRecord, i64)> {
        let terms = tokenize(query);
        if terms.is_empty() {
            return Vec::new();
        }
        let mut matches = Vec::new();
        for record in self.iter_records(memory_class) {
            if !include_negative && record.memory_class == MemoryClass::Negative {
                continue;
            }
            let mut haystack = record.statement.clone();
            for tag in &record.tags {
                haystack.push(' ');
                haystack.push_str(tag);
            }
            let haystack = haystack.to_lowercase();
            let score: i64 = terms
                .iter()
                .map(|term| haystack.matches(term.as_str()).count() as i64)
                .sum();
            if score > 0 {
                matches.push((record.clone(), score));
            }
        }
        matches.sort_by(|left, right| {
            right
                .1
                .cmp(&left.1)
                .then_with(|| left.0.record_id.cmp(&right.0.record_id))
        });
        matches
    }

    pub fn relation_projection(&self) -> Vec<(String, String, String)> {
        let mut edges = BTreeSet::new();
        for record in self.iter_records(None) {
            for (relation, targets) in &record.relations {
                for target in targets {
                    edges.insert((record.record_id.clone(), relation.clone(), target.clone()));
                }
            }
        }
        for proposal in &self.proposals {
            let support: HashSet<_> = proposal.proposal.supporting_ids.iter().collect();
            let contradictions: HashSet<_> = proposal.proposal.contradicting_ids.iter().collect();
            let superseded: HashSet<_> = proposal.proposal.superseded_ids.iter().collect();
            for record_id in &proposal.proposal.member_ids {
                let relation = if support.contains(record_id) {
                    "supporting"
                } else if contradictions.contains(record_id) {
                    "contradicting"
                } else if superseded.contains(record_id) {
                    "superseded"
                } else {
                    "member"
                };
                edges.insert((
                    proposal.proposal.proposal_id.clone(),
                    relation.to_string(),
                    record_id.clone(),
                ));
            }
        }
        edges.into_iter().collect()
    }

    pub fn export_jsonl(&self) -> Result<String, ImmutableRecordError> {
        let mut lines = Vec::new();
        for item in &self.records {
            lines.push(canonical_json(&item.record.to_value()).map_err(MemoryError::from)?);
        }
        for item in &self.proposals {
            lines.push(canonical_json(&item.proposal.to_value()).map_err(MemoryError::from)?);
        }
        for item in &self.events {
            lines.push(canonical_json(&item.event.to_value()).map_err(MemoryError::from)?);
        }
        if lines.is_empty() {
            Ok(String::new())
        } else {
            Ok(format!("{}\n", lines.join("\n")))
        }
    }
}

fn tokenize(query: &str) -> Vec<String> {
    let folded = query.to_lowercase();
    let mut terms = BTreeSet::new();
    let mut current = String::new();
    for ch in folded.chars() {
        if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
            current.push(ch);
        } else if !current.is_empty() {
            if current
                .chars()
                .next()
                .is_some_and(|first| first.is_ascii_alphanumeric())
            {
                terms.insert(current.clone());
            }
            current.clear();
        }
    }
    if !current.is_empty()
        && current
            .chars()
            .next()
            .is_some_and(|first| first.is_ascii_alphanumeric())
    {
        terms.insert(current);
    }
    terms.into_iter().collect()
}

fn allowed_lifecycle(previous: &str) -> &'static [&'static str] {
    match previous {
        "proposed" => &["reviewed", "challenged", "superseded"],
        "reviewed" => &["accepted", "challenged", "superseded"],
        "accepted" => &["challenged", "superseded"],
        "challenged" => &["reviewed", "accepted", "superseded"],
        "superseded" => &[],
        _ => &[],
    }
}

fn proposal_from_value(value: &Value) -> Result<ConsolidationProposal, ImmutableRecordError> {
    let object = value
        .as_object()
        .ok_or_else(|| ImmutableRecordError::Invalid("proposal must be an object".into()))?;
    let str_field = |key: &str| -> Result<String, ImmutableRecordError> {
        object
            .get(key)
            .and_then(Value::as_str)
            .map(str::to_string)
            .ok_or_else(|| ImmutableRecordError::Invalid(format!("{key} is required")))
    };
    let list = |key: &str| -> Vec<String> {
        object
            .get(key)
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default()
    };
    let class = object
        .get("memory_class")
        .and_then(Value::as_str)
        .unwrap_or("semantic");
    let memory_class = match class {
        "episodic" => MemoryClass::Episodic,
        "causal" => MemoryClass::Causal,
        "semantic" => MemoryClass::Semantic,
        "procedural" => MemoryClass::Procedural,
        "negative" => MemoryClass::Negative,
        other => {
            return Err(ImmutableRecordError::Invalid(format!(
                "unsupported memory class: {other}"
            )));
        }
    };
    let scope = object
        .get("scope")
        .and_then(Value::as_object)
        .map(|map| {
            map.iter()
                .filter_map(|(key, value)| {
                    value.as_str().map(|text| (key.clone(), text.to_string()))
                })
                .collect()
        })
        .unwrap_or_default();
    Ok(ConsolidationProposal {
        proposal_id: str_field("proposal_id")?,
        method_version: str_field("method_version")?,
        created_at: str_field("created_at")?,
        memory_class,
        canonical_statement: str_field("canonical_statement")?,
        scope,
        member_ids: list("member_ids"),
        supporting_ids: list("supporting_ids"),
        contradicting_ids: list("contradicting_ids"),
        superseded_ids: list("superseded_ids"),
        retrieval_keys: list("retrieval_keys"),
        clustering_confidence: object
            .get("clustering_confidence")
            .and_then(Value::as_f64)
            .unwrap_or(0.0),
        status: object
            .get("status")
            .and_then(Value::as_str)
            .unwrap_or("proposed")
            .to_string(),
        scope_contract_id: object
            .get("scope_contract_id")
            .and_then(Value::as_str)
            .unwrap_or(ravel_contracts::schema::SCOPE_EXACT_CONTRACT)
            .to_string(),
        limitations: list("limitations"),
    })
}

fn event_from_value(value: &Value) -> Result<ProposalLifecycleEvent, ImmutableRecordError> {
    let object = value
        .as_object()
        .ok_or_else(|| ImmutableRecordError::Invalid("lifecycle event must be an object".into()))?;
    let str_field = |key: &str| -> Result<String, ImmutableRecordError> {
        object
            .get(key)
            .and_then(Value::as_str)
            .map(str::to_string)
            .ok_or_else(|| ImmutableRecordError::Invalid(format!("{key} is required")))
    };
    let event = ProposalLifecycleEvent {
        event_id: str_field("event_id")?,
        proposal_id: str_field("proposal_id")?,
        status: str_field("status")?,
        created_at: str_field("created_at")?,
        reason: str_field("reason")?,
    };
    event.validate()?;
    Ok(event)
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    #[test]
    fn search_is_deterministic_and_keeps_negative_records() {
        let directory = std::env::temp_dir().join(format!("ravel-memory-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).expect("temp dir");
        let mut store = JsonlMemoryStore::open(directory.join("memory.jsonl")).expect("open");
        let mut scope = BTreeMap::new();
        scope.insert("partition".into(), "dev".into());
        let mut accepted = MemoryRecord::new(
            "experience:a:accepted",
            MemoryClass::Negative,
            "retention-constrained-adaptation on toy returned UNKNOWN via ravel-candidate.",
            scope.clone(),
            "2026-08-08T00:00:00Z",
            "ravel-experience",
        )
        .expect("record");
        accepted.tags = vec![
            "ravel-toy-branching-c/1".into(),
            "retention-constrained-adaptation".into(),
            "development-raw-observation".into(),
        ];
        let mut rejected = accepted.clone();
        rejected.record_id = "experience:a:rejected".into();
        rejected.statement =
            "retention-constrained-adaptation on toy returned UNKNOWN via ravel-candidate.".into();
        store
            .insert_records_atomic(vec![accepted, rejected])
            .expect("insert");
        let first = store.search_records("retention constrained adaptation", None, true);
        let second = store.search_records("retention constrained adaptation", None, true);
        assert_eq!(first.len(), 2);
        assert_eq!(
            first
                .iter()
                .map(|item| item.0.record_id.clone())
                .collect::<Vec<_>>(),
            second
                .iter()
                .map(|item| item.0.record_id.clone())
                .collect::<Vec<_>>()
        );
        assert!(store.search_records("retention", None, false).is_empty());
        let _ = fs::remove_dir_all(&directory);
    }
}
