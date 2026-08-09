from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from ravel.experience import ExperienceRecord
from ravel.fabric import (
    FabricError,
    FabricLocalBackend,
    FabricQuestion,
    FabricUnavailableError,
    FabricWorkload,
    FabricNetworkConfig,
)
from ravel.memory import MemoryClass
from ravel.memory.store import SQLiteMemoryStore


class FabricContractTests(unittest.TestCase):
    def test_workload_is_development_only_and_binds_candidate(self) -> None:
        workload = FabricWorkload(
            candidate_identity="ravel-0.6-candidate-001",
            experiment_identity="sha256:" + "1" * 64,
            question_kind=FabricQuestion.PROVIDER_PARITY,
            bundle_identity="sha256:" + "2" * 64,
            fabric_manifest_identity="sha256:" + "3" * 64,
        )
        self.assertEqual(workload.to_dict()["visibility"], "development-visible")
        self.assertEqual(workload.to_dict()["authority"], "development-only")
        self.assertNotEqual(workload.workload_identity, workload.candidate_binding_identity)
        with self.assertRaises(FabricError):
            FabricWorkload(
                candidate_identity="ravel-0.6-candidate-001",
                experiment_identity="sha256:" + "1" * 64,
                question_kind=FabricQuestion.PROVIDER_PARITY,
                bundle_identity="sha256:" + "2" * 64,
                fabric_manifest_identity="sha256:" + "3" * 64,
                visibility="selection-visible",
            )

    def test_missing_required_fabric_identity_is_rejected(self) -> None:
        with self.assertRaises(FabricError):
            FabricWorkload(
                candidate_identity="ravel-0.6-candidate-001",
                experiment_identity="not-an-identity",
                question_kind=FabricQuestion.PROVIDER_PARITY,
                bundle_identity="sha256:" + "2" * 64,
                fabric_manifest_identity="sha256:" + "3" * 64,
            )

    def test_network_template_never_falls_back_without_operator_trust(self) -> None:
        with self.assertRaises(FabricUnavailableError):
            FabricNetworkConfig.load("config/ravel-fabric.example.toml")


class FabricLocalReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="ravel-test-fabric-")
        self.backend = FabricLocalBackend(Path(self.directory.name))
        if not self.backend.available:
            self.skipTest(self.backend.unavailable_reason or "mncs-fabric unavailable")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_branching_local_replication_replay_and_negative_matrix(self) -> None:
        report = self.backend.execute_provider_parity("branching")
        self.assertEqual(report.fabric_status, "PASS")
        self.assertEqual(report.bundle["mncs_status"], "PASS")
        self.assertEqual(report.bundle["verified"], "PASS")
        self.assertEqual(report.bundle["pre_staged"], "PASS")
        self.assertEqual(report.bundle["executed"], "UNKNOWN")
        self.assertEqual(report.bundle["official_receipt_binding"], "UNKNOWN")
        self.assertEqual(report.bundle["receipt_binding_probe"]["status"], "FAIL")
        self.assertEqual(len(report.bundle["receipt_binding_probe"]["results"]), 2)
        self.assertEqual(report.reconciliation["outcome"], "PASS")
        self.assertEqual(report.reconciliation["scope"], "local-in-process-replication")
        self.assertEqual(report.reconciliation["independence"], "UNKNOWN")
        self.assertEqual(len(report.observations), 2)
        self.assertTrue(all(item.fabric_outcome == "PASS" for item in report.observations))
        self.assertTrue(all(item.challenge_identity for item in report.observations))
        self.assertTrue(all(item.replay_identity for item in report.observations))
        self.assertTrue(all(item.bundle_identity == report.bundle["logical_identity"] for item in report.observations))
        self.assertTrue(all(item.semantics.endswith("not evaluator authority") for item in report.observations))
        self.assertEqual(report.replay["results"][0]["first"], "PASS")
        self.assertEqual(report.replay["results"][0]["duplicate"], "FAIL")
        self.assertEqual(report.negative_cases["duplicate_request"], "DUPLICATE_IDEMPOTENT")
        self.assertEqual(report.negative_cases["conflicting_replay"], "CONFLICTING_REPLAY")
        self.assertEqual(report.negative_cases["capability_mismatch"]["outcome"], "UNKNOWN")
        self.assertEqual(report.negative_cases["wrong_manifest"]["outcome"], "FAIL")
        self.assertEqual(report.negative_cases["corrupt_record_identity"]["outcome"], "FAIL")
        try:
            import jsonschema
        except ImportError:
            jsonschema = None
        if jsonschema is not None:
            schema = json.loads(
                Path("ravel_versions/0.6/ravel-0.6-fabric-observation.schema.json").read_text()
            )
            jsonschema.validate(
                {"schema": "ravel-fabric-reference-run/0.1", "status": report.fabric_status,
                 "authority": "development-only", "semantics": "reference", "providers": [report.to_dict()]},
                schema,
            )

    def test_ring_local_replication_has_same_contract(self) -> None:
        report = self.backend.execute_provider_parity("ring")
        self.assertEqual(report.fabric_status, "PASS")
        self.assertEqual(report.reconciliation["outcome"], "PASS")
        self.assertTrue(all(item.provider_identity == "ring" for item in report.observations))
        self.assertTrue(all(item.candidate_binding_identity == report.workload.candidate_binding_identity for item in report.observations))

    def test_fabric_observation_enters_memory_as_scoped_unknown(self) -> None:
        report = self.backend.execute_provider_parity("branching", replication_count=1)
        experience = ExperienceRecord.from_fabric_observation(report.observations[0].to_dict())
        self.assertEqual(experience.formal_disposition, "UNKNOWN")
        self.assertEqual(experience.task_environment, "mncs-fabric")
        self.assertEqual(experience.raw_result["fabric_reference"]["bundle_identity"], report.bundle["logical_identity"])
        self.assertNotIn("record", experience.raw_result)
        with tempfile.TemporaryDirectory(prefix="ravel-test-memory-") as directory:
            with SQLiteMemoryStore(f"{directory}/memory.sqlite") as store:
                store.insert_records_atomic((experience.to_memory_record(created_at="2026-08-09T00:00:00Z"),))
                records = store.search_records("fabric development execution")
                self.assertEqual(len(records), 1)
                self.assertIs(records[0][0].memory_class, MemoryClass.NEGATIVE)


if __name__ == "__main__":
    unittest.main()
