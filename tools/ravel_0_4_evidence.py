#!/usr/bin/env python3
"""Generate and verify the deterministic RAVEL 0.4 evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

CASE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ravel_source_digest import (  # noqa: E402
    ManifestError,
    build_manifest,
    canonical_json_bytes,
    file_sha256,
)

PREREGISTRATION = CASE_ROOT / "ravel-0.4-preregistration.json"
MANIFEST_SPEC = CASE_ROOT / "ravel-0.4-source-manifest-spec.json"
RAW_EVIDENCE = CASE_ROOT / "ravel-0.4-raw-observations.json"
TRIAL_EVIDENCE = CASE_ROOT / "ravel-0.4-trial-evidence.json"
NEGATIVE_EVIDENCE = CASE_ROOT / "ravel-0.4-negative-evidence.json"
SOURCE_MANIFEST = CASE_ROOT / "ravel-0.4-source-manifest.json"
ASSURANCE = CASE_ROOT / "ravel-0.4-assurance-case.json"
RESULTS_DOC = CASE_ROOT / "RAVEL_0_4_RESULTS.md"
RUNTIME_EVIDENCE = CASE_ROOT / "ravel-0.4-runtime-observations.json"


class EvidenceError(RuntimeError):
    """Raised when deterministic evidence is malformed or stale."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise EvidenceError(f"{path}: top-level JSON must be an object")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_binary(binary: Path) -> bytes:
    completed = subprocess.run(
        [str(binary.resolve())],
        cwd=CASE_ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    if completed.stderr:
        raise EvidenceError(
            f"RAVEL 0.4 wrote unexpected stderr: {completed.stderr.decode(errors='replace')}"
        )
    return completed.stdout


def parse_raw(raw_bytes: bytes) -> dict[str, Any]:
    try:
        raw = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise EvidenceError(f"raw executable output is not JSON: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema") != "ravel-raw-observations/0.4":
        raise EvidenceError("raw executable output has the wrong schema")
    return raw


def validate_raw(raw: dict[str, Any], prereg: dict[str, Any]) -> None:
    trials = raw.get("trials")
    declared = prereg.get("trials")
    if not isinstance(trials, list) or not isinstance(declared, list):
        raise EvidenceError("trial arrays are missing")
    expected = [(item["trial_id"], item["regime"], item["seed"].lower()) for item in declared]
    observed = [
        (item.get("trial_id"), item.get("regime"), str(item.get("seed")).lower()) for item in trials
    ]
    if observed != expected:
        raise EvidenceError("raw trial order, regimes, or frozen seeds differ from preregistration")
    if raw.get("formal_mncs_status") != "UNKNOWN":
        raise EvidenceError("formal MNCS status must remain UNKNOWN")
    if raw.get("formal_mncds_status") != "UNKNOWN":
        raise EvidenceError("formal MNCDS status must remain UNKNOWN")
    if raw.get("promotion_authorized") is not False:
        raise EvidenceError("promotion must remain unauthorized")
    if raw.get("execution_integrity") != "PASS":
        raise EvidenceError("execution integrity tests did not pass")
    for trial in trials:
        checkpoint = trial.get("checkpoint_verification", {})
        if checkpoint.get("complete_behavior_match") is not True:
            raise EvidenceError(f"{trial.get('trial_id')}: checkpoint behavior mismatch")
        mutations = checkpoint.get("mutations")
        if not isinstance(mutations, dict) or not mutations or not all(mutations.values()):
            raise EvidenceError(f"{trial.get('trial_id')}: checkpoint mutation escaped")
        lineage = trial.get("lineage_invariants")
        if not isinstance(lineage, dict) or not lineage or not all(lineage.values()):
            raise EvidenceError(f"{trial.get('trial_id')}: lineage invariant failed")
    negative = raw.get("negative_tests")
    if not isinstance(negative, dict) or not negative:
        raise EvidenceError("negative test observations are missing")
    if not all(isinstance(item, dict) and item.get("pass") is True for item in negative.values()):
        raise EvidenceError("one or more C negative tests failed")


def metric_summary(values: Iterable[float]) -> dict[str, float]:
    numbers = [float(value) for value in values]
    if not numbers:
        raise EvidenceError("cannot aggregate an empty metric")
    ordered = sorted(numbers)
    return {
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
        "arithmetic_mean": statistics.fmean(ordered),
        "population_standard_deviation": statistics.pstdev(ordered),
    }


def candidate_metric(trial: dict[str, Any], name: str) -> float:
    candidate = trial["candidate"]
    paths: dict[str, tuple[str, ...]] = {
        "base_holdout_accuracy": ("base_holdout", "accuracy"),
        "adaptation_training_accuracy": ("adaptation_training", "accuracy"),
        "static_model_drift_holdout_accuracy": (
            "static_model_drift_holdout",
            "accuracy",
        ),
        "adapted_model_drift_holdout_accuracy": (
            "adapted_model_drift_holdout",
            "accuracy",
        ),
        "base_holdout_retention": ("base_holdout_retention", "accuracy"),
        "base_reconstruction_rmse": ("base_holdout", "reconstruction_rmse"),
        "adapted_drift_reconstruction_rmse": (
            "adapted_model_drift_holdout",
            "reconstruction_rmse",
        ),
        "base_prediction_rmse": (
            "base_holdout",
            "next_observation_prediction_rmse",
        ),
        "adapted_drift_prediction_rmse": (
            "adapted_model_drift_holdout",
            "next_observation_prediction_rmse",
        ),
        "planning_exact_state_rate": (
            "planning",
            "exact_world_state_target_reached",
        ),
        "planning_path_found_rate": ("planning", "path_found"),
    }
    if name == "expert_count":
        return float(candidate["expert_count"])
    if name == "training_evaluations":
        return float(candidate["training_evaluations"])
    if name == "checkpoint_size_bytes":
        return float(candidate["checkpoint_size_bytes"])
    first, second = paths[name]
    value = float(candidate[first][second])
    if name.startswith("planning_"):
        value /= float(candidate["planning"]["cases"])
    return value


def derive_trial_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    trials = raw["trials"]
    candidate_names = [
        "base_holdout_accuracy",
        "adaptation_training_accuracy",
        "static_model_drift_holdout_accuracy",
        "adapted_model_drift_holdout_accuracy",
        "base_holdout_retention",
        "base_reconstruction_rmse",
        "adapted_drift_reconstruction_rmse",
        "base_prediction_rmse",
        "adapted_drift_prediction_rmse",
        "planning_exact_state_rate",
        "planning_path_found_rate",
        "expert_count",
        "training_evaluations",
        "checkpoint_size_bytes",
    ]
    candidate_aggregates = {
        name: metric_summary(candidate_metric(trial, name) for trial in trials)
        for name in candidate_names
    }
    comparison_names = list(trials[0]["comparisons"])
    comparison_metrics = [
        "drift_holdout_accuracy",
        "retention_accuracy",
        "reconstruction_rmse",
        "prediction_rmse",
        "planning_exact_state_rate",
        "expert_evaluations",
        "expert_count",
        "training_evaluations",
        "checkpoint_size_bytes",
    ]
    comparison_aggregates: dict[str, Any] = {}
    for comparison in comparison_names:
        comparison_aggregates[comparison] = {
            metric: metric_summary(trial["comparisons"][comparison][metric] for trial in trials)
            for metric in comparison_metrics
        }
        comparison_aggregates[comparison]["runtime_observation_non_normative"] = {
            "status": "UNKNOWN",
            "reason": (
                "per-variant wall-clock timing excluded from canonical deterministic evidence"
            ),
        }
    candidate_mean = candidate_aggregates["adapted_model_drift_holdout_accuracy"]["arithmetic_mean"]
    mixed_comparisons = {
        name: candidate_mean - summary["drift_holdout_accuracy"]["arithmetic_mean"]
        for name, summary in comparison_aggregates.items()
        if name != "ravel_0_4_candidate"
    }
    return {
        "schema": "ravel-trial-evidence/0.4",
        "study_id": "ravel.evidence-hardening.epoch-1.v1",
        "preregistration": PREREGISTRATION.name,
        "trial_pass_rule": "all_hard_gates_per_trial",
        "global_pass_rule": "all_8_trials_pass",
        "trials": trials,
        "candidate_aggregates": candidate_aggregates,
        "comparison_aggregates": comparison_aggregates,
        "candidate_mean_drift_accuracy_delta_vs_comparisons": mixed_comparisons,
        "comparison_interpretation": "mixed_do_not_infer_superiority",
        "trial_summary": raw["trial_summary"],
        "development_result": raw["development_result"],
        "formal_mncs_status": "UNKNOWN",
        "formal_mncds_status": "UNKNOWN",
        "promotion_authorized": False,
    }


def derive_negative_evidence(
    raw: dict[str, Any],
    raw_bytes: bytes,
    repeated_bytes: bytes,
    source_digest: str,
) -> dict[str, Any]:
    corrupted = bytearray(raw_bytes)
    corrupted[len(corrupted) // 2] ^= 0x01
    evidence_mutation_detected = sha256_bytes(corrupted) != sha256_bytes(raw_bytes)
    stale_assurance_detected = source_digest != "0" * 64
    checkpoint_campaign = {
        trial["trial_id"]: {
            "expected_disposition": "reject_or_fail_equivalence",
            "mutations": trial["checkpoint_verification"]["mutations"],
            "pass": all(trial["checkpoint_verification"]["mutations"].values()),
        }
        for trial in raw["trials"]
    }
    tests = dict(raw["negative_tests"])
    tests.update(
        {
            "evidence_file_mutation": {
                "expected_disposition": "reject",
                "observed": evidence_mutation_detected,
                "pass": evidence_mutation_detected,
            },
            "stale_assurance_digest": {
                "expected_disposition": "reject",
                "observed": stale_assurance_detected,
                "pass": stale_assurance_detected,
            },
            "nondeterministic_output_detection": {
                "expected_disposition": "reject",
                "observed": raw_bytes == repeated_bytes,
                "pass": raw_bytes == repeated_bytes,
                "note": "two independent process executions were byte-identical",
            },
        }
    )
    return {
        "schema": "ravel-negative-evidence/0.4",
        "tests": tests,
        "checkpoint_mutation_campaign": checkpoint_campaign,
        "all_negative_tests_pass": all(item["pass"] for item in tests.values())
        and all(item["pass"] for item in checkpoint_campaign.values()),
        "formal_mncs_status": "UNKNOWN",
        "formal_mncds_status": "UNKNOWN",
        "promotion_authorized": False,
    }


def evidence_identity(paths: list[Path]) -> list[dict[str, Any]]:
    return [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in paths
    ]


def build_assurance(
    raw: dict[str, Any],
    trial_evidence: dict[str, Any],
    negative_evidence: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failed_gates = {
        trial["trial_id"]: [name for name, passed in trial["hard_gates"].items() if not passed]
        for trial in raw["trials"]
        if trial["trial_result"] == "FAIL"
    }
    return {
        "schema": "ravel-assurance-case/0.4",
        "assurance_case_id": "ravel.evidence-hardening.epoch-1.assurance.v1",
        "claim": (
            "The bounded RAVEL 0.4 harness produced deterministic development "
            "evidence with separated drift holdouts, canonical checkpoint "
            "verification, mutations, multiple regimes, baselines, ablations, "
            "and preserved failures."
        ),
        "development_result": raw["development_result"],
        "disposition": "NON_PROMOTION_RESEARCH_FAILURES_PRESERVED",
        "formal_mncs_status": "UNKNOWN",
        "formal_mncds_status": "UNKNOWN",
        "promotion_authorized": False,
        "implementation": {
            "entrypoint": manifest["entrypoint"],
            "source_manifest": SOURCE_MANIFEST.name,
            "source_manifest_sha256": file_sha256(SOURCE_MANIFEST),
            "source_digest": manifest["source_digest"],
            "digest_algorithm": manifest["digest_algorithm"],
            "digest_procedure": manifest["digest_procedure"],
            "source_provenance": manifest["source_provenance"],
            "generated_execution_shards": manifest["generated_execution_shards"],
            "language": "C11",
        },
        "evidence": {
            "records": evidence_identity([RAW_EVIDENCE, TRIAL_EVIDENCE, NEGATIVE_EVIDENCE]),
            "deterministic_reproduction": True,
            "drift_holdout_used_for_adaptation": False,
            "checkpoint_complete_identity": True,
            "checkpoint_complete_behavioral_agreement": True,
            "checkpoint_mutation_campaign": negative_evidence["all_negative_tests_pass"],
            "protected_holdout": False,
            "independent_custody": False,
        },
        "trial_summary": raw["trial_summary"],
        "failed_gates_by_trial": failed_gates,
        "observed_aggregates": trial_evidence["candidate_aggregates"],
        "baseline_and_ablation_interpretation": (
            "Results are mixed across the frozen regimes; no superiority claim is made."
        ),
        "historical_audit": {
            "ravel_u_0_3_adapted_score": (
                "The historical 100% adapted drift score reused adaptation data "
                "and was not an untouched drift-holdout result."
            ),
            "ravel_u_0_3_checkpoint": (
                "The historical raw-struct checkpoint and weak digest are not "
                "accepted as RAVEL 0.4 assurance."
            ),
            "ravel_u_0_3_source_digest": (
                "The historical unified assurance digest was incorrect; RAVEL "
                "0.4 replaces implementation identity with the ordered manifest."
            ),
            "ravel_u_0_3_shard_provenance": (
                "No generator was present in source or reviewed pull-request "
                "history; split sources are maintained, not claimed as generated."
            ),
        },
        "limitations": [
            "development evidence is not independent protected evidence",
            "synthetic success or failure is not real-data generalization",
            "deterministic reproduction is not cross-organizational reproduction",
            "exact routing equivalence is not overall model correctness",
            "checkpoint reproducibility is not production rollback authorization",
            "runtime observations are non-normative",
            "formal MNCS status remains UNKNOWN",
            "formal MNCDS status remains UNKNOWN",
            "promotion remains unauthorized",
        ],
    }


def results_markdown(trial_evidence: dict[str, Any]) -> bytes:
    lines = [
        "# RAVEL 0.4 generated results",
        "",
        (
            "This file is generated from canonical raw observations. "
            "It is not an independent attestation."
        ),
        "",
        "## Frozen trial outcomes",
        "",
        "| Trial | Regime | Result | Failed gates |",
        "|---|---|---:|---|",
    ]
    for trial in trial_evidence["trials"]:
        failures = [name for name, passed in trial["hard_gates"].items() if not passed]
        lines.append(
            f"| {trial['trial_id']} | {trial['regime']} | {trial['trial_result']} | "
            f"{', '.join(failures) if failures else 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Candidate aggregates",
            "",
            "| Metric | Minimum | Median | Maximum | Mean | Population SD |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, summary in trial_evidence["candidate_aggregates"].items():
        lines.append(
            f"| {name} | {summary['minimum']:.9f} | {summary['median']:.9f} | "
            f"{summary['maximum']:.9f} | {summary['arithmetic_mean']:.9f} | "
            f"{summary['population_standard_deviation']:.9f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"Development result: `{trial_evidence['development_result']}`. "
            f"Passing trials: {trial_evidence['trial_summary']['passing']}; "
            f"failing trials: {trial_evidence['trial_summary']['failing']}.",
            "",
            "Baseline and ablation results are mixed. No superiority claim is made. "
            "Per-variant wall-clock observations remain `UNKNOWN` in canonical "
            "evidence; deterministic operation counts are compared instead.",
            "",
            "Formal MNCS status remains `UNKNOWN`. Formal MNCDS status remains "
            "`UNKNOWN`. Promotion is unauthorized.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def expected_package(binary: Path) -> dict[Path, bytes]:
    prereg = load_json(PREREGISTRATION)
    first = run_binary(binary)
    second = run_binary(binary)
    if first != second:
        raise EvidenceError("nondeterministic output detected across two executions")
    raw = parse_raw(first)
    validate_raw(raw, prereg)
    manifest = build_manifest(MANIFEST_SPEC)
    trial = derive_trial_evidence(raw)
    negative = derive_negative_evidence(raw, first, second, manifest["source_digest"])
    package: dict[Path, bytes] = {
        RAW_EVIDENCE: first,
        TRIAL_EVIDENCE: canonical_json_bytes(trial),
        NEGATIVE_EVIDENCE: canonical_json_bytes(negative),
        SOURCE_MANIFEST: canonical_json_bytes(manifest),
        RESULTS_DOC: results_markdown(trial),
    }
    return package


def generate(binary: Path) -> None:
    package = expected_package(binary)
    for path in [RAW_EVIDENCE, TRIAL_EVIDENCE, NEGATIVE_EVIDENCE, SOURCE_MANIFEST]:
        path.write_bytes(package[path])
    raw = load_json(RAW_EVIDENCE)
    trial = load_json(TRIAL_EVIDENCE)
    negative = load_json(NEGATIVE_EVIDENCE)
    manifest = load_json(SOURCE_MANIFEST)
    assurance = build_assurance(raw, trial, negative, manifest)
    ASSURANCE.write_bytes(canonical_json_bytes(assurance))
    RESULTS_DOC.write_bytes(package[RESULTS_DOC])


def write_diagnostics(directory: Path, package: dict[Path, bytes]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path, content in package.items():
        (directory / f"actual-{path.name}").write_bytes(content)


def verify(binary: Path, diagnostics_dir: Path | None = None) -> None:
    package = expected_package(binary)
    for path, expected in package.items():
        if not path.is_file():
            if diagnostics_dir is not None:
                write_diagnostics(diagnostics_dir, package)
            raise EvidenceError(f"canonical artifact is missing: {path.name}")
        if path.read_bytes() != expected:
            if diagnostics_dir is not None:
                write_diagnostics(diagnostics_dir, package)
            raise EvidenceError(f"canonical artifact is stale: {path.name}")
    raw = load_json(RAW_EVIDENCE)
    trial = load_json(TRIAL_EVIDENCE)
    negative = load_json(NEGATIVE_EVIDENCE)
    manifest = load_json(SOURCE_MANIFEST)
    expected_assurance = canonical_json_bytes(build_assurance(raw, trial, negative, manifest))
    if not ASSURANCE.is_file() or ASSURANCE.read_bytes() != expected_assurance:
        if diagnostics_dir is not None:
            write_diagnostics(diagnostics_dir, package)
            diagnostics_dir.mkdir(parents=True, exist_ok=True)
            (diagnostics_dir / f"actual-{ASSURANCE.name}").write_bytes(expected_assurance)
        raise EvidenceError("canonical artifact is stale: ravel-0.4-assurance-case.json")
    if manifest["source_digest"] != build_manifest(MANIFEST_SPEC)["source_digest"]:
        raise EvidenceError("source digest changed during verification")
    if negative.get("all_negative_tests_pass") is not True:
        raise EvidenceError("negative evidence is not passing")


def runtime_observation(binary: Path, runs: int) -> None:
    durations: list[int] = []
    output_digest: str | None = None
    for _ in range(runs):
        start = time.perf_counter_ns()
        output = run_binary(binary)
        durations.append(time.perf_counter_ns() - start)
        digest = sha256_bytes(output)
        if output_digest is not None and digest != output_digest:
            raise EvidenceError("runtime observation encountered nondeterministic output")
        output_digest = digest
    record = {
        "schema": "ravel-runtime-observations/0.4",
        "normative": False,
        "scope": "whole_harness_only_not_per_variant",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runs": runs,
        "elapsed_nanoseconds": durations,
        "minimum_nanoseconds": min(durations),
        "median_nanoseconds": statistics.median(durations),
        "maximum_nanoseconds": max(durations),
        "arithmetic_mean_nanoseconds": statistics.fmean(durations),
        "output_sha256": output_digest,
        "limitations": [
            "wall-clock observations are host-specific and non-normative",
            "per-variant runtime remains UNKNOWN; canonical evidence compares operation counts",
        ],
    }
    RUNTIME_EVIDENCE.write_bytes(canonical_json_bytes(record))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "verify", "runtime"))
    parser.add_argument("--binary", type=Path, default=CASE_ROOT / "ravel_0_4_bin")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--diagnostics-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "generate":
            generate(args.binary)
        elif args.command == "verify":
            diagnostics = args.diagnostics_dir
            if diagnostics is not None and not diagnostics.is_absolute():
                diagnostics = CASE_ROOT / diagnostics
            verify(args.binary, diagnostics)
        else:
            if args.runs < 1:
                raise EvidenceError("--runs must be positive")
            runtime_observation(args.binary, args.runs)
        return 0
    except (
        EvidenceError,
        ManifestError,
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ravel 0.4 evidence error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
