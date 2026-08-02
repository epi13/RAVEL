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

RAVEL_DIR = Path(__file__).resolve().parents[1]
FROZEN_SOURCE = RAVEL_DIR / "ravel_0_5.c"
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
