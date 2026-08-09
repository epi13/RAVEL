"""Scoped execution experience records for advisory RAVEL memory."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
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
    execution_identity: str | None = None

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
        suffix = f":{self.execution_identity}" if self.execution_identity else ""
        return f"experience:{self.candidate_id}:{self.context_identity}{suffix}"

    @classmethod
    def from_development_transaction(
        cls,
        *,
        candidate_id: str,
        context_identity: str,
        task_environment: str,
        provider_id: str,
        transaction: Mapping[str, Any],
        matched_compute: Mapping[str, Any] | None = None,
        partition_identity: str = "ravel-0.6-development-adaptation-v1",
        provenance: Mapping[str, str] | None = None,
    ) -> "ExperienceRecord":
        """Convert raw C development output into advisory, fail-closed memory."""

        committed = transaction.get("committed")
        if not isinstance(committed, bool):
            raise ValueError("development transaction committed flag is malformed")
        raw_result: dict[str, Any] = {"transaction": dict(transaction)}
        if matched_compute is not None:
            raw_result["matched_compute"] = dict(matched_compute)
        material = json.dumps(raw_result, sort_keys=True, separators=(",", ":")).encode()
        execution_identity = hashlib.sha256(material).hexdigest()[:24]
        return cls(
            candidate_id=candidate_id,
            context_identity=context_identity,
            task_environment=task_environment,
            requested_strategy="retention-constrained-adaptation",
            provider_id=provider_id,
            verifier_id="development-raw-observation",
            raw_result=raw_result,
            formal_disposition="UNKNOWN",
            adaptation_decision="accepted" if committed else "rejected",
            rejection_reason=transaction.get("rejection_reason") if not committed else None,
            provenance=dict(provenance or {}),
            applicability_scope={"partition": partition_identity},
            execution_identity=execution_identity,
        )

    @classmethod
    def from_fabric_observation(
        cls,
        observation: Mapping[str, Any],
        *,
        partition_identity: str = "ravel-0.6-development-adaptation-v1",
    ) -> "ExperienceRecord":
        """Retain a Fabric observation by reference, never as evaluator authority.

        Fabric owns the immutable execution record and receipt.  RAVEL stores only
        their identities and a scoped diagnostic interpretation; a Fabric PASS is
        deliberately represented as ``UNKNOWN`` here until a RAVEL evaluator
        answers the question it owns.
        """

        required = ("candidate_identity", "workload_identity", "fabric_outcome")
        if any(not isinstance(observation.get(key), str) for key in required):
            raise ValueError("Fabric observation identity or outcome is malformed")
        candidate_id = str(observation["candidate_identity"])
        workload_identity = str(observation["workload_identity"])
        provider_id = str(observation.get("provider_identity") or "unknown-provider")
        references = {
            key: value
            for key in (
                "workload_identity",
                "candidate_binding_identity",
                "request_identity",
                "worker_identity",
                "fabric_record_identity",
                "receipt_identity",
                "bundle_identity",
                "bundle_archive_identity",
                "fabric_manifest_identity",
                "challenge_identity",
                "replay_identity",
            )
            if isinstance(value := observation.get(key), str)
        }
        raw_result = {
            "fabric_reference": references,
            "fabric_outcome": observation["fabric_outcome"],
            "reason_codes": list(observation.get("reason_codes", ())),
            "semantics": "development observation; not evaluator authority",
        }
        return cls(
            candidate_id=candidate_id,
            context_identity=workload_identity,
            task_environment="mncs-fabric",
            requested_strategy="fabric-development-execution",
            provider_id=provider_id,
            verifier_id="fabric-execution-observation",
            raw_result=raw_result,
            formal_disposition="UNKNOWN",
            resource_observations=dict(observation.get("resource_observations", {})),
            provenance={
                "fabric_record_identity": references.get("fabric_record_identity", ""),
                "receipt_identity": references.get("receipt_identity", ""),
                "bundle_identity": references.get("bundle_identity", ""),
            },
            applicability_scope={
                "partition": partition_identity,
                "visibility": "development-visible",
                "authority": "development-only",
                "worker": references.get("worker_identity", "unknown"),
            },
            execution_identity=(
                references.get("receipt_identity")
                or references.get("fabric_record_identity")
                or workload_identity
            ),
        )

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
