"""Deterministic semantic consolidation and retrieval-layout planning.

This module is intentionally conservative. It creates proposals over compatible
records; it does not rewrite history, promote knowledge, infer formal status, or
modify MNCS/MNCDS-governed evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Sequence

from .models import (
    AccessEvent,
    ConsolidationProposal,
    MemoryRecord,
    RetrievalBucket,
    ScopeCompatibility,
    utc_now,
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-]*")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "with",
    }
)


def _normalize_token(token: str) -> str:
    # A deliberately small, deterministic normalization baseline. This handles
    # common inflectional duplicates such as preserve/preserves without adding a
    # language-model or stemming dependency.
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        _normalize_token(token)
        for token in _TOKEN_RE.findall(text.casefold())
        if token not in _STOP_WORDS
    )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _stable_id(prefix: str, values: Sequence[str]) -> str:
    material = "\x1f".join(sorted(values)).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(material).hexdigest()[:24]}"


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        # Stable root selection makes output independent of input order.
        low, high = sorted((left_root, right_root))
        self.parent[high] = low


@dataclass(frozen=True, slots=True)
class ConsolidationPolicy:
    similarity_threshold: float = 0.72
    minimum_cluster_size: int = 2
    maximum_cluster_size: int = 64
    retrieval_key_count: int = 8
    method_version: str = "ravel-semantic-consolidation/0.1"
    scope_compatibility: ScopeCompatibility = ScopeCompatibility()

    def __post_init__(self) -> None:
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if self.minimum_cluster_size < 2:
            raise ValueError("minimum_cluster_size must be at least 2")
        if self.maximum_cluster_size < self.minimum_cluster_size:
            raise ValueError("maximum_cluster_size must not be smaller than minimum")
        if self.retrieval_key_count < 1:
            raise ValueError("retrieval_key_count must be positive")


class MemoryConsolidator:
    """Create provenance-preserving consolidation proposals."""

    def __init__(self, policy: ConsolidationPolicy | None = None) -> None:
        self.policy = policy or ConsolidationPolicy()

    def propose(
        self,
        records: Iterable[MemoryRecord],
        *,
        created_at: str | None = None,
    ) -> tuple[ConsolidationProposal, ...]:
        ordered = sorted(records, key=lambda record: record.record_id)
        if not ordered:
            return ()

        record_by_id = {record.record_id: record for record in ordered}
        if len(record_by_id) != len(ordered):
            raise ValueError("record_id values must be unique")

        groups: list[list[MemoryRecord]] = []
        for record in ordered:
            for group in groups:
                if (
                    group[0].memory_class == record.memory_class
                    and self.policy.scope_compatibility.compatible(
                        group[0].scope, record.scope
                    )
                ):
                    group.append(record)
                    break
            else:
                groups.append([record])

        proposals: list[ConsolidationProposal] = []
        timestamp = created_at or utc_now()
        for scoped_records in groups:
            proposals.extend(
                self._propose_group(scoped_records, record_by_id, created_at=timestamp)
            )
        return tuple(sorted(proposals, key=lambda item: item.proposal_id))

    def _propose_group(
        self,
        records: Sequence[MemoryRecord],
        record_by_id: dict[str, MemoryRecord],
        *,
        created_at: str,
    ) -> list[ConsolidationProposal]:
        if len(records) < self.policy.minimum_cluster_size:
            return []

        token_map = {record.record_id: _tokens(record.statement) for record in records}
        forest = _UnionFind(token_map)

        for index, left in enumerate(records):
            for right in records[index + 1 :]:
                similarity = _jaccard(token_map[left.record_id], token_map[right.record_id])
                if similarity >= self.policy.similarity_threshold:
                    forest.union(left.record_id, right.record_id)

        components: dict[str, list[MemoryRecord]] = defaultdict(list)
        for record in records:
            components[forest.find(record.record_id)].append(record)

        proposals: list[ConsolidationProposal] = []
        for component in components.values():
            if len(component) < self.policy.minimum_cluster_size:
                continue
            if len(component) > self.policy.maximum_cluster_size:
                component = sorted(component, key=lambda item: item.record_id)[
                    : self.policy.maximum_cluster_size
                ]
            proposals.append(
                self._make_proposal(component, record_by_id, token_map, created_at)
            )
        return proposals

    def _make_proposal(
        self,
        component: Sequence[MemoryRecord],
        record_by_id: dict[str, MemoryRecord],
        token_map: dict[str, frozenset[str]],
        created_at: str,
    ) -> ConsolidationProposal:
        members = sorted(component, key=lambda item: item.record_id)
        member_ids = tuple(record.record_id for record in members)

        contradicted: set[str] = set()
        superseded: set[str] = set()
        for record in members:
            contradicted.update(record.relations.get("contradicts", ()))
            superseded.update(record.relations.get("supersedes", ()))

        # Keep only valid source identities; unresolved links remain in raw records.
        contradiction_ids = tuple(
            sorted(item for item in contradicted if item in record_by_id)
        )
        superseded_ids = tuple(
            sorted(item for item in superseded if item in record_by_id)
        )
        supporting_ids = tuple(
            record_id
            for record_id in member_ids
            if record_id not in contradicted and record_id not in superseded
        )

        representative = max(members, key=self._representative_rank)
        keys = self._retrieval_keys(members)
        confidence = self._cluster_confidence(members, token_map)

        return ConsolidationProposal(
            proposal_id=_stable_id("consolidation", member_ids),
            method_version=self.policy.method_version,
            created_at=created_at,
            memory_class=representative.memory_class,
            canonical_statement=representative.statement.strip(),
            scope=dict(representative.scope),
            member_ids=member_ids,
            supporting_ids=supporting_ids,
            contradicting_ids=contradiction_ids,
            superseded_ids=superseded_ids,
            retrieval_keys=keys,
            clustering_confidence=round(confidence, 6),
            scope_contract_id=self.policy.scope_compatibility.contract_id,
        )

    @staticmethod
    def _representative_rank(record: MemoryRecord) -> tuple[int, int, int, str, str]:
        status_rank = 0 if record.status in {"retired", "rejected"} else 1
        authority_rank = {
            "advisory": 0,
            "repository-local": 1,
            "governed-evaluation": 2,
            "protected": 3,
        }.get(record.authority_class, 0)
        return (
            status_rank,
            authority_rank,
            len(record.source_ids),
            record.created_at,
            record.record_id,
        )

    def _retrieval_keys(self, records: Sequence[MemoryRecord]) -> tuple[str, ...]:
        counts: Counter[str] = Counter()
        for record in records:
            counts.update(_tokens(record.statement))
            counts.update(tag.casefold() for tag in record.tags)
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return tuple(token for token, _ in ordered[: self.policy.retrieval_key_count])

    @staticmethod
    def _cluster_confidence(
        records: Sequence[MemoryRecord],
        token_map: dict[str, frozenset[str]],
    ) -> float:
        if len(records) < 2:
            return 0.0
        similarities: list[float] = []
        for index, left in enumerate(records):
            for right in records[index + 1 :]:
                similarities.append(
                    _jaccard(token_map[left.record_id], token_map[right.record_id])
                )
        return sum(similarities) / len(similarities)


class RetrievalLayoutPlanner:
    """Suggest record co-location from observed access patterns.

    This planner changes no source record and performs no physical write. It
    emits rebuildable layout buckets that a future storage adapter may choose to
    use for pages, shards, caches, graph entry points, or prefetch groups.
    """

    def plan(
        self,
        events: Iterable[AccessEvent],
        *,
        minimum_coaccess: int = 2,
    ) -> tuple[RetrievalBucket, ...]:
        if minimum_coaccess < 1:
            raise ValueError("minimum_coaccess must be positive")

        weights: Counter[tuple[str, str]] = Counter()
        all_ids: set[str] = set()
        for event in events:
            chosen = tuple(sorted(set(event.selected_ids or event.retrieved_ids)))
            all_ids.update(chosen)
            for index, left in enumerate(chosen):
                for right in chosen[index + 1 :]:
                    weights[(left, right)] += 1

        eligible = {
            edge: weight for edge, weight in weights.items() if weight >= minimum_coaccess
        }
        if not eligible:
            return ()

        forest = _UnionFind(all_ids)
        for left, right in eligible:
            forest.union(left, right)

        components: dict[str, set[str]] = defaultdict(set)
        for record_id in all_ids:
            components[forest.find(record_id)].add(record_id)

        buckets: list[RetrievalBucket] = []
        for members in components.values():
            if len(members) < 2:
                continue
            member_ids = tuple(sorted(members))
            member_set = set(member_ids)
            edges = tuple(
                sorted(
                    (left, right, weight)
                    for (left, right), weight in eligible.items()
                    if left in member_set and right in member_set
                )
            )
            buckets.append(
                RetrievalBucket(
                    bucket_id=_stable_id("retrieval-bucket", member_ids),
                    member_ids=member_ids,
                    weighted_edges=edges,
                )
            )
        return tuple(sorted(buckets, key=lambda bucket: bucket.bucket_id))
