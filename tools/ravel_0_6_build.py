#!/usr/bin/env python3
"""Build the reproducible RAVEL 0.6 candidate as development material only.

The generated source and executable are deliberately placed in a caller-owned
temporary directory. The JSON record binds the frozen 0.5 input, generator,
compiler invocation, selected environment identities, and raw build output;
it does not turn a successful build into evaluation evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Any

try:
    from .ravel_0_6_seed_candidate import (
        FROZEN_SOURCE,
        FROZEN_SOURCE_SHA256,
        build_candidate_source,
    )
    from .ravel_0_6_decompose import write_decomposed_candidate
except ImportError:  # direct script execution from the tools directory
    from ravel_0_6_seed_candidate import (  # type: ignore[no-redef]
        FROZEN_SOURCE,
        FROZEN_SOURCE_SHA256,
        build_candidate_source,
    )
    from ravel_0_6_decompose import write_decomposed_candidate  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = Path(__file__).resolve()
TRANSACTION_SURFACE = ROOT / "tools/ravel_0_6_transaction_surface.py"
POLICY_FILE = ROOT / "src/ravel/policy.py"
FROZEN_PREREGISTRATION = ROOT / "ravel_versions/0.6/ravel-0.6-preregistration.json"
INHERITED_05_PREREGISTRATION = ROOT / "ravel_versions/0.5/ravel-0.5-preregistration.json"
COMPONENT_FILES = (
    "src/ravel/mechanism_state.py",
    "src/ravel/world.py",
    "src/ravel/transition.py",
    "src/ravel/planning.py",
    "src/ravel/checkpoint.py",
    "src/ravel/lifecycle.py",
    "src/ravel/experience.py",
)
C_CHECKPOINT_HEADER = ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_checkpoint.h"
C_CHECKPOINT_IMPLEMENTATION = ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_checkpoint.c"
C_WORLD_HEADER = ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_world.h"
C_PROVIDER_SOURCES = {
    "branching": ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_provider_branching.c",
    "ring": ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_provider_ring.c",
}
CANDIDATE_ID = "ravel-0.6-candidate-001"
ENVIRONMENT_KEYS = (
    "CC",
    "CFLAGS",
    "CPPFLAGS",
    "LDFLAGS",
    "LC_ALL",
    "LANG",
    "RAVEL06_PROVIDER",
    "RAVEL06_EXTRA_CFLAGS",
)
CANONICAL_FLAGS = ("-std=c11", "-O3", "-Wall", "-Wextra", "-Werror", "-pedantic")


class BuildError(RuntimeError):
    """Raised when a development build cannot be identity-checked."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def environment_identities() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in ENVIRONMENT_KEYS:
        value = os.environ.get(key)
        result[key] = {
            "present": value is not None,
            "sha256": sha256_bytes(value.encode("utf-8")) if value is not None else None,
        }
    return result


def compiler_command() -> list[str]:
    configured = os.environ.get("CC", "cc")
    command = shlex.split(configured)
    if len(command) != 1 or not command[0]:
        raise BuildError("CC must name one compiler executable without arguments")
    executable = shutil.which(command[0])
    if executable is None:
        raise BuildError(f"compiler executable is unavailable: {command[0]}")
    return [executable]


def provider_configuration() -> tuple[str, Path]:
    provider = os.environ.get("RAVEL06_PROVIDER", "branching")
    if provider not in C_PROVIDER_SOURCES:
        raise BuildError("RAVEL06_PROVIDER must be branching or ring")
    provider_id = {
        "branching": "ravel-toy-branching-c/1",
        "ring": "ravel-toy-ring-c/1",
    }[provider]
    return provider_id, C_PROVIDER_SOURCES[provider]


def extra_compile_flags() -> list[str]:
    value = os.environ.get("RAVEL06_EXTRA_CFLAGS", "")
    try:
        return shlex.split(value)
    except ValueError as error:
        raise BuildError("RAVEL06_EXTRA_CFLAGS is malformed") from error


def run_capture(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)


def worktree_status() -> list[str]:
    result = run_capture(["git", "status", "--porcelain", "--untracked-files=all"])
    if result.returncode != 0:
        raise BuildError(f"git status failed: {result.stderr.strip()}")
    return result.stdout.splitlines()


def build(output_dir: Path, *, require_clean_worktree: bool = False) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "ravel_0_6_candidate_001.c"
    monolithic_source_path = output_dir / "ravel_0_6_candidate_001.generated.c"
    binary_path = output_dir / "ravel_0_6_candidate_001"
    unity_binary_path = output_dir / "ravel_0_6_candidate_001.unity"
    unity_source_path = output_dir / "ravel_0_6_candidate_001.unity.c"
    candidate_object_path = output_dir / "ravel_0_6_candidate_001.o"
    checkpoint_object_path = output_dir / "ravel_0_6_checkpoint.o"
    provider_object_path = output_dir / "ravel_0_6_provider.o"
    record_path = output_dir / "ravel-0.6-candidate-001-build.json"

    existing = [
        path
        for path in (
            source_path,
            monolithic_source_path,
            binary_path,
            unity_binary_path,
            unity_source_path,
            candidate_object_path,
            checkpoint_object_path,
            provider_object_path,
            record_path,
        )
        if path.exists()
    ]
    if existing:
        raise BuildError(
            "stale generated output exists; use a new empty output directory: "
            + ", ".join(str(path) for path in existing)
        )
    if require_clean_worktree:
        status = worktree_status()
        if status:
            raise BuildError("clean-worktree check failed: " + " | ".join(status))

    source = build_candidate_source(FROZEN_SOURCE.read_bytes()).encode("utf-8")
    provider_id, provider_source = provider_configuration()
    monolithic_source_path.write_bytes(source)
    source_path, component_paths = write_decomposed_candidate(
        source.decode("utf-8"), output_dir
    )
    unity_source_path.write_text(
        '#include "ravel_0_6_candidate_001.generated.c"\n'
        f'#include "{provider_source.name}"\n',
        encoding="utf-8",
        newline="\n",
    )
    compiler = compiler_command()
    version = run_capture(compiler + ["--version"])
    include_flags = ["-I", str(C_CHECKPOINT_HEADER.parent)]
    extra_flags = extra_compile_flags()
    compile_flags = list(CANONICAL_FLAGS) + extra_flags
    unity_argv = compiler + compile_flags + include_flags + ["-I", str(provider_source.parent)] + [
        str(unity_source_path),
        "-lm",
        "-o",
        str(unity_binary_path),
    ]
    checkpoint_compile_argv = compiler + compile_flags + include_flags + [
        "-DRAVEL06_SEPARATE_CHECKPOINT",
        "-c",
        str(C_CHECKPOINT_IMPLEMENTATION),
        "-o",
        str(checkpoint_object_path),
    ]
    candidate_compile_argv = compiler + compile_flags + include_flags + [
        "-DRAVEL06_SEPARATE_CHECKPOINT",
        "-c",
        str(source_path),
        "-o",
        str(candidate_object_path),
    ]
    provider_compile_argv = compiler + compile_flags + include_flags + [
        "-c",
        str(provider_source),
        "-o",
        str(provider_object_path),
    ]
    link_argv = compiler + extra_flags + [
        str(candidate_object_path),
        str(checkpoint_object_path),
        str(provider_object_path),
        "-lm",
        "-o",
        str(binary_path),
    ]
    unity_result = run_capture(unity_argv)
    checkpoint_result = run_capture(checkpoint_compile_argv)
    candidate_result = run_capture(candidate_compile_argv)
    provider_result = run_capture(provider_compile_argv)
    link_result = run_capture(link_argv)
    argv = candidate_compile_argv + ["<link>"] + link_argv
    result = link_result
    if unity_result.returncode != 0:
        result = unity_result
    elif checkpoint_result.returncode != 0:
        result = checkpoint_result
    elif candidate_result.returncode != 0:
        result = candidate_result
    elif provider_result.returncode != 0:
        result = provider_result
    elif link_result.returncode != 0:
        result = link_result
    record: dict[str, Any] = {
        "schema": "ravel-0.6-development-build/0.1",
        "candidate_id": CANDIDATE_ID,
        "authoritative_evidence": False,
        "evaluation_status": "UNKNOWN",
        "baseline": {
            "candidate_id": "ravel-0.5-candidate-1",
            "source_path": "ravel_versions/0.5/ravel_0_5.c",
            "source_sha256": FROZEN_SOURCE_SHA256,
        },
        "generator": {
            "path": str(GENERATOR.relative_to(ROOT)),
            "sha256": sha256_file(GENERATOR),
            "seed_builder": "tools/ravel_0_6_seed_candidate.py",
            "transaction_surface": {
                "path": str(TRANSACTION_SURFACE.relative_to(ROOT)),
                "sha256": sha256_file(TRANSACTION_SURFACE),
            },
            "policy_source": {
                "path": str(POLICY_FILE.relative_to(ROOT)),
                "sha256": sha256_file(POLICY_FILE),
            },
        },
        "component_contracts": {
            "checkpoint": {
                "abi_version": "ravel-0.6-checkpoint-abi/1",
                "header_path": str(C_CHECKPOINT_HEADER.relative_to(ROOT)),
                "header_sha256": sha256_file(C_CHECKPOINT_HEADER),
                "implementation_path": str(C_CHECKPOINT_IMPLEMENTATION.relative_to(ROOT)),
                "implementation_sha256": sha256_file(C_CHECKPOINT_IMPLEMENTATION),
                "object_sha256": sha256_file(checkpoint_object_path) if checkpoint_result.returncode == 0 else None,
                "compile_argv": checkpoint_compile_argv,
                "compiler_identity": version.stdout.strip(),
                "declared_dependencies": [],
            },
            "world": {
                "abi_version": "ravel-0.6-world-abi/1",
                "header_path": str(C_WORLD_HEADER.relative_to(ROOT)),
                "header_sha256": sha256_file(C_WORLD_HEADER),
                "provider_source_path": str(provider_source.relative_to(ROOT)),
                "provider_source_sha256": sha256_file(provider_source),
                "implementation_sha256": sha256_file(provider_source),
                "object_sha256": sha256_file(provider_object_path) if provider_result.returncode == 0 else None,
                "compile_argv": provider_compile_argv,
                "compiler_identity": version.stdout.strip(),
                "declared_dependencies": [str(C_WORLD_HEADER.relative_to(ROOT))],
                "provider_id": provider_id,
            }
        },
        "policy": {
            "preregistration_path": str(FROZEN_PREREGISTRATION.relative_to(ROOT)),
            "preregistration_sha256": sha256_file(FROZEN_PREREGISTRATION),
            "inherited_05_preregistration_path": str(INHERITED_05_PREREGISTRATION.relative_to(ROOT)),
            "inherited_05_preregistration_sha256": sha256_file(INHERITED_05_PREREGISTRATION),
        },
        "environment_provider": {
                "provider_id": provider_id,
                "compile_flags": [],
                "source_path": str(provider_source.relative_to(ROOT)),
            },
        "mechanism_components": [
            {"path": path, "sha256": sha256_file(ROOT / path)}
            for path in COMPONENT_FILES
        ],
        "generated_source": {
            "path": source_path.name,
            "monolithic_path": monolithic_source_path.name,
            "sha256": sha256_file(source_path),
            "bytes": source_path.stat().st_size,
            "monolithic_sha256": sha256_bytes(source),
            "monolithic_bytes": len(source),
            "development_only": True,
        },
        "generated_components": [
            {"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in component_paths
        ],
        "compiler": {
            "executable": compiler[0],
            "version_argv": compiler + ["--version"],
            "version_stdout": version.stdout,
            "version_stderr": version.stderr,
            "version_exit_status": version.returncode,
            "argv": argv,
            "unity_argv": unity_argv,
            "checkpoint_compile_argv": checkpoint_compile_argv,
            "candidate_compile_argv": candidate_compile_argv,
            "provider_compile_argv": provider_compile_argv,
            "link_argv": link_argv,
        },
        "worktree": {
            "required_clean": require_clean_worktree,
            "status": worktree_status(),
        },
        "build": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_status": result.returncode,
            "binary_sha256": sha256_file(binary_path) if result.returncode == 0 else None,
            "separate_binary_sha256": sha256_file(binary_path) if result.returncode == 0 else None,
            "unity_binary_sha256": sha256_file(unity_binary_path) if unity_result.returncode == 0 else None,
            "unity_source_sha256": sha256_file(unity_source_path) if unity_source_path.exists() else None,
            "candidate_object_sha256": sha256_file(candidate_object_path) if candidate_result.returncode == 0 else None,
            "checkpoint_object_sha256": sha256_file(checkpoint_object_path) if checkpoint_result.returncode == 0 else None,
            "provider_object_sha256": sha256_file(provider_object_path) if provider_result.returncode == 0 else None,
        },
        "execution": {
            "argv": None,
            "status": "NOT_RUN",
            "reason": "build record does not claim a trial execution",
        },
    }
    record_path.write_text(canonical_json(record) + "\n", encoding="utf-8")
    if version.returncode != 0:
        raise BuildError("compiler version probe failed")
    if result.returncode != 0:
        raise BuildError("candidate compilation failed; see " + str(record_path))
    return record


def derive(output: Path) -> str:
    if output.exists():
        raise BuildError(f"stale generated source exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    source = build_candidate_source(FROZEN_SOURCE.read_bytes()).encode("utf-8")
    output.write_bytes(source)
    return sha256_bytes(source)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--output-dir", type=Path, required=True)
    build_parser.add_argument("--require-clean-worktree", action="store_true")
    derive_parser = subparsers.add_parser("derive")
    derive_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "derive":
            digest = derive(args.output)
            print(f"{CANDIDATE_ID} sha256={digest}")
        else:
            record = build(args.output_dir, require_clean_worktree=args.require_clean_worktree)
            print(canonical_json(record))
    except (BuildError, OSError, UnicodeError, ValueError) as error:
        print(f"ravel 0.6 development build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
