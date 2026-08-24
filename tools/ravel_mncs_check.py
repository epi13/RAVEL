#!/usr/bin/env python3
"""Bounded Forge checks for the MNCS-native RAVEL workspace (mncs/).

Runs the language-owned experiment flow for each MNCS-native RAVEL module:
source -> semantic/HIR/SSA -> backend artifact -> bounded corpus execution,
then verifies layered agreement and per-case expectations. Results are
development evidence only: they are bounded local observations, not proof of
universal equivalence, conformance, or promotion.
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

MODULES: dict[str, dict[str, object]] = {
    "ravel_core": {"module": "ravel.core.v1"},
    "ravel_loop": {"module": "ravel.loop.v1"},
    "ravel_checkpoint": {"module": "ravel.checkpoint.v1"},
    "ravel_memory": {"module": "ravel.memory.v1"},
    "ravel_task": {"module": "ravel.task.v1"},
}

BACKENDS: list[str] = ["mncs-research-bytecode"]


def _mncs_cli() -> str | None:
    """Locate the sibling mncs-language CLI binary or build it."""
    candidates = [
        Path(os.environ.get("MNCS_LANGUAGE_ROOT", "")) if os.environ.get("MNCS_LANGUAGE_ROOT") else None,
        ROOT.parent / "mncs-language",
    ]
    for base in candidates:
        if not base:
            continue
        binary = base / "target/debug/mncs"
        if binary.is_file():
            return str(binary)
        if (base / "Cargo.toml").is_file():
            result = subprocess.run(
                ["cargo", "build", "-p", "mncs-cli"],
                cwd=base,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and binary.is_file():
                return str(binary)
    return None


def run_experiment(binary: str, source: Path, corpus: Path, backend: str) -> tuple[str, dict]:
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
    # obligations (e.g. exact-cost evidence). FAIL means an expectation or
    # layered agreement broke.
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

    binary = _mncs_cli()
    if not binary:
        print(
            json.dumps(
                {
                    "check": "mncs-experiments",
                    "status": "BLOCKED",
                    "reason": "sibling mncs-language checkout with a built mncs-cli is required",
                }
            )
        )
        return 0

    report: dict[str, object] = {
        "check": "mncs-experiments",
        "interpretation": "bounded local development evidence; not equivalence, conformance, or promotion",
        "modules": {},
    }
    failed = False
    for stem, spec in MODULES.items():
        source = WORKSPACE / f"{stem}.mncs"
        corpus_name = f"{stem.replace(chr(95), chr(45))}-corpus.json"
        corpus = CORPUS / corpus_name
        module_report: dict[str, object] = {}
        for backend in BACKENDS:
            status, detail = run_experiment(binary, source, corpus, backend)
            module_report[backend] = {"status": status, **detail}
            if status != "PASS":
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
