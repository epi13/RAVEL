from __future__ import annotations

from pathlib import Path
import unittest

from ravel.providers import EvidenceRequest, ForgeAdapter, ForgeCliProvider


ROOT = Path(__file__).resolve().parents[1]
FORGE = ROOT.parent / "mncs-forge-mcp/.venv/bin/mncs-forge"
FORGE_CONFIG = ROOT.parent / "mncs-forge-mcp/examples/minimal/mncs-forge.toml"


class ForgeIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(FORGE.is_file() and FORGE_CONFIG.is_file(), "local Forge checkout unavailable")
    def test_actual_forge_inventory_and_lifecycle_rejection(self) -> None:
        provider = ForgeCliProvider(executable=str(FORGE), config=FORGE_CONFIG)
        inventory = provider.verifier_inventory()
        self.assertGreaterEqual(len(inventory.get("verifiers", [])), 1)
        receipt = ForgeAdapter((provider,)).request(
            EvidenceRequest(
                "ravel-forge-integration-request",
                "ravel-0.6-candidate-001",
                "sha256:" + "a" * 64,
                "ravel-development-contract/0.6",
                "python.bounded-add-equivalence",
                "does the declared bounded verifier exist?",
                "diagnostic",
            )
        )
        # The minimal Forge project has no active candidate. Its lifecycle
        # rejection is an actual Forge observation and must remain UNKNOWN.
        self.assertEqual(receipt.status, "UNKNOWN")
        self.assertEqual(receipt.raw.provider_id, provider.provider_id)


if __name__ == "__main__":
    unittest.main()
