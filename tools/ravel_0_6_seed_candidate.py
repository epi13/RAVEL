#!/usr/bin/env python3
"""Derive the first RAVEL 0.6 development seed from the frozen 0.5 source.

The frozen RAVEL 0.5 source and evidence are historical authority and must not
be edited. This tool applies two narrowly reviewed corrections to an exact,
SHA-256-bound copy of that source:

1. planning traverses every declared supported transition target; and
2. a newly born adaptation expert starts with support from its spawning event
   only, rather than inheriting empirical counters and transitions from its
   parent.

The output is development source only. It is not selected, final, independently
evaluated, or promotion-authorized evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    from .ravel_0_6_transaction_surface import TRANSACTION_SURFACE
except ImportError:  # direct script execution from the tools directory
    from ravel_0_6_transaction_surface import TRANSACTION_SURFACE  # type: ignore[no-redef]

RAVEL_DIR = Path(__file__).resolve().parents[1]
FROZEN_SOURCE = RAVEL_DIR / "ravel_versions/0.5/ravel_0_5.c"
FROZEN_SOURCE_SHA256 = "1a8466ea1805811873c461fb891aaeaec18f6c9e7491b5ea7bd09bf698be102d"

OLD_SEED_FUNCTION = """\
static void seed_adaptation_expert(Model *m, uint16_t id,
                                   const Event *event, uint32_t event_index) {
    uint64_t evaluations = 0u;
    uint16_t parent = full_nearest(event->x, m, &evaluations);
    Expert seeded;
    if (parent != INVALID_EXPERT) seeded = m->e[parent];
    else memset(&seeded, 0, sizeof seeded);
    for (uint32_t d = 0; d < D; ++d) {
        seeded.key[d] = (double)event->x[d];
        seeded.decode[d] = (double)event->x[d];
        seeded.next[event->action][d] = (double)event->nx[d];
    }
    memset(seeded.labels, 0, sizeof seeded.labels);
    seeded.labels[event->label] = 1u;
    seeded.label = event->label;
    seeded.active = 1u;
    seeded.lifecycle = 1u;
    seeded.anchored = 0u;
    seeded.generation = parent == INVALID_EXPERT
        ? (uint16_t)(m->epoch + 1u)
        : (uint16_t)(m->e[parent].generation + 1u);
    seeded.lineage =
        mix64(UINT64_C(0x4144415054424952) ^ m->epoch ^ id ^ event_index ^
              (parent == INVALID_EXPERT ? 0u : m->e[parent].lineage));
    m->e[id] = seeded;
}
"""

NEW_SEED_FUNCTION = """\
static void seed_adaptation_expert(Model *m, uint16_t id,
                                   const Event *event, uint32_t event_index) {
    uint64_t evaluations = 0u;
    uint16_t parent = full_nearest(event->x, m, &evaluations);
    Expert seeded;
    memset(&seeded, 0, sizeof seeded);
    for (uint32_t action = 0; action < ACTIONS; ++action) {
        for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
            seeded.transition_target[action][k] = INVALID_EXPERT;
        }
    }
    for (uint32_t d = 0; d < D; ++d) {
        seeded.key[d] = (double)event->x[d];
        seeded.decode[d] = (double)event->x[d];
        seeded.next[event->action][d] = (double)event->nx[d];
    }
    seeded.labels[event->label] = 1u;
    seeded.action_count[event->action] = 1u;
    seeded.count = 1u;
    seeded.label = event->label;
    seeded.active = 1u;
    seeded.lifecycle = 1u;
    seeded.anchored = 0u;
    seeded.generation = parent == INVALID_EXPERT
        ? (uint16_t)(m->epoch + 1u)
        : (uint16_t)(m->e[parent].generation + 1u);
    seeded.lineage =
        mix64(UINT64_C(0x4144415054424952) ^ m->epoch ^ id ^ event_index ^
              (parent == INVALID_EXPERT ? 0u : m->e[parent].lineage));
    m->e[id] = seeded;
}
"""

OLD_PLANNER_CONTEXT = """\
        for (uint16_t action = 0; action < ACTIONS; ++action) {
            int supported = 0;
            for (uint32_t k = 0; k < 1u; ++k) {
"""
NEW_PLANNER_CONTEXT = """\
        for (uint16_t action = 0; action < ACTIONS; ++action) {
            int supported = 0;
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
"""

PROVIDER_SURFACE = """\
#ifndef RAVEL06_PROVIDER_RING
#define RAVEL06_PROVIDER_ID "ravel-toy-branching-c/1"
#else
#define RAVEL06_PROVIDER_ID "ravel-toy-ring-c/1"
#endif

void make_ring_world(World *w, const TrialSpec *spec) {
    memset(w, 0, sizeof *w);
    for (uint32_t s = 0; s < STATES; ++s) {
        for (uint32_t d = 0; d < D; ++d) {
            int sign = ((s + 3u * d + (s >> 2u)) & 1u) ? 1 : -1;
            w->center[s][d] = (int16_t)(sign * (spec->amplitude - (int)(d % 3u)));
        }
        w->label[s] = (uint8_t)((s * 7u + (s >> 3u)) & 7u);
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            w->base_next[s][a] = (uint8_t)((s + a + 1u) & 63u);
            w->drift_next[s][a] = w->base_next[s][a];
        }
        if (spec->transition_drift && s < 24u) {
            w->drift_next[s][1] = (uint8_t)((s + 5u) & 63u);
        }
    }
}

static void make_world(World *w, const TrialSpec *spec) {
#ifdef RAVEL06_PROVIDER_RING
    make_ring_world(w, spec);
#else
    make_branching_world(w, spec);
#endif
}
"""

SOURCE_MARKER = " * It emits observations and integrity facts, never development verdicts.\n"
CANDIDATE_MARKER = (
    SOURCE_MARKER
    + " *\n"
    + " * RAVEL 0.6 development seed: generated from the frozen 0.5 source by\n"
    + " * tools/ravel_0_6_seed_candidate.py. No evaluation claim is implied.\n"
)


class SeedError(RuntimeError):
    """Raised when the frozen source or an expected transformation is invalid."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_candidate_source(source_bytes: bytes) -> str:
    """Validate the frozen source and apply each reviewed transformation once."""

    actual = _sha256(source_bytes)
    if actual != FROZEN_SOURCE_SHA256:
        raise SeedError(
            "frozen RAVEL 0.5 source identity mismatch: "
            f"expected {FROZEN_SOURCE_SHA256}, got {actual}"
        )

    source = source_bytes.decode("utf-8")
    replacements = (
        (OLD_SEED_FUNCTION, NEW_SEED_FUNCTION, "adaptation support reset"),
        (OLD_PLANNER_CONTEXT, NEW_PLANNER_CONTEXT, "top-two transition traversal"),
        (SOURCE_MARKER, CANDIDATE_MARKER, "candidate provenance marker"),
    )
    for old, new, name in replacements:
        count = source.count(old)
        if count != 1:
            raise SeedError(f"{name}: expected one source match, found {count}")
        source = source.replace(old, new, 1)

    old_world_start = "static void make_world(World *w, const TrialSpec *spec) {"
    if source.count(old_world_start) != 1:
        raise SeedError("provider surface: expected one synthetic world provider")
    source = source.replace(
        old_world_start,
        "void make_branching_world(World *w, const TrialSpec *spec) {",
        1,
    )
    provider_boundary = "\n}\n\nstatic void make_observation"
    if source.count(provider_boundary) != 1:
        raise SeedError("provider surface: expected world provider boundary")
    source = source.replace(
        provider_boundary,
        "\n}\n\n" + PROVIDER_SURFACE + "\nstatic void make_observation",
        1,
    )

    old_trial_identity = r'''           "  \"trial_id\":\"%s\",\"regime\":\"%s\","'''
    new_trial_identity = r'''           "  \"environment_provider_id\":\"%s\",\n"
           "  \"trial_id\":\"%s\",\"regime\":\"%s\","'''
    if source.count(old_trial_identity) != 1:
        raise SeedError("provider surface: expected trial identity output")
    source = source.replace(old_trial_identity, new_trial_identity, 1)
    old_trial_args = "           spec->trial_id, spec->regime, spec->seed,"
    new_trial_args = "           RAVEL06_PROVIDER_ID, spec->trial_id, spec->regime, spec->seed,"
    if source.count(old_trial_args) != 1:
        raise SeedError("provider surface: expected trial identity arguments")
    source = source.replace(old_trial_args, new_trial_args, 1)

    old_observe_signature = (
        "    VariantObservation *out, const Model *base, const Event *base_train,\n"
        "    const Event *adapt_train, const Event *drift_hold, const Event *retention,"
    )
    new_observe_signature = (
        "    VariantObservation *out, const Model *base, const Event *base_train,\n"
        "    const Event *base_hold, const Event *adapt_train,\n"
        "    const Event *drift_hold, const Event *retention,"
    )
    if source.count(old_observe_signature) != 1:
        raise SeedError("transaction surface: expected one variant observation signature")
    source = source.replace(old_observe_signature, new_observe_signature, 1)
    old_observe_call = "&candidate, &base, base_train, adapt_train,"
    if source.count(old_observe_call) != 1:
        raise SeedError("transaction surface: expected candidate observation call")
    source = source.replace(old_observe_call, "&candidate, &base, base_train, base_hold, adapt_train,", 1)
    old_variant_call = "&observation, &base, base_train, adapt_train,"
    if source.count(old_variant_call) != 2:
        raise SeedError("transaction surface: expected two comparator observation calls")
    source = source.replace(old_variant_call, "&observation, &base, base_train, base_hold, adapt_train,", 2)

    observation_marker = "typedef struct {\n    Model model;\n"
    if source.count(observation_marker) != 1:
        raise SeedError("transaction surface: expected one observation boundary")
    source = source.replace(
        observation_marker, TRANSACTION_SURFACE + "\n" + observation_marker, 1
    )

    old_observation_type = "    int adaptation_ok;\n} VariantObservation;"
    new_observation_type = (
        "    int adaptation_ok;\n"
        "    AdaptationTransaction transaction;\n"
        "} VariantObservation;"
    )
    if source.count(old_observation_type) != 1:
        raise SeedError("transaction surface: expected one variant observation type")
    source = source.replace(old_observation_type, new_observation_type, 1)

    old_observation_call = """        adapt_model(&out->model, base_train, adapt_train, config,
                    &out->adaptation_metric, &out->replay_metric, &out->topology);"""
    new_observation_call = """        adapt_model_transaction(&out->model, base_train, adapt_train,
                                base_hold, BASE_HOLD_N,
                                retention, RETENTION_N, config,
                                &out->adaptation_metric, &out->replay_metric,
                                &out->topology, &out->transaction);"""
    if source.count(old_observation_call) != 1:
        raise SeedError("transaction surface: expected one trial adaptation call")
    source = source.replace(old_observation_call, new_observation_call, 1)

    old_candidate_output = (
        '    printf(",\\"topology\\":");\n'
        '    print_topology_json(&candidate.topology, &candidate.adaptation_metric);'
    )
    new_candidate_output = (
        '    printf(",\\"topology\\":");\n'
        '    print_topology_json(&candidate.topology, &candidate.adaptation_metric);\n'
        '    printf(",\\"adaptation_transaction\\":");\n'
        '    print_adaptation_transaction_json(&candidate.transaction);'
    )
    if source.count(old_candidate_output) != 1:
        raise SeedError("transaction surface: expected one candidate JSON boundary")
    source = source.replace(old_candidate_output, new_candidate_output, 1)

    old_comparison_boundary = '    printf("  \\\"comparisons\\\":{\\n");'
    if source.count(old_comparison_boundary) != 1:
        raise SeedError("matched compute: expected one comparison boundary")
    source = source.replace(
        old_comparison_boundary,
        old_comparison_boundary + "\n    MatchedComputeObservation matched_compute = {0};",
        1,
    )
    old_matched_metrics = (
        "        observation.planning =\n"
        "            evaluate_planning(&observation.model, &world, &spec,\n"
        "                              planning_seed, 1);\n"
        "        BEGIN_VARIANT();"
    )
    new_matched_metrics = (
        "        observation.planning =\n"
        "            evaluate_planning(&observation.model, &world, &spec,\n"
        "                              planning_seed, 1);\n"
        "        matched_compute.candidate_training_evaluations =\n"
        "            base_metric.expert_evaluations + candidate.adaptation_metric.expert_evaluations;\n"
        "        matched_compute.matched_training_evaluations =\n"
        "            base_metric.expert_evaluations + observation.adaptation_metric.expert_evaluations;\n"
        "        matched_compute.reference_available =\n"
        "            matched_compute.matched_training_evaluations > 0u;\n"
        "        matched_compute.ratio_q20 = matched_compute.reference_available\n"
        "            ? (matched_compute.candidate_training_evaluations * UINT64_C(1048576)) /\n"
        "              matched_compute.matched_training_evaluations\n"
        "            : 0u;\n"
        "        matched_compute.maximum_ratio_q20 = RAVEL06_MAX_COMPUTE_RATIO_Q20;\n"
        "        matched_compute.threshold_identity = RAVEL06_THRESHOLD_IDENTITY;\n"
        "        matched_compute.comparator_identity =\n"
        "            \"fixed-topology-64-expert-routed/matched-development-work-v1\";\n"
        "        matched_compute.partition_identity = \"ravel-0.6-development-adaptation-v1\";\n"
        "        BEGIN_VARIANT();"
    )
    if source.count(old_matched_metrics) != 1:
        raise SeedError("matched compute: expected one comparator observation boundary")
    source = source.replace(old_matched_metrics, new_matched_metrics, 1)
    old_trial_close = '    printf("\\n  }\\n}\\n");'
    new_trial_close = (
        '    printf("\\n  },\\n  \\"matched_compute\\":");\n'
        '    print_matched_compute_json(&matched_compute);\n'
        '    printf("\\n}\\n");'
    )
    if source.count(old_trial_close) != 1:
        raise SeedError("matched compute: expected one trial JSON close")
    source = source.replace(old_trial_close, new_trial_close, 1)
    return source


def write_candidate(output: Path) -> str:
    """Write the deterministic candidate and return its SHA-256 identity."""

    candidate = build_candidate_source(FROZEN_SOURCE.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(candidate, encoding="utf-8", newline="\n")
    return _sha256(candidate.encode())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="write the generated development source to this path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and derive the candidate without writing it",
    )
    args = parser.parse_args(argv)
    if args.output is None and not args.check:
        parser.error("one of --output or --check is required")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.output is not None:
            digest = write_candidate(args.output)
        else:
            candidate = build_candidate_source(FROZEN_SOURCE.read_bytes())
            digest = _sha256(candidate.encode())
    except (OSError, UnicodeError, SeedError) as error:
        print(f"ravel 0.6 seed candidate failed: {error}", file=sys.stderr)
        return 1

    print(f"ravel-0.6-candidate-001 sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
