//! Append-only RAVEL memory, consolidation, retention, and knowledge lifecycle.

pub mod artifacts;
pub mod consolidation;
pub mod curation;
pub mod knowledge;
pub mod models;
pub mod retention;
pub mod store;

pub use artifacts::{ArtifactRecord, ArtifactStore};
pub use consolidation::{ConsolidationPolicy, MemoryConsolidator, RetrievalLayoutPlanner};
pub use curation::{CurationReport, curate};
pub use knowledge::{KnowledgeRecord, KnowledgeStage, promote};
pub use models::{
    AccessEvent, ConsolidationProposal, MemoryClass, MemoryError, MemoryRecord,
    ProposalLifecycleEvent, RetrievalBucket, ScopeCompatibility,
};
pub use retention::{RetentionPolicy, compact};
pub use store::{ImmutableRecordError, JsonlMemoryStore};
