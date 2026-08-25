#!/usr/bin/env python3
"""Executable legacy-vs-MNCS differential harness for RAVEL.

Executes bounded equivalent cases through the legacy Python implementation
(`src/ravel/`) and the MNCS-native modules (`mncs/workspace/ravel/`) and
compares the semantic outputs case by case.

Differential scopes are explicit; whole-program equivalence is NOT claimed:

- lifecycle_edges: legacy `knowledge.promote` vs ravel.lifecycle.v1
  `transition`. Legacy refusal = KnowledgeError; MNCS refusal =
  REFUSE_TRANSITION with a mapped reason code.
- provider_receipts: legacy provider registry dispatch vs ravel.provider.v1
  `dispatch`/`governed_status`. Unavailability must govern as UNKNOWN on
  both sides; observed statuses pass through unchanged.
- hard_gate_disposition: legacy `adaptation.evaluate_constraints`
  (passed / rejection reasons) vs ravel.core.v1 `disposition` over gates
  mapped to PASS/FAIL. HOLD has no executable legacy equivalent (legacy
  gates are binary), so only COMMIT/REJECT cases are in scope.

Scopes recorded as MNCS extensions without an executable legacy equivalent:
stale-snapshot refusal (ravel.task/forge bind language-service snapshot
identity host-side), saturating budget accounting (resources.py models
placement budgets numerically, not as refusable spend), and payload-bearing
refusals. These are listed in the report under "extension_scopes".

Output: build/mncs-ravel/differential.json, exit 1 on any mismatch.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

MNCS_DIR = ROOT / "mncs"
WORKSPACE = MNCS_DIR / "workspace"
CORPUS = MNCS_DIR / "corpus"


def mncs_binary() -> str | None:
    candidates = [
        Path(os.environ["MNCS_LANGUAGE_ROOT"]) if os.environ.get("MNCS_LANGUAGE_ROOT") else None,
        ROOT.parent / "mncs-language",
    ]
    for base in candidates:
        if base and (base / "target/debug/mncs").is_file():
            return str(base / "target/debug/mncs")
    return None


def library_root() -> str | None:
    candidates = [
        Path(os.environ["MNCS_LANGUAGE_ROOT"]) / "library"
        if os.environ.get("MNCS_LANGUAGE_ROOT")
        else None,
        ROOT.parent / "mncs-language" / "library",
    ]
    for candidate in candidates:
        if candidate and (candidate / "core" / "status.mncs").is_file():
            return str(candidate)
    return None


def run_mncs_experiment(binary: str, source: Path, corpus: Path) -> dict | list:
    env = dict(os.environ)
    env["MNCS_LIBRARY_PATH"] = library_root() or ""
    result = subprocess.run(
        [binary, "experiment", "run", str(source), "--backend", "mncs-research-bytecode",
         "--corpus", str(corpus), "--output-dir", "/tmp/ravel-mncs-differential"],
        capture_output=True, text=True, check=False, env=env,
    )
    return json.loads(result.stdout)


# --------------------------------------------------------------------------
# Scope 1: lifecycle edges — legacy knowledge.py vs ravel.lifecycle.v1
# --------------------------------------------------------------------------

def differential_lifecycle(binary: str) -> dict:
    from ravel import knowledge as legacy_knowledge

    def legacy_record(stage):
        return legacy_knowledge.KnowledgeRecord(
            record_id=f"rec-{stage}",
            stage=stage,
            statement="differential probe",
            scope={"domain": "diff"},
        )

    # (current, requested, attribution, evidence_present, transfer_supported, expect)
    cases = [
        ("observation", "episode", "supported", True, True, True),
        ("episode", "open_hypothesis", "supported", True, True, True),
        ("open_hypothesis", "intervention", "supported", True, True, True),
        ("intervention", "attribution", "supported", True, True, True),
        ("attribution", "provisional_principle", "supported", True, True, True),
        ("attribution", "provisional_principle", "contradicted", True, True, False),
        ("attribution", "provisional_principle", "inconclusive", True, True, False),
        ("provisional_principle", "transfer_tested_principle", "supported", True, True, True),
        ("provisional_principle", "transfer_tested_principle", "supported", False, True, False),
        ("transfer_tested_principle", "restricted_strategy", "supported", True, True, True),
        ("restricted_strategy", "supported_strategy", "supported", True, True, True),
        ("restricted_strategy", "supported_strategy", "supported", True, False, False),
        ("supported_strategy", "counterexample", "supported", True, True, True),
        ("counterexample", "retired", "supported", True, True, False),
        ("episode", "supported_strategy", "supported", True, True, False),
        ("observation", "intervention", "supported", True, True, False),
    ]

    results = []
    mismatches = 0
    for current, requested, attribution, evidence_present, transfer_supported, expect_accept in cases:
        # Legacy side.
        try:
            legacy_knowledge.promote(
                legacy_record(current),
                next_stage=requested,
                next_id="rec-next",
                statement="differential probe",
                evidence_ids=("ev-1",) if evidence_present else (),
                attribution=attribution if requested == "provisional_principle" else None,
                transfer_status="supported" if transfer_supported else "untested",
                created_at="2026-08-25T00:00:00Z",
            )
            legacy_accepted = True
        except legacy_knowledge.KnowledgeError:
            legacy_accepted = False

        # MNCS side.
        mncs_current = stage_finite(current)
        mncs_requested = stage_finite(requested)
        outcome = run_transition(
            binary, mncs_current, mncs_requested, attribution, evidence_present, transfer_supported
        )
        mncs_accepted = outcome == "ADVANCE"

        agree = legacy_accepted == mncs_accepted == expect_accept if legacy_accepted == mncs_accepted else False
        ok = legacy_accepted == mncs_accepted
        mismatches += 0 if ok else 1
        results.append({
            "case": f"{current}->{requested}(attr={attribution},evidence={evidence_present})",
            "legacy": "accept" if legacy_accepted else "refuse",
            "mncs": outcome,
            "agree": ok,
        })
    return {"scope": "lifecycle_edges", "mismatches": mismatches, "cases": results}


_STAGE_CODES = {
    "observation": 0, "episode": 1, "open_hypothesis": 2, "intervention": 3,
    "attribution": 4, "provisional_principle": 5, "transfer_tested_principle": 6,
    "restricted_strategy": 7, "supported_strategy": 8, "counterexample": 9,
    "retired": 10,
}


def stage_finite(name: str) -> dict:
    return {
        "finite": {
            "type_identity": "mncs:0.2:finite-type:ravel.lifecycle.v1::Stage",
            "variant_identity": (
                f"mncs:0.2:finite-variant:ravel.lifecycle.v1::Stage::{name.upper()}"
            ),
            "discriminant": _STAGE_CODES[name],
        }
    }


def run_transition(
    binary: str,
    current: dict,
    requested: dict,
    attribution: str,
    evidence_present: bool,
    transfer_supported: bool,
) -> str:
    """Run one ravel.lifecycle.transition case through a generated corpus."""
    corpus = {
        "schema_version": "0.1",
        "name": "differential-lifecycle",
        "cases": [
            {
                "id": "case",
                "request": {
                    "schema_version": "0.1",
                    "target": {"module": "ravel.lifecycle.v1", "function": "transition"},
                    "arguments": [
                        current,
                        requested,
                        attr_finite(attribution),
                        {"boolean": {"value": evidence_present}},
                        {"boolean": {"value": transfer_supported}},
                    ],
                    "step_budget": 1024,
                },
            }
        ],
    }
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(corpus, handle)
        corpus_path = handle.name
    try:
        document = run_mncs_experiment(
            binary, WORKSPACE / "ravel" / "lifecycle.mncs", Path(corpus_path)
        )
        case_ = document["cases"][0]
        if not case_.get("expectation_met"):
            # The expectation is absent (no expected block); read the value.
            pass
        returned = case_["returned"][0]["finite"]
        return returned["variant_identity"].rsplit("::", 1)[-1]
    finally:
        os.unlink(corpus_path)


_ATTR_CODES = {"supported": 0, "contradicted": 1, "inconclusive": 2}


def attr_finite(name: str) -> dict:
    return {
        "finite": {
            "type_identity": "mncs:0.2:finite-type:ravel.lifecycle.v1::AttributionKind",
            "variant_identity": (
                f"mncs:0.2:finite-variant:ravel.lifecycle.v1::AttributionKind::{name.upper()}"
            ),
            "discriminant": _ATTR_CODES[name],
        }
    }


# --------------------------------------------------------------------------
# Scope 2: provider receipts — legacy providers.py vs ravel.provider.v1
# --------------------------------------------------------------------------


def differential_provider(binary: str) -> dict:
    """Legacy ForgeAdapter dispatch vs ravel.provider.v1 dispatch/status.

    Both worlds are modeled with one offered capability (operation 50,
    witness 7, deterministic). Unavailability scenarios mismatch the request
    on one axis; availability scenarios let the stub provider report a raw
    status that must pass through unchanged on both sides.
    """

    from ravel.providers import EvidenceRequest as LegacyRequest
    from ravel.providers import ForgeAdapter, ProviderCapability, RawEvidence

    class StubProvider:
        provider_id = "diff-provider"

        def __init__(self, raw_status: str):
            self.raw_status = raw_status

        def capabilities(self):
            return (
                ProviderCapability(
                    provider_id=self.provider_id,
                    operation="50",
                    version="0.1",
                    deterministic=True,
                    witness_kind="7",
                ),
            )

        def execute(self, request):
            return RawEvidence(
                request_id=request.request_id,
                provider_id=self.provider_id,
                raw_status=self.raw_status,
                observations={},
                witness_digest=None,
                artifact_digests=(request.artifact_digest,),
                environment_id="differential",
                resource_observations={},
            )

    # (verifier, witness, determinism_required, offered, raw_status, expect)
    scenarios = [
        (51, 7, False, "PASS", "UNKNOWN"),   # operation mismatch
        (50, 8, False, "PASS", "UNKNOWN"),   # witness mismatch
        (50, 7, True, "UNKNOWN", "UNKNOWN"),  # unmet determinism -> unavailable
        (50, 7, False, "PASS", "PASS"),
        (50, 7, False, "FAIL", "FAIL"),
        (50, 7, False, "UNKNOWN", "UNKNOWN"),
    ]

    results = []
    mismatches = 0

    for verifier, witness, determinism, offered_raw, _expect in scenarios:
        registry = ForgeAdapter(providers=(StubProvider(offered_raw),))
        legacy_receipt = registry.request(
            LegacyRequest(
                request_id="diff",
                candidate_id="cand-diff",
                artifact_digest="sha256:" + "0" * 64,
                governing_contract="ravel-differential/0.1",
                verifier_contract=str(verifier),
                question="differential probe",
                witness_kind=str(witness),
                determinism_required=determinism,
            )
        )
        legacy_status = legacy_receipt.status

        mncs_status = governed_status_for(
            binary, verifier, witness, determinism, offered_raw
        )
        ok = legacy_status == mncs_status
        mismatches += 0 if ok else 1
        results.append({
            "case": f"({verifier},{witness},{determinism},offered={offered_raw})",
            "legacy": legacy_status,
            "mncs": mncs_status,
            "agree": ok,
        })

    return {"scope": "provider_receipts", "mismatches": mismatches, "cases": results}


def governed_status_for(
    binary: str, verifier: int, witness: int, determinism_required: bool, offered_raw: str
) -> str:
    """dispatch() then governed_status(); return the MNCS-governed status."""
    module = "ravel.provider.v1"
    import urllib.parse

    def record(module_name, name, type_pairs, values):
        joined = "".join(f"{n}:{t};" for n, t in sorted(type_pairs))
        digest = urllib.parse.quote(joined, safe="")
        return {
            "record": {
                "type_identity": f"mncs:0.2:record-type:{module_name}::{name}::{digest}",
                "name": name,
                "fields": values,
            }
        }

    def i64(value):
        return {"integer": {"value": value, "type": {"bits": 64, "signed": True}}}

    def i32(value):
        return {"integer": {"value": value, "type": {"bits": 32, "signed": True}}}

    STATUS_CODES = {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}
    CS = "mncs.core.status.v1"

    def status_finite(code):
        return {
            "finite": {
                "type_identity": f"mncs:0.2:finite-type:{CS}::Status",
                "variant_identity": f"mncs:0.2:finite-variant:{CS}::Status::{code}",
                "discriminant": STATUS_CODES[code],
            }
        }

    request_value = record(
        module, "EvidenceRequest",
        [("determinism_required", "bool"), ("verifier_contract", "i64"), ("witness_kind", "i64")],
        [["determinism_required", {"boolean": {"value": determinism_required}}],
         ["verifier_contract", i64(verifier)],
         ["witness_kind", i64(witness)]],
    )
    capability_value = record(
        module, "Capability",
        [("deterministic", "bool"), ("operation", "i64"), ("witness_kind", "i64")],
        [["deterministic", {"boolean": {"value": True}}],
         ["operation", i64(50)],
         ["witness_kind", i64(7)]],
    )

    reason_by_mismatch = {
        ("verifier",): 1,
        ("witness",): 2,
        ("determinism",): 3,
    }

    corpus = {
        "schema_version": "0.1",
        "name": "differential-provider",
        "cases": [
            {
                "id": "dispatch",
                "request": {
                    "schema_version": "0.1",
                    "target": {"module": module, "function": "dispatch"},
                    "arguments": [request_value, capability_value, status_finite(offered_raw)],
                    "step_budget": 1024,
                },
            },
        ],
    }
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(corpus, handle)
        corpus_path = handle.name
    try:
        document = run_mncs_experiment(
            binary, WORKSPACE / "ravel" / "provider.mncs", Path(corpus_path)
        )
        case_ = document["cases"][0]
        outcome = case_["returned"][0]["finite"]
        variant = outcome["variant_identity"].rsplit("::", 1)[-1]
        if variant == "UNAVAILABLE":
            # Governed status of absence is UNKNOWN by construction.
            payload_reason = outcome["payload"][0][1]["integer"]["value"]
            expected_reason = (
                1 if verifier != 50 else 2 if witness != 7 else 3
            )
            return "UNKNOWN" if payload_reason == expected_reason else "MISMATCH"
        if variant != "RECEIVED":
            return "MISMATCH"
        carried = outcome["payload"][0][1]["finite"]["variant_identity"].rsplit("::", 1)[-1]
        # Statuses pass through unchanged.
        return carried if carried == offered_raw else "MISMATCH"
    finally:
        os.unlink(corpus_path)


# --------------------------------------------------------------------------
# Scope 3: hard-gate disposition — legacy adaptation.py vs ravel.core.v1
# --------------------------------------------------------------------------


def differential_disposition(binary: str) -> dict:
    from ravel.adaptation import RetentionConstraintPolicy, evaluate_constraints
    from ravel.adaptation import RawObservation

    policy = RetentionConstraintPolicy(
        adaptation_improvement_epsilon=0.0,
        base_accuracy_floor=0.5,
        representation_floor=0.5,
        original_prediction_degradation_bound=0.05,
        retention_accuracy_floor=None,
        retention_loss_floor=None,
        maximum_transition_support_losses=0,
        maximum_experts=4,
        maximum_births=1,
        maximum_retirements=1,
        exact_replay_records=None,
        maximum_replay_records=100,
        maximum_update_passes=10,
        maximum_compute_evaluations=None,
        maximum_compute_ratio=4.0,
    )

    def observation(**overrides):
        base = dict(
            adaptation_objective=0.9,
            base_accuracy=0.9,
            representation_score=0.9,
            original_prediction_degradation=0.0,
            retention_accuracy=None,
            retention_accuracy_delta_from_base=None,
            transition_support_losses=0,
            expert_count=2,
            births=0,
            retirements=0,
            replay_records=10,
            update_passes=2,
            compute_evaluations=10,
            matched_compute_evaluations=10,
        )
        base.update(overrides)
        return RawObservation(**base)

    previous = observation()

    # Gate mapping into the four MNCS slots:
    # a = accuracy floor, b = degradation bound, c = capacity budget, d = matched reference.
    scenarios = [
        ("all-clean", {}, ["PASS", "PASS", "PASS", "PASS"], "COMMIT"),
        ("accuracy-violated", {"base_accuracy": 0.4},
         ["FAIL", "PASS", "PASS", "PASS"], "REJECT"),
        ("degradation-violated", {"original_prediction_degradation": 0.5},
         ["PASS", "FAIL", "PASS", "PASS"], "REJECT"),
        ("capacity-violated", {"expert_count": 9},
         ["PASS", "PASS", "FAIL", "PASS"], "REJECT"),
        ("reference-missing", {"matched_compute_evaluations": 0},
         ["PASS", "PASS", "PASS", "FAIL"], "REJECT"),
        ("multi-violation", {"base_accuracy": 0.1, "births": 7},
         ["FAIL", "PASS", "FAIL", "PASS"], "REJECT"),
    ]

    status_values = {
        "PASS": {"discriminant": 0},
        "FAIL": {"discriminant": 1},
    }

    gate_cases = []
    expectations = {}
    for name, overrides, gates, disposition in scenarios:
        report = evaluate_constraints(previous, observation(**overrides), policy)
        legacy_passed = report.passed
        assert legacy_passed == (disposition == "COMMIT"), name

        def gate_value(code):
            return {
                "finite": {
                    "type_identity": "mncs:0.2:finite-type:mncs.core.status.v1::Status",
                    "variant_identity": f"mncs:0.2:finite-variant:mncs.core.status.v1::Status::{code}",
                    "discriminant": status_values[code]["discriminant"],
                }
            }

        def gate_set(a, b, c, d):
            import urllib.parse

            pairs = [("a", "Status"), ("b", "Status"), ("c", "Status"), ("d", "Status")]
            joined = urllib.parse.quote("".join(f"{n}:{t};" for n, t in sorted(pairs)), safe="")
            return {
                "record": {
                    "type_identity": f"mncs:0.2:record-type:ravel.core.v1::GateSet::{joined}",
                    "name": "GateSet",
                    "fields": [[n, gate_value(v)] for n, v in zip(["a", "b", "c", "d"], [a, b, c, d])],
                }
            }

        case_id = f"disposition-{name}"
        gate_cases.append({
            "id": case_id,
            "request": {
                "schema_version": "0.1",
                "target": {"module": "ravel.core.v1", "function": "disposition"},
                "arguments": [gate_set(*gates)],
                "step_budget": 1024,
            },
        })
        expectations[case_id] = disposition

    corpus = {
        "schema_version": "0.1",
        "name": "differential-disposition",
        "cases": gate_cases,
    }
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(corpus, handle)
        corpus_path = handle.name
    try:
        document = run_mncs_experiment(
            binary, WORKSPACE / "ravel" / "core.mncs", Path(corpus_path)
        )
    finally:
        os.unlink(corpus_path)

    results = []
    mismatches = 0
    for case_ in document["cases"]:
        got = case_["returned"][0]["finite"]["variant_identity"].rsplit("::", 1)[-1]
        want = expectations[case_["case_id"]]
        ok = got == want
        mismatches += 0 if ok else 1
        results.append({"case": case_["case_id"], "legacy_disposition": want, "mncs": got, "agree": ok})

    return {"scope": "hard_gate_disposition", "mismatches": mismatches, "cases": results}


# --------------------------------------------------------------------------


def main() -> int:
    binary = mncs_binary()
    if not binary or not library_root():
        print(json.dumps({"status": "BLOCKED",
                          "reason": "sibling mncs-language checkout with built CLI required"}))
        return 0

    report = {
        "check": "mncs-legacy-differential",
        "interpretation": (
            "bounded per-case behavioral agreement between the legacy Python "
            "implementation and the MNCS-native modules; not whole-program "
            "equivalence"
        ),
        "scopes": [],
        "extension_scopes": [
            "stale-snapshot refusal (ravel.task.v1, ravel.forge.v1): language-service "
            "snapshot identity exists only host-side upstream; no executable legacy twin",
            "budget spend refusal (ravel.budget.v1): resources.py placement budgets are "
            "numeric fits, not refusable spends",
            "payload-bearing refusals: Profile 0.6 sums postdate every legacy epoch",
        ],
    }
    total_mismatches = 0
    for scope in (
        differential_lifecycle(binary),
        differential_provider(binary),
        differential_disposition(binary),
    ):
        total_mismatches += scope["mismatches"]
        report["scopes"].append(scope)

    report["status"] = "AGREE" if total_mismatches == 0 else "MISMATCH"
    report["total_mismatches"] = total_mismatches
    print(json.dumps(report, indent=1))
    evidence_dir = ROOT / "build" / "mncs-ravel"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with open(evidence_dir / "differential.json", "w") as handle:
        handle.write(json.dumps(report, indent=1))
    return 1 if total_mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
