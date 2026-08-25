#!/usr/bin/env python3
"""Generate the corpus for mncs/workspace/ravel/task.mncs.

The module binds snapshot identity through ravel.types.v1's SnapshotId
record and refuses stale contexts with a payload-bearing variant that names
the expected snapshot.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import case, emit, fields_hash, finite_payload, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
M = "ravel.task.v1"
T = "ravel.types.v1"


def record(module, name, type_pairs, values):
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{module}::{name}::{fields_hash(type_pairs)}",
            "name": name,
            "fields": list(values),
        }
    }


def snapshot(hi=111, lo=222):
    return record(
        T,
        "SnapshotId",
        [("hi", "i64"), ("lo", "i64")],
        [["hi", integer(hi, bits=64)], ["lo", integer(lo, bits=64)]],
    )


def dead_snapshot():
    return snapshot(hi=0, lo=0)


def context(task=1, hi=111, lo=222, subject=33, domain=7, budget=512):
    pairs = [
        ("authority_domain", "i64"),
        ("budget_steps", "i64"),
        ("snapshot", "SnapshotId"),
        ("subject", "i64"),
        ("task_id", "i64"),
    ]
    values = [
        ["authority_domain", integer(domain, bits=64)],
        ["budget_steps", integer(budget, bits=64)],
        ["snapshot", snapshot(hi, lo)],
        ["subject", integer(subject, bits=64)],
        ["task_id", integer(task, bits=64)],
    ]
    return record(M, "TaskContext", pairs, values)


def request(decision_value, task=1, snap=None, subject=33, verifier=9, steps=256):
    snap = snap if snap is not None else snapshot()
    pairs = [
        ("max_steps", "i64"),
        ("snapshot", "SnapshotId"),
        ("subject", "i64"),
        ("task_id", "i64"),
        ("verifier", "i64"),
    ]
    values = [
        ["max_steps", integer(steps, bits=64)],
        ["snapshot", snap],
        ["subject", integer(subject, bits=64)],
        ["task_id", integer(task, bits=64)],
        ["verifier", integer(verifier, bits=64)],
    ]
    inner = record(M, "EvidenceRequest", pairs, values)
    if decision_value == "ISSUE_REQUEST":
        decision = {
            "finite": {
                "type_identity": f"mncs:0.2:finite-type:{M}::RequestDecision",
                "variant_identity": f"mncs:0.2:finite-variant:{M}::RequestDecision::ISSUE_REQUEST",
                "discriminant": 0,
            }
        }
    elif decision_value == "REFUSE_STALE":
        # Payload variant: names the snapshot the context was bound to.
        decision = finite_payload(
            M,
            "RequestDecision",
            "REFUSE_STALE",
            1,
            [("expected", snapshot())],
        )
    elif decision_value == "REFUSE_AUTHORITY":
        decision = {
            "finite": {
                "type_identity": f"mncs:0.2:finite-type:{M}::RequestDecision",
                "variant_identity": f"mncs:0.2:finite-variant:{M}::RequestDecision::REFUSE_AUTHORITY",
                "discriminant": 2,
            }
        }
    else:
        decision = {
            "finite": {
                "type_identity": f"mncs:0.2:finite-type:{M}::RequestDecision",
                "variant_identity": f"mncs:0.2:finite-variant:{M}::RequestDecision::REFUSE_BUDGET",
                "discriminant": 3,
            }
        }
    return {
        "record": {
            "type_identity": (
                f"mncs:0.2:record-type:{M}::PlannedRequest::"
                f"{fields_hash([('decision', 'RequestDecision'), ('request', 'EvidenceRequest')])}"
            ),
            "name": "PlannedRequest",
            "fields": [
                ["decision", decision],
                ["request", inner],
            ],
        }
    }


cases = [
    # Fresh snapshot, right subject/domain, within budget -> issued.
    case(
        "issue",
        M,
        "plan_request",
        [
            context(),
            snapshot(),
            integer(33, bits=64),
            integer(7, bits=64),
            integer(256, bits=64),
            integer(9, bits=64),
        ],
        request("ISSUE_REQUEST", steps=256),
    ),
    # Snapshot advanced -> refuse stale, naming the expected (bound) snapshot;
    # the inert request carries the dead zero identity.
    case(
        "refuse-stale-names-expected-snapshot",
        M,
        "plan_request",
        [
            context(),
            snapshot(hi=999, lo=222),
            integer(33, bits=64),
            integer(7, bits=64),
            integer(256, bits=64),
            integer(9, bits=64),
        ],
        request("REFUSE_STALE", snap=snapshot(), subject=0, steps=0),
    ),
    # Low half drift is equally fatal: any half mismatching is stale.
    case(
        "refuse-stale-on-low-half-drift",
        M,
        "plan_request",
        [
            context(),
            snapshot(hi=111, lo=223),
            integer(33, bits=64),
            integer(7, bits=64),
            integer(256, bits=64),
            integer(9, bits=64),
        ],
        request("REFUSE_STALE", snap=snapshot(), subject=0, steps=0),
    ),
    # Wrong authority domain -> refuse.
    case(
        "refuse-authority",
        M,
        "plan_request",
        [
            context(),
            snapshot(),
            integer(33, bits=64),
            integer(8, bits=64),
            integer(256, bits=64),
            integer(9, bits=64),
        ],
        request("REFUSE_AUTHORITY", subject=0, steps=0),
    ),
    # Over budget -> refuse without issuing a partial request.
    case(
        "refuse-budget",
        M,
        "plan_request",
        [
            context(budget=128),
            snapshot(),
            integer(33, bits=64),
            integer(7, bits=64),
            integer(256, bits=64),
            integer(9, bits=64),
        ],
        request("REFUSE_BUDGET", subject=0, steps=0),
    ),
]
emit(os.path.join(HERE, "..", "corpus", "ravel-task-corpus.json"), "ravel-task-v1", cases)
