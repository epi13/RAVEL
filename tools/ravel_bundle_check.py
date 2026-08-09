#!/usr/bin/env python3
"""Forge workflow helper for one bounded, development-only MNCS bundle."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from ravel.mncs_bundles import build_execution_bundle, verify_execution_bundle


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="ravel-bundle-") as directory:
        work = Path(directory)
        source_root = work / "source"
        source_root.mkdir()
        (source_root / "fixture.txt").write_text("ravel development fixture\n", encoding="utf-8")
        manifest = work / "bundle-source.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "0.1-experimental",
                    "record_type": "mncs-execution-bundle-source",
                    "bundle_id": "ravel-development-representative",
                    "entries": [{"path": "fixture.txt", "source": "fixture.txt", "role": "fixture", "mode": "0644"}],
                    "entrypoints": [{"name": "fixture", "path": "fixture.txt"}],
                    "runtime_requirements": [],
                    "policy_references": [],
                    "limits": {"max_file_count": 8, "max_file_bytes": 4096, "max_total_bytes": 8192, "max_path_bytes": 128, "max_expansion_ratio": 20},
                    "extensions": {"ravel:purpose": "development-only representative verification"},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        archive = work / "ravel-development-bundle.zip"
        built = build_execution_bundle(manifest, source_root, archive)
        checked = verify_execution_bundle(archive, expected_logical_identity=built.logical_identity) if built.status == "PASS" else built
        status = "PASS" if built.status == "PASS" and checked.status == "PASS" else checked.status
        print(json.dumps({"status": status, "bundle": built.__dict__ if hasattr(built, "__dict__") else {"reason_code": built.reason_code}, "verified": checked.reason_code}, sort_keys=True))
        return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
