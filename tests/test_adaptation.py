from __future__ import annotations

import unittest

from ravel.adaptation import (
    RawObservation,
    RetentionConstraintPolicy,
    canonical_transaction_json,
    evaluate_constraints,
    run_transaction,
)


def observation(**changes: object) -> RawObservation:
    values: dict[str, object] = {
        "adaptation_objective": 10.0,
        "base_accuracy": 0.95,
        "representation_score": 0.90,
        "original_prediction_degradation": 0.25,
        "transition_support_losses": 0,
        "expert_count": 70,
        "births": 2,
        "retirements": 1,
        "replay_records": 256,
        "update_passes": 1,
        "compute_evaluations": 100,
        "matched_compute_evaluations": 100,
    }
    values.update(changes)
    return RawObservation(**values)


POLICY = RetentionConstraintPolicy(
    adaptation_improvement_epsilon=0.05,
    base_accuracy_floor=0.85,
    representation_floor=0.80,
    original_prediction_degradation_bound=1.0,
    maximum_transition_support_losses=0,
    maximum_experts=80,
    maximum_births=16,
    maximum_retirements=4,
    maximum_replay_records=256,
    maximum_update_passes=2,
    maximum_compute_evaluations=110,
    maximum_compute_ratio=1.10,
)


class TransactionTests(unittest.TestCase):
    def test_all_constraints_accept_and_commit_candidate_bytes(self) -> None:
        previous = observation()
        proposed = observation(adaptation_objective=10.10)
        transaction = run_transaction(
            b"checkpoint-before",
            previous,
            lambda state: state + b"-candidate",
            lambda state: proposed,
            POLICY,
        )
        self.assertEqual(transaction.status, "accepted")
        self.assertEqual(transaction.state_after, b"checkpoint-before-candidate")
        self.assertFalse(transaction.report.rejection_reasons)

    def test_each_hard_constraint_has_a_distinct_reason(self) -> None:
        cases = {
            "adaptation_improvement_below_epsilon": {"adaptation_objective": 10.01},
            "base_accuracy_floor": {"base_accuracy": 0.84, "adaptation_objective": 10.10},
            "representation_floor": {"representation_score": 0.79, "adaptation_objective": 10.10},
            "original_prediction_degradation_bound": {
                "original_prediction_degradation": 1.01,
                "adaptation_objective": 10.10,
            },
            "transition_support_preservation": {
                "transition_support_losses": 1,
                "adaptation_objective": 10.10,
            },
            "expert_capacity_budget": {"expert_count": 81, "adaptation_objective": 10.10},
            "birth_budget": {"births": 17, "adaptation_objective": 10.10},
            "retirement_budget": {"retirements": 5, "adaptation_objective": 10.10},
            "replay_budget": {"replay_records": 257, "adaptation_objective": 10.10},
            "update_pass_budget": {"update_passes": 3, "adaptation_objective": 10.10},
            "compute_budget": {"compute_evaluations": 111, "adaptation_objective": 10.10},
            "matched_compute_ratio": {
                "compute_evaluations": 111,
                "matched_compute_evaluations": 100,
                "adaptation_objective": 10.10,
            },
        }
        previous = observation()
        for reason, changes in cases.items():
            report = evaluate_constraints(previous, observation(**changes), POLICY)
            self.assertIn(reason, report.rejection_reasons)
            transaction = run_transaction(
                b"prior",
                previous,
                lambda state: state + b"-must-not-commit",
                lambda state, changes=changes: observation(**changes),
                POLICY,
            )
            self.assertEqual(transaction.status, "rejected", reason)
            self.assertTrue(transaction.rolled_back_byte_identical, reason)
            self.assertEqual(transaction.checkpoint_before_sha256, transaction.checkpoint_after_sha256)

    def test_strong_adaptation_cannot_compensate_for_retention_failure(self) -> None:
        report = evaluate_constraints(
            observation(),
            observation(adaptation_objective=1000.0, base_accuracy=0.1),
            POLICY,
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.rejection_reasons, ("base_accuracy_floor",))

    def test_rollback_and_record_serialization_are_deterministic(self) -> None:
        transaction = run_transaction(
            b"prior",
            observation(),
            lambda state: state + b"-candidate",
            lambda state: observation(adaptation_objective=10.01),
            POLICY,
        )
        self.assertTrue(transaction.rolled_back_byte_identical)
        self.assertEqual(canonical_transaction_json(transaction), canonical_transaction_json(transaction))


if __name__ == "__main__":
    unittest.main()
