#!/usr/bin/env python3
"""Independent RAVEL 0.5 raw-observation evaluator.

The C harness emits integer observations and integrity facts. This module is the
only authority that loads preregistered thresholds, derives metrics and gates,
and determines trial and global development results.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

Q20_SCALE = 1_048_576
DIMENSIONS = 8
UINT64_MASK = (1 << 64) - 1

CHECKPOINT_MUTATION_KEYS = {
    "retrieval_key_component",
    "reconstruction_component",
    "next_observation_component",
    "label",
    "label_count",
    "lineage",
    "transition_graph_edge",
    "transition_support",
    "anchored_status",
    "payload_byte",
    "checkpoint_truncation",
    "appended_unexpected_byte",
    "incorrect_schema_version",
    "checkpoint_substitution",
}

LINEAGE_INVARIANT_KEYS = {
    "sibling_generation_equality",
    "parent_child_generation_increment",
    "lineage_uniqueness",
    "repeated_descendant_splitting",
    "no_accidental_lineage_reuse",
    "deterministic_topology_reproduction",
}

DATASET_KEYS = {
    "base_training",
    "base_holdout",
    "drift_adaptation_training",
    "drift_holdout",
    "original_task_retention_holdout",
    "planning_cases",
}

DATASET_SEED_XORS = {
    "base_training": 0x4241534554524149,
    "base_holdout": 0x42415345484F4C44,
    "drift_adaptation_training": 0x414441505454524E,
    "drift_holdout": 0x4452494654484F4C,
    "original_task_retention_holdout": 0x524554454E54494F,
    "planning_cases": 0x504C414E43415345,
}


class EvaluationError(RuntimeError):
    """Raised when raw or preregistered evidence is not admissible."""


def _reject_constant(value: str) -> None:
    raise EvaluationError(f"non-finite JSON constant rejected: {value}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(), parse_constant=_reject_constant)
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"cannot load {path}: {error}") from error


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationError(f"{context}: expected object")
    return value


def require_exact_keys(
    value: dict[str, Any], keys: set[str], context: str
) -> None:
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        raise EvaluationError(
            f"{context}: key mismatch missing={missing} unknown={unknown}"
        )


def require_int(
    value: Any, context: str, minimum: int = 0, maximum: int | None = None
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvaluationError(f"{context}: expected integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise EvaluationError(f"{context}: integer outside declared range")
    return value


def require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationError(f"{context}: expected boolean")
    return value


def require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationError(f"{context}: expected non-empty string")
    return value


def _validate_hex(value: Any, context: str, digits: int) -> str:
    text = require_string(value, context)
    if len(text) != digits or any(c not in "0123456789abcdef" for c in text):
        raise EvaluationError(f"{context}: expected {digits} lowercase hex digits")
    return text


def _validate_u64_hex(value: Any, context: str) -> int:
    text = require_string(value, context)
    if len(text) != 18 or not text.startswith("0x"):
        raise EvaluationError(f"{context}: expected 0x plus 16 lowercase hex digits")
    _validate_hex(text[2:], context, 16)
    return int(text[2:], 16)


def _mix64(value: int) -> int:
    value &= UINT64_MASK
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & UINT64_MASK
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & UINT64_MASK
    return (value ^ (value >> 31)) & UINT64_MASK


def _derive_validation_seed(root: int, regime: str, index: int) -> int:
    framed = (
        root.to_bytes(8, "big")
        + b"validation\0"
        + regime.encode("utf-8")
        + b"\0"
        + index.to_bytes(4, "big")
    )
    return int.from_bytes(hashlib.sha256(framed).digest()[:8], "big")


EVAL_KEYS = {
    "samples",
    "rejected",
    "correct",
    "reconstruction_sse_q20",
    "prediction_sse_q20",
    "prediction_samples",
    "transition_correct",
    "transition_supported",
    "transition_unknown",
    "routing_certification_count",
    "routed_complete_mismatches",
    "expert_evaluations",
    "classification_checksum",
    "reconstruction_checksum",
    "prediction_checksum",
    "transition_checksum",
}

PLAN_KEYS = {
    "cases",
    "path_found",
    "exact_world_state_target_reached",
    "goal_expert_reached",
    "belief_set_target_reached",
    "executed_path_length",
    "optimal_path_length",
    "path_length_regret",
    "graph_disconnection_failures",
    "no_supported_edge_failures",
    "transition_model_error_failures",
    "state_aliasing_failures",
    "expansions",
    "checksum",
}


def validate_eval(value: Any, context: str) -> dict[str, Any]:
    record = require_object(value, context)
    require_exact_keys(record, EVAL_KEYS, context)
    for key in EVAL_KEYS - {
        "classification_checksum",
        "reconstruction_checksum",
        "prediction_checksum",
        "transition_checksum",
    }:
        require_int(record[key], f"{context}.{key}")
    samples = record["samples"]
    prediction_samples = record["prediction_samples"]
    transition_supported = record["transition_supported"]
    if record["correct"] > samples or prediction_samples > samples:
        raise EvaluationError(f"{context}: count exceeds samples")
    if transition_supported > samples or record["transition_correct"] > transition_supported:
        raise EvaluationError(f"{context}: transition count contradiction")
    if transition_supported + record["transition_unknown"] != samples:
        raise EvaluationError(f"{context}: transition support partition contradiction")
    for key in (
        "classification_checksum",
        "reconstruction_checksum",
        "prediction_checksum",
        "transition_checksum",
    ):
        _validate_hex(record[key], f"{context}.{key}", 16)
    return record


def validate_plan(value: Any, context: str) -> dict[str, Any]:
    record = require_object(value, context)
    require_exact_keys(record, PLAN_KEYS, context)
    for key in PLAN_KEYS - {"checksum"}:
        require_int(record[key], f"{context}.{key}")
    cases = record["cases"]
    for key in (
        "path_found",
        "exact_world_state_target_reached",
        "goal_expert_reached",
        "belief_set_target_reached",
        "graph_disconnection_failures",
        "no_supported_edge_failures",
        "transition_model_error_failures",
        "state_aliasing_failures",
    ):
        if record[key] > cases:
            raise EvaluationError(f"{context}.{key}: exceeds cases")
    if record["path_found"] + record["graph_disconnection_failures"] + record[
        "no_supported_edge_failures"
    ] != cases:
        raise EvaluationError(f"{context}: planning disposition contradiction")
    _validate_hex(record["checksum"], f"{context}.checksum", 16)
    return record


def derive_eval(record: dict[str, Any]) -> dict[str, float | int]:
    samples = record["samples"]
    prediction_samples = record["prediction_samples"]
    supported = record["transition_supported"]
    if samples == 0:
        raise EvaluationError("evaluation has zero samples")
    result: dict[str, float | int] = {
        "accuracy": record["correct"] / samples,
        "reconstruction_rmse": math.sqrt(
            (record["reconstruction_sse_q20"] / Q20_SCALE)
            / (samples * DIMENSIONS)
        ),
        "prediction_rmse": math.sqrt(
            (record["prediction_sse_q20"] / Q20_SCALE)
            / (prediction_samples * DIMENSIONS)
        )
        if prediction_samples
        else math.inf,
        "transition_accuracy": record["transition_correct"] / supported
        if supported
        else 0.0,
        "transition_support_rate": supported / samples,
        "routing_mismatches": record["routed_complete_mismatches"],
        "expert_evaluations": record["expert_evaluations"],
    }
    if not all(
        math.isfinite(value)
        for value in result.values()
        if isinstance(value, float)
    ):
        raise EvaluationError("derived evaluation contains non-finite metric")
    return result


def derive_plan(record: dict[str, Any]) -> dict[str, float | int]:
    cases = record["cases"]
    if cases == 0:
        raise EvaluationError("planning has zero cases")
    return {
        "path_found_rate": record["path_found"] / cases,
        "exact_state_rate": record["exact_world_state_target_reached"] / cases,
        "goal_expert_rate": record["goal_expert_reached"] / cases,
        "belief_set_rate": record["belief_set_target_reached"] / cases,
        "path_length_regret": record["path_length_regret"],
        "graph_disconnections": record["graph_disconnection_failures"],
        "unsupported_edge_failures": record["no_supported_edge_failures"],
        "transition_model_failures": record["transition_model_error_failures"],
        "state_aliasing_failures": record["state_aliasing_failures"],
    }


def _validate_replay(value: Any, context: str) -> dict[str, Any]:
    keys = {
        "selected",
        "unique",
        "labels_covered",
        "actions_covered",
        "states_covered",
        "assigned_experts_covered",
        "transition_pairs_covered",
        "rare_cases_selected",
        "high_loss_cases_selected",
        "selection_checksum",
    }
    record = require_object(value, context)
    require_exact_keys(record, keys, context)
    for key in keys - {"selection_checksum"}:
        require_int(record[key], f"{context}.{key}")
    if record["unique"] > record["selected"]:
        raise EvaluationError(f"{context}: unique exceeds selected")
    _validate_hex(record["selection_checksum"], f"{context}.selection_checksum", 16)
    return record


def _validate_topology(value: Any, context: str) -> dict[str, Any]:
    keys = {
        "accepted_births",
        "rejected_births",
        "accepted_retirements",
        "rejected_retirements",
        "objective_before_q20",
        "objective_after_q20",
        "births",
        "retired_lineages",
        "training_observations",
    }
    record = require_object(value, context)
    require_exact_keys(record, keys, context)
    for key in keys - {"births", "retired_lineages", "training_observations"}:
        require_int(record[key], f"{context}.{key}")
    births = record["births"]
    if not isinstance(births, list) or len(births) != record["accepted_births"]:
        raise EvaluationError(f"{context}: birth trace length mismatch")
    for index, birth in enumerate(births):
        birth = require_object(birth, f"{context}.births[{index}]")
        require_exact_keys(
            birth,
            {"event_index", "normalized_score_q20", "dominant_channel"},
            f"{context}.births[{index}]",
        )
        require_int(birth["event_index"], f"{context}.births[{index}].event_index")
        require_int(
            birth["normalized_score_q20"],
            f"{context}.births[{index}].normalized_score_q20",
        )
        require_int(
            birth["dominant_channel"],
            f"{context}.births[{index}].dominant_channel",
            0,
            7,
        )
    retired = record["retired_lineages"]
    if not isinstance(retired, list) or len(retired) != record["accepted_retirements"]:
        raise EvaluationError(f"{context}: retirement trace length mismatch")
    for index, lineage in enumerate(retired):
        _validate_hex(lineage, f"{context}.retired_lineages[{index}]", 16)
    training = require_object(record["training_observations"], f"{context}.training")
    require_exact_keys(
        training,
        {
            "expert_evaluations",
            "samples",
            "certified",
            "births",
            "retired",
            "rejected_births",
            "rejected_retirements",
        },
        f"{context}.training",
    )
    for key, item in training.items():
        require_int(item, f"{context}.training.{key}")
    if training["births"] != record["accepted_births"]:
        raise EvaluationError(f"{context}: accepted birth contradiction")
    if training["retired"] != record["accepted_retirements"]:
        raise EvaluationError(f"{context}: accepted retirement contradiction")
    return record


def _validate_variant(value: Any, context: str) -> dict[str, Any]:
    record = require_object(value, context)
    require_exact_keys(
        record,
        {
            "expert_count",
            "training_evaluations",
            "checkpoint_size_bytes",
            "drift_holdout",
            "retention_holdout",
            "planning",
        },
        context,
    )
    require_int(record["expert_count"], f"{context}.expert_count", 1, 80)
    require_int(record["training_evaluations"], f"{context}.training_evaluations")
    require_int(record["checkpoint_size_bytes"], f"{context}.checkpoint_size_bytes")
    validate_eval(record["drift_holdout"], f"{context}.drift_holdout")
    validate_eval(record["retention_holdout"], f"{context}.retention_holdout")
    validate_plan(record["planning"], f"{context}.planning")
    return record


def validate_preregistration(value: Any) -> dict[str, Any]:
    prereg = require_object(value, "preregistration")
    require_exact_keys(
        prereg,
        {
            "schema",
            "study_id",
            "candidate_id",
            "freeze",
            "seed_derivation",
            "datasets_per_trial",
            "dataset_prohibitions",
            "mechanism_constants",
            "trials",
            "comparison_variants",
            "common_gates",
            "regime_gates",
            "global_pass_rule",
            "negative_test_dispositions",
            "formal_status_regardless_of_development_result",
        },
        "preregistration",
    )
    if prereg["schema"] != "ravel-preregistration/0.5":
        raise EvaluationError("unsupported preregistration schema")
    require_string(prereg["study_id"], "preregistration.study_id")
    require_string(prereg["candidate_id"], "preregistration.candidate_id")
    freeze = require_object(prereg["freeze"], "preregistration.freeze")
    require_exact_keys(
        freeze,
        {
            "state",
            "frozen_before_final_validation",
            "development_corpus",
            "final_validation_use",
        },
        "preregistration.freeze",
    )
    if freeze["state"] != "FROZEN" or not require_bool(
        freeze["frozen_before_final_validation"],
        "preregistration.freeze.frozen_before_final_validation",
    ):
        raise EvaluationError("preregistration is not frozen")
    if freeze["final_validation_use"] != "one_shot":
        raise EvaluationError("final validation must be declared one-shot")
    require_string(freeze["development_corpus"], "preregistration.freeze.development")

    derivation = require_object(
        prereg["seed_derivation"], "preregistration.seed_derivation"
    )
    require_exact_keys(
        derivation,
        {
            "root_seed",
            "algorithm",
            "framing",
            "validation_seeds_per_regime",
        },
        "preregistration.seed_derivation",
    )
    if derivation["algorithm"] != "sha256-first-u64-big-endian":
        raise EvaluationError("unsupported validation seed derivation")
    if (
        derivation["framing"]
        != "root_seed_u64_be || utf8('validation\\0') || utf8(regime) || zero_byte || index_u32_be"
    ):
        raise EvaluationError("unsupported validation seed framing")
    root_seed = _validate_u64_hex(
        derivation["root_seed"], "preregistration.seed_derivation.root_seed"
    )
    expected_per_regime = require_int(
        derivation["validation_seeds_per_regime"],
        "validation_seeds_per_regime",
        1,
    )

    datasets = require_object(
        prereg["datasets_per_trial"], "preregistration.datasets_per_trial"
    )
    require_exact_keys(datasets, DATASET_KEYS, "preregistration.datasets_per_trial")
    for name, count in datasets.items():
        require_int(count, f"preregistration.datasets_per_trial.{name}", 1)
    prohibitions = prereg["dataset_prohibitions"]
    if not isinstance(prohibitions, list) or not prohibitions:
        raise EvaluationError("dataset_prohibitions must be a non-empty list")
    for index, prohibition in enumerate(prohibitions):
        require_string(prohibition, f"dataset_prohibitions[{index}]")

    constants = require_object(
        prereg["mechanism_constants"], "preregistration.mechanism_constants"
    )
    require_exact_keys(
        constants,
        {
            "dimensions",
            "classes",
            "actions",
            "states",
            "maximum_experts",
            "checkpoint_schema",
            "evidence_schema",
            "transition_top_k",
            "transition_support_min",
            "replay_count",
            "maximum_adaptation_births",
            "maximum_adaptation_retirements",
            "topology_objective_min_q20",
            "birth_residual_min_q20",
        },
        "preregistration.mechanism_constants",
    )
    for name, constant in constants.items():
        if name == "evidence_schema":
            require_string(constant, f"mechanism_constants.{name}")
        else:
            require_int(constant, f"mechanism_constants.{name}", 0)
    if constants["dimensions"] != DIMENSIONS:
        raise EvaluationError("evaluator dimension schema mismatch")

    trials = prereg["trials"]
    if not isinstance(trials, list) or not trials:
        raise EvaluationError("preregistration.trials must be non-empty list")
    identities: set[str] = set()
    seeds: set[str] = set()
    regimes: dict[str, int] = {}
    for index, trial in enumerate(trials):
        trial = require_object(trial, f"preregistration.trials[{index}]")
        require_exact_keys(
            trial, {"trial_id", "regime", "seed"}, f"preregistration.trials[{index}]"
        )
        trial_id = require_string(trial["trial_id"], f"trials[{index}].trial_id")
        regime = require_string(trial["regime"], f"trials[{index}].regime")
        seed = require_string(trial["seed"], f"trials[{index}].seed")
        seed_value = _validate_u64_hex(seed, f"trials[{index}].seed")
        regime_index = regimes.get(regime, 0)
        derived_seed = _derive_validation_seed(root_seed, regime, regime_index)
        if seed_value != derived_seed:
            raise EvaluationError(
                f"trials[{index}].seed disagrees with frozen derivation"
            )
        if trial_id in identities or seed in seeds:
            raise EvaluationError("duplicate trial id or seed")
        identities.add(trial_id)
        seeds.add(seed)
        regimes[regime] = regimes.get(regime, 0) + 1
    declared_regimes = set(prereg["regime_gates"])
    if set(regimes) != declared_regimes:
        raise EvaluationError("trial regimes do not match regime gate authority")
    if any(count != expected_per_regime for count in regimes.values()):
        raise EvaluationError("unexpected validation seed count per regime")
    variants = prereg["comparison_variants"]
    if (
        not isinstance(variants, list)
        or not variants
        or len(variants) != len(set(variants))
    ):
        raise EvaluationError("comparison_variants must be a unique non-empty list")
    for index, variant in enumerate(variants):
        require_string(variant, f"comparison_variants[{index}]")
    for collection_name in ("common_gates",):
        _validate_gate_list(prereg[collection_name], collection_name)
    for regime, gates in prereg["regime_gates"].items():
        _validate_gate_list(gates, f"regime_gates.{regime}")
    global_rule = require_object(
        prereg["global_pass_rule"], "preregistration.global_pass_rule"
    )
    require_exact_keys(
        global_rule,
        {
            "minimum_passing_trials",
            "minimum_passing_trials_per_regime",
            "all_integrity_gates_required",
        },
        "preregistration.global_pass_rule",
    )
    require_int(
        global_rule["minimum_passing_trials"],
        "global_pass_rule.minimum_passing_trials",
        0,
        len(trials),
    )
    require_int(
        global_rule["minimum_passing_trials_per_regime"],
        "global_pass_rule.minimum_passing_trials_per_regime",
        0,
        expected_per_regime,
    )
    require_bool(
        global_rule["all_integrity_gates_required"],
        "global_pass_rule.all_integrity_gates_required",
    )
    dispositions = require_object(
        prereg["negative_test_dispositions"], "negative_test_dispositions"
    )
    if not dispositions:
        raise EvaluationError("negative_test_dispositions must not be empty")
    for name, disposition in dispositions.items():
        require_string(name, f"negative_test_dispositions.{name}")
        disposition = require_object(disposition, f"negative_test_dispositions.{name}")
        require_exact_keys(
            disposition,
            {"expected_disposition", "expected_observation", "rationale"},
            f"negative_test_dispositions.{name}",
        )
        if disposition["expected_disposition"] not in {
            "reject",
            "fall_back",
            "fail_a_gate",
            "report_UNKNOWN",
            "preserve_non_promotion",
        }:
            raise EvaluationError(f"negative_test_dispositions.{name}: unsupported")
        require_string(
            disposition["rationale"],
            f"negative_test_dispositions.{name}.rationale",
        )
        require_bool(
            disposition["expected_observation"],
            f"negative_test_dispositions.{name}.expected_observation",
        )
    formal = require_object(
        prereg["formal_status_regardless_of_development_result"],
        "formal_status_regardless_of_development_result",
    )
    require_exact_keys(
        formal,
        {"mncs", "mncds", "promotion_authorized"},
        "formal_status_regardless_of_development_result",
    )
    if (
        formal["mncs"] != "UNKNOWN"
        or formal["mncds"] != "UNKNOWN"
        or require_bool(
            formal["promotion_authorized"],
            "formal_status_regardless_of_development_result.promotion_authorized",
        )
    ):
        raise EvaluationError("formal status boundary changed")
    return prereg


def _validate_gate_list(value: Any, context: str) -> None:
    if not isinstance(value, list) or not value:
        raise EvaluationError(f"{context}: expected non-empty gate list")
    identities: set[str] = set()
    for index, gate in enumerate(value):
        gate = require_object(gate, f"{context}[{index}]")
        require_exact_keys(
            gate,
            {"gate_id", "metric", "operator", "value", "rationale"},
            f"{context}[{index}]",
        )
        identity = require_string(gate["gate_id"], f"{context}[{index}].gate_id")
        if identity in identities:
            raise EvaluationError(f"{context}: duplicate gate id")
        identities.add(identity)
        if gate["operator"] not in {"ge", "le", "eq"}:
            raise EvaluationError(f"{context}[{index}]: unsupported operator")
        if isinstance(gate["value"], float) and not math.isfinite(gate["value"]):
            raise EvaluationError(f"{context}[{index}]: non-finite threshold")


def validate_trial(
    trial: Any, expected: dict[str, Any], prereg: dict[str, Any]
) -> dict[str, Any]:
    context = f"trial[{expected['trial_id']}]"
    record = require_object(trial, context)
    require_exact_keys(
        record,
        {
            "schema",
            "trial_id",
            "regime",
            "seed",
            "dataset_seeds",
            "dataset_sizes",
            "checkpoint_format",
            "candidate",
            "integrity",
            "comparisons",
        },
        context,
    )
    if record["schema"] != "ravel-raw-trial/0.5":
        raise EvaluationError(f"{context}: unsupported raw schema")
    for key in ("trial_id", "regime", "seed"):
        if record[key] != expected[key]:
            raise EvaluationError(f"{context}: {key} disagrees with preregistration")
    trial_seed = _validate_u64_hex(record["seed"], f"{context}.seed")
    dataset_seeds = require_object(record["dataset_seeds"], f"{context}.dataset_seeds")
    require_exact_keys(
        dataset_seeds,
        DATASET_KEYS,
        f"{context}.dataset_seeds",
    )
    parsed_dataset_seeds = {
        name: _validate_u64_hex(value, f"{context}.dataset_seeds.{name}")
        for name, value in dataset_seeds.items()
    }
    if len(set(parsed_dataset_seeds.values())) != len(parsed_dataset_seeds):
        raise EvaluationError(f"{context}: dataset seed collision")
    expected_dataset_seeds = {
        name: _mix64(trial_seed ^ xor_value)
        for name, xor_value in DATASET_SEED_XORS.items()
    }
    if parsed_dataset_seeds != expected_dataset_seeds:
        raise EvaluationError(f"{context}: dataset seed derivation mismatch")
    dataset_sizes = require_object(record["dataset_sizes"], f"{context}.dataset_sizes")
    require_exact_keys(
        dataset_sizes,
        DATASET_KEYS,
        f"{context}.dataset_sizes",
    )
    if dataset_sizes != prereg["datasets_per_trial"]:
        raise EvaluationError(f"{context}: partition sizes disagree with preregistration")
    checkpoint = require_object(record["checkpoint_format"], f"{context}.checkpoint")
    require_exact_keys(
        checkpoint,
        {
            "magic_hex",
            "schema_version",
            "byte_order",
            "real_encoding",
            "payload_digest",
            "transition_top_k",
            "transition_support_min",
        },
        f"{context}.checkpoint",
    )
    constants = prereg["mechanism_constants"]
    if checkpoint["schema_version"] != constants["checkpoint_schema"]:
        raise EvaluationError(f"{context}: checkpoint schema mismatch")
    expected_checkpoint = {
        "magic_hex": "524156454c303500",
        "schema_version": constants["checkpoint_schema"],
        "byte_order": "big_endian",
        "real_encoding": "signed_q20_int64",
        "payload_digest": "sha256",
        "transition_top_k": constants["transition_top_k"],
        "transition_support_min": constants["transition_support_min"],
    }
    if checkpoint != expected_checkpoint:
        raise EvaluationError(f"{context}: checkpoint format declaration mismatch")
    candidate = require_object(record["candidate"], f"{context}.candidate")
    require_exact_keys(
        candidate,
        {
            "adaptation_completed",
            "expert_count",
            "base_training_evaluations",
            "adaptation_training_evaluations",
            "checkpoint_size_bytes",
            "model_identity",
            "behavior_identity",
            "base_holdout",
            "adaptation_training",
            "static_model_drift_holdout",
            "adapted_model_drift_holdout",
            "base_holdout_retention",
            "planning",
            "replay",
            "topology",
        },
        f"{context}.candidate",
    )
    require_bool(candidate["adaptation_completed"], f"{context}.adaptation_completed")
    require_int(candidate["expert_count"], f"{context}.expert_count", 1, 80)
    require_int(candidate["base_training_evaluations"], f"{context}.base_training")
    require_int(
        candidate["adaptation_training_evaluations"],
        f"{context}.adaptation_training_evaluations",
    )
    require_int(candidate["checkpoint_size_bytes"], f"{context}.checkpoint_size")
    _validate_hex(candidate["model_identity"], f"{context}.model_identity", 64)
    _validate_hex(candidate["behavior_identity"], f"{context}.behavior_identity", 64)
    for name in (
        "base_holdout",
        "adaptation_training",
        "static_model_drift_holdout",
        "adapted_model_drift_holdout",
        "base_holdout_retention",
    ):
        validate_eval(candidate[name], f"{context}.candidate.{name}")
    validate_plan(candidate["planning"], f"{context}.candidate.planning")
    _validate_replay(candidate["replay"], f"{context}.candidate.replay")
    _validate_topology(candidate["topology"], f"{context}.candidate.topology")
    integrity = require_object(record["integrity"], f"{context}.integrity")
    require_exact_keys(
        integrity,
        {
            "checkpoint_roundtrip",
            "checkpoint_identity_match",
            "checkpoint_behavior_match",
            "checkpoint_mutations",
            "lineage_invariants",
            "unsupported_graph_edge_violations",
        },
        f"{context}.integrity",
    )
    for key in (
        "checkpoint_roundtrip",
        "checkpoint_identity_match",
        "checkpoint_behavior_match",
    ):
        require_bool(integrity[key], f"{context}.integrity.{key}")
    require_int(
        integrity["unsupported_graph_edge_violations"],
        f"{context}.unsupported_graph_edge_violations",
    )
    expected_integrity_keys = {
        "checkpoint_mutations": CHECKPOINT_MUTATION_KEYS,
        "lineage_invariants": LINEAGE_INVARIANT_KEYS,
    }
    for collection, expected_keys in expected_integrity_keys.items():
        values = require_object(integrity[collection], f"{context}.{collection}")
        require_exact_keys(values, expected_keys, f"{context}.{collection}")
        for key, value in values.items():
            require_bool(value, f"{context}.{collection}.{key}")
    comparisons = require_object(record["comparisons"], f"{context}.comparisons")
    if set(comparisons) != set(prereg["comparison_variants"]):
        raise EvaluationError(f"{context}: comparison variant set mismatch")
    for name, variant in comparisons.items():
        _validate_variant(variant, f"{context}.comparisons.{name}")
    candidate_comparison = comparisons["ravel_0_5_candidate"]
    if (
        candidate_comparison["expert_count"] != candidate["expert_count"]
        or candidate_comparison["checkpoint_size_bytes"]
        != candidate["checkpoint_size_bytes"]
        or candidate_comparison["drift_holdout"]
        != candidate["adapted_model_drift_holdout"]
        or candidate_comparison["retention_holdout"]
        != candidate["base_holdout_retention"]
        or candidate_comparison["planning"] != candidate["planning"]
    ):
        raise EvaluationError(f"{context}: candidate comparison contradicts raw candidate")
    return record


def _headroom_improvement(adapted: float, static: float) -> float:
    headroom = 1.0 - static
    if headroom <= 0.0:
        return 0.0 if adapted >= static else adapted - static
    return (adapted - static) / headroom


def derive_trial_metrics(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record["candidate"]
    base = derive_eval(candidate["base_holdout"])
    adaptation = derive_eval(candidate["adaptation_training"])
    static = derive_eval(candidate["static_model_drift_holdout"])
    adapted = derive_eval(candidate["adapted_model_drift_holdout"])
    retention = derive_eval(candidate["base_holdout_retention"])
    planning = derive_plan(candidate["planning"])
    integrity = record["integrity"]
    replay = candidate["replay"]
    topology = candidate["topology"]
    routing_mismatches = sum(
        int(view["routing_mismatches"])
        for view in (base, adaptation, static, adapted, retention)
    )
    metrics: dict[str, Any] = {
        "adaptation_completed": candidate["adaptation_completed"],
        "base_accuracy": base["accuracy"],
        "adaptation_training_accuracy": adaptation["accuracy"],
        "static_drift_accuracy": static["accuracy"],
        "adapted_drift_accuracy": adapted["accuracy"],
        "retention_accuracy": retention["accuracy"],
        "retention_accuracy_delta_from_base": float(retention["accuracy"])
        - float(base["accuracy"]),
        "drift_accuracy_delta": adapted["accuracy"] - static["accuracy"],
        "headroom_normalized_accuracy_improvement": _headroom_improvement(
            float(adapted["accuracy"]), float(static["accuracy"])
        ),
        "base_reconstruction_rmse": base["reconstruction_rmse"],
        "static_reconstruction_rmse": static["reconstruction_rmse"],
        "adapted_reconstruction_rmse": adapted["reconstruction_rmse"],
        "retention_reconstruction_rmse": retention["reconstruction_rmse"],
        "retention_reconstruction_degradation_ratio": (
            float(retention["reconstruction_rmse"])
            - float(base["reconstruction_rmse"])
        )
        / max(float(base["reconstruction_rmse"]), 1e-12),
        "reconstruction_improvement_ratio": (
            float(static["reconstruction_rmse"])
            - float(adapted["reconstruction_rmse"])
        )
        / max(float(static["reconstruction_rmse"]), 1e-12),
        "base_prediction_rmse": base["prediction_rmse"],
        "static_prediction_rmse": static["prediction_rmse"],
        "adapted_prediction_rmse": adapted["prediction_rmse"],
        "retention_prediction_rmse": retention["prediction_rmse"],
        "prediction_improvement_ratio": (
            float(static["prediction_rmse"]) - float(adapted["prediction_rmse"])
        )
        / max(float(static["prediction_rmse"]), 1e-12),
        "retention_prediction_degradation": float(retention["prediction_rmse"])
        - float(base["prediction_rmse"]),
        "static_transition_accuracy": static["transition_accuracy"],
        "adapted_transition_accuracy": adapted["transition_accuracy"],
        "transition_accuracy_delta": float(adapted["transition_accuracy"])
        - float(static["transition_accuracy"]),
        "retention_transition_accuracy_delta": float(
            retention["transition_accuracy"]
        )
        - float(base["transition_accuracy"]),
        "transition_support_rate": adapted["transition_support_rate"],
        "path_found_rate": planning["path_found_rate"],
        "exact_state_rate": planning["exact_state_rate"],
        "belief_set_rate": planning["belief_set_rate"],
        "routing_mismatches": routing_mismatches,
        "expert_count": candidate["expert_count"],
        "accepted_births": topology["accepted_births"],
        "accepted_retirements": topology["accepted_retirements"],
        "training_evaluations": candidate["base_training_evaluations"]
        + candidate["adaptation_training_evaluations"],
        "inference_expert_evaluations": adapted["expert_evaluations"],
        "checkpoint_size_bytes": candidate["checkpoint_size_bytes"],
        "replay_selected": replay["selected"],
        "replay_unique": replay["unique"],
        "replay_labels_covered": replay["labels_covered"],
        "replay_actions_covered": replay["actions_covered"],
        "replay_states_covered": replay["states_covered"],
        "replay_experts_covered": replay["assigned_experts_covered"],
        "replay_transition_pairs_covered": replay["transition_pairs_covered"],
        "checkpoint_roundtrip": integrity["checkpoint_roundtrip"],
        "checkpoint_identity": integrity["checkpoint_identity_match"],
        "checkpoint_behavior": integrity["checkpoint_behavior_match"],
        "checkpoint_mutations": all(integrity["checkpoint_mutations"].values()),
        "lineage_invariants": all(integrity["lineage_invariants"].values()),
        "unsupported_graph_edge_violations": integrity[
            "unsupported_graph_edge_violations"
        ],
    }
    comparison_metrics: dict[str, dict[str, float | int]] = {}
    for name, variant in record["comparisons"].items():
        variant_drift = derive_eval(variant["drift_holdout"])
        variant_retention = derive_eval(variant["retention_holdout"])
        variant_plan = derive_plan(variant["planning"])
        comparison_metrics[name] = {
            "drift_accuracy": variant_drift["accuracy"],
            "retention_accuracy": variant_retention["accuracy"],
            "reconstruction_rmse": variant_drift["reconstruction_rmse"],
            "prediction_rmse": variant_drift["prediction_rmse"],
            "transition_accuracy": variant_drift["transition_accuracy"],
            "transition_support_rate": variant_drift["transition_support_rate"],
            "exact_state_rate": variant_plan["exact_state_rate"],
            "belief_set_rate": variant_plan["belief_set_rate"],
            "expert_evaluations": variant_drift["expert_evaluations"],
            "training_evaluations": variant["training_evaluations"],
            "expert_count": variant["expert_count"],
            "checkpoint_size_bytes": variant["checkpoint_size_bytes"],
        }
    static_comparison = comparison_metrics["no_adaptation_static"]
    matched_compute = comparison_metrics["matched_compute_fixed_topology"]
    no_birth = comparison_metrics["ravel_no_birth_same_replay_iterations"]
    no_retirement = comparison_metrics["ravel_without_retirement_matched_work"]
    periodic_replay = comparison_metrics["periodic_replay_policy"]
    flat_complete = comparison_metrics["flat_64_expert_complete_scan"]
    metrics.update(
        {
            "static_exact_state_rate": static_comparison["exact_state_rate"],
            "static_belief_set_rate": static_comparison["belief_set_rate"],
            "exact_state_rate_delta": float(planning["exact_state_rate"])
            - float(static_comparison["exact_state_rate"]),
            "belief_set_rate_delta": float(planning["belief_set_rate"])
            - float(static_comparison["belief_set_rate"]),
            "matched_compute_drift_accuracy_delta": float(adapted["accuracy"])
            - float(matched_compute["drift_accuracy"]),
            "matched_compute_retention_delta": float(retention["accuracy"])
            - float(matched_compute["retention_accuracy"]),
            "matched_compute_training_evaluation_ratio": float(
                metrics["training_evaluations"]
            )
            / max(float(matched_compute["training_evaluations"]), 1.0),
            "no_birth_drift_accuracy_delta": float(adapted["accuracy"])
            - float(no_birth["drift_accuracy"]),
            "no_retirement_drift_accuracy_delta": float(adapted["accuracy"])
            - float(no_retirement["drift_accuracy"]),
            "balanced_vs_periodic_drift_accuracy_delta": float(adapted["accuracy"])
            - float(periodic_replay["drift_accuracy"]),
            "balanced_vs_periodic_retention_delta": float(retention["accuracy"])
            - float(periodic_replay["retention_accuracy"]),
            "inference_evaluation_ratio_vs_flat64": float(
                metrics["inference_expert_evaluations"]
            )
            / max(float(flat_complete["expert_evaluations"]), 1.0),
            "topology_objective_gain_q20": topology["objective_after_q20"]
            - topology["objective_before_q20"],
        }
    )
    if not all(
        math.isfinite(value)
        for value in metrics.values()
        if isinstance(value, float)
    ):
        raise EvaluationError("trial derived non-finite metric")
    return metrics


def _apply_gate(gate: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    metric_name = gate["metric"]
    if metric_name not in metrics:
        raise EvaluationError(f"gate references unknown metric: {metric_name}")
    observed = metrics[metric_name]
    expected = gate["value"]
    operator = gate["operator"]
    if operator == "ge":
        passed = observed >= expected
    elif operator == "le":
        passed = observed <= expected
    else:
        passed = observed == expected
    return {
        "gate_id": gate["gate_id"],
        "metric": metric_name,
        "operator": operator,
        "threshold": expected,
        "observed": observed,
        "pass": bool(passed),
        "rationale": gate["rationale"],
    }


def _aggregate(values: list[float | int]) -> dict[str, float]:
    numeric = [float(value) for value in values]
    return {
        "minimum": min(numeric),
        "median": statistics.median(numeric),
        "maximum": max(numeric),
        "arithmetic_mean": statistics.fmean(numeric),
        "population_standard_deviation": statistics.pstdev(numeric),
    }


def _pareto_relation(
    candidate: dict[str, float | int], variant: dict[str, float | int]
) -> str:
    maximize = {
        "drift_accuracy",
        "retention_accuracy",
        "planning_exact_state_rate",
        "planning_belief_set_rate",
    }
    minimize = {
        "reconstruction_rmse",
        "prediction_rmse",
        "expert_evaluations",
        "training_evaluations",
        "expert_count",
        "checkpoint_size_bytes",
    }
    candidate_better = False
    variant_better = False
    for metric in maximize:
        candidate_better |= candidate[metric] > variant[metric]
        variant_better |= candidate[metric] < variant[metric]
    for metric in minimize:
        candidate_better |= candidate[metric] < variant[metric]
        variant_better |= candidate[metric] > variant[metric]
    if candidate_better and not variant_better:
        return "candidate_dominates"
    if variant_better and not candidate_better:
        return "variant_dominates"
    if not candidate_better and not variant_better:
        return "equivalent"
    return "mixed"


def evaluate(raw: Any, preregistration: Any) -> dict[str, Any]:
    prereg = validate_preregistration(preregistration)
    root = require_object(raw, "raw")
    require_exact_keys(
        root,
        {
            "schema",
            "preregistration",
            "preregistration_sha256",
            "trials",
            "self_tests_sha256",
        },
        "raw",
    )
    if root["schema"] != "ravel-raw-observations/0.5":
        raise EvaluationError("unsupported aggregate raw schema")
    if root["preregistration"] != "ravel-0.5-preregistration.json":
        raise EvaluationError("raw evidence names unexpected preregistration authority")
    if root["preregistration_sha256"] != sha256_json(prereg):
        raise EvaluationError("raw evidence preregistration digest mismatch")
    _validate_hex(root["self_tests_sha256"], "raw.self_tests_sha256", 64)
    trials = root["trials"]
    if not isinstance(trials, list) or len(trials) != len(prereg["trials"]):
        raise EvaluationError("raw trial count mismatch")
    evaluated_trials: list[dict[str, Any]] = []
    metric_series: dict[str, list[float | int]] = {}
    passing = 0
    passing_by_regime: dict[str, int] = {
        regime: 0 for regime in prereg["regime_gates"]
    }
    for index, expected in enumerate(prereg["trials"]):
        record = validate_trial(trials[index], expected, prereg)
        metrics = derive_trial_metrics(record)
        gates = [
            _apply_gate(gate, metrics)
            for gate in prereg["common_gates"]
            + prereg["regime_gates"][record["regime"]]
        ]
        trial_pass = all(gate["pass"] for gate in gates)
        passing += int(trial_pass)
        passing_by_regime[record["regime"]] += int(trial_pass)
        for name, value in metrics.items():
            if isinstance(value, bool):
                continue
            metric_series.setdefault(name, []).append(value)
        comparisons: dict[str, Any] = {}
        candidate_quality = {
            "drift_accuracy": metrics["adapted_drift_accuracy"],
            "retention_accuracy": metrics["retention_accuracy"],
            "reconstruction_rmse": metrics["adapted_reconstruction_rmse"],
            "prediction_rmse": metrics["adapted_prediction_rmse"],
            "planning_exact_state_rate": metrics["exact_state_rate"],
            "planning_belief_set_rate": metrics["belief_set_rate"],
            "expert_evaluations": metrics["inference_expert_evaluations"],
            "training_evaluations": metrics["training_evaluations"],
            "expert_count": metrics["expert_count"],
            "checkpoint_size_bytes": metrics["checkpoint_size_bytes"],
        }
        for name, variant in record["comparisons"].items():
            drift = derive_eval(variant["drift_holdout"])
            retention_view = derive_eval(variant["retention_holdout"])
            plan = derive_plan(variant["planning"])
            variant_metrics = {
                "drift_accuracy": drift["accuracy"],
                "retention_accuracy": retention_view["accuracy"],
                "reconstruction_rmse": drift["reconstruction_rmse"],
                "prediction_rmse": drift["prediction_rmse"],
                "planning_exact_state_rate": plan["exact_state_rate"],
                "planning_belief_set_rate": plan["belief_set_rate"],
                "expert_evaluations": drift["expert_evaluations"],
                "training_evaluations": variant["training_evaluations"],
                "expert_count": variant["expert_count"],
                "checkpoint_size_bytes": variant["checkpoint_size_bytes"],
            }
            comparisons[name] = {
                "metrics": variant_metrics,
                "paired_delta_candidate_minus_variant": {
                    metric: candidate_quality[metric] - value
                    for metric, value in variant_metrics.items()
                },
                "pareto_relation": _pareto_relation(
                    candidate_quality, variant_metrics
                ),
            }
        evaluated_trials.append(
            {
                "trial_id": record["trial_id"],
                "regime": record["regime"],
                "seed": record["seed"],
                "metrics": metrics,
                "gates": gates,
                "trial_result": "PASS" if trial_pass else "FAIL",
                "comparisons": comparisons,
            }
        )
    failing = len(evaluated_trials) - passing
    required = prereg["global_pass_rule"]["minimum_passing_trials"]
    required_per_regime = prereg["global_pass_rule"][
        "minimum_passing_trials_per_regime"
    ]
    global_pass = passing >= required and all(
        count >= required_per_regime for count in passing_by_regime.values()
    )
    development_result = "PASS" if global_pass else "FAIL"
    return {
        "schema": "ravel-trial-evidence/0.5",
        "study_id": prereg["study_id"],
        "preregistration_sha256": sha256_json(prereg),
        "trial_summary": {
            "declared": len(evaluated_trials),
            "passing": passing,
            "failing": failing,
            "minimum_passing_trials": required,
            "passing_by_regime": passing_by_regime,
            "minimum_passing_trials_per_regime": required_per_regime,
        },
        "trials": evaluated_trials,
        "aggregates": {
            name: _aggregate(values) for name, values in metric_series.items()
        },
        "development_result": development_result,
        "evidence_reproduction": "PASS",
        "formal_mncs_status": "UNKNOWN",
        "formal_mncds_status": "UNKNOWN",
        "promotion_authorized": False,
    }
