from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ravel.fabric import FabricQuestion, FabricReferenceResult, FabricWorkload
from ravel.fabric_agent import FabricAgent, _execution_state
from ravel.fabric_persistent import FabricPersistentSubmission


class _Backend:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.items: list[FabricPersistentSubmission] = []
        self.submitted: list[str] = []
        self.closed = False

    def health(self):
        return {"outcome": "PASS", "eligible_workers": ["fabric-worker-01"]}

    def submissions(self):
        return tuple(self.items)

    def submit_provider_parity(self, provider: str, *, replication_count: int):
        self.submitted.append(provider)
        workload = FabricWorkload(
            candidate_identity="ravel-0.6-candidate-001",
            experiment_identity="sha256:" + "1" * 64,
            question_kind=FabricQuestion.PROVIDER_PARITY,
            bundle_identity="sha256:" + "2" * 64,
            fabric_manifest_identity="sha256:" + "3" * 64,
            required_capabilities=("python", "os:linux", "arch:x86_64"),
            replication_count=replication_count,
            provider_identity=f"ravel-toy-{provider}-c/1",
        )
        item = FabricPersistentSubmission(
            workload=workload,
            work_id=f"work-{provider}",
            accepted_state="QUEUED",
            provider_identity=provider,
            plan={"schema_version": "mncs-fabric.job-plan.v0.1"},
            manifest={"manifest_identity": "sha256:" + "3" * 64},
            bundle_identity="sha256:" + "2" * 64,
            bundle_archive_identity="sha256:" + "4" * 64,
            archive_path=self.root / f"{provider}.zip",
            request_identity="sha256:" + ("5" if provider == "branching" else "6") * 64,
        )
        self.items.append(item)
        return item

    def execution_status(self, submission):
        return {"state": "COMPLETED"}

    def collect_submission(self, submission):
        return FabricReferenceResult(
            workload=submission.workload,
            observations=(),
            reconciliation={"outcome": "UNKNOWN"},
            bundle={"executed": "PASS"},
            replay={"status": "UNKNOWN"},
            negative_cases={"status": "UNKNOWN"},
            fabric_status="PASS",
            limitations=(),
        )

    def close(self):
        self.closed = True


class FabricAgentTests(unittest.TestCase):
    def test_execution_state_handles_nested_result(self) -> None:
        self.assertEqual(_execution_state({"result": {"state": "completed"}}), "COMPLETED")
        self.assertEqual(_execution_state({}), "UNKNOWN")

    def test_bootstrap_is_idempotent_and_collects_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ravel-agent-") as directory:
            root = Path(directory)
            backend = _Backend(root)
            agent = FabricAgent(backend, root, replication_count=1)
            first = agent.tick(bootstrap=True)
            self.assertEqual(backend.submitted, ["branching", "ring"])
            self.assertEqual(len(first["bootstrap_submissions"]), 2)
            self.assertEqual(len(list((root / "fabric-reports").glob("*.json"))), 2)
            second = agent.tick(bootstrap=True)
            self.assertEqual(backend.submitted, ["branching", "ring"])
            self.assertEqual(second["bootstrap_submissions"], [])
            heartbeat = json.loads((root / "agent-heartbeat.json").read_text())
            self.assertEqual(heartbeat["schema"], "ravel-fabric-agent-state/0.1")
            self.assertEqual(len(heartbeat["submissions"]), 2)


if __name__ == "__main__":
    unittest.main()
