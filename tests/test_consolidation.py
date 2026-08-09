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
    ProposalLifecycleEvent,
    RetrievalLayoutPlanner,
    ScopeCompatibility,
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
    memory_class: MemoryClass = MemoryClass.SEMANTIC,
    evidence_identity: str | None = None,
    experience_identity: str | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        record_id=record_id,
        memory_class=memory_class,
        statement=statement,
        scope=scope or SCOPE,
        created_at="2026-08-04T16:00:00Z",
        producer_id="test-suite",
        authority_class=authority_class,
        status=status,
        relations=relations or {},
        evidence_identity=evidence_identity,
        experience_identity=experience_identity,
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

    def test_named_scope_contract_can_allow_declared_extra_fields(self) -> None:
        records = [
            record("memory:1", "The verifier result remains UNKNOWN."),
            record(
                "memory:2",
                "The verifier result remains UNKNOWN.",
                scope={"repository": "epi13/RAVEL", "contract": "other"},
            ),
        ]
        policy = ConsolidationPolicy(
            scope_compatibility=ScopeCompatibility(
                contract_id="repository-only/1",
                equal_fields=("repository",),
                allow_extra_fields=True,
            )
        )
        self.assertEqual(len(MemoryConsolidator(policy).propose(records)), 1)


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

    def test_atomic_batch_rolls_back_when_a_later_record_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite3") as store:
                store.insert_record(record("memory:existing", "Original."))
                with self.assertRaises(ImmutableRecordError):
                    store.insert_records_atomic(
                        [
                            record("memory:new", "Must roll back."),
                            record("memory:existing", "Changed."),
                        ]
                    )
                self.assertIsNone(store.get_record("memory:new"))

    def test_search_keeps_negative_source_and_rebuilds_relations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite3") as store:
                store.insert_records_atomic(
                    [
                        record(
                            "memory:success",
                            "CUDA execution succeeds within the memory budget.",
                            evidence_identity="ravel-evidence:1",
                            experience_identity="ravel-experience:1",
                        ),
                        record(
                            "memory:failure",
                            "CUDA execution fails with an out of memory error.",
                            memory_class=MemoryClass.NEGATIVE,
                            relations={"contradicts": ("memory:success",)},
                        ),
                    ]
                )
                results = store.search_records("CUDA execution memory")
                self.assertEqual(
                    [item[0].record_id for item in results],
                    ["memory:failure", "memory:success"],
                )
                self.assertEqual(
                    store.relation_projection(),
                    (("memory:failure", "contradicts", "memory:success"),),
                )
                self.assertEqual(
                    store.get_record("memory:success").evidence_identity,
                    "ravel-evidence:1",
                )

    def test_proposal_lifecycle_is_append_only_and_ordered(self) -> None:
        records = [
            record("memory:1", "RAVEL keeps source history."),
            record("memory:2", "RAVEL keeps source history."),
        ]
        proposal = MemoryConsolidator().propose(records, created_at="2026-08-04T17:00:00Z")[0]
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite3") as store:
                store.insert_records(records)
                store.insert_proposal(proposal)
                store.insert_proposal_lifecycle(
                    ProposalLifecycleEvent("event:1", proposal.proposal_id, "reviewed", "2026-08-04T18:00:00Z", "reviewed")
                )
                store.insert_proposal_lifecycle(
                    ProposalLifecycleEvent("event:2", proposal.proposal_id, "accepted", "2026-08-04T19:00:00Z", "accepted for retrieval")
                )
                self.assertEqual(
                    [event.status for event in store.proposal_lifecycle(proposal.proposal_id)],
                    ["reviewed", "accepted"],
                )
                self.assertIn('"status":"accepted"', store.export_jsonl())


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
