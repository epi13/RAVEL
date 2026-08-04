"""Small SQLite-backed append-only store for RAVEL memory records."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .models import ConsolidationProposal, MemoryClass, MemoryRecord, canonical_json


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

                CREATE INDEX IF NOT EXISTS source_records_class_idx
                    ON source_records(memory_class, sequence);
                CREATE INDEX IF NOT EXISTS proposal_status_idx
                    ON consolidation_proposals(status, sequence);
                """
            )

    def insert_record(self, record: MemoryRecord) -> None:
        payload = canonical_json(record.to_dict())
        existing = self._connection.execute(
            "SELECT digest FROM source_records WHERE record_id = ?", (record.record_id,)
        ).fetchone()
        if existing is not None:
            if existing["digest"] == record.digest:
                return
            raise ImmutableRecordError(
                f"record {record.record_id!r} already exists with different content"
            )
        with self._connection:
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
        for record in records:
            self.insert_record(record)

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
        )
