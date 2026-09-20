from __future__ import annotations

from pathlib import Path

from ravel.obligations import build_obligation_plan


def _inventory() -> dict:
    return {
        "schema_version": "mncs-family.verification-obligation-inventory/v1",
        "repository": "fixture",
        "revision": 1,
        "obligations": [
            {
                "identity": "fixture.semantic.regression",
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
                    "execution_fields": ["test_case_identity", "verifier_identity"],
                },
            },
            {
                "identity": "fixture.migration.parity",
                "guarantee_domain": "runtime",
                "evidence_role": "differential_oracle",
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


def _plan() -> dict:
    return {
        "schema_version": "mncs.verification-plan/1",
        "plan_id": "plan",
        "source": {
            "path": "/tmp/source.mncs",
            "sha256": "a" * 64,
            "subject_identity": "fixture:subject",
            "subject_fingerprint": "b" * 64,
        },
        "impact": {
            "graph_identity": "c" * 64,
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


def test_reference_only_parity_is_excluded_and_missing_evidence_requires_execution() -> None:
    plan = build_obligation_plan(
        _plan(),
        _inventory(),
        source_path=Path("/tmp/source.mncs"),
        compiler_inventory={
            "inventory": {
                "tests": [
                    {
                        "declaration_identity": "fixture:test-declaration",
                        "test_case_identity": "fixture:test-case",
                    }
                ]
            }
        },
    )
    assert [item["status"] for item in plan["obligations"]] == ["new_execution_required"]
    assert plan["stop"]["sufficient_to_stop"] is False
    assert plan["stop"]["new_execution_required"] == ["fixture.semantic.regression"]
    assert plan["excluded"] == [
        {
            "identity": "fixture.migration.parity",
            "lifecycle": "reference_only",
            "reason": "lifecycle is not part of ordinary verification",
        }
    ]


def test_exact_pass_evidence_is_reusable() -> None:
    plan = build_obligation_plan(
        _plan(),
        _inventory(),
        source_path=Path("/tmp/source.mncs"),
        compiler_inventory={
            "inventory": {
                "tests": [
                    {
                        "declaration_identity": "fixture:test-declaration",
                        "test_case_identity": "fixture:test-case",
                    }
                ]
            }
        },
        current_evidence=[
            {
                "obligation_identity": "fixture.semantic.regression",
                "evidence_identity": "fixture:evidence",
                "status": "PASS",
                "subject_identity": "fixture:subject",
                "subject_fingerprint": "b" * 64,
            }
        ],
    )
    assert plan["obligations"][0]["status"] == "current"
    assert plan["stop"]["sufficient_to_stop"] is True
