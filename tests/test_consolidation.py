from __future__ import annotations

import tempfile
import unittest

from ravel.memory import (
    AccessEvent,
    ConsolidationPolicy,
    ImmutableRecordError,
    MemoryClass,
    MemoryConsolidator,
    MemoryRecord,
    RetrievalLayoutPlanner,
    SQLiteMemoryStore,
)


SCOPE = {"repository": "epi13/RAVEL", "contract": "mncs-memory-v1"}


def record(
    record_id: str,
    statement: str,
    *,
    scope: dict[str, str] | None = None,
    relations: dict[str, tuple[str, ...]] | None = None,
    status: str = "active",
    authority_class: str = "repository-local",
) -> MemoryRecord:
    return MemoryRecord(
        record_id=record_id,
        memory_class=MemoryClass.SEMANTIC,
        statement=statement,
        scope=scope or SCOPE,
        created_at="2026-08-04T16:00:00Z",
        producer_id="test-suite",
        authority_class=authority_class,
        status=status,
        relations=relations or {},
    )


class ConsolidationTests(unittest.TestCase):
    def test_near_duplicates_produce_provenance_preserving_proposal(self) -> None:
        records = [
            record("memory:1", "RAVEL preserves negative memory during retrieval."),
            record("memory:2", "During retrieval RAVEL must preserve negative memory."),
        ]
        proposals = MemoryConsolidator(
            ConsolidationPolicy(similarity_threshold=0.65)
        ).propose(records, created_at="2026-08-04T17:00:00Z")

        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal.member_ids, ("memory:1", "memory:2"))
        self.assertEqual(proposal.supporting_ids, proposal.member_ids)
        self.assertEqual(proposal.status, "proposed")
        self.assertIn("negative", proposal.retrieval_keys)
        self.assertEqual(
            records[0].statement,
            "RAVEL preserves negative memory during retrieval.",
        )

    def test_scope_boundary_prevents_false_consolidation(self) -> None:
        records = [
            record("memory:1", "The verifier result remains UNKNOWN."),
            record(
                "memory:2",
                "The verifier result remains UNKNOWN.",
                scope={"repository": "other/project", "contract": "mncs-memory-v1"},
            ),
        ]
        proposals = MemoryConsolidator().propose(
            records, created_at="2026-08-04T17:00:00Z"
        )
        self.assertEqual(proposals, ())

    def test_explicit_contradiction_is_retained(self) -> None:
        records = [
            record("memory:old", "The routing policy uses a static verifier order."),
            record(
                "memory:new",
                "The routing policy uses a static verifier order.",
                relations={"contradicts": ("memory:old",)},
                authority_class="governed-evaluation",
            ),
        ]
        proposal = MemoryConsolidator().propose(
            records, created_at="2026-08-04T17:00:00Z"
        )[0]
        self.assertEqual(proposal.contradicting_ids, ("memory:old",))
        self.assertEqual(proposal.supporting_ids, ("memory:new",))

    def test_output_is_independent_of_input_order(self) -> None:
        records = [
            record("memory:a", "RAVEL stores immutable source records."),
            record("memory:b", "RAVEL keeps immutable source records."),
        ]
        consolidator = MemoryConsolidator(
            ConsolidationPolicy(similarity_threshold=0.6)
        )
        forward = consolidator.propose(
            records, created_at="2026-08-04T17:00:00Z"
        )
        reverse = consolidator.propose(
            reversed(records), created_at="2026-08-04T17:00:00Z"
        )
        self.assertEqual(forward, reverse)


class StoreTests(unittest.TestCase):
    def test_store_rejects_identity_reuse_with_different_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite3") as store:
                store.insert_record(record("memory:1", "Original statement."))
                with self.assertRaises(ImmutableRecordError):
                    store.insert_record(record("memory:1", "Changed statement."))

    def test_store_persists_sources_before_proposals(self) -> None:
        records = [
            record("memory:1", "RAVEL preserves negative memory during retrieval."),
            record("memory:2", "During retrieval RAVEL preserves negative memory."),
        ]
        proposal = MemoryConsolidator(
            ConsolidationPolicy(similarity_threshold=0.65)
        ).propose(records, created_at="2026-08-04T17:00:00Z")[0]
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite3") as store:
                store.insert_records(records)
                store.insert_proposal(proposal)
                replay = store.export_jsonl().splitlines()
                self.assertEqual(len(replay), 3)
                self.assertIn('"record_id":"memory:1"', replay[0])
                self.assertIn('"proposal_id":', replay[2])


class RetrievalLayoutTests(unittest.TestCase):
    def test_frequent_coaccess_forms_rebuildable_bucket(self) -> None:
        events = [
            AccessEvent(
                "query:1",
                ("memory:a", "memory:b", "memory:c"),
                ("memory:a", "memory:b"),
            ),
            AccessEvent(
                "query:2",
                ("memory:a", "memory:b"),
                ("memory:a", "memory:b"),
            ),
            AccessEvent(
                "query:3",
                ("memory:a", "memory:c"),
                ("memory:a", "memory:c"),
            ),
        ]
        buckets = RetrievalLayoutPlanner().plan(events, minimum_coaccess=2)
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0].member_ids, ("memory:a", "memory:b"))
        self.assertEqual(
            buckets[0].weighted_edges,
            (("memory:a", "memory:b", 2),),
        )


if __name__ == "__main__":
    unittest.main()
