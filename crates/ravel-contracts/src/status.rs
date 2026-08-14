//! Status vocabularies that must stay distinct. No status in one space may
//! silently promote a status in another.

use serde::{Deserialize, Serialize};
use std::fmt::{Display, Formatter};

/// Normalized verifier / evidence status. Missing capability is UNKNOWN.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum EvidenceStatus {
    Pass,
    Fail,
    Unknown,
}

impl EvidenceStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "PASS",
            Self::Fail => "FAIL",
            Self::Unknown => "UNKNOWN",
        }
    }
}

impl Display for EvidenceStatus {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Formal disposition attached to an experience record. Absent is allowed.
pub type FormalDisposition = Option<EvidenceStatus>;

/// Adaptation transaction commit/rollback status. Not an MNCS disposition.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TransactionStatus {
    Accepted,
    Rejected,
}

impl TransactionStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Accepted => "accepted",
            Self::Rejected => "rejected",
        }
    }
}

/// Bounded planner result. Route absence is UNKNOWN, never FAIL.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum PlanStatus {
    Pass,
    Unknown,
}

impl PlanStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "PASS",
            Self::Unknown => "UNKNOWN",
        }
    }
}

/// Outcome of an interchange operation. Not an evidentiary disposition.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum OperationOutcome {
    Ok,
    Error,
}

impl OperationOutcome {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Ok => "OK",
            Self::Error => "ERROR",
        }
    }
}
