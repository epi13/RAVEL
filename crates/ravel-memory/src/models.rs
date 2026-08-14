//! Typed, deterministic records for the RAVEL memory prototype.

use ravel_contracts::{
    CanonicalError, canonical_json, digest_canonical, schema::MEMORY_RECORD_SCHEMA,
    schema::SCOPE_EXACT_CONTRACT,
};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::collections::BTreeMap;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum MemoryError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Canonical(#[from] CanonicalError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MemoryClass {
    Episodic,
    Causal,
    Semantic,
    Procedural,
    Negative,
}

impl MemoryClass {
    pub fn parse(value: &str) -> Result<Self, MemoryError> {
        match value {
            "episodic" => Ok(Self::Episodic),
            "causal" => Ok(Self::Causal),
            "semantic" => Ok(Self::Semantic),
            "procedural" => Ok(Self::Procedural),
            "negative" => Ok(Self::Negative),
            other => Err(MemoryError::Invalid(format!(
                "unsupported memory class: {other}"
            ))),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Episodic => "episodic",
            Self::Causal => "causal",
            Self::Semantic => "semantic",
            Self::Procedural => "procedural",
            Self::Negative => "negative",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AuthorityClass {
    Advisory,
    #[serde(rename = "repository-local")]
    RepositoryLocal,
    #[serde(rename = "governed-evaluation")]
    GovernedEvaluation,
    Protected,
}

impl AuthorityClass {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Advisory => "advisory",
            Self::RepositoryLocal => "repository-local",
            Self::GovernedEvaluation => "governed-evaluation",
            Self::Protected => "protected",
        }
    }

    pub fn parse(value: &str) -> Result<Self, MemoryError> {
        match value {
            "advisory" => Ok(Self::Advisory),
            "repository-local" => Ok(Self::RepositoryLocal),
            "governed-evaluation" => Ok(Self::GovernedEvaluation),
            "protected" => Ok(Self::Protected),
            other => Err(MemoryError::Invalid(format!(
                "unsupported authority class: {other}"
            ))),
        }
    }

    pub fn rank(self) -> i32 {
        match self {
            Self::Advisory => 0,
            Self::RepositoryLocal => 1,
            Self::GovernedEvaluation => 2,
            Self::Protected => 3,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RecordStatus {
    Active,
    Retired,
    Rejected,
}

impl RecordStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Active => "active",
            Self::Retired => "retired",
            Self::Rejected => "rejected",
        }
    }

    pub fn parse(value: &str) -> Result<Self, MemoryError> {
        match value {
            "active" => Ok(Self::Active),
            "retired" => Ok(Self::Retired),
            "rejected" => Ok(Self::Rejected),
            other => Err(MemoryError::Invalid(format!(
                "unsupported record status: {other}"
            ))),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScopeCompatibility {
    pub contract_id: String,
    pub equal_fields: Vec<String>,
    pub allow_extra_fields: bool,
}

impl Default for ScopeCompatibility {
    fn default() -> Self {
        Self {
            contract_id: SCOPE_EXACT_CONTRACT.to_string(),
            equal_fields: Vec::new(),
            allow_extra_fields: false,
        }
    }
}

impl ScopeCompatibility {
    pub fn compatible(
        &self,
        left: &BTreeMap<String, String>,
        right: &BTreeMap<String, String>,
    ) -> bool {
        if self.equal_fields.is_empty() {
            return left == right;
        }
        if self
            .equal_fields
            .iter()
            .any(|field| left.get(field) != right.get(field))
        {
            return false;
        }
        self.allow_extra_fields || left.keys().eq(right.keys())
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct MemoryRecord {
    pub record_id: String,
    pub memory_class: MemoryClass,
    pub statement: String,
    pub scope: BTreeMap<String, String>,
    pub created_at: String,
    pub producer_id: String,
    pub authority_class: AuthorityClass,
    pub status: RecordStatus,
    pub tags: Vec<String>,
    pub source_ids: Vec<String>,
    pub relations: BTreeMap<String, Vec<String>>,
    pub metadata: Map<String, Value>,
    pub schema_version: String,
    pub evidence_identity: Option<String>,
    pub experience_identity: Option<String>,
}

impl MemoryRecord {
    pub fn new(
        record_id: impl Into<String>,
        memory_class: MemoryClass,
        statement: impl Into<String>,
        scope: BTreeMap<String, String>,
        created_at: impl Into<String>,
        producer_id: impl Into<String>,
    ) -> Result<Self, MemoryError> {
        let record = Self {
            record_id: record_id.into(),
            memory_class,
            statement: statement.into(),
            scope,
            created_at: created_at.into(),
            producer_id: producer_id.into(),
            authority_class: AuthorityClass::Advisory,
            status: RecordStatus::Active,
            tags: Vec::new(),
            source_ids: Vec::new(),
            relations: BTreeMap::new(),
            metadata: Map::new(),
            schema_version: MEMORY_RECORD_SCHEMA.to_string(),
            evidence_identity: None,
            experience_identity: None,
        };
        record.validate()?;
        Ok(record)
    }

    pub fn validate(&self) -> Result<(), MemoryError> {
        if self.record_id.trim().is_empty() {
            return Err(MemoryError::Invalid("record_id must not be empty".into()));
        }
        if self.statement.trim().is_empty() {
            return Err(MemoryError::Invalid("statement must not be empty".into()));
        }
        if self.scope.is_empty() {
            return Err(MemoryError::Invalid(
                "scope must declare at least one boundary".into(),
            ));
        }
        if self.producer_id.trim().is_empty() {
            return Err(MemoryError::Invalid("producer_id must not be empty".into()));
        }
        if self.schema_version.trim().is_empty() {
            return Err(MemoryError::Invalid(
                "schema_version must not be empty".into(),
            ));
        }
        Ok(())
    }

    pub fn to_value(&self) -> Value {
        let relations: Map<String, Value> = self
            .relations
            .iter()
            .map(|(key, values)| (key.clone(), json!(values)))
            .collect();
        let scope: Map<String, Value> = self
            .scope
            .iter()
            .map(|(key, value)| (key.clone(), Value::String(value.clone())))
            .collect();
        json!({
            "record_id": self.record_id,
            "memory_class": self.memory_class.as_str(),
            "statement": self.statement,
            "scope": Value::Object(scope),
            "created_at": self.created_at,
            "producer_id": self.producer_id,
            "authority_class": self.authority_class.as_str(),
            "status": self.status.as_str(),
            "tags": self.tags,
            "source_ids": self.source_ids,
            "relations": Value::Object(relations),
            "metadata": Value::Object(self.metadata.clone()),
            "schema_version": self.schema_version,
            "evidence_identity": self.evidence_identity,
            "experience_identity": self.experience_identity,
        })
    }

    pub fn digest(&self) -> Result<String, MemoryError> {
        Ok(digest_canonical(&self.to_value())?)
    }

    pub fn from_value(value: &Value) -> Result<Self, MemoryError> {
        let object = value
            .as_object()
            .ok_or_else(|| MemoryError::Invalid("memory record must be an object".into()))?;
        let required_str = |key: &str| -> Result<String, MemoryError> {
            object
                .get(key)
                .and_then(Value::as_str)
                .map(str::to_string)
                .ok_or_else(|| MemoryError::Invalid(format!("{key} is required")))
        };
        let class = object
            .get("memory_class")
            .and_then(Value::as_str)
            .ok_or_else(|| MemoryError::Invalid("memory_class is required".into()))?;
        let memory_class = MemoryClass::parse(class)?;
        let scope = object
            .get("scope")
            .and_then(Value::as_object)
            .ok_or_else(|| MemoryError::Invalid("scope is required".into()))?
            .iter()
            .map(|(key, value)| {
                value
                    .as_str()
                    .map(|text| (key.clone(), text.to_string()))
                    .ok_or_else(|| MemoryError::Invalid("scope values must be strings".into()))
            })
            .collect::<Result<BTreeMap<_, _>, _>>()?;
        let string_list = |key: &str| -> Result<Vec<String>, MemoryError> {
            match object.get(key) {
                None => Ok(Vec::new()),
                Some(Value::Array(items)) => items
                    .iter()
                    .map(|item| {
                        item.as_str().map(str::to_string).ok_or_else(|| {
                            MemoryError::Invalid(format!("{key} entries must be strings"))
                        })
                    })
                    .collect(),
                Some(_) => Err(MemoryError::Invalid(format!("{key} must be an array"))),
            }
        };
        let relations = match object.get("relations") {
            None => BTreeMap::new(),
            Some(Value::Object(map)) => {
                let mut out = BTreeMap::new();
                for (key, value) in map {
                    let Value::Array(items) = value else {
                        return Err(MemoryError::Invalid(
                            "relation values must be string arrays".into(),
                        ));
                    };
                    let values = items
                        .iter()
                        .map(|item| {
                            item.as_str().map(str::to_string).ok_or_else(|| {
                                MemoryError::Invalid("relation targets must be strings".into())
                            })
                        })
                        .collect::<Result<Vec<_>, _>>()?;
                    out.insert(key.clone(), values);
                }
                out
            }
            Some(_) => {
                return Err(MemoryError::Invalid("relations must be an object".into()));
            }
        };
        let metadata = object
            .get("metadata")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default();
        let optional_str = |key: &str| -> Option<String> {
            object.get(key).and_then(Value::as_str).map(str::to_string)
        };
        let record = Self {
            record_id: required_str("record_id")?,
            memory_class,
            statement: required_str("statement")?,
            scope,
            created_at: required_str("created_at")?,
            producer_id: required_str("producer_id")?,
            authority_class: match object.get("authority_class") {
                None => AuthorityClass::Advisory,
                Some(Value::String(value)) => AuthorityClass::parse(value)?,
                Some(_) => {
                    return Err(MemoryError::Invalid(
                        "authority_class must be a string".into(),
                    ));
                }
            },
            status: match object.get("status") {
                None => RecordStatus::Active,
                Some(Value::String(value)) => RecordStatus::parse(value)?,
                Some(_) => return Err(MemoryError::Invalid("status must be a string".into())),
            },
            tags: string_list("tags")?,
            source_ids: string_list("source_ids")?,
            relations,
            metadata,
            schema_version: object
                .get("schema_version")
                .and_then(Value::as_str)
                .unwrap_or(MEMORY_RECORD_SCHEMA)
                .to_string(),
            evidence_identity: optional_str("evidence_identity"),
            experience_identity: optional_str("experience_identity"),
        };
        record.validate()?;
        Ok(record)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ConsolidationProposal {
    pub proposal_id: String,
    pub method_version: String,
    pub created_at: String,
    pub memory_class: MemoryClass,
    pub canonical_statement: String,
    pub scope: BTreeMap<String, String>,
    pub member_ids: Vec<String>,
    pub supporting_ids: Vec<String>,
    pub contradicting_ids: Vec<String>,
    pub superseded_ids: Vec<String>,
    pub retrieval_keys: Vec<String>,
    pub clustering_confidence: f64,
    pub status: String,
    pub scope_contract_id: String,
    pub limitations: Vec<String>,
}

impl ConsolidationProposal {
    pub fn to_value(&self) -> Value {
        let scope: Map<String, Value> = self
            .scope
            .iter()
            .map(|(key, value)| (key.clone(), Value::String(value.clone())))
            .collect();
        json!({
            "proposal_id": self.proposal_id,
            "method_version": self.method_version,
            "created_at": self.created_at,
            "memory_class": self.memory_class.as_str(),
            "canonical_statement": self.canonical_statement,
            "scope": Value::Object(scope),
            "member_ids": self.member_ids,
            "supporting_ids": self.supporting_ids,
            "contradicting_ids": self.contradicting_ids,
            "superseded_ids": self.superseded_ids,
            "retrieval_keys": self.retrieval_keys,
            "clustering_confidence": self.clustering_confidence,
            "status": self.status,
            "scope_contract_id": self.scope_contract_id,
            "limitations": self.limitations,
        })
    }

    pub fn digest(&self) -> Result<String, MemoryError> {
        Ok(digest_canonical(&self.to_value())?)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccessEvent {
    pub query_id: String,
    pub retrieved_ids: Vec<String>,
    pub selected_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RetrievalBucket {
    pub bucket_id: String,
    pub member_ids: Vec<String>,
    pub weighted_edges: Vec<(String, String, i64)>,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProposalLifecycleEvent {
    pub event_id: String,
    pub proposal_id: String,
    pub status: String,
    pub created_at: String,
    pub reason: String,
}

impl ProposalLifecycleEvent {
    pub const ALLOWED_STATUSES: [&'static str; 5] = [
        "proposed",
        "reviewed",
        "accepted",
        "challenged",
        "superseded",
    ];

    pub fn validate(&self) -> Result<(), MemoryError> {
        if !Self::ALLOWED_STATUSES.contains(&self.status.as_str()) {
            return Err(MemoryError::Invalid(format!(
                "unsupported proposal lifecycle status: {}",
                self.status
            )));
        }
        if self.event_id.is_empty() || self.proposal_id.is_empty() || self.reason.is_empty() {
            return Err(MemoryError::Invalid(
                "proposal lifecycle identity and reason are required".into(),
            ));
        }
        Ok(())
    }

    pub fn to_value(&self) -> Value {
        json!({
            "event_id": self.event_id,
            "proposal_id": self.proposal_id,
            "status": self.status,
            "created_at": self.created_at,
            "reason": self.reason,
        })
    }

    pub fn payload_json(&self) -> Result<String, MemoryError> {
        Ok(canonical_json(&self.to_value())?)
    }
}
