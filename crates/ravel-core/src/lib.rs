//! Foundational RAVEL control-plane behavior.
//!
//! These modules are the Rust-native ports of the tested Python surfaces.
//! They do not create MNCS/MNCDS authority, freeze candidate-001, or consume
//! selection partitions.

pub mod adaptation;
pub mod c_observations;
pub mod checkpoint;
pub mod experience;
pub mod lifecycle;
pub mod matched_compute;
pub mod mechanism;
pub mod planning;
pub mod policy;
pub mod providers;
pub mod repository;
pub mod transition;
pub mod world;

pub use adaptation::{
    AdaptationError, AdaptationTransaction, ConstraintReport, RawObservation,
    RetentionConstraintPolicy, canonical_transaction_json, evaluate_constraints, run_transaction,
};
pub use checkpoint::{CheckpointCodec, CheckpointError};
pub use experience::{ExperienceError, ExperienceRecord};
pub use lifecycle::{CandidateLedger, CandidateRecord, CandidateState, LedgerError};
pub use matched_compute::MatchedComputeObservation;
pub use mechanism::{ExpertState, MechanismError, MechanismState};
pub use planning::{PlanResult, plan};
pub use policy::{FrozenRavel06Policy, PolicyError, load_frozen_policy, policy_c_header};
pub use providers::{
    EvidenceReceipt, EvidenceRequest, EvidenceStatus, ForgeProvider, ProviderCapability,
    RawEvidence, UnavailableProvider,
};
pub use repository::discover_repository_root;
pub use transition::{CompiledTransitions, TransitionCompiler, TransitionError};
pub use world::{ToyBranchingWorld, ToyRingWorld, WorldProvider, WorldTransition};
