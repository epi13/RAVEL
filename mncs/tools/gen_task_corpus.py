#!/usr/bin/env python3
"""Generate the corpus for ravel_task.mncs."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import case, emit, fields_hash, finite, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
M = "ravel.task.v1"


def record(name, type_pairs, values):
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{M}::{name}::{fields_hash(type_pairs)}",
            "name": name,
            "fields": list(values),
        }
    }


def context(task=1, hi=111, lo=222, subject=33, domain=7, budget=512):
    pairs = [
        ("authority_domain", "i64"),
        ("budget_steps", "i64"),
        ("snapshot_hi", "i64"),
        ("snapshot_lo", "i64"),
        ("subject", "i64"),
        ("task_id", "i64"),
    ]
    values = [
        ["authority_domain", integer(domain, bits=64)],
        ["budget_steps", integer(budget, bits=64)],
        ["snapshot_hi", integer(hi, bits=64)],
        ["snapshot_lo", integer(lo, bits=64)],
        ["subject", integer(subject, bits=64)],
        ["task_id", integer(task, bits=64)],
    ]
    return record("TaskContext", pairs, values)


def request(decision, d, task=1, hi=111, lo=222, subject=33, verifier=9, steps=256):
    pairs = [
        ("max_steps", "i64"),
        ("snapshot_hi", "i64"),
        ("snapshot_lo", "i64"),
        ("subject", "i64"),
        ("task_id", "i64"),
        ("verifier", "i64"),
    ]
    values = [
        ["max_steps", integer(steps, bits=64)],
        ["snapshot_hi", integer(hi, bits=64)],
        ["snapshot_lo", integer(lo, bits=64)],
        ["subject", integer(subject, bits=64)],
        ["task_id", integer(task, bits=64)],
        ["verifier", integer(verifier, bits=64)],
    ]
    inner = record("EvidenceRequest", pairs, values)
    return {
        "record": {
            "type_identity": (
                f"mncs:0.2:record-type:{M}::PlannedRequest::"
                f"{fields_hash([('decision', 'RequestDecision'), ('request', 'EvidenceRequest')])}"
            ),
            "name": "PlannedRequest",
            "fields": [
                ["decision", finite(M, "RequestDecision", decision, d)],
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
        [context(), integer(111, bits=64), integer(222, bits=64), integer(33, bits=64), integer(7, bits=64), integer(256, bits=64), integer(9, bits=64)],
        request("ISSUE_REQUEST", 0, steps=256),
    ),
    # Snapshot advanced -> refuse stale.
    case(
        "refuse-stale",
        M,
        "plan_request",
        [context(), integer(999, bits=64), integer(222, bits=64), integer(33, bits=64), integer(7, bits=64), integer(256, bits=64), integer(9, bits=64)],
        request("REFUSE_STALE", 1, subject=0, steps=0),
    ),
    # Wrong authority domain -> refuse.
    case(
        "refuse-authority",
        M,
        "plan_request",
        [context(), integer(111, bits=64), integer(222, bits=64), integer(33, bits=64), integer(8, bits=64), integer(256, bits=64), integer(9, bits=64)],
        request("REFUSE_AUTHORITY", 2, subject=0, steps=0),
    ),
    # Different subject than bound -> refuse.
    case(
        "refuse-subject-drift",
        M,
        "plan_request",
        [context(), integer(111, bits=64), integer(222, bits=64), integer(44, bits=64), integer(7, bits=64), integer(256, bits=64), integer(9, bits=64)],
        request("REFUSE_AUTHORITY", 2, subject=0, steps=0),
    ),
    # Over-budget -> refuse budget.
    case(
        "refuse-budget",
        M,
        "plan_request",
        [context(budget=100), integer(111, bits=64), integer(222, bits=64), integer(33, bits=64), integer(7, bits=64), integer(256, bits=64), integer(9, bits=64)],
        request("REFUSE_BUDGET", 3, subject=0, steps=0),
    ),
]
emit(os.path.join(HERE, "..", "corpus", "ravel-task-corpus.json"), "ravel-task-v1", cases)
