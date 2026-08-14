//! Authoritative append-only memory log with rebuildable projections.

use crate::models::{
    ConsolidationProposal, MemoryClass, MemoryError, MemoryRecord, ProposalLifecycleEvent,
};
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::MEMORY_LOG_SCHEMA;
use ravel_contracts::{canonical_json, digest_canonical};
use serde_json::{Value, json};
use std::collections::{BTreeSet, HashSet};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use thiserror::Error;

pub const GENESIS_DIGEST: &str = "0000000000000000000000000000000000000000000000000000000000000000";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TailPolicy {
    /// Any malformed or incomplete line fails the load.
    FailClosed,
    /// An incomplete *final* line is ignored and reported; earlier lines stay fail-closed.
    IgnoreIncompleteLastLine,
}

#[derive(Debug, Error)]
pub enum ImmutableRecordError {
    #[error("record {0:?} already exists with different content")]
    RecordConflict(String),
    #[error("proposal {0:?} already exists with different content")]
    ProposalConflict(String),
    #[error("lifecycle event {0:?} already exists with different content")]
    EventConflict(String),
    #[error("memory log is truncated or has an incomplete tail")]
    IncompleteTail,
    #[error("memory log hash chain is broken at sequence {0}")]
    BrokenChain(u64),
    #[error("memory log sequence has a gap or mutation at {0}")]
    SequenceGap(u64),
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Memory(#[from] MemoryError),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone)]
pub struct LogEntry {
    pub sequence: u64,
    pub kind: String,
    pub record_identity: String,
    pub payload: Value,
    pub record_digest: String,
}

/// Deterministic append-only JSONL log. Projections are rebuilt on load.
pub struct JsonlMemoryStore {
    path: PathBuf,
    tail_policy: TailPolicy,
    records: Vec<MemoryRecord>,
    proposals: Vec<ConsolidationProposal>,
    events: Vec<ProposalLifecycleEvent>,
    entries: Vec<LogEntry>,
    next_sequence: u64,
    last_digest: String,
    recovered_incomplete_tail: bool,
}

impl JsonlMemoryStore {
    pub fn open(path: impl AsRef<Path>) -> Result<Self, ImmutableRecordError> {
        Self::open_with(path, TailPolicy::FailClosed)
    }

    pub fn open_with(
        path: impl AsRef<Path>,
        tail_policy: TailPolicy,
    ) -> Result<Self, ImmutableRecordError> {
        let path = path.as_ref().to_path_buf();
        let mut store = Self {
            path,
            tail_policy,
            records: Vec::new(),
            proposals: Vec::new(),
            events: Vec::new(),
            entries: Vec::new(),
            next_sequence: 1,
            last_digest: GENESIS_DIGEST.to_string(),
            recovered_incomplete_tail: false,
        };
        store.reload()?;
        Ok(store)
    }

    pub fn recovered_incomplete_tail(&self) -> bool {
        self.recovered_incomplete_tail
    }

    pub fn last_digest(&self) -> &str {
        &self.last_digest
    }

    pub fn entries(&self) -> &[LogEntry] {
        &self.entries
    }

    pub fn proposals(&self) -> &[ConsolidationProposal] {
        &self.proposals
    }

    pub fn lifecycle_events(&self) -> &[ProposalLifecycleEvent] {
        &self.events
    }

    fn reload(&mut self) -> Result<(), ImmutableRecordError> {
        self.records.clear();
        self.proposals.clear();
        self.events.clear();
        self.entries.clear();
        self.next_sequence = 1;
        self.last_digest = GENESIS_DIGEST.to_string();
        self.recovered_incomplete_tail = false;
        if !self.path.exists() {
            return Ok(());
        }
        let text = fs::read_to_string(&self.path)?;
        if text.is_empty() {
            return Ok(());
        }
        let raw_lines: Vec<&str> = text.lines().collect();
        if raw_lines.is_empty() && !text.trim().is_empty() {
            return self.handle_incomplete(text.trim_end_matches('\n'));
        }
        for (index, line) in raw_lines.iter().enumerate() {
            let is_last = index + 1 == raw_lines.len();
            if line.trim().is_empty() {
                if is_last {
                    continue;
                }
                return Err(ImmutableRecordError::Invalid(
                    "memory log contains an empty historical line".into(),
                ));
            }
            let value = match serde_json::from_str::<Value>(line) {
                Ok(value) => value,
                Err(_) if is_last && !text.ends_with('\n') => {
                    return self.handle_incomplete(line);
                }
                Err(_) if is_last && self.tail_policy == TailPolicy::IgnoreIncompleteLastLine => {
                    self.recovered_incomplete_tail = true;
                    continue;
                }
                Err(_) => {
                    return Err(ImmutableRecordError::Invalid(format!(
                        "memory log contains malformed JSON at sequence {}",
                        index + 1
                    )));
                }
            };
            self.ingest_entry(value, (index as u64) + 1)?;
        }
        Ok(())
    }

    fn handle_incomplete(&mut self, _line: &str) -> Result<(), ImmutableRecordError> {
        match self.tail_policy {
            TailPolicy::FailClosed => Err(ImmutableRecordError::IncompleteTail),
            TailPolicy::IgnoreIncompleteLastLine => {
                self.recovered_incomplete_tail = true;
                Ok(())
            }
        }
    }

    fn ingest_entry(&mut self, value: Value, expected: u64) -> Result<(), ImmutableRecordError> {
        let object = value
            .as_object()
            .ok_or_else(|| ImmutableRecordError::Invalid("log entry must be an object".into()))?;
        if object.get("schema").and_then(Value::as_str) != Some(MEMORY_LOG_SCHEMA) {
            return Err(ImmutableRecordError::Invalid(
                "memory log schema is unsupported or missing".into(),
            ));
        }
        let sequence = object
            .get("sequence")
            .and_then(Value::as_u64)
            .ok_or_else(|| ImmutableRecordError::Invalid("log sequence is required".into()))?;
        if sequence != expected {
            return Err(ImmutableRecordError::SequenceGap(expected));
        }
        let previous = object
            .get("previous_digest")
            .and_then(Value::as_str)
            .ok_or_else(|| ImmutableRecordError::Invalid("previous_digest is required".into()))?;
        if previous != self.last_digest {
            return Err(ImmutableRecordError::BrokenChain(sequence));
        }
        let digest = object
            .get("record_digest")
            .and_then(Value::as_str)
            .ok_or_else(|| ImmutableRecordError::Invalid("record_digest is required".into()))?;
        let mut unsigned = object.clone();
        unsigned.remove("record_digest");
        let expected_digest = hex_sha256(canonical_json(&Value::Object(unsigned))?.as_bytes());
        if digest != expected_digest {
            return Err(ImmutableRecordError::Invalid(
                "log record digest mismatch".into(),
            ));
        }
        let kind = object
            .get("kind")
            .and_then(Value::as_str)
            .ok_or_else(|| ImmutableRecordError::Invalid("log kind is required".into()))?
            .to_string();
        let record_identity = object
            .get("record_identity")
            .and_then(Value::as_str)
            .ok_or_else(|| ImmutableRecordError::Invalid("record_identity is required".into()))?
            .to_string();
        let payload = object
            .get("payload")
            .cloned()
            .ok_or_else(|| ImmutableRecordError::Invalid("payload is required".into()))?;
        self.apply_payload(&kind, &payload)?;
        self.entries.push(LogEntry {
            sequence,
            kind,
            record_identity,
            payload,
            record_digest: digest.to_string(),
        });
        self.last_digest = digest.to_string();
        self.next_sequence = sequence + 1;
        Ok(())
    }

    fn apply_payload(&mut self, kind: &str, payload: &Value) -> Result<(), ImmutableRecordError> {
        match kind {
            "source_record" => {
                let record = MemoryRecord::from_value(payload)?;
                if let Some(existing) = self
                    .records
                    .iter()
                    .find(|item| item.record_id == record.record_id)
                {
                    if existing.digest()? != record.digest()? {
                        return Err(ImmutableRecordError::RecordConflict(record.record_id));
                    }
                    return Ok(());
                }
                self.records.push(record);
            }
            "consolidation_proposal" => {
                let proposal = proposal_from_value(payload)?;
                if let Some(existing) = self
                    .proposals
                    .iter()
                    .find(|item| item.proposal_id == proposal.proposal_id)
                {
                    if existing.digest()? != proposal.digest()? {
                        return Err(ImmutableRecordError::ProposalConflict(proposal.proposal_id));
                    }
                    return Ok(());
                }
                self.proposals.push(proposal);
            }
            "proposal_lifecycle" => {
                let event = event_from_value(payload)?;
                if self
                    .events
                    .iter()
                    .any(|item| item.event_id == event.event_id)
                {
                    return Ok(());
                }
                self.events.push(event);
            }
            other => {
                return Err(ImmutableRecordError::Invalid(format!(
                    "memory store contains an unknown record kind: {other}"
                )));
            }
        }
        Ok(())
    }

    fn append_entry(
        &mut self,
        kind: &str,
        record_identity: &str,
        payload: Value,
    ) -> Result<(), ImmutableRecordError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let sequence = self.next_sequence;
        let payload_digest = digest_canonical(&payload).map_err(MemoryError::from)?;
        let mut unsigned = json!({
            "schema": MEMORY_LOG_SCHEMA,
            "sequence": sequence,
            "kind": kind,
            "record_identity": record_identity,
            "payload": payload,
            "payload_digest": payload_digest,
            "previous_digest": self.last_digest,
        });
        let digest = hex_sha256(canonical_json(&unsigned)?.as_bytes());
        if let Some(object) = unsigned.as_object_mut() {
            object.insert("record_digest".into(), Value::String(digest.clone()));
        }
        let line = format!("{}\n", canonical_json(&unsigned)?);
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        file.write_all(line.as_bytes())?;
        file.sync_all()?;
        self.entries.push(LogEntry {
            sequence,
            kind: kind.to_string(),
            record_identity: record_identity.to_string(),
            payload,
            record_digest: digest.clone(),
        });
        self.last_digest = digest;
        self.next_sequence = sequence + 1;
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
                .find(|item| item.record_id == record.record_id)
                && existing.digest()? != record.digest()?
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
                .any(|item| item.record_id == record.record_id)
            {
                continue;
            }
            let payload = record.to_value();
            let identity = record.record_id.clone();
            self.records.push(record);
            self.append_entry("source_record", &identity, payload)?;
        }
        Ok(())
    }

    pub fn get_record(&self, record_id: &str) -> Option<&MemoryRecord> {
        self.records.iter().find(|item| item.record_id == record_id)
    }

    pub fn iter_records(&self, memory_class: Option<MemoryClass>) -> Vec<&MemoryRecord> {
        self.records
            .iter()
            .filter(|item| memory_class.is_none_or(|class| item.memory_class == class))
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
            .find(|item| item.proposal_id == proposal.proposal_id)
        {
            if existing.digest()? != proposal.digest()? {
                return Err(ImmutableRecordError::ProposalConflict(
                    proposal.proposal_id.clone(),
                ));
            }
            return Ok(());
        }
        let payload = proposal.to_value();
        let identity = proposal.proposal_id.clone();
        self.proposals.push(proposal);
        self.append_entry("consolidation_proposal", &identity, payload)
    }

    pub fn insert_proposal_lifecycle(
        &mut self,
        event: ProposalLifecycleEvent,
    ) -> Result<(), ImmutableRecordError> {
        event.validate()?;
        let proposal = self
            .proposals
            .iter()
            .find(|item| item.proposal_id == event.proposal_id)
            .ok_or_else(|| {
                ImmutableRecordError::Invalid(format!(
                    "proposal does not exist: {}",
                    event.proposal_id
                ))
            })?;
        let mut previous = proposal.status.as_str();
        if let Some(latest) = self
            .events
            .iter()
            .rev()
            .find(|item| item.proposal_id == event.proposal_id)
        {
            previous = latest.status.as_str();
        }
        if !allowed_lifecycle(previous).contains(&event.status.as_str()) {
            return Err(ImmutableRecordError::Invalid(format!(
                "invalid proposal lifecycle transition: {previous}->{}",
                event.status
            )));
        }
        if let Some(existing) = self
            .events
            .iter()
            .find(|item| item.event_id == event.event_id)
        {
            let digest = digest_canonical(&event.to_value()).map_err(MemoryError::from)?;
            let existing_digest =
                digest_canonical(&existing.to_value()).map_err(MemoryError::from)?;
            if digest != existing_digest {
                return Err(ImmutableRecordError::EventConflict(event.event_id.clone()));
            }
            return Ok(());
        }
        let payload = event.to_value();
        let identity = event.event_id.clone();
        self.events.push(event);
        self.append_entry("proposal_lifecycle", &identity, payload)
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
        for record in &self.records {
            for (relation, targets) in &record.relations {
                for target in targets {
                    edges.insert((record.record_id.clone(), relation.clone(), target.clone()));
                }
            }
        }
        for proposal in &self.proposals {
            let support: HashSet<_> = proposal.supporting_ids.iter().collect();
            let contradictions: HashSet<_> = proposal.contradicting_ids.iter().collect();
            let superseded: HashSet<_> = proposal.superseded_ids.iter().collect();
            for record_id in &proposal.member_ids {
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
                    proposal.proposal_id.clone(),
                    relation.to_string(),
                    record_id.clone(),
                ));
            }
        }
        edges.into_iter().collect()
    }

    pub fn reference_projection(&self) -> Vec<(String, String, String)> {
        let mut edges = BTreeSet::new();
        for record in &self.records {
            if let Some(identity) = &record.evidence_identity {
                edges.insert((
                    record.record_id.clone(),
                    "evidence".into(),
                    identity.clone(),
                ));
            }
            if let Some(identity) = &record.experience_identity {
                edges.insert((
                    record.record_id.clone(),
                    "experience".into(),
                    identity.clone(),
                ));
            }
            for source in &record.source_ids {
                edges.insert((record.record_id.clone(), "source".into(), source.clone()));
            }
        }
        for (source, relation, target) in self.relation_projection() {
            edges.insert((source, relation, target));
        }
        edges.into_iter().collect()
    }

    pub fn export_jsonl(&self) -> Result<String, ImmutableRecordError> {
        let mut lines = Vec::new();
        for item in &self.records {
            lines.push(canonical_json(&item.to_value()).map_err(MemoryError::from)?);
        }
        for item in &self.proposals {
            lines.push(canonical_json(&item.to_value()).map_err(MemoryError::from)?);
        }
        for item in &self.events {
            lines.push(canonical_json(&item.to_value()).map_err(MemoryError::from)?);
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
    let list = |key: &str| -> Result<Vec<String>, ImmutableRecordError> {
        match object.get(key) {
            None => Ok(Vec::new()),
            Some(Value::Array(items)) => items
                .iter()
                .map(|item| {
                    item.as_str().map(str::to_string).ok_or_else(|| {
                        ImmutableRecordError::Invalid(format!("{key} entries must be strings"))
                    })
                })
                .collect(),
            Some(_) => Err(ImmutableRecordError::Invalid(format!(
                "{key} must be an array"
            ))),
        }
    };
    let class = object
        .get("memory_class")
        .and_then(Value::as_str)
        .ok_or_else(|| ImmutableRecordError::Invalid("memory_class is required".into()))?;
    let memory_class = MemoryClass::parse(class)?;
    let scope = object
        .get("scope")
        .and_then(Value::as_object)
        .ok_or_else(|| ImmutableRecordError::Invalid("scope is required".into()))?
        .iter()
        .map(|(key, value)| {
            value
                .as_str()
                .map(|text| (key.clone(), text.to_string()))
                .ok_or_else(|| ImmutableRecordError::Invalid("scope values must be strings".into()))
        })
        .collect::<Result<_, _>>()?;
    Ok(ConsolidationProposal {
        proposal_id: str_field("proposal_id")?,
        method_version: str_field("method_version")?,
        created_at: str_field("created_at")?,
        memory_class,
        canonical_statement: str_field("canonical_statement")?,
        scope,
        member_ids: list("member_ids")?,
        supporting_ids: list("supporting_ids")?,
        contradicting_ids: list("contradicting_ids")?,
        superseded_ids: list("superseded_ids")?,
        retrieval_keys: list("retrieval_keys")?,
        clustering_confidence: object
            .get("clustering_confidence")
            .and_then(Value::as_f64)
            .ok_or_else(|| {
                ImmutableRecordError::Invalid("clustering_confidence is required".into())
            })?,
        status: object
            .get("status")
            .and_then(Value::as_str)
            .ok_or_else(|| ImmutableRecordError::Invalid("proposal status is required".into()))?
            .to_string(),
        scope_contract_id: str_field("scope_contract_id")?,
        limitations: list("limitations")?,
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
    use crate::models::MemoryClass;
    use std::collections::BTreeMap;

    fn sample(record_id: &str) -> MemoryRecord {
        let mut scope = BTreeMap::new();
        scope.insert("partition".into(), "dev".into());
        let mut record = MemoryRecord::new(
            record_id,
            MemoryClass::Negative,
            "retention-constrained-adaptation on toy returned UNKNOWN via ravel-candidate.",
            scope,
            "2026-08-08T00:00:00Z",
            "ravel-experience",
        )
        .expect("record");
        record.tags = vec![
            "ravel-toy-branching-c/1".into(),
            "retention-constrained-adaptation".into(),
            "development-raw-observation".into(),
        ];
        record
    }

    #[test]
    fn search_is_deterministic_and_keeps_negative_records() {
        let directory = std::env::temp_dir().join(format!("ravel-memory-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).expect("temp dir");
        let mut store = JsonlMemoryStore::open(directory.join("memory.jsonl")).expect("open");
        store
            .insert_records_atomic(vec![
                sample("experience:a:accepted"),
                sample("experience:a:rejected"),
            ])
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
        let reopened = JsonlMemoryStore::open(directory.join("memory.jsonl")).expect("reopen");
        assert_eq!(reopened.entries().len(), 2);
        assert_eq!(reopened.last_digest().len(), 64);
        let _ = fs::remove_dir_all(&directory);
    }

    #[test]
    fn incomplete_tail_is_fail_closed_unless_explicitly_recovered() {
        let directory =
            std::env::temp_dir().join(format!("ravel-memory-tail-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).expect("temp dir");
        let path = directory.join("memory.jsonl");
        let mut store = JsonlMemoryStore::open(&path).expect("open");
        store.insert_record(sample("memory:1")).expect("insert");
        let mut bytes = fs::read(&path).expect("read");
        bytes.extend_from_slice(b"{\"schema\":\"ravel-memory-log/0.1\"");
        fs::write(&path, bytes).expect("write tail");
        assert!(matches!(
            JsonlMemoryStore::open(&path),
            Err(ImmutableRecordError::IncompleteTail | ImmutableRecordError::Invalid(_))
        ));
        let recovered = JsonlMemoryStore::open_with(&path, TailPolicy::IgnoreIncompleteLastLine)
            .expect("recover");
        assert!(recovered.recovered_incomplete_tail());
        assert_eq!(recovered.iter_records(None).len(), 1);
        let _ = fs::remove_dir_all(&directory);
    }

    #[test]
    fn historical_mutation_breaks_the_hash_chain() {
        let directory =
            std::env::temp_dir().join(format!("ravel-memory-mut-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).expect("temp dir");
        let path = directory.join("memory.jsonl");
        let mut store = JsonlMemoryStore::open(&path).expect("open");
        store.insert_record(sample("memory:1")).expect("insert");
        store.insert_record(sample("memory:2")).expect("insert");
        let text = fs::read_to_string(&path).expect("read");
        let mutated = text.replace("memory:1", "memory:mutated");
        fs::write(&path, mutated).expect("mutate");
        assert!(JsonlMemoryStore::open(&path).is_err());
        let _ = fs::remove_dir_all(&directory);
    }
}
