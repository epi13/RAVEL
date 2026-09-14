"""Bounded semantic-impact planning for the MNCS development loop.

RAVEL owns the bounded selection policy, not compiler semantics.  The
compiler's ``mncs.semantic-impact/1`` document is the only source of graph
relationships; this module validates that projection, joins it to the
compiler-owned test inventory, and emits the shared
``mncs.verification-plan/1`` transport contract for mncs-test and Forge.

The subprocess calls in this module are platform transport.  RAVEL never
parses source text or rebuilds a call graph, and every failure to acquire
impact evidence becomes an explicit canonical escalation rather than a
silently optimistic narrow plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


IMPACT_SCHEMA = "mncs.semantic-impact/1"
PLAN_SCHEMA = "mncs.verification-plan/1"
PLAN_LEVELS = (
    "changed_item",
    "direct_dependents",
    "affected_subsystem",
    "repository_canonical",
    "family",
)
CHANGE_CLASSES = {
    "implementation",
    "public_contract",
    "shared_type",
    "parser_semantics",
    "serialization_format",
    "effect_semantics",
    "abi_boundary",
    "canonical_fixture",
    "language_profile",
    "cross_repository_contract",
}
ESCALATION_REASONS = {
    "direct_dependents_affected",
    "public_contract_changed",
    "shared_type_changed",
    "parser_semantics_changed",
    "serialization_format_changed",
    "effect_semantics_changed",
    "abi_boundary_changed",
    "canonical_fixture_changed",
    "high_connectivity_definition_changed",
    "dependent_targeted_test_failed",
    "insufficient_diagnostic_evidence",
    "migration_broad_semantic_surface",
    "language_profile_changed",
    "cross_repository_contract_changed",
    "impact_evidence_truncated",
    "unknown_changed_identity",
}


class ImpactError(ValueError):
    """Impact evidence or plan input was malformed or unavailable."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ImpactError(f"{field} must be a list of non-empty strings")
    return sorted(set(value))


def validate_impact(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != IMPACT_SCHEMA:
        raise ImpactError(f"compiler impact must be {IMPACT_SCHEMA}")
    if not isinstance(document.get("graph_identity"), str) or not document["graph_identity"]:
        raise ImpactError("impact graph_identity is missing")
    roots = _strings(document.get("roots"), "impact roots")
    if not isinstance(document.get("complete"), bool):
        raise ImpactError("impact complete must be boolean")
    for field in ("direct_dependents", "test_identities", "risk_flags", "limitations"):
        _strings(document.get(field), f"impact {field}")
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        raise ImpactError("impact nodes must be a list")
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not isinstance(node.get("identity"), str):
            raise ImpactError(f"impact nodes[{index}] must carry an identity")
    result = dict(document)
    result["roots"] = roots
    result["direct_dependents"] = _strings(document["direct_dependents"], "impact direct_dependents")
    result["test_identities"] = _strings(document["test_identities"], "impact test_identities")
    result["risk_flags"] = _strings(document["risk_flags"], "impact risk_flags")
    result["limitations"] = _strings(document["limitations"], "impact limitations")
    result["affected_count"] = len(nodes)
    return result


def _inventory_tests(inventory_document: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(inventory_document, dict) or inventory_document.get("schema_version") != "mncs.test-inventory/1":
        raise ImpactError("compiler inventory has an unsupported schema")
    if inventory_document.get("valid") is not True or not isinstance(inventory_document.get("inventory"), dict):
        raise ImpactError("compiler did not establish a valid test inventory")
    inventory = inventory_document["inventory"]
    tests = inventory.get("tests")
    if not isinstance(tests, list) or not all(isinstance(test, dict) for test in tests):
        raise ImpactError("compiler inventory tests must be a list of objects")
    for index, test in enumerate(tests):
        if not all(isinstance(test.get(field), str) and test[field] for field in ("test_case_identity", "function_identity")):
            raise ImpactError(f"compiler inventory tests[{index}] lacks stable identities")
    return inventory, tests


def _reason_for_change(change_class: str) -> str | None:
    mapping = {
        "public_contract": "public_contract_changed",
        "shared_type": "shared_type_changed",
        "parser_semantics": "parser_semantics_changed",
        "serialization_format": "serialization_format_changed",
        "effect_semantics": "effect_semantics_changed",
        "abi_boundary": "abi_boundary_changed",
        "canonical_fixture": "canonical_fixture_changed",
        "language_profile": "language_profile_changed",
        "cross_repository_contract": "cross_repository_contract_changed",
    }
    return mapping.get(change_class)


def select_level(
    impact: dict[str, Any],
    *,
    change_class: str,
    cross_repository: bool = False,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    explicit_reason = _reason_for_change(change_class)
    if cross_repository or change_class == "cross_repository_contract":
        reasons.append("cross_repository_contract_changed")
        return "family", sorted(set(reasons))
    if not impact.get("complete"):
        reasons.append("impact_evidence_truncated")
    risk_flags = set(impact.get("risk_flags", []))
    if "unknown_root" in risk_flags:
        reasons.append("unknown_changed_identity")
    if "truncated" in risk_flags:
        reasons.append("impact_evidence_truncated")
    if explicit_reason:
        reasons.append(explicit_reason)
    if reasons:
        return "repository_canonical", sorted(set(reasons))
    risk_reasons = {
        reason
        for flag, reason in (
            ("high_connectivity", "high_connectivity_definition_changed"),
            ("shared_type", "shared_type_changed"),
            ("effect_semantics", "effect_semantics_changed"),
            ("abi_boundary", "abi_boundary_changed"),
            ("public_contract", "public_contract_changed"),
        )
        if flag in risk_flags
    }
    if "public_contract" in risk_flags:
        return "repository_canonical", sorted(risk_reasons)
    if risk_reasons:
        return "affected_subsystem", sorted(risk_reasons)
    if impact.get("direct_dependents"):
        return "direct_dependents", ["direct_dependents_affected"]
    return "changed_item", []


def build_verification_plan(
    impact_document: dict[str, Any],
    inventory_document: dict[str, Any],
    *,
    source_path: Path,
    source_sha256: str | None = None,
    change_class: str = "implementation",
    cross_repository: bool = False,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Join compiler evidence into a deterministic minimum-proof plan."""

    if change_class not in CHANGE_CLASSES:
        raise ImpactError(f"unsupported change class: {change_class}")
    impact = validate_impact(impact_document)
    inventory, tests = _inventory_tests(inventory_document)
    try:
        actual_source_sha256 = sha256_bytes(source_path.read_bytes())
    except OSError as error:
        raise ImpactError(f"source is unavailable for verification planning: {source_path}") from error
    if source_sha256 is not None and source_sha256 != actual_source_sha256:
        raise ImpactError("verification plan source sha256 does not match the current source")
    source_sha256 = actual_source_sha256
    test_by_id = {test["test_case_identity"]: test for test in tests}
    impacted_tests = [identity for identity in impact["test_identities"] if identity in test_by_id]
    level, reasons = select_level(
        impact,
        change_class=change_class,
        cross_repository=cross_repository,
    )
    # A neighborhood with no joinable tests cannot establish a narrow
    # behavioral proof. Run the canonical inventory in that case, and make
    # the uncertainty visible in the plan.
    if not impacted_tests and tests:
        level = "repository_canonical"
        reasons = sorted(set(reasons + ["insufficient_diagnostic_evidence"]))
        selected = sorted(test_by_id)
    else:
        selected = sorted(impacted_tests)
    # A local plan can establish a stop condition after its selected proof.
    # Family selection is only a routing decision: the local inventory cannot
    # establish family-wide proof by itself.
    sufficient = bool(selected) and level != "family"
    required_evidence = [
        "selected_test_cases_pass" if level != "family" else "family_verification_pass",
    ]
    if level == "repository_canonical":
        required_evidence = ["repository_canonical_suite_pass"]
    payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA,
        "source": {
            "path": str(source_path.resolve()),
            "sha256": source_sha256,
            "subject_identity": inventory.get("subject_identity"),
            "subject_fingerprint": inventory.get("subject_fingerprint"),
        },
        "impact": {
            "graph_identity": impact["graph_identity"],
            "roots": impact["roots"],
            "affected_count": impact["affected_count"],
            "direct_dependents": impact["direct_dependents"],
            "test_identities": impact["test_identities"],
            "risk_flags": impact["risk_flags"],
            "complete": impact["complete"],
            "limitations": impact["limitations"],
        },
        "selection": {
            "level": level,
            "selected_test_identities": selected,
            "available_test_count": len(tests),
            "escalation_reasons": reasons,
        },
        "proof": {
            "sufficient_to_stop": sufficient,
            "required_evidence": required_evidence,
        },
        "provenance": {
            "provider": "ravel",
            "policy": "bounded-impact-v1",
            "compiler_impact_schema": IMPACT_SCHEMA,
            **(provenance or {}),
        },
    }
    plan_id = sha256_bytes(canonical_bytes(payload))
    payload["plan_id"] = plan_id
    return payload


def _run_json(command: Sequence[str], *, cwd: Path, environment: dict[str, str], timeout: float) -> Any:
    try:
        process = subprocess.run(
            list(command),
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ImpactError(f"impact provider command unavailable: {error}") from error
    try:
        document = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise ImpactError(f"impact provider emitted non-JSON output: {error}") from error
    if process.returncode != 0:
        raise ImpactError(f"impact provider command failed with exit {process.returncode}")
    return document


def _unavailable_impact(roots: Sequence[str], error: ImpactError) -> dict[str, Any]:
    """Represent unavailable compiler impact as an explicit canonical escalation."""

    limitation = f"compiler impact evidence unavailable: {error}"
    return {
        "schema_version": IMPACT_SCHEMA,
        "graph_identity": sha256_bytes(limitation.encode("utf-8")),
        "roots": sorted(set(roots)),
        "nodes": [],
        "edges": [],
        "direct_dependents": [],
        "test_identities": [],
        "risk_flags": ["unknown_root"],
        "complete": False,
        "limitations": [limitation],
    }


def request_verification_plan(
    *,
    source_path: Path,
    mncs: str,
    roots: Sequence[str],
    libraries: Sequence[Path] = (),
    cwd: Path | None = None,
    max_depth: int = 4,
    max_nodes: int = 256,
    timeout: float = 60.0,
    change_class: str = "implementation",
    cross_repository: bool = False,
) -> dict[str, Any]:
    if not roots:
        raise ImpactError("at least one changed semantic identity is required")
    if max_depth < 1 or max_nodes < 1:
        raise ImpactError("impact bounds must be positive")
    source_path = source_path.resolve()
    base = (cwd or source_path.parent).resolve()
    environment = dict(os.environ)
    if libraries:
        environment["MNCS_LIBRARY_PATH"] = os.pathsep.join(str(path.resolve()) for path in libraries)
    impact_command = [mncs, "impact", str(source_path)]
    for root in roots:
        impact_command.extend(("--root", root))
    impact_command.extend(("--max-depth", str(max_depth), "--max-nodes", str(max_nodes)))
    impact_error: ImpactError | None = None
    try:
        impact_document = _run_json(
            impact_command, cwd=base, environment=environment, timeout=timeout
        )
    except ImpactError as error:
        # The safe fallback is a canonical-boundary plan, not a guessed narrow
        # selection.  Preserve the provider failure in the plan limitations.
        impact_error = error
        impact_document = _unavailable_impact(roots, error)
    inventory_error: ImpactError | None = None
    try:
        inventory_document = _run_json(
            [mncs, "test-inventory", str(source_path)],
            cwd=base,
            environment=environment,
            timeout=timeout,
        )
    except ImpactError as error:
        # No inventory means no executable identity can be selected. Emit an
        # explicit non-stopping plan so mncs-test fails closed with the
        # provider diagnosis instead of treating zero tests as proof.
        inventory_error = error
        inventory_document = {
            "schema_version": "mncs.test-inventory/1",
            "valid": True,
            "inventory": {"tests": []},
        }
    return build_verification_plan(
        impact_document,
        inventory_document,
        source_path=source_path,
        change_class=change_class,
        cross_repository=cross_repository,
        provenance={
            "mncs": str(Path(mncs).resolve()) if Path(mncs).exists() else mncs,
            "roots_requested": sorted(set(roots)),
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "change_class": change_class,
            "cross_repository": cross_repository,
            "impact_provider_error": str(impact_error) if impact_error is not None else None,
            "inventory_provider_error": str(inventory_error) if inventory_error is not None else None,
        },
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAVEL bounded MNCS semantic-impact planner")
    parser.add_argument("source", type=Path)
    parser.add_argument("--mncs", required=True)
    parser.add_argument("--root", dest="roots", action="append", required=True)
    parser.add_argument("--library", dest="libraries", action="append", default=[])
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--max-nodes", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--change-class", choices=sorted(CHANGE_CLASSES), default="implementation")
    parser.add_argument("--cross-repository", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = request_verification_plan(
            source_path=args.source,
            mncs=args.mncs,
            roots=args.roots,
            libraries=[Path(value) for value in args.libraries],
            cwd=args.cwd,
            max_depth=args.max_depth,
            max_nodes=args.max_nodes,
            timeout=args.timeout,
            change_class=args.change_class,
            cross_repository=args.cross_repository,
        )
    except (ImpactError, OSError, ValueError) as error:
        print(json.dumps({"schema_version": PLAN_SCHEMA, "status": "UNKNOWN", "error": str(error)}, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    output = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
