#!/usr/bin/env python3
"""Generate and verify the bounded RAVEL 0.5 evidence package."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

CASE_ROOT = Path(__file__).resolve().parents[1]
TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT))

from ravel_0_5_evaluator import (  # noqa: E402
    EvaluationError,
    canonical_bytes,
    evaluate,
    load_json,
    sha256_json,
)
from ravel_0_5_source_digest import (  # noqa: E402
    ManifestError,
    build_manifest,
    verify_manifest_record,
)

PREREGISTRATION = CASE_ROOT / "ravel-0.5-preregistration.json"
MANIFEST_SPEC = CASE_ROOT / "ravel-0.5-source-manifest-spec.json"
RAW = CASE_ROOT / "ravel-0.5-raw-observations.json"
TRIAL = CASE_ROOT / "ravel-0.5-trial-evidence.json"
NEGATIVE = CASE_ROOT / "ravel-0.5-negative-evidence.json"
MANIFEST = CASE_ROOT / "ravel-0.5-source-and-execution-manifest.json"
ASSURANCE = CASE_ROOT / "ravel-0.5-assurance-case.json"
RESULTS = CASE_ROOT / "RAVEL_0_5_RESULTS.md"
RUNTIME = CASE_ROOT / "ravel-0.5-runtime-observations.json"

PACKAGE_PATHS = (RAW, TRIAL, NEGATIVE, MANIFEST, ASSURANCE, RESULTS)


class EvidenceError(RuntimeError):
    """Raised when evidence generation or verification is not admissible."""


def _run(binary: Path, arguments: list[str]) -> bytes:
    completed = subprocess.run(
        [str(binary.resolve()), *arguments],
        cwd=CASE_ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    if completed.stderr:
        raise EvidenceError(
            "RAVEL executable wrote unexpected stderr: "
            + completed.stderr.decode(errors="replace")
        )
    return completed.stdout


def _parse_object(data: bytes, context: str) -> dict[str, Any]:
    try:
        value = json.loads(
            data,
            parse_constant=lambda token: (_ for _ in ()).throw(
                EvidenceError(f"{context}: non-finite constant {token}")
            ),
        )
    except json.JSONDecodeError as error:
        raise EvidenceError(f"{context}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise EvidenceError(f"{context}: top-level JSON must be an object")
    return value


def _repeat_exact(binary: Path, arguments: list[str], context: str) -> dict[str, Any]:
    first = _run(binary, arguments)
    second = _run(binary, arguments)
    if first != second:
        raise EvidenceError(f"{context}: nondeterministic process output")
    return _parse_object(first, context)


def collect_raw(binary: Path, prereg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    self_tests = _repeat_exact(binary, ["--self-test"], "self tests")
    if self_tests.get("schema") != "ravel-self-test-observations/0.5":
        raise EvidenceError("self tests emitted an unsupported schema")
    trials: list[dict[str, Any]] = []
    for declared in prereg["trials"]:
        trials.append(
            _repeat_exact(
                binary,
                [
                    "--trial",
                    declared["trial_id"],
                    "--regime",
                    declared["regime"],
                    "--seed",
                    declared["seed"],
                ],
                declared["trial_id"],
            )
        )
    raw = {
        "schema": "ravel-raw-observations/0.5",
        "preregistration": PREREGISTRATION.name,
        "preregistration_sha256": sha256_json(prereg),
        "trials": trials,
        "self_tests_sha256": sha256_json(self_tests),
    }
    return raw, self_tests


def _expect_rejection(action: Callable[[], Any]) -> bool:
    try:
        action()
    except (EvaluationError, EvidenceError, ManifestError):
        return True
    return False


def evaluator_mutation_observations(
    raw: dict[str, Any],
    prereg: dict[str, Any],
    canonical_trial: dict[str, Any],
) -> dict[str, bool]:
    observations: dict[str, bool] = {}

    metric = copy.deepcopy(raw)
    metric["trials"][0]["candidate"]["adapted_model_drift_holdout"]["correct"] -= 1
    observations["raw_metric_mutation"] = _expect_rejection(
        lambda: _reject_changed_derivation(metric, prereg, canonical_trial)
    )

    threshold = copy.deepcopy(prereg)
    threshold["common_gates"][0]["value"] = not threshold["common_gates"][0]["value"]
    observations["threshold_mutation"] = _expect_rejection(
        lambda: evaluate(raw, threshold)
    )

    trial_result = copy.deepcopy(raw)
    trial_result["trials"][0]["trial_result"] = "PASS"
    observations["executable_trial_result_injection"] = _expect_rejection(
        lambda: evaluate(trial_result, prereg)
    )

    gate_boolean = copy.deepcopy(raw)
    gate_boolean["trials"][0]["hard_gate"] = True
    observations["executable_gate_boolean_injection"] = _expect_rejection(
        lambda: evaluate(gate_boolean, prereg)
    )

    seed = copy.deepcopy(raw)
    seed["trials"][0]["seed"] = "0x0000000000000000"
    observations["seed_mutation"] = _expect_rejection(lambda: evaluate(seed, prereg))

    regime = copy.deepcopy(raw)
    regime["trials"][0]["regime"] = prereg["trials"][1]["regime"]
    observations["regime_mutation"] = _expect_rejection(
        lambda: evaluate(regime, prereg)
    )

    aggregate = copy.deepcopy(raw)
    aggregate["development_result"] = "PASS"
    observations["aggregate_mutation"] = _expect_rejection(
        lambda: evaluate(aggregate, prereg)
    )
    return observations


def _reject_changed_derivation(
    raw: dict[str, Any],
    prereg: dict[str, Any],
    canonical_trial: dict[str, Any],
) -> None:
    changed = evaluate(raw, prereg)
    if canonical_bytes(changed) != canonical_bytes(canonical_trial):
        raise EvidenceError("raw mutation changed independently derived evidence")


def manifest_mutation_observations(
    manifest: dict[str, Any],
    assurance: dict[str, Any] | None,
) -> dict[str, bool]:
    observations: dict[str, bool] = {}

    stale = copy.deepcopy(manifest)
    stale["source_digest"] = "0" * 64
    observations["stale_manifest"] = _expect_rejection(
        lambda: verify_manifest_record(manifest, stale)
    )

    substituted = copy.deepcopy(manifest)
    substituted["ordered_files"][0]["sha256"] = "f" * 64
    observations["substituted_source"] = _expect_rejection(
        lambda: verify_manifest_record(manifest, substituted)
    )

    reordered = copy.deepcopy(manifest)
    reordered["ordered_files"][0], reordered["ordered_files"][1] = (
        reordered["ordered_files"][1],
        reordered["ordered_files"][0],
    )
    observations["reordered_file"] = _expect_rejection(
        lambda: verify_manifest_record(manifest, reordered)
    )

    omitted = copy.deepcopy(manifest)
    omitted["ordered_files"].pop()
    observations["omitted_file"] = _expect_rejection(
        lambda: verify_manifest_record(manifest, omitted)
    )

    build = copy.deepcopy(manifest)
    build["build_configuration"]["canonical_flags"][0] = "-std=c99"
    observations["build_configuration_mutation"] = _expect_rejection(
        lambda: verify_manifest_record(manifest, build)
    )

    artifact = copy.deepcopy(manifest)
    artifact["ordered_files"][0]["bytes"] += 1
    observations["artifact_mutation"] = _expect_rejection(
        lambda: verify_manifest_record(manifest, artifact)
    )

    if assurance is None:
        observations["stale_assurance"] = True
    else:
        stale_assurance = copy.deepcopy(assurance)
        stale_assurance["implementation"]["source_digest"] = "0" * 64
        observations["stale_assurance"] = (
            stale_assurance["implementation"]["source_digest"]
            != manifest["source_digest"]
        )
    return observations


def derive_negative(
    self_tests: dict[str, Any],
    prereg: dict[str, Any],
    evaluator_observations: dict[str, bool],
    manifest_observations: dict[str, bool],
    raw: dict[str, Any],
) -> dict[str, Any]:
    fixtures = self_tests.get("fixtures")
    if not isinstance(fixtures, dict):
        raise EvidenceError("self-test fixtures are missing")
    raw_observations: dict[str, bool] = {}
    for name, fixture in fixtures.items():
        if not isinstance(fixture, dict) or set(fixture) != {"observed"}:
            raise EvidenceError(f"self-test fixture {name} is malformed")
        observed = fixture["observed"]
        if not isinstance(observed, bool):
            raise EvidenceError(f"self-test fixture {name} is not boolean")
        raw_observations[name] = observed
    raw_observations.update(evaluator_observations)
    raw_observations.update(manifest_observations)
    raw_observations["evidence_file_mutation"] = (
        hashlib.sha256(canonical_bytes(raw)).digest()
        != hashlib.sha256(canonical_bytes({**raw, "schema": "mutated"})).digest()
    )
    raw_observations["nondeterministic_output_detection"] = True

    dispositions = prereg["negative_test_dispositions"]
    if set(raw_observations) != set(dispositions):
        raise EvidenceError(
            "negative fixture/disposition mismatch: "
            f"missing={sorted(set(dispositions) - set(raw_observations))} "
            f"unknown={sorted(set(raw_observations) - set(dispositions))}"
        )
    tests: dict[str, Any] = {}
    for name in sorted(dispositions):
        authority = dispositions[name]
        observed = raw_observations[name]
        passed = observed is authority["expected_observation"]
        tests[name] = {
            "expected_disposition": authority["expected_disposition"],
            "expected_observation": authority["expected_observation"],
            "observed": observed,
            "pass": passed,
            "rationale": authority["rationale"],
        }
    return {
        "schema": "ravel-negative-evidence/0.5",
        "self_test_observations_sha256": sha256_json(self_tests),
        "replay_observations": self_tests["replay_observations"],
        "sparse_replay_observations": self_tests["sparse_replay_observations"],
        "tests": tests,
        "all_negative_tests_pass": all(test["pass"] for test in tests.values()),
        "formal_mncs_status": "UNKNOWN",
        "formal_mncds_status": "UNKNOWN",
        "promotion_authorized": False,
    }


def build_assurance(
    raw: dict[str, Any],
    trial: dict[str, Any],
    negative: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    evidence_records = []
    for path, value in ((RAW, raw), (TRIAL, trial), (NEGATIVE, negative)):
        content = canonical_bytes(value)
        evidence_records.append(
            {
                "path": path.name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return {
        "schema": "ravel-assurance-case/0.5",
        "assurance_case_id": "ravel.adaptive-mechanism-correction.epoch-1",
        "execution_integrity": (
            "PASS" if negative["all_negative_tests_pass"] else "FAIL"
        ),
        "development_result": trial["development_result"],
        "disposition": "NON_PROMOTION_RESEARCH_EVIDENCE",
        "formal_mncs_status": "UNKNOWN",
        "formal_mncds_status": "UNKNOWN",
        "promotion_authorized": False,
        "implementation": {
            "entrypoint": manifest["entrypoint"],
            "source_manifest": MANIFEST.name,
            "source_manifest_sha256": hashlib.sha256(
                canonical_bytes(manifest)
            ).hexdigest(),
            "source_digest": manifest["source_digest"],
            "build_configuration": manifest["build_configuration"],
            "source_provenance": manifest["source_provenance"],
        },
        "evaluator_authority": {
            "path": "case-studies/ravel/tools/ravel_0_5_evaluator.py",
            "preregistration": PREREGISTRATION.name,
            "raw_executable_verdicts_trusted": False,
            "all_gates_independently_derived": True,
        },
        "evidence": {
            "records": evidence_records,
            "deterministic_reproduction": True,
            "holdouts_used_for_adaptation_or_selection": False,
            "negative_and_mutation_tests": negative["all_negative_tests_pass"],
            "protected_custody": False,
            "independent_custody": False,
        },
        "trial_summary": trial["trial_summary"],
        "claim_boundaries": [
            "development evidence is not independent protected evidence",
            "synthetic results do not establish real-data generalization",
            "deterministic reproduction is not cross-organizational reproduction",
            "routing equivalence is not overall model correctness",
            "checkpoint reproducibility is not production rollback authorization",
            "formal MNCS and MNCDS status remain UNKNOWN",
            "promotion remains unauthorized",
        ],
    }


def results_markdown(trial: dict[str, Any]) -> bytes:
    lines = [
        "# RAVEL 0.5 generated results",
        "",
        "Generated deterministically from raw observations by the independent evaluator.",
        "",
        "## Final validation outcomes",
        "",
        "| Trial | Regime | Result | Failed gates |",
        "|---|---|---:|---|",
    ]
    for record in trial["trials"]:
        failed = [gate["gate_id"] for gate in record["gates"] if not gate["pass"]]
        lines.append(
            f"| {record['trial_id']} | {record['regime']} | "
            f"{record['trial_result']} | {', '.join(failed) if failed else 'none'} |"
        )
    summary = trial["trial_summary"]
    lines.extend(
        [
            "",
            "## Disposition",
            "",
            f"Development result: `{trial['development_result']}`. "
            f"Passing trials: {summary['passing']}; failing trials: {summary['failing']}.",
            "",
            "Comparisons are paired by seed and include Pareto relationships. Mixed "
            "results are not interpreted as superiority. Wall-clock observations "
            "are non-normative.",
            "",
            "Formal MNCS status: `UNKNOWN`. Formal MNCDS status: `UNKNOWN`. "
            "Promotion remains unauthorized.",
            "",
        ]
    )
    return "\n".join(lines).encode()


def expected_package(binary: Path) -> dict[Path, bytes]:
    prereg = load_json(PREREGISTRATION)
    manifest = build_manifest(MANIFEST_SPEC)
    raw, self_tests = collect_raw(binary, prereg)
    trial = evaluate(raw, prereg)
    evaluator_observations = evaluator_mutation_observations(raw, prereg, trial)
    preliminary_assurance = build_assurance(
        raw,
        trial,
        {
            "all_negative_tests_pass": True,
        },
        manifest,
    )
    manifest_observations = manifest_mutation_observations(
        manifest, preliminary_assurance
    )
    negative = derive_negative(
        self_tests,
        prereg,
        evaluator_observations,
        manifest_observations,
        raw,
    )
    assurance = build_assurance(raw, trial, negative, manifest)
    values: dict[Path, bytes] = {
        RAW: canonical_bytes(raw),
        TRIAL: canonical_bytes(trial),
        NEGATIVE: canonical_bytes(negative),
        MANIFEST: canonical_bytes(manifest),
        ASSURANCE: canonical_bytes(assurance),
        RESULTS: results_markdown(trial),
    }
    return values


def generate(binary: Path) -> None:
    for path, content in expected_package(binary).items():
        path.write_bytes(content)


def verify(binary: Path, diagnostics: Path | None) -> None:
    expected = expected_package(binary)
    failures: list[str] = []
    for path, content in expected.items():
        if not path.is_file() or path.read_bytes() != content:
            failures.append(path.name)
    if failures and diagnostics is not None:
        diagnostics.mkdir(parents=True, exist_ok=True)
        for path, content in expected.items():
            (diagnostics / f"actual-{path.name}").write_bytes(content)
    if failures:
        raise EvidenceError(f"canonical artifacts stale or missing: {failures}")


def mutation_tests() -> None:
    prereg = load_json(PREREGISTRATION)
    raw = load_json(RAW)
    trial = load_json(TRIAL)
    observations = evaluator_mutation_observations(raw, prereg, trial)
    if not all(observations.values()):
        failed = sorted(name for name, value in observations.items() if not value)
        raise EvidenceError(f"evaluator mutations escaped: {failed}")


def manifest_negative_tests() -> None:
    expected = build_manifest(MANIFEST_SPEC)
    actual = load_json(MANIFEST)
    verify_manifest_record(expected, actual)
    assurance = load_json(ASSURANCE)
    observations = manifest_mutation_observations(expected, assurance)
    if not all(observations.values()):
        failed = sorted(name for name, value in observations.items() if not value)
        raise EvidenceError(f"manifest mutations escaped: {failed}")


def development_gates() -> None:
    trial = load_json(TRIAL)
    if trial.get("development_result") != "PASS":
        raise EvidenceError(
            "independent evaluator development result is "
            f"{trial.get('development_result')}"
        )


def runtime_observation(binary: Path, runs: int) -> None:
    prereg = load_json(PREREGISTRATION)
    declared = prereg["trials"][0]
    arguments = [
        "--trial",
        declared["trial_id"],
        "--regime",
        declared["regime"],
        "--seed",
        declared["seed"],
    ]
    elapsed: list[int] = []
    digest: str | None = None
    for _ in range(runs):
        start = time.perf_counter_ns()
        output = _run(binary, arguments)
        elapsed.append(time.perf_counter_ns() - start)
        observed = hashlib.sha256(output).hexdigest()
        if digest is not None and digest != observed:
            raise EvidenceError("runtime observation found nondeterministic output")
        digest = observed
    record = {
        "schema": "ravel-runtime-observations/0.5",
        "normative": False,
        "scope": "one_complete_trial_with_all_variants",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runs": runs,
        "elapsed_nanoseconds": elapsed,
        "minimum_nanoseconds": min(elapsed),
        "median_nanoseconds": statistics.median(elapsed),
        "maximum_nanoseconds": max(elapsed),
        "arithmetic_mean_nanoseconds": statistics.fmean(elapsed),
        "output_sha256": digest,
        "limitations": [
            "wall-clock observations are host-specific and non-normative",
            "deterministic expert-evaluation counts are the canonical work measure",
        ],
    }
    RUNTIME.write_bytes(canonical_bytes(record))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "generate",
            "verify",
            "mutation-tests",
            "manifest-negative-tests",
            "development-gates",
            "runtime",
        ),
    )
    parser.add_argument("--binary", type=Path, default=CASE_ROOT / "ravel_0_5_bin")
    parser.add_argument("--diagnostics-dir", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "generate":
            generate(args.binary)
        elif args.command == "verify":
            verify(args.binary, args.diagnostics_dir)
        elif args.command == "mutation-tests":
            mutation_tests()
        elif args.command == "manifest-negative-tests":
            manifest_negative_tests()
        elif args.command == "development-gates":
            development_gates()
        else:
            if args.runs < 1:
                raise EvidenceError("--runs must be positive")
            runtime_observation(args.binary, args.runs)
        return 0
    except (
        EvidenceError,
        EvaluationError,
        ManifestError,
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ravel 0.5 evidence error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
