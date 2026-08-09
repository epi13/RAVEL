"""Narrow RAVEL-to-Forge provider boundary.

Forge remains the evidence executor and governing system. RAVEL can discover a
provider and submit a request, but it cannot rewrite raw observations or turn a
missing capability into PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Protocol

EvidenceStatus = Literal["PASS", "FAIL", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider_id: str
    operation: str
    version: str
    deterministic: bool
    witness_kind: str


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    request_id: str
    candidate_id: str
    artifact_digest: str
    governing_contract: str
    verifier_contract: str
    question: str
    witness_kind: str
    resource_budget: Mapping[str, int] = field(default_factory=dict)
    timeout_seconds: int = 0
    determinism_required: bool = True


@dataclass(frozen=True, slots=True)
class RawEvidence:
    request_id: str
    provider_id: str
    raw_status: EvidenceStatus
    observations: Mapping[str, object]
    witness_digest: str | None
    artifact_digests: tuple[str, ...]
    environment_id: str
    resource_observations: Mapping[str, object]
    limitations: tuple[str, ...] = ()
    diagnostics: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    """RAVEL's bounded disposition over immutable raw provider evidence."""

    status: EvidenceStatus
    reason_code: str
    raw: RawEvidence


class ForgeProvider(Protocol):
    provider_id: str

    def capabilities(self) -> tuple[ProviderCapability, ...]: ...

    def execute(self, request: EvidenceRequest) -> RawEvidence: ...


class ForgeAdapter:
    """Capability discovery and fail-closed request handling for Forge-like providers."""

    def __init__(self, providers: tuple[ForgeProvider, ...] = ()) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        values = [capability for provider in self._providers.values() for capability in provider.capabilities()]
        return tuple(sorted(values, key=lambda item: (item.operation, item.provider_id, item.version)))

    def request(self, request: EvidenceRequest) -> EvidenceReceipt:
        matches = [
            (provider, capability)
            for provider in self._providers.values()
            for capability in provider.capabilities()
            if capability.operation == request.verifier_contract
            and capability.witness_kind == request.witness_kind
            and (not request.determinism_required or capability.deterministic)
        ]
        if not matches:
            return EvidenceReceipt(
                status="UNKNOWN",
                reason_code="capability_unavailable",
                raw=RawEvidence(
                    request_id=request.request_id,
                    provider_id="ravel-adapter",
                    raw_status="UNKNOWN",
                    observations={},
                    witness_digest=None,
                    artifact_digests=(request.artifact_digest,),
                    environment_id="unavailable",
                    resource_observations={},
                    limitations=("Required Forge capability was unavailable.",),
                ),
            )
        provider, _ = sorted(matches, key=lambda item: item[0].provider_id)[0]
        try:
            raw = provider.execute(request)
        except Exception as error:  # provider failures are explicit UNKNOWN, not dropped
            raw = RawEvidence(
                request_id=request.request_id,
                provider_id=provider.provider_id,
                raw_status="UNKNOWN",
                observations={},
                witness_digest=None,
                artifact_digests=(request.artifact_digest,),
                environment_id="provider-failure",
                resource_observations={},
                limitations=("Provider execution failed before a governed observation was returned.",),
                diagnostics=type(error).__name__,
            )
        if raw.request_id != request.request_id:
            return EvidenceReceipt("UNKNOWN", "request_identity_mismatch", raw)
        if raw.provider_id != provider.provider_id:
            return EvidenceReceipt("UNKNOWN", "provider_identity_mismatch", raw)
        if raw.raw_status not in {"PASS", "FAIL", "UNKNOWN"}:
            return EvidenceReceipt("UNKNOWN", "malformed_raw_status", raw)
        return EvidenceReceipt(raw.raw_status, "provider_observation", raw)
