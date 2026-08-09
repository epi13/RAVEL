from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ravel.c_observations import CTransactionObservation
from ravel.matched_compute import MatchedComputeObservation
from ravel.policy import load_frozen_policy
from tools.ravel_0_6_seed_candidate import FROZEN_SOURCE, build_candidate_source


ROOT = Path(__file__).resolve().parents[1]


def run_mutated(replacement: tuple[str, str] | None) -> dict[str, object]:
    source = build_candidate_source(FROZEN_SOURCE.read_bytes())
    if replacement is not None:
        old, new = replacement
        if source.count(old) != 1:
            raise AssertionError(f"mutation target is not unique: {old}")
        source = source.replace(old, new, 1)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_path = root / "candidate.c"
        binary = root / "candidate"
        source_path.write_text(source, encoding="utf-8")
        built = subprocess.run(
            ["cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror", "-pedantic", str(source_path), "-lm", "-o", str(binary)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if built.returncode != 0:
            raise AssertionError(built.stderr)
        result = subprocess.run(
            [str(binary), "--trial", "negative-matrix", "--regime", "separated_state", "--seed", "0x1234"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)


class NegativeMatrixTests(unittest.TestCase):
    def test_python_raw_observation_matrix_has_each_reason(self) -> None:
        payload = run_mutated(None)
        transaction = payload["candidate"]["adaptation_transaction"]
        matched = MatchedComputeObservation.from_json(payload["matched_compute"])
        cases = (
            ("adaptation_improvement_below_epsilon", {"objective_after_q20": transaction["raw"]["objective_before_q20"]}),
            ("base_accuracy_floor", {"base_accuracy_after_q20": 0}),
            ("retention_accuracy_floor", {"retention_accuracy_after_q20": 0}),
            ("retention_loss_floor", {"retention_accuracy_delta_q20": -200000}),
            ("expert_capacity_budget", {"expert_count": 81}),
            ("birth_budget", {"births": 17}),
            ("replay_budget", {"replay_records": 255}),
            ("update_pass_budget", {"update_passes": 3}),
            ("transition_support_preservation", {"transition_support_losses": 1}),
        )
        for reason, changes in cases:
            with self.subTest(reason=reason):
                mutated = json.loads(json.dumps(transaction))
                mutated["raw"].update(changes)
                parsed = CTransactionObservation.from_json(mutated)
                report = parsed.evaluate(matched)
                self.assertIn(reason, report.rejection_reasons)
        ratio_mutation = dict(payload["matched_compute"])
        ratio_mutation.update(
            {
                "candidate_training_evaluations": 1200000,
                "matched_training_evaluations": 1000000,
                "ratio_q20": 1200000 * 1048576 // 1000000,
            }
        )
        over_budget = MatchedComputeObservation.from_json(ratio_mutation)
        self.assertEqual(over_budget.evaluate().rejection_reasons, ("matched_compute_ratio",))

    def test_policy_gate_mutations_have_stable_c_and_python_reasons(self) -> None:
        cases = (
            (
                "objective",
                "#define RAVEL06_OBJECTIVE_EPSILON_Q20 UINT64_C(105)",
                "#define RAVEL06_OBJECTIVE_EPSILON_Q20 UINT64_C(1000000)",
                "adaptation_improvement_below_epsilon",
            ),
            (
                "base",
                "#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_C(891290)",
                "#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_MAX",
                "base_accuracy_floor",
            ),
            (
                "retention",
                "#define RAVEL06_RETENTION_ACCURACY_FLOOR_Q20 UINT64_C(943718)",
                "#define RAVEL06_RETENTION_ACCURACY_FLOOR_Q20 UINT64_MAX",
                "retention_accuracy_floor",
            ),
            (
                "retention loss",
                "#define RAVEL06_RETENTION_LOSS_FLOOR_Q20 INT64_C(-104858)",
                "#define RAVEL06_RETENTION_LOSS_FLOOR_Q20 INT64_C(200000)",
                "retention_loss_floor",
            ),
            (
                "expert",
                "#define RAVEL06_MAX_EXPERTS 80u",
                "#define RAVEL06_MAX_EXPERTS 0u",
                "expert_capacity_budget",
            ),
            (
                "birth",
                "#define RAVEL06_MAX_BIRTHS 16u",
                "#define RAVEL06_MAX_BIRTHS 0u",
                "birth_budget",
            ),
            (
                "replay",
                "#define RAVEL06_REPLAY_RECORDS 256u",
                "#define RAVEL06_REPLAY_RECORDS 255u",
                "replay_budget",
            ),
            (
                "update",
                "#define RAVEL06_MAX_UPDATE_PASSES 2u",
                "#define RAVEL06_MAX_UPDATE_PASSES 1u",
                "update_pass_budget",
            ),
        )
        for name, old, new, reason in cases:
            with self.subTest(name=name):
                payload = run_mutated((old, new))
                transaction = payload["candidate"]["adaptation_transaction"]
                self.assertFalse(transaction["committed"])
                self.assertEqual(transaction["rejection_reason"], reason)
                parsed = CTransactionObservation.from_json(transaction)
                matched = MatchedComputeObservation.from_json(payload["matched_compute"])
                # The source mutation is deliberately outside the frozen policy
                # loader.  C must reject it, while Python must remain bound to
                # the unmutated policy; the build manifest is what detects this
                # implementation-policy drift.
                if transaction["committed"]:
                    self.fail(f"C accepted the mutated {name} constraint")
                if name == "objective":
                    self.assertTrue(parsed.evaluate(matched).passed)
                else:
                    self.assertNotIn(reason, parsed.evaluate(matched).rejection_reasons)
                self.assertTrue(transaction["rollback_byte_identical"])

    def test_malformed_threshold_and_matched_compute_are_not_pass(self) -> None:
        policy = load_frozen_policy()
        payload = run_mutated(
            (
                f'#define RAVEL06_THRESHOLD_IDENTITY "{policy.threshold_identity}"',
                '#define RAVEL06_THRESHOLD_IDENTITY "mutated-policy"',
            )
        )
        transaction = CTransactionObservation.from_json(
            payload["candidate"]["adaptation_transaction"]
        )
        self.assertEqual(transaction.evaluate().rejection_reasons, ("threshold_identity_mismatch",))
        matched = MatchedComputeObservation.from_json(payload["matched_compute"])
        mutated = dict(payload["matched_compute"])
        mutated["ratio_q20"] = mutated["maximum_ratio_q20"] + 1
        with self.assertRaises(ValueError):
            MatchedComputeObservation.from_json(mutated)
        self.assertEqual(matched.evaluate().rejection_reasons, ("threshold_identity_mismatch",))


if __name__ == "__main__":
    unittest.main()
