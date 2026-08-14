//! Fail-closed knowledge promotion. Source records stay immutable.

use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::KNOWLEDGE_RECORD_SCHEMA;
use ravel_contracts::status::EvidenceStatus;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum KnowledgeError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum KnowledgeStage {
    Observation,
    Episode,
    OpenHypothesis,
    Intervention,
    Attribution,
    ProvisionalPrinciple,
    TransferTestedPrinciple,
    RestrictedStrategy,
    SupportedStrategy,
    Counterexample,
    Retired,
}

impl KnowledgeStage {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Observation => "observation",
            Self::Episode => "episode",
            Self::OpenHypothesis => "open_hypothesis",
            Self::Intervention => "intervention",
            Self::Attribution => "attribution",
            Self::ProvisionalPrinciple => "provisional_principle",
            Self::TransferTestedPrinciple => "transfer_tested_principle",
            Self::RestrictedStrategy => "restricted_strategy",
            Self::SupportedStrategy => "supported_strategy",
            Self::Counterexample => "counterexample",
            Self::Retired => "retired",
        }
    }

    pub fn parse(value: &str) -> Result<Self, KnowledgeError> {
        match value {
            "observation" => Ok(Self::Observation),
            "episode" => Ok(Self::Episode),
            "open_hypothesis" => Ok(Self::OpenHypothesis),
            "intervention" => Ok(Self::Intervention),
            "attribution" => Ok(Self::Attribution),
            "provisional_principle" => Ok(Self::ProvisionalPrinciple),
            "transfer_tested_principle" => Ok(Self::TransferTestedPrinciple),
            "restricted_strategy" => Ok(Self::RestrictedStrategy),
            "supported_strategy" => Ok(Self::SupportedStrategy),
            "counterexample" => Ok(Self::Counterexample),
            "retired" => Ok(Self::Retired),
            other => Err(KnowledgeError::Invalid(format!(
                "unknown knowledge stage: {other}"
            ))),
        }
    }

    fn allowed_next(self) -> &'static [Self] {
        match self {
            Self::Observation => &[Self::Episode],
            Self::Episode => &[Self::OpenHypothesis, Self::Retired],
            Self::OpenHypothesis => &[Self::Intervention, Self::Counterexample, Self::Retired],
            Self::Intervention => &[Self::Attribution, Self::Counterexample, Self::Retired],
            Self::Attribution => &[
                Self::ProvisionalPrinciple,
                Self::Counterexample,
                Self::Retired,
            ],
            Self::ProvisionalPrinciple => &[
                Self::TransferTestedPrinciple,
                Self::Counterexample,
                Self::Retired,
            ],
            Self::TransferTestedPrinciple => &[
                Self::RestrictedStrategy,
                Self::Counterexample,
                Self::Retired,
            ],
            Self::RestrictedStrategy => {
                &[Self::SupportedStrategy, Self::Counterexample, Self::Retired]
            }
            Self::SupportedStrategy => &[Self::Counterexample, Self::Retired],
            Self::Counterexample | Self::Retired => &[],
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TransferStatus {
    Untested,
    Failed,
    Partial,
    Supported,
}

impl TransferStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Untested => "untested",
            Self::Failed => "failed",
            Self::Partial => "partial",
            Self::Supported => "supported",
        }
    }

    pub fn parse(value: &str) -> Result<Self, KnowledgeError> {
        match value {
            "untested" => Ok(Self::Untested),
            "failed" => Ok(Self::Failed),
            "partial" => Ok(Self::Partial),
            "supported" => Ok(Self::Supported),
            other => Err(KnowledgeError::Invalid(format!(
                "unsupported transfer status: {other}"
            ))),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AttributionDisposition {
    Inconclusive,
    Supported,
    Challenged,
    Rejected,
}

impl AttributionDisposition {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Inconclusive => "inconclusive",
            Self::Supported => "supported",
            Self::Challenged => "challenged",
            Self::Rejected => "rejected",
        }
    }

    pub fn parse(value: &str) -> Result<Self, KnowledgeError> {
        match value {
            "inconclusive" => Ok(Self::Inconclusive),
            "supported" => Ok(Self::Supported),
            "challenged" => Ok(Self::Challenged),
            "rejected" => Ok(Self::Rejected),
            other => Err(KnowledgeError::Invalid(format!(
                "unsupported attribution disposition: {other}"
            ))),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AttributionRecord {
    pub attribution_id: String,
    pub source_intervention_ids: Vec<String>,
    pub evaluator_identity: String,
    pub evidence_ids: Vec<String>,
    pub disposition: AttributionDisposition,
    pub scope: BTreeMap<String, String>,
}

impl AttributionRecord {
    pub fn validate(&self) -> Result<(), KnowledgeError> {
        if self.attribution_id.trim().is_empty()
            || self.evaluator_identity.trim().is_empty()
            || self.source_intervention_ids.is_empty()
            || self.evidence_ids.is_empty()
        {
            return Err(KnowledgeError::Invalid(
                "attribution requires identity, evaluator, intervention, and evidence".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TransferTestRecord {
    pub test_id: String,
    pub principle_id: String,
    pub context_identity: String,
    pub evidence_ids: Vec<String>,
    pub outcome: TransferStatus,
}

impl TransferTestRecord {
    pub fn validate(&self) -> Result<(), KnowledgeError> {
        if self.test_id.trim().is_empty()
            || self.principle_id.trim().is_empty()
            || self.context_identity.trim().is_empty()
            || self.evidence_ids.is_empty()
        {
            return Err(KnowledgeError::Invalid(
                "transfer test requires identity, principle, context, and evidence".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct KnowledgeRecord {
    pub record_id: String,
    pub stage: KnowledgeStage,
    pub statement: String,
    pub scope: BTreeMap<String, String>,
    pub parent_ids: Vec<String>,
    pub evidence_ids: Vec<String>,
    pub evaluation_status: Option<EvidenceStatus>,
    pub transfer_status: TransferStatus,
    pub attribution_id: Option<String>,
    pub transfer_test_ids: Vec<String>,
    pub challenged_ids: Vec<String>,
    pub producer_id: String,
    pub created_at: String,
}

impl KnowledgeRecord {
    pub fn validate(&self) -> Result<(), KnowledgeError> {
        if self.record_id.trim().is_empty() || self.statement.trim().is_empty() {
            return Err(KnowledgeError::Invalid(
                "knowledge record identity and statement are required".into(),
            ));
        }
        if self.scope.is_empty() {
            return Err(KnowledgeError::Invalid(
                "knowledge record scope is required".into(),
            ));
        }
        Ok(())
    }

    pub fn to_value(&self) -> Value {
        json!({
            "schema": KNOWLEDGE_RECORD_SCHEMA,
            "record_id": self.record_id,
            "stage": self.stage.as_str(),
            "statement": self.statement,
            "scope": self.scope,
            "parent_ids": self.parent_ids,
            "evidence_ids": self.evidence_ids,
            "evaluation_status": self.evaluation_status.map(|item| item.as_str()),
            "transfer_status": self.transfer_status.as_str(),
            "attribution_id": self.attribution_id,
            "transfer_test_ids": self.transfer_test_ids,
            "challenged_ids": self.challenged_ids,
            "producer_id": self.producer_id,
            "created_at": self.created_at,
        })
    }

    pub fn digest(&self) -> Result<String, KnowledgeError> {
        Ok(format!(
            "sha256:{}",
            hex_sha256(canonical_json(&self.to_value())?.as_bytes())
        ))
    }
}

#[allow(clippy::too_many_arguments)]
pub fn promote(
    current: &KnowledgeRecord,
    next_stage: KnowledgeStage,
    next_id: &str,
    statement: &str,
    evidence_ids: Vec<String>,
    evaluation_status: Option<EvidenceStatus>,
    attribution: Option<AttributionRecord>,
    transfer_tests: Vec<TransferTestRecord>,
    created_at: &str,
) -> Result<KnowledgeRecord, KnowledgeError> {
    current.validate()?;
    if !current.stage.allowed_next().contains(&next_stage) {
        return Err(KnowledgeError::Invalid(format!(
            "invalid knowledge transition: {}->{}",
            current.stage.as_str(),
            next_stage.as_str()
        )));
    }
    if current.evaluation_status == Some(EvidenceStatus::Unknown)
        && evaluation_status == Some(EvidenceStatus::Pass)
        || current.evaluation_status == Some(EvidenceStatus::Fail)
            && evaluation_status == Some(EvidenceStatus::Pass)
    {
        return Err(KnowledgeError::Invalid(
            "knowledge promotion cannot convert FAIL or UNKNOWN into PASS".into(),
        ));
    }
    if next_id == current.record_id {
        return Err(KnowledgeError::Invalid(
            "promotion must not overwrite its parent".into(),
        ));
    }
    if next_stage == KnowledgeStage::ProvisionalPrinciple {
        let Some(record) = attribution.as_ref() else {
            return Err(KnowledgeError::Invalid(
                "a principle requires a valid attribution record".into(),
            ));
        };
        record.validate()?;
        if record.disposition != AttributionDisposition::Supported {
            return Err(KnowledgeError::Invalid(
                "a principle requires a supported attribution disposition".into(),
            ));
        }
        if record.scope != current.scope {
            return Err(KnowledgeError::Invalid(
                "attribution scope must match the parent knowledge scope".into(),
            ));
        }
        if !record
            .source_intervention_ids
            .iter()
            .any(|item| item == &current.record_id || current.parent_ids.contains(item))
        {
            return Err(KnowledgeError::Invalid(
                "attribution must cite the source intervention".into(),
            ));
        }
    }
    if next_stage == KnowledgeStage::TransferTestedPrinciple {
        if transfer_tests.is_empty() {
            return Err(KnowledgeError::Invalid(
                "a transfer-tested principle must identify actual transfer tests".into(),
            ));
        }
        for test in &transfer_tests {
            test.validate()?;
            if test.principle_id != current.record_id {
                return Err(KnowledgeError::Invalid(
                    "transfer test must name the parent principle".into(),
                ));
            }
            if test.outcome == TransferStatus::Untested {
                return Err(KnowledgeError::Invalid(
                    "untested transfer evidence cannot authorize transfer".into(),
                ));
            }
        }
    }
    if next_stage == KnowledgeStage::SupportedStrategy {
        let contexts: BTreeSet<_> = transfer_tests
            .iter()
            .filter(|item| item.outcome == TransferStatus::Supported)
            .map(|item| item.context_identity.as_str())
            .collect();
        if contexts.len() < 2 {
            return Err(KnowledgeError::Invalid(
                "a supported strategy must not be created from one local context".into(),
            ));
        }
    }
    if next_stage == KnowledgeStage::Counterexample && evidence_ids.is_empty() {
        return Err(KnowledgeError::Invalid(
            "a counterexample must remain linked to the knowledge it challenges".into(),
        ));
    }
    let transfer_status = if next_stage == KnowledgeStage::SupportedStrategy {
        TransferStatus::Supported
    } else if next_stage == KnowledgeStage::TransferTestedPrinciple {
        TransferStatus::Partial
    } else {
        TransferStatus::Untested
    };
    let promoted = KnowledgeRecord {
        record_id: next_id.to_string(),
        stage: next_stage,
        statement: statement.to_string(),
        scope: current.scope.clone(),
        parent_ids: vec![current.record_id.clone()],
        evidence_ids,
        evaluation_status,
        transfer_status,
        attribution_id: attribution.as_ref().map(|item| item.attribution_id.clone()),
        transfer_test_ids: transfer_tests
            .iter()
            .map(|item| item.test_id.clone())
            .collect(),
        challenged_ids: if next_stage == KnowledgeStage::Counterexample {
            vec![current.record_id.clone()]
        } else {
            Vec::new()
        },
        producer_id: current.producer_id.clone(),
        created_at: created_at.to_string(),
    };
    promoted.validate()?;
    Ok(promoted)
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    fn observation() -> KnowledgeRecord {
        KnowledgeRecord {
            record_id: "knowledge:obs".into(),
            stage: KnowledgeStage::Observation,
            statement: "A bounded Forge check returned UNKNOWN.".into(),
            scope: BTreeMap::from([("partition".into(), "development".into())]),
            parent_ids: Vec::new(),
            evidence_ids: vec!["obs:1".into()],
            evaluation_status: Some(EvidenceStatus::Unknown),
            transfer_status: TransferStatus::Untested,
            attribution_id: None,
            transfer_test_ids: Vec::new(),
            challenged_ids: Vec::new(),
            producer_id: "ravel-knowledge".into(),
            created_at: "2026-08-14T00:00:00Z".into(),
        }
    }

    #[test]
    fn skips_and_unknown_to_pass_fail_closed() {
        let current = observation();
        assert!(
            promote(
                &current,
                KnowledgeStage::SupportedStrategy,
                "knowledge:bad",
                "must not skip",
                vec!["e".into()],
                Some(EvidenceStatus::Unknown),
                None,
                Vec::new(),
                "t1",
            )
            .is_err()
        );
        let episode = promote(
            &current,
            KnowledgeStage::Episode,
            "knowledge:ep",
            &current.statement,
            current.evidence_ids.clone(),
            Some(EvidenceStatus::Unknown),
            None,
            Vec::new(),
            "t1",
        )
        .expect("episode");
        assert!(
            promote(
                &episode,
                KnowledgeStage::Episode,
                "knowledge:pass",
                &episode.statement,
                episode.evidence_ids.clone(),
                Some(EvidenceStatus::Pass),
                None,
                Vec::new(),
                "t2",
            )
            .is_err()
        );
    }

    #[test]
    fn principle_requires_supported_attribution_record() {
        let mut current = observation();
        current.stage = KnowledgeStage::Attribution;
        current.record_id = "knowledge:attr".into();
        assert!(
            promote(
                &current,
                KnowledgeStage::ProvisionalPrinciple,
                "knowledge:prin",
                "lesson",
                vec!["e".into()],
                Some(EvidenceStatus::Unknown),
                None,
                Vec::new(),
                "t1",
            )
            .is_err()
        );
        let attribution = AttributionRecord {
            attribution_id: "attr:1".into(),
            source_intervention_ids: vec!["knowledge:attr".into()],
            evaluator_identity: "evaluator:dev".into(),
            evidence_ids: vec!["e".into()],
            disposition: AttributionDisposition::Supported,
            scope: current.scope.clone(),
        };
        let principle = promote(
            &current,
            KnowledgeStage::ProvisionalPrinciple,
            "knowledge:prin",
            "lesson",
            vec!["e".into()],
            Some(EvidenceStatus::Unknown),
            Some(attribution),
            Vec::new(),
            "t1",
        )
        .expect("principle");
        assert_eq!(principle.attribution_id.as_deref(), Some("attr:1"));
    }
}
