#!/usr/bin/env python3
"""Bounded Forge checks for the MNCS-native RAVEL workspace (mncs/).

Runs the language-owned experiment flow for each MNCS-native RAVEL module:
source -> semantic/HIR/SSA -> backend artifact -> bounded corpus execution,
then verifies layered agreement and per-case expectations.

The modules form a linked multi-module program: they import the standard
library (mncs.core.status, mncs.core.logic) through MNCS_LIBRARY_PATH and
each other through ravel.types.v1. Every module is exercised on every
backend whose declared executable envelope should admit it; artifact-only
targets are additionally compiled so honest refusals are recorded as
evidence instead of silence.

Results are development evidence only: bounded local observations, not
proof of universal equivalence, conformance, or promotion.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MNCS_DIR = ROOT / "mncs"
WORKSPACE = MNCS_DIR / "workspace"
CORPUS = MNCS_DIR / "corpus"

# Linked modules under workspace/ravel/. The corpus file name is explicit
# because stems no longer map 1:1 onto flat file names.
MODULES: dict[str, dict[str, object]] = {
    "core": {
        "module": "ravel.core.v1",
        "source": "ravel/core.mncs",
        "corpus": "ravel-core-corpus.json",
    },
    "loop": {
        "module": "ravel.loop.v1",
        "source": "ravel/loop.mncs",
        "corpus": "ravel-loop-corpus.json",
    },
    "checkpoint": {
        "module": "ravel.checkpoint.v1",
        "source": "ravel/checkpoint.mncs",
        "corpus": "ravel-checkpoint-corpus.json",
    },
    "memory": {
        "module": "ravel.memory.v1",
        "source": "ravel/memory.mncs",
        "corpus": "ravel-memory-corpus.json",
    },
    "task": {
        "module": "ravel.task.v1",
        "source": "ravel/task.mncs",
        "corpus": "ravel-task-corpus.json",
    },
}

# Backends whose declared envelope realizes composite values end to end;
# each RAVEL module carries records and payload sums.
EXECUTION_BACKENDS: list[str] = [
    "mncs-research-bytecode",
    "mncs-portable-wasm-mvp",
]

# Backends with a scalar process/object envelope: compilation is attempted
# so the recorded refusal (composite values outside the scalar boundary) is
# evidence-backed rather than assumed.
ARTIFACT_TARGETS: list[str] = ["c11", "llvm", "cranelift"]

PROBE_SOURCE = """mncs 0.6;

// Forge probe: requires profile 0.6 use-resolution of the status lattice,
// payload-free finite matching, strict booleans, and explicit saturating
// arithmetic intents. A toolchain missing any of these refuses honestly and
// this check reports BLOCKED instead of trusting stale semantics.
module ravel.forge.probe;

use mncs.core.status.v1;

fn bump(count: i64) -> (result: i64) {
    return count +| 1;
}

fn soften(left: Status, right: Status) -> (result: bool) {
    return is_decided(dominate(left, right)) && bump(0) == 0;
}
"""


def _probe_ok(binary: str, library_path: str) -> bool:
    """The binary must elaborate the 0.6 probe (imports + intents)."""
    import tempfile

    env = dict(os.environ)
    env["MNCS_LIBRARY_PATH"] = library_path
    with tempfile.NamedTemporaryFile("w", suffix=".mncs", delete=False) as handle:
        handle.write(PROBE_SOURCE)
        path = handle.name
    try:
        result = subprocess.run(
            [binary, "source-study", path, "--node-id", "forge-probe"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        document = json.loads(result.stdout or "{}")
        return not document.get("diagnostics")
    except Exception:
        return False
    finally:
        os.unlink(path)


def _library_root() -> Path | None:
    """Standard-library root inside a sibling mncs-language checkout."""
    candidates = [
        Path(os.environ["MNCS_LANGUAGE_ROOT"]) / "library"
        if os.environ.get("MNCS_LANGUAGE_ROOT")
        else None,
        ROOT.parent / "mncs-language" / "library",
    ]
    for candidate in candidates:
        if candidate and (candidate / "core" / "status.mncs").is_file():
            return candidate
    return None


def _mncs_cli(library_path: str) -> str | None:
    """Locate the sibling mncs-language CLI binary or build it."""
    base_candidates = [
        Path(os.environ["MNCS_LANGUAGE_ROOT"])
        if os.environ.get("MNCS_LANGUAGE_ROOT")
        else None,
        ROOT.parent / "mncs-language",
    ]
    for base in base_candidates:
        if not base:
            continue
        binary = base / "target/debug/mncs"
        if binary.is_file():
            if _probe_ok(str(binary), library_path):
                return str(binary)
            # Stale or wrong toolchain: keep searching rather than fail.
            continue
        if (base / "Cargo.toml").is_file():
            result = subprocess.run(
                ["cargo", "build", "-p", "mncs-cli"],
                cwd=base,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and binary.is_file() and _probe_ok(str(binary), library_path):
                return str(binary)
    return None


def _environment(library_path: str) -> dict[str, str]:
    env = dict(os.environ)
    env["MNCS_LIBRARY_PATH"] = library_path
    return env


def run_experiment(
    binary: str, source: Path, corpus: Path, backend: str, library_path: str
) -> tuple[str, dict]:
    output_dir = f"/tmp/ravel-mncs-forge/{source.stem}-{backend.replace('mncs-', '')}"
    result = subprocess.run(
        [
            binary,
            "experiment",
            "run",
            str(source),
            "--backend",
            backend,
            "--corpus",
            str(corpus),
            "--output-dir",
            output_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_environment(library_path),
    )
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "FAIL", {"error": "non-JSON CLI output", "stderr": result.stderr[-800:]}
    if "cases" not in document:
        diagnostics = [d.get("code") for d in document.get("diagnostics", [])][:6]
        return "FAIL", {"error": "compilation refused", "diagnostics": diagnostics}
    met = sum(1 for case_ in document["cases"] if case_.get("expectation_met") is True)
    total = len(document["cases"])
    validations = [v.get("judgement") for v in document.get("translation_validations", [])]
    status = document.get("status")
    ok = met == total and all(v == "PASS" for v in validations)
    # Overall PASS/UNKNOWN are acceptable: UNKNOWN preserves honest unresolved
    # obligations. FAIL means an expectation or layered agreement broke.
    overall_ok = ok and status in ("PASS", "UNKNOWN")
    detail = {
        "cases_met": met,
        "cases_total": total,
        "translation_validations": validations,
        "status": status,
        "unresolved_reasons": document.get("unresolved_reasons", []),
    }
    return ("PASS" if overall_ok else "FAIL"), detail


def compile_artifact(
    binary: str, source: Path, target: str, library_path: str
) -> tuple[str, dict]:
    """Artifact-realization probe: record realized vs honest refusal."""
    output_dir = f"/tmp/ravel-mncs-forge/artifact-{source.stem}-{target}"
    result = subprocess.run(
        [
            binary,
            "compile",
            str(source),
            "--emit",
            "backend",
            "--target",
            target,
            "--output-dir",
            output_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_environment(library_path),
    )
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "FAIL", {"error": "non-JSON CLI output", "stderr": result.stderr[-800:]}
    # Refusals print a bare diagnostics list; successes print a result object.
    if isinstance(document, list):
        codes = [d.get("code") for d in document][:6]
        return "UNKNOWN", {"status": "refused", "diagnostics": codes}
    status = document.get("status")
    diagnostics = [d.get("code") for d in document.get("diagnostics", [])][:6]
    if status == "completed":
        return "PASS", {"artifact": True}
    # Honest refusal (unsupported envelope, unresolved target evidence) is
    # recorded as UNKNOWN evidence, never silently ignored.
    return "UNKNOWN", {"status": status, "diagnostics": diagnostics}


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name != "mncs-experiments":
        print(json.dumps({"available_checks": ["mncs-experiments"], "requested": name}))
        return 2

    library = _library_root()
    if not library:
        print(
            json.dumps(
                {
                    "check": "mncs-experiments",
                    "status": "BLOCKED",
                    "reason": "sibling mncs-language checkout with library/ required",
                }
            )
        )
        return 0
    binary = _mncs_cli(str(library))
    if not binary:
        print(
            json.dumps(
                {
                    "check": "mncs-experiments",
                    "status": "BLOCKED",
                    "reason": (
                        "sibling mncs-language checkout with a built mncs-cli "
                        "supporting profile 0.6 imports and arithmetic intents "
                        "is required"
                    ),
                }
            )
        )
        return 0

    report: dict[str, object] = {
        "check": "mncs-experiments",
        "interpretation": "bounded local development evidence; not equivalence, conformance, or promotion",
        "toolchain": {"binary": binary, "library_root": str(library)},
        "modules": {},
    }
    failed = False
    for stem, spec in MODULES.items():
        source = WORKSPACE / str(spec["source"])
        corpus = CORPUS / str(spec["corpus"])
        module_report: dict[str, object] = {}
        for backend in EXECUTION_BACKENDS:
            status, detail = run_experiment(binary, source, corpus, backend, str(library))
            module_report[backend] = {"kind": "execution", "status": status, **detail}
            if status != "PASS":
                failed = True
        for target in ARTIFACT_TARGETS:
            status, detail = compile_artifact(binary, source, target, str(library))
            module_report[target] = {"kind": "artifact", "status": status, **detail}
            if status == "FAIL":
                failed = True
        report["modules"][spec["module"]] = module_report  # type: ignore[index]

    report["overall"] = "FAIL" if failed else "PASS"
    print(json.dumps(report, indent=1))
    evidence_dir = ROOT / "build" / "mncs-ravel"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with open(evidence_dir / "mncs-experiments.json", "w") as handle:
        handle.write(json.dumps(report, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
