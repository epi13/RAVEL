"""Typed, deterministic records for the RAVEL memory prototype.

The records in this module deliberately separate authoritative source memory from
replaceable consolidation and retrieval projections. Consolidation proposals
never overwrite or delete their source records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


def utc_now() -> str:
    """Return a stable RFC 3339 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Mapping[str, Any]) -> str:
    """Serialize a mapping deterministically for hashing and export."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_mapping(value: Mapping[str, Any]) -> str:
    """Return a SHA-256 content digest for a canonical mapping."""

    payload = canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class MemoryClass(str, Enum):
    EPISODIC = "episodic"
    CAUSAL = "causal"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class ScopeCompatibility:
    """Named, testable policy for deciding whether two scopes may be grouped."""

    contract_id: str = "ravel-scope-exact/1"
    equal_fields: tuple[str, ...] = ()
    allow_extra_fields: bool = False

    def compatible(self, left: Mapping[str, str], right: Mapping[str, str]) -> bool:
        if self.equal_fields:
            if any(left.get(field) != right.get(field) for field in self.equal_fields):
                return False
            return self.allow_extra_fields or set(left) == set(right)
        return dict(left) == dict(right)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """An immutable source memory record.

    ``scope`` is intentionally structured. Records with incompatible scope are
    never automatically consolidated, even when their text is very similar.
    ``relations`` supports explicit links such as ``contradicts`` and
    ``supersedes`` without asking the consolidator to invent causal meaning.
    """

    record_id: str
    memory_class: MemoryClass
    statement: str
    scope: Mapping[str, str]
    created_at: str
    producer_id: str
    authority_class: str = "advisory"
    status: str = "active"
    tags: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    relations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "ravel-memory-record/0.1"
    evidence_identity: str | None = None
    experience_identity: str | None = None

    def __post_init__(self) -> None:
        if not self.record_id.strip():
            raise ValueError("record_id must not be empty")
        if not self.statement.strip():
            raise ValueError("statement must not be empty")
        if not self.scope:
            raise ValueError("scope must declare at least one boundary")
        if not self.producer_id.strip():
            raise ValueError("producer_id must not be empty")
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["memory_class"] = self.memory_class.value
        payload["tags"] = list(self.tags)
        payload["source_ids"] = list(self.source_ids)
        payload["relations"] = {
            key: list(values) for key, values in sorted(self.relations.items())
        }
        payload["scope"] = dict(sorted(self.scope.items()))
        payload["metadata"] = dict(self.metadata)
        return payload

    @property
    def digest(self) -> str:
        return digest_mapping(self.to_dict())

    @property
    def scope_signature(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self.scope.items()))


@dataclass(frozen=True, slots=True)
class ConsolidationProposal:
    """A derived, challengeable summary over source records."""

    proposal_id: str
    method_version: str
    created_at: str
    memory_class: MemoryClass
    canonical_statement: str
    scope: Mapping[str, str]
    member_ids: tuple[str, ...]
    supporting_ids: tuple[str, ...]
    contradicting_ids: tuple[str, ...]
    superseded_ids: tuple[str, ...]
    retrieval_keys: tuple[str, ...]
    clustering_confidence: float
    status: str = "proposed"
    scope_contract_id: str = "ravel-scope-exact/1"
    limitations: tuple[str, ...] = (
        "Derived projection only; does not alter source status or authority.",
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["memory_class"] = self.memory_class.value
        payload["scope"] = dict(sorted(self.scope.items()))
        for key in (
            "member_ids",
            "supporting_ids",
            "contradicting_ids",
            "superseded_ids",
            "retrieval_keys",
            "limitations",
        ):
            payload[key] = list(payload[key])
        return payload

    @property
    def digest(self) -> str:
        return digest_mapping(self.to_dict())


@dataclass(frozen=True, slots=True)
class AccessEvent:
    """One query-time access observation for a replaceable retrieval projection."""

    query_id: str
    retrieved_ids: tuple[str, ...]
    selected_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalBucket:
    """A suggested co-location bucket based only on observed co-access."""

    bucket_id: str
    member_ids: tuple[str, ...]
    weighted_edges: tuple[tuple[str, str, int], ...]
    reason: str = "frequent-co-access"


@dataclass(frozen=True, slots=True)
class ProposalLifecycleEvent:
    """Append-only review state transition for a consolidation proposal."""

    event_id: str
    proposal_id: str
    status: str
    created_at: str
    reason: str

    ALLOWED_STATUSES = frozenset(
        {"proposed", "reviewed", "accepted", "challenged", "superseded"}
    )

    def __post_init__(self) -> None:
        if self.status not in self.ALLOWED_STATUSES:
            raise ValueError(f"unsupported proposal lifecycle status: {self.status}")
        if not self.event_id or not self.proposal_id or not self.reason:
            raise ValueError("proposal lifecycle identity and reason are required")
