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
            ROOT / "src/ravel/generated/verification_plan.py",
            ROOT / "family-semantic-contracts-v1.json",
        )
        self.assertEqual(rendered, (ROOT / "family-provider-metadata-v1.json").read_text(encoding="utf-8"))

    def test_changed_binding_identity_changes_generated_provider_fact(self) -> None:
        binding = (ROOT / "src/ravel/generated/verification_plan.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="ravel-provider-facts-") as directory:
            path = Path(directory) / "verification_plan.py"
            path.write_text(
                binding.replace(
                    "INTERFACE_IDENTITY = '31c958b74518d2d4341b510e15dfd35c8f767bc2ae5ea159abc516a095e0e406'",
                    "INTERFACE_IDENTITY = '41c958b74518d2d4341b510e15dfd35c8f767bc2ae5ea159abc516a095e0e406'",
                ),
                encoding="utf-8",
            )
            changed = generator.render(path, ROOT / "family-semantic-contracts-v1.json")
        self.assertNotEqual(changed, (ROOT / "family-provider-metadata-v1.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
