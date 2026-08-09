"""Optional adapter to the MNCS experimental execution-receipt implementation.

RAVEL does not define a competing receipt schema.  When the sibling MNCS
Fabric builder and MNCS validator are installed, this module delegates to
them.  Without those optional packages it returns an explicit UNKNOWN result.
Receipt validity is structural observation only; it is never an assurance or
conformance disposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .providers import RawEvidence


ReceiptBuilder = Callable[[dict[str, Any]], dict[str, Any]]
ReceiptValidator = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class ReceiptResult:
    receipt: Mapping[str, Any] | None
    validation_status: str
    reason_code: str
    limitations: tuple[str, ...]


def _optional_builder() -> ReceiptBuilder | None:
    try:
        from mncs_fabric.receipts import build_execution_receipt
    except ImportError:
        return None
    return build_execution_receipt


def _optional_validator() -> ReceiptValidator | None:
    try:
        from mncs_validator.execution_receipt import validate_execution_receipt_value
    except ImportError:
        return None
    return validate_execution_receipt_value


def _execution_record(raw: RawEvidence) -> dict[str, Any]:
    """Project immutable Forge observations into Fabric's input vocabulary."""

    status = raw.raw_status
    termination = {
        "PASS": "COMPLETED",
        "FAIL": "NONZERO_EXIT",
        "UNKNOWN": "CAPABILITY_UNAVAILABLE",
    }[status]
    return {
        "record_id": raw.request_id,
        "job_identity": raw.request_id,
        "candidate_identity": raw.artifact_digests[0] if raw.artifact_digests else None,
        "artifact_manifest_identity": raw.artifact_digests[0] if raw.artifact_digests else None,
        "declared_argv": ["mncs-forge", "verifier", "run"],
        "declared_environment": {"environment_id": raw.environment_id},
        "termination_reason": termination,
        "exit_code": 0 if status == "PASS" else 1,
        "outcome": status,
        "results": [],
        "stdout": {"bytes": 0, "captured_utf8": "", "truncated": False},
        "stderr": {
            "bytes": len(raw.diagnostics.encode("utf-8")),
            "captured_utf8": raw.diagnostics,
            "truncated": False,
        },
        "node": {"machine_label": raw.environment_id},
        "policy_observations": {},
        "resource_observations": dict(raw.resource_observations),
    }


def build_validated_receipt(
    raw: RawEvidence,
    *,
    builder: ReceiptBuilder | None = None,
    validator: ReceiptValidator | None = None,
) -> ReceiptResult:
    """Delegate receipt construction/validation, failing closed if unavailable."""

    selected_builder = builder or _optional_builder()
    if selected_builder is None:
        return ReceiptResult(
            None,
            "UNKNOWN",
            "mncs_receipt_builder_unavailable",
            ("Install the sibling MNCS Fabric receipt adapter to build this record.",),
        )
    try:
        receipt = selected_builder(_execution_record(raw))
    except Exception as error:
        return ReceiptResult(
            None,
            "UNKNOWN",
            "mncs_receipt_builder_failed",
            (f"Receipt construction failed with {type(error).__name__}.",),
        )
    if not isinstance(receipt, Mapping):
        return ReceiptResult(None, "UNKNOWN", "mncs_receipt_malformed", ("Builder returned a non-object.",))
    selected_validator = validator or _optional_validator()
    if selected_validator is None:
        return ReceiptResult(
            receipt,
            "UNKNOWN",
            "mncs_receipt_validator_unavailable",
            ("Receipt exists, but the official MNCS validator is unavailable.",),
        )
    try:
        report = selected_validator(dict(receipt), target="<ravel>")
    except Exception as error:
        return ReceiptResult(
            receipt,
            "UNKNOWN",
            "mncs_receipt_validator_failed",
            (f"Receipt validation failed with {type(error).__name__}.",),
        )
    if getattr(report, "valid", False) is True:
        return ReceiptResult(
            receipt,
            "PASS",
            "mncs_receipt_structurally_valid",
            ("Structural receipt validity is not assurance or conformance.",),
        )
    return ReceiptResult(
        receipt,
        "FAIL",
        "mncs_receipt_structurally_invalid",
        tuple(str(issue) for issue in getattr(report, "issues", ()))
        or ("Official validator rejected the receipt.",),
    )
