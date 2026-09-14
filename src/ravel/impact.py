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
import tempfile
from pathlib import Path
from typing import Any, Sequence

try:
    from .family_contract import consumers_for, load_family_graph, plan_identity, validate_plan
except ImportError:  # direct ``python src/ravel/impact.py`` transport entrypoint
    from family_contract import consumers_for, load_family_graph, plan_identity, validate_plan


IMPACT_SCHEMA = "mncs.semantic-impact/1"
PLAN_SCHEMA = "mncs.verification-plan/1"
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
class ImpactError(ValueError):
    """Impact evidence or plan input was malformed or unavailable."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


_NATIVE_LEVELS = {
    0: "changed_item",
    1: "direct_dependents",
    2: "affected_subsystem",
    3: "repository_canonical",
    4: "family",
}
_NATIVE_REASON_BITS = {
    1: "cross_repository_contract_changed",
    2: "impact_evidence_truncated",
    4: "unknown_changed_identity",
    8: "impact_evidence_truncated",
    16: "public_contract_changed",
    32: "shared_type_changed",
    64: "parser_semantics_changed",
    128: "serialization_format_changed",
    256: "effect_semantics_changed",
    512: "abi_boundary_changed",
    1024: "canonical_fixture_changed",
    2048: "language_profile_changed",
    4096: "high_connectivity_definition_changed",
    8192: "direct_dependents_affected",
}
_CHANGE_CLASS_CODES = {
    "implementation": 0,
    "public_contract": 1,
    "shared_type": 2,
    "parser_semantics": 3,
    "serialization_format": 4,
    "effect_semantics": 5,
    "abi_boundary": 6,
    "canonical_fixture": 7,
    "language_profile": 8,
    "cross_repository_contract": 9,
}


def _native_selection_policy(
    *,
    mncs: str,
    impact: dict[str, Any],
    change_class: str,
    cross_repository: bool,
    selected_tests: int,
    cwd: Path,
    libraries: Sequence[Path],
    timeout: float,
) -> tuple[str, list[str]]:
    """Ask the MNCS-native policy module for level and reason-mask semantics."""

    policy_path = Path(
        os.environ.get(
            "MNCS_VERIFICATION_POLICY",
            str(Path(__file__).resolve().parents[3] / "mncs-language" / "library" / "family" / "verification_plan.mncs"),
        )
    )
    if not policy_path.is_file():
        raise ImpactError(f"native verification policy is unavailable: {policy_path}")
    fields = {
        "cross_repository": int(cross_repository),
        "impact_complete": int(bool(impact.get("complete"))),
        "unknown_root": int("unknown_root" in set(impact.get("risk_flags", []))),
        "truncated": int("truncated" in set(impact.get("risk_flags", []))),
        "change_class": _CHANGE_CLASS_CODES[change_class],
        "high_connectivity": int("high_connectivity" in set(impact.get("risk_flags", []))),
        "shared_type": int("shared_type" in set(impact.get("risk_flags", []))),
        "effect_semantics": int("effect_semantics" in set(impact.get("risk_flags", []))),
        "abi_boundary": int("abi_boundary" in set(impact.get("risk_flags", []))),
        "public_contract": int("public_contract" in set(impact.get("risk_flags", []))),
        "direct_dependents": int(bool(impact.get("direct_dependents"))),
        "selected_tests": selected_tests,
    }
    request = {
        "schema_version": "0.1",
        "target": {"module": "mncs.family.verification_plan.v1", "function": "select_codes"},
        "arguments": [
            {"integer": {"value": value, "type": {"bits": 32, "signed": True}}}
            for value in fields.values()
        ],
        "step_budget": 512,
    }
    with tempfile.TemporaryDirectory(prefix="ravel-verification-policy-") as directory:
        request_path = Path(directory) / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        command = [mncs, "execute", str(policy_path), str(request_path)]
        environment = dict(os.environ)
        if libraries:
            environment["MNCS_LIBRARY_PATH"] = os.pathsep.join(str(path.resolve()) for path in libraries)
        raw = _run_json(command, cwd=cwd, environment=environment, timeout=timeout)
    if not isinstance(raw, dict) or raw.get("status") != "returned":
        raise ImpactError(f"native verification policy did not return a decision: {raw!r}")
    returned = raw.get("returned")
    fields_value = returned[0].get("record", {}).get("fields") if isinstance(returned, list) and returned else None
    values: dict[str, int] = {}
    for pair in fields_value if isinstance(fields_value, list) else []:
        if isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str):
            integer = pair[1].get("integer") if isinstance(pair[1], dict) else None
            if isinstance(integer, dict) and isinstance(integer.get("value"), int):
                values[pair[0]] = integer["value"]
    level = _NATIVE_LEVELS.get(values.get("level_code"))
    if level is None:
        raise ImpactError(f"native verification policy returned an unknown level: {values!r}")
    mask = values.get("reason_mask", 0)
    reasons = sorted({reason for bit, reason in _NATIVE_REASON_BITS.items() if mask & bit})
    return level, reasons


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
    """Compatibility fallback for offline callers without the MNCS runtime.

    The normal ``request_verification_plan`` path supplies the native policy
    module.  This pure helper remains only for bounded provider-failure and
    unit-fixture paths, where it fails closed to the same canonical scopes.
    """

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
    family_graph: dict[str, Any] | None = None,
    producer_repository: str = "ravel",
    contract_identity: str | None = None,
    policy_runtime: str | None = None,
    policy_cwd: Path | None = None,
    policy_libraries: Sequence[Path] = (),
    policy_timeout: float = 60.0,
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
    if policy_runtime is not None:
        level, reasons = _native_selection_policy(
            mncs=policy_runtime,
            impact=impact,
            change_class=change_class,
            cross_repository=cross_repository,
            selected_tests=len(impacted_tests),
            cwd=(policy_cwd or source_path.parent).resolve(),
            libraries=policy_libraries,
            timeout=policy_timeout,
        )
    else:
        level, reasons = select_level(
            impact,
            change_class=change_class,
            cross_repository=cross_repository,
        )
    # A neighborhood with no joinable tests cannot establish a narrow
    # behavioral proof. Run the canonical inventory in that case, and make
    # the uncertainty visible in the plan.
    if not impacted_tests and tests and not cross_repository:
        level = "repository_canonical"
        reasons = sorted(set(reasons + ["test_selection_unresolved"]))
        selected = sorted(test_by_id)
    else:
        selected = sorted(impacted_tests)
    if family_graph is None:
        cross_repository_projection: dict[str, Any] = {
            "graph_identity": sha256_bytes(b"no-cross-repository-overlay"),
            "edges": [],
            "selected_repositories": [],
            "complete": not cross_repository,
            "limitations": [
                "cross-repository topology was not requested"
                if not cross_repository
                else "cross-repository topology was requested but no family overlay was supplied"
            ],
        }
    else:
        edges = consumers_for(
            family_graph,
            producer_repository=producer_repository,
            contract_identity=contract_identity,
        )
        cross_repository_projection = {
            "graph_identity": family_graph["graph_identity"],
            "edges": edges,
            "selected_repositories": sorted({edge["consumer_repository"] for edge in edges}),
            "complete": bool(family_graph.get("complete")),
            "limitations": list(family_graph.get("limitations", [])),
        }
    if cross_repository and not cross_repository_projection["complete"]:
        reasons = sorted(set(reasons + ["cross_repository_graph_incomplete"]))

    # A source inventory is not a repository-wide canonical proof.  The
    # compiler currently reports a source/module inventory, so a canonical
    # request remains non-stopping until an executor supplies repository scope.
    inventory_scope = str(inventory.get("scope", "source"))
    sufficient = bool(selected) and level != "family" and (
        level != "repository_canonical" or inventory_scope == "repository"
    )
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
            "cross_repository": cross_repository_projection,
        },
        "selection": {
            "level": level,
            "selected_test_identities": selected,
            "available_test_count": len(tests),
            "escalation_reasons": reasons,
            "selected_repositories": cross_repository_projection["selected_repositories"],
            "available_repository_count": len(family_graph.get("repositories", [])) if family_graph else 0,
        },
        "proof": {
            "sufficient_to_stop": sufficient,
            "required_evidence": required_evidence,
            "boundary": {
                "claimed_scope": "family" if level == "family" else ("repository" if level == "repository_canonical" else level),
                "established": sufficient,
                "executor": "family-router" if level == "family" else "mncs-test",
                "stop_condition": required_evidence[0],
            },
        },
        "provenance": {
            "provider": "ravel",
            "policy": "bounded-impact-v1",
            "compiler_impact_schema": IMPACT_SCHEMA,
            **(provenance or {}),
            "dependencies": {
                "source_sha256": source_sha256,
                "semantic_graph_identity": impact["graph_identity"],
                "inventory_subject_identity": inventory.get("subject_identity"),
                "inventory_subject_fingerprint": inventory.get("subject_fingerprint"),
                "family_graph_identity": cross_repository_projection["graph_identity"],
                "selected_test_identities": selected,
                "contract_revision": PLAN_SCHEMA,
            },
        },
    }
    for field in ("subject_identity", "subject_fingerprint"):
        if isinstance(inventory.get(field), str) and inventory[field]:
            payload["source"][field] = inventory[field]
    payload["plan_id"] = plan_identity(payload)
    try:
        return validate_plan(payload, source_path=source_path)
    except ValueError as error:
        raise ImpactError(str(error)) from error


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
    family_graph_path: Path | None = None,
    producer_repository: str = "ravel",
    contract_identity: str | None = None,
) -> dict[str, Any]:
    if not roots:
        raise ImpactError("at least one changed semantic identity is required")
    if max_depth < 1 or max_nodes < 1:
        raise ImpactError("impact bounds must be positive")
    source_path = source_path.resolve()
    family_graph = load_family_graph(family_graph_path) if family_graph_path else None
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
        family_graph=family_graph,
        producer_repository=producer_repository,
        contract_identity=contract_identity,
        policy_runtime=mncs if impact_error is None and inventory_error is None else None,
        policy_cwd=base,
        policy_libraries=libraries,
        policy_timeout=timeout,
        provenance={
            "mncs": str(Path(mncs).resolve()) if Path(mncs).exists() else mncs,
            "roots_requested": sorted(set(roots)),
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "change_class": change_class,
            "cross_repository": cross_repository,
            "producer_repository": producer_repository,
            "contract_identity": contract_identity,
            "family_graph_identity": family_graph.get("graph_identity") if family_graph else None,
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
    parser.add_argument("--family-graph", type=Path)
    parser.add_argument("--repository", default="ravel")
    parser.add_argument("--contract-identity")
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
            family_graph_path=args.family_graph,
            producer_repository=args.repository,
            contract_identity=args.contract_identity,
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
