//! Versioned schema and ABI identities. These strings are part of the public
//! contract and must not be renamed without a new identity.

pub const FOUNDATION_CONTRACT: &str = "ravel-rust-foundation/0.1";
pub const INTERCHANGE_SCHEMA: &str = "ravel-interchange/0.1";
pub const CANONICAL_JSON_CONTRACT: &str = "ravel-canonical-json/1";
pub const CHECKPOINT_SCHEMA: &str = "ravel-0.6-mechanism-checkpoint/0.1";
pub const LEDGER_SCHEMA: &str = "ravel-0.6-candidate-ledger/0.1";
pub const MEMORY_RECORD_SCHEMA: &str = "ravel-memory-record/0.1";
pub const TRANSACTION_SCHEMA: &str = "ravel-0.6-transaction/0.1";
pub const MATCHED_COMPUTE_SCHEMA: &str = "ravel-0.6-matched-compute/0.1";
pub const FABRIC_WORKLOAD_SCHEMA: &str = "ravel-fabric-workload/0.1";
pub const FABRIC_OBSERVATION_SCHEMA: &str = "ravel-fabric-observation/0.1";
pub const WORLD_ABI: &str = "ravel-0.6-world-abi/1";
pub const CHECKPOINT_ABI: &str = "ravel-0.6-checkpoint-abi/1";
pub const FAMILY_COMPATIBILITY_LOCK_SCHEMA: &str = "ravel-family-compatibility-lock/1";
pub const SCOPE_EXACT_CONTRACT: &str = "ravel-scope-exact/1";
pub const SEMANTIC_CONSOLIDATION_METHOD: &str = "ravel-semantic-consolidation/0.1";
pub const KNOWLEDGE_RECORD_SCHEMA: &str = "ravel-knowledge-record/0.1";
pub const KNOWLEDGE_LIFECYCLE_CONTRACT: &str = "ravel-knowledge-lifecycle/0.1";
pub const ARTIFACT_SCHEMA: &str = "ravel-artifact/0.1";
pub const RETENTION_POLICY_SCHEMA: &str = "ravel-retention-policy/0.1";
pub const CURATION_REPORT_SCHEMA: &str = "ravel-curation-report/0.1";

pub const TOY_BRANCHING_PROVIDER: &str = "ravel-toy-branching/1";
pub const TOY_RING_PROVIDER: &str = "ravel-toy-ring/1";

pub const EXPECTED_06_PREREGISTRATION_SHA256: &str =
    "26ae0b001355c978dbb2bda57fd7bcd74a3b3d4e46f45fa0b9658d88fcc885a3";
pub const EXPECTED_05_PREREGISTRATION_SHA256: &str =
    "f240c391b92823471132ffce1eeed154b3f03dc2af1e3e1f789690a99eb4cfaa";
