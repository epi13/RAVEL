from __future__ import annotations

import unittest
import json

from ravel.providers import (
    EvidenceRequest,
    ForgeAdapter,
    ForgeCliProvider,
    ProviderCapability,
    RawEvidence,
)
from ravel.resources import (
    CudaOutOfMemory,
    DevicePolicy,
    OffloadPolicy,
    PlacementDecision,
    ProviderFootprint,
    ResourceSnapshot,
    RuntimePolicy,
    ExecutionExperience,
    choose_placement,
    execute_with_bounded_recovery,
)


class FakeProvider:
    provider_id = "fake-forge"

    def __init__(self, raw: RawEvidence | None = None) -> None:
        self.raw = raw

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        return (ProviderCapability("fake-forge", "compile", "1", True, "diagnostic"),)

    def execute(self, request: EvidenceRequest) -> RawEvidence:
        if self.raw is not None:
            return self.raw
        return RawEvidence(
            request.request_id,
            self.provider_id,
            "FAIL",
            {"exit_status": 1},
            "sha256:witness",
            (request.artifact_digest,),
            "fake-host",
            {},
        )


REQUEST = EvidenceRequest("request:1", "candidate:1", "sha256:artifact", "mncs:v1", "compile", "does it compile?", "diagnostic")


class ProviderTests(unittest.TestCase):
    def test_adapter_preserves_raw_fail(self) -> None:
        receipt = ForgeAdapter((FakeProvider(),)).request(REQUEST)
        self.assertEqual(receipt.status, "FAIL")
        self.assertEqual(receipt.raw.observations["exit_status"], 1)

    def test_missing_capability_is_unknown(self) -> None:
        receipt = ForgeAdapter(()).request(REQUEST)
        self.assertEqual((receipt.status, receipt.reason_code), ("UNKNOWN", "capability_unavailable"))

    def test_cli_adapter_preserves_forge_status_and_identity(self) -> None:
        class Completed:
            returncode = 0
            stdout = json.dumps(
                {
                    "verifiers": [
                        {
                            "verifier_id": "compile",
                            "provider_id": "provider-v1",
                            "version": "1",
                        }
                    ]
                }
            )
            stderr = ""

        class Runner:
            def __call__(self, argv, **kwargs):
                if "run" in argv:
                    Completed.stdout = json.dumps(
                        {"status": "FAIL", "output_identity": "sha256:witness"}
                    )
                return Completed()

        provider = ForgeCliProvider(executable="forge-test", runner=Runner())
        receipt = ForgeAdapter((provider,)).request(REQUEST)
        self.assertEqual(receipt.status, "FAIL")
        self.assertEqual(receipt.raw.provider_id, provider.provider_id)
        self.assertEqual(receipt.raw.witness_digest, "sha256:witness")

    def test_cli_adapter_malformed_or_unavailable_fails_closed(self) -> None:
        class Completed:
            returncode = 0
            stdout = "not-json"
            stderr = "bad response"

        provider = ForgeCliProvider(executable="forge-test", runner=lambda *args, **kwargs: Completed())
        receipt = ForgeAdapter((provider,)).request(REQUEST)
        self.assertEqual(receipt.status, "UNKNOWN")


SNAPSHOT = ResourceSnapshot(True, True, 8_000, 12_000, 64_000, True, 1_000)
FOOTPRINT = ProviderFootprint(10_000, 1_000, 3_000, "bf16")


class ResourceTests(unittest.TestCase):
    def test_execution_experience_keeps_strategy_scope_and_verifier_status(self) -> None:
        experience = ExecutionExperience(
            "provider:1",
            "model:1",
            "toy-task",
            DevicePolicy.CUDA,
            OffloadPolicy.SEQUENTIAL_CPU,
            "bf16",
            8_000,
            123.0,
            "success",
            "UNKNOWN",
            "provider-observation",
        )
        self.assertEqual(experience.verifier_status, "UNKNOWN")
        self.assertEqual(experience.offload, OffloadPolicy.SEQUENTIAL_CPU)

    def test_full_cuda_requires_observed_kernel_and_budget(self) -> None:
        decision = choose_placement(RuntimePolicy(device=DevicePolicy.CUDA), FOOTPRINT, SNAPSHOT)
        self.assertEqual((decision.device, decision.offload), (DevicePolicy.CPU, OffloadPolicy.NONE))

    def test_sequential_offload_records_ram_tradeoff(self) -> None:
        decision = choose_placement(
            RuntimePolicy(device=DevicePolicy.CUDA, offload=OffloadPolicy.SEQUENTIAL_CPU),
            FOOTPRINT,
            SNAPSHOT,
        )
        self.assertEqual((decision.device, decision.offload), (DevicePolicy.CUDA, OffloadPolicy.SEQUENTIAL_CPU))
        self.assertIn("system RAM", decision.total_memory_note)

    def test_oom_recovery_is_bounded(self) -> None:
        class Backend:
            def snapshot(self, dtype: str) -> ResourceSnapshot:
                return ResourceSnapshot(True, True, 20_000, 24_000, 64_000, True, 1_000)

            def execute(self, placement: PlacementDecision, operation):
                if placement.offload == OffloadPolicy.NONE:
                    raise CudaOutOfMemory()
                return "ok"

        result, placement, recovered = execute_with_bounded_recovery(
            Backend(), RuntimePolicy(device=DevicePolicy.CUDA, allow_oom_recovery=True), FOOTPRINT, lambda: None
        )
        self.assertEqual(result, "ok")
        self.assertTrue(recovered)
        self.assertEqual(placement.offload, OffloadPolicy.SEQUENTIAL_CPU)


if __name__ == "__main__":
    unittest.main()
