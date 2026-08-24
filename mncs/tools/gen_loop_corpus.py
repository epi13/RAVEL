#!/usr/bin/env python3
"""Generate the corpus for mncs/workspace/ravel_loop.mncs."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import case, emit, fields_hash, finite, integer  # noqa: E402

M = "ravel.loop.v1"
S = lambda v, d: finite(M, "Status", v, d)  # noqa: E731
A = lambda v, d: finite(M, "Attribution", v, d)  # noqa: E731
P, F, U = S("PASS", 0), S("FAIL", 1), S("UNKNOWN", 2)
C, R, I = A("CONFIRMED", 0), A("REFUTED", 1), A("INCONCLUSIVE", 2)

cases = []
# attribute(): falsifiable predictions only; UNKNOWN never fabricates.
for predicted, observed, kind in [
    (P, P, C),
    (P, F, R),
    (P, U, I),
    (F, F, C),
    (F, P, R),
    (F, U, I),
    (U, P, I),
    (U, F, I),
    (U, U, I),
]:
    cases.append(
        case(
            f"attribute-{predicted['finite']['discriminant']}-{observed['finite']['discriminant']}",
            M,
            "attribute",
            [predicted, observed],
            kind,
        )
    )

# dominates(): MNCS status dominance lattice.
for left, right, result in [
    (P, P, P),
    (P, F, F),
    (P, U, U),
    (F, P, F),
    (F, F, F),
    (F, U, F),
    (U, P, U),
    (U, F, F),
    (U, U, U),
]:
    cases.append(
        case(
            f"dominates-{left['finite']['discriminant']}-{right['finite']['discriminant']}",
            M,
            "dominates",
            [left, right],
            result,
        )
    )

# evaluate(): commit needs all gates PASS and a confirmed prediction;
# refuted or failed observations retain negative experience.
def hypothesis(predicted):
    pairs = [("change", "i64"), ("id", "i64"), ("predicted", "Status"), ("subject", "i64")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::Hypothesis::{fields_hash(pairs)}",
            "name": "Hypothesis",
            "fields": [
                ["change", integer(77, bits=64)],
                ["id", integer(9, bits=64)],
                ["predicted", predicted],
                ["subject", integer(4, bits=64)],
            ],
        }
    }


def gates(a, b, c):
    pairs = [("a", "Status"), ("b", "Status"), ("c", "Status")]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::GateSet::{fields_hash(pairs)}",
            "name": "GateSet",
            "fields": [["a", a], ["b", b], ["c", c]],
        }
    }


def outcome(kind, commit, negative):
    pairs = [
        ("attribution_kind", "Attribution"),
        ("commit_eligible", "bool"),
        ("retain_negative", "bool"),
    ]
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::LoopOutcome::{fields_hash(pairs)}",
            "name": "LoopOutcome",
            "fields": [
                ["attribution_kind", kind],
                ["commit_eligible", {"boolean": {"value": commit}}],
                ["retain_negative", {"boolean": {"value": negative}}],
            ],
        }
    }


cases.append(
    case(
        "evaluate-commit",
        M,
        "evaluate",
        [hypothesis(P), gates(P, P, P), P],
        outcome(C, True, False),
    )
)
cases.append(
    case(
        "evaluate-hold-on-unknown-gate",
        M,
        "evaluate",
        [hypothesis(P), gates(P, U, P), P],
        outcome(C, False, False),
    )
)
cases.append(
    case(
        "evaluate-refuted-retains-negative",
        M,
        "evaluate",
        [hypothesis(P), gates(P, P, P), F],
        outcome(R, False, True),
    )
)
cases.append(
    case(
        "evaluate-confirmed-failure-prediction-retains-negative",
        M,
        "evaluate",
        [hypothesis(F), gates(P, P, P), F],
        outcome(C, True, True),
    )
)

emit(
    os.path.join(os.path.dirname(__file__), "..", "corpus", "ravel-loop-corpus.json"),
    "ravel-loop-v1",
    cases,
)
