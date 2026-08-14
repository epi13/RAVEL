"""Optional RAVEL integration with the public MNCS Fabric boundary.

RAVEL owns the semantic question and its development-only workload identity.
Fabric owns artifact admission, bounded execution, worker placement, raw
execution records, receipts, challenge/replay evidence, and reconciliation.
This module retains Fabric records by identity and never turns Fabric status
into an RAVEL evaluator or promotion decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any, Mapping, Protocol

from .mncs_bundles import BundleResult, build_execution_bundle
from .siblings import ensure_sibling_src


WORKLOAD_SCHEMA = "ravel-fabric-workload/0.1"
OBSERVATION_SCHEMA = "ravel-fabric-observation/0.1"
REFERENCE_SCHEMA = "ravel-fabric-reference-report/0.1"
DEVELOPMENT_PARTITION = "ravel-0.6-development-adaptation-v1"
DEVELOPMENT_VISIBILITY = "development-visible"
DEVELOPMENT_AUTHORITY = "development-only"
MAX_OUTPUT_BYTES = 256 * 1024
MAX_REPLICAS = 8


class FabricError(RuntimeError):
    """A bounded RAVEL/Fabric integration error."""


class FabricUnavailableError(FabricError):
    """The optional public Fabric package or requested capability is absent."""


class FabricQuestion(StrEnum):
    BEHAVIORAL_FIXTURE = "behavioral-fixture"
    PROVIDER_PARITY = "provider-parity"
    CHECKPOINT_INTEGRITY = "checkpoint-integrity"
    NEGATIVE_MUTATION = "negative-mutation"
    COMPILE_PORTABILITY = "compile-portability"
    COMPONENT_PARITY = "component-parity"
    MATCHED_COMPUTE = "matched-compute-observation"
    REPLICATED_EXECUTION = "replicated-execution"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _identity(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _is_identity(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(char in "0123456789abcdef" for char in value[7:])
    )


def _is_external_identity(value: object) -> bool:
    return _is_identity(value) or (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _bounded_text(value: object, label: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise FabricError(f"{label} must be bounded text")
    return value


def _aggregate(statuses: list[str]) -> str:
    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "PASS"


@dataclass(frozen=True, slots=True)
class FabricWorkload:
    """RAVEL's semantic request, distinct from Fabric's JobPlan."""

    candidate_identity: str
    experiment_identity: str
    question_kind: FabricQuestion | str
    bundle_identity: str
    fabric_manifest_identity: str
    required_capabilities: tuple[str, ...] = ("python",)
    resource_budget: Mapping[str, int | float] = field(
        default_factory=lambda: {"wall_seconds": 60, "output_bytes": MAX_OUTPUT_BYTES}
    )
    replication_count: int = 1
    provider_identity: str | None = None
    expected_output_kind: str = "diagnostic-observation"
    partition_identity: str = DEVELOPMENT_PARTITION
    forge_workflow_identity: str = "ravel-forge-fabric-reference/1"
    visibility: str = DEVELOPMENT_VISIBILITY
    authority: str = DEVELOPMENT_AUTHORITY

    def __post_init__(self) -> None:
        _bounded_text(self.candidate_identity, "candidate_identity")
        if not _is_identity(self.experiment_identity):
            raise FabricError("experiment_identity must be a sha256 identity")
        _bounded_text(str(self.question_kind), "question_kind", 96)
        if not _is_external_identity(self.bundle_identity):
            raise FabricError("bundle_identity must be a supported external identity")
        if not _is_identity(self.fabric_manifest_identity):
            raise FabricError("fabric_manifest_identity must be a sha256 identity")
        if not self.required_capabilities or len(set(self.required_capabilities)) != len(
            self.required_capabilities
        ):
            raise FabricError("required capabilities must be non-empty and unique")
        for capability in self.required_capabilities:
            _bounded_text(capability, "required capability", 128)
        if self.replication_count < 1 or self.replication_count > MAX_REPLICAS:
            raise FabricError("replication_count is outside the bounded range")
        if self.visibility != DEVELOPMENT_VISIBILITY:
            raise FabricError("Fabric workloads may expose development-visible material only")
        if self.partition_identity != DEVELOPMENT_PARTITION:
            raise FabricError("Fabric workloads must use the frozen development partition")
        if self.authority != DEVELOPMENT_AUTHORITY:
            raise FabricError("Fabric workloads are development-only")
        _bounded_text(self.expected_output_kind, "expected_output_kind")
        _bounded_text(self.forge_workflow_identity, "forge_workflow_identity")
        for key, value in self.resource_budget.items():
            _bounded_text(key, "resource budget key", 96)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise FabricError("resource budget values must be finite numbers")
            if not math.isfinite(float(value)) or value < 0:
                raise FabricError("resource budget values must be finite and non-negative")
        if self.provider_identity is not None:
            _bounded_text(self.provider_identity, "provider_identity")

    @property
    def candidate_binding_identity(self) -> str:
        return _identity({"ravel_candidate_identity": self.candidate_identity})

    def to_dict(self, *, include_identity: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": WORKLOAD_SCHEMA,
            "candidate_identity": self.candidate_identity,
            "candidate_binding_identity": self.candidate_binding_identity,
            "experiment_identity": self.experiment_identity,
            "question_kind": str(self.question_kind),
            "bundle_identity": self.bundle_identity,
            "fabric_manifest_identity": self.fabric_manifest_identity,
            "required_capabilities": list(self.required_capabilities),
            "resource_budget": dict(self.resource_budget),
            "replication_count": self.replication_count,
            "provider_identity": self.provider_identity,
            "expected_output_kind": self.expected_output_kind,
            "partition_identity": self.partition_identity,
            "forge_workflow_identity": self.forge_workflow_identity,
            "visibility": self.visibility,
            "authority": self.authority,
            "semantics": "RAVEL semantic development request; not a JobPlan, verdict, or promotion input",
        }
        if include_identity:
            value["workload_identity"] = _identity(value)
        return value

    @property
    def workload_identity(self) -> str:
        return self.to_dict(include_identity=False).get("workload_identity") or _identity(
            self.to_dict(include_identity=False)
        )


@dataclass(frozen=True, slots=True)
class FabricExecutionObservation:
    """A RAVEL reference to immutable Fabric evidence."""

    workload_identity: str
    candidate_identity: str
    candidate_binding_identity: str | None
    worker_identity: str | None
    request_identity: str | None
    fabric_record_identity: str | None
    fabric_manifest_identity: str | None
    bundle_identity: str | None
    bundle_archive_identity: str | None
    receipt_identity: str | None
    challenge_identity: str | None
    replay_identity: str | None
    provider_identity: str | None
    result_identities: tuple[str, ...]
    fabric_outcome: str
    reason_codes: tuple[str, ...] = ()
    resource_observations: Mapping[str, Any] = field(default_factory=dict)
    semantics: str = "development observation; not evaluator authority"

    def __post_init__(self) -> None:
        if not _is_identity(self.workload_identity):
            raise FabricError("workload_identity is invalid")
        _bounded_text(self.candidate_identity, "candidate_identity")
        if self.candidate_binding_identity is not None and not _is_identity(
            self.candidate_binding_identity
        ):
            raise FabricError("candidate_binding_identity is invalid")
        if self.fabric_outcome not in {"PASS", "FAIL", "UNKNOWN"}:
            raise FabricError("fabric_outcome must be PASS, FAIL, or UNKNOWN")
        if self.semantics != "development observation; not evaluator authority":
            raise FabricError("Fabric observations cannot claim evaluator authority")
        for label, value in (
            ("fabric_record_identity", self.fabric_record_identity),
            ("fabric_manifest_identity", self.fabric_manifest_identity),
            ("receipt_identity", self.receipt_identity),
            ("challenge_identity", self.challenge_identity),
            ("replay_identity", self.replay_identity),
        ):
            if value is not None and not _is_external_identity(value):
                raise FabricError(f"{label} is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OBSERVATION_SCHEMA,
            "workload_identity": self.workload_identity,
            "candidate_identity": self.candidate_identity,
            "candidate_binding_identity": self.candidate_binding_identity,
            "worker_identity": self.worker_identity,
            "request_identity": self.request_identity,
            "fabric_record_identity": self.fabric_record_identity,
            "fabric_manifest_identity": self.fabric_manifest_identity,
            "bundle_identity": self.bundle_identity,
            "bundle_archive_identity": self.bundle_archive_identity,
            "receipt_identity": self.receipt_identity,
            "challenge_identity": self.challenge_identity,
            "replay_identity": self.replay_identity,
            "provider_identity": self.provider_identity,
            "result_identities": list(self.result_identities),
            "fabric_outcome": self.fabric_outcome,
            "reason_codes": list(self.reason_codes),
            "resource_observations": dict(self.resource_observations),
            "semantics": self.semantics,
        }


@dataclass(frozen=True, slots=True)
class FabricReferenceResult:
    workload: FabricWorkload
    observations: tuple[FabricExecutionObservation, ...]
    reconciliation: Mapping[str, Any]
    bundle: Mapping[str, Any]
    replay: Mapping[str, Any]
    negative_cases: Mapping[str, Any]
    fabric_status: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REFERENCE_SCHEMA,
            "workload": self.workload.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "reconciliation": dict(self.reconciliation),
            "bundle": dict(self.bundle),
            "replay": dict(self.replay),
            "negative_cases": dict(self.negative_cases),
            "fabric_status": self.fabric_status,
            "limitations": list(self.limitations),
            "authority": DEVELOPMENT_AUTHORITY,
            "semantics": "Fabric development reference report; not evaluator authority",
        }


class ExecutionBackend(Protocol):
    def capabilities(self, worker_label: str) -> Mapping[str, Any]: ...

    def execute_provider_parity(
        self,
        provider: str,
        *,
        candidate_identity: str = "ravel-0.6-candidate-001",
        replication_count: int = 2,
    ) -> FabricReferenceResult: ...

    def reconcile(self, records: list[Mapping[str, Any]]) -> Mapping[str, Any]: ...


def _write_bundle_source_manifest(source_root: Path, destination: Path) -> None:
    entries = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source_root).as_posix()
        entries.append({"path": relative, "source": relative, "role": "test", "mode": "0644"})
    value = {
        "schema_version": "0.1-experimental",
        "record_type": "mncs-execution-bundle-source",
        "bundle_id": "ravel-fabric-reference",
        "entries": entries,
        "entrypoints": [{"name": "ravel-fabric-task", "path": "fabric_task.py"}],
        "runtime_requirements": [],
        "policy_references": [],
        "limits": {
            "max_file_count": max(8, len(entries) + 4),
            "max_file_bytes": 8 * 1024 * 1024,
            "max_total_bytes": 64 * 1024 * 1024,
            "max_path_bytes": 512,
            "max_expansion_ratio": 100,
        },
        "extensions": {"ravel:purpose": "development-only Fabric reference"},
    }
    destination.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _task_source(provider: str) -> str:
    return f'''import json
from pathlib import Path
import subprocess

provider = {provider!r}
outputs = {{}}
for label, executable in (("separate", "candidate-separate"), ("unity", "candidate-unity")):
    path = Path(executable)
    path.chmod(path.stat().st_mode | 0o111)
    result = subprocess.run(
        [str(path.resolve()), "--trial", "decomposition", "--regime", "separated_state", "--seed", "0x1234"],
        capture_output=True,
        check=False,
    )
    raw = result.stdout.decode("utf-8", errors="replace")
    outputs[label] = {{"returncode": result.returncode, "stdout": raw}}
    if result.returncode != 0:
        raise SystemExit(result.returncode or 1)
parsed = {{label: json.loads(value["stdout"]) for label, value in outputs.items()}}
parity = outputs["separate"]["stdout"] == outputs["unity"]["stdout"]
result = {{
    "schema": "ravel-fabric-c-trial/0.1",
    "provider_identity": provider,
    "candidate_identity": parsed["separate"].get("candidate_id"),
    "environment_provider_id": parsed["separate"].get("environment_provider_id"),
    "parity": parity,
    "separate": parsed["separate"],
    "unity": parsed["unity"],
}}
Path("fabric-result.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
raise SystemExit(0 if parity else 1)
'''


class FabricLocalBackend:
    """Execute a bounded RAVEL C parity workload via LocalController/Worker."""

    backend_identity = "ravel-fabric-local-public-controller/0.1"

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        ensure_sibling_src("mncs-fabric", "mncs_validator")
        try:
            from mncs_fabric.artifacts import build_manifest
            from mncs_fabric.challenges import ChallengeReplayStore, challenge_for_receipt
            from mncs_fabric.controller import LocalController
            from mncs_fabric.receipts import build_execution_receipt
            from mncs_fabric.service import FabricService
            from mncs_fabric.worker import LocalWorker
        except ImportError as error:
            self.available = False
            self.unavailable_reason = f"mncs-fabric unavailable: {type(error).__name__}"
            return
        self.available = True
        self.unavailable_reason = None
        self._build_manifest = build_manifest
        self._ChallengeReplayStore = ChallengeReplayStore
        self._challenge_for_receipt = challenge_for_receipt
        self._LocalController = LocalController
        self._LocalWorker = LocalWorker
        self._build_receipt = build_execution_receipt
        self._service = FabricService()

    def _require(self) -> None:
        if not self.available:
            raise FabricUnavailableError(self.unavailable_reason or "mncs-fabric is unavailable")

    def capabilities(self, worker_label: str) -> Mapping[str, Any]:
        self._require()
        return self._service.capabilities(worker_label)

    def reconcile(self, records: list[Mapping[str, Any]]) -> Mapping[str, Any]:
        self._require()
        return self._service.reconcile(list(records), require_distinct_nodes=True)

    def _build_provider(self, provider: str, output: Path) -> dict[str, Any]:
        from tools.ravel_0_6_build import build

        prior = os.environ.get("RAVEL06_PROVIDER")
        try:
            os.environ["RAVEL06_PROVIDER"] = provider
            return build(output)
        finally:
            if prior is None:
                os.environ.pop("RAVEL06_PROVIDER", None)
            else:
                os.environ["RAVEL06_PROVIDER"] = prior

    def _make_artifact(self, provider: str, root: Path) -> tuple[Path, dict[str, Any], BundleResult]:
        artifact = root / "artifact"
        artifact.mkdir(parents=True, exist_ok=True)
        build_record = self._build_provider(provider, root / "build")
        build_root = root / "build"
        for source, target in (
            (build_root / "ravel_0_6_candidate_001", artifact / "candidate-separate"),
            (build_root / "ravel_0_6_candidate_001.unity", artifact / "candidate-unity"),
        ):
            shutil.copyfile(source, target)
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        (artifact / "build-record.json").write_text(
            json.dumps(build_record, sort_keys=True), encoding="utf-8"
        )
        (artifact / "fabric_task.py").write_text(_task_source(provider), encoding="utf-8")
        manifest = self._build_manifest(artifact)
        source_manifest = root / "mncs-source-manifest.json"
        _write_bundle_source_manifest(artifact, source_manifest)
        bundle = build_execution_bundle(source_manifest, artifact, root / "ravel-execution-bundle.zip")
        return artifact, manifest, bundle

    def _plan(self, workload: FabricWorkload) -> dict[str, Any]:
        return {
            "schema_version": "mncs-fabric.job-plan.v0.1",
            "job_id": "ravel-fabric-" + workload.workload_identity[7:31],
            "candidate_identity": workload.candidate_binding_identity,
            "artifact_manifest_identity": workload.fabric_manifest_identity,
            "argv": ["@python", "fabric_task.py"],
            "working_directory": ".",
            "timeout_seconds": float(workload.resource_budget.get("wall_seconds", 60)),
            "output_limit_bytes": int(workload.resource_budget.get("output_bytes", MAX_OUTPUT_BYTES)),
            "environment": {"PYTHONHASHSEED": "0"},
            "required_capabilities": list(workload.required_capabilities),
            "result_paths": ["fabric-result.json"],
            "network_policy": "DECLARED_OFFLINE",
        }

    def _receipt_with_challenge(self, record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        base = self._build_receipt(
            record,
            subject_family="RAVEL",
            subject_kind="development-fabric-workload",
            runner_identity="ravel-fabric-local-worker:0.1",
        )
        challenge_report = self._challenge_for_receipt(
            base, issuer_identity="ravel-development-challenge"
        )
        if not challenge_report.valid or challenge_report.challenge is None:
            return base, None
        return (
            self._build_receipt(
                record,
                subject_family="RAVEL",
                subject_kind="development-fabric-workload",
                runner_identity="ravel-fabric-local-worker:0.1",
                challenge=challenge_report.challenge,
            ),
            challenge_report.challenge,
        )

    def execute_provider_parity(
        self,
        provider: str,
        *,
        candidate_identity: str = "ravel-0.6-candidate-001",
        replication_count: int = 2,
    ) -> FabricReferenceResult:
        self._require()
        if provider not in {"branching", "ring"}:
            raise FabricError("provider must be branching or ring")
        if replication_count < 1 or replication_count > MAX_REPLICAS:
            raise FabricError("replication_count is outside the bounded range")
        provider_root = self.workspace / provider
        provider_root.mkdir(parents=True, exist_ok=True)
        artifact, manifest, bundle = self._make_artifact(provider, provider_root)
        bundle_identity = bundle.logical_identity or manifest["manifest_identity"]
        experiment_identity = _identity(
            {"candidate_identity": candidate_identity, "provider": provider, "question": FabricQuestion.PROVIDER_PARITY}
        )
        workload = FabricWorkload(
            candidate_identity=candidate_identity,
            experiment_identity=experiment_identity,
            question_kind=FabricQuestion.PROVIDER_PARITY,
            bundle_identity=bundle_identity,
            fabric_manifest_identity=manifest["manifest_identity"],
            required_capabilities=("python",),
            replication_count=replication_count,
            provider_identity=f"ravel-toy-{provider}-c/1",
        )
        plan = self._plan(workload)
        controller = self._LocalController(
            f"ravel-fabric-controller-{provider}", provider_root / "controller.jsonl"
        )
        workers = []
        for suffix in ("a", "b")[:replication_count]:
            worker = self._LocalWorker(
                f"ravel-{provider}-worker-{suffix}",
                artifact,
                provider_root / f"worker-{suffix}.jsonl",
            )
            controller.register(worker)
            workers.append(worker)
        responses = controller.dispatch(plan, manifest, replicas=replication_count)
        raw_records = [
            response.get("payload", {}).get("record")
            for response in responses
            if response.get("message_type") == "execution.result"
            and isinstance(response.get("payload", {}).get("record"), dict)
        ]
        receipts: list[dict[str, Any]] = []
        challenges: list[dict[str, Any]] = []
        receipt_bindings: list[dict[str, Any]] = []
        observations: list[FabricExecutionObservation] = []
        for response, record in zip(responses, raw_records):
            self._service.verify_record(record)
            receipt, challenge = self._receipt_with_challenge(record)
            receipts.append(receipt)
            try:
                binding = self._service.bind_receipt_to_execution_bundle(
                    receipt, provider_root / "ravel-execution-bundle.zip"
                )
                receipt_bindings.append(
                    {
                        "status": "PASS" if binding.get("valid") else "FAIL",
                        "valid": bool(binding.get("valid")),
                        "issues": list(binding.get("issues", [])),
                    }
                )
            except Exception as error:
                receipt_bindings.append(
                    {"status": "UNKNOWN", "issues": [type(error).__name__]}
                )
            if challenge is not None:
                challenges.append(challenge)
            result_values = record.get("results", [])
            result_ids = tuple(
                value["sha256"]
                for value in result_values
                if isinstance(value, dict) and isinstance(value.get("sha256"), str)
            )
            node = record.get("node") if isinstance(record.get("node"), dict) else {}
            observations.append(
                FabricExecutionObservation(
                    workload_identity=workload.workload_identity,
                    candidate_identity=candidate_identity,
                    candidate_binding_identity=workload.candidate_binding_identity,
                    worker_identity=response.get("worker_id") or node.get("machine_label"),
                    request_identity=response.get("request_id"),
                    fabric_record_identity=record.get("record_id"),
                    fabric_manifest_identity=record.get("artifact_manifest_identity"),
                    bundle_identity=bundle.logical_identity,
                    bundle_archive_identity=bundle.archive_identity,
                    receipt_identity=receipt.get("receipt_identity"),
                    challenge_identity=challenge.get("challenge_identity") if challenge else None,
                    replay_identity=None,
                    provider_identity=provider,
                    result_identities=result_ids,
                    fabric_outcome=record.get("outcome", "UNKNOWN"),
                    reason_codes=(record.get("termination_reason", "UNKNOWN"),),
                    resource_observations={
                        "duration_ms": record.get("duration_ms"),
                        "node_fingerprint": node.get("node_fingerprint"),
                        "capabilities": sorted(self._service.capabilities(str(node.get("machine_label"))).get("capabilities", [])),
                    },
                )
            )
        reconciliation = self._service.reconcile(raw_records, require_distinct_nodes=True) if raw_records else {"outcome": "UNKNOWN", "reasons": ["worker_result_unavailable"]}
        replay_store = self._ChallengeReplayStore(provider_root / "challenge-replay.jsonl")
        replay_results: list[dict[str, Any]] = []
        for challenge, receipt in zip(challenges, receipts):
            first = replay_store.consume(challenge, receipt)
            duplicate = replay_store.consume(challenge, receipt)
            replay_results.append(
                {
                    "challenge_identity": challenge.get("challenge_identity"),
                    "first": first.category,
                    "replay_identity": first.replay_receipt.get("replay_identity") if first.replay_receipt else None,
                    "duplicate": duplicate.category,
                    "duplicate_reasons": list(duplicate.issues),
                }
            )
        duplicate_response = None
        conflict_response = None
        if workers and raw_records:
            worker = workers[0]
            first_response = responses[0]
            request_id = first_response.get("request_id")
            if isinstance(request_id, str):
                from mncs_fabric.transport import InProcessTransport

                duplicate_response = controller.dispatch_via(
                    InProcessTransport(worker), plan, manifest, worker_id=worker.worker_id, request_id=request_id
                )
                changed = dict(plan)
                changed["candidate_identity"] = _identity({"ravel_candidate_identity": "ravel-0.6-candidate-002"})
                conflict_response = controller.dispatch_via(
                    InProcessTransport(worker), changed, manifest, worker_id=worker.worker_id, request_id=request_id
                )
        capability_plan = dict(plan)
        capability_plan["job_id"] = capability_plan["job_id"] + "-capability"
        capability_plan["required_capabilities"] = ["capability:ravel-does-not-provide"]
        capability_record = self._service.execute_local(
            capability_plan, artifact, manifest, f"ravel-{provider}-capability", work_root=provider_root
        )
        wrong_manifest = dict(plan)
        wrong_manifest["job_id"] = wrong_manifest["job_id"] + "-manifest"
        wrong_manifest["artifact_manifest_identity"] = "sha256:" + "f" * 64
        wrong_manifest_record = self._service.execute_local(
            wrong_manifest, artifact, manifest, f"ravel-{provider}-wrong-manifest", work_root=provider_root
        )
        malformed_record = dict(raw_records[0]) if raw_records else {}
        if malformed_record:
            malformed_record["record_id"] = "sha256:" + "0" * 64
        negative_cases = {
            "capability_mismatch": {
                "outcome": capability_record.get("outcome"),
                "reason": capability_record.get("termination_reason"),
            },
            "wrong_manifest": {
                "outcome": wrong_manifest_record.get("outcome"),
                "reason": wrong_manifest_record.get("termination_reason"),
            },
            "duplicate_request": duplicate_response.get("payload", {}).get("disposition") if isinstance(duplicate_response, dict) else "UNKNOWN",
            "conflicting_replay": conflict_response.get("payload", {}).get("disposition") if isinstance(conflict_response, dict) else "UNKNOWN",
            "corrupt_record_identity": self._service.verify_record(malformed_record) if malformed_record else {"outcome": "UNKNOWN"},
        }
        fabric_status = _aggregate(
            [str(item.get("outcome", "UNKNOWN")) for item in [reconciliation] if isinstance(item, Mapping)]
            + [item.fabric_outcome for item in observations]
        )
        observation_replay = {}
        for item, replay in zip(observations, replay_results):
            object.__setattr__(item, "replay_identity", replay.get("replay_identity"))
            observation_replay[item.worker_identity or "unknown"] = replay
        return FabricReferenceResult(
            workload=workload,
            observations=tuple(observations),
            reconciliation={**reconciliation, "scope": "local-in-process-replication", "independence": "UNKNOWN"},
            bundle={
                "mncs_status": bundle.status,
                "logical_identity": bundle.logical_identity,
                "archive_identity": bundle.archive_identity,
                "fabric_manifest_identity": manifest["manifest_identity"],
                "verified": "PASS" if bundle.status == "PASS" else bundle.status,
                "pre_staged": "PASS",
                "executed": "UNKNOWN",
                "official_receipt_binding": "UNKNOWN",
                "receipt_binding_probe": {
                    "status": _aggregate(
                        [str(item.get("status", "UNKNOWN")) for item in receipt_bindings]
                    ) if receipt_bindings else "UNKNOWN",
                    "results": receipt_bindings,
                    "semantics": "probe only; Fabric did not execute the MNCS archive",
                },
                "issues": list(bundle.issues),
            },
            replay={"results": replay_results, "store": "workspace-local-development-ledger"},
            negative_cases=negative_cases,
            fabric_status=fabric_status,
            limitations=(
                "Local logical workers share one controller process and host.",
                "Replication is not independent evaluation or protected custody.",
                "MNCS archive execution is UNKNOWN because Fabric native bundle transfer is not claimed.",
                "Fabric local execution is bounded but not a hostile-code security sandbox.",
            ),
        )


@dataclass(frozen=True, slots=True)
class FabricWorkerEndpoint:
    worker_id: str
    host: str
    port: int
    capabilities: tuple[str, ...]
    ca_file: Path
    client_cert: Path
    client_key: Path
    trust_store: Path


@dataclass(frozen=True, slots=True)
class FabricNetworkConfig:
    controller_id: str
    state_path: Path
    workers: tuple[FabricWorkerEndpoint, ...]
    pre_staged_bundle_identity: str | None = None

    @classmethod
    def load(cls, path: str | Path) -> "FabricNetworkConfig":
        import tomllib

        source = Path(path).resolve(strict=True)
        try:
            raw = tomllib.loads(source.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise FabricError(f"invalid RAVEL Fabric network configuration: {error}") from error
        base = source.parent
        workers = tuple(
            FabricWorkerEndpoint(
                worker_id=str(item["worker_id"]),
                host=str(item["host"]),
                port=int(item["port"]),
                capabilities=tuple(str(value) for value in item["capabilities"]),
                ca_file=(base / str(item["ca_file"])).resolve(),
                client_cert=(base / str(item["client_cert"])).resolve(),
                client_key=(base / str(item["client_key"])).resolve(),
                trust_store=(base / str(item["trust_store"])).resolve(),
            )
            for item in raw.get("workers", [])
        )
        if not raw.get("controller_id") or not workers:
            raise FabricError("network configuration requires controller_id and workers")
        if len({item.worker_id for item in workers}) != len(workers):
            raise FabricError("network workers must have unique identities")
        for worker in workers:
            if not worker.capabilities or not 1 <= worker.port <= 65535:
                raise FabricError("network worker endpoint is incomplete")
            for path_value in (
                worker.ca_file,
                worker.client_cert,
                worker.client_key,
                worker.trust_store,
            ):
                if not path_value.is_file():
                    raise FabricUnavailableError(f"network trust material unavailable: {path_value}")
        bundle = raw.get("pre_staged_bundle_identity")
        if bundle is not None and not _is_external_identity(bundle):
            raise FabricError("pre_staged_bundle_identity is invalid")
        return cls(str(raw["controller_id"]), (base / str(raw.get("state_path", "fabric-controller.jsonl"))).resolve(), workers, bundle)


class FabricNetworkBackend:
    """Optional TLS-only adapter; bundle transfer remains operator-owned."""

    backend_identity = "ravel-fabric-network-public-controller/0.1"

    def __init__(self, config: FabricNetworkConfig) -> None:
        ensure_sibling_src("mncs-fabric", "mncs_validator")
        try:
            from mncs_fabric.controller import NetworkController
            from mncs_fabric.enrollment import TrustStore
            from mncs_fabric.transport import TLSNetworkTransport
        except ImportError as error:
            raise FabricUnavailableError("mncs-fabric network API is unavailable") from error
        self.config = config
        self.controller = NetworkController(config.controller_id, config.state_path)
        for worker in config.workers:
            transport = TLSNetworkTransport(
                worker.host,
                worker.port,
                ca_file=worker.ca_file,
                client_cert=worker.client_cert,
                client_key=worker.client_key,
                expected_worker_id=worker.worker_id,
                trust_store=TrustStore(worker.trust_store),
            )
            self.controller.register_remote(
                worker.worker_id, frozenset(worker.capabilities), transport
            )

    def dispatch(self, plan: Mapping[str, Any], manifest: Mapping[str, Any], *, replicas: int = 1) -> list[dict[str, Any]]:
        expected = self.config.pre_staged_bundle_identity
        if expected is None or expected != manifest.get("manifest_identity"):
            raise FabricUnavailableError(
                "network Fabric requires an explicitly pre-staged matching Fabric manifest"
            )
        return self.controller.dispatch_remote(dict(plan), dict(manifest), replicas=replicas)


__all__ = [
    "DEVELOPMENT_PARTITION",
    "DEVELOPMENT_VISIBILITY",
    "ExecutionBackend",
    "FabricError",
    "FabricExecutionObservation",
    "FabricLocalBackend",
    "FabricNetworkBackend",
    "FabricNetworkConfig",
    "FabricQuestion",
    "FabricReferenceResult",
    "FabricUnavailableError",
    "FabricWorkerEndpoint",
    "FabricWorkload",
]
