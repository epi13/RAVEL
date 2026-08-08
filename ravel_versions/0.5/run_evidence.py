#!/usr/bin/env python3
"""Run preserved 0.5 tooling with historical logical-path compatibility."""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path
from typing import Any

CASE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = CASE_ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

import ravel_0_5_evidence as evidence  # noqa: E402
import ravel_0_5_source_digest as source_digest  # noqa: E402

source_digest.CASE_ROOT = CASE_ROOT
source_digest.REPOSITORY_ROOT = REPOSITORY_ROOT
evidence.CASE_ROOT = CASE_ROOT
evidence.TOOL_ROOT = REPOSITORY_ROOT / "tools"
for name in (
    "PREREGISTRATION",
    "MANIFEST_SPEC",
    "RAW",
    "TRIAL",
    "NEGATIVE",
    "MANIFEST",
    "ASSURANCE",
    "RESULTS",
    "RUNTIME",
):
    setattr(evidence, name, CASE_ROOT / getattr(evidence, name).name)
evidence.PACKAGE_PATHS = (
    evidence.RAW,
    evidence.TRIAL,
    evidence.NEGATIVE,
    evidence.MANIFEST,
    evidence.ASSURANCE,
    evidence.RESULTS,
)


def physical_path(logical: str, repository_root: Path) -> Path | None:
    """Resolve a historical manifest path without changing its logical spelling."""

    if logical == "Makefile" and repository_root == REPOSITORY_ROOT:
        return None
    direct = repository_root / logical
    if direct.is_file():
        return direct
    prefix = "case-studies/ravel/"
    if logical.startswith(prefix):
        relative = logical.removeprefix(prefix)
        candidate = (
            REPOSITORY_ROOT / "tools" / relative.removeprefix("tools/")
            if relative.startswith("tools/")
            else CASE_ROOT / relative
        )
        return candidate if candidate.is_file() else None
    return direct if direct.is_file() else None


def compat_build_manifest(
    spec_path: Path, repository_root: Path | None = None
) -> dict[str, Any]:
    root = REPOSITORY_ROOT if repository_root is None else repository_root
    spec = source_digest.load_json(spec_path)
    source_digest.validate_spec(spec)
    declared = set(spec["generated_execution_shards"]) | set(
        spec["maintained_execution_sources"]
    )
    discovered: set[str] = set()
    for pattern in spec.get("execution_source_discovery_globs", []):
        prefix = "case-studies/ravel/"
        if pattern.startswith(prefix):
            for path in CASE_ROOT.glob(pattern.removeprefix(prefix)):
                if path.is_file():
                    discovered.add(prefix + path.relative_to(CASE_ROOT).as_posix())
        else:
            for path in root.glob(pattern):
                if path.is_file():
                    discovered.add(path.relative_to(root).as_posix())
    unexpected = sorted(discovered - declared)
    omitted = sorted(declared - discovered)
    if unexpected:
        raise source_digest.ManifestError(
            f"unexpected execution shard outside manifest: {unexpected}"
        )
    if omitted:
        raise source_digest.ManifestError(
            f"declared execution shard is missing: {omitted}"
        )

    entries: list[dict[str, Any]] = []
    for item in spec["ordered_files"]:
        logical = item["path"]
        absolute = physical_path(logical, root)
        if absolute is None:
            raise source_digest.ManifestError(
                f"listed source file is missing: {logical}"
            )
        content = absolute.read_bytes()
        entries.append(
            {
                "order": len(entries),
                "role": item["role"],
                "path": logical,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    digest = hashlib.sha256()
    for entry in entries:
        logical_bytes = entry["path"].encode("utf-8")
        content_path = physical_path(entry["path"], root)
        assert content_path is not None
        content = content_path.read_bytes()
        digest.update(struct.pack(">I", len(logical_bytes)))
        digest.update(logical_bytes)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return {
        "schema": "ravel-source-and-execution-manifest/0.5",
        "entrypoint": spec["entrypoint"],
        "maintained_execution_sources": spec["maintained_execution_sources"],
        "generated_execution_shards": spec["generated_execution_shards"],
        "generator_source": None,
        "source_provenance": spec["source_provenance"],
        "build_configuration": spec["build_configuration"],
        "checkpoint_schema": spec["checkpoint_schema"],
        "evidence_schema_versions": spec["evidence_schema_versions"],
        "digest_algorithm": spec["digest_algorithm"],
        "digest_procedure": spec["digest_procedure"],
        "ordered_files": entries,
        "source_digest": digest.hexdigest(),
        "unexpected_execution_shards": [],
    }


evidence.build_manifest = compat_build_manifest

raise SystemExit(evidence.main())
