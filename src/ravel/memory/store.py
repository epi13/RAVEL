"""Small SQLite-backed append-only store for RAVEL memory records."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Iterable

from .models import (
    ConsolidationProposal,
    MemoryClass,
    MemoryRecord,
    ProposalLifecycleEvent,
    canonical_json,
)


class ImmutableRecordError(RuntimeError):
    """Raised when an existing logical identity is reused with different bytes."""


class SQLiteMemoryStore:
    """Persist source records and derived proposals without mutating history."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_records (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE,
                    digest TEXT NOT NULL,
                    memory_class TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS consolidation_proposals (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL UNIQUE,
                    digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS consolidation_members (
                    proposal_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    PRIMARY KEY (proposal_id, record_id, relation),
                    FOREIGN KEY (proposal_id)
                        REFERENCES consolidation_proposals(proposal_id),
                    FOREIGN KEY (record_id)
                        REFERENCES source_records(record_id)
                );

                CREATE TABLE IF NOT EXISTS proposal_lifecycle_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    proposal_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (proposal_id)
                        REFERENCES consolidation_proposals(proposal_id)
                );

                CREATE INDEX IF NOT EXISTS source_records_class_idx
                    ON source_records(memory_class, sequence);
                CREATE INDEX IF NOT EXISTS proposal_status_idx
                    ON consolidation_proposals(status, sequence);
                """
            )

    def insert_record(self, record: MemoryRecord) -> None:
        self.insert_records_atomic((record,))

    def insert_records_atomic(self, records: Iterable[MemoryRecord]) -> None:
        """Insert a batch in one SQLite transaction or insert none of it."""

        ordered = tuple(records)
        payloads: list[tuple[MemoryRecord, str]] = [
            (record, canonical_json(record.to_dict())) for record in ordered
        ]
        with self._connection:
            for record, payload in payloads:
                existing = self._connection.execute(
                    "SELECT digest FROM source_records WHERE record_id = ?",
                    (record.record_id,),
                ).fetchone()
                if existing is not None:
                    if existing["digest"] == record.digest:
                        continue
                    raise ImmutableRecordError(
                        f"record {record.record_id!r} already exists with different content"
                    )
                self._connection.execute(
                    """
                    INSERT INTO source_records
                        (record_id, digest, memory_class, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.record_id,
                        record.digest,
                        record.memory_class.value,
                        payload,
                        record.created_at,
                    ),
                )

    def insert_records(self, records: Iterable[MemoryRecord]) -> None:
        self.insert_records_atomic(records)

    def get_record(self, record_id: str) -> MemoryRecord | None:
        row = self._connection.execute(
            "SELECT payload_json FROM source_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return self._decode_record(row["payload_json"]) if row else None

    def iter_records(
        self, memory_class: MemoryClass | None = None
    ) -> tuple[MemoryRecord, ...]:
        if memory_class is None:
            rows = self._connection.execute(
                "SELECT payload_json FROM source_records ORDER BY sequence"
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT payload_json FROM source_records
                WHERE memory_class = ? ORDER BY sequence
                """,
                (memory_class.value,),
            ).fetchall()
        return tuple(self._decode_record(row["payload_json"]) for row in rows)

    def insert_proposal(self, proposal: ConsolidationProposal) -> None:
        missing = [
            record_id
            for record_id in proposal.member_ids
            if self.get_record(record_id) is None
        ]
        if missing:
            raise ValueError(f"proposal references missing records: {missing}")

        payload = canonical_json(proposal.to_dict())
        existing = self._connection.execute(
            """
            SELECT digest FROM consolidation_proposals WHERE proposal_id = ?
            """,
            (proposal.proposal_id,),
        ).fetchone()
        if existing is not None:
            if existing["digest"] == proposal.digest:
                return
            raise ImmutableRecordError(
                f"proposal {proposal.proposal_id!r} already exists with different content"
            )

        relations: list[tuple[str, str, str]] = []
        support = set(proposal.supporting_ids)
        contradictions = set(proposal.contradicting_ids)
        superseded = set(proposal.superseded_ids)
        for record_id in proposal.member_ids:
            relation = "member"
            if record_id in support:
                relation = "supporting"
            elif record_id in contradictions:
                relation = "contradicting"
            elif record_id in superseded:
                relation = "superseded"
            relations.append((proposal.proposal_id, record_id, relation))

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO consolidation_proposals
                    (proposal_id, digest, payload_json, created_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.digest,
                    payload,
                    proposal.created_at,
                    proposal.status,
                ),
            )
            self._connection.executemany(
                """
                INSERT INTO consolidation_members
                    (proposal_id, record_id, relation)
                VALUES (?, ?, ?)
                """,
                relations,
            )

    def insert_proposal_lifecycle(self, event: ProposalLifecycleEvent) -> None:
        """Append one governed review event without mutating the proposal row."""

        proposal = self._connection.execute(
            "SELECT status FROM consolidation_proposals WHERE proposal_id = ?",
            (event.proposal_id,),
        ).fetchone()
        if proposal is None:
            raise ValueError(f"proposal does not exist: {event.proposal_id}")
        previous = proposal["status"]
        latest = self._connection.execute(
            """
            SELECT status FROM proposal_lifecycle_events
            WHERE proposal_id = ? ORDER BY sequence DESC LIMIT 1
            """,
            (event.proposal_id,),
        ).fetchone()
        if latest is not None:
            previous = latest["status"]
        allowed = {
            "proposed": {"reviewed", "challenged", "superseded"},
            "reviewed": {"accepted", "challenged", "superseded"},
            "accepted": {"challenged", "superseded"},
            "challenged": {"reviewed", "accepted", "superseded"},
            "superseded": set(),
        }
        if event.status not in allowed.get(previous, set()):
            raise ValueError(f"invalid proposal lifecycle transition: {previous}->{event.status}")
        payload = canonical_json(
            {
                "event_id": event.event_id,
                "proposal_id": event.proposal_id,
                "status": event.status,
                "created_at": event.created_at,
                "reason": event.reason,
            }
        )
        digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
        with self._connection:
            existing = self._connection.execute(
                "SELECT digest FROM proposal_lifecycle_events WHERE event_id = ?",
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                if existing["digest"] == digest:
                    return
                raise ImmutableRecordError(
                    f"lifecycle event {event.event_id!r} already exists with different content"
                )
            self._connection.execute(
                """
                INSERT INTO proposal_lifecycle_events
                    (event_id, proposal_id, status, reason, created_at, digest, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.proposal_id,
                    event.status,
                    event.reason,
                    event.created_at,
                    digest,
                    payload,
                ),
            )

    def proposal_lifecycle(self, proposal_id: str) -> tuple[ProposalLifecycleEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT event_id, proposal_id, status, created_at, reason
            FROM proposal_lifecycle_events WHERE proposal_id = ? ORDER BY sequence
            """,
            (proposal_id,),
        ).fetchall()
        return tuple(
            ProposalLifecycleEvent(
                event_id=row["event_id"],
                proposal_id=row["proposal_id"],
                status=row["status"],
                created_at=row["created_at"],
                reason=row["reason"],
            )
            for row in rows
        )

    def search_records(
        self,
        query: str,
        *,
        memory_class: MemoryClass | None = None,
        include_negative: bool = True,
    ) -> tuple[tuple[MemoryRecord, int], ...]:
        """Deterministic source retrieval; negative records are included by default."""

        terms = tuple(sorted(set(re.findall(r"[a-z0-9][a-z0-9_-]*", query.casefold()))))
        if not terms:
            return ()
        matches: list[tuple[MemoryRecord, int]] = []
        for record in self.iter_records(memory_class):
            if not include_negative and record.memory_class is MemoryClass.NEGATIVE:
                continue
            haystack = " ".join((record.statement, *record.tags)).casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                matches.append((record, score))
        return tuple(sorted(matches, key=lambda item: (-item[1], item[0].record_id)))

    def relation_projection(self) -> tuple[tuple[str, str, str], ...]:
        """Rebuild a disposable graph projection from append-only records."""

        edges: set[tuple[str, str, str]] = set()
        for record in self.iter_records():
            for relation, targets in record.relations.items():
                for target in targets:
                    edges.add((record.record_id, relation, target))
        for row in self._connection.execute(
            "SELECT proposal_id, record_id, relation FROM consolidation_members"
        ):
            edges.add((row["proposal_id"], row["relation"], row["record_id"]))
        return tuple(sorted(edges))

    def export_jsonl(self) -> str:
        """Return a deterministic source-first replay stream."""

        lines: list[str] = []
        for row in self._connection.execute(
            "SELECT payload_json FROM source_records ORDER BY sequence"
        ):
            lines.append(row["payload_json"])
        for row in self._connection.execute(
            "SELECT payload_json FROM consolidation_proposals ORDER BY sequence"
        ):
            lines.append(row["payload_json"])
        for row in self._connection.execute(
            "SELECT payload_json FROM proposal_lifecycle_events ORDER BY sequence"
        ):
            lines.append(row["payload_json"])
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _decode_record(payload_json: str) -> MemoryRecord:
        payload = json.loads(payload_json)
        return MemoryRecord(
            record_id=payload["record_id"],
            memory_class=MemoryClass(payload["memory_class"]),
            statement=payload["statement"],
            scope=payload["scope"],
            created_at=payload["created_at"],
            producer_id=payload["producer_id"],
            authority_class=payload.get("authority_class", "advisory"),
            status=payload.get("status", "active"),
            tags=tuple(payload.get("tags", ())),
            source_ids=tuple(payload.get("source_ids", ())),
            relations={
                key: tuple(values)
                for key, values in payload.get("relations", {}).items()
            },
            metadata=payload.get("metadata", {}),
            schema_version=payload.get("schema_version", "ravel-memory-record/0.1"),
            evidence_identity=payload.get("evidence_identity"),
            experience_identity=payload.get("experience_identity"),
        )
