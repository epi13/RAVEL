"""Path adapter for the preserved 0.4 manifest protocol."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any


def physical_path(logical: str, case_root: Path, repository_root: Path) -> Path | None:
    candidate = case_root / logical
    if candidate.is_file():
        return candidate
    if logical.startswith("tools/"):
        candidate = repository_root / logical
        return candidate if candidate.is_file() else None
    return None


def build_manifest(
    spec_path: Path, case_root: Path, repository_root: Path, digest_module: Any
) -> dict[str, Any]:
    spec = digest_module.load_json(spec_path)
    digest_module.validate_spec(spec)
    entries: list[dict[str, Any]] = []
    for item in spec["ordered_files"]:
        logical = item["path"]
        absolute = physical_path(logical, case_root, repository_root)
        if absolute is None:
            raise digest_module.ManifestError(f"listed source file is missing: {logical}")
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
    framed = hashlib.sha256()
    for entry in entries:
        logical_bytes = entry["path"].encode("utf-8")
        content_path = physical_path(entry["path"], case_root, repository_root)
        assert content_path is not None
        content = content_path.read_bytes()
        framed.update(struct.pack(">I", len(logical_bytes)))
        framed.update(logical_bytes)
        framed.update(struct.pack(">Q", len(content)))
        framed.update(content)
    return {
        "schema": "ravel-source-manifest/0.4",
        "entrypoint": spec["entrypoint"],
        "generated_execution_shards": spec["generated_execution_shards"],
        "generator_source": None,
        "source_provenance": spec["source_provenance"],
        "evidence_schema_versions": spec["evidence_schema_versions"],
        "digest_algorithm": spec["digest_algorithm"],
        "digest_procedure": spec["digest_procedure"],
        "ordered_files": entries,
        "source_digest": framed.hexdigest(),
        "unexpected_execution_shards": [],
    }
