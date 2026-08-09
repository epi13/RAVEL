"""Retention-constrained adaptation transactions.

This module is a provider-neutral development surface. It evaluates raw
observations against an immutable policy and commits a proposed checkpoint only
when every hard constraint passes. It does not derive MNCS/MNCDS authority or a
final RAVEL 0.6 disposition.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Callable


class AdaptationInputError(ValueError):
    """Raised when an observation or policy is not a valid hard-gate input."""


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise AdaptationInputError(f"{name} must be finite")
    return value


def _nonnegative(value: int, name: str) -> int:
    if value < 0:
        raise AdaptationInputError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class RawObservation:
    """Executable measurements retained separately from gate dispositions."""

    adaptation_objective: float
    base_accuracy: float
    representation_score: float
    original_prediction_degradation: float
    transition_support_losses: int
    expert_count: int
    births: int
    retirements: int
    replay_records: int
    update_passes: int
    compute_evaluations: int
    matched_compute_evaluations: int
    retention_accuracy: float | None = None
    retention_accuracy_delta_from_base: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "adaptation_objective",
            "base_accuracy",
            "representation_score",
            "original_prediction_degradation",
        ):
            _finite(getattr(self, name), name)
        for name in ("retention_accuracy", "retention_accuracy_delta_from_base"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
        for name in (
            "transition_support_losses",
            "expert_count",
            "births",
            "retirements",
            "replay_records",
            "update_passes",
            "compute_evaluations",
            "matched_compute_evaluations",
        ):
            _nonnegative(getattr(self, name), name)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetentionConstraintPolicy:
    """Explicit hard constraints for one development transaction."""

    adaptation_improvement_epsilon: float
    base_accuracy_floor: float
    representation_floor: float
    original_prediction_degradation_bound: float
    maximum_transition_support_losses: int
    maximum_experts: int
    maximum_births: int
    maximum_retirements: int
    maximum_replay_records: int
    maximum_update_passes: int
    maximum_compute_evaluations: int | None
    maximum_compute_ratio: float
    retention_accuracy_floor: float | None = None
    retention_loss_floor: float | None = None
    exact_replay_records: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "adaptation_improvement_epsilon",
            "base_accuracy_floor",
            "representation_floor",
            "original_prediction_degradation_bound",
            "maximum_compute_ratio",
        ):
            value = _finite(getattr(self, name), name)
            if value < 0:
                raise AdaptationInputError(f"{name} must be non-negative")
        for name in (
            "maximum_transition_support_losses",
            "maximum_experts",
            "maximum_births",
            "maximum_retirements",
            "maximum_replay_records",
            "maximum_update_passes",
        ):
            _nonnegative(getattr(self, name), name)
        if self.maximum_compute_evaluations is not None:
            _nonnegative(self.maximum_compute_evaluations, "maximum_compute_evaluations")
        for name in ("retention_accuracy_floor", "retention_loss_floor", "exact_replay_records"):
            value = getattr(self, name)
            if value is not None:
                if name == "exact_replay_records":
                    _nonnegative(value, name)
                else:
                    _finite(value, name)
                    if name == "retention_accuracy_floor" and value < 0:
                        raise AdaptationInputError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class ConstraintReport:
    """Independent hard-gate results in stable order."""

    passed: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "rejection_reasons": list(self.rejection_reasons),
        }


def evaluate_constraints(
    previous: RawObservation,
    proposed: RawObservation,
    policy: RetentionConstraintPolicy,
) -> ConstraintReport:
    """Derive each hard gate independently; no metric compensates for another."""

    reasons: list[str] = []
    if proposed.adaptation_objective - previous.adaptation_objective < policy.adaptation_improvement_epsilon:
        reasons.append("adaptation_improvement_below_epsilon")
    if proposed.base_accuracy < policy.base_accuracy_floor:
        reasons.append("base_accuracy_floor")
    if proposed.representation_score < policy.representation_floor:
        reasons.append("representation_floor")
    if proposed.original_prediction_degradation > policy.original_prediction_degradation_bound:
        reasons.append("original_prediction_degradation_bound")
    if (
        policy.retention_accuracy_floor is not None
        and proposed.retention_accuracy is not None
        and proposed.retention_accuracy < policy.retention_accuracy_floor
    ):
        reasons.append("retention_accuracy_floor")
    if (
        policy.retention_loss_floor is not None
        and proposed.retention_accuracy_delta_from_base is not None
        and proposed.retention_accuracy_delta_from_base < policy.retention_loss_floor
    ):
        reasons.append("retention_loss_floor")
    if proposed.transition_support_losses > policy.maximum_transition_support_losses:
        reasons.append("transition_support_preservation")
    if proposed.expert_count > policy.maximum_experts:
        reasons.append("expert_capacity_budget")
    if proposed.births > policy.maximum_births:
        reasons.append("birth_budget")
    if proposed.retirements > policy.maximum_retirements:
        reasons.append("retirement_budget")
    if policy.exact_replay_records is not None and proposed.replay_records != policy.exact_replay_records:
        reasons.append("replay_budget")
    elif proposed.replay_records > policy.maximum_replay_records:
        reasons.append("replay_budget")
    if proposed.update_passes > policy.maximum_update_passes:
        reasons.append("update_pass_budget")
    if (
        policy.maximum_compute_evaluations is not None
        and proposed.compute_evaluations > policy.maximum_compute_evaluations
    ):
        reasons.append("compute_budget")
    if proposed.matched_compute_evaluations == 0:
        reasons.append("matched_compute_reference_unavailable")
    elif (
        proposed.compute_evaluations / proposed.matched_compute_evaluations
        > policy.maximum_compute_ratio
    ):
        reasons.append("matched_compute_ratio")
    return ConstraintReport(not reasons, tuple(reasons))


@dataclass(frozen=True, slots=True)
class AdaptationTransaction:
    """Raw observation plus the exact committed or rolled-back bytes."""

    status: str
    state_before: bytes
    state_after: bytes
    observation: RawObservation
    report: ConstraintReport
    checkpoint_before_sha256: str
    checkpoint_after_sha256: str

    def __post_init__(self) -> None:
        if self.status not in {"accepted", "rejected"}:
            raise AdaptationInputError(f"unknown transaction status: {self.status}")
        if self.status == "accepted" and not self.report.passed:
            raise AdaptationInputError("accepted transaction has failed constraints")
        if self.status == "rejected" and self.report.passed:
            raise AdaptationInputError("rejected transaction has no failed constraints")

    @property
    def rolled_back_byte_identical(self) -> bool:
        return self.status == "rejected" and self.state_before == self.state_after

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "state_before_sha256": self.checkpoint_before_sha256,
            "state_after_sha256": self.checkpoint_after_sha256,
            "observation": self.observation.to_dict(),
            "constraints": self.report.to_dict(),
            "rolled_back_byte_identical": self.rolled_back_byte_identical,
        }


def _digest(state: bytes) -> str:
    return hashlib.sha256(state).hexdigest()


def run_transaction(
    previous_state: bytes,
    previous_observation: RawObservation,
    propose: Callable[[bytes], bytes],
    observe: Callable[[bytes], RawObservation],
    policy: RetentionConstraintPolicy,
) -> AdaptationTransaction:
    """Evaluate a copied proposal and commit only when all gates pass."""

    before = bytes(previous_state)
    candidate = bytes(propose(before))
    observation = observe(candidate)
    report = evaluate_constraints(previous_observation, observation, policy)
    after = candidate if report.passed else before
    status = "accepted" if report.passed else "rejected"
    return AdaptationTransaction(
        status=status,
        state_before=before,
        state_after=after,
        observation=observation,
        report=report,
        checkpoint_before_sha256=_digest(before),
        checkpoint_after_sha256=_digest(after),
    )


def canonical_transaction_json(transaction: AdaptationTransaction) -> str:
    """Serialize a disposition deterministically for append-only records."""

    return json.dumps(transaction.to_dict(), sort_keys=True, separators=(",", ":"))
