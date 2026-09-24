from __future__ import annotations

from pathlib import Path

from ravel.obligations import (
    _cargo_test_target_declarations,
    _manifest_host_grants,
    _native_obligation_execution_limits,
    build_obligation_plan,
)


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


def test_cargo_package_test_declaration_expands_to_stable_target_obligations() -> None:
    metadata = {
        "workspace_root": "/workspace",
        "workspace_members": ["path+file:///workspace#fixture@0.1.0"],
        "packages": [{
            "id": "path+file:///workspace#fixture@0.1.0",
            "name": "fixture",
            "targets": [
                {"name": "fixture", "kind": ["lib"], "src_path": "/workspace/src/lib.rs", "test": True, "doctest": True},
                {"name": "parser", "kind": ["test"], "src_path": "/workspace/tests/parser.rs", "test": True, "doctest": False},
                {"name": "fixture-tool", "kind": ["bin"], "src_path": "/workspace/src/bin/fixture-tool.rs", "test": True, "doctest": False},
            ],
        }],
    }
    targets = _cargo_test_target_declarations(
        metadata, "fixture", "fixture-tests", ["cargo", "test", "--package", "fixture"]
    )
    assert [target["target_identity"] for target in targets] == [
        "fixture:bin:fixture-tool",
        "fixture:doc:fixture",
        "fixture:lib:fixture",
        "fixture:test:parser",
    ]
    assert [target["argv"][4:] for target in targets] == [
        ["--bin", "fixture-tool"],
        ["--doc"],
        ["--lib"],
        ["--test", "parser"],
    ]


def test_repository_grants_are_exact_and_unknown_selectors_fail_closed() -> None:
    test_identity = "mncs:0.2:test-case:process::cancel"
    grant = {"capability": "process_capability", "locator": "/usr/bin/sleep", "bytes": []}
    grants, complete = _manifest_host_grants(
        {"host_grant_sets": [{"test_case_identity": test_identity, "grants": [grant]}]},
        {test_identity},
    )
    assert complete is True
    assert grants == [{"test_case_identity": test_identity, "grants": [grant]}]
    stale, complete = _manifest_host_grants(
        {"host_grant_sets": [{"test_case_identity": "stale-test", "grants": [grant]}]},
        {test_identity},
    )
    assert complete is False
    assert stale == []


def test_native_obligation_planner_limits_scale_with_declared_work_and_stay_bounded() -> None:
    small = {"obligations": [{}], "compiler_tests": [], "evidence": []}
    language = {
        "obligations": [{}] * 104,
        "compiler_tests": [{}],
        "evidence": [{}] * 10,
    }
    maximum = {"obligations": [{}] * 256, "compiler_tests": [{}] * 256, "evidence": [{}] * 256}

    small_steps, small_timeout = _native_obligation_execution_limits(small, 180.0)
    language_steps, language_timeout = _native_obligation_execution_limits(language, 180.0)
    max_steps, max_timeout = _native_obligation_execution_limits(maximum, 180.0)

    assert small_steps == 1_179_648
    assert small_timeout == 180.0
    assert language_steps == 8_000_000
    assert language_timeout == 476.0
    assert max_steps == 8_000_000
    assert max_timeout == 600.0
