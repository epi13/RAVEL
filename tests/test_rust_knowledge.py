from __future__ import annotations

import unittest

from ravel.knowledge import KnowledgeError, KnowledgeRecord, promote
from ravel.memory import (
    AccessEvent,
    ConsolidationPolicy,
    MemoryClass,
    MemoryConsolidator,
    MemoryRecord,
    RetrievalLayoutPlanner,
    ScopeCompatibility,
)
from ravel.rust_bridge import RustFoundationUnavailable, identity, interchange


SCOPE = {"repository": "epi13/RAVEL", "contract": "mncs-memory-v1"}


def record(record_id: str, statement: str, **changes: object) -> MemoryRecord:
    values: dict[str, object] = {
        "record_id": record_id,
        "memory_class": MemoryClass.SEMANTIC,
        "statement": statement,
        "scope": SCOPE,
        "created_at": "2026-08-04T16:00:00Z",
        "producer_id": "test-suite",
        "authority_class": "repository-local",
    }
    values.update(changes)
    return MemoryRecord(**values)


class KnowledgeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            identity()
        except RustFoundationUnavailable as error:
            raise unittest.SkipTest(f"Rust foundation unavailable: {error}") from error

    def test_consolidation_proposals_match_python(self) -> None:
        records = [
            record("memory:1", "RAVEL preserves negative memory during retrieval."),
            record("memory:2", "During retrieval RAVEL must preserve negative memory."),
        ]
        python = MemoryConsolidator(
            ConsolidationPolicy(similarity_threshold=0.65)
        ).propose(records, created_at="2026-08-04T17:00:00Z")
        rust = interchange(
            "memory.propose_consolidation",
            {
                "created_at": "2026-08-04T17:00:00Z",
                "policy": {"similarity_threshold": 0.65},
                "records": [item.to_dict() for item in records],
            },
        )
        self.assertEqual(len(rust["proposals"]), 1)
        self.assertEqual(python[0].proposal_id, rust["proposals"][0]["proposal_id"])
        self.assertEqual(list(python[0].member_ids), rust["proposals"][0]["member_ids"])
        self.assertEqual(python[0].canonical_statement, rust["proposals"][0]["canonical_statement"])

    def test_scope_still_blocks_cross_boundary_compaction(self) -> None:
        records = [
            record("memory:1", "The verifier result remains UNKNOWN."),
            record(
                "memory:2",
                "The verifier result remains UNKNOWN.",
                scope={"repository": "other/project", "contract": "mncs-memory-v1"},
            ),
        ]
        rust = interchange(
            "memory.propose_consolidation",
            {
                "created_at": "2026-08-04T17:00:00Z",
                "records": [item.to_dict() for item in records],
            },
        )
        self.assertEqual(rust["proposals"], [])
        rust_allowed = interchange(
            "memory.propose_consolidation",
            {
                "created_at": "2026-08-04T17:00:00Z",
                "policy": {
                    "similarity_threshold": 0.72,
                    "scope_compatibility": {
                        "contract_id": "repository-only/1",
                        "equal_fields": ["repository"],
                        "allow_extra_fields": True,
                    },
                },
                "records": [
                    record("memory:1", "The verifier result remains UNKNOWN.").to_dict(),
                    record(
                        "memory:2",
                        "The verifier result remains UNKNOWN.",
                        scope={"repository": "epi13/RAVEL", "contract": "other"},
                    ).to_dict(),
                ],
            },
        )
        python_allowed = MemoryConsolidator(
            ConsolidationPolicy(
                scope_compatibility=ScopeCompatibility(
                    contract_id="repository-only/1",
                    equal_fields=("repository",),
                    allow_extra_fields=True,
                )
            )
        ).propose(
            [
                record("memory:1", "The verifier result remains UNKNOWN."),
                record(
                    "memory:2",
                    "The verifier result remains UNKNOWN.",
                    scope={"repository": "epi13/RAVEL", "contract": "other"},
                ),
            ]
        )
        self.assertEqual(len(python_allowed), 1)
        self.assertEqual(len(rust_allowed["proposals"]), 1)

    def test_retrieval_buckets_match_python(self) -> None:
        events = [
            AccessEvent("query:1", ("memory:a", "memory:b", "memory:c"), ("memory:a", "memory:b")),
            AccessEvent("query:2", ("memory:a", "memory:b"), ("memory:a", "memory:b")),
            AccessEvent("query:3", ("memory:a", "memory:c"), ("memory:a", "memory:c")),
        ]
        python = RetrievalLayoutPlanner().plan(events, minimum_coaccess=2)
        rust = interchange(
            "memory.plan_retrieval",
            {
                "minimum_coaccess": 2,
                "events": [
                    {
                        "query_id": event.query_id,
                        "retrieved_ids": list(event.retrieved_ids),
                        "selected_ids": list(event.selected_ids),
                    }
                    for event in events
                ],
            },
        )
        self.assertEqual(rust["buckets"][0]["member_ids"], list(python[0].member_ids))
        self.assertEqual(rust["buckets"][0]["bucket_id"], python[0].bucket_id)

    def test_compaction_does_not_delete_sources(self) -> None:
        records = [
            record("memory:1", "RAVEL stores immutable source records."),
            record("memory:2", "RAVEL keeps immutable source records."),
        ]
        rust = interchange(
            "retention.compact",
            {
                "created_at": "2026-08-04T17:00:00Z",
                "policy": {"similarity_threshold": 0.6},
                "records": [item.to_dict() for item in records],
            },
        )
        self.assertEqual(rust["deleted"], 0)
        self.assertEqual(len(rust["proposals"]), 1)

    def test_knowledge_promotion_is_fail_closed_on_both_sides(self) -> None:
        current = KnowledgeRecord(
            record_id="knowledge:obs",
            stage="observation",
            statement="A bounded Forge check returned UNKNOWN.",
            scope={"partition": "development"},
            evidence_ids=("obs:1",),
            evaluation_status="UNKNOWN",
            created_at="2026-08-14T00:00:00Z",
        )
        with self.assertRaises(KnowledgeError):
            promote(
                current,
                next_stage="supported_strategy",
                next_id="knowledge:bad",
                statement="must not skip",
                created_at="t1",
            )
        rust_skip = interchange(
            "knowledge.promote",
            {
                "current": current.to_dict(),
                "next_stage": "supported_strategy",
                "next_id": "knowledge:bad",
                "statement": "must not skip",
                "evaluation_status": "UNKNOWN",
                "created_at": "t1",
            },
        )
        self.assertEqual(rust_skip["status"], "FAIL")
        episode = promote(
            current,
            next_stage="episode",
            next_id="knowledge:ep",
            statement=current.statement,
            evidence_ids=current.evidence_ids,
            evaluation_status="UNKNOWN",
            created_at="t1",
        )
        rust_episode = interchange(
            "knowledge.promote",
            {
                "current": current.to_dict(),
                "next_stage": "episode",
                "next_id": "knowledge:ep",
                "statement": current.statement,
                "evidence_ids": list(current.evidence_ids),
                "evaluation_status": "UNKNOWN",
                "created_at": "t1",
            },
        )
        self.assertEqual(rust_episode["status"], "PASS")
        self.assertEqual(rust_episode["record"]["stage"], episode.stage)
        rust_unknown = interchange(
            "knowledge.promote",
            {
                "current": rust_episode["record"],
                "next_stage": "episode",
                "next_id": "knowledge:pass",
                "statement": episode.statement,
                "evaluation_status": "PASS",
                "created_at": "t2",
            },
        )
        self.assertEqual(rust_unknown["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
