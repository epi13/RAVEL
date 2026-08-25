#!/usr/bin/env python3
"""Generate corpora for the Phase 3 RAVEL modules:

- ravel/lifecycle.mncs (ravel.lifecycle.v1) — promotion state machine
- ravel/provider.mncs  (ravel.provider.v1)  — Forge provider dispatch
- ravel/budget.mncs    (ravel.budget.v1)    — resource accounting
- ravel/forge.mncs     (ravel.forge.v1)     — request/receipt binding
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ravel_corpus import boolean, case, emit, fields_hash, finite, integer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "..", "corpus")
CS = "mncs.core.status.v1"


def record(module, name, type_pairs, values):
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{module}::{name}::{fields_hash(type_pairs)}",
            "name": name,
            "fields": list(values),
        }
    }


def st(v, d):
    return finite(CS, "Status", v, d)


P, F, U = st("PASS", 0), st("FAIL", 1), st("UNKNOWN", 2)

STAGES = [
    "OBSERVATION",
    "EPISODE",
    "OPEN_HYPOTHESIS",
    "INTERVENTION",
    "ATTRIBUTION",
    "PROVISIONAL_PRINCIPLE",
    "TRANSFER_TESTED_PRINCIPLE",
    "RESTRICTED_STRATEGY",
    "SUPPORTED_STRATEGY",
    "COUNTEREXAMPLE",
    "RETIRED",
]


def stage(name):
    return finite("ravel.lifecycle.v1", "Stage", name, STAGES.index(name))


ATTRS = ["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"]


def attr(name):
    return finite("ravel.lifecycle.v1", "AttributionKind", name, ATTRS.index(name))


def step(kind, following=None, reason=None):
    if kind == "ADVANCE":
        return finite_payload_step("ADVANCE", 0, [("following", stage(following))])
    return finite_payload_step(
        "REFUSE_TRANSITION", 1, [("reason", integer(reason, bits=32))]
    )


def finite_payload_step(variant, discriminant, pairs):
    ordered = sorted(pairs, key=lambda pair: pair[0])
    return {
        "finite": {
            "type_identity": "mncs:0.2:finite-type:ravel.lifecycle.v1::Step",
            "variant_identity": (
                f"mncs:0.2:finite-variant:ravel.lifecycle.v1::Step::{variant}"
            ),
            "discriminant": discriminant,
            "payload": [[name, value] for name, value in ordered],
        }
    }


# ---------------------------------------------------------------- lifecycle
LM = "ravel.lifecycle.v1"
lifecycle_cases = [
    # The canonical promotion path advances one edge at a time.
    case(
        "observation-to-episode",
        LM,
        "transition",
        [stage("OBSERVATION"), stage("EPISODE"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("ADVANCE", following="EPISODE"),
    ),
    case(
        "episode-to-hypothesis",
        LM,
        "transition",
        [stage("EPISODE"), stage("OPEN_HYPOTHESIS"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("ADVANCE", following="OPEN_HYPOTHESIS"),
    ),
    # Evidence-skip attack refused: an episode cannot become a strategy.
    case(
        "episode-cannot-skip-to-global-strategy",
        LM,
        "transition",
        [stage("EPISODE"), stage("SUPPORTED_STRATEGY"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("REFUSE", reason=2),
    ),
    # Principle minting requires supported attribution.
    case(
        "attribution-supported-mints-principle",
        LM,
        "transition",
        [stage("ATTRIBUTION"), stage("PROVISIONAL_PRINCIPLE"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("ADVANCE", following="PROVISIONAL_PRINCIPLE"),
    ),
    case(
        "attribution-contradicted-cannot-mint-principle",
        LM,
        "transition",
        [stage("ATTRIBUTION"), stage("PROVISIONAL_PRINCIPLE"), attr("CONTRADICTED"), boolean(True), boolean(True)],
        step("REFUSE", reason=3),
    ),
    # Transfer requires evidence: an untested principle cannot authorize it.
    case(
        "transfer-without-evidence-refused",
        LM,
        "transition",
        [stage("PROVISIONAL_PRINCIPLE"), stage("TRANSFER_TESTED_PRINCIPLE"), attr("SUPPORTED"), boolean(False), boolean(True)],
        step("REFUSE", reason=5),
    ),
    case(
        "transfer-with-evidence-accepted",
        LM,
        "transition",
        [stage("PROVISIONAL_PRINCIPLE"), stage("TRANSFER_TESTED_PRINCIPLE"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("ADVANCE", following="TRANSFER_TESTED_PRINCIPLE"),
    ),
    # Counterexamples are terminal; negative knowledge is never unpromoted.
    case(
        "counterexample-is-terminal",
        LM,
        "transition",
        [stage("COUNTEREXAMPLE"), stage("OPEN_HYPOTHESIS"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("REFUSE", reason=4),
    ),
    # Unsupported edges are refused.
    case(
        "observation-cannot-leap-to-intervention",
        LM,
        "transition",
        [stage("OBSERVATION"), stage("INTERVENTION"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("REFUSE", reason=1),
    ),
    # Final promotion requires a supported transfer test.
    case(
        "final-promotion-without-supported-transfer-refused",
        LM,
        "transition",
        [stage("RESTRICTED_STRATEGY"), stage("SUPPORTED_STRATEGY"), attr("SUPPORTED"), boolean(True), boolean(False)],
        step("REFUSE", reason=6),
    ),
    case(
        "final-promotion-with-supported-transfer-accepted",
        LM,
        "transition",
        [stage("RESTRICTED_STRATEGY"), stage("SUPPORTED_STRATEGY"), attr("SUPPORTED"), boolean(True), boolean(True)],
        step("ADVANCE", following="SUPPORTED_STRATEGY"),
    ),
]
emit(
    os.path.join(CORPUS_DIR, "ravel-lifecycle-corpus.json"),
    "ravel-lifecycle-v1",
    lifecycle_cases,
)

# ----------------------------------------------------------------- provider
PM = "ravel.provider.v1"


def capability(operation=50, witness=7, deterministic=True):
    return record(
        PM,
        "Capability",
        [("deterministic", "bool"), ("operation", "i64"), ("witness_kind", "i64")],
        [
            ["deterministic", boolean(deterministic)],
            ["operation", integer(operation, bits=64)],
            ["witness_kind", integer(witness, bits=64)],
        ],
    )


def request(verifier=50, witness=7, determinism=True):
    return record(
        PM,
        "EvidenceRequest",
        [("determinism_required", "bool"), ("verifier_contract", "i64"), ("witness_kind", "i64")],
        [
            ["determinism_required", boolean(determinism)],
            ["verifier_contract", integer(verifier, bits=64)],
            ["witness_kind", integer(witness, bits=64)],
        ],
    )


def receipt(kind, discriminant, payload=None, status=None):
    if status is not None:
        payload = [("status", status)]
    entry = {
        "finite": {
            "type_identity": f"mncs:0.2:finite-type:{PM}::Receipt",
            "variant_identity": f"mncs:0.2:finite-variant:{PM}::Receipt::{kind}",
            "discriminant": discriminant,
        }
    }
    if payload:
        entry["finite"]["payload"] = [[name, value] for name, value in sorted(payload)]
    return entry


provider_cases = [
    case(
        "dispatch-receives-pass",
        PM,
        "dispatch",
        [request(), capability(), P],
        receipt("RECEIVED", 0, status=P),
    ),
    case(
        "dispatch-receives-fail-and-retains-negative",
        PM,
        "dispatch",
        [request(), capability(), F],
        receipt("RECEIVED", 0, status=F),
    ),
    case(
        "dispatch-receives-unknown-stays-unknown",
        PM,
        "dispatch",
        [request(), capability(), U],
        receipt("RECEIVED", 0, status=U),
    ),
    # Missing capability: explicit UNAVAILABLE, never a fabricated PASS.
    case(
        "unavailable-operation-is-explicit",
        PM,
        "dispatch",
        [request(verifier=51), capability(), U],
        receipt("UNAVAILABLE", 1, payload=[("reason", integer(1, bits=32))]),
    ),
    case(
        "wrong-witness-kind-is-explicit",
        PM,
        "dispatch",
        [request(witness=8), capability(), U],
        receipt("UNAVAILABLE", 1, payload=[("reason", integer(2, bits=32))]),
    ),
    case(
        "nondeterministic-provider-refused-for-determinism-request",
        PM,
        "dispatch",
        [request(determinism=True), capability(deterministic=False), U],
        receipt("UNAVAILABLE", 1, payload=[("reason", integer(3, bits=32))]),
    ),
    # Governed status of absence is UNKNOWN.
    case(
        "unavailable-governs-as-unknown",
        PM,
        "governed_status",
        [receipt("UNAVAILABLE", 1, payload=[("reason", integer(1, bits=32))])],
        U,
    ),
    case(
        "received-pass-governs-as-pass",
        PM,
        "governed_status",
        [receipt("RECEIVED", 0, status=P)],
        P,
    ),
    case(
        "failed-execution-retains-negative",
        PM,
        "retains_negative",
        [receipt("FAILED", 2, payload=[("reason", integer(4, bits=32))])],
        boolean(True),
    ),
    case(
        "received-pass-retains-nothing-negative",
        PM,
        "retains_negative",
        [receipt("RECEIVED", 0, status=P)],
        boolean(False),
    ),
]
emit(
    os.path.join(CORPUS_DIR, "ravel-provider-corpus.json"),
    "ravel-provider-v1",
    provider_cases,
)

# ------------------------------------------------------------------- budget
BM = "ravel.budget.v1"


def budget(steps, slots):
    return record(
        BM,
        "Budget",
        [("evidence_slots", "i64"), ("steps", "i64")],
        [
            ["evidence_slots", integer(slots, bits=64)],
            ["steps", integer(steps, bits=64)],
        ],
    )


def spend(kind, steps=None, slots=None, reason=None):
    payload_budget = budget(steps, slots)
    if kind == "SPENT":
        return {
            "finite": {
                "type_identity": f"mncs:0.2:finite-type:{BM}::Spend",
                "variant_identity": f"mncs:0.2:finite-variant:{BM}::Spend::SPENT",
                "discriminant": 0,
                "payload": [["budget", payload_budget]],
            }
        }
    payload = sorted([("budget", payload_budget), ("reason", integer(reason, bits=32))])
    return {
        "finite": {
            "type_identity": f"mncs:0.2:finite-type:{BM}::Spend",
            "variant_identity": f"mncs:0.2:finite-variant:{BM}::Spend::REFUSE_BUDGET",
            "discriminant": 1,
            "payload": [[name, value] for name, value in payload],
        }
    }


budget_cases = [
    case(
        "spend-within-budget",
        BM,
        "spend_steps",
        [budget(100, 4), integer(60, bits=64)],
        spend("SPENT", steps=40, slots=4),
    ),
    # Overdraw refuses with the untouched budget returned.
    case(
        "spend-overdraw-refuses-with-budget-intact",
        BM,
        "spend_steps",
        [budget(100, 4), integer(120, bits=64)],
        spend("REFUSE", steps=100, slots=4, reason=2),
    ),
    case(
        "negative-spend-refused",
        BM,
        "spend_steps",
        [budget(100, 4), integer(-5, bits=64)],
        spend("REFUSE", steps=100, slots=4, reason=1),
    ),
    case(
        "last-evidence-slot-consumable",
        BM,
        "consume_evidence_slot",
        [budget(10, 1)],
        spend("SPENT", steps=10, slots=0),
    ),
    case(
        "exhausted-slots-refuse",
        BM,
        "consume_evidence_slot",
        [budget(10, 0)],
        spend("REFUSE", steps=10, slots=0, reason=3),
    ),
    case(
        "merge-adds-capacity",
        BM,
        "merge",
        [budget(30, 2), budget(12, 5)],
        budget(42, 7),
    ),
    case(
        "plan-affordable-on-both-axes",
        BM,
        "affordable",
        [budget(100, 4), integer(90, bits=64), integer(4, bits=64)],
        boolean(True),
    ),
    case(
        "plan-over-one-axis-unaffordable",
        BM,
        "affordable",
        [budget(100, 4), integer(90, bits=64), integer(5, bits=64)],
        boolean(False),
    ),
]
emit(
    os.path.join(CORPUS_DIR, "ravel-budget-corpus.json"),
    "ravel-budget-v1",
    budget_cases,
)

# -------------------------------------------------------------------- forge
FM = "ravel.forge.v1"
T = "ravel.types.v1"


def snap(hi=111, lo=222):
    return record(
        T,
        "SnapshotId",
        [("hi", "i64"), ("lo", "i64")],
        [["hi", integer(hi, bits=64)], ["lo", integer(lo, bits=64)]],
    )


def forge_request(task=1, obligation=900, hi=111, lo=222):
    return record(
        FM,
        "ForgeRequest",
        [("max_steps", "i64"), ("obligation", "i64"), ("snapshot", "SnapshotId"), ("task_id", "i64")],
        [
            ["max_steps", integer(256, bits=64)],
            ["obligation", integer(obligation, bits=64)],
            ["snapshot", snap(hi, lo)],
            ["task_id", integer(task, bits=64)],
        ],
    )


def forge_receipt(task=1, obligation=900, hi=111, lo=222, steps_used=200, status=P):
    return record(
        FM,
        "ForgeReceipt",
        [
            ("obligation", "i64"),
            ("snapshot", "SnapshotId"),
            ("status", "Status"),
            ("steps_used", "i64"),
            ("task_id", "i64"),
        ],
        [
            ["obligation", integer(obligation, bits=64)],
            ["snapshot", snap(hi, lo)],
            ["status", status],
            ["steps_used", integer(steps_used, bits=64)],
            ["task_id", integer(task, bits=64)],
        ],
    )


def binding(kind, field=None):
    entry = {
        "finite": {
            "type_identity": f"mncs:0.2:finite-type:{FM}::Binding",
            "variant_identity": f"mncs:0.2:finite-variant:{FM}::Binding::{kind}",
            "discriminant": {"MATCHES": 0, "STALE_RECEIPT": 1, "MISMATCH": 2}[kind],
        }
    }
    if field is not None:
        entry["finite"]["payload"] = [["field", integer(field, bits=32)]]
    return entry


forge_cases = [
    case(
        "matching-receipt-binds",
        FM,
        "bind",
        [forge_request(), forge_receipt()],
        binding("MATCHES"),
    ),
    # A favorable receipt from a drifted snapshot is stale, not evidence.
    case(
        "stale-receipt-refused-even-when-passing",
        FM,
        "bind",
        [forge_request(), forge_receipt(hi=999)],
        binding("STALE_RECEIPT"),
    ),
    case(
        "wrong-obligation-mismatches",
        FM,
        "bind",
        [forge_request(), forge_receipt(obligation=901)],
        binding("MISMATCH", field=2),
    ),
    case(
        "wrong-task-mismatches",
        FM,
        "bind",
        [forge_request(), forge_receipt(task=2)],
        binding("MISMATCH", field=1),
    ),
    # UNKNOWN receipts stay UNKNOWN through governed_status.
    case(
        "unknown-status-survives-binding",
        FM,
        "governed_status",
        [binding("MATCHES"), forge_receipt(status=U)],
        U,
    ),
    case(
        "pass-status-governs-as-pass-when-bound",
        FM,
        "governed_status",
        [binding("MATCHES"), forge_receipt(status=P)],
        P,
    ),
    # An unreportable PASS degrades to UNKNOWN — never the reverse.
    case(
        "stale-pass-degrades-to-unknown-never-upgrades",
        FM,
        "governed_status",
        [binding("STALE_RECEIPT"), forge_receipt(status=P)],
        U,
    ),
    # Failed evidence remains failed even when unbound.
    case(
        "failed-status-remains-fail-when-stale",
        FM,
        "governed_status",
        [binding("STALE_RECEIPT"), forge_receipt(status=F)],
        F,
    ),
]
emit(os.path.join(CORPUS_DIR, "ravel-forge-corpus.json"), "ravel-forge-v1", forge_cases)
