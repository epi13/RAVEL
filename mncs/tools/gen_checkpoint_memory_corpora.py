#!/usr/bin/env python3
"""Generate corpora for ravel_checkpoint.mncs and ravel_memory.mncs."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import boolean, case, emit, fields_hash, finite, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "..", "corpus")


def record(module, name, type_pairs, values):
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{module}::{name}::{fields_hash(type_pairs)}",
            "name": name,
            "fields": list(values),
        }
    }


# ---------------------------------------------------------------- checkpoint
CM = "ravel.checkpoint.v1"


def status(v, d):
    return finite(CM, "Status", v, d)


def gates(a, b, c):
    return record(
        CM,
        "GateSet",
        [("a", "Status"), ("b", "Status"), ("c", "Status")],
        [["a", a], ["b", b], ["c", c]],
    )


def checkpoint(cid, total, count):
    return record(
        CM,
        "Checkpoint",
        [("count", "i64"), ("id", "i64"), ("total", "i64")],
        [
            ["count", integer(count, bits=64)],
            ["id", integer(cid, bits=64)],
            ["total", integer(total, bits=64)],
        ],
    )


def candidate(parent, dt, dc, predicted):
    return record(
        CM,
        "Candidate",
        [("delta_count", "i64"), ("delta_total", "i64"), ("parent", "i64"), ("predicted", "Status")],
        [
            ["delta_count", integer(dc, bits=64)],
            ["delta_total", integer(dt, bits=64)],
            ["parent", integer(parent, bits=64)],
            ["predicted", predicted],
        ],
    )


def tx(kind, d, cid, total, count, negative):
    return record(
        CM,
        "TxOutcome",
        [("checkpoint_id", "i64"), ("count", "i64"), ("kind", "TxKind"), ("negative_retained", "bool"), ("total", "i64")],
        [
            ["checkpoint_id", integer(cid, bits=64)],
            ["count", integer(count, bits=64)],
            ["kind", finite(CM, "TxKind", kind, d)],
            ["negative_retained", boolean(negative)],
            ["total", integer(total, bits=64)],
        ],
    )


P, F, U = status("PASS", 0), status("FAIL", 1), status("UNKNOWN", 2)

cases = [
    # Commit: gates clean, prediction PASS, observation PASS, parent matches.
    case(
        "tx-commit",
        CM,
        "transact",
        [checkpoint(7, 100, 3), candidate(7, 5, 1, P), gates(P, P, P), P],
        tx("COMMITTED", 0, 7, 105, 4, False),
    ),
    # Hard gate FAIL: rollback to baseline, negative retained.
    case(
        "tx-rollback-on-failed-gate",
        CM,
        "transact",
        [checkpoint(7, 100, 3), candidate(7, 5, 1, P), gates(P, F, P), P],
        tx("ROLLED_BACK", 1, 7, 100, 3, True),
    ),
    # Unknown gate holds: rollback without fabricated negative.
    case(
        "tx-hold-on-unknown-gate",
        CM,
        "transact",
        [checkpoint(7, 100, 3), candidate(7, 5, 1, P), gates(P, U, P), P],
        tx("ROLLED_BACK", 1, 7, 100, 3, False),
    ),
    # Failed observation: rollback with negative retained.
    case(
        "tx-rollback-on-failed-observation",
        CM,
        "transact",
        [checkpoint(7, 100, 3), candidate(7, 5, 1, P), gates(P, P, P), F],
        tx("ROLLED_BACK", 1, 7, 100, 3, True),
    ),
    # Parent mismatch refuses commit even with clean evidence.
    case(
        "tx-refuses-orphan-candidate",
        CM,
        "transact",
        [checkpoint(7, 100, 3), candidate(9, 5, 1, P), gates(P, P, P), P],
        tx("ROLLED_BACK", 1, 7, 100, 3, False),
    ),
]
emit(os.path.join(CORPUS_DIR, "ravel-checkpoint-corpus.json"), "ravel-checkpoint-v1", cases)

# -------------------------------------------------------------------- memory
MM = "ravel.memory.v1"
MS = lambda v, d: finite(MM, "Status", v, d)  # noqa: E731


def principle(sid, scope, support, counter):
    return record(
        MM,
        "Principle",
        [("counterexample_count", "i64"), ("id", "i64"), ("scope_domain", "i64"), ("support_count", "i64")],
        [
            ["counterexample_count", integer(counter, bits=64)],
            ["id", integer(sid, bits=64)],
            ["scope_domain", integer(scope, bits=64)],
            ["support_count", integer(support, bits=64)],
        ],
    )


def strategy(pid, scope, rank):
    return record(
        MM,
        "Strategy",
        [("principle_id", "i64"), ("rank", "i64"), ("scope_domain", "i64")],
        [
            ["principle_id", integer(pid, bits=64)],
            ["rank", integer(rank, bits=64)],
            ["scope_domain", integer(scope, bits=64)],
        ],
    )


def out_transfer(v, d):
    return finite(MM, "TransferOutcome", v, d)


SEL = lambda v, d: finite(MM, "Selection", v, d)  # noqa: E731

cases = [
    case("promotable-clean-supported", MM, "promotable", [principle(1, 10, 2, 0)], boolean(True)),
    case("promotable-single-support", MM, "promotable", [principle(1, 10, 1, 0)], boolean(False)),
    case("promotable-counterexample-blocks", MM, "promotable", [principle(1, 10, 5, 1)], boolean(False)),
    case(
        "absorb-success-after-failure-retains-negative",
        MM,
        "absorb_success_after_failure",
        [principle(1, 10, 2, 1)],
        principle(1, 10, 3, 1),
    ),
    case("absorb-counterexample", MM, "absorb_counterexample", [principle(1, 10, 2, 0)], principle(1, 10, 2, 1)),
    case(
        "transfer-inside-scope",
        MM,
        "transfer_test",
        [principle(1, 10, 3, 0), strategy(1, 10, 5), integer(10, bits=64)],
        out_transfer("TRANSFERS", 0),
    ),
    case(
        "transfer-out-of-scope-untested",
        MM,
        "transfer_test",
        [principle(1, 10, 3, 0), strategy(1, 10, 5), integer(11, bits=64)],
        out_transfer("UNTESTED", 2),
    ),
    case(
        "select-primary-in-scope-clean",
        MM,
        "select",
        [strategy(1, 10, 5), strategy(2, 10, 1), integer(0, bits=64), integer(0, bits=64), integer(10, bits=64)],
        SEL("PRIMARY_STRATEGY", 0),
    ),
    case(
        "select-demotes-primary-with-counterexamples",
        MM,
        "select",
        [strategy(1, 10, 5), strategy(2, 10, 1), integer(2, bits=64), integer(0, bits=64), integer(10, bits=64)],
        SEL("FALLBACK_STRATEGY", 1),
    ),
    case(
        "select-no-strategy-out-of-scope",
        MM,
        "select",
        [strategy(1, 10, 5), strategy(2, 20, 1), integer(0, bits=64), integer(0, bits=64), integer(99, bits=64)],
        SEL("NO_STRATEGY", 2),
    ),
    case(
        "select-refuses-dirty-fallback",
        MM,
        "select",
        [strategy(1, 99, 5), strategy(2, 10, 1), integer(0, bits=64), integer(1, bits=64), integer(10, bits=64)],
        SEL("NO_STRATEGY", 2),
    ),
]
emit(os.path.join(CORPUS_DIR, "ravel-memory-corpus.json"), "ravel-memory-v1", cases)
