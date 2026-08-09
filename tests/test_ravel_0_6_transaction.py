from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ravel.c_observations import CTransactionObservation
from ravel.development_evaluator import evaluate_trial
from ravel.matched_compute import MatchedComputeObservation
from ravel.policy import load_frozen_policy
from tools.ravel_0_6_seed_candidate import FROZEN_SOURCE, build_candidate_source


ROOT = Path(__file__).resolve().parents[1]


def build_and_trial(source_text: str, directory: Path) -> dict[str, object]:
    source = directory / "candidate.c"
    binary = directory / "candidate"
    source.write_text(source_text, encoding="utf-8")
    built = subprocess.run(
        [
            "cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-I", str(ROOT / "ravel_versions/0.6/ravel_0_6"), str(source),
            str(ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_provider_branching.c"),
            "-lm", "-o", str(binary),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        raise AssertionError(built.stderr)
    run = subprocess.run(
        [str(binary), "--trial", "transaction-test", "--regime", "separated_state", "--seed", "0x1234"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


class CandidateTransactionTests(unittest.TestCase):
    def test_trial_uses_all_constraint_transaction_and_emits_raw_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(
                build_candidate_source(FROZEN_SOURCE.read_bytes()), Path(directory)
            )
        transaction = payload["candidate"]["adaptation_transaction"]
        self.assertTrue(transaction["committed"])
        self.assertFalse(transaction["rollback_byte_identical"])
        self.assertEqual(transaction["threshold_identity"], load_frozen_policy().threshold_identity)
        self.assertEqual(transaction["failed_constraint_mask"], 0)
        self.assertEqual(transaction["rejection_reason"], "none")
        self.assertEqual(transaction["raw"]["transition_support_losses"], 0)
        self.assertLessEqual(transaction["raw"]["births"], 16)
        self.assertLessEqual(transaction["raw"]["retirements"], 4)
        self.assertLessEqual(transaction["raw"]["replay_records"], 256)
        parsed = CTransactionObservation.from_json(transaction)
        self.assertFalse(parsed.matched_compute_reference_available)
        self.assertFalse(parsed.evaluate().passed)
        self.assertEqual(
            parsed.evaluate().rejection_reasons,
            ("matched_compute_reference_unavailable",),
        )
        matched = MatchedComputeObservation.from_json(payload["matched_compute"])
        self.assertTrue(matched.evaluate().passed)
        self.assertTrue(parsed.evaluate(matched).passed)
        development = evaluate_trial(
            payload,
            expected_provider_id="ravel-toy-branching-c/1",
        )
        self.assertEqual((development.status, development.reason_codes), ("PASS", ()))
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is unavailable")
        schema = json.loads(
            (ROOT / "ravel_versions/0.6/ravel-0.6-transaction.schema.json").read_text()
        )
        jsonschema.validate(transaction, schema)
        matched_schema = json.loads(
            (ROOT / "ravel_versions/0.6/ravel-0.6-matched-compute.schema.json").read_text()
        )
        jsonschema.validate(payload["matched_compute"], matched_schema)

    def test_mutated_hard_gate_rejects_and_rolls_back(self) -> None:
        source = build_candidate_source(FROZEN_SOURCE.read_bytes())
        mutated = source.replace(
            "#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_C(891290)",
            "#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_MAX",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(mutated, Path(directory))
        transaction = payload["candidate"]["adaptation_transaction"]
        self.assertFalse(transaction["committed"])
        self.assertEqual(transaction["rejection_reason"], "base_accuracy_floor")
        self.assertTrue(transaction["rollback_byte_identical"])
        self.assertNotEqual(transaction["failed_constraint_mask"], 0)

    def test_development_evaluator_rejects_identity_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(
                build_candidate_source(FROZEN_SOURCE.read_bytes()), Path(directory)
            )
        payload["candidate_id"] = "ravel-0.6-candidate-002"
        evaluation = evaluate_trial(payload, expected_provider_id="ravel-toy-branching-c/1")
        self.assertEqual(evaluation.status, "UNKNOWN")
        self.assertIn("candidate_identity_mismatch", evaluation.reason_codes)
        self.assertEqual(evaluation.evidence_completeness_status, "UNKNOWN")

    def test_evaluator_distinguishes_mechanism_failure_from_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(
                build_candidate_source(FROZEN_SOURCE.read_bytes()), Path(directory)
            )
        payload["candidate"]["adaptation_transaction"]["raw"]["base_accuracy_after_q20"] = 0
        payload["candidate"]["adaptation_transaction"]["committed"] = False
        payload["candidate"]["adaptation_transaction"]["failed_constraint_mask"] = 4
        payload.pop("matched_compute")
        evaluation = evaluate_trial(payload, expected_provider_id="ravel-toy-branching-c/1")
        self.assertEqual(evaluation.mechanism_status, "FAIL")
        self.assertEqual(evaluation.matched_compute_status, "UNKNOWN")
        self.assertEqual(evaluation.status, "FAIL")

    def test_evaluator_marks_malformed_required_evidence_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(
                build_candidate_source(FROZEN_SOURCE.read_bytes()), Path(directory)
            )
        payload["candidate"]["adaptation_transaction"] = {"committed": True}
        evaluation = evaluate_trial(payload, expected_provider_id="ravel-toy-branching-c/1")
        self.assertEqual(evaluation.status, "UNKNOWN")
        self.assertIn("malformed_required_observation", evaluation.reason_codes)

    def test_mechanism_failure_with_valid_compute_remains_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(
                build_candidate_source(FROZEN_SOURCE.read_bytes()), Path(directory)
            )
        payload["candidate"]["adaptation_transaction"]["raw"]["base_accuracy_after_q20"] = 0
        payload["candidate"]["adaptation_transaction"]["committed"] = False
        payload["candidate"]["adaptation_transaction"]["failed_constraint_mask"] = 4
        evaluation = evaluate_trial(payload, expected_provider_id="ravel-toy-branching-c/1")
        self.assertEqual(evaluation.mechanism_status, "FAIL")
        self.assertEqual(evaluation.matched_compute_status, "PASS")
        self.assertEqual(evaluation.status, "FAIL")

    def test_execution_integrity_failure_is_unknown_not_mechanism_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = build_and_trial(
                build_candidate_source(FROZEN_SOURCE.read_bytes()), Path(directory)
            )
        payload["execution_integrity_status"] = "FAIL"
        evaluation = evaluate_trial(payload, expected_provider_id="ravel-toy-branching-c/1")
        self.assertEqual(evaluation.mechanism_status, "PASS")
        self.assertEqual(evaluation.execution_integrity_status, "UNKNOWN")
        self.assertEqual(evaluation.status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
