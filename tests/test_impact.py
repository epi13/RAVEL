from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
import json
from pathlib import Path

from ravel.impact import build_verification_plan, request_verification_plan, select_level


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


class ImpactPlanTests(unittest.TestCase):
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
                )
        self.assertEqual(plan["selection"]["level"], "repository_canonical")
        self.assertIn("impact_evidence_truncated", plan["selection"]["escalation_reasons"])
        self.assertIn("unknown_changed_identity", plan["selection"]["escalation_reasons"])
        self.assertEqual(plan["selection"]["selected_test_identities"], ["mncs:test-case:one"])
        self.assertTrue(plan["proof"]["sufficient_to_stop"])
        self.assertIsNotNone(plan["provenance"]["impact_provider_error"])


if __name__ == "__main__":
    unittest.main()
