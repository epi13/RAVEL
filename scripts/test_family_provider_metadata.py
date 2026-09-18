#!/usr/bin/env python3
"""Determinism and stale-binding tests for Ravel provider metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import generate_family_provider_metadata as generator


ROOT = Path(__file__).resolve().parents[1]


class ProviderMetadataTests(unittest.TestCase):
    def test_checked_in_metadata_is_current(self) -> None:
        rendered = generator.render(
            ROOT / "src/ravel/generated/verification_policy.py",
            ROOT / "family-semantic-contracts-v1.json",
        )
        self.assertEqual(rendered, (ROOT / "family-provider-metadata-v1.json").read_text(encoding="utf-8"))

    def test_changed_binding_identity_changes_generated_provider_fact(self) -> None:
        binding = (ROOT / "src/ravel/generated/verification_policy.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="ravel-provider-facts-") as directory:
            path = Path(directory) / "verification_policy.py"
            interface_line = next(
                line for line in binding.splitlines() if line.startswith("INTERFACE_IDENTITY = ")
            )
            path.write_text(
                binding.replace(
                    interface_line,
                    "INTERFACE_IDENTITY = '" + "41" * 32 + "'",
                    1,
                ),
                encoding="utf-8",
            )
            changed = generator.render(path, ROOT / "family-semantic-contracts-v1.json")
        self.assertNotEqual(changed, (ROOT / "family-provider-metadata-v1.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
