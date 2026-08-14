//! Narrow RAVEL-to-Forge provider boundary.
//!
//! Forge remains the evidence executor. Missing capability is UNKNOWN. This
//! module does not reimplement Forge or Fabric.

use ravel_contracts::status::EvidenceStatus as ContractStatus;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

pub type EvidenceStatus = ContractStatus;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProviderCapability {
    pub provider_id: String,
    pub operation: String,
    pub version: String,
    pub deterministic: bool,
    pub witness_kind: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EvidenceRequest {
    pub request_id: String,
    pub candidate_id: String,
    pub artifact_digest: String,
    pub governing_contract: String,
    pub verifier_contract: String,
    pub question: String,
    pub witness_kind: String,
    #[serde(default)]
    pub resource_budget: Map<String, Value>,
    #[serde(default)]
    pub timeout_seconds: i64,
    #[serde(default = "default_true")]
    pub determinism_required: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RawEvidence {
    pub request_id: String,
    pub provider_id: String,
    pub raw_status: EvidenceStatus,
    pub observations: Map<String, Value>,
    pub witness_digest: Option<String>,
    pub artifact_digests: Vec<String>,
    pub environment_id: String,
    pub resource_observations: Map<String, Value>,
    #[serde(default)]
    pub limitations: Vec<String>,
    #[serde(default)]
    pub diagnostics: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EvidenceReceipt {
    pub status: EvidenceStatus,
    pub reason_code: String,
    pub raw: RawEvidence,
}

pub trait ForgeProvider {
    fn provider_id(&self) -> &str;
    fn capabilities(&self) -> Vec<ProviderCapability>;
    fn execute(&self, request: &EvidenceRequest) -> RawEvidence;
}

/// Fail-closed placeholder used when a sibling Forge/Fabric backend is absent.
#[derive(Debug, Default, Clone, Copy)]
pub struct UnavailableProvider;

impl UnavailableProvider {
    pub const ID: &'static str = "ravel-unavailable-provider/0.1";
}

impl ForgeProvider for UnavailableProvider {
    fn provider_id(&self) -> &str {
        Self::ID
    }

    fn capabilities(&self) -> Vec<ProviderCapability> {
        Vec::new()
    }

    fn execute(&self, request: &EvidenceRequest) -> RawEvidence {
        RawEvidence {
            request_id: request.request_id.clone(),
            provider_id: Self::ID.to_string(),
            raw_status: EvidenceStatus::Unknown,
            observations: Map::new(),
            witness_digest: None,
            artifact_digests: Vec::new(),
            environment_id: "unavailable".into(),
            resource_observations: Map::new(),
            limitations: vec!["provider capability unavailable".into()],
            diagnostics: "sibling Forge/Fabric executable was not injected".into(),
        }
    }
}

pub fn receipt_from_raw(raw: RawEvidence) -> EvidenceReceipt {
    let (status, reason_code) = match raw.raw_status {
        EvidenceStatus::Pass => (EvidenceStatus::Pass, "raw_pass"),
        EvidenceStatus::Fail => (EvidenceStatus::Fail, "raw_fail"),
        EvidenceStatus::Unknown => (EvidenceStatus::Unknown, "capability_or_result_unavailable"),
    };
    EvidenceReceipt {
        status,
        reason_code: reason_code.into(),
        raw,
    }
}
