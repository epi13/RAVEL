#!/usr/bin/env python3
"""Generate the corpus for ravel_core.mncs."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import case, emit, fields_hash, finite, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
M = "ravel.core.v1"
S = lambda v, d: finite(M, "Status", v, d)  # noqa: E731
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


cases = []
# dominate(): full 3x3 lattice join.
JOIN = {
    (0, 0): ("PASS", 0),  # P P
    (0, 1): ("FAIL", 1),  # P F
    (0, 2): ("UNKNOWN", 2),  # P U
    (1, 0): ("FAIL", 1),  # F P
    (1, 1): ("FAIL", 1),  # F F
    (1, 2): ("FAIL", 1),  # F U
    (2, 0): ("UNKNOWN", 2),  # U P
    (2, 1): ("FAIL", 1),  # U F
    (2, 2): ("UNKNOWN", 2),  # U U
}
for left, right in [(P, P), (P, F), (P, U), (F, P), (F, F), (F, U), (U, P), (U, F), (U, U)]:
    name, d = JOIN[(left["finite"]["discriminant"], right["finite"]["discriminant"])]
    cases.append(
        case(
            f"dominate-{left['finite']['discriminant']}-{right['finite']['discriminant']}",
            M,
            "dominate",
            [left, right],
            S(name, d),
        )
    )

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
