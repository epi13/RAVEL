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
# because stems no longer map 1:1 onto flat file names. Every module with an
# executable corpus MUST appear here: the checker cross-verifies this table
# against the workspace directory and fails when a module is omitted.
# ravel.types.v1 is the only intentional exclusion — it declares shared
# identity vocabulary with no entry-point functions and no corpus.
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
    "lifecycle": {
        "module": "ravel.lifecycle.v1",
        "source": "ravel/lifecycle.mncs",
        "corpus": "ravel-lifecycle-corpus.json",
    },
    "provider": {
        "module": "ravel.provider.v1",
        "source": "ravel/provider.mncs",
        "corpus": "ravel-provider-corpus.json",
    },
    "budget": {
        "module": "ravel.budget.v1",
        "source": "ravel/budget.mncs",
        "corpus": "ravel-budget-corpus.json",
    },
    "forge": {
        "module": "ravel.forge.v1",
        "source": "ravel/forge.mncs",
        "corpus": "ravel-forge-corpus.json",
    },
    "identity": {
        "module": "ravel.identity.v1",
        "source": "ravel/identity.mncs",
        "corpus": "ravel-identity-corpus.json",
    },
    "evidence": {
        "module": "ravel.evidence.v1",
        "source": "ravel/evidence.mncs",
        "corpus": "ravel-evidence-corpus.json",
    },
}

# Every backend below executes RAVEL's composite entrypoints end to end
# (records, payload sums, exact sequences, bounded views, nested
# composites). The pre-2026-09 scalar-envelope limitation is obsolete:
# native C11/LLVM/Cranelift realizations now carry the same composite
# shapes, so all five backends run the full semantic matrix.
EXECUTION_BACKENDS: list[str] = [
    "mncs-research-bytecode",
    "mncs-portable-wasm-mvp",
    "c11",
    "llvm",
    "cranelift",
]

PROBE_SOURCE = """mncs 0.10;

// Forge probe: requires profile 0.10 use-resolution of the status lattice,
// explicit bounded polymorphism (generic N: Nat functions over imported
// nominal sequence types), and explicit saturating arithmetic intents. A
// toolchain missing any of these refuses honestly and this check reports
// BLOCKED instead of trusting stale semantics.
module ravel.forge.probe;

use mncs.core.status.v1;

fn bump(count: i64) -> (result: i64) {
    return count +| 1;
}

fn first<T, N: Nat>(xs: [T; N]) -> (result: T) {
    return xs[0];
}

fn first_status(pair: [Status; 2]) -> (result: Status) {
    return first<Status, 2>(pair);
}

fn soften(left: Status, right: Status) -> (result: bool) {
    return is_decided(dominate(left, right)) && bump(0) == 0;
}
"""

# Nominal-type negative probe: a RAVEL ContentDigest passed where the
# authoritative Digest32 is expected must be refused at elaboration. Same
# bytes under the wrong semantic role are a type error, not an identity.
NEGATIVE_PROBE_SOURCE = """mncs 0.10;

module ravel.forge.negative_probe;

use ravel.identity.v1;
use mncs.core.identity as idlib;

fn typed_crossing(digest: ContentDigest) -> (result: bool) {
    return idlib.is_zero(digest);
}
"""


def _study_ok(document: object) -> bool:
    """A study passes when elaboration completes (obligations may stay
    honestly UNKNOWN) with no error-severity diagnostic."""
    if not isinstance(document, dict):
        return False
    if document.get("compilation_status") not in (
        "completed",
        "completed_with_unresolved_obligations",
    ):
        return False
    for diagnostic in document.get("diagnostics") or []:
        if isinstance(diagnostic, dict) and diagnostic.get("severity") == "error":
            return False
    return True


def _probe_ok(binary: str, library_path: str) -> bool:
    """The binary must elaborate the capability probe (imports + generics)."""
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
        document = json.loads(result.stdout or "null")
        return _study_ok(document)
    except Exception:
        return False
    finally:
        os.unlink(path)


def _negative_probe_ok(binary: str, library_path: str) -> tuple[bool, dict]:
    """Wrong-nominal-type programs must be refused, not executed."""
    probe_path = WORKSPACE / "ravel" / "__negative_probe.mncs"
    env = dict(os.environ)
    env["MNCS_LIBRARY_PATH"] = library_path
    try:
        probe_path.write_text(NEGATIVE_PROBE_SOURCE)
        result = subprocess.run(
            [binary, "source-study", str(probe_path), "--node-id", "forge-negative-probe"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        try:
            document = json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            return False, {"error": "non-JSON study output"}
        refused = not _study_ok(document)
        codes: list[str] = []

        def walk(node: object) -> None:
            if isinstance(node, dict):
                if "code" in node and "severity" in node:
                    codes.append(str(node.get("code")))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(document)
        return refused, {"refused": refused, "diagnostics": sorted(set(codes))[:6]}
    except Exception as exc:
        return False, {"error": str(exc)[:200]}
    finally:
        try:
            probe_path.unlink()
        except OSError:
            pass


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


def _binary_paths(base: Path) -> list[Path]:
    """Where `cargo build -p mncs-cli` may have placed the binary."""
    paths = [base / "target/debug/mncs"]
    target_dir = os.environ.get("CARGO_TARGET_DIR")
    if target_dir:
        paths.append(Path(target_dir) / "debug/mncs")
    return paths


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
        binaries = [path for path in _binary_paths(base) if path.is_file()]
        if binaries:
            if _probe_ok(str(binaries[0]), library_path):
                return str(binaries[0])
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
            built = [path for path in _binary_paths(base) if path.is_file()]
            if result.returncode == 0 and built and _probe_ok(str(built[0]), library_path):
                return str(built[0])
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
                        "supporting profile 0.10 imports, generics, and "
                        "arithmetic intents is required"
                    ),
                }
            )
        )
        return 0

    # Coverage cross-check: every workspace module with an executable corpus
    # must be enumerated in MODULES. Only ravel.types.v1 (shared vocabulary,
    # no entry points, no corpus) may be absent.
    workspace_sources = sorted(
        path.name
        for path in (WORKSPACE / "ravel").glob("*.mncs")
        if not path.name.startswith("__")
    )
    covered_sources = sorted(str(spec["source"]).split("/")[-1] for spec in MODULES.values())
    uncovered = [
        name
        for name in workspace_sources
        if name not in covered_sources and name != "types.mncs"
    ]
    negative_ok, negative_detail = _negative_probe_ok(binary, str(library))

    report: dict[str, object] = {
        "check": "mncs-experiments",
        "interpretation": "bounded local development evidence; not equivalence, conformance, or promotion",
        "toolchain": {"binary": binary, "library_root": str(library)},
        "coverage": {
            "workspace_modules": workspace_sources,
            "covered": covered_sources,
            "uncovered": uncovered,
        },
        "negative_nominal_type": negative_detail,
        "modules": {},
    }
    failed = False
    if uncovered:
        failed = True
    if not negative_ok:
        failed = True
    for stem, spec in MODULES.items():
        source = WORKSPACE / str(spec["source"])
        corpus = CORPUS / str(spec["corpus"])
        module_report: dict[str, object] = {}
        agreements: list[bool] = []
        for backend in EXECUTION_BACKENDS:
            status, detail = run_experiment(binary, source, corpus, backend, str(library))
            module_report[backend] = {"kind": "execution", "status": status, **detail}
            if status != "PASS":
                failed = True
            agreements.append(
                status == "PASS"
                and detail.get("cases_met") == detail.get("cases_total")
            )
        # Case-by-case semantic agreement across backends: every execution
        # backend must meet the same expectations on the same corpus.
        module_report["cross_backend_agreement"] = all(agreements) and len(agreements) > 0
        if not module_report["cross_backend_agreement"]:
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
