from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ravel.adaptation import (
    RawObservation,
    RetentionConstraintPolicy,
    evaluate_constraints,
    run_transaction,
)
from ravel.c_observations import CTransactionObservation
from ravel.checkpoint import CheckpointCodec
from ravel.experience import ExperienceRecord
from ravel.mechanism_state import ExpertState, MechanismState
from ravel.planning import plan
from ravel.policy import load_frozen_policy
from ravel.rust_bridge import (
    FOUNDATION_CONTRACT,
    RustFoundationUnavailable,
    identity,
    interchange,
)
from ravel.transition import TransitionCompiler
from ravel.world import ToyBranchingWorld, ToyRingWorld


ROOT = Path(__file__).resolve().parents[1]


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


def _policy_dict() -> dict[str, object]:
    return {
        "adaptation_improvement_epsilon": POLICY.adaptation_improvement_epsilon,
        "base_accuracy_floor": POLICY.base_accuracy_floor,
        "representation_floor": POLICY.representation_floor,
        "original_prediction_degradation_bound": POLICY.original_prediction_degradation_bound,
        "maximum_transition_support_losses": POLICY.maximum_transition_support_losses,
        "maximum_experts": POLICY.maximum_experts,
        "maximum_births": POLICY.maximum_births,
        "maximum_retirements": POLICY.maximum_retirements,
        "maximum_replay_records": POLICY.maximum_replay_records,
        "maximum_update_passes": POLICY.maximum_update_passes,
        "maximum_compute_evaluations": POLICY.maximum_compute_evaluations,
        "maximum_compute_ratio": POLICY.maximum_compute_ratio,
    }


class RustParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.identity = identity()
        except RustFoundationUnavailable as error:
            raise unittest.SkipTest(f"Rust foundation unavailable: {error}") from error

    def test_foundation_identity_is_versioned(self) -> None:
        self.assertEqual(self.identity["foundation_contract"], FOUNDATION_CONTRACT)
        self.assertEqual(self.identity["implementation"], "ravel-rs/0.1")
        self.assertEqual(self.identity["world_abi"], "ravel-0.6-world-abi/1")
        self.assertEqual(self.identity["checkpoint_abi"], "ravel-0.6-checkpoint-abi/1")

    def test_constraint_reasons_match_python(self) -> None:
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
            proposed = observation(**changes)
            python = evaluate_constraints(previous, proposed, POLICY)
            rust = interchange(
                "adaptation.evaluate_constraints",
                {
                    "previous": previous.to_dict(),
                    "proposed": proposed.to_dict(),
                    "policy": _policy_dict(),
                },
            )
            self.assertEqual(rust["report"]["passed"], python.passed, reason)
            self.assertEqual(
                rust["report"]["rejection_reasons"],
                list(python.rejection_reasons),
                reason,
            )
            self.assertIn(reason, rust["report"]["rejection_reasons"])

    def test_accepted_transaction_commits_and_rejected_rolls_back(self) -> None:
        accepted = interchange(
            "adaptation.run_transaction",
            {
                "previous": observation().to_dict(),
                "proposed": observation(adaptation_objective=10.10).to_dict(),
                "policy": _policy_dict(),
                "state_before": "checkpoint-before",
                "state_candidate": "checkpoint-before-candidate",
            },
        )
        python_accepted = run_transaction(
            b"checkpoint-before",
            observation(),
            lambda state: state + b"-candidate",
            lambda state: observation(adaptation_objective=10.10),
            POLICY,
        )
        self.assertEqual(accepted["transaction"]["status"], python_accepted.status)
        self.assertFalse(accepted["transaction"]["rolled_back_byte_identical"])

        rejected = interchange(
            "adaptation.run_transaction",
            {
                "previous": observation().to_dict(),
                "proposed": observation(adaptation_objective=10.01).to_dict(),
                "policy": _policy_dict(),
                "state_before": "prior",
                "state_candidate": "prior-must-not-commit",
            },
        )
        self.assertEqual(rejected["transaction"]["status"], "rejected")
        self.assertTrue(rejected["transaction"]["rolled_back_byte_identical"])
        self.assertEqual(
            rejected["transaction"]["state_before_sha256"],
            rejected["transaction"]["state_after_sha256"],
        )

    def test_frozen_policy_identity_matches(self) -> None:
        python = load_frozen_policy()
        rust = interchange("policy.load", {"root": str(ROOT)})
        self.assertEqual(rust["policy"]["threshold_identity"], python.threshold_identity)
        self.assertEqual(rust["policy"]["base_accuracy_floor_q20"], python.base_accuracy_floor_q20)
        self.assertEqual(
            rust["policy"]["retention_loss_floor_q20"], python.retention_loss_floor_q20
        )
        self.assertIsNone(rust["policy"]["maximum_compute_evaluations"])

    def test_world_planning_matches_python(self) -> None:
        for provider_id, provider in (
            ("ravel-toy-branching/1", ToyBranchingWorld()),
            ("ravel-toy-ring/1", ToyRingWorld()),
        ):
            graph = TransitionCompiler().compile(provider)
            python = plan(graph, start=0, goal=3)
            rust = interchange(
                "world.compile_and_plan",
                {"provider_id": provider_id, "start": 0, "goal": 3, "maximum_steps": 32},
            )
            self.assertEqual(rust["provider_id"], provider.provider_id)
            self.assertEqual(rust["plan"]["status"], python.status)
            self.assertEqual(rust["plan"]["actions"], list(python.actions))
            self.assertEqual(rust["plan"]["reason"], python.reason)

        unknown = interchange(
            "world.compile_and_plan",
            {
                "provider_id": "ravel-toy-branching/1",
                "start": 2,
                "goal": 3,
                "maximum_steps": 1,
            },
        )
        self.assertEqual(unknown["plan"]["status"], "UNKNOWN")
        self.assertEqual(unknown["plan"]["reason"], "route_unavailable")

    def test_checkpoint_bytes_match_python(self) -> None:
        state = MechanismState(
            experts=(ExpertState("lineage-a", (1,), (0,)),),
            epoch=2,
            births=1,
        )
        python = CheckpointCodec().encode(state).decode()
        rust = interchange(
            "checkpoint.encode",
            {
                "experts": [
                    {
                        "lineage": "lineage-a",
                        "labels": [1],
                        "supported_actions": [0],
                    }
                ],
                "epoch": 2,
                "births": 1,
                "retirements": 0,
            },
        )
        self.assertEqual(rust["checkpoint"], python)

    def test_c_transaction_evaluation_matches_python(self) -> None:
        threshold = load_frozen_policy().threshold_identity
        payload = {
            "committed": False,
            "threshold_identity": threshold,
            "rejection_reason": "base_accuracy_floor",
            "failed_constraint_mask": 2,
            "rollback_byte_identical": True,
            "raw": {
                "objective_before_q20": 10_485_760,
                "objective_after_q20": 11_534_336,
                "base_accuracy_before_q20": 996_147,
                "base_accuracy_after_q20": 838_861,
                "retention_accuracy_before_q20": 996_147,
                "retention_accuracy_after_q20": 996_147,
                "retention_accuracy_delta_q20": 0,
                "representation_before_q20": 104_858,
                "representation_after_q20": 104_858,
                "prediction_rmse_before_q20": 104_858,
                "prediction_rmse_after_q20": 104_858,
                "transition_support_losses": 0,
                "expert_count": 70,
                "births": 1,
                "retirements": 0,
                "replay_records": 256,
                "update_passes": 1,
                "compute_evaluations": 100,
                "matched_compute_evaluations": 100,
                "matched_compute_reference_available": True,
            },
        }
        python = CTransactionObservation.from_json(payload).evaluate()
        rust = interchange(
            "c_observations.evaluate",
            {"root": str(ROOT), "observation": payload},
        )
        self.assertEqual(rust["report"]["passed"], python.passed)
        self.assertEqual(rust["report"]["rejection_reasons"], list(python.rejection_reasons))
        self.assertIn("base_accuracy_floor", rust["report"]["rejection_reasons"])

    def test_development_experience_stays_advisory_unknown(self) -> None:
        transaction = {"committed": True, "rejection_reason": "none"}
        python = ExperienceRecord.from_development_transaction(
            candidate_id="ravel-0.6-candidate-001",
            context_identity="transaction-accepted",
            task_environment="ravel-toy-branching-c/1",
            provider_id="ravel-candidate",
            transaction=transaction,
        )
        rust = interchange(
            "experience.from_development_transaction",
            {
                "candidate_id": "ravel-0.6-candidate-001",
                "context_identity": "transaction-accepted",
                "task_environment": "ravel-toy-branching-c/1",
                "provider_id": "ravel-candidate",
                "transaction": transaction,
            },
        )
        self.assertTrue(python.negative)
        self.assertTrue(rust["negative"])
        self.assertEqual(rust["memory_class"], "negative")
        self.assertEqual(rust["record_id"], python.record_id)

    def test_lifecycle_round_trip_uses_same_candidate_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rust = interchange(
                "lifecycle.round_trip",
                {"path": str(Path(directory) / "candidates.jsonl")},
            )
        self.assertEqual(rust["candidate_id"], "ravel-0.6-candidate-001")
        self.assertEqual(rust["state"], "candidate_frozen")


if __name__ == "__main__":
    unittest.main()
