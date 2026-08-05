#!/usr/bin/env python3
"""Validate the recursive experience substrate profile and reference records."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent
PROFILE_PATH = ROOT / "architecture-profile.json"
RECORDS_PATH = ROOT / "reference-records.json"

RECORD_ID_FIELDS = {
    "experience_episode": "episode_id",
    "causal_hypothesis": "hypothesis_id",
    "intervention_record": "intervention_id",
    "causal_attribution": "attribution_id",
    "learned_principle": "principle_id",
    "strategy_record": "strategy_id",
}

REQUIRED_MEMORY_CLASSES = {
    "episodic",
    "causal",
    "semantic",
    "procedural",
    "negative",
}

REQUIRED_OUTCOMES = {"success", "error", "neutral", "abstention"}

REQUIRED_CREDIT_CLASSES = {
    "immediate",
    "enabling",
    "delayed-descendant",
    "transfer",
    "retention",
    "negative-downstream",
}

REQUIRED_CONTROLS = {
    "shuffled-attribution-control",
    "success-memory-ablation",
    "negative-memory-ablation",
    "transfer-holdout",
    "aggregate-only-feedback-control",
}

REQUIRED_NEGATIVE_TESTS = {
    "evaluator-authority-expansion",
    "error-only-memory",
    "deleted-failure-memory",
    "post-hoc-hypothesis",
    "unsupported-principle",
    "strategy-without-failure-modes",
    "global-reuse-without-transfer",
    "attribution-without-credit-class",
    "aggregate-only-causal-promotion",
    "future-final-early-access",
}


class ExperienceValidationError(ValueError):
    """Raised when the recursive experience boundary is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperienceValidationError(message)


def _object(value: object, name: str) -> dict[str, Any]:
    _require(isinstance(value, dict), name)
    return cast(dict[str, Any], value)


def _list(value: object, name: str) -> list[Any]:
    _require(isinstance(value, list), name)
    return cast(list[Any], value)


def _strings(value: object, name: str, *, nonempty: bool = False) -> list[str]:
    items = _list(value, name)
    _require(all(isinstance(item, str) and item for item in items), name)
    if nonempty:
        _require(bool(items), name)
    return cast(list[str], items)


def _require_false_fields(value: dict[str, Any], fields: tuple[str, ...], name: str) -> None:
    for field in fields:
        _require(value.get(field) is False, f"forbidden {name}: {field}")


def _status_sets(profile: dict[str, Any]) -> dict[str, set[str]]:
    statuses = _object(profile.get("allowed_statuses"), "allowed_statuses")
    return {
        name: set(_strings(statuses.get(name), f"allowed statuses: {name}", nonempty=True))
        for name in (
            "episode_outcome_class",
            "hypothesis_disposition",
            "principle_maturity",
            "transfer_status",
            "strategy_reuse_status",
        )
    }


def validate_profile(profile: dict[str, Any]) -> None:
    _require(
        profile.get("schema") == "mncs-recursive-experience-substrate/0.1",
        "schema",
    )
    _require(profile.get("status") == "design-only", "status")

    relationship = _object(profile.get("relationship"), "relationship")
    _require(relationship.get("phase") == "post-ravel-0.6", "relationship phase")
    _require(
        relationship.get("extends_recursive_architecture_study") is True,
        "recursive architecture relationship",
    )
    _require_false_fields(
        relationship,
        (
            "changes_existing_preregistration",
            "may_modify_frozen_ravel_0_4_or_0_5",
            "may_modify_ravel_0_6_preregistration_or_final_material",
        ),
        "relationship permission",
    )

    authority = _object(profile.get("immutable_authority"), "immutable_authority")
    _require_false_fields(
        authority,
        (
            "experience_system_may_modify_evaluator",
            "experience_system_may_modify_thresholds",
            "experience_system_may_modify_partitions",
            "experience_system_may_modify_resource_policy",
            "experience_system_may_access_future_final_before_freeze",
            "experience_system_may_authorize_promotion",
            "experience_system_may_delete_failed_or_rejected_records",
        ),
        "authority permission",
    )

    memory_classes = set(_strings(profile.get("memory_classes"), "memory_classes", nonempty=True))
    _require(memory_classes >= REQUIRED_MEMORY_CLASSES, "memory classes")

    vocabulary = _object(profile.get("record_vocabulary"), "record_vocabulary")
    _require(set(RECORD_ID_FIELDS) <= set(vocabulary), "record vocabulary")
    for record_type in RECORD_ID_FIELDS:
        fields = _strings(
            vocabulary.get(record_type),
            f"record fields: {record_type}",
            nonempty=True,
        )
        _require(len(fields) == len(set(fields)), f"duplicate record field: {record_type}")

    statuses = _status_sets(profile)
    _require(statuses["episode_outcome_class"] >= REQUIRED_OUTCOMES, "episode statuses")
    _require(
        {"open", "supported", "challenged", "rejected", "inconclusive"}
        <= statuses["hypothesis_disposition"],
        "hypothesis statuses",
    )
    _require(
        {"provisional", "supported", "challenged", "rejected", "retired"}
        <= statuses["principle_maturity"],
        "principle maturity",
    )
    _require(
        {"untested", "failed", "partial", "supported"} <= statuses["transfer_status"],
        "transfer statuses",
    )
    _require(
        {"untested", "restricted", "supported", "retired"} <= statuses["strategy_reuse_status"],
        "strategy reuse statuses",
    )

    required_outcomes = set(
        _strings(profile.get("required_episode_outcomes"), "required_episode_outcomes")
    )
    _require(required_outcomes >= REQUIRED_OUTCOMES, "required episode outcomes")

    credit_classes = set(_strings(profile.get("credit_classes"), "credit_classes", nonempty=True))
    _require(credit_classes >= REQUIRED_CREDIT_CLASSES, "credit classes")

    diagnostics = _object(
        profile.get("diagnostic_requirements"),
        "diagnostic_requirements",
    )
    _require(
        diagnostics.get("structured_probe_identity_required") is True,
        "probe identity",
    )
    _require(
        diagnostics.get("counterfactual_or_control_required_for_supported_causal_claim") is True,
        "causal control requirement",
    )
    _require(
        diagnostics.get("aggregate_score_alone_may_support_causal_claim") is False,
        "aggregate causal promotion",
    )
    _require(
        diagnostics.get("provider_or_verifier_status_may_be_redefined") is False,
        "verifier status redefinition",
    )
    _require(
        diagnostics.get("hidden_reasoning_transcript_required") is False,
        "hidden reasoning requirement",
    )

    reuse = _object(profile.get("reuse_rules"), "reuse_rules")
    for field in (
        "principle_must_bind_supporting_attributions",
        "strategy_must_bind_principles",
        "failed_and_rejected_experience_must_remain_retrievable",
        "reuse_must_bind_context_and_candidate_lineage",
    ):
        _require(reuse.get(field) is True, f"reuse rule: {field}")
    _require(
        reuse.get("untested_transfer_may_authorize_global_reuse") is False,
        "untested transfer reuse",
    )

    controls = set(_strings(profile.get("required_controls"), "required_controls"))
    _require(controls >= REQUIRED_CONTROLS, "required controls")

    hard_gates = set(_strings(profile.get("hard_gates"), "hard_gates"))
    _require(
        {
            "immutable-evaluator-authority",
            "append-only-experience-lineage",
            "hypotheses-recorded-before-intervention",
            "all-outcome-classes-retained",
            "principles-bind-attributions-and-falsifiers",
            "strategies-bind-principles-and-known-failure-modes",
            "global-reuse-requires-transfer-support",
            "future-final-material-unavailable-before-freeze",
        }
        <= hard_gates,
        "hard gates",
    )

    negative_tests = set(
        _strings(profile.get("required_negative_tests"), "required_negative_tests")
    )
    _require(negative_tests >= REQUIRED_NEGATIVE_TESTS, "required negative tests")

    claim = _object(profile.get("claim_boundary"), "claim_boundary")
    _require(claim.get("formal_mncs_status") == "UNKNOWN", "MNCS claim")
    _require(claim.get("formal_mncds_status") == "UNKNOWN", "MNCDS claim")
    _require(
        claim.get("general_recursive_self_improvement") == "UNKNOWN",
        "recursive improvement claim",
    )
    _require(claim.get("promotion_authorized") is False, "promotion boundary")


def _normalize_records(
    profile: dict[str, Any], bundle: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    vocabulary = _object(profile.get("record_vocabulary"), "record_vocabulary")
    records = _object(bundle.get("records"), "records")
    normalized: dict[str, list[dict[str, Any]]] = {}
    all_ids: set[str] = set()

    for record_type, id_field in RECORD_ID_FIELDS.items():
        required_fields = set(
            _strings(vocabulary.get(record_type), f"record fields: {record_type}")
        )
        values = _list(records.get(record_type), f"records: {record_type}")
        _require(bool(values), f"records: {record_type}")
        typed_values: list[dict[str, Any]] = []

        for index, value in enumerate(values):
            record = _object(value, f"record object: {record_type}[{index}]")
            _require(
                required_fields <= set(record),
                f"missing fields: {record_type}[{index}]",
            )
            record_id = record.get(id_field)
            _require(
                isinstance(record_id, str) and bool(record_id),
                f"record id: {record_type}",
            )
            _require(record_id not in all_ids, f"duplicate record id: {record_id}")
            all_ids.add(record_id)
            typed_values.append(record)

        normalized[record_type] = typed_values

    return normalized


def _validate_episodes(
    profile: dict[str, Any],
    records: dict[str, list[dict[str, Any]]],
    statuses: dict[str, set[str]],
) -> set[str]:
    episodes = records["experience_episode"]
    episode_ids = {str(record["episode_id"]) for record in episodes}
    observed_outcomes: set[str] = set()

    for episode in episodes:
        episode_id = str(episode["episode_id"])
        outcome = episode.get("outcome_class")
        _require(outcome in statuses["episode_outcome_class"], f"episode outcome: {episode_id}")
        observed_outcomes.add(str(outcome))
        _strings(episode.get("route"), f"episode route: {episode_id}")
        _strings(episode.get("observed_anomalies"), f"episode anomalies: {episode_id}")
        cost = episode.get("resource_cost")
        _require(
            isinstance(cost, int) and cost >= 0,
            f"episode resource cost: {episode_id}",
        )

    required_outcomes = set(
        _strings(profile.get("required_episode_outcomes"), "required episode outcomes")
    )
    _require(
        required_outcomes <= observed_outcomes,
        "error-only or incomplete experience memory",
    )
    return episode_ids


def _validate_hypotheses(
    records: dict[str, list[dict[str, Any]]],
    episode_ids: set[str],
    statuses: dict[str, set[str]],
) -> set[str]:
    hypotheses = records["causal_hypothesis"]
    hypothesis_ids = {str(record["hypothesis_id"]) for record in hypotheses}

    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis["hypothesis_id"])
        supporting = set(
            _strings(
                hypothesis.get("supporting_episode_ids"),
                f"supporting episodes: {hypothesis_id}",
                nonempty=True,
            )
        )
        _require(supporting <= episode_ids, f"unknown supporting episode: {hypothesis_id}")

        competing = set(
            _strings(
                hypothesis.get("competing_hypothesis_ids"),
                f"competing hypotheses: {hypothesis_id}",
                nonempty=True,
            )
        )
        _require(
            competing <= hypothesis_ids,
            f"unknown competing hypothesis: {hypothesis_id}",
        )
        _strings(
            hypothesis.get("required_probe_ids"),
            f"required probes: {hypothesis_id}",
            nonempty=True,
        )
        _require(
            hypothesis.get("recorded_before_intervention") is True,
            f"post-hoc hypothesis: {hypothesis_id}",
        )
        _require(
            hypothesis.get("disposition") in statuses["hypothesis_disposition"],
            f"hypothesis disposition: {hypothesis_id}",
        )
        _require(bool(hypothesis.get("falsifier")), f"hypothesis falsifier: {hypothesis_id}")

    return hypothesis_ids


def _validate_interventions(
    records: dict[str, list[dict[str, Any]]], hypothesis_ids: set[str]
) -> set[str]:
    interventions = records["intervention_record"]
    intervention_ids = {str(record["intervention_id"]) for record in interventions}

    for intervention in interventions:
        intervention_id = str(intervention["intervention_id"])
        _require(
            intervention.get("hypothesis_id") in hypothesis_ids,
            f"unknown intervention hypothesis: {intervention_id}",
        )
        parent = intervention.get("parent_candidate_identity")
        child = intervention.get("child_candidate_identity")
        _require(
            isinstance(parent, str) and bool(parent),
            f"intervention parent: {intervention_id}",
        )
        _require(
            isinstance(child, str) and bool(child),
            f"intervention child: {intervention_id}",
        )
        _require(parent != child, f"in-place intervention: {intervention_id}")
        _require(
            intervention.get("rollback_target") == parent,
            f"rollback target: {intervention_id}",
        )
        _strings(
            intervention.get("affected_surfaces"),
            f"affected surfaces: {intervention_id}",
            nonempty=True,
        )
        predicted = _object(
            intervention.get("predicted_effects"),
            f"predicted effects: {intervention_id}",
        )
        _require(bool(predicted), f"predicted effects: {intervention_id}")
        _object(
            intervention.get("resource_budget"),
            f"resource budget: {intervention_id}",
        )

    return intervention_ids


def _validate_attributions(
    profile: dict[str, Any],
    records: dict[str, list[dict[str, Any]]],
    intervention_ids: set[str],
    statuses: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    attributions = records["causal_attribution"]
    allowed_credit = set(_strings(profile.get("credit_classes"), "credit classes"))
    attribution_by_id = {str(record["attribution_id"]): record for record in attributions}

    for attribution_id, attribution in attribution_by_id.items():
        _require(
            attribution.get("intervention_id") in intervention_ids,
            f"unknown attribution intervention: {attribution_id}",
        )
        _object(attribution.get("actual_effects"), f"actual effects: {attribution_id}")
        _require(
            attribution.get("hypothesis_disposition") in statuses["hypothesis_disposition"],
            f"attribution disposition: {attribution_id}",
        )
        _strings(
            attribution.get("alternative_explanations_remaining"),
            f"alternative explanations: {attribution_id}",
        )
        credits = set(
            _strings(
                attribution.get("credit_classes"),
                f"credit classes: {attribution_id}",
                nonempty=True,
            )
        )
        _require(credits <= allowed_credit, f"unknown credit class: {attribution_id}")
        _require(
            bool(attribution.get("evaluator_identity")),
            f"evaluator identity: {attribution_id}",
        )

    return attribution_by_id


def _validate_principles(
    records: dict[str, list[dict[str, Any]]],
    episode_ids: set[str],
    attribution_by_id: dict[str, dict[str, Any]],
    statuses: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    principles = records["learned_principle"]
    attribution_ids = set(attribution_by_id)
    principle_by_id = {str(record["principle_id"]): record for record in principles}

    for principle_id, principle in principle_by_id.items():
        supporting = set(
            _strings(
                principle.get("supporting_attribution_ids"),
                f"principle attributions: {principle_id}",
                nonempty=True,
            )
        )
        _require(
            supporting <= attribution_ids,
            f"unknown principle attribution: {principle_id}",
        )
        counterexamples = set(
            _strings(
                principle.get("counterexample_episode_ids"),
                f"principle counterexamples: {principle_id}",
            )
        )
        _require(
            counterexamples <= episode_ids,
            f"unknown principle counterexample: {principle_id}",
        )
        _require(
            principle.get("maturity") in statuses["principle_maturity"],
            f"principle maturity: {principle_id}",
        )
        transfer = principle.get("transfer_status")
        _require(
            transfer in statuses["transfer_status"],
            f"principle transfer: {principle_id}",
        )
        _require(bool(principle.get("falsifier")), f"principle falsifier: {principle_id}")
        _object(principle.get("scope"), f"principle scope: {principle_id}")

        if transfer == "supported":
            _require(
                any(
                    "transfer" in attribution_by_id[item].get("credit_classes", [])
                    for item in supporting
                ),
                f"transfer support evidence: {principle_id}",
            )

    return principle_by_id


def _validate_strategies(
    records: dict[str, list[dict[str, Any]]],
    principle_by_id: dict[str, dict[str, Any]],
    statuses: dict[str, set[str]],
) -> None:
    principle_ids = set(principle_by_id)

    for strategy in records["strategy_record"]:
        strategy_id = str(strategy["strategy_id"])
        bound_principles = set(
            _strings(
                strategy.get("principle_ids"),
                f"strategy principles: {strategy_id}",
                nonempty=True,
            )
        )
        _require(
            bound_principles <= principle_ids,
            f"unknown strategy principle: {strategy_id}",
        )
        _strings(
            strategy.get("preconditions"),
            f"strategy preconditions: {strategy_id}",
            nonempty=True,
        )
        _strings(
            strategy.get("known_failure_modes"),
            f"strategy failure modes: {strategy_id}",
            nonempty=True,
        )
        _object(strategy.get("applicability_scope"), f"strategy scope: {strategy_id}")

        reuse_status = strategy.get("reuse_status")
        _require(
            reuse_status in statuses["strategy_reuse_status"],
            f"strategy reuse status: {strategy_id}",
        )
        if reuse_status == "supported":
            _require(
                all(
                    principle_by_id[item].get("transfer_status") == "supported"
                    for item in bound_principles
                ),
                f"global reuse without transfer: {strategy_id}",
            )


def validate_records(profile: dict[str, Any], bundle: dict[str, Any]) -> None:
    _require(
        bundle.get("schema") == "mncs-recursive-experience-records/0.1",
        "record schema",
    )
    _require(bundle.get("profile_id") == profile.get("profile_id"), "profile identity")

    records = _normalize_records(profile, bundle)
    statuses = _status_sets(profile)
    episode_ids = _validate_episodes(profile, records, statuses)
    hypothesis_ids = _validate_hypotheses(records, episode_ids, statuses)
    intervention_ids = _validate_interventions(records, hypothesis_ids)
    attribution_by_id = _validate_attributions(
        profile,
        records,
        intervention_ids,
        statuses,
    )
    principle_by_id = _validate_principles(
        records,
        episode_ids,
        attribution_by_id,
        statuses,
    )
    _validate_strategies(records, principle_by_id, statuses)

    rejected_hypotheses = {
        str(record["hypothesis_id"])
        for record in records["causal_hypothesis"]
        if record.get("disposition") == "rejected"
    }
    _require(bool(rejected_hypotheses), "negative memory must retain rejected hypotheses")

    controls = set(_strings(bundle.get("controls_applied"), "controls applied"))
    required_controls = set(_strings(profile.get("required_controls"), "required controls"))
    _require(required_controls <= controls, "missing experience control")


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExperienceValidationError(f"{path.name} must contain an object")
    return cast(dict[str, Any], value)


def mutated_fixture(
    profile: dict[str, Any],
    bundle: dict[str, Any],
    mutation: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return deterministic negative fixtures for the executable regression test."""

    profile_copy = copy.deepcopy(profile)
    bundle_copy = copy.deepcopy(bundle)
    records = bundle_copy["records"]

    if mutation == "evaluator-authority-expansion":
        profile_copy["immutable_authority"]["experience_system_may_modify_evaluator"] = True
    elif mutation == "error-only-memory":
        records["experience_episode"] = [
            item for item in records["experience_episode"] if item["outcome_class"] == "error"
        ]
    elif mutation == "deleted-failure-memory":
        records["experience_episode"] = [
            item for item in records["experience_episode"] if item["outcome_class"] != "error"
        ]
    elif mutation == "post-hoc-hypothesis":
        records["causal_hypothesis"][0]["recorded_before_intervention"] = False
    elif mutation == "unsupported-principle":
        records["learned_principle"][0]["supporting_attribution_ids"] = []
    elif mutation == "strategy-without-failure-modes":
        records["strategy_record"][0]["known_failure_modes"] = []
    elif mutation == "global-reuse-without-transfer":
        records["learned_principle"][0]["transfer_status"] = "untested"
    elif mutation == "attribution-without-credit-class":
        records["causal_attribution"][0]["credit_classes"] = []
    elif mutation == "aggregate-only-causal-promotion":
        profile_copy["diagnostic_requirements"][
            "aggregate_score_alone_may_support_causal_claim"
        ] = True
    elif mutation == "future-final-early-access":
        profile_copy["immutable_authority"][
            "experience_system_may_access_future_final_before_freeze"
        ] = True
    else:
        raise KeyError(mutation)

    return profile_copy, bundle_copy


def main() -> int:
    profile = load_object(PROFILE_PATH)
    bundle = load_object(RECORDS_PATH)
    validate_profile(profile)
    validate_records(profile, bundle)
    print("recursive experience substrate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
