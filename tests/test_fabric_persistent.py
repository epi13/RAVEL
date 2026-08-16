from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ravel.fabric import FabricError, FabricQuestion, FabricWorkload
from ravel.fabric_persistent import (
    FabricPersistentBackend,
    FabricPersistentConfig,
    FabricPersistentSubmission,
)


class _Context:
    def __init__(self, **values):
        self.values = values


class PersistentConfigTests(unittest.TestCase):
    def test_config_exposes_only_controller_consumer_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ravel-persistent-config-") as directory:
            path = Path(directory) / "fabric.toml"
            path.write_text(
                """
[fabric]
mode = "persistent-controller"
socket_path = "/run/mncs-fabric/controller.sock"
client_identity = "ravel"
timeout = 7.5
""".strip()
                + "\n",
                encoding="utf-8",
            )
            config = FabricPersistentConfig.load(path)
            self.assertEqual(config.client_identity, "ravel")
            self.assertEqual(config.timeout, 7.5)
            self.assertEqual(config.to_dict()["authority"], "consumer-only")

    def test_config_rejects_worker_credentials_and_endpoints(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ravel-persistent-config-") as directory:
            path = Path(directory) / "fabric.toml"
            path.write_text(
                """
[fabric]
mode = "persistent-controller"
socket_path = "/run/mncs-fabric/controller.sock"
ca_file = "/secret/ca.pem"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(FabricError):
                FabricPersistentConfig.load(path)


class PersistentContractTests(unittest.TestCase):
    def _workload(self) -> FabricWorkload:
        return FabricWorkload(
            candidate_identity="ravel-0.6-candidate-001",
            experiment_identity="sha256:" + "1" * 64,
            question_kind=FabricQuestion.PROVIDER_PARITY,
            bundle_identity="sha256:" + "2" * 64,
            fabric_manifest_identity="sha256:" + "3" * 64,
            provider_identity="ravel-toy-branching-c/1",
        )

    def test_consumer_context_hashes_ravel_labels_into_fabric_provenance(self) -> None:
        backend = FabricPersistentBackend.__new__(FabricPersistentBackend)
        backend._ConsumerContext = _Context
        context = backend._consumer_context(self._workload())
        self.assertEqual(context.values["source_project"], "RAVEL")
        self.assertTrue(context.values["consumer_workload_identity"].startswith("sha256:"))
        self.assertTrue(context.values["forge_workflow_identity"].startswith("sha256:"))
        self.assertTrue(context.values["provider_identity"].startswith("sha256:"))
        self.assertTrue(context.values["partition_identity"].startswith("sha256:"))

    def test_persistent_report_keeps_fabric_status_separate_from_evaluator_authority(self) -> None:
        backend = FabricPersistentBackend.__new__(FabricPersistentBackend)
        backend.available = True
        backend.unavailable_reason = None
        workload = self._workload()
        result = backend._report(
            workload,
            "branching",
            "sha256:" + "2" * 64,
            "sha256:" + "4" * 64,
            [
                {
                    "disposition": "EXECUTED",
                    "worker_identity": "fabric-worker-01",
                    "request_identity": "sha256:" + "5" * 64,
                    "record_identity": "sha256:" + "6" * 64,
                    "receipt_identity": "sha256:" + "7" * 64,
                    "bundle_identity": "sha256:" + "2" * 64,
                    "record": {
                        "record_id": "sha256:" + "6" * 64,
                        "artifact_manifest_identity": "sha256:" + "3" * 64,
                        "outcome": "PASS",
                        "termination_reason": "completed",
                        "results": [{"sha256": "8" * 64}],
                        "node": {
                            "machine_label": "fabric-worker-01",
                            "node_fingerprint": "sha256:" + "9" * 64,
                        },
                    },
                    "receipt": {"receipt_identity": "sha256:" + "7" * 64},
                    "provenance_binding": {"authority": "provenance-only"},
                }
            ],
            detached_work_id="work-123",
        )
        self.assertEqual(result.fabric_status, "PASS")
        self.assertEqual(result.reconciliation["outcome"], "UNKNOWN")
        self.assertEqual(result.bundle["pre_staged"], "NOT_REQUIRED")
        self.assertEqual(
            result.bundle["transport"], "fabric-controller-owned-native-bundle-transfer"
        )
        self.assertEqual(len(result.observations), 1)
        observation = result.observations[0]
        self.assertEqual(observation.fabric_outcome, "PASS")
        self.assertEqual(
            observation.semantics, "development observation; not evaluator authority"
        )
        self.assertEqual(
            observation.resource_observations["fabric_work_id"], "work-123"
        )


    def test_workload_pins_precompiled_artifact_platform(self) -> None:
        backend = FabricPersistentBackend.__new__(FabricPersistentBackend)
        capabilities = backend.artifact_required_capabilities()
        self.assertIn("python", capabilities)
        self.assertTrue(any(item.startswith("os:") for item in capabilities))
        self.assertTrue(any(item.startswith("arch:") for item in capabilities))

    def test_report_rejects_manifest_binding_mismatch(self) -> None:
        backend = FabricPersistentBackend.__new__(FabricPersistentBackend)
        backend.available = True
        backend.unavailable_reason = None
        workload = self._workload()
        with self.assertRaises(FabricError):
            backend._report(
                workload,
                "branching",
                "sha256:" + "2" * 64,
                "sha256:" + "4" * 64,
                [{"record": {"artifact_manifest_identity": "sha256:" + "f" * 64}}],
            )

    def test_submission_round_trip_preserves_workload_identity(self) -> None:
        workload = self._workload()
        submission = FabricPersistentSubmission(
            workload=workload,
            work_id="work-123",
            accepted_state="QUEUED",
            provider_identity="branching",
            plan={"schema_version": "mncs-fabric.job-plan.v0.1"},
            manifest={"manifest_identity": "sha256:" + "3" * 64},
            bundle_identity="sha256:" + "2" * 64,
            bundle_archive_identity="sha256:" + "4" * 64,
            archive_path=Path("/tmp/ravel-execution-bundle.zip"),
            request_identity="sha256:" + "5" * 64,
            accepted={"work_id": "work-123", "state": "QUEUED"},
        )
        restored = FabricPersistentSubmission.from_dict(
            json.loads(json.dumps(submission.to_dict()))
        )
        self.assertEqual(restored.work_id, submission.work_id)
        self.assertEqual(
            restored.workload.workload_identity, submission.workload.workload_identity
        )
        self.assertEqual(restored.bundle_identity, submission.bundle_identity)


if __name__ == "__main__":
    unittest.main()
