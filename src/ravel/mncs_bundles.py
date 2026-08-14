"""Optional adapter to the MNCS experimental immutable execution bundle.

RAVEL stores the sibling bundle's logical and archive identities.  Bundle
path, archive, manifest, and receipt validators remain owned by MNCS.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .siblings import ensure_sibling_src


@dataclass(frozen=True, slots=True)
class BundleResult:
    status: str
    logical_identity: str | None
    archive_identity: str | None
    manifest: Mapping[str, Any] | None
    reason_code: str
    issues: tuple[str, ...] = ()


def _unknown(reason: str) -> BundleResult:
    return BundleResult("UNKNOWN", None, None, None, reason)


def _report(value: Any, *, invalid_reason: str) -> BundleResult:
    valid = bool(getattr(value, "valid", False))
    issues = tuple(str(item) for item in getattr(value, "issues", ()))
    return BundleResult(
        "PASS" if valid else "FAIL",
        getattr(value, "bundle_identity", None),
        getattr(value, "archive_identity", None),
        getattr(value, "manifest", None),
        "mncs_bundle_verified" if valid else invalid_reason,
        issues,
    )


def build_execution_bundle(
    source_manifest: Path, source_root: Path, output: Path
) -> BundleResult:
    """Delegate deterministic bundle construction to MNCS when installed."""

    ensure_sibling_src("mncs_validator")
    try:
        from mncs_validator.execution_bundle import build_execution_bundle as build
    except ImportError:
        return _unknown("mncs_bundle_implementation_unavailable")
    try:
        return _report(build(source_manifest, source_root, output), invalid_reason="mncs_bundle_invalid")
    except Exception as error:
        return BundleResult("UNKNOWN", None, None, None, "mncs_bundle_build_failed", (type(error).__name__,))


def verify_execution_bundle(
    archive: Path, *, expected_logical_identity: str | None = None
) -> BundleResult:
    """Verify an archive and optionally bind its logical identity."""

    ensure_sibling_src("mncs_validator")
    try:
        from mncs_validator.execution_bundle import verify_execution_bundle_archive
    except ImportError:
        return _unknown("mncs_bundle_implementation_unavailable")
    try:
        report = verify_execution_bundle_archive(
            archive, expected_bundle_identity=expected_logical_identity
        )
        return _report(report, invalid_reason="mncs_bundle_verification_failed")
    except Exception as error:
        return BundleResult("UNKNOWN", None, None, None, "mncs_bundle_verify_failed", (type(error).__name__,))


def bind_receipt_to_bundle(receipt: Mapping[str, Any], bundle: BundleResult) -> str:
    """Return the official binding disposition without recreating its checks."""

    if bundle.status != "PASS" or bundle.logical_identity is None:
        return "UNKNOWN"
    ensure_sibling_src("mncs_validator")
    try:
        from mncs_validator.execution_bundle import (
            ExecutionBundleReport,
            bind_receipt_to_bundle as bind,
        )
    except ImportError:
        return "UNKNOWN"
    report = ExecutionBundleReport(
        target="<ravel>",
        valid=True,
        bundle_identity=bundle.logical_identity,
        archive_identity=bundle.archive_identity,
        manifest=dict(bundle.manifest or {}),
    )
    try:
        return "PASS" if bind(dict(receipt), report).valid else "FAIL"
    except Exception:
        return "UNKNOWN"
