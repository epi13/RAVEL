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
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from .family_contract import (
        consumers_for,
        contract_vocab,
        default_family_graph_path,
        load_family_graph,
        plan_identity,
        validate_plan,
    )
except ImportError:  # direct ``python src/ravel/impact.py`` transport entrypoint
    from family_contract import (
        consumers_for,
        contract_vocab,
        default_family_graph_path,
        load_family_graph,
        plan_identity,
        validate_plan,
    )

try:
    from .generated.verification_policy import (
        Binding as VerificationPlanBinding,
        ChangeClass as NativeChangeClass,
        SelectionInput,
    )
except ImportError:  # direct script execution
    from generated.verification_policy import (
        Binding as VerificationPlanBinding,
        ChangeClass as NativeChangeClass,
        SelectionInput,
    )

try:
    from .obligations import (
        build_native_obligation_plan,
        build_obligation_plan,
        load_current_evidence,
    )
except ImportError:  # direct script execution
    from obligations import (  # type: ignore
        build_native_obligation_plan,
        build_obligation_plan,
        load_current_evidence,
    )


IMPACT_SCHEMA = "mncs.semantic-impact/1"
PLAN_SCHEMA = "mncs.verification-plan/1"
OBLIGATION_PLAN_SCHEMA = "mncs.verification-obligation-plan/1"
SEMANTIC_PROVIDER = "ravel.verification_policy"
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
GUARANTEE_DOMAINS = {
    "semantic",
    "parser_front_end",
    "type_system",
    "compiler",
    "runtime",
    "backend_portability",
    "integration",
    "family_contract",
}
CHANGE_KINDS = {
    "private_implementation",
    "public_contract",
    "shared_type",
    "parser_semantics",
    "type_system",
    "effect_capability",
    "abi",
    "runtime_semantics",
    "backend_lowering",
    "language_profile",
    "canonical_fixture",
    "cross_repository_contract",
    "unknown",
}
class ImpactError(ValueError):
    """Impact evidence or plan input was malformed or unavailable."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ImpactError(f"{field} must be a list of non-empty strings")
    return sorted(set(value))


def _ordered_strings(value: Any, field: str) -> list[str]:
    """Validate an ordered compiler classification without rewriting it.

    Classification arrays are compiler-owned facts transported through the
    native planner.  Their order is part of the parity surface, so preserve
    the first occurrence while still rejecting empty values and duplicates.
    """

    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ImpactError(f"{field} must be a list of non-empty strings")
    result: list[str] = []
    for item in value:
        if item in result:
            continue
        result.append(item)
    return result


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
    guarantee_domains = document.get("guarantee_domains")
    if guarantee_domains is None:
        guarantee_domains = ["semantic"] if not result["risk_flags"] else []
        if "shared_type" in result["risk_flags"]:
            guarantee_domains.extend(["type_system", "compiler", "runtime", "backend_portability"])
        if "public_contract" in result["risk_flags"]:
            guarantee_domains.extend(["semantic", "compiler", "family_contract", "integration"])
        if "effect_semantics" in result["risk_flags"]:
            guarantee_domains.extend(["semantic", "runtime", "integration"])
        if "abi_boundary" in result["risk_flags"]:
            guarantee_domains.extend(["compiler", "runtime", "backend_portability"])
        if "unknown_root" in result["risk_flags"] or "truncated" in result["risk_flags"]:
            guarantee_domains.extend(["compiler", "integration"])
    result["guarantee_domains"] = _ordered_strings(guarantee_domains, "impact guarantee_domains")
    unknown_domains = sorted(set(result["guarantee_domains"]) - GUARANTEE_DOMAINS)
    if unknown_domains:
        raise ImpactError(f"impact guarantee_domains contain unsupported values: {unknown_domains}")
    change_kinds = document.get("change_kinds")
    if change_kinds is None:
        change_kinds = ["unknown"] if ("unknown_root" in result["risk_flags"] or not result["complete"]) else ["private_implementation"]
        if "public_contract" in result["risk_flags"]:
            change_kinds.append("public_contract")
        if "shared_type" in result["risk_flags"]:
            change_kinds.append("shared_type")
        if "effect_semantics" in result["risk_flags"]:
            change_kinds.append("effect_capability")
        if "abi_boundary" in result["risk_flags"]:
            change_kinds.append("abi")
    result["change_kinds"] = _ordered_strings(change_kinds, "impact change_kinds")
    unknown_kinds = sorted(set(result["change_kinds"]) - CHANGE_KINDS)
    if unknown_kinds:
        raise ImpactError(f"impact change_kinds contain unsupported values: {unknown_kinds}")
    result["classification_schema_version"] = document.get(
        "classification_schema_version", "mncs.semantic-impact-classification/1"
    )
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
    commons_root: Path | None = None,
    cross_repository_graph_incomplete: bool = False,
    family_registry_coverage_incomplete: bool = False,
) -> tuple[str, list[str], bool]:
    """Ask the MNCS-native policy for typed level, reasons, and sufficiency.

    The request crosses the language-owned typed-call membrane.  RAVEL names
    record fields and the enum variant; the compiler/runtime supplies scalar
    widths, nominal identities, and canonical field order from the callable
    interface metadata.
    """

    policy_path = Path(
        os.environ.get(
            "MNCS_VERIFICATION_POLICY",
            str(Path(__file__).resolve().parents[2] / "mncs" / "workspace" / "ravel" / "verification_policy.mncs"),
        )
    )
    if not policy_path.is_file():
        raise ImpactError(f"native verification policy is unavailable: {policy_path}")
    risk_flags = set(impact.get("risk_flags", []))
    try:
        decision = VerificationPlanBinding(str(mncs), policy_path, libraries=tuple(libraries), timeout=timeout).choose(
            SelectionInput(
                cross_repository=cross_repository,
                impact_complete=bool(impact.get("complete")),
                unknown_root="unknown_root" in risk_flags,
                truncated="truncated" in risk_flags,
                change_class=NativeChangeClass(change_class),
                high_connectivity="high_connectivity" in risk_flags,
                shared_type="shared_type" in risk_flags,
                effect_semantics="effect_semantics" in risk_flags,
                abi_boundary="abi_boundary" in risk_flags,
                public_contract="public_contract" in risk_flags,
                direct_dependents=bool(impact.get("direct_dependents")),
                selected_tests=selected_tests,
                selection_unresolved=selected_tests == 0,
                cross_repository_graph_incomplete=cross_repository_graph_incomplete,
                family_registry_coverage_incomplete=family_registry_coverage_incomplete,
            )
        )
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise ImpactError(f"native verification policy binding failed: {error}") from error
    levels, reasons_vocab = contract_vocab(commons_root=commons_root)
    level = decision.level.value
    reasons = [reason.value for reason in decision.reasons if reason.value != "none"]
    if level not in levels or any(reason not in reasons_vocab for reason in reasons):
        raise ImpactError(f"generated verification binding returned an unknown semantic value: {decision!r}")
    return level, reasons, decision.sufficient_local


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
    commons_root: Path | None = None,
    producer_repository: str = "ravel",
    contract_identity: str | None = None,
    policy_runtime: str | None = None,
    policy_cwd: Path | None = None,
    policy_libraries: Sequence[Path] = (),
    policy_timeout: float = 60.0,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Python differential oracle plan from compiler evidence.

    The normal RAVEL path never calls this function.  It remains available
    for explicit parity tests and offline compatibility diagnostics while the
    native workspace planner is the semantic authority.
    """

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
    policy_sufficient_local: bool | None = None
    if policy_runtime is not None:
        native_graph_incomplete = False
        native_registry_incomplete = False
        if cross_repository or change_class == "cross_repository_contract":
            native_graph_incomplete = family_graph is None or not bool(family_graph.get("complete"))
            coverage = family_graph.get("coverage", {}) if isinstance(family_graph, dict) else {}
            native_registry_incomplete = not isinstance(coverage, dict) or coverage.get("coverage_status") != "complete"
        level, reasons, policy_sufficient_local = _native_selection_policy(
            mncs=policy_runtime,
            impact=impact,
            change_class=change_class,
            cross_repository=cross_repository,
            selected_tests=len(impacted_tests),
            cwd=(policy_cwd or source_path.parent).resolve(),
            libraries=policy_libraries,
            timeout=policy_timeout,
            commons_root=commons_root,
            cross_repository_graph_incomplete=native_graph_incomplete,
            family_registry_coverage_incomplete=native_registry_incomplete,
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
    family_scope_requested = cross_repository or change_class == "cross_repository_contract"
    if family_graph is None or not family_scope_requested:
        no_registry_identity = sha256_bytes(b"no-family-registry-overlay")
        cross_repository_projection: dict[str, Any] = {
            "graph_identity": sha256_bytes(b"no-cross-repository-overlay"),
            "edges": [],
            "selected_repositories": [],
            "complete": not family_scope_requested,
            "limitations": [
                "cross-repository topology was not requested"
                if not family_scope_requested
                else "cross-repository topology was requested but no family overlay was supplied"
            ],
            "coverage": {
                "registry_identity": no_registry_identity,
                "registered_family_project_count": 0,
                "classified_project_count": 0,
                "semantic_graph_participant_count": 0,
                "explicit_nonparticipant_count": 0,
                "unclassified_project_count": 0,
                "unclassified_repositories": [],
                "coverage_status": "not_requested" if not family_scope_requested else "incomplete",
                "topology_status": "not_requested" if not family_scope_requested else "unavailable",
            },
        }
    else:
        edges = consumers_for(
            family_graph,
            producer_repository=producer_repository,
            contract_identity=contract_identity,
            commons_root=commons_root,
        )
        coverage = family_graph.get("coverage", {})
        if not isinstance(coverage, dict):
            coverage = {}
        cross_repository_projection = {
            "graph_identity": family_graph["graph_identity"],
            "edges": edges,
            "selected_repositories": sorted({edge["consumer_repository"] for edge in edges}),
            "complete": bool(family_graph.get("complete")),
            "limitations": list(family_graph.get("limitations", [])),
            # `complete` describes joined topology only. Keep registry
            # coverage beside it so a selected proof cannot be mistaken for
            # closed-world family closure.
            "coverage": {
                "registry_identity": coverage.get("registry_identity") or sha256_bytes(b"missing-family-registry-coverage"),
                "registered_family_project_count": coverage.get("registered_family_project_count", 0),
                "classified_project_count": coverage.get("classified_project_count", 0),
                "semantic_graph_participant_count": coverage.get("semantic_graph_participant_count", 0),
                "explicit_nonparticipant_count": coverage.get("explicit_nonparticipant_count", 0),
                "unclassified_project_count": coverage.get("unclassified_project_count", 0),
                "unclassified_repositories": list(coverage.get("unclassified_repositories", [])),
                "coverage_status": coverage.get("coverage_status", "incomplete"),
                "topology_status": coverage.get("topology_status"),
            },
        }
    if cross_repository and not cross_repository_projection["complete"]:
        reasons = sorted(set(reasons + ["cross_repository_graph_incomplete"]))
    coverage_projection = cross_repository_projection.get("coverage", {})
    if cross_repository and isinstance(coverage_projection, dict) and coverage_projection.get("coverage_status") != "complete":
        cross_repository_projection["limitations"] = sorted(
            set(cross_repository_projection["limitations"])
            | {"family registry coverage is incomplete; selected proof is not family-wide closure"}
        )
        reasons = sorted(set(reasons + ["family_registry_coverage_incomplete"]))

    # A source inventory is not a repository-wide canonical proof.  The
    # compiler currently reports a source/module inventory, so a canonical
    # request remains non-stopping until an executor supplies repository scope.
    inventory_scope = str(inventory.get("scope", "source"))
    # The native policy owns whether the selected local evidence is sufficient
    # for the selected level.  RAVEL adds only facts it owns: the actual joined
    # test set and the source-vs-repository proof boundary.  The offline
    # fallback necessarily retains the old bounded policy calculation.
    if policy_sufficient_local is None:
        policy_sufficient_local = bool(selected) and level != "family" and (
            level != "repository_canonical" or inventory_scope == "repository"
        )
    sufficient = bool(selected) and policy_sufficient_local and (
        level != "repository_canonical" or inventory_scope == "repository"
    )
    selected_consumer_routing = bool(cross_repository_projection["selected_repositories"])
    if selected_consumer_routing:
        required_evidence = ["selected_consumer_proofs_pass"]
        claimed_scope = "selected_repositories"
        proof_executor = "mncs-actions"
    elif level == "family":
        required_evidence = ["family_verification_pass"]
        claimed_scope = "family"
        proof_executor = "family-router"
    elif level == "repository_canonical":
        required_evidence = ["repository_canonical_suite_pass"]
        claimed_scope = "repository"
        proof_executor = "mncs-test"
    else:
        required_evidence = ["selected_test_cases_pass"]
        claimed_scope = level
        proof_executor = "mncs-test"
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
            "guarantee_domains": impact["guarantee_domains"],
            "change_kinds": impact["change_kinds"],
            "classification_schema_version": impact["classification_schema_version"],
            "complete": impact["complete"],
            "limitations": impact["limitations"],
            "cross_repository": cross_repository_projection,
        },
        "selection": {
            "level": level,
            "selected_test_identities": selected,
            "available_test_count": len(tests),
            "escalation_reasons": reasons,
            "routing_scope": (
                "selected_repositories"
                if cross_repository_projection["selected_repositories"]
                else ("family" if level == "family" else "local")
            ),
            "selected_repositories": cross_repository_projection["selected_repositories"],
            # Backward-compatible name: this is the semantic graph count,
            # never the registered family count.
            "available_repository_count": len(family_graph.get("repositories", [])) if family_graph else 0,
            "semantic_graph_repository_count": len(family_graph.get("repositories", [])) if family_graph else 0,
            "registered_family_project_count": (
                family_graph.get("coverage", {}).get("registered_family_project_count", 0)
                if family_graph
                else 0
            ),
            "coverage_classified_project_count": (
                family_graph.get("coverage", {}).get("classified_project_count", 0)
                if family_graph
                else 0
            ),
            "unclassified_project_count": (
                family_graph.get("coverage", {}).get("unclassified_project_count", 0)
                if family_graph
                else 0
            ),
        },
        "proof": {
            "sufficient_to_stop": sufficient,
            "required_evidence": required_evidence,
            "boundary": {
                "claimed_scope": claimed_scope,
                "established": sufficient,
                "executor": proof_executor,
                "stop_condition": required_evidence[0],
            },
        },
        "provenance": {
            # The native policy module is the semantic authority.  This
            # Python module remains the transport/compatibility adapter around
            # compiler and filesystem boundaries.
            "provider": SEMANTIC_PROVIDER,
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
    payload["plan_id"] = plan_identity(payload, commons_root=commons_root)
    try:
        return validate_plan(payload, source_path=source_path, commons_root=commons_root)
    except ValueError as error:
        raise ImpactError(str(error)) from error


def _native_planner_request(
    *,
    impact_document: Mapping[str, Any],
    inventory_document: Mapping[str, Any],
    source_path: Path,
    source_sha256: str,
    cross_repository: bool,
    change_class: str,
    family_graph: dict[str, Any] | None,
    commons_root: Path | None,
    producer_repository: str,
    contract_identity: str | None,
) -> dict[str, Any]:
    """Build only the typed transport envelope consumed by native RAVEL.

    Compiler and Commons own the facts in this document. This adapter only
    changes the compiler inventory's nested transport shape into the
    Commons-owned ``TestInventoryContract`` shape; selection, escalation,
    proof boundary, and plan identity are produced by ``planner_app``.
    """

    impact = validate_impact(dict(impact_document))
    inventory, tests = _inventory_tests(dict(inventory_document))
    family_scope_requested = (
        cross_repository
        or change_class == "cross_repository_contract"
        or contract_identity is not None
    )
    if family_graph is None or not family_scope_requested:
        no_registry_identity = sha256_bytes(b"no-family-registry-overlay")
        cross_projection: dict[str, Any] = {
            "graph_identity": sha256_bytes(b"no-cross-repository-overlay"),
            "edges": [],
            "selected_repositories": [],
            "complete": not family_scope_requested,
            "limitations": [
                "cross-repository topology was not requested"
                if not family_scope_requested
                else "cross-repository topology was requested but no family overlay was supplied"
            ],
            "coverage": {
                "registry_identity": no_registry_identity,
                "registered_family_project_count": 0,
                "classified_project_count": 0,
                "semantic_graph_participant_count": 0,
                "explicit_nonparticipant_count": 0,
                "unclassified_project_count": 0,
                "unclassified_repositories": [],
                "coverage_status": "not_requested" if not family_scope_requested else "incomplete",
                "topology_status": "not_requested" if not family_scope_requested else "unavailable",
            },
        }
    else:
        edges = consumers_for(
            family_graph,
            producer_repository=producer_repository,
            contract_identity=contract_identity,
            commons_root=commons_root,
        )
        coverage = family_graph.get("coverage", {})
        if not isinstance(coverage, Mapping):
            coverage = {}
        cross_projection = {
            "graph_identity": family_graph["graph_identity"],
            "edges": edges,
            "selected_repositories": sorted({edge["consumer_repository"] for edge in edges}),
            "complete": bool(family_graph.get("complete")),
            "limitations": list(family_graph.get("limitations", [])),
            "coverage": {
                "registry_identity": coverage.get("registry_identity") or sha256_bytes(b"missing-family-registry-coverage"),
                "registered_family_project_count": coverage.get("registered_family_project_count", 0),
                "classified_project_count": coverage.get("classified_project_count", 0),
                "semantic_graph_participant_count": coverage.get("semantic_graph_participant_count", 0),
                "explicit_nonparticipant_count": coverage.get("explicit_nonparticipant_count", 0),
                "unclassified_project_count": coverage.get("unclassified_project_count", 0),
                "unclassified_repositories": list(coverage.get("unclassified_repositories", [])),
                "coverage_status": coverage.get("coverage_status", "incomplete"),
                "topology_status": coverage.get("topology_status"),
            },
        }

    return {
        "schema_version": "mncs.ravel-planner-request/1",
        "source": {
            "path": str(source_path.resolve()),
            "sha256": source_sha256,
            "subject_identity": str(inventory.get("subject_identity", "")),
            "subject_fingerprint": str(inventory.get("subject_fingerprint", "0" * 64)),
        },
        "impact": {
            "graph_identity": impact["graph_identity"],
            "roots": impact["roots"],
            "affected_count": impact["affected_count"],
            "direct_dependents": impact["direct_dependents"],
            "test_identities": impact["test_identities"],
            "risk_flags": impact["risk_flags"],
            "guarantee_domains": impact["guarantee_domains"],
            "change_kinds": impact["change_kinds"],
            "classification_schema_version": impact["classification_schema_version"],
            "complete": impact["complete"],
            "limitations": impact["limitations"],
            "cross_repository": cross_projection,
        },
        "inventory": {
            "subject_identity": inventory.get("subject_identity", ""),
            "subject_fingerprint": inventory.get("subject_fingerprint", ""),
            "test_case_identities": [test["test_case_identity"] for test in tests],
        },
        "cross_repository": cross_repository,
        "change_class": change_class,
    }


def _run_native_planner(
    *,
    mncs: str,
    source_path: Path,
    impact_document: Mapping[str, Any],
    inventory_document: Mapping[str, Any],
    source_sha256: str,
    cross_repository: bool,
    change_class: str,
    family_graph: dict[str, Any] | None,
    commons_root: Path | None,
    producer_repository: str,
    contract_identity: str | None,
    cwd: Path,
    libraries: Sequence[Path],
    timeout: float,
) -> dict[str, Any]:
    """Run the canonical native planner application through one host boundary."""

    request = _native_planner_request(
        impact_document=impact_document,
        inventory_document=inventory_document,
        source_path=source_path,
        source_sha256=source_sha256,
        cross_repository=cross_repository,
        change_class=change_class,
        family_graph=family_graph,
        commons_root=commons_root,
        producer_repository=producer_repository,
        contract_identity=contract_identity,
    )
    descriptor = Path(__file__).resolve().parents[2] / "native-applications" / "ravel-planner.json"
    if not descriptor.is_file():
        raise ImpactError(f"native RAVEL planner descriptor is unavailable: {descriptor}")
    try:
        with tempfile.TemporaryDirectory(prefix=".ravel-native-", dir=cwd) as directory:
            work = Path(directory)
            request_path = work / "planner-request.json"
            decision_path = work / "planner-decision.json"
            plan_path = work / "verification-plan.json"
            request_path.write_text(
                json.dumps(request, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )
            command = [str(mncs), "run-app", str(descriptor)]
            command.extend(("--library", str(Path(__file__).resolve().parents[2] / "mncs" / "workspace" / "ravel")))
            for library in libraries:
                command.extend(("--library", str(library)))
            command.extend(
                (
                    "--grant-structured",
                    "ravel_artifact",
                    "--grant-structured",
                    "ravel_digest",
                    "--",
                    os.path.relpath(request_path, cwd),
                    os.path.relpath(decision_path, cwd),
                    os.path.relpath(plan_path, cwd),
                )
            )
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            if completed.returncode != 0:
                raise ImpactError(
                    "native RAVEL planner failed: "
                    + (completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
                )
            try:
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ImpactError(f"native RAVEL planner produced no canonical plan: {error}") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ImpactError(f"native RAVEL planner unavailable: {error}") from error
    if not isinstance(plan, dict):
        raise ImpactError("native RAVEL planner returned a non-object plan")
    try:
        return validate_plan(plan, source_path=source_path, commons_root=commons_root)
    except ValueError as error:
        raise ImpactError(f"native RAVEL plan failed canonical validation: {error}") from error


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
    # A native application invocation may include a cold compiler pass. Keep
    # this boundary budget above the observed cold-start envelope while still
    # allowing callers to impose a tighter explicit limit.
    timeout: float = 180.0,
    change_class: str = "implementation",
    cross_repository: bool = False,
    family_graph_path: Path | None = None,
    commons_root: Path | None = None,
    producer_repository: str = "ravel",
    contract_identity: str | None = None,
    allow_python_oracle: bool = False,
    obligation_inventory_path: Path | None = None,
    current_evidence_path: Path | None = None,
    obligation_output_path: Path | None = None,
) -> dict[str, Any]:
    if not roots:
        raise ImpactError("at least one changed semantic identity is required")
    if max_depth < 1 or max_nodes < 1:
        raise ImpactError("impact bounds must be positive")
    source_path = source_path.resolve()
    graph_path = family_graph_path
    if graph_path is None and (cross_repository or change_class == "cross_repository_contract"):
        graph_path = default_family_graph_path(commons_root=commons_root)
    family_graph = load_family_graph(graph_path, commons_root=commons_root) if graph_path else None
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
    if impact_error is None and inventory_error is None:
        try:
            source_sha256 = sha256_bytes(source_path.read_bytes())
        except OSError as error:
            raise ImpactError(f"source is unavailable for native verification planning: {source_path}") from error
        plan = _run_native_planner(
            mncs=mncs,
            source_path=source_path,
            impact_document=impact_document,
            inventory_document=inventory_document,
            source_sha256=source_sha256,
            cross_repository=cross_repository,
            change_class=change_class,
            family_graph=family_graph,
            commons_root=commons_root,
            producer_repository=producer_repository,
            contract_identity=contract_identity,
            cwd=base,
            libraries=libraries,
            timeout=timeout,
        )
        _write_obligation_plan_if_requested(
            plan,
            impact_document=impact_document,
            compiler_inventory_document=inventory_document,
            source_path=source_path,
            obligation_inventory_path=obligation_inventory_path,
            current_evidence_path=current_evidence_path,
            obligation_output_path=obligation_output_path,
            cwd=base,
            commons_root=commons_root,
            mncs=mncs,
            libraries=libraries,
            timeout=timeout,
            use_native=True,
        )
        return plan
    if not allow_python_oracle:
        detail = "; ".join(
            item
            for item in (
                str(impact_error) if impact_error is not None else "",
                str(inventory_error) if inventory_error is not None else "",
            )
            if item
        )
        raise ImpactError(
            "native RAVEL planning could not acquire compiler facts; "
            "Python semantic plan construction is disabled on the normal path"
            + (f": {detail}" if detail else "")
            + "; pass allow_python_oracle=True only for differential tests"
        )
    # This is an explicit compatibility/differential-oracle path.  It
    # preserves the conservative escalation and records the provider failure;
    # it is never selected implicitly by a successful normal request.
    plan = build_verification_plan(
        impact_document,
        inventory_document,
        source_path=source_path,
        change_class=change_class,
        cross_repository=cross_repository,
        family_graph=family_graph,
        commons_root=commons_root,
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
    _write_obligation_plan_if_requested(
        plan,
        impact_document=impact_document,
        compiler_inventory_document=inventory_document,
        source_path=source_path,
        obligation_inventory_path=obligation_inventory_path,
        current_evidence_path=current_evidence_path,
        obligation_output_path=obligation_output_path,
        cwd=base,
        commons_root=commons_root,
        mncs=mncs,
        libraries=libraries,
        timeout=timeout,
        use_native=False,
    )
    return plan


def _write_obligation_plan_if_requested(
    verification_plan: Mapping[str, Any],
    *,
    impact_document: Mapping[str, Any],
    compiler_inventory_document: Mapping[str, Any],
    source_path: Path,
    obligation_inventory_path: Path | None,
    current_evidence_path: Path | None,
    obligation_output_path: Path | None,
    cwd: Path,
    commons_root: Path | None,
    mncs: str | Path,
    libraries: Sequence[Path],
    timeout: float,
    use_native: bool,
) -> dict[str, Any] | None:
    if obligation_inventory_path is None and obligation_output_path is None:
        return None
    inventory_path = obligation_inventory_path or (cwd / ".mncs" / "verification-obligations.json")
    try:
        obligation_inventory_document = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ImpactError(f"verification obligation inventory is unavailable: {inventory_path}: {error}") from error
    enriched_plan = dict(verification_plan)
    enriched_plan["impact"] = {
        **dict(verification_plan.get("impact", {})),
        "guarantee_domains": list(impact_document.get("guarantee_domains", [])),
        "change_kinds": list(impact_document.get("change_kinds", [])),
    }
    current_evidence = load_current_evidence(current_evidence_path)
    if use_native:
        obligation_plan = build_native_obligation_plan(
            enriched_plan,
            obligation_inventory_document,
            source_path=source_path,
            mncs=mncs,
            cwd=cwd,
            libraries=libraries,
            timeout=timeout,
            compiler_inventory=compiler_inventory_document,
            current_evidence=current_evidence,
            commons_root=commons_root,
        )
    else:
        obligation_plan = build_obligation_plan(
            enriched_plan,
            obligation_inventory_document,
            source_path=source_path,
            compiler_inventory=compiler_inventory_document,
            current_evidence=current_evidence,
            commons_root=commons_root,
        )
    if obligation_output_path is not None:
        output_path = obligation_output_path if obligation_output_path.is_absolute() else cwd / obligation_output_path
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(obligation_plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return obligation_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAVEL bounded MNCS semantic-impact planner")
    parser.add_argument("source", type=Path)
    parser.add_argument("--mncs", required=True)
    parser.add_argument("--root", dest="roots", action="append", required=True)
    parser.add_argument("--library", dest="libraries", action="append", default=[])
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--max-nodes", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--change-class", choices=sorted(CHANGE_CLASSES), default="implementation")
    parser.add_argument("--cross-repository", action="store_true")
    parser.add_argument("--family-graph", type=Path)
    parser.add_argument("--commons-root", type=Path)
    parser.add_argument("--repository", default="ravel")
    parser.add_argument("--contract-identity")
    parser.add_argument(
        "--obligation-inventory",
        type=Path,
        help="repository-owned mncs-family.verification-obligation-inventory/v1",
    )
    parser.add_argument(
        "--current-evidence",
        type=Path,
        help="identity-bound evidence records available for reuse",
    )
    parser.add_argument(
        "--obligation-output",
        type=Path,
        help="write the companion mncs.verification-obligation-plan/1 document",
    )
    parser.add_argument(
        "--python-oracle",
        action="store_true",
        help="explicitly use the Python differential oracle if compiler facts are unavailable",
    )
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
            commons_root=args.commons_root,
            producer_repository=args.repository,
            contract_identity=args.contract_identity,
            allow_python_oracle=args.python_oracle,
            obligation_inventory_path=args.obligation_inventory,
            current_evidence_path=args.current_evidence,
            obligation_output_path=args.obligation_output,
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
