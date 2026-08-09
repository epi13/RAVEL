from __future__ import annotations

import tempfile
import unittest

from ravel.experience import ExperienceRecord
from ravel.lifecycle import CandidateLedger, CandidateState, LedgerError
from ravel.memory import MemoryClass
from ravel.memory.store import SQLiteMemoryStore


class LifecycleTests(unittest.TestCase):
    def test_candidate_numbers_are_sequential_and_freeze_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = CandidateLedger(f"{directory}/candidates.jsonl")
            candidate = ledger.create(development_partition="dev-a", created_at="t0")
            self.assertEqual(candidate.candidate_id, "ravel-0.6-candidate-001")
            ledger.begin_development(candidate.candidate_id)
            ledger.append_development_feedback(candidate.candidate_id, result_ref="dev-result-1")
            frozen = ledger.freeze(
                candidate.candidate_id,
                source_identity="sha256:source",
                evaluator_identity="sha256:evaluator",
                threshold_identity="sha256:threshold",
                selection_partition="selection-a",
            )
            self.assertEqual(frozen.state, CandidateState.FROZEN)
            with self.assertRaises(LedgerError):
                ledger.append_development_feedback(candidate.candidate_id, result_ref="must-not-enter")
            self.assertEqual(len(ledger.records()), 1)

    def test_selection_result_is_retained_without_same_candidate_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = CandidateLedger(f"{directory}/candidates.jsonl")
            candidate = ledger.create(development_partition="dev", created_at="t0")
            ledger.begin_development(candidate.candidate_id)
            ledger.freeze(
                candidate.candidate_id,
                source_identity="sha256:source",
                evaluator_identity="sha256:evaluator",
                threshold_identity="sha256:threshold",
                selection_partition="selection",
            )
            ledger.start_selection(candidate.candidate_id)
            rejected = ledger.record_selection(
                candidate.candidate_id,
                selected=False,
                result_ref="selection-result",
                rejection_reasons=("base_accuracy_floor",),
            )
            self.assertEqual(rejected.state, CandidateState.REJECTED)
            self.assertEqual(rejected.rejection_reasons, ("base_accuracy_floor",))
            with self.assertRaises(LedgerError):
                ledger.append_development_feedback(candidate.candidate_id, result_ref="selection-feedback")

    def test_ledger_mutation_and_candidate_limit_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/candidates.jsonl"
            ledger = CandidateLedger(path, maximum_candidates=1)
            candidate = ledger.create(development_partition="dev", created_at="t0")
            with self.assertRaises(LedgerError):
                ledger.create(development_partition="dev-2", created_at="t1")
            with open(path, "a", encoding="utf-8") as stream:
                stream.write("{}\n")
            with self.assertRaises(LedgerError):
                ledger.get(candidate.candidate_id)

    def test_candidate_number_gap_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = CandidateLedger(f"{directory}/candidates.jsonl", maximum_candidates=8)
            first = ledger.create(development_partition="dev", created_at="t0")
            ledger._append(
                "ravel-0.6-candidate-003",
                CandidateState.CREATED,
                {"number": 3, "development_partition": "dev", "created_at": "t2"},
            )
            with self.assertRaises(LedgerError):
                ledger.get(first.candidate_id)

    def test_contamination_flag_and_rejection_are_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = CandidateLedger(f"{directory}/candidates.jsonl")
            candidate = ledger.create(development_partition="dev", created_at="t0")
            ledger.begin_development(candidate.candidate_id)
            ledger.freeze(
                candidate.candidate_id,
                source_identity="sha256:source",
                evaluator_identity="sha256:evaluator",
                threshold_identity="sha256:threshold",
                selection_partition="selection",
            )
            ledger.start_selection(candidate.candidate_id)
            result = ledger.record_selection(
                candidate.candidate_id,
                selected=False,
                result_ref="selection-result",
                rejection_reasons=("UNKNOWN",),
                contamination_flag=True,
            )
            self.assertTrue(result.contamination_flag)
            self.assertEqual(result.rejection_reasons, ("UNKNOWN",))


class ExperienceTests(unittest.TestCase):
    def test_unknown_and_rejected_experience_becomes_negative_memory(self) -> None:
        experience = ExperienceRecord(
            candidate_id="ravel-0.6-candidate-001",
            context_identity="toy-a",
            task_environment="toy-environment",
            requested_strategy="sequential-cpu",
            provider_id="fake-provider",
            verifier_id="forge-verifier",
            raw_result={"oom": True},
            formal_disposition="UNKNOWN",
            adaptation_decision="rejected",
            rejection_reason="compute_budget",
            applicability_scope={"hardware": "cpu-only"},
        )
        record = experience.to_memory_record(created_at="2026-08-08T00:00:00Z")
        self.assertEqual(record.memory_class.value, "negative")
        self.assertEqual(record.experience_identity, experience.record_id)
        self.assertIn("UNKNOWN", record.statement)

    def test_real_development_outcomes_remain_scoped_negative_memory(self) -> None:
        accepted = ExperienceRecord.from_development_transaction(
            candidate_id="ravel-0.6-candidate-001",
            context_identity="transaction-accepted",
            task_environment="ravel-toy-branching-c/1",
            provider_id="ravel-candidate",
            transaction={"committed": True, "rejection_reason": "none"},
            matched_compute={"reference_available": True},
        )
        rejected = ExperienceRecord.from_development_transaction(
            candidate_id="ravel-0.6-candidate-001",
            context_identity="transaction-rejected",
            task_environment="ravel-toy-branching-c/1",
            provider_id="ravel-candidate",
            transaction={"committed": False, "rejection_reason": "retention_loss_floor"},
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite") as store:
                store.insert_records_atomic(
                    (
                        accepted.to_memory_record(created_at="2026-08-08T00:00:00Z"),
                        rejected.to_memory_record(created_at="2026-08-08T00:00:01Z"),
                    )
                )
                first = store.search_records("retention constrained adaptation")
                second = store.search_records("retention constrained adaptation")
                self.assertEqual(first, second)
                self.assertEqual(len(first), 2)
                self.assertTrue(all(record.memory_class is MemoryClass.NEGATIVE for record, _ in first))
                self.assertEqual(
                    store.search_records("retention", include_negative=False), ()
                )


if __name__ == "__main__":
    unittest.main()
