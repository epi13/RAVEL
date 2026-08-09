from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ravel.policy import PolicyError, load_frozen_policy, policy_c_header


ROOT = Path(__file__).resolve().parents[1]


class FrozenPolicyTests(unittest.TestCase):
    def test_policy_is_derived_from_frozen_records(self) -> None:
        policy = load_frozen_policy()
        self.assertEqual(policy.base_accuracy_floor_q20, 891290)
        self.assertEqual(policy.retention_accuracy_floor_q20, 943718)
        self.assertEqual(policy.retention_loss_floor_q20, -104858)
        self.assertEqual(policy.maximum_update_passes, 2)
        self.assertEqual(policy.replay_records, 256)
        self.assertEqual(policy.maximum_compute_ratio_q20, 1153434)
        self.assertIsNone(policy.maximum_compute_evaluations)
        self.assertIn(policy.threshold_identity, policy_c_header(policy))

    def test_mutating_either_policy_record_is_fail_closed(self) -> None:
        source = json.loads(
            (ROOT / "ravel_versions/0.6/ravel-0.6-preregistration.json").read_text()
        )
        source["mechanism"]["budget"]["maximum_experts"] = 79
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaises(PolicyError):
                load_frozen_policy(path)

    def test_policy_identity_is_stable(self) -> None:
        first = load_frozen_policy()
        second = load_frozen_policy()
        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
