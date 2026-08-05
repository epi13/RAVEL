#!/usr/bin/env python3
"""Validate the recursive architecture comparison research boundary."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PLAN_PATH = ROOT / "study-plan.json"


class StudyValidationError(ValueError):
    """Raised when the research design violates a required boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StudyValidationError(message)


def validate(plan: dict[str, Any]) -> None:
    _require(plan.get("schema") == "mncs-recursive-architecture-study/0.1", "schema")
    _require(plan.get("status") == "preregistered-design-only", "status")

    authority = plan.get("immutable_authority")
    _require(isinstance(authority, dict), "immutable_authority")
    forbidden_permissions = (
        "generator_may_modify_evaluator",
        "generator_may_modify_thresholds",
        "generator_may_modify_partitions",
        "generator_may_modify_resource_policy",
        "generator_may_access_future_final_before_freeze",
        "generator_may_authorize_promotion",
    )
    for permission in forbidden_permissions:
        _require(authority.get(permission) is False, f"forbidden permission: {permission}")

    budgets = plan.get("budgets")
    _require(isinstance(budgets, dict), "budgets")
    for field in (
        "candidate_slots_per_arm",
        "max_lineage_depth",
        "max_children_per_candidate",
        "max_bounded_operations_per_arm",
    ):
        value = budgets.get(field)
        _require(isinstance(value, int) and value > 0, f"positive budget: {field}")
    _require(
        budgets.get("equal_budget_before_adaptive_portfolio_allocation") is True,
        "equal-budget prephase",
    )

    arms = plan.get("architecture_arms")
    _require(isinstance(arms, list) and len(arms) >= 5, "architecture_arms")
    ids = [arm.get("id") for arm in arms if isinstance(arm, dict)]
    _require(len(ids) == len(arms), "arm object")
    _require(all(isinstance(value, str) and value for value in ids), "arm id")
    _require(len(ids) == len(set(ids)), "duplicate arm id")

    allowed_layers = {"parameter", "structural", "policy", "portfolio"}
    for arm in arms:
        arm_id = arm["id"]
        layers = arm.get("recursive_layers")
        _require(isinstance(layers, list), f"layers: {arm_id}")
        _require(set(layers) <= allowed_layers, f"unknown layer: {arm_id}")
        _require(arm.get("candidate_replacement") is True, f"replacement: {arm_id}")
        _require(
            arm.get("in_place_mutation_after_evaluation") is False,
            f"in-place mutation: {arm_id}",
        )
        if arm.get("policy_replacement"):
            _require("policy" in layers, f"policy layer missing: {arm_id}")
        if arm.get("portfolio_allocation"):
            _require("portfolio" in layers, f"portfolio layer missing: {arm_id}")

    required_controls = plan.get("required_controls")
    _require(isinstance(required_controls, list), "required_controls")
    _require(set(required_controls) <= set(ids), "missing required control")
    classes = {arm["id"]: arm.get("class") for arm in arms}
    _require(all(classes[item] == "control" for item in required_controls), "control class")
    feedback = {arm["id"]: arm.get("feedback") for arm in arms}
    _require(feedback.get("random-proposal-control") == "none", "random control")
    _require(feedback.get("shuffled-feedback-control") == "shuffled", "shuffled control")
    _require(
        feedback.get("diagnostic-ablation-control") == "aggregate-only",
        "diagnostic ablation",
    )

    required_fields = set(plan.get("candidate_record_required_fields", []))
    _require(
        {
            "candidate_id",
            "parent_ids",
            "content_identity",
            "predicted_effects",
            "actual_effects",
            "disposition",
            "rollback_target",
        }
        <= required_fields,
        "candidate record fields",
    )

    partitions = set(plan.get("partitions", []))
    _require(
        {"development", "selection", "transfer-unseen", "future-final"} <= partitions,
        "partitions",
    )

    hard_gates = set(plan.get("hard_gates", []))
    _require(
        {
            "zero_evaluator_identity_changes",
            "zero_threshold_changes",
            "zero_future_final_access_before_freeze",
            "acyclic_append_only_lineage",
            "rejected_transactions_preserve_parent_identity",
            "predictions_recorded_before_evaluation",
        }
        <= hard_gates,
        "hard gates",
    )

    negative_tests = set(plan.get("required_negative_tests", []))
    _require(
        {
            "evaluator-modification",
            "threshold-modification",
            "future-final-early-access",
            "in-place-post-evaluation-mutation",
            "lineage-cycle",
            "post-hoc-prediction",
            "rejected-update-checkpoint-change",
            "missing-causal-feedback-control",
        }
        <= negative_tests,
        "negative tests",
    )

    rule = plan.get("selection_rule")
    _require(isinstance(rule, dict), "selection_rule")
    _require(rule.get("requires_all_hard_gates") is True, "hard-gate selection")
    _require(
        rule.get("single_aggregate_may_override_hard_gate") is False,
        "aggregate override",
    )
    _require(
        rule.get("recursive_feedback_claim_requires_control_advantage") is True,
        "causal feedback control",
    )

    claim = plan.get("claim_boundary")
    _require(isinstance(claim, dict), "claim_boundary")
    _require(claim.get("formal_mncs_status") == "UNKNOWN", "MNCS claim")
    _require(claim.get("formal_mncds_status") == "UNKNOWN", "MNCDS claim")
    _require(claim.get("promotion_authorized") is False, "promotion boundary")


def load_plan(path: Path = PLAN_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StudyValidationError("plan must be an object")
    return value


def mutated_plan(plan: dict[str, Any], mutation: str) -> dict[str, Any]:
    """Return deterministic negative fixtures used by the executable tests."""

    candidate = copy.deepcopy(plan)
    if mutation == "evaluator-authority":
        candidate["immutable_authority"]["generator_may_modify_evaluator"] = True
    elif mutation == "in-place-mutation":
        candidate["architecture_arms"][1]["in_place_mutation_after_evaluation"] = True
    elif mutation == "missing-control":
        candidate["architecture_arms"] = [
            arm
            for arm in candidate["architecture_arms"]
            if arm["id"] != "shuffled-feedback-control"
        ]
    elif mutation == "duplicate-arm":
        candidate["architecture_arms"][1]["id"] = candidate["architecture_arms"][0]["id"]
    elif mutation == "aggregate-overrides-gate":
        candidate["selection_rule"]["single_aggregate_may_override_hard_gate"] = True
    elif mutation == "promotion-authorized":
        candidate["claim_boundary"]["promotion_authorized"] = True
    else:
        raise KeyError(mutation)
    return candidate


def main() -> int:
    validate(load_plan())
    print("recursive architecture study plan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
