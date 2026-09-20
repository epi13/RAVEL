"""Deterministic RAVEL obligation/evidence projection.

The native RAVEL policy still owns verification level, escalation vocabulary,
and proof boundary. This module performs the bounded, identity-based join from
that decision to a repository-owned obligation inventory. It never executes a
provider and never upgrades evidence to PASS.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from .family_contract import (
        obligation_inventory_identity,
        obligation_plan_identity,
        validate_obligation_inventory,
        validate_obligation_plan,
    )
except ImportError:  # direct script execution
    from family_contract import (  # type: ignore
        obligation_inventory_identity,
        obligation_plan_identity,
        validate_obligation_inventory,
        validate_obligation_plan,
    )


ACTIVE_LIFECYCLES = {"permanent", "transitional"}
ORDINARY_EXCLUDED_LIFECYCLES = {"scheduled", "reference_only", "retired"}


def _strings(value: Any) -> list[str]:
    return sorted({item for item in value if isinstance(item, str) and item}) if isinstance(value, list) else []


def _compiler_tests(inventory_document: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(inventory_document, Mapping):
        return []
    inventory = inventory_document.get("inventory")
    tests = inventory.get("tests") if isinstance(inventory, Mapping) else None
    return [item for item in tests if isinstance(item, dict)] if isinstance(tests, list) else []


def _test_case_identities(obligation: Mapping[str, Any], compiler_inventory: Mapping[str, Any] | None) -> list[str]:
    executor = obligation.get("executor", {})
    explicit = _strings(executor.get("test_case_identities")) if isinstance(executor, Mapping) else []
    declaration_ids = set(_strings(executor.get("declaration_identities"))) if isinstance(executor, Mapping) else set()
    subjects = set(_strings(obligation.get("subjects")))
    dependencies = set(_strings(obligation.get("invalidation_dependencies")))
    selected: set[str] = set(explicit)
    for test in _compiler_tests(compiler_inventory):
        if "*" in declaration_ids:
            if isinstance(test.get("test_case_identity"), str):
                selected.add(test["test_case_identity"])
        elif declaration_ids and test.get("declaration_identity") in declaration_ids:
            if isinstance(test.get("test_case_identity"), str):
                selected.add(test["test_case_identity"])
        elif test.get("function_identity") in subjects or test.get("function_identity") in dependencies:
            if isinstance(test.get("test_case_identity"), str):
                selected.add(test["test_case_identity"])
    return sorted(selected)


def _matches_impact(obligation: Mapping[str, Any], impact: Mapping[str, Any]) -> bool:
    tokens = set(
        _strings(impact.get("roots"))
        + _strings(impact.get("direct_dependents"))
        + _strings(impact.get("test_identities"))
        + [
            item.get("identity")
            for item in impact.get("nodes", [])
            if isinstance(item, Mapping) and isinstance(item.get("identity"), str)
        ]
    )
    subjects = set(_strings(obligation.get("subjects")))
    dependencies = set(_strings(obligation.get("invalidation_dependencies")))
    if "*" in subjects or "*" in dependencies:
        return True
    if tokens.intersection(subjects | dependencies):
        return True
    domains = set(_strings(impact.get("guarantee_domains")))
    return obligation.get("guarantee_domain") in domains and bool(tokens)


def _source_identity(verification_plan: Mapping[str, Any]) -> tuple[str | None, str | None]:
    source = verification_plan.get("source")
    if not isinstance(source, Mapping):
        return None, None
    subject_identity = source.get("subject_identity")
    subject_fingerprint = source.get("subject_fingerprint")
    return (
        subject_identity if isinstance(subject_identity, str) else None,
        subject_fingerprint if isinstance(subject_fingerprint, str) else None,
    )


def _evidence_state(
    obligation_identity: str,
    current_evidence: Sequence[Mapping[str, Any]],
    *,
    subject_identity: str | None,
    subject_fingerprint: str | None,
    inventory_identity: str,
) -> tuple[str, str, list[str], list[dict[str, Any]]]:
    related = [
        dict(item)
        for item in current_evidence
        if item.get("obligation_identity") == obligation_identity
    ]
    if not related:
        return "new_execution_required", "no identity-bound evidence is available", [], []
    exact: list[dict[str, Any]] = []
    for item in related:
        if subject_identity and item.get("subject_identity") not in (None, subject_identity):
            continue
        if subject_fingerprint and item.get("subject_fingerprint") not in (None, subject_fingerprint):
            continue
        if item.get("definition_identity") not in (None, inventory_identity):
            continue
        exact.append(item)
    statuses = {item.get("status") for item in exact}
    identities = sorted(
        item["evidence_identity"]
        for item in exact
        if isinstance(item.get("evidence_identity"), str)
    )
    if len(statuses) > 1:
        return "contradictory", "identity-bound evidence has contradictory verdicts", identities, exact
    if exact and statuses == {"PASS"}:
        return "current", "current identity-bound PASS evidence can be reused", identities, exact
    if exact and statuses == {"FAIL"}:
        return "escalation_required", "current identity-bound evidence is FAIL", identities, exact
    if exact and statuses == {"UNKNOWN"}:
        return "escalation_required", "current identity-bound evidence is UNKNOWN", identities, exact
    return "stale", "evidence exists but its subject or definition identity is stale", identities, related


def build_obligation_plan(
    verification_plan: Mapping[str, Any],
    obligation_inventory: Mapping[str, Any],
    *,
    source_path: Path,
    compiler_inventory: Mapping[str, Any] | None = None,
    current_evidence: Sequence[Mapping[str, Any]] = (),
    commons_root: Path | None = None,
) -> dict[str, Any]:
    """Join a native RAVEL plan to a repository-owned obligation inventory."""

    normalized_inventory = validate_obligation_inventory(
        dict(obligation_inventory), commons_root=commons_root
    )
    impact = verification_plan.get("impact")
    if not isinstance(impact, Mapping):
        raise ValueError("verification plan impact is unavailable")
    source_sha256 = verification_plan.get("source", {}).get("sha256") if isinstance(verification_plan.get("source"), Mapping) else None
    if not isinstance(source_sha256, str):
        raise ValueError("verification plan source sha256 is unavailable")
    subject_identity, subject_fingerprint = _source_identity(verification_plan)
    impact_domains = _strings(impact.get("guarantee_domains")) or ["semantic"]
    change_kinds = _strings(impact.get("change_kinds"))
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reasons: set[str] = set()
    for obligation in normalized_inventory["obligations"]:
        lifecycle = obligation["lifecycle"]
        if lifecycle in ORDINARY_EXCLUDED_LIFECYCLES:
            excluded.append(
                {
                    "identity": obligation["identity"],
                    "lifecycle": lifecycle,
                    "reason": "lifecycle is not part of ordinary verification",
                }
            )
            continue
        if lifecycle not in ACTIVE_LIFECYCLES:
            excluded.append(
                {
                    "identity": obligation["identity"],
                    "lifecycle": lifecycle,
                    "reason": "inventory lifecycle is not executable",
                }
            )
            continue
        if not _matches_impact(obligation, impact):
            excluded.append(
                {
                    "identity": obligation["identity"],
                    "lifecycle": lifecycle,
                    "reason": "no compiler-owned subject, dependency, or guarantee-domain intersection",
                }
            )
            continue
        status, reason, evidence_ids, _ = _evidence_state(
            obligation["identity"],
            current_evidence,
            subject_identity=subject_identity,
            subject_fingerprint=subject_fingerprint,
            inventory_identity=obligation_inventory_identity(normalized_inventory, commons_root=commons_root),
        )
        if status in {"stale", "contradictory", "escalation_required"}:
            reasons.add({"stale": "evidence_stale", "contradictory": "evidence_contradictory", "escalation_required": "evidence_escalation_required"}[status])
        test_case_ids = _test_case_identities(obligation, compiler_inventory)
        if obligation["executor"]["kind"] == "native_first_class_test" and not test_case_ids:
            status = "selection_unresolved"
            reason = "native obligation has no current compiler test-case identity"
            reasons.add("obligation_selection_unresolved")
        selected.append(
            {
                "identity": obligation["identity"],
                "status": status,
                "lifecycle": lifecycle,
                "guarantee_domain": obligation["guarantee_domain"],
                "evidence_role": obligation["evidence_role"],
                "reason": reason,
                "evidence_identities": evidence_ids,
                "test_case_identities": test_case_ids,
                "executor": obligation["executor"],
            }
        )
    if not selected:
        reasons.add("obligation_selection_unresolved")
    if not bool(verification_plan.get("proof", {}).get("sufficient_to_stop")):
        reasons.add("verification_plan_not_sufficient")
    plan_selection = verification_plan.get("selection", {})
    if isinstance(plan_selection, Mapping):
        reasons.update(_strings(plan_selection.get("escalation_reasons")))
    required = [item["identity"] for item in selected]
    needs_execution = [
        item["identity"]
        for item in selected
        if item["status"] in {"new_execution_required", "stale", "selection_unresolved", "escalation_required", "contradictory"}
    ]
    sufficient = bool(verification_plan.get("proof", {}).get("sufficient_to_stop")) and bool(selected) and not needs_execution and not reasons.intersection(
        {"obligation_selection_unresolved", "evidence_stale", "evidence_contradictory", "evidence_escalation_required", "verification_plan_not_sufficient"}
    )
    payload: dict[str, Any] = {
        "schema_version": "mncs.verification-obligation-plan/1",
        "verification_plan_id": str(verification_plan.get("plan_id", "")),
        "source": {
            "path": str(source_path.resolve()),
            "sha256": source_sha256,
        },
        "impact_identity": str(impact.get("graph_identity", "")),
        "impact": {
            "guarantee_domains": sorted(set(impact_domains)),
            "change_kinds": change_kinds,
            "roots": _strings(impact.get("roots")),
        },
        "inventory": {
            "repository": normalized_inventory["repository"],
            "revision": normalized_inventory["revision"],
            "identity": obligation_inventory_identity(normalized_inventory, commons_root=commons_root),
        },
        "obligations": selected,
        "excluded": excluded,
        "evidence": [dict(item) for item in current_evidence],
        "stop": {
            "sufficient_to_stop": sufficient,
            "required_obligation_identities": required,
            "new_execution_required": needs_execution,
            "escalation_reasons": sorted(reasons),
            "boundary": str(verification_plan.get("proof", {}).get("boundary", {}).get("claimed_scope", "unknown")),
        },
    }
    payload["obligation_plan_id"] = obligation_plan_identity(payload, commons_root=commons_root)
    return validate_obligation_plan(payload, commons_root=commons_root)


def load_current_evidence(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    import json

    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, Mapping):
        value = value.get("evidence", [])
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError("current evidence must be an array or an object with an evidence array")
    return [dict(item) for item in value]
