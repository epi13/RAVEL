//! Append-only RAVEL 0.6 candidate-development lifecycle.

use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::LEDGER_SCHEMA;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum LedgerError {
    #[error("{0}")]
    Invalid(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CandidateState {
    #[serde(rename = "created")]
    Created,
    #[serde(rename = "development")]
    Development,
    #[serde(rename = "candidate_frozen")]
    Frozen,
    #[serde(rename = "selection_evaluation")]
    Selection,
    #[serde(rename = "selected")]
    Selected,
    #[serde(rename = "rejected")]
    Rejected,
}

impl CandidateState {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Created => "created",
            Self::Development => "development",
            Self::Frozen => "candidate_frozen",
            Self::Selection => "selection_evaluation",
            Self::Selected => "selected",
            Self::Rejected => "rejected",
        }
    }

    pub fn parse(value: &str) -> Result<Self, LedgerError> {
        match value {
            "created" => Ok(Self::Created),
            "development" => Ok(Self::Development),
            "candidate_frozen" => Ok(Self::Frozen),
            "selection_evaluation" => Ok(Self::Selection),
            "selected" => Ok(Self::Selected),
            "rejected" => Ok(Self::Rejected),
            other => Err(LedgerError::Invalid(format!(
                "unknown candidate state: {other}"
            ))),
        }
    }

    fn allowed_next(self) -> &'static [Self] {
        match self {
            Self::Created => &[Self::Development],
            Self::Development => &[Self::Frozen],
            Self::Frozen => &[Self::Selection],
            Self::Selection => &[Self::Selected, Self::Rejected],
            Self::Selected | Self::Rejected => &[],
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CandidateRecord {
    pub candidate_id: String,
    pub number: i64,
    pub state: CandidateState,
    pub source_identity: Option<String>,
    pub evaluator_identity: Option<String>,
    pub threshold_identity: Option<String>,
    pub development_partition: Option<String>,
    pub selection_partition: Option<String>,
    pub selection_result_ref: Option<String>,
    pub rejection_reasons: Vec<String>,
    pub contamination_flag: bool,
}

pub fn candidate_id(number: i64) -> Result<String, LedgerError> {
    if number < 1 {
        return Err(LedgerError::Invalid(
            "candidate number must be positive".into(),
        ));
    }
    Ok(format!("ravel-0.6-candidate-{number:03}"))
}

pub struct CandidateLedger {
    pub path: PathBuf,
    pub maximum_candidates: i64,
}

impl CandidateLedger {
    pub fn new(path: impl AsRef<Path>, maximum_candidates: i64) -> Result<Self, LedgerError> {
        if maximum_candidates < 1 {
            return Err(LedgerError::Invalid(
                "maximum_candidates must be positive".into(),
            ));
        }
        Ok(Self {
            path: path.as_ref().to_path_buf(),
            maximum_candidates,
        })
    }

    fn events(&self) -> Result<Vec<Value>, LedgerError> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }
        let text = fs::read_to_string(&self.path)?;
        let mut events = Vec::new();
        let mut previous = "0".repeat(64);
        for (index, line) in text.lines().enumerate() {
            let expected = (index as i64) + 1;
            let event: Value = serde_json::from_str(line)
                .map_err(|_| LedgerError::Invalid("ledger contains malformed JSON".into()))?;
            if event.get("sequence").and_then(Value::as_i64) != Some(expected) {
                return Err(LedgerError::Invalid(
                    "ledger sequence has a gap or mutation".into(),
                ));
            }
            if event.get("previous_digest").and_then(Value::as_str) != Some(previous.as_str()) {
                return Err(LedgerError::Invalid("ledger hash chain is broken".into()));
            }
            let Some(object) = event.as_object() else {
                return Err(LedgerError::Invalid(
                    "ledger event must be an object".into(),
                ));
            };
            let digest = object
                .get("record_digest")
                .and_then(Value::as_str)
                .ok_or_else(|| LedgerError::Invalid("ledger record digest mismatch".into()))?;
            let mut unsigned = object.clone();
            unsigned.remove("record_digest");
            let expected_digest = hex_sha256(canonical_json(&Value::Object(unsigned))?.as_bytes());
            if digest != expected_digest {
                return Err(LedgerError::Invalid("ledger record digest mismatch".into()));
            }
            previous = digest.to_string();
            events.push(event);
        }
        Ok(events)
    }

    fn current(&self) -> Result<BTreeMap<String, CandidateRecord>, LedgerError> {
        let mut current = BTreeMap::new();
        for event in self.events()? {
            let identifier = event
                .get("candidate_id")
                .and_then(Value::as_str)
                .ok_or_else(|| LedgerError::Invalid("candidate_id missing".into()))?
                .to_string();
            let payload = event
                .get("payload")
                .and_then(Value::as_object)
                .cloned()
                .unwrap_or_default();
            let previous = current.get(&identifier).cloned();
            let record = CandidateRecord {
                candidate_id: identifier.clone(),
                number: payload
                    .get("number")
                    .and_then(Value::as_i64)
                    .or_else(|| previous.as_ref().map(|item: &CandidateRecord| item.number))
                    .unwrap_or(0),
                state: CandidateState::parse(
                    event
                        .get("state")
                        .and_then(Value::as_str)
                        .ok_or_else(|| LedgerError::Invalid("state missing".into()))?,
                )?,
                source_identity: payload_or_previous(
                    &payload,
                    previous.as_ref(),
                    |item| item.source_identity.clone(),
                    "source_identity",
                ),
                evaluator_identity: payload_or_previous(
                    &payload,
                    previous.as_ref(),
                    |item| item.evaluator_identity.clone(),
                    "evaluator_identity",
                ),
                threshold_identity: payload_or_previous(
                    &payload,
                    previous.as_ref(),
                    |item| item.threshold_identity.clone(),
                    "threshold_identity",
                ),
                development_partition: payload_or_previous(
                    &payload,
                    previous.as_ref(),
                    |item| item.development_partition.clone(),
                    "development_partition",
                ),
                selection_partition: payload_or_previous(
                    &payload,
                    previous.as_ref(),
                    |item| item.selection_partition.clone(),
                    "selection_partition",
                ),
                selection_result_ref: payload_or_previous(
                    &payload,
                    previous.as_ref(),
                    |item| item.selection_result_ref.clone(),
                    "selection_result_ref",
                ),
                rejection_reasons: payload
                    .get("rejection_reasons")
                    .and_then(Value::as_array)
                    .map(|items| {
                        items
                            .iter()
                            .filter_map(Value::as_str)
                            .map(str::to_string)
                            .collect()
                    })
                    .or_else(|| previous.as_ref().map(|item| item.rejection_reasons.clone()))
                    .unwrap_or_default(),
                contamination_flag: payload
                    .get("contamination_flag")
                    .and_then(Value::as_bool)
                    .or_else(|| previous.as_ref().map(|item| item.contamination_flag))
                    .unwrap_or(false),
            };
            current.insert(identifier, record);
        }
        let mut ordered: Vec<CandidateRecord> = current.values().cloned().collect();
        ordered.sort_by_key(|item| item.number);
        for (index, record) in ordered.iter().enumerate() {
            let expected = (index as i64) + 1;
            if record.number != expected || record.candidate_id != candidate_id(expected)? {
                return Err(LedgerError::Invalid(
                    "candidate numbering has a gap or identity mutation".into(),
                ));
            }
        }
        Ok(current)
    }

    pub fn records(&self) -> Result<Vec<CandidateRecord>, LedgerError> {
        let mut records: Vec<_> = self.current()?.into_values().collect();
        records.sort_by_key(|item| item.number);
        Ok(records)
    }

    pub fn get(&self, identifier: &str) -> Result<CandidateRecord, LedgerError> {
        self.current()?
            .remove(identifier)
            .ok_or_else(|| LedgerError::Invalid(format!("unknown candidate: {identifier}")))
    }

    fn append(
        &self,
        identifier: &str,
        state: CandidateState,
        payload: Map<String, Value>,
    ) -> Result<(), LedgerError> {
        let events = self.events()?;
        let current = self.current()?;
        if let Some(previous) = current.get(identifier) {
            if previous.state != state && !previous.state.allowed_next().contains(&state) {
                return Err(LedgerError::Invalid(format!(
                    "invalid candidate transition: {}->{}",
                    previous.state.as_str(),
                    state.as_str()
                )));
            }
        } else if state != CandidateState::Created {
            return Err(LedgerError::Invalid(
                "candidate must be created before a state transition".into(),
            ));
        }
        let previous_digest = events
            .last()
            .and_then(|event| event.get("record_digest").and_then(Value::as_str))
            .unwrap_or("0000000000000000000000000000000000000000000000000000000000000000")
            .to_string();
        let mut event = json!({
            "schema": LEDGER_SCHEMA,
            "sequence": events.len() as i64 + 1,
            "candidate_id": identifier,
            "state": state.as_str(),
            "payload": Value::Object(payload),
            "previous_digest": previous_digest,
        });
        let digest = hex_sha256(canonical_json(&event)?.as_bytes());
        if let Some(object) = event.as_object_mut() {
            object.insert("record_digest".into(), Value::String(digest));
        }
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{}", canonical_json(&event)?)?;
        Ok(())
    }

    pub fn create(
        &self,
        development_partition: &str,
        created_at: &str,
    ) -> Result<CandidateRecord, LedgerError> {
        let records = self.records()?;
        let number = records.len() as i64 + 1;
        if number > self.maximum_candidates {
            return Err(LedgerError::Invalid("candidate limit exceeded".into()));
        }
        let identifier = candidate_id(number)?;
        if records
            .last()
            .is_some_and(|record| record.number != number - 1)
        {
            return Err(LedgerError::Invalid(
                "candidate numbering is not gap-resistant".into(),
            ));
        }
        let mut payload = Map::new();
        payload.insert("number".into(), json!(number));
        payload.insert("development_partition".into(), json!(development_partition));
        payload.insert("created_at".into(), json!(created_at));
        self.append(&identifier, CandidateState::Created, payload)?;
        self.get(&identifier)
    }

    pub fn begin_development(&self, identifier: &str) -> Result<CandidateRecord, LedgerError> {
        if self.get(identifier)?.state != CandidateState::Created {
            return Err(LedgerError::Invalid(
                "candidate cannot re-enter development".into(),
            ));
        }
        self.append(identifier, CandidateState::Development, Map::new())?;
        self.get(identifier)
    }

    pub fn freeze(
        &self,
        identifier: &str,
        source_identity: &str,
        evaluator_identity: &str,
        threshold_identity: &str,
        selection_partition: &str,
    ) -> Result<CandidateRecord, LedgerError> {
        if source_identity.is_empty()
            || evaluator_identity.is_empty()
            || threshold_identity.is_empty()
            || selection_partition.is_empty()
        {
            return Err(LedgerError::Invalid(
                "freeze requires all immutable identities".into(),
            ));
        }
        let record = self.get(identifier)?;
        if record.development_partition.as_deref() == Some(selection_partition) {
            return Err(LedgerError::Invalid(
                "development and selection partitions must differ".into(),
            ));
        }
        let mut payload = Map::new();
        payload.insert("source_identity".into(), json!(source_identity));
        payload.insert("evaluator_identity".into(), json!(evaluator_identity));
        payload.insert("threshold_identity".into(), json!(threshold_identity));
        payload.insert("selection_partition".into(), json!(selection_partition));
        self.append(identifier, CandidateState::Frozen, payload)?;
        self.get(identifier)
    }

    pub fn start_selection(&self, identifier: &str) -> Result<CandidateRecord, LedgerError> {
        self.append(identifier, CandidateState::Selection, Map::new())?;
        self.get(identifier)
    }

    pub fn record_selection(
        &self,
        identifier: &str,
        selected: bool,
        result_ref: &str,
        rejection_reasons: Vec<String>,
        contamination_flag: bool,
    ) -> Result<CandidateRecord, LedgerError> {
        if result_ref.is_empty() {
            return Err(LedgerError::Invalid(
                "selection result reference is required".into(),
            ));
        }
        let state = if selected {
            CandidateState::Selected
        } else {
            CandidateState::Rejected
        };
        let mut payload = Map::new();
        payload.insert("selection_result_ref".into(), json!(result_ref));
        payload.insert("rejection_reasons".into(), json!(rejection_reasons));
        payload.insert("contamination_flag".into(), json!(contamination_flag));
        self.append(identifier, state, payload)?;
        self.get(identifier)
    }

    pub fn append_development_feedback(
        &self,
        identifier: &str,
        result_ref: &str,
    ) -> Result<(), LedgerError> {
        if self.get(identifier)?.state != CandidateState::Development {
            return Err(LedgerError::Invalid(
                "selection or frozen evidence cannot feed the same candidate".into(),
            ));
        }
        if result_ref.is_empty() {
            return Err(LedgerError::Invalid(
                "development result reference is required".into(),
            ));
        }
        let mut payload = Map::new();
        payload.insert("feedback_ref".into(), json!(result_ref));
        self.append(identifier, CandidateState::Development, payload)
    }
}

fn payload_or_previous(
    payload: &Map<String, Value>,
    previous: Option<&CandidateRecord>,
    previous_value: impl Fn(&CandidateRecord) -> Option<String>,
    key: &str,
) -> Option<String> {
    payload
        .get(key)
        .and_then(Value::as_str)
        .map(str::to_string)
        .or_else(|| previous.and_then(previous_value))
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn candidate_numbers_are_sequential_and_freeze_is_immutable() {
        let directory = std::env::temp_dir().join(format!("ravel-ledger-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).expect("dir");
        let ledger = CandidateLedger::new(directory.join("candidates.jsonl"), 8).expect("ledger");
        let candidate = ledger.create("dev-a", "t0").expect("create");
        assert_eq!(candidate.candidate_id, "ravel-0.6-candidate-001");
        ledger
            .begin_development(&candidate.candidate_id)
            .expect("develop");
        ledger
            .append_development_feedback(&candidate.candidate_id, "dev-result-1")
            .expect("feedback");
        let frozen = ledger
            .freeze(
                &candidate.candidate_id,
                "sha256:source",
                "sha256:evaluator",
                "sha256:threshold",
                "selection-a",
            )
            .expect("freeze");
        assert_eq!(frozen.state, CandidateState::Frozen);
        assert!(
            ledger
                .append_development_feedback(&candidate.candidate_id, "must-not-enter")
                .is_err()
        );
        assert_eq!(ledger.records().expect("records").len(), 1);
        let _ = fs::remove_dir_all(&directory);
    }
}
