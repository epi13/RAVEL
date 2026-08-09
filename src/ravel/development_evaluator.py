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
    mechanism_status: str
    execution_integrity_status: str
    matched_compute_status: str
    evidence_completeness_status: str
    provider_status: str
    receipt_status: str
    bundle_status: str
    aggregate_development_status: str


def _aggregate_status(*statuses: str) -> str:
    """Apply the declared PASS < UNKNOWN < FAIL lattice."""

    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "PASS"


def _optional_status(trial: Mapping[str, Any], name: str, reasons: list[str]) -> str:
    value = trial.get(name)
    if value is None:
        return "PASS"  # optional Forge/bundle/receipt references were not requested
    if value not in {"PASS", "FAIL", "UNKNOWN"}:
        reasons.append(f"{name}_malformed")
        return "UNKNOWN"
    # Evidence-integrity failures are unresolved evidence, not mechanism fails.
    if value == "FAIL":
        reasons.append(f"{name}_invalid")
        return "UNKNOWN"
    return str(value)


def evaluate_trial(
    trial: Mapping[str, Any],
    *,
    expected_candidate_id: str = "ravel-0.6-candidate-001",
    expected_provider_id: str | None = None,
) -> DevelopmentEvaluation:
    """Validate and evaluate one local development trial, fail-closed."""

    reasons: list[str] = []
    evidence_reasons: list[str] = []
    transaction_report: ConstraintReport | None = None
    matched_report: ConstraintReport | None = None
    mechanism_report: ConstraintReport | None = None
    if trial.get("schema") != "ravel-raw-trial/0.5":
        evidence_reasons.append("trial_schema_mismatch")
    if not isinstance(expected_candidate_id, str) or not expected_candidate_id:
        evidence_reasons.append("candidate_identity_malformed")
    provider_id = trial.get("environment_provider_id")
    if not isinstance(provider_id, str) or not provider_id:
        evidence_reasons.append("provider_identity_missing")
    elif expected_provider_id is not None and provider_id != expected_provider_id:
        evidence_reasons.append("provider_identity_mismatch")
    if trial.get("candidate_id") != expected_candidate_id:
        evidence_reasons.append("candidate_identity_mismatch")
    candidate = trial.get("candidate")
    if not isinstance(candidate, Mapping):
        evidence_reasons.append("candidate_observation_missing")
    comparisons = trial.get("comparisons")
    if not isinstance(comparisons, Mapping):
        evidence_reasons.append("comparison_observation_missing")
    transaction_value = candidate.get("adaptation_transaction") if isinstance(candidate, Mapping) else None
    matched_value = trial.get("matched_compute")
    try:
        if not isinstance(transaction_value, Mapping):
            raise ValueError("adaptation transaction is missing")
        parsed_transaction = CTransactionObservation.from_json(transaction_value)
        transaction_report = parsed_transaction.evaluate()
        mechanism_reasons = tuple(
            reason
            for reason in transaction_report.rejection_reasons
            if reason != "matched_compute_reference_unavailable"
        )
        mechanism_report = ConstraintReport(not mechanism_reasons, mechanism_reasons)
        if not isinstance(matched_value, Mapping):
            evidence_reasons.append("matched_compute_observation_missing")
        else:
            parsed_matched = MatchedComputeObservation.from_json(matched_value)
            transaction_report = parsed_transaction.evaluate(parsed_matched)
            matched_report = parsed_matched.evaluate()
            if not matched_report.passed:
                reasons.extend(matched_report.rejection_reasons)
            if parsed_matched.partition_identity != "ravel-0.6-development-adaptation-v1":
                evidence_reasons.append("partition_identity_mismatch")
        if parsed_transaction.threshold_identity != load_frozen_policy().threshold_identity:
            evidence_reasons.append("threshold_identity_mismatch")
        # The C disposition is a parity observation.  Python independently
        # derives the disposition and reports disagreement instead of trusting C.
        if matched_report is not None and parsed_transaction.committed != transaction_report.passed:
            evidence_reasons.append("c_python_disposition_disagreement")
        if not transaction_report.passed:
            reasons.extend(
                reason
                for reason in transaction_report.rejection_reasons
                if reason != "matched_compute_reference_unavailable"
            )
    except (TypeError, ValueError):
        evidence_reasons.append("malformed_required_observation")

    mechanism_status = "UNKNOWN" if mechanism_report is None else (
        "PASS" if mechanism_report.passed else "FAIL"
    )
    matched_compute_status = "UNKNOWN" if matched_report is None else (
        "PASS" if matched_report.passed else "FAIL"
    )
    provider_status = "PASS" if isinstance(provider_id, str) and provider_id else "UNKNOWN"
    evidence_completeness_status = "UNKNOWN" if evidence_reasons else "PASS"
    execution_integrity_status = _optional_status(trial, "execution_integrity_status", reasons)
    receipt_status = _optional_status(trial, "receipt_status", reasons)
    bundle_status = _optional_status(trial, "bundle_status", reasons)
    reasons.extend(evidence_reasons)
    unique_reasons = tuple(dict.fromkeys(reasons))
    aggregate = _aggregate_status(
        mechanism_status,
        execution_integrity_status,
        matched_compute_status,
        evidence_completeness_status,
        provider_status,
        receipt_status,
        bundle_status,
    )
    return DevelopmentEvaluation(
        aggregate,
        unique_reasons,
        transaction_report,
        matched_report,
        mechanism_status,
        execution_integrity_status,
        matched_compute_status,
        evidence_completeness_status,
        provider_status,
        receipt_status,
        bundle_status,
        aggregate,
    )
