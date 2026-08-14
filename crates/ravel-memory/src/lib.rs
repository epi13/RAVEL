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
pub use knowledge::{
    AttributionDisposition, AttributionRecord, KnowledgeRecord, KnowledgeStage, TransferStatus,
    TransferTestRecord, promote,
};
pub use models::{
    AccessEvent, AuthorityClass, ConsolidationProposal, MemoryClass, MemoryError, MemoryRecord,
    ProposalLifecycleEvent, RecordStatus, RetrievalBucket, ScopeCompatibility,
};
pub use retention::{
    RetentionAdvisory, RetentionClass, RetentionPolicy, advise_retention, compact,
};
pub use store::{ImmutableRecordError, JsonlMemoryStore, TailPolicy};
