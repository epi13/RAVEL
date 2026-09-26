from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from ravel.obligations import (
    build_native_obligation_plan,
    build_obligation_plan,
    obligation_inventory_identity,
    validate_obligation_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_ROOT = Path(os.environ.get("MNCS_LANGUAGE_ROOT", "/home/epi13/Documents/Projects/mncs-language"))
COMMONS_ROOT = Path(os.environ.get("MNCS_COMMONS_ROOT", "/home/epi13/Documents/Projects/MNCS-Commons"))


def _inventory() -> dict:
    return {
        "schema_version": "mncs-family.verification-obligation-inventory/v1",
        "repository": "fixture",
        "revision": 1,
        "obligations": [
            {
                "identity": "fixture.semantic.regression",
                "title": "fixture",
                "guarantee_domain": "semantic",
                "evidence_role": "canonical_regression",
                "lifecycle": "permanent",
                "scope": "local",
                "subjects": ["fixture:function"],
                "invalidation_dependencies": ["fixture:function"],
                "executor": {
                    "provider": "mncs-test",
                    "kind": "native_first_class_test",
                    "entrypoint": "mncs test",
                    "declaration_identities": ["fixture:test-declaration"],
                },
                "evidence_identity": {
                    "subject_fields": ["subject_fingerprint"],
                    "definition_fields": ["obligation_identity"],
                    "execution_fields": ["test_case_identity"],
                },
            },
            {
                "identity": "fixture.reference",
                "title": "fixture reference",
                "guarantee_domain": "semantic",
                "evidence_role": "historical_reference",
                "lifecycle": "reference_only",
                "scope": "local",
                "subjects": ["fixture:function"],
                "invalidation_dependencies": ["fixture:function"],
                "executor": {
                    "provider": "fixture",
                    "kind": "differential_oracle",
                    "entrypoint": "reference",
                },
                "evidence_identity": {
                    "subject_fields": ["subject_fingerprint"],
                    "definition_fields": ["obligation_identity"],
                    "execution_fields": ["execution_identity"],
                },
            },
        ],
    }


def _plan(source: Path) -> dict:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "schema_version": "mncs.verification-plan/1",
        "plan_id": "fixture-plan",
        "source": {
            "path": str(source),
            "sha256": digest,
            "subject_identity": "fixture:subject",
            "subject_fingerprint": "fixture:fingerprint",
        },
        "impact": {
            "graph_identity": "fixture:graph",
            "roots": ["fixture:function"],
            "nodes": [{"identity": "fixture:function"}],
            "direct_dependents": [],
            "test_identities": [],
            "guarantee_domains": ["semantic"],
            "change_kinds": ["private_implementation"],
        },
        "selection": {"escalation_reasons": []},
        "proof": {"sufficient_to_stop": True, "boundary": {"claimed_scope": "changed_item"}},
    }


def test_native_obligation_kernel_matches_python_oracle_projection(tmp_path: Path) -> None:
    binary = Path(os.environ.get("MNCS_BINARY", str(LANGUAGE_ROOT / "target" / "debug" / "mncs")))
    if not binary.is_file():
        pytest.skip(f"MNCS runtime is not built: {binary}")
    source = tmp_path / "source.mncs"
    source.write_text("native obligation kernel fixture\n", encoding="utf-8")
    compiler_inventory = {
        "inventory": {
            "tests": [
                {
                    "declaration_identity": "fixture:test-declaration",
                    "test_case_identity": "fixture:test-case",
                    "function_identity": "fixture:function",
                }
            ]
        }
    }
    native = build_native_obligation_plan(
        _plan(source),
        _inventory(),
        source_path=source,
        mncs=binary,
        cwd=ROOT,
        libraries=[LANGUAGE_ROOT / "library", COMMONS_ROOT / "src" / "mncs_commons" / "mesh"],
        compiler_inventory=compiler_inventory,
        commons_root=COMMONS_ROOT,
    )
    oracle = build_obligation_plan(
        _plan(source),
        _inventory(),
        source_path=source,
        compiler_inventory=compiler_inventory,
        commons_root=COMMONS_ROOT,
    )
    assert [(item["identity"], item["status"], item["test_case_identities"]) for item in native["obligations"]] == [
        (item["identity"], item["status"], item["test_case_identities"]) for item in oracle["obligations"]
    ]
    assert native["excluded"] == oracle["excluded"]
    assert native["stop"]["required_obligation_identities"] == oracle["stop"]["required_obligation_identities"]
    assert native["stop"]["new_execution_required"] == oracle["stop"]["new_execution_required"]
    assert native["stop"]["sufficient_to_stop"] is False


def test_direct_plan_reuses_source_bound_evidence_for_repository_scoped_rows(tmp_path: Path) -> None:
    binary = Path(os.environ.get("MNCS_BINARY", str(LANGUAGE_ROOT / "target" / "debug" / "mncs")))
    if not binary.is_file():
        pytest.skip(f"MNCS runtime is not built: {binary}")
    source = tmp_path / "source.mncs"
    source.write_text("direct evidence reuse fixture\n", encoding="utf-8")
    inventory = _inventory()
    inventory["obligations"][0]["scope"] = "repository_canonical"
    normalized = validate_obligation_inventory(inventory, commons_root=COMMONS_ROOT)
    evidence = [{
        "obligation_identity": "fixture.semantic.regression",
        "evidence_identity": "fixture:source-bound-pass",
        "status": "PASS",
        "subject_identity": "fixture:subject",
        "subject_fingerprint": "fixture:fingerprint",
        "definition_identity": obligation_inventory_identity(normalized, commons_root=COMMONS_ROOT),
    }]
    compiler_inventory = {
        "inventory": {
            "tests": [{
                "declaration_identity": "fixture:test-declaration",
                "test_case_identity": "fixture:test-case",
                "function_identity": "fixture:function",
            }]
        }
    }
    verification_plan = _plan(source)
    verification_plan["proof"] = {
        "sufficient_to_stop": False,
        "boundary": {"claimed_scope": "direct_dependents"},
    }
    native = build_native_obligation_plan(
        verification_plan, inventory, source_path=source, mncs=binary, cwd=ROOT,
        libraries=[LANGUAGE_ROOT / "library", COMMONS_ROOT / "src" / "mncs_commons" / "mesh"],
        compiler_inventory=compiler_inventory, current_evidence=evidence,
        commons_root=COMMONS_ROOT,
    )
    oracle = build_obligation_plan(
        verification_plan, inventory, source_path=source,
        compiler_inventory=compiler_inventory, current_evidence=evidence,
        commons_root=COMMONS_ROOT,
    )
    native_selected = {item["identity"]: item for item in native["obligations"]}
    oracle_selected = {item["identity"]: item for item in oracle["obligations"]}
    assert native_selected["fixture.semantic.regression"]["status"] == "current"
    assert native_selected["fixture.semantic.regression"]["status"] == oracle_selected["fixture.semantic.regression"]["status"]
    assert native["stop"]["new_execution_required"] == oracle["stop"]["new_execution_required"] == []
    assert native["stop"]["sufficient_to_stop"] is False


def _repository_obligation(identity: str, suffix: str) -> dict:
    subject = f"fixture:subject:{suffix}"
    return {
        "identity": identity,
        "title": f"Fixture repository obligation {suffix}",
        "guarantee_domain": "integration",
        "evidence_role": "canonical_regression",
        "lifecycle": "permanent",
        "scope": "repository_canonical",
        "subjects": ["fixture:function"],
        "invalidation_dependencies": [f"fixture/dependency-{suffix}.txt"],
        "executor": {
            "provider": "mncs-test",
            "kind": "external_integration",
            "entrypoint": f"fixture:{suffix}",
            "argv": ["python3", "fixture.py", suffix],
            "working_directory": ".",
            "timeout_seconds": 60,
            "target_identity": suffix,
            "verifier_identity": "fixture-executor/1",
        },
        "evidence_identity": {
            "subject_fields": ["repository_fingerprint", "subject_fingerprint"],
            "definition_fields": ["definition_identity"],
            "execution_fields": ["executor_identity", "verifier_identity", "invalidation_identity"],
        },
        "definition_identity": f"{ord(suffix[0]):064x}",
        "subject_identity": subject,
        "subject_fingerprint": f"{ord(suffix[0]) + 1:064x}",
        "executor_identity": f"{ord(suffix[0]) + 2:064x}",
        "verifier_identity": f"{ord(suffix[0]) + 3:064x}",
        "invalidation_identity": f"{ord(suffix[0]) + 4:064x}",
    }


def _repository_context(obligations: list[dict], required: list[str], *, complete: bool = True) -> dict:
    return {
        "requested": True,
        "complete": complete,
        "impact_complete": complete,
        "unknown_root": not complete,
        "identity": "fixture-repository",
        "revision": "fixture-revision",
        "fingerprint": "f" * 64,
        "inventory_identity": "e" * 64,
        "required_obligation_identities": required,
        "obligations": obligations,
        "compiler_test_inventories": [
            {
                "path": "tests/fixture.mncs",
                "scope": "source_module",
                "identity": "d" * 64,
                "test_case_identities": ["mncs:0.2:test-case:fixture::case"],
            }
        ],
    }


def _repository_verification_plan(source: Path) -> dict:
    plan = _plan(source)
    plan["impact"]["guarantee_domains"] = ["integration"]
    plan["impact"]["change_kinds"] = ["effect_semantics"]
    plan["proof"]["boundary"] = {"claimed_scope": "repository_canonical"}
    return plan


def _current_repository_evidence(obligation: dict, *, status: str = "PASS", fingerprint: str = "f" * 64) -> dict:
    return {
        "obligation_identity": obligation["identity"],
        "evidence_identity": f"fixture-evidence:{obligation['identity']}",
        "status": status,
        "repository_identity": "fixture-repository",
        "repository_revision": "fixture-revision",
        "repository_fingerprint": fingerprint,
        "subject_identity": obligation["subject_identity"],
        "subject_fingerprint": obligation["subject_fingerprint"],
        "definition_identity": obligation["definition_identity"],
        "executor_identity": obligation["executor_identity"],
        "verifier_identity": obligation["verifier_identity"],
        "invalidation_identity": obligation["invalidation_identity"],
    }


def test_native_repository_boundary_fails_closed_and_accepts_only_complete_current_passes(
    tmp_path: Path,
) -> None:
    binary = Path(os.environ.get("MNCS_BINARY", str(LANGUAGE_ROOT / "target" / "debug" / "mncs")))
    if not binary.is_file():
        pytest.skip(f"MNCS runtime is not built: {binary}")
    source = tmp_path / "source.mncs"
    source.write_text("native repository obligation fixture\n", encoding="utf-8")

    passing = _repository_obligation("fixture.repository.pass", "pass")
    failing = _repository_obligation("fixture.repository.fail", "fail")
    unknown = _repository_obligation("fixture.repository.timeout", "unknown")
    stale = _repository_obligation("fixture.repository.stale", "stale")
    declared = [passing, failing, unknown, stale]
    required = [item["identity"] for item in declared] + ["fixture.repository.missing"]
    incomplete = build_native_obligation_plan(
        _repository_verification_plan(source),
        _inventory(),
        source_path=source,
        mncs=binary,
        cwd=ROOT,
        libraries=[LANGUAGE_ROOT / "library", COMMONS_ROOT / "src" / "mncs_commons" / "mesh"],
        compiler_inventory={
            "inventory": {
                "scope": "source_module",
                "tests": [{
                    "declaration_identity": "fixture:test-declaration",
                    "test_case_identity": "mncs:0.2:test-case:fixture::case",
                    "function_identity": "fixture:function",
                }],
            }
        },
        current_evidence=[
            _current_repository_evidence(passing),
            _current_repository_evidence(failing, status="FAIL"),
            _current_repository_evidence(unknown, status="UNKNOWN"),
            _current_repository_evidence(stale, fingerprint="0" * 64),
        ],
        commons_root=COMMONS_ROOT,
        repository_context=_repository_context(declared, required),
    )
    selected = {item["identity"]: item for item in incomplete["obligations"]}
    assert incomplete["stop"]["sufficient_to_stop"] is False
    assert incomplete["repository"]["missing_obligation_identities"] == ["fixture.repository.missing"]
    assert selected[passing["identity"]]["status"] == "current"
    for obligation, evidence_id, reason_fragment in (
        (failing, f"fixture-evidence:{failing['identity']}", "FAIL"),
        (unknown, f"fixture-evidence:{unknown['identity']}", "UNKNOWN"),
    ):
        item = selected[obligation["identity"]]
        assert item["status"] == "escalation_required"
        assert item["identity"] in incomplete["stop"]["new_execution_required"]
        assert item["evidence_identities"] == [evidence_id]
        assert reason_fragment in item["reason"]
        assert item["executor_identity"] == obligation["executor_identity"]
    assert selected[stale["identity"]]["status"] == "stale"
    assert stale["identity"] in incomplete["stop"]["new_execution_required"]

    pass_set = [
        _repository_obligation("fixture.repository.complete-a", "first"),
        _repository_obligation("fixture.repository.complete-b", "second"),
    ]
    complete_required = [item["identity"] for item in pass_set]
    complete = build_native_obligation_plan(
        _repository_verification_plan(source),
        _inventory(),
        source_path=source,
        mncs=binary,
        cwd=ROOT,
        libraries=[LANGUAGE_ROOT / "library", COMMONS_ROOT / "src" / "mncs_commons" / "mesh"],
        compiler_inventory=None,
        current_evidence=[_current_repository_evidence(item) for item in pass_set],
        commons_root=COMMONS_ROOT,
        repository_context=_repository_context(pass_set, complete_required),
    )
    assert complete["repository"]["scope"] == "repository_canonical"
    assert complete["repository"]["complete"] is True
    assert complete["repository"]["selected_obligation_identities"] == complete_required
    assert complete["repository"]["missing_obligation_identities"] == []
    assert complete["stop"]["sufficient_to_stop"] is True

    source_only = build_native_obligation_plan(
        _repository_verification_plan(source),
        _inventory(),
        source_path=source,
        mncs=binary,
        cwd=ROOT,
        libraries=[LANGUAGE_ROOT / "library", COMMONS_ROOT / "src" / "mncs_commons" / "mesh"],
        compiler_inventory={"inventory": {"scope": "source_module", "tests": []}},
        current_evidence=[],
        commons_root=COMMONS_ROOT,
        repository_context=_repository_context([], ["fixture.repository.required"], complete=False),
    )
    assert source_only["repository"]["scope"] == "repository_canonical"
    assert source_only["repository"]["compiler_test_inventories"][0]["scope"] == "source_module"
    assert source_only["repository"]["complete"] is False
    assert source_only["repository"]["missing_obligation_identities"] == ["fixture.repository.required"]
    assert source_only["stop"]["sufficient_to_stop"] is False
