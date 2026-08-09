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
    bundle_binding_status: str = "UNKNOWN"


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
    """Project only an explicitly observed runner record.

    A verifier disposition is not a process outcome.  In particular, this
    function must not infer an exit code, argv, stream contents, termination,
    resource enforcement, or bundle use from ``raw_status``.
    """

    observations = raw.observations
    nested = observations.get("execution_record") if isinstance(observations, Mapping) else None
    if not isinstance(nested, Mapping) and isinstance(observations, Mapping):
        nested = observations.get("execution")
    record: dict[str, Any] = dict(nested) if isinstance(nested, Mapping) else {}
    # The adapter record identity is known locally.  Every runner fact below
    # remains absent unless Forge/Fabric actually supplied it.
    record.setdefault("record_id", raw.request_id)
    return record


def _has_observed_runner_record(raw: RawEvidence) -> bool:
    observations = raw.observations
    if not isinstance(observations, Mapping):
        return False
    return isinstance(observations.get("execution_record"), Mapping) or isinstance(
        observations.get("execution"), Mapping
    )


def build_validated_receipt(
    raw: RawEvidence,
    *,
    builder: ReceiptBuilder | None = None,
    validator: ReceiptValidator | None = None,
    bundle: Any | None = None,
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
        if not _has_observed_runner_record(raw):
            return ReceiptResult(
                receipt,
                "UNKNOWN",
                "mncs_receipt_runner_facts_not_observed",
                (
                    "The official builder produced a structural envelope, but Forge did not "
                    "observe runner process facts for this verifier response.",
                ),
            )
        bundle_binding_status = "UNKNOWN"
        if bundle is not None:
            from .mncs_bundles import bind_receipt_to_bundle

            bundle_binding_status = bind_receipt_to_bundle(receipt, bundle)
            if bundle_binding_status != "PASS":
                return ReceiptResult(
                    receipt,
                    "UNKNOWN",
                    "mncs_receipt_bundle_binding_unresolved",
                    ("Receipt validation passed, but the supplied bundle binding did not pass.",),
                    bundle_binding_status,
                )
        return ReceiptResult(
            receipt,
            "PASS",
            "mncs_receipt_structurally_valid",
            ("Structural receipt validity is not assurance or conformance.",),
            bundle_binding_status,
        )
    return ReceiptResult(
        receipt,
        "FAIL",
        "mncs_receipt_structurally_invalid",
        tuple(str(issue) for issue in getattr(report, "issues", ()))
        or ("Official validator rejected the receipt.",),
    )
