#!/usr/bin/env python3
"""Generate the corpus for ravel_core.mncs."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import case, emit, fields_hash, finite, finite as core_finite, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
M = "ravel.core.v1"
# Status is the standard-library lattice type; its declaring identity is
# mncs.core.status.v1 even when referenced from a RAVEL module.
CS = "mncs.core.status.v1"
S = lambda v, d: finite(CS, "Status", v, d)  # noqa: E731
D = lambda v, d: finite(M, "Disposition", v, d)  # noqa: E731
P, F, U = S("PASS", 0), S("FAIL", 1), S("UNKNOWN", 2)
COMMIT, REJECT, HOLD = D("COMMIT", 0), D("REJECT", 1), D("HOLD", 2)


def evidence(obligation, verifier, status):
    pairs = [("obligation", "i64"), ("status", "Status"), ("verifier", "i64")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::EvidenceRef::{fields_hash(pairs)}",
            "name": "EvidenceRef",
            "fields": [
                ["obligation", integer(obligation, bits=64)],
                ["status", status],
                ["verifier", integer(verifier, bits=64)],
            ],
        }
    }


def gate_set(a, b, c, d):
    pairs = [("a", "Status"), ("b", "Status"), ("c", "Status"), ("d", "Status")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::GateSet::{fields_hash(pairs)}",
            "name": "GateSet",
            "fields": [["a", a], ["b", b], ["c", c], ["d", d]],
        }
    }


def envelope(*statuses):
    pairs = [("statuses", "[Status; 4]")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::EvidenceEnvelope::{fields_hash(pairs)}",
            "name": "EvidenceEnvelope",
            "fields": [["statuses", {"sequence": {"values": list(statuses)}}]],
        }
    }


def summary_record(status, passed, failed, unknown, observed, valid):
    # Canonical field order is sorted; the StatusSummary identity is declared
    # by mncs.core.status.v1 even when observed through a RAVEL envelope.
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
                ["valid", {"boolean": {"value": valid}}],
            ],
        }
    }


cases = []
# combine_evidence(): status join over two evidence references.
cases.append(
    case(
        "combine-fail-dominates-pass",
        M,
        "combine_evidence",
        [evidence(1, 100, P), evidence(2, 101, F)],
        F,
    )
)
cases.append(
    case(
        "combine-unknown-survives",
        M,
        "combine_evidence",
        [evidence(1, 100, P), evidence(2, 101, U)],
        U,
    )
)

# disposition(): FAIL anywhere rejects; UNKNOWN holds only absent FAIL;
# all-PASS commits - UNKNOWN is never promoted to PASS.
cases.append(case("disposition-commit", M, "disposition", [gate_set(P, P, P, P)], COMMIT))
cases.append(case("disposition-reject", M, "disposition", [gate_set(P, F, P, P)], REJECT))
cases.append(case("disposition-hold", M, "disposition", [gate_set(P, U, P, P)], HOLD))
cases.append(case("disposition-fail-beats-unknown", M, "disposition", [gate_set(U, F, U, U)], REJECT))

# envelope_disposition(): the same authority boundary through the generic
# fold — FAIL rejects even beside UNKNOWN, UNKNOWN holds, all-PASS commits.
cases.append(case("envelope-commit", M, "envelope_disposition", [envelope(P, P, P, P)], COMMIT))
cases.append(case("envelope-reject", M, "envelope_disposition", [envelope(P, F, P, P)], REJECT))
cases.append(case("envelope-hold", M, "envelope_disposition", [envelope(P, U, P, P)], HOLD))
cases.append(case("envelope-fail-beats-unknown", M, "envelope_disposition", [envelope(U, F, U, U)], REJECT))
cases.append(case("envelope-all-unknown-holds", M, "envelope_disposition", [envelope(U, U, U, U)], HOLD))
cases.append(case("envelope-mixed-rejects", M, "envelope_disposition", [envelope(P, F, U, P)], REJECT))

# envelope_summary(): conflict stays visible in the counts — the mixed
# envelope reports PASS, FAIL, and UNKNOWN lanes together with the total.
cases.append(
    case(
        "envelope-summary-conflict-visible",
        M,
        "envelope_summary",
        [envelope(P, F, U, P)],
        summary_record(F, 2, 1, 1, 4, True),
    )
)
cases.append(
    case(
        "envelope-summary-all-pass",
        M,
        "envelope_summary",
        [envelope(P, P, P, P)],
        summary_record(U, 4, 0, 0, 4, True),
    )
)

# confidence_ranked(): advisory ranking only; failed subjects are skipped.
cases.append(
    case(
        "confidence-prefers-stronger",
        M,
        "confidence_ranked",
        [integer(80, bits=64), integer(40, bits=64), P, P],
        integer(80, bits=64),
    )
)
cases.append(
    case(
        "confidence-skips-failed-subject",
        M,
        "confidence_ranked",
        [integer(80, bits=64), integer(40, bits=64), F, P],
        integer(40, bits=64),
    )
)

emit(os.path.join(HERE, "..", "corpus", "ravel-core-corpus.json"), "ravel-core-v1", cases)
