//! Fail-closed knowledge promotion. Source records stay immutable.

use ravel_contracts::canonical_json;
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::KNOWLEDGE_RECORD_SCHEMA;
use ravel_contracts::status::EvidenceStatus;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeMap;
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct KnowledgeRecord {
    pub record_id: String,
    pub stage: KnowledgeStage,
    pub statement: String,
    pub scope: BTreeMap<String, String>,
    pub parent_ids: Vec<String>,
    pub evidence_ids: Vec<String>,
    pub evaluation_status: Option<EvidenceStatus>,
    pub transfer_status: String,
    pub attribution: Option<String>,
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
            "transfer_status": self.transfer_status,
            "attribution": self.attribution,
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
    transfer_status: &str,
    attribution: Option<String>,
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
    if current.stage == KnowledgeStage::Episode && next_stage == KnowledgeStage::SupportedStrategy {
        return Err(KnowledgeError::Invalid(
            "an episode cannot directly become a global strategy".into(),
        ));
    }
    if next_stage == KnowledgeStage::ProvisionalPrinciple
        && attribution.as_deref() != Some("supported")
    {
        return Err(KnowledgeError::Invalid(
            "a successful intervention cannot become a principle without supported attribution"
                .into(),
        ));
    }
    if next_stage == KnowledgeStage::TransferTestedPrinciple && evidence_ids.is_empty() {
        return Err(KnowledgeError::Invalid(
            "an untested principle cannot authorize transfer".into(),
        ));
    }
    if next_stage == KnowledgeStage::SupportedStrategy && transfer_status != "supported" {
        return Err(KnowledgeError::Invalid(
            "an untested principle cannot authorize broad reuse".into(),
        ));
    }
    if current.evaluation_status == Some(EvidenceStatus::Unknown)
        && evaluation_status == Some(EvidenceStatus::Pass)
    {
        return Err(KnowledgeError::Invalid(
            "knowledge promotion cannot convert UNKNOWN into PASS".into(),
        ));
    }
    if next_stage == KnowledgeStage::Counterexample && evidence_ids.is_empty() {
        return Err(KnowledgeError::Invalid(
            "a failed transfer test must remain linked to the principle".into(),
        ));
    }
    let promoted = KnowledgeRecord {
        record_id: next_id.to_string(),
        stage: next_stage,
        statement: statement.to_string(),
        scope: current.scope.clone(),
        parent_ids: vec![current.record_id.clone()],
        evidence_ids,
        evaluation_status,
        transfer_status: transfer_status.to_string(),
        attribution,
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
            transfer_status: "untested".into(),
            attribution: None,
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
                "supported",
                None,
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
            "untested",
            None,
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
                "untested",
                None,
                "t2",
            )
            .is_err()
        );
    }
}
