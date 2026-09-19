from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from ravel.family_contract import plan_identity, validate_plan
from ravel.impact import build_verification_plan


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_ROOT = Path(
    os.environ.get(
        "MNCS_LANGUAGE_ROOT",
        "/home/epi13/Documents/Projects/mncs-language",
    )
)
COMMONS_ROOT = Path(
    os.environ.get(
        "MNCS_COMMONS_ROOT",
        "/home/epi13/Documents/Projects/MNCS-Commons",
    )
)


def runtime() -> Path:
    configured = os.environ.get("MNCS_BINARY")
    if configured:
        return Path(configured)
    return LANGUAGE_ROOT / "target" / "debug" / "mncs"


def run_native(request: dict[str, object]) -> dict[str, object]:
    binary = runtime()
    if not binary.is_file():
        raise unittest.SkipTest(f"MNCS runtime is not built: {binary}")
    with tempfile.TemporaryDirectory(prefix="ravel-phase6-", dir=ROOT) as directory:
        work = Path(directory)
        request_path = work / "request.json"
        decision_path = work / "decision.json"
        plan_path = work / "verification-plan.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        command = [
            str(binary),
            "run-app",
            str(ROOT / "native-applications" / "ravel-planner.json"),
            "--library",
            str(LANGUAGE_ROOT / "library"),
            "--library",
            str(COMMONS_ROOT / "src" / "mncs_commons" / "mesh"),
            "--library",
            str(ROOT / "mncs" / "workspace" / "ravel"),
            "--grant-structured",
            "ravel_artifact",
            "--grant-structured",
            "ravel_digest",
            "--",
            request_path.relative_to(ROOT).as_posix(),
            decision_path.relative_to(ROOT).as_posix(),
            plan_path.relative_to(ROOT).as_posix(),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        return (
            json.loads(decision_path.read_text(encoding="utf-8")),
            json.loads(plan_path.read_text(encoding="utf-8")),
        )


def request_with_ids(ids: list[str]) -> dict[str, object]:
    base = json.loads(
        (ROOT / "examples" / "native-planner" / "request.json").read_text(
            encoding="utf-8"
        )
    )
    base["impact"]["test_identities"] = ids
    base["inventory"]["test_case_identities"] = ids
    return base


class Phase6NativePlannerTests(unittest.TestCase):
    def test_native_plan_is_external_contract_and_identity_canonical(self) -> None:
        ids = ["mncs:test-case:phase6:identity"]
        _, plan = run_native(request_with_ids(ids))
        self.assertIsInstance(plan["selection"]["level"], str)
        self.assertEqual(plan["proof"]["boundary"]["claimed_scope"], "direct_dependents")
        self.assertEqual(plan["plan_id"], plan_identity(plan, commons_root=COMMONS_ROOT))
        self.assertEqual(plan["provenance"]["provider"], "ravel.verification_policy")
        validate_plan(plan, commons_root=COMMONS_ROOT)

    def test_native_complete_plan_matches_python_parity_oracle(self) -> None:
        ids = ["mncs:test-case:phase6:parity"]
        request = request_with_ids(ids)
        with tempfile.TemporaryDirectory(prefix="ravel-phase6-parity-", dir=ROOT) as directory:
            source = Path(directory) / "source.mncs"
            source.write_text("phase6 parity source", encoding="utf-8")
            request["source"]["path"] = str(source.resolve())
            request["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            _, native_plan = run_native(request)
            impact = dict(request["impact"])
            impact["schema_version"] = "mncs.semantic-impact/1"
            impact["nodes"] = [
                {"identity": "mncs:root:implementation", "kind": "function", "distance": 0},
                {"identity": "mncs-test:consumer", "kind": "function", "distance": 1},
            ]
            inventory = {
                "schema_version": "mncs.test-inventory/1",
                "valid": True,
                "inventory": {
                    "subject_identity": request["inventory"]["subject_identity"],
                    "subject_fingerprint": request["inventory"]["subject_fingerprint"],
                    "scope": "source",
                    "tests": [
                        {"test_case_identity": identity, "function_identity": identity}
                        for identity in ids
                    ],
                },
            }
            python_plan = build_verification_plan(
                impact,
                inventory,
                source_path=source,
                source_sha256=request["source"]["sha256"],
                change_class="implementation",
                commons_root=COMMONS_ROOT,
            )
        self.assertEqual(native_plan, python_plan)

    def test_native_selection_materializes_more_than_eight_ids(self) -> None:
        ids = [f"mncs:test-case:phase6:{index:02d}" for index in range(9)]
        decision, plan = run_native(request_with_ids(ids))
        self.assertTrue(decision["inventory_join_complete"])
        self.assertEqual(decision["joinable_test_count"], 9)
        self.assertEqual(decision["selected_test_identities"], ids)
        self.assertEqual(plan["selection"]["selected_test_identities"], ids)
        self.assertEqual(plan["selection"]["available_test_count"], 9)
        self.assertEqual(plan["provenance"]["dependencies"]["selected_test_identities"], ids)

    def test_native_selection_rejects_duplicate_ids_fail_closed(self) -> None:
        ids = ["mncs:test-case:phase6:duplicate"] * 2
        decision, plan = run_native(request_with_ids(ids))
        self.assertFalse(decision["inventory_join_complete"])
        self.assertEqual(decision["selected_test_identities"], [])
        self.assertEqual(plan["selection"]["selected_test_identities"], [])

    def test_native_selection_rejects_missing_inventory_join_fail_closed(self) -> None:
        impact_ids = ["mncs:test-case:phase6:present", "mncs:test-case:phase6:missing"]
        request = request_with_ids(impact_ids)
        request["inventory"]["test_case_identities"] = [impact_ids[0]]
        decision, plan = run_native(request)
        self.assertFalse(decision["inventory_join_complete"])
        self.assertEqual(decision["selected_test_identities"], [])
        self.assertEqual(plan["selection"]["selected_test_identities"], [])

    def test_native_zero_join_escalates_to_the_complete_inventory(self) -> None:
        request = request_with_ids(["mncs:test-case:phase6:not-in-inventory"])
        inventory_ids = [
            "mncs:test-case:phase6:available-01",
            "mncs:test-case:phase6:available-02",
        ]
        request["inventory"]["test_case_identities"] = inventory_ids
        decision, plan = run_native(request)
        self.assertFalse(decision["inventory_join_complete"])
        self.assertEqual(decision["selected_test_identities"], inventory_ids)
        self.assertEqual(plan["selection"]["level"], "repository_canonical")
        self.assertEqual(plan["selection"]["selected_test_identities"], inventory_ids)
        self.assertIn("test_selection_unresolved", plan["selection"]["escalation_reasons"])


if __name__ == "__main__":
    unittest.main()
