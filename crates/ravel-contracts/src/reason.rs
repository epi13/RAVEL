//! Stable rejection-reason vocabulary shared with the Python and C surfaces.

pub struct RejectionReason;

impl RejectionReason {
    pub const ADAPTATION_IMPROVEMENT_BELOW_EPSILON: &str = "adaptation_improvement_below_epsilon";
    pub const BASE_ACCURACY_FLOOR: &str = "base_accuracy_floor";
    pub const REPRESENTATION_FLOOR: &str = "representation_floor";
    pub const ORIGINAL_PREDICTION_DEGRADATION_BOUND: &str = "original_prediction_degradation_bound";
    pub const RETENTION_ACCURACY_FLOOR: &str = "retention_accuracy_floor";
    pub const RETENTION_LOSS_FLOOR: &str = "retention_loss_floor";
    pub const TRANSITION_SUPPORT_PRESERVATION: &str = "transition_support_preservation";
    pub const EXPERT_CAPACITY_BUDGET: &str = "expert_capacity_budget";
    pub const BIRTH_BUDGET: &str = "birth_budget";
    pub const RETIREMENT_BUDGET: &str = "retirement_budget";
    pub const REPLAY_BUDGET: &str = "replay_budget";
    pub const UPDATE_PASS_BUDGET: &str = "update_pass_budget";
    pub const COMPUTE_BUDGET: &str = "compute_budget";
    pub const MATCHED_COMPUTE_REFERENCE_UNAVAILABLE: &str = "matched_compute_reference_unavailable";
    pub const MATCHED_COMPUTE_RATIO: &str = "matched_compute_ratio";
    pub const THRESHOLD_IDENTITY_MISMATCH: &str = "threshold_identity_mismatch";
}
