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
except ImportError:  # direct script execution from the tools directory
    from ravel_0_6_seed_candidate import (  # type: ignore[no-redef]
        FROZEN_SOURCE,
        FROZEN_SOURCE_SHA256,
        build_candidate_source,
    )

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = Path(__file__).resolve()
TRANSACTION_SURFACE = ROOT / "tools/ravel_0_6_transaction_surface.py"
COMPONENT_FILES = (
    "src/ravel/mechanism_state.py",
    "src/ravel/world.py",
    "src/ravel/transition.py",
    "src/ravel/planning.py",
    "src/ravel/checkpoint.py",
    "src/ravel/lifecycle.py",
    "src/ravel/experience.py",
)
CANDIDATE_ID = "ravel-0.6-candidate-001"
ENVIRONMENT_KEYS = ("CC", "CFLAGS", "CPPFLAGS", "LDFLAGS", "LC_ALL", "LANG")
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
    binary_path = output_dir / "ravel_0_6_candidate_001"
    record_path = output_dir / "ravel-0.6-candidate-001-build.json"

    existing = [path for path in (source_path, binary_path, record_path) if path.exists()]
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
    source_path.write_bytes(source)
    compiler = compiler_command()
    version = run_capture(compiler + ["--version"])
    argv = compiler + list(CANONICAL_FLAGS) + [str(source_path), "-lm", "-o", str(binary_path)]
    result = run_capture(argv)
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
        },
        "mechanism_components": [
            {"path": path, "sha256": sha256_file(ROOT / path)}
            for path in COMPONENT_FILES
        ],
        "generated_source": {
            "path": str(source_path),
            "sha256": sha256_bytes(source),
            "bytes": len(source),
            "development_only": True,
        },
        "compiler": {
            "executable": compiler[0],
            "version_argv": compiler + ["--version"],
            "version_stdout": version.stdout,
            "version_stderr": version.stderr,
            "version_exit_status": version.returncode,
            "argv": argv,
        },
        "environment_keys": environment_identities(),
        "worktree": {
            "required_clean": require_clean_worktree,
            "status": worktree_status(),
        },
        "build": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_status": result.returncode,
            "binary_sha256": sha256_file(binary_path) if result.returncode == 0 else None,
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
