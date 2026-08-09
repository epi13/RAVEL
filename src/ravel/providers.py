"""Narrow RAVEL-to-Forge provider boundary.

Forge remains the evidence executor and governing system. RAVEL can discover a
provider and submit a request, but it cannot rewrite raw observations or turn a
missing capability into PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
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


class ForgeCliProvider:
    """Optional adapter for the installed MNCS Forge JSON CLI.

    Forge remains the executor and record authority.  This class only invokes
    its documented read/invoke operations and carries the returned envelope as
    raw observations.  A missing executable, malformed response, lifecycle
    rejection, or provider failure is represented as ``UNKNOWN``.
    """

    provider_id = "mncs-forge-cli/0.1"

    def __init__(
        self,
        *,
        executable: str = "mncs-forge",
        config: Path | None = None,
        runner: object = subprocess.run,
    ) -> None:
        self.executable = executable
        self.config = config
        self._runner = runner

    def _invoke(self, arguments: tuple[str, ...]) -> tuple[int, object, str]:
        executable = shutil.which(self.executable) or self.executable
        argv = [executable]
        if self.config is not None:
            argv.extend(["--config", str(self.config)])
        argv.extend(["--json", *arguments])
        try:
            completed = self._runner(
                argv,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            return 127, {}, type(error).__name__
        stdout = getattr(completed, "stdout", "")
        stderr = getattr(completed, "stderr", "")
        try:
            value = json.loads(stdout)
        except (TypeError, json.JSONDecodeError):
            value = {}
        return int(getattr(completed, "returncode", 1)), value, stderr[-4096:]

    def inspect(self) -> Mapping[str, object]:
        status, value, _ = self._invoke(("inspect",))
        return value if status == 0 and isinstance(value, Mapping) else {}

    def provider_inventory(self) -> Mapping[str, object]:
        status, value, _ = self._invoke(("providers", "list"))
        return value if status == 0 and isinstance(value, Mapping) else {}

    def verifier_inventory(self) -> Mapping[str, object]:
        status, value, _ = self._invoke(("verifier", "list"))
        return value if status == 0 and isinstance(value, Mapping) else {}

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        inventory = self.verifier_inventory()
        values = inventory.get("verifiers") if isinstance(inventory, Mapping) else None
        if not isinstance(values, list):
            return ()
        capabilities: list[ProviderCapability] = []
        for value in values:
            if not isinstance(value, Mapping):
                continue
            verifier_id = value.get("verifier_id")
            version = value.get("version")
            provider_id = value.get("provider_id")
            if not all(isinstance(item, str) and item for item in (verifier_id, version, provider_id)):
                continue
            capabilities.append(
                ProviderCapability(
                    provider_id=self.provider_id,
                    operation=verifier_id,
                    version=version,
                    deterministic=True,
                    witness_kind="diagnostic",
                )
            )
        return tuple(sorted(capabilities, key=lambda item: (item.operation, item.version)))

    def execute(self, request: EvidenceRequest) -> RawEvidence:
        parameters = {
            "question": request.question,
            "artifact_digest": request.artifact_digest,
            "witness_kind": request.witness_kind,
            "resource_budget": dict(request.resource_budget),
            "timeout_seconds": request.timeout_seconds,
        }
        arguments = (
            "verifier",
            "run",
            request.verifier_contract,
            "--candidate",
            request.candidate_id,
            "--changed",
            request.artifact_digest,
            "--contract",
            request.governing_contract,
            "--parameters",
            json.dumps(parameters, sort_keys=True, separators=(",", ":")),
        )
        status, value, diagnostics = self._invoke(arguments)
        observations = value if isinstance(value, Mapping) else {}
        raw_status = observations.get("status") if isinstance(observations, Mapping) else None
        if raw_status not in {"PASS", "FAIL", "UNKNOWN"}:
            raw_status = "UNKNOWN"
        artifact_digests = [request.artifact_digest]
        if isinstance(observations, Mapping):
            reported = observations.get("artifact_digests")
            if isinstance(reported, list) and all(isinstance(item, str) for item in reported):
                artifact_digests.extend(reported)
        limitations = [
            "RAVEL carries Forge observations; Forge and the governing evaluator retain authority.",
        ]
        if status != 0:
            limitations.append("Forge returned a nonzero command status or lifecycle rejection.")
        return RawEvidence(
            request_id=request.request_id,
            provider_id=self.provider_id,
            raw_status=raw_status,
            observations=observations,
            witness_digest=(
                observations.get("output_identity")
                if isinstance(observations, Mapping)
                and isinstance(observations.get("output_identity"), str)
                else None
            ),
            artifact_digests=tuple(dict.fromkeys(artifact_digests)),
            environment_id=(
                observations.get("environment_id", "forge-unknown")
                if isinstance(observations, Mapping)
                else "forge-unknown"
            ),
            resource_observations=(
                observations.get("resources", {})
                if isinstance(observations, Mapping)
                and isinstance(observations.get("resources", {}), Mapping)
                else {}
            ),
            limitations=tuple(limitations),
            diagnostics=diagnostics,
        )


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
