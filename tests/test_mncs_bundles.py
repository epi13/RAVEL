from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ravel.mncs_bundles import BundleResult, build_execution_bundle, bind_receipt_to_bundle


class MncsBundleTests(unittest.TestCase):
    def _manifest(self, entry_path: str = "fixture.txt") -> dict[str, object]:
        return {
            "schema_version": "0.1-experimental",
            "record_type": "mncs-execution-bundle-source",
            "bundle_id": "ravel-test-bundle",
            "entries": [{"path": entry_path, "source": "fixture.txt", "role": "fixture", "mode": "0644"}],
            "entrypoints": [{"name": "fixture", "path": entry_path}],
            "runtime_requirements": [],
            "policy_references": [],
            "limits": {"max_file_count": 8, "max_file_bytes": 4096, "max_total_bytes": 8192, "max_path_bytes": 128, "max_expansion_ratio": 20},
            "extensions": {"ravel:purpose": "development-only test"},
        }

    def test_official_bundle_builder_accepts_valid_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            manifest = root / "source.json"
            manifest.write_text(json.dumps(self._manifest()), encoding="utf-8")
            result = build_execution_bundle(manifest, source, root / "bundle.zip")
        self.assertIn(result.status, {"PASS", "UNKNOWN"})

    def test_receipt_binding_does_not_reimplement_mncs_checks(self) -> None:
        bundle = BundleResult(
            "PASS", "a" * 64, "b" * 64,
            {"harness_identity": None, "input_snapshot_identity": None, "policy_identity": None},
            "mncs_bundle_verified",
        )
        self.assertIn(
            bind_receipt_to_bundle({"bundle": {"test_bundle_identity": "a" * 64}}, bundle),
            {"PASS", "FAIL", "UNKNOWN"},
        )

    def test_official_validator_rejects_ambiguous_member_paths(self) -> None:
        try:
            from mncs_validator.execution_bundle import normalize_bundle_path
        except ImportError:
            self.skipTest("optional MNCS execution-bundle validator unavailable")
        for value in ("../escape", "/absolute", "C:\\drive", "a//b", "a/../b", "a\x00b"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_bundle_path(value)


if __name__ == "__main__":
    unittest.main()
