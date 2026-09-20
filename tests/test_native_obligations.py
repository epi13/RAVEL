from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from ravel.obligations import build_native_obligation_plan, build_obligation_plan


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
