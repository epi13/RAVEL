"""Scoped execution experience records for advisory RAVEL memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .memory import MemoryClass, MemoryRecord


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    candidate_id: str
    context_identity: str
    task_environment: str
    requested_strategy: str
    provider_id: str
    verifier_id: str
    raw_result: Mapping[str, Any]
    formal_disposition: str | None = None
    adaptation_decision: str | None = None
    rejection_reason: str | None = None
    checkpoint_before: str | None = None
    checkpoint_after: str | None = None
    resource_observations: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, str] = field(default_factory=dict)
    applicability_scope: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.context_identity or not self.task_environment:
            raise ValueError("candidate, context, and task identities are required")
        if self.formal_disposition not in {None, "PASS", "FAIL", "UNKNOWN"}:
            raise ValueError("formal disposition must be PASS, FAIL, UNKNOWN, or absent")

    @property
    def negative(self) -> bool:
        return self.formal_disposition in {"FAIL", "UNKNOWN"} or self.adaptation_decision == "rejected"

    @property
    def record_id(self) -> str:
        return f"experience:{self.candidate_id}:{self.context_identity}"

    def to_memory_record(self, *, created_at: str) -> MemoryRecord:
        scope = dict(self.applicability_scope)
        scope.update({"candidate": self.candidate_id, "context": self.context_identity})
        statement = (
            f"{self.requested_strategy} on {self.task_environment} returned "
            f"{self.formal_disposition or 'unadjudicated'} via {self.provider_id}."
        )
        relations = {"contradicts": ()} if self.negative else {}
        return MemoryRecord(
            record_id=self.record_id,
            memory_class=MemoryClass.NEGATIVE if self.negative else MemoryClass.EPISODIC,
            statement=statement,
            scope=scope,
            created_at=created_at,
            producer_id="ravel-experience",
            authority_class="advisory",
            tags=(self.task_environment, self.requested_strategy, self.verifier_id),
            relations=relations,
            metadata={
                "raw_result": dict(self.raw_result),
                "adaptation_decision": self.adaptation_decision,
                "rejection_reason": self.rejection_reason,
                "resource_observations": dict(self.resource_observations),
            },
            evidence_identity=self.provenance.get("evidence_identity"),
            experience_identity=self.record_id,
        )
