#!/usr/bin/env python3
"""Build and verify ordered RAVEL source manifests without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

CASE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_ROLES = {
    "entrypoint",
    "contract",
    "scope",
    "preregistration",
    "development_corpus",
    "manifest_specification",
    "threat_model",
    "limitations",
    "postmortem",
    "independent_evaluator",
    "evidence_generator",
    "source_digest_utility",
    "case_build_specification",
    "root_build_specification",
    "ci_workflow",
}


class ManifestError(RuntimeError):
    """Raised when a source manifest is incomplete or stale."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ManifestError(f"{path}: top-level JSON value must be an object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def framed_source_digest(
    entries: list[dict[str, Any]], repository_root: Path = REPOSITORY_ROOT
) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        relative = entry["path"].encode("utf-8")
        content = (repository_root / entry["path"]).read_bytes()
        digest.update(struct.pack(">I", len(relative)))
        digest.update(relative)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return digest.hexdigest()


def validate_spec(spec: dict[str, Any]) -> None:
    ordered = spec.get("ordered_files")
    if not isinstance(ordered, list) or not ordered:
        raise ManifestError("manifest specification has no ordered_files")
    roles: list[str] = []
    paths: list[str] = []
    for index, item in enumerate(ordered):
        if not isinstance(item, dict):
            raise ManifestError(f"ordered_files[{index}] is not an object")
        role = item.get("role")
        path = item.get("path")
        if not isinstance(role, str) or not isinstance(path, str):
            raise ManifestError(f"ordered_files[{index}] lacks string role/path")
        roles.append(role)
        paths.append(path)
    if len(roles) != len(set(roles)):
        raise ManifestError("duplicate ordered manifest role")
    if len(paths) != len(set(paths)):
        raise ManifestError("duplicate ordered manifest path")
    missing_roles = sorted(REQUIRED_ROLES - set(roles))
    if missing_roles:
        raise ManifestError(f"required manifest roles omitted: {missing_roles}")
    if spec.get("entrypoint") not in paths:
        raise ManifestError("entrypoint is omitted from ordered_files")
    maintained = spec.get("maintained_execution_sources")
    if not isinstance(maintained, list) or not maintained:
        raise ManifestError("maintained_execution_sources must be a non-empty array")
    for source in maintained:
        if source not in paths:
            raise ManifestError(f"maintained execution source omitted: {source}")
    generated = spec.get("generated_execution_shards")
    if not isinstance(generated, list):
        raise ManifestError("generated_execution_shards must be an array")
    for shard in generated:
        if shard not in paths:
            raise ManifestError(f"generated shard omitted from ordered_files: {shard}")
    build = spec.get("build_configuration")
    if not isinstance(build, dict):
        raise ManifestError("build_configuration must be an object")
    for name in ("language", "standard", "canonical_compiler", "canonical_flags"):
        if name not in build:
            raise ManifestError(f"build_configuration omits {name}")
    if not isinstance(build["canonical_flags"], list) or not build["canonical_flags"]:
        raise ManifestError("canonical_flags must be a non-empty array")


def discover_execution_shards(
    spec: dict[str, Any], repository_root: Path = REPOSITORY_ROOT
) -> set[str]:
    discovered: set[str] = set()
    globs = spec.get("execution_source_discovery_globs", [])
    if not isinstance(globs, list):
        raise ManifestError("execution_source_discovery_globs must be an array")
    for pattern in globs:
        if not isinstance(pattern, str):
            raise ManifestError("execution shard glob must be a string")
        for path in repository_root.glob(pattern):
            if path.is_file():
                discovered.add(path.relative_to(repository_root).as_posix())
    return discovered


def build_manifest(
    spec_path: Path, repository_root: Path = REPOSITORY_ROOT
) -> dict[str, Any]:
    spec = load_json(spec_path)
    validate_spec(spec)
    declared_shards = set(spec["generated_execution_shards"]) | set(
        spec["maintained_execution_sources"]
    )
    discovered_shards = discover_execution_shards(spec, repository_root)
    unexpected = sorted(discovered_shards - declared_shards)
    omitted = sorted(declared_shards - discovered_shards)
    if unexpected:
        raise ManifestError(f"unexpected execution shard outside manifest: {unexpected}")
    if omitted:
        raise ManifestError(f"declared execution shard is missing: {omitted}")

    entries: list[dict[str, Any]] = []
    for item in spec["ordered_files"]:
        relative = item["path"]
        absolute = repository_root / relative
        if not absolute.is_file():
            raise ManifestError(f"listed source file is missing: {relative}")
        content = absolute.read_bytes()
        entries.append(
            {
                "order": len(entries),
                "role": item["role"],
                "path": relative,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
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
        "source_digest": framed_source_digest(entries, repository_root),
        "unexpected_execution_shards": [],
    }


def verify_manifest(
    spec_path: Path,
    manifest_path: Path,
    assurance_path: Path | None = None,
) -> dict[str, Any]:
    expected = build_manifest(spec_path)
    actual = load_json(manifest_path)
    verify_manifest_record(expected, actual)
    result: dict[str, Any] = {
        "manifest_match": True,
        "source_digest": expected["source_digest"],
        "manifest_sha256": file_sha256(manifest_path),
    }
    if assurance_path is not None:
        assurance = load_json(assurance_path)
        verify_assurance_record(
            assurance,
            expected,
            manifest_path.name,
            result["manifest_sha256"],
        )
        result["assurance_match"] = True
    return result


def verify_manifest_record(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    """Reject any manifest record that is not the exact recalculated authority."""
    if actual != expected:
        raise ManifestError(
            "source manifest is stale, reordered, incomplete, or contains unexpected data"
        )


def verify_assurance_record(
    assurance: dict[str, Any],
    manifest: dict[str, Any],
    manifest_name: str,
    manifest_sha256: str,
) -> None:
    """Reject an assurance record that does not bind the exact manifest."""
    implementation = assurance.get("implementation")
    if not isinstance(implementation, dict):
        raise ManifestError("assurance record lacks implementation object")
    if implementation.get("source_digest") != manifest["source_digest"]:
        raise ManifestError("assurance record contains a stale source digest")
    if implementation.get("source_manifest_sha256") != manifest_sha256:
        raise ManifestError("assurance record contains a stale manifest digest")
    if implementation.get("source_manifest") != manifest_name:
        raise ManifestError("assurance record names the wrong source manifest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--spec", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--spec", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--assurance", type=Path)
    show = subparsers.add_parser("print-digest")
    show.add_argument("--spec", type=Path, required=True)
    return parser.parse_args()


def resolve_case_path(path: Path) -> Path:
    return path if path.is_absolute() else CASE_ROOT / path


def main() -> int:
    args = parse_args()
    try:
        spec = resolve_case_path(args.spec)
        if args.command == "generate":
            output = resolve_case_path(args.output)
            output.write_bytes(canonical_json_bytes(build_manifest(spec)))
            return 0
        if args.command == "verify":
            manifest = resolve_case_path(args.manifest)
            assurance = resolve_case_path(args.assurance) if args.assurance is not None else None
            print(
                json.dumps(
                    verify_manifest(spec, manifest, assurance),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        if args.command == "print-digest":
            print(build_manifest(spec)["source_digest"])
            return 0
    except (ManifestError, OSError, json.JSONDecodeError) as error:
        print(f"ravel source manifest error: {error}", file=sys.stderr)
        return 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
