"""Portable parser/evaluator for candidate-001 C transaction observations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from .adaptation import (
    ConstraintReport,
    RawObservation,
    RetentionConstraintPolicy,
    evaluate_constraints,
)
from .policy import load_frozen_policy
from .matched_compute import MatchedComputeObservation


Q20 = 1_048_576.0


@dataclass(frozen=True, slots=True)
class CTransactionObservation:
    previous: RawObservation
    proposed: RawObservation
    committed: bool
    threshold_identity: str
    matched_compute_reference_available: bool
    rejection_reason: str
    failed_constraint_mask: int
    rollback_byte_identical: bool

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "CTransactionObservation":
        raw = value.get("raw")
        if not isinstance(raw, Mapping):
            raise ValueError("C transaction raw observation is missing")

        def q20(name: str) -> float:
            number = raw.get(name)
            if not isinstance(number, int) or number < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            return number / Q20

        def count(name: str) -> int:
            number = raw.get(name)
            if not isinstance(number, int) or number < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            return number

        before_representation = q20("representation_before_q20")
        after_representation = q20("representation_after_q20")
        previous_representation_score = 1.0 / (1.0 + before_representation)
        proposed_representation_score = 1.0 / (1.0 + after_representation)
        retention_before = q20("retention_accuracy_before_q20")
        retention_after = q20("retention_accuracy_after_q20")
        retention_delta = raw.get("retention_accuracy_delta_q20")
        if not isinstance(retention_delta, int):
            raise ValueError("retention_accuracy_delta_q20 is malformed")
        previous = RawObservation(
            adaptation_objective=q20("objective_before_q20"),
            base_accuracy=q20("base_accuracy_before_q20"),
            representation_score=previous_representation_score,
            original_prediction_degradation=0.0,
            transition_support_losses=0,
            expert_count=count("expert_count"),
            births=0,
            retirements=0,
            replay_records=0,
            update_passes=0,
            compute_evaluations=0,
            matched_compute_evaluations=0,
            retention_accuracy=retention_before,
            retention_accuracy_delta_from_base=0.0,
        )
        before_prediction = q20("prediction_rmse_before_q20")
        after_prediction = q20("prediction_rmse_after_q20")
        proposed = RawObservation(
            adaptation_objective=q20("objective_after_q20"),
            base_accuracy=q20("base_accuracy_after_q20"),
            representation_score=proposed_representation_score,
            original_prediction_degradation=max(0.0, after_prediction - before_prediction),
            transition_support_losses=count("transition_support_losses"),
            expert_count=count("expert_count"),
            births=count("births"),
            retirements=count("retirements"),
            replay_records=count("replay_records"),
            update_passes=count("update_passes"),
            compute_evaluations=count("compute_evaluations"),
            matched_compute_evaluations=count("matched_compute_evaluations"),
            retention_accuracy=retention_after,
            retention_accuracy_delta_from_base=retention_delta / Q20,
        )
        committed = value.get("committed")
        rollback = value.get("rollback_byte_identical")
        reason = value.get("rejection_reason")
        threshold_identity = value.get("threshold_identity")
        matched_compute_reference_available = raw.get("matched_compute_reference_available")
        mask = value.get("failed_constraint_mask")
        if not isinstance(committed, bool) or not isinstance(rollback, bool):
            raise ValueError("C transaction disposition fields must be boolean")
        if not isinstance(threshold_identity, str) or not threshold_identity:
            raise ValueError("C transaction threshold identity is malformed")
        if not isinstance(matched_compute_reference_available, bool):
            raise ValueError("C transaction compute-reference flag is malformed")
        if not isinstance(reason, str) or not isinstance(mask, int) or mask < 0:
            raise ValueError("C transaction reason fields are malformed")
        return cls(
            previous,
            proposed,
            committed,
            threshold_identity,
            matched_compute_reference_available,
            reason,
            mask,
            rollback,
        )

    def evaluate(
        self, matched_compute: MatchedComputeObservation | None = None
    ) -> ConstraintReport:
        """Apply the existing Python evaluator to the C observation pair."""

        frozen = load_frozen_policy()
        if self.threshold_identity != frozen.threshold_identity:
            return ConstraintReport(False, ("threshold_identity_mismatch",))
        policy = RetentionConstraintPolicy(
            adaptation_improvement_epsilon=frozen.adaptation_epsilon_q20 / Q20,
            base_accuracy_floor=frozen.base_accuracy_floor_q20 / Q20,
            representation_floor=self.previous.representation_score,
            original_prediction_degradation_bound=frozen.prediction_degradation_bound_q20 / Q20,
            maximum_transition_support_losses=frozen.maximum_transition_support_losses,
            maximum_experts=frozen.maximum_experts,
            maximum_births=frozen.maximum_births,
            maximum_retirements=frozen.maximum_retirements,
            maximum_replay_records=frozen.replay_records,
            maximum_update_passes=frozen.maximum_update_passes,
            maximum_compute_evaluations=frozen.maximum_compute_evaluations,
            maximum_compute_ratio=frozen.maximum_compute_ratio_q20 / Q20,
            retention_accuracy_floor=frozen.retention_accuracy_floor_q20 / Q20,
            retention_loss_floor=frozen.retention_loss_floor_q20 / Q20,
            exact_replay_records=frozen.replay_records,
        )
        proposed = self.proposed
        if matched_compute is not None:
            proposed = replace(
                proposed,
                compute_evaluations=matched_compute.candidate_training_evaluations,
                matched_compute_evaluations=matched_compute.matched_training_evaluations,
            )
        return evaluate_constraints(self.previous, proposed, policy)
