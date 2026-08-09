"""Separately maintained RAVEL 0.6 development evaluator.

This evaluator consumes raw candidate observations and derives a development
disposition.  Executable ``committed`` fields, C reason strings, and RAVEL
confidence are observations or cross-check inputs, never authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .adaptation import ConstraintReport
from .c_observations import CTransactionObservation
from .matched_compute import MatchedComputeObservation
from .policy import load_frozen_policy


@dataclass(frozen=True, slots=True)
class DevelopmentEvaluation:
    status: str
    reason_codes: tuple[str, ...]
    transaction: ConstraintReport | None
    matched_compute: ConstraintReport | None


def evaluate_trial(
    trial: Mapping[str, Any],
    *,
    expected_candidate_id: str = "ravel-0.6-candidate-001",
    expected_provider_id: str | None = None,
) -> DevelopmentEvaluation:
    """Validate and evaluate one local development trial, fail-closed."""

    reasons: list[str] = []
    transaction_report: ConstraintReport | None = None
    matched_report: ConstraintReport | None = None
    if trial.get("schema") != "ravel-raw-trial/0.5":
        reasons.append("trial_schema_mismatch")
    if not isinstance(expected_candidate_id, str) or not expected_candidate_id:
        reasons.append("candidate_identity_malformed")
    provider_id = trial.get("environment_provider_id")
    if not isinstance(provider_id, str) or not provider_id:
        reasons.append("provider_identity_missing")
    elif expected_provider_id is not None and provider_id != expected_provider_id:
        reasons.append("provider_identity_mismatch")
    if trial.get("candidate_id") != expected_candidate_id:
        reasons.append("candidate_identity_mismatch")
    candidate = trial.get("candidate")
    if not isinstance(candidate, Mapping):
        reasons.append("candidate_observation_missing")
    comparisons = trial.get("comparisons")
    if not isinstance(comparisons, Mapping):
        reasons.append("comparison_observation_missing")
    transaction_value = candidate.get("adaptation_transaction") if isinstance(candidate, Mapping) else None
    matched_value = trial.get("matched_compute")
    try:
        if not isinstance(transaction_value, Mapping):
            raise ValueError("adaptation transaction is missing")
        if not isinstance(matched_value, Mapping):
            raise ValueError("matched-compute observation is missing")
        parsed_transaction = CTransactionObservation.from_json(transaction_value)
        parsed_matched = MatchedComputeObservation.from_json(matched_value)
        transaction_report = parsed_transaction.evaluate(parsed_matched)
        matched_report = parsed_matched.evaluate()
        if parsed_transaction.threshold_identity != load_frozen_policy().threshold_identity:
            reasons.append("threshold_identity_mismatch")
        if parsed_matched.partition_identity != "ravel-0.6-development-adaptation-v1":
            reasons.append("partition_identity_mismatch")
        # The C disposition is a parity observation.  Python independently
        # derives the disposition and reports disagreement instead of trusting C.
        if parsed_transaction.committed != transaction_report.passed:
            reasons.append("c_python_disposition_disagreement")
        if not transaction_report.passed:
            reasons.extend(transaction_report.rejection_reasons)
        if not matched_report.passed:
            reasons.extend(matched_report.rejection_reasons)
    except (TypeError, ValueError):
        reasons.append("malformed_required_observation")
    unique_reasons = tuple(dict.fromkeys(reasons))
    if any(reason == "malformed_required_observation" for reason in unique_reasons):
        status = "UNKNOWN"
    elif unique_reasons:
        status = "FAIL"
    else:
        status = "PASS"
    return DevelopmentEvaluation(status, unique_reasons, transaction_report, matched_report)
