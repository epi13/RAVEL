#!/usr/bin/env python3
"""Generate the corpus for ravel.evidence.v1."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import boolean, case, emit, fields_hash, finite, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
M = "ravel.evidence.v1"
TM = "ravel.types.v1"
CS = "mncs.core.status.v1"
S = lambda v, d: finite(CS, "Status", v, d)  # noqa: E731
P, F, U = S("PASS", 0), S("FAIL", 1), S("UNKNOWN", 2)


def snapshot(hi, lo):
    pairs = [("hi", "i64"), ("lo", "i64")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{TM}::SnapshotId::{fields_hash(pairs)}",
            "name": "SnapshotId",
            "fields": [
                ["hi", integer(hi, bits=64)],
                ["lo", integer(lo, bits=64)],
            ],
        }
    }


def envelope(hi, lo, active, *statuses):
    assert len(statuses) == 8
    pairs = [("active", "byte"), ("snapshot", "SnapshotId"), ("statuses", "[Status; 8]")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::Envelope::{fields_hash(pairs)}",
            "name": "Envelope",
            "fields": [
                ["active", {"byte": {"value": active}}],
                ["snapshot", snapshot(hi, lo)],
                ["statuses", {"sequence": {"values": list(statuses)}}],
            ],
        }
    }


def summary_record(status, passed, failed, unknown, observed, valid):
    pairs = [
        ("fail_count", "i64"),
        ("observed_count", "i64"),
        ("pass_count", "i64"),
        ("status", "Status"),
        ("unknown_count", "i64"),
        ("valid", "bool"),
    ]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{CS}::StatusSummary::{fields_hash(pairs)}",
            "name": "StatusSummary",
            "fields": [
                ["fail_count", integer(failed, bits=64)],
                ["observed_count", integer(observed, bits=64)],
                ["pass_count", integer(passed, bits=64)],
                ["status", status],
                ["unknown_count", integer(unknown, bits=64)],
                ["valid", boolean(valid)],
            ],
        }
    }


def ask_record(hi, lo, missing, priority):
    pairs = [("missing", "i64"), ("priority", "i64"), ("snapshot", "SnapshotId")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::EvidenceAsk::{fields_hash(pairs)}",
            "name": "EvidenceAsk",
            "fields": [
                ["missing", integer(missing, bits=64)],
                ["priority", integer(priority, bits=64)],
                ["snapshot", snapshot(hi, lo)],
            ],
        }
    }


ALL_PASS = [P] * 8
cases = []

# Aggregation preserves counts; conflict stays visible.
cases.append(
    case(
        "summary-conflict-visible",
        M,
        "summarize_envelope",
        [envelope(1, 2, 8, P, F, U, P, P, P, P, P)],
        summary_record(F, 6, 1, 1, 8, True),
    )
)
cases.append(
    case(
        "summary-unused-lanes-unobserved",
        M,
        "summarize_envelope",
        [envelope(1, 2, 2, P, P, F, F, F, F, F, F)],
        summary_record(U, 2, 0, 0, 2, True),
    )
)
cases.append(
    case(
        "summary-empty-envelope",
        M,
        "summarize_envelope",
        [envelope(1, 2, 0, P, P, P, P, P, P, P, P)],
        summary_record(U, 0, 0, 0, 0, True),
    )
)

# Governing status passes through: FAIL stays FAIL, an invalid envelope
# degrades to UNKNOWN, and all-PASS stays at the undecided floor — RAVEL
# cannot promote it; only committable decides commitment.
cases.append(
    case("governing-fail", M, "governing_status",
         [envelope(1, 2, 8, P, F, P, P, P, P, P, P)], F)
)
cases.append(
    case("governing-invalid-degrades", M, "governing_status",
         [envelope(1, 2, 9, P, P, P, P, P, P, P, P)], U)
)
cases.append(
    case("governing-all-pass-undecided", M, "governing_status",
         [envelope(1, 2, 8, *ALL_PASS)], U)
)

# Commitment: all observed PASS commits; failures, unknowns, invalid
# counts, and the empty envelope all refuse.
cases.append(
    case("committable-all-pass", M, "committable",
         [envelope(1, 2, 8, *ALL_PASS)], boolean(True))
)
cases.append(
    case("committable-fail-refuses", M, "committable",
         [envelope(1, 2, 8, P, F, P, P, P, P, P, P)], boolean(False))
)
cases.append(
    case("committable-unknown-refuses", M, "committable",
         [envelope(1, 2, 8, P, U, P, P, P, P, P, P)], boolean(False))
)
cases.append(
    case("committable-invalid-refuses", M, "committable",
         [envelope(1, 2, 9, *ALL_PASS)], boolean(False))
)
cases.append(
    case("committable-empty-refuses", M, "committable",
         [envelope(1, 2, 0, *ALL_PASS)], boolean(False))
)
cases.append(
    case("committable-prefix-only", M, "committable",
         [envelope(1, 2, 2, P, P, F, F, F, F, F, F)], boolean(True))
)

# Conflict reporting.
cases.append(
    case("conflict-mixed", M, "has_conflict",
         [envelope(1, 2, 8, P, F, P, P, P, P, P, P)], boolean(True))
)
cases.append(
    case("conflict-clean", M, "has_conflict",
         [envelope(1, 2, 8, *ALL_PASS)], boolean(False))
)
cases.append(
    case("conflict-fail-only", M, "has_conflict",
         [envelope(1, 2, 8, F, F, U, U, U, U, U, U)], boolean(False))
)

# Advisory asks carry the unresolved count with the bound snapshot and the
# caller priority; they change no status.
cases.append(
    case("ask-carries-missing", M, "ask_for_more",
         [envelope(1, 2, 3, P, U, U, F, F, F, F, F), integer(7, bits=64)],
         ask_record(1, 2, 2, 7))
)

# Freshness: the bound snapshot replays fresh; drift is stale.
cases.append(
    case("fresh-same", M, "envelope_fresh",
         [envelope(1, 2, 2, P, P, P, P, P, P, P, P), snapshot(1, 2)],
         boolean(True))
)
cases.append(
    case("stale-drift", M, "envelope_fresh",
         [envelope(1, 2, 2, P, P, P, P, P, P, P, P), snapshot(1, 3)],
         boolean(False))
)

emit(os.path.join(HERE, "..", "corpus", "ravel-evidence-corpus.json"), "ravel-evidence-v1", cases)
