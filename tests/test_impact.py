from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ravel.family_contract import load_family_graph
from ravel.impact import (
    ImpactError,
    _native_selection_policy,
    build_verification_plan,
    request_verification_plan,
    select_level,
)


def _impact(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "mncs.semantic-impact/1",
        "graph_identity": "b" * 64,
        "roots": ["mncs:fn:changed"],
        "nodes": [{"identity": "mncs:fn:changed", "kind": "function", "distance": 0}],
        "edges": [],
        "direct_dependents": [],
        "test_identities": ["mncs:test-case:one"],
        "risk_flags": [],
        "complete": True,
        "limitations": ["cross-repository edges are not represented"],
    }
    value.update(overrides)
    return value


def _inventory() -> dict[str, object]:
    return {
        "schema_version": "mncs.test-inventory/1",
        "valid": True,
        "inventory": {
            "subject_identity": "mncs:program:one",
            "subject_fingerprint": "c" * 64,
            "tests": [
                {"test_case_identity": "mncs:test-case:one", "function_identity": "mncs:fn:changed"},
                {"test_case_identity": "mncs:test-case:two", "function_identity": "mncs:fn:other"},
            ],
        },
    }


def _graph_path() -> Path:
    configured = os.environ.get("MNCS_FAMILY_GRAPH_PATH")
    if configured:
        return Path(configured)
    configured_root = os.environ.get("MNCS_COMMONS_ROOT")
    if configured_root:
        return Path(configured_root) / "family" / "semantic-edges-v1.json"
    return Path(__file__).resolve().parents[2] / "MNCS-Commons" / "family" / "semantic-edges-v1.json"


class ImpactPlanTests(unittest.TestCase):
    def test_explicit_commons_root_binds_graph_and_plan_validation(self) -> None:
        configured_root = os.environ.get("MNCS_COMMONS_ROOT")
        candidates = [Path(configured_root)] if configured_root else []
        candidates.append(Path(__file__).resolve().parents[2] / "MNCS-Commons")
        commons_root = next(
            (
                candidate
                for candidate in candidates
                if (candidate / "src" / "mncs_commons" / "verification_plan.py").is_file()
                and (candidate / "family" / "semantic-edges-v1.json").is_file()
            ),
            None,
        )
        if commons_root is None:
            self.skipTest("a checked-out MNCS-Commons contract and family graph are required")

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("current", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"MNCS_COMMONS_ROOT": str(Path(directory) / "wrong-commons-root")},
                clear=False,
            ):
                graph = load_family_graph(
                    commons_root / "family" / "semantic-edges-v1.json",
                    commons_root=commons_root,
                )
                plan = build_verification_plan(
                    _impact(),
                    _inventory(),
                    source_path=source,
                    cross_repository=True,
                    family_graph=graph,
                    commons_root=commons_root,
                    producer_repository="ravel",
                    contract_identity="mncs.verification-plan/1",
                )

        self.assertEqual(plan["impact"]["cross_repository"]["graph_identity"], graph["graph_identity"])
        self.assertEqual(plan["selection"]["routing_scope"], "selected_repositories")

    def test_native_selection_policy_matches_bounded_local_cases(self) -> None:
        runtime = Path(
            os.environ.get(
                "MNCS_BINARY",
                "/home/epi13/Documents/Projects/mncs-language/target/debug/mncs",
            )
        )
        if not runtime.is_file():
            self.skipTest("mncs runtime is not built")
        level, reasons, sufficient = _native_selection_policy(
            mncs=str(runtime),
            impact=_impact(direct_dependents=["mncs:operation:caller"]),
            change_class="implementation",
            cross_repository=False,
            selected_tests=1,
            cwd=Path(__file__).resolve().parents[1],
            libraries=(),
            timeout=30.0,
        )
        assert level == "direct_dependents"
        assert reasons == ["direct_dependents_affected"]
        assert sufficient is True

    def test_cross_repository_contract_selects_declared_consumers_only(self) -> None:
        graph = load_family_graph(
            _graph_path()
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("current", encoding="utf-8")
            plan = build_verification_plan(
                _impact(),
                _inventory(),
                source_path=source,
                cross_repository=True,
                family_graph=graph,
                producer_repository="ravel",
                contract_identity="mncs.verification-plan/1",
            )
        assert plan["selection"]["level"] == "family"
        assert plan["selection"]["selected_repositories"] == [
            "mncs-actions",
            "mncs-forge",
            "mncs-test",
        ]
        assert plan["selection"]["available_repository_count"] == 6
        assert plan["proof"]["sufficient_to_stop"] is False
        assert plan["selection"]["routing_scope"] == "selected_repositories"
        assert plan["proof"]["boundary"]["claimed_scope"] == "selected_repositories"
        assert "selected_consumer_proofs_pass" in plan["proof"]["required_evidence"]

    def test_narrow_plan_joins_only_compiler_reported_test_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("source", encoding="utf-8")
            plan = build_verification_plan(
                _impact(),
                _inventory(),
                source_path=source,
            )
        self.assertEqual(plan["schema_version"], "mncs.verification-plan/1")
        self.assertEqual(plan["selection"]["level"], "changed_item")
        self.assertEqual(plan["selection"]["selected_test_identities"], ["mncs:test-case:one"])
        self.assertTrue(plan["proof"]["sufficient_to_stop"])
        self.assertEqual(len(plan["plan_id"]), 64)

    def test_local_plan_does_not_project_family_consumers(self) -> None:
        graph = load_family_graph(
            _graph_path()
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("source", encoding="utf-8")
            plan = build_verification_plan(
                _impact(),
                _inventory(),
                source_path=source,
                family_graph=graph,
                producer_repository="ravel",
                contract_identity="mncs.verification-plan/1",
            )
        self.assertEqual(plan["selection"]["routing_scope"], "local")
        self.assertEqual(plan["selection"]["selected_repositories"], [])
        self.assertEqual(plan["impact"]["cross_repository"]["edges"], [])

    def test_dependents_expand_without_escalating_to_canonical(self) -> None:
        level, reasons = select_level(
            _impact(direct_dependents=["mncs:operation:caller"]),
            change_class="implementation",
        )
        self.assertEqual((level, reasons), ("direct_dependents", ["direct_dependents_affected"]))

    def test_structural_risks_raise_scope_with_typed_reasons(self) -> None:
        level, reasons = select_level(
            _impact(risk_flags=["high_connectivity"]),
            change_class="implementation",
        )
        self.assertEqual((level, reasons), ("affected_subsystem", ["high_connectivity_definition_changed"]))
        level, reasons = select_level(
            _impact(risk_flags=["shared_type"]),
            change_class="implementation",
        )
        self.assertEqual((level, reasons), ("affected_subsystem", ["shared_type_changed"]))

    def test_unknown_or_public_contract_change_has_explicit_reason(self) -> None:
        level, reasons = select_level(
            _impact(complete=False, risk_flags=["truncated"]),
            change_class="implementation",
        )
        self.assertEqual(level, "repository_canonical")
        self.assertIn("impact_evidence_truncated", reasons)
        level, reasons = select_level(_impact(), change_class="public_contract")
        self.assertEqual(level, "repository_canonical")
        self.assertEqual(reasons, ["public_contract_changed"])

    def test_unavailable_impact_falls_back_to_explicit_canonical_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("source", encoding="utf-8")
            inventory = json.dumps(
                {
                    "schema_version": "mncs.test-inventory/1",
                    "valid": True,
                    "inventory": {
                        "tests": [
                            {
                                "test_case_identity": "mncs:test-case:one",
                                "function_identity": "mncs:fn:one",
                            }
                        ]
                    },
                }
            )
            from subprocess import CompletedProcess

            calls = [
                CompletedProcess(["mncs", "impact"], 2, "", "compiler unavailable"),
                CompletedProcess(["mncs", "test-inventory"], 0, inventory, ""),
            ]
            with patch("subprocess.run", side_effect=calls):
                plan = request_verification_plan(
                    source_path=source,
                    mncs="mncs",
                    roots=["mncs:fn:one"],
                    cwd=Path(directory),
                    allow_python_oracle=True,
                )
        self.assertEqual(plan["selection"]["level"], "repository_canonical")
        self.assertIn("impact_evidence_truncated", plan["selection"]["escalation_reasons"])
        self.assertIn("unknown_changed_identity", plan["selection"]["escalation_reasons"])
        self.assertEqual(plan["selection"]["selected_test_identities"], ["mncs:test-case:one"])
        self.assertFalse(plan["proof"]["sufficient_to_stop"])
        self.assertFalse(plan["proof"]["boundary"]["established"])
        self.assertIsNotNone(plan["provenance"]["impact_provider_error"])

    def test_normal_request_fails_closed_instead_of_using_python_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("source", encoding="utf-8")
            from subprocess import CompletedProcess

            with patch(
                "subprocess.run",
                return_value=CompletedProcess(["mncs", "impact"], 2, "", "compiler unavailable"),
            ):
                with self.assertRaisesRegex(ImpactError, "Python semantic plan construction is disabled"):
                    request_verification_plan(
                        source_path=source,
                        mncs="mncs",
                        roots=["mncs:fn:one"],
                        cwd=Path(directory),
                    )


if __name__ == "__main__":
    unittest.main()
