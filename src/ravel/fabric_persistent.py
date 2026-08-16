"""Persistent-controller RAVEL integration for MNCS Fabric.

This adapter is intentionally a Fabric *consumer*. It never loads worker
endpoints, TLS keys, TrustStore state, registry files, or bundle-cache paths.
Those remain owned by the persistent Fabric controller.

The module coexists with :mod:`ravel.fabric`'s historical local/network
reference backends so old evidence remains reproducible while live experiments
can use Fabric's current public consumer boundary.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fabric import (
    DEVELOPMENT_AUTHORITY,
    MAX_OUTPUT_BYTES,
    MAX_REPLICAS,
    FabricError,
    FabricExecutionObservation,
    FabricQuestion,
    FabricReferenceResult,
    FabricUnavailableError,
    FabricWorkload,
    _aggregate,
    _identity,
    _task_source,
    _write_bundle_source_manifest,
)
from .mncs_bundles import BundleResult, build_execution_bundle
from .siblings import ensure_sibling_src

PERSISTENT_CONFIG_SCHEMA = "ravel-fabric-persistent-config/0.1"
PERSISTENT_SUBMISSION_SCHEMA = "ravel-fabric-persistent-submission/0.1"


@dataclass(frozen=True, slots=True)
class FabricPersistentConfig:
    """Consumer-only connection data for the controller-owned service socket."""

    socket_path: Path
    client_identity: str = "ravel"
    timeout: float = 5.0

    def __post_init__(self) -> None:
        if not str(self.socket_path):
            raise FabricError("persistent Fabric socket_path is required")
        if not self.socket_path.is_absolute():
            raise FabricError("persistent Fabric socket_path must be absolute")
        if not self.client_identity or len(self.client_identity) > 128 or "\x00" in self.client_identity:
            raise FabricError("persistent Fabric client_identity must be bounded text")
        if self.timeout <= 0 or self.timeout > 300:
            raise FabricError("persistent Fabric timeout must be within (0, 300] seconds")

    @classmethod
    def default(cls) -> FabricPersistentConfig:
        """Use the controller's standard per-user state location without owning it."""

        state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        return cls(socket_path=state_root / "mncs-fabric" / "controller.sock")

    @classmethod
    def load(cls, path: str | Path) -> FabricPersistentConfig:
        """Load a deliberately narrow config that cannot smuggle worker trust state."""

        candidate = Path(path)
        try:
            value = tomllib.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise FabricUnavailableError(
                f"persistent Fabric config unavailable: {type(error).__name__}"
            ) from error

        if set(value) != {"fabric"} or not isinstance(value.get("fabric"), dict):
            raise FabricError("persistent Fabric config must contain only a [fabric] table")
        fabric = value["fabric"]
        allowed = {"mode", "socket_path", "client_identity", "timeout"}
        unknown = set(fabric) - allowed
        if unknown:
            raise FabricError(
                "persistent Fabric config contains controller-owned fields: "
                + ", ".join(sorted(unknown))
            )
        if fabric.get("mode") != "persistent-controller":
            raise FabricError("persistent Fabric mode must be persistent-controller")
        socket_path = fabric.get("socket_path")
        if not isinstance(socket_path, str) or not socket_path:
            raise FabricError("persistent Fabric socket_path must be non-empty text")
        client_identity = fabric.get("client_identity", "ravel")
        timeout = fabric.get("timeout", 5.0)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise FabricError("persistent Fabric timeout must be numeric")
        return cls(
            socket_path=Path(socket_path).expanduser(),
            client_identity=str(client_identity),
            timeout=float(timeout),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PERSISTENT_CONFIG_SCHEMA,
            "mode": "persistent-controller",
            "socket_path": str(self.socket_path),
            "client_identity": self.client_identity,
            "timeout": self.timeout,
            "authority": "consumer-only",
        }


@dataclass(frozen=True, slots=True)
class FabricPersistentSubmission:
    """Detached Fabric work retained by RAVEL as provenance, not authority."""

    workload: FabricWorkload
    work_id: str
    accepted_state: str
    provider_identity: str
    plan: Mapping[str, Any]
    manifest: Mapping[str, Any]
    bundle_identity: str
    bundle_archive_identity: str | None
    archive_path: Path
    request_identity: str
    accepted: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.work_id or not self.accepted_state:
            raise FabricError("persistent submission requires Fabric work identity and state")
        if not self.request_identity.startswith("sha256:"):
            raise FabricError("persistent submission request identity is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PERSISTENT_SUBMISSION_SCHEMA,
            "workload": self.workload.to_dict(),
            "work_id": self.work_id,
            "accepted_state": self.accepted_state,
            "provider_identity": self.provider_identity,
            "plan": dict(self.plan),
            "manifest": dict(self.manifest),
            "bundle_identity": self.bundle_identity,
            "bundle_archive_identity": self.bundle_archive_identity,
            "archive_path": str(self.archive_path),
            "request_identity": self.request_identity,
            "accepted": dict(self.accepted),
            "authority": DEVELOPMENT_AUTHORITY,
            "semantics": "detached Fabric work reference; not evaluator authority",
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FabricPersistentSubmission:
        if value.get("schema") != PERSISTENT_SUBMISSION_SCHEMA:
            raise FabricError("unsupported persistent submission schema")
        workload_value = value.get("workload")
        if not isinstance(workload_value, Mapping):
            raise FabricError("persistent submission workload is missing")
        workload = FabricWorkload(
            candidate_identity=str(workload_value["candidate_identity"]),
            experiment_identity=str(workload_value["experiment_identity"]),
            question_kind=str(workload_value["question_kind"]),
            bundle_identity=str(workload_value["bundle_identity"]),
            fabric_manifest_identity=str(workload_value["fabric_manifest_identity"]),
            required_capabilities=tuple(workload_value.get("required_capabilities", ("python",))),
            resource_budget=dict(workload_value.get("resource_budget", {})),
            replication_count=int(workload_value.get("replication_count", 1)),
            provider_identity=workload_value.get("provider_identity"),
            expected_output_kind=str(workload_value.get("expected_output_kind", "diagnostic-observation")),
            partition_identity=str(workload_value.get("partition_identity")),
            forge_workflow_identity=str(workload_value.get("forge_workflow_identity")),
            visibility=str(workload_value.get("visibility")),
            authority=str(workload_value.get("authority")),
        )
        expected_workload_identity = workload_value.get("workload_identity")
        if expected_workload_identity is not None and expected_workload_identity != workload.workload_identity:
            raise FabricError("persistent submission workload identity does not verify")
        manifest = value.get("manifest")
        plan = value.get("plan")
        accepted = value.get("accepted")
        if not isinstance(manifest, Mapping) or not isinstance(plan, Mapping):
            raise FabricError("persistent submission plan or manifest is missing")
        return cls(
            workload=workload,
            work_id=str(value["work_id"]),
            accepted_state=str(value["accepted_state"]),
            provider_identity=str(value["provider_identity"]),
            plan=dict(plan),
            manifest=dict(manifest),
            bundle_identity=str(value["bundle_identity"]),
            bundle_archive_identity=(
                str(value["bundle_archive_identity"])
                if value.get("bundle_archive_identity") is not None
                else None
            ),
            archive_path=Path(str(value["archive_path"])),
            request_identity=str(value["request_identity"]),
            accepted=dict(accepted) if isinstance(accepted, Mapping) else {},
        )


class FabricPersistentBackend:
    """Use FabricClient against the persistent controller-owned service boundary."""

    backend_identity = "ravel-fabric-persistent-consumer/0.1"

    def __init__(
        self,
        workspace: str | Path,
        config: FabricPersistentConfig,
        *,
        client: Any | None = None,
        consumer_context_type: type | None = None,
        build_manifest_fn: Any | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.submission_root = self.workspace / "fabric-submissions"
        self.submission_root.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.available = False
        self.unavailable_reason: str | None = None

        if client is not None and consumer_context_type is not None and build_manifest_fn is not None:
            self._client = client
            self._ConsumerContext = consumer_context_type
            self._build_manifest = build_manifest_fn
            self.available = True
            return

        ensure_sibling_src("mncs-fabric", "mncs_validator")
        try:
            from mncs_fabric import ConsumerContext, FabricClient
            from mncs_fabric.artifacts import build_manifest
        except ImportError as error:
            self.unavailable_reason = f"mncs-fabric unavailable: {type(error).__name__}"
            return
        try:
            self._client = FabricClient.connect(
                config.socket_path,
                client_identity=config.client_identity,
                timeout=config.timeout,
            )
        except Exception as error:  # noqa: BLE001
            self.unavailable_reason = (
                f"persistent Fabric controller unavailable: {type(error).__name__}"
            )
            return

        self._ConsumerContext = ConsumerContext
        self._build_manifest = build_manifest
        self.available = True

    def _require(self) -> None:
        if not self.available:
            raise FabricUnavailableError(
                self.unavailable_reason or "persistent Fabric controller is unavailable"
            )

    def close(self) -> None:
        if self.available and hasattr(self._client, "close"):
            self._client.close()
        self.available = False
        self.unavailable_reason = "persistent Fabric backend is closed"

    def _submission_path(self, work_id: str) -> Path:
        digest = _identity({"fabric_work_id": work_id})[7:]
        return self.submission_root / f"{digest}.json"

    def _persist_submission(self, submission: FabricPersistentSubmission) -> None:
        path = self._submission_path(submission.work_id)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(submission.to_dict(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)

    def submissions(self) -> tuple[FabricPersistentSubmission, ...]:
        """Load all locally retained detached-work references, failing closed on corruption."""

        items: list[FabricPersistentSubmission] = []
        for path in sorted(self.submission_root.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                submission = FabricPersistentSubmission.from_dict(value)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise FabricError(
                    f"persistent submission metadata is corrupt: {path.name}: {type(error).__name__}"
                ) from error
            if self._submission_path(submission.work_id).name != path.name:
                raise FabricError("persistent submission filename does not bind its work identity")
            items.append(submission)
        return tuple(items)

    def load_submission(self, work_id: str) -> FabricPersistentSubmission:
        path = self._submission_path(work_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise FabricUnavailableError(
                f"persistent submission metadata unavailable: {type(error).__name__}"
            ) from error
        submission = FabricPersistentSubmission.from_dict(value)
        if submission.work_id != work_id:
            raise FabricError("persistent submission work identity does not match filename")
        return submission

    def contract(self) -> Mapping[str, Any]:
        self._require()
        contract = getattr(self._client, "contract", None)
        if contract is None:
            return {
                "outcome": "UNKNOWN",
                "reason": "fabric_public_contract_unavailable",
            }
        return dict(contract())

    @staticmethod
    def artifact_required_capabilities() -> tuple[str, ...]:
        """Bind precompiled candidate artifacts to the platform that produced them."""

        system = platform.system().lower()
        machine = platform.machine().lower()
        os_capability = {
            "linux": "os:linux",
            "windows": "os:windows",
            "darwin": "os:darwin",
        }.get(system, f"os:{system or 'unknown'}")
        architecture = machine or "unknown"
        return ("python", os_capability, f"arch:{architecture}")

    def health(self) -> Mapping[str, Any]:
        """Return a bounded live-readiness view from Fabric's public consumer surface."""

        self._require()
        controller_status: Mapping[str, Any] = {}
        controller_doctor: Mapping[str, Any] = {}
        status_fn = getattr(self._client, "controller_status", None)
        doctor_fn = getattr(self._client, "controller_doctor", None)
        if status_fn is not None:
            controller_status = dict(status_fn())
        if doctor_fn is not None:
            controller_doctor = dict(doctor_fn())
        required = set(self.artifact_required_capabilities())
        workers = self.workers()
        summaries = []
        eligible = []
        for worker in workers:
            capabilities = {str(item) for item in worker.get("capabilities", ())}
            summary = {
                "worker_id": worker.get("worker_id") or worker.get("worker_identity"),
                "availability": worker.get("availability", "UNKNOWN"),
                "available": bool(worker.get("available", False)),
                "capabilities": sorted(capabilities),
                "capability_inventory_status": worker.get("capability_inventory_status", "UNKNOWN"),
            }
            summaries.append(summary)
            if summary["available"] and required.issubset(capabilities):
                eligible.append(summary["worker_id"])
        checks = controller_doctor.get("checks", {}) if isinstance(controller_doctor, Mapping) else {}
        controller_ok = not checks or all(
            value in {"PASS", "CONTROLLER_MANAGED_ENDPOINTS", "NOT_CONFIGURED", "LOCAL_OPERATOR_SOCKET"}
            for value in checks.values()
        )
        return {
            "schema": "ravel-fabric-persistent-health/0.1",
            "backend": self.backend_identity,
            "outcome": "PASS" if controller_ok and eligible else "UNKNOWN",
            "controller_id": controller_status.get("controller_id"),
            "fabric_version": controller_status.get("fabric_version"),
            "configured": controller_status.get("configured"),
            "required_capabilities": sorted(required),
            "eligible_workers": eligible,
            "workers": summaries,
            "controller_checks": dict(checks) if isinstance(checks, Mapping) else {},
            "authority": "consumer-only",
            "semantics": "live readiness only; not evaluator or conformance authority",
        }

    def workers(self) -> list[dict[str, Any]]:
        """Return controller-observed fleet state without reading worker secrets."""

        self._require()
        return [dict(item) for item in self._client.workers()]

    def capabilities(self, worker_label: str) -> Mapping[str, Any]:
        self._require()
        for worker in self.workers():
            identity = worker.get("worker_id") or worker.get("worker_identity")
            if identity == worker_label:
                return worker
        return {
            "worker_identity": worker_label,
            "availability": "UNKNOWN",
            "capabilities": [],
            "reason": "worker_not_visible_through_persistent_controller",
        }

    def reconcile(self, records: list[Mapping[str, Any]]) -> Mapping[str, Any]:
        """Do not recreate Fabric reconciliation in the consumer process."""

        self._require()
        return {
            "outcome": "UNKNOWN",
            "scope": "persistent-controller",
            "independence": "UNKNOWN",
            "records": len(records),
            "reason": "fabric_reconciliation_not_exposed_on_public_persistent_boundary",
            "semantics": "RAVEL refuses to synthesize Fabric-owned reconciliation",
        }

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

    def _make_artifact(
        self, provider: str, root: Path
    ) -> tuple[Path, dict[str, Any], BundleResult, Path]:
        artifact = root / "artifact"
        artifact.mkdir(parents=True, exist_ok=True)
        build_record = self._build_provider(provider, root / "build")
        build_root = root / "build"
        for source, target in (
            (build_root / "ravel_0_6_candidate_001", artifact / "candidate-separate"),
            (build_root / "ravel_0_6_candidate_001.unity", artifact / "candidate-unity"),
        ):
            shutil.copyfile(source, target)
            target.chmod(
                target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
        (artifact / "build-record.json").write_text(
            json.dumps(build_record, sort_keys=True), encoding="utf-8"
        )
        (artifact / "fabric_task.py").write_text(
            _task_source(provider), encoding="utf-8"
        )
        manifest = self._build_manifest(artifact)
        source_manifest = root / "mncs-source-manifest.json"
        _write_bundle_source_manifest(artifact, source_manifest)
        archive = root / "ravel-execution-bundle.zip"
        bundle = build_execution_bundle(source_manifest, artifact, archive)
        if (
            bundle.status != "PASS"
            or bundle.logical_identity is None
            or bundle.archive_identity is None
        ):
            raise FabricUnavailableError(
                "MNCS execution bundle could not be built for persistent Fabric: "
                + bundle.reason_code
            )
        return artifact, manifest, bundle, archive

    @staticmethod
    def _plan(workload: FabricWorkload) -> dict[str, Any]:
        return {
            "schema_version": "mncs-fabric.job-plan.v0.1",
            "job_id": "ravel-fabric-" + workload.workload_identity[7:31],
            "candidate_identity": workload.candidate_binding_identity,
            "artifact_manifest_identity": workload.fabric_manifest_identity,
            "argv": ["@python", "fabric_task.py"],
            "working_directory": ".",
            "timeout_seconds": float(
                workload.resource_budget.get("wall_seconds", 60)
            ),
            "output_limit_bytes": int(
                workload.resource_budget.get("output_bytes", MAX_OUTPUT_BYTES)
            ),
            "environment": {"PYTHONHASHSEED": "0"},
            "required_capabilities": list(workload.required_capabilities),
            "result_paths": ["fabric-result.json"],
            "network_policy": "DECLARED_OFFLINE",
        }

    def _workload(
        self,
        provider: str,
        *,
        candidate_identity: str,
        replication_count: int,
        manifest: Mapping[str, Any],
        bundle: BundleResult,
    ) -> FabricWorkload:
        experiment_identity = _identity(
            {
                "candidate_identity": candidate_identity,
                "provider": provider,
                "question": FabricQuestion.PROVIDER_PARITY,
            }
        )
        return FabricWorkload(
            candidate_identity=candidate_identity,
            experiment_identity=experiment_identity,
            question_kind=FabricQuestion.PROVIDER_PARITY,
            bundle_identity=str(bundle.logical_identity),
            fabric_manifest_identity=str(manifest["manifest_identity"]),
            required_capabilities=self.artifact_required_capabilities(),
            replication_count=replication_count,
            provider_identity=f"ravel-toy-{provider}-c/1",
        )

    def _consumer_context(self, workload: FabricWorkload) -> Any:
        """Translate RAVEL labels into Fabric's opaque sha256 provenance fields."""

        return self._ConsumerContext(
            source_project="RAVEL",
            consumer_workload_identity=workload.workload_identity,
            experiment_identity=workload.experiment_identity,
            forge_workflow_identity=_identity(
                {"forge_workflow_identity": workload.forge_workflow_identity}
            ),
            provider_identity=(
                _identity({"provider_identity": workload.provider_identity})
                if workload.provider_identity is not None
                else None
            ),
            partition_identity=_identity(
                {"partition_identity": workload.partition_identity}
            ),
        )

    def _prepare(
        self,
        provider: str,
        *,
        candidate_identity: str,
        replication_count: int,
    ) -> tuple[FabricWorkload, dict[str, Any], dict[str, Any], BundleResult, Path]:
        self._require()
        if provider not in {"branching", "ring"}:
            raise FabricError("provider must be branching or ring")
        if replication_count < 1 or replication_count > MAX_REPLICAS:
            raise FabricError("replication_count is outside the bounded range")
        root = self.workspace / provider
        root.mkdir(parents=True, exist_ok=True)
        _artifact, manifest, bundle, archive = self._make_artifact(provider, root)
        workload = self._workload(
            provider,
            candidate_identity=candidate_identity,
            replication_count=replication_count,
            manifest=manifest,
            bundle=bundle,
        )
        return workload, self._plan(workload), manifest, bundle, archive

    def submit_provider_parity(
        self,
        provider: str,
        *,
        candidate_identity: str = "ravel-0.6-candidate-001",
        replication_count: int = 2,
        model: str | None = None,
        role: str | None = "ravel-development",
    ) -> FabricPersistentSubmission:
        """Submit detached work; Fabric owns placement, transfer, and execution."""

        workload, plan, manifest, bundle, archive = self._prepare(
            provider,
            candidate_identity=candidate_identity,
            replication_count=replication_count,
        )
        request_identity = _identity(
            {
                "backend": self.backend_identity,
                "workload_identity": workload.workload_identity,
                "operation": "execution.submit",
            }
        )
        accepted = self._client.submit_execution(
            plan,
            manifest,
            replicas=replication_count,
            request_id=request_identity,
            idempotency_key=workload.workload_identity,
            consumer_context=self._consumer_context(workload),
            execution_bundle_archive=archive,
            model=model,
            role=role,
        )
        work_id = accepted.get("work_id")
        state = accepted.get("state", "UNKNOWN")
        if not isinstance(work_id, str) or not work_id:
            raise FabricError("persistent Fabric submission returned no work identity")
        submission = FabricPersistentSubmission(
            workload=workload,
            work_id=work_id,
            accepted_state=str(state),
            provider_identity=provider,
            plan=plan,
            manifest=manifest,
            bundle_identity=str(bundle.logical_identity),
            bundle_archive_identity=bundle.archive_identity,
            archive_path=archive,
            request_identity=request_identity,
            accepted=dict(accepted),
        )
        self._persist_submission(submission)
        return submission

    def execution_status(self, submission: FabricPersistentSubmission | str) -> Mapping[str, Any]:
        self._require()
        work_id = submission.work_id if isinstance(submission, FabricPersistentSubmission) else submission
        return dict(self._client.execution_status(work_id))

    def collect_work_id(self, work_id: str) -> FabricReferenceResult:
        """Recover persisted RAVEL provenance after a client/process restart."""

        return self.collect_submission(self.load_submission(work_id))

    def collect_submission(
        self, submission: FabricPersistentSubmission
    ) -> FabricReferenceResult:
        """Collect completed detached work without turning Fabric state into a verdict."""

        self._require()
        payload = dict(self._client.execution_result(submission.work_id))
        container = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        results = container.get("results", []) if isinstance(container, dict) else []
        if not isinstance(results, list):
            results = []
        return self._report(
            submission.workload,
            submission.provider_identity,
            submission.bundle_identity,
            submission.bundle_archive_identity,
            [dict(item) for item in results if isinstance(item, Mapping)],
            detached_work_id=submission.work_id,
        )

    def execute_provider_parity(
        self,
        provider: str,
        *,
        candidate_identity: str = "ravel-0.6-candidate-001",
        replication_count: int = 2,
    ) -> FabricReferenceResult:
        """Execute through FabricClient; long plans may detach inside FabricClient."""

        workload, plan, manifest, bundle, archive = self._prepare(
            provider,
            candidate_identity=candidate_identity,
            replication_count=replication_count,
        )
        request_identity = _identity(
            {
                "backend": self.backend_identity,
                "workload_identity": workload.workload_identity,
                "operation": "execution.execute",
            }
        )
        results = self._client.execute(
            plan,
            manifest,
            replicas=replication_count,
            request_id=request_identity,
            consumer_context=self._consumer_context(workload),
            execution_bundle_archive=archive,
        )
        return self._report(
            workload,
            provider,
            str(bundle.logical_identity),
            bundle.archive_identity,
            [dict(item) for item in results if isinstance(item, Mapping)],
        )

    def _report(
        self,
        workload: FabricWorkload,
        provider: str,
        bundle_identity: str,
        bundle_archive_identity: str | None,
        results: list[Mapping[str, Any]],
        *,
        detached_work_id: str | None = None,
    ) -> FabricReferenceResult:
        observations: list[FabricExecutionObservation] = []
        records: list[Mapping[str, Any]] = []
        statuses: list[str] = []

        for result in results:
            record = result.get("record") if isinstance(result.get("record"), Mapping) else {}
            receipt = result.get("receipt") if isinstance(result.get("receipt"), Mapping) else {}
            observed_manifest = record.get("artifact_manifest_identity")
            if observed_manifest is not None and observed_manifest != workload.fabric_manifest_identity:
                raise FabricError("persistent Fabric result does not bind the submitted manifest")
            observed_bundle = result.get("bundle_identity")
            if observed_bundle is not None and observed_bundle != bundle_identity:
                raise FabricError("persistent Fabric result does not bind the submitted bundle")
            records.append(record)
            raw_status = record.get("outcome", "UNKNOWN")
            status = raw_status if raw_status in {"PASS", "FAIL", "UNKNOWN"} else "UNKNOWN"
            statuses.append(status)

            result_identities = tuple(
                item["sha256"]
                for item in record.get("results", [])
                if isinstance(item, Mapping) and isinstance(item.get("sha256"), str)
            )
            node = record.get("node") if isinstance(record.get("node"), Mapping) else {}
            reason = record.get("termination_reason") or result.get("reason") or result.get("disposition") or "UNKNOWN"
            resources: dict[str, Any] = {
                "duration_ms": record.get("duration_ms"),
                "node_fingerprint": node.get("node_fingerprint"),
                "persistent_controller": True,
            }
            for key in (
                "placement_admission",
                "resource_snapshot",
                "runtime_observation",
                "runtime_binding",
                "runtime_capability_observation",
                "runtime_capability_binding",
                "provenance_binding",
            ):
                if isinstance(result.get(key), Mapping):
                    resources[key] = dict(result[key])
            if detached_work_id is not None:
                resources["fabric_work_id"] = detached_work_id

            observations.append(
                FabricExecutionObservation(
                    workload_identity=workload.workload_identity,
                    candidate_identity=workload.candidate_identity,
                    candidate_binding_identity=workload.candidate_binding_identity,
                    worker_identity=result.get("worker_identity") or node.get("machine_label"),
                    request_identity=result.get("request_identity"),
                    fabric_record_identity=result.get("record_identity") or record.get("record_id"),
                    fabric_manifest_identity=record.get("artifact_manifest_identity")
                    or workload.fabric_manifest_identity,
                    bundle_identity=result.get("bundle_identity") or bundle_identity,
                    bundle_archive_identity=bundle_archive_identity,
                    receipt_identity=result.get("receipt_identity") or receipt.get("receipt_identity"),
                    challenge_identity=result.get("challenge_identity"),
                    replay_identity=None,
                    provider_identity=provider,
                    result_identities=result_identities,
                    fabric_outcome=status,
                    reason_codes=(str(reason),),
                    resource_observations=resources,
                )
            )

        aggregate = _aggregate(statuses) if statuses else "UNKNOWN"
        reconciliation = self.reconcile(records)
        return FabricReferenceResult(
            workload=workload,
            observations=tuple(observations),
            reconciliation=reconciliation,
            bundle={
                "mncs_status": "PASS",
                "verified": "PASS",
                "logical_identity": bundle_identity,
                "archive_identity": bundle_archive_identity,
                "pre_staged": "NOT_REQUIRED",
                "transport": "fabric-controller-owned-native-bundle-transfer",
                "executed": aggregate,
                "official_receipt_binding": "UNKNOWN",
            },
            replay={
                "status": "UNKNOWN",
                "scope": "persistent-controller",
                "reason": "challenge_replay_not_requested_by_this_adapter",
            },
            negative_cases={
                "status": "UNKNOWN",
                "scope": "persistent-controller",
                "reason": "legacy_local_negative_matrix_not_replayed_automatically",
            },
            fabric_status=aggregate,
            limitations=(
                "Fabric owns worker placement, endpoint trust, bundle transport, and raw execution evidence.",
                "RAVEL does not synthesize persistent-controller reconciliation.",
                "Persistent execution evidence is development-only and does not grant evaluator or promotion authority.",
                "Legacy local/network backends remain available for historical compatibility and negative-matrix reproduction.",
            ),
        )


__all__ = [
    "PERSISTENT_CONFIG_SCHEMA",
    "PERSISTENT_SUBMISSION_SCHEMA",
    "FabricPersistentBackend",
    "FabricPersistentConfig",
    "FabricPersistentSubmission",
]
