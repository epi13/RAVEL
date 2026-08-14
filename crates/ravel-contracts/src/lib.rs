//! Canonical RAVEL contract identities, status vocabulary, and JSON codec.
//!
//! This crate is the versioned interchange surface for the Rust-native
//! implementation. It does not evaluate MNCS/MNCDS conformance and does not
//! promote development observations.

pub mod canonical;
pub mod identity;
pub mod reason;
pub mod schema;
pub mod status;

pub use canonical::{CanonicalError, canonical_json, canonical_to_vec};
pub use identity::{digest_bytes, digest_canonical, hex_sha256, prefixed_sha256};
pub use reason::RejectionReason;
pub use schema::{
    CANONICAL_JSON_CONTRACT, CHECKPOINT_SCHEMA, FAMILY_COMPATIBILITY_LOCK_SCHEMA,
    FOUNDATION_CONTRACT, INTERCHANGE_SCHEMA, LEDGER_SCHEMA, MATCHED_COMPUTE_SCHEMA,
    MEMORY_RECORD_SCHEMA, TRANSACTION_SCHEMA, WORLD_ABI,
};
pub use status::{
    EvidenceStatus, FormalDisposition, OperationOutcome, PlanStatus, TransactionStatus,
};

/// Workspace identity bound into interchange envelopes and Forge reports.
pub const IMPLEMENTATION_IDENTITY: &str = "ravel-rs/0.1";
pub const Q20: i64 = 1_048_576;
