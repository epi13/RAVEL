"""Development-only matched-compute observations and fail-closed evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .adaptation import ConstraintReport
from .policy import load_frozen_policy


Q20 = 1_048_576


@dataclass(frozen=True, slots=True)
class MatchedComputeObservation:
    candidate_training_evaluations: int
    matched_training_evaluations: int
    ratio_q20: int
    maximum_ratio_q20: int
    reference_available: bool
    threshold_identity: str
    comparator_identity: str
    partition_identity: str

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "MatchedComputeObservation":
        def count(name: str) -> int:
            result = value.get(name)
            if not isinstance(result, int) or result < 0:
                raise ValueError(f"matched-compute field {name} is malformed")
            return result

        ratio = count("ratio_q20")
        maximum = count("maximum_ratio_q20")
        available = value.get("reference_available")
        comparator = value.get("comparator_identity")
        partition = value.get("partition_identity")
        threshold = value.get("threshold_identity")
        if not isinstance(available, bool):
            raise ValueError("matched-compute availability is malformed")
        if not isinstance(comparator, str) or not comparator:
            raise ValueError("matched-compute comparator identity is malformed")
        if not isinstance(partition, str) or not partition:
            raise ValueError("matched-compute partition identity is malformed")
        if not isinstance(threshold, str) or not threshold:
            raise ValueError("matched-compute threshold identity is malformed")
        result = cls(
            count("candidate_training_evaluations"),
            count("matched_training_evaluations"),
            ratio,
            maximum,
            available,
            threshold,
            comparator,
            partition,
        )
        expected = (
            result.candidate_training_evaluations * Q20
            // result.matched_training_evaluations
            if result.matched_training_evaluations
            else 0
        )
        if result.ratio_q20 != expected:
            raise ValueError("matched-compute ratio does not reconstruct from raw counts")
        return result

    def evaluate(self) -> ConstraintReport:
        policy = load_frozen_policy()
        reasons: list[str] = []
        if self.threshold_identity != policy.threshold_identity:
            reasons.append("threshold_identity_mismatch")
        if not self.reference_available or self.matched_training_evaluations == 0:
            reasons.append("matched_compute_reference_unavailable")
        if self.maximum_ratio_q20 != policy.maximum_compute_ratio_q20:
            reasons.append("threshold_identity_mismatch")
        if self.ratio_q20 > policy.maximum_compute_ratio_q20:
            reasons.append("matched_compute_ratio")
        return ConstraintReport(not reasons, tuple(reasons))
