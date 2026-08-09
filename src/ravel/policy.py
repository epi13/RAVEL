"""Validated, immutable policy extraction for the RAVEL 0.6 development epoch.

The machine-readable 0.6 preregistration is authoritative for the epoch.  A
small amount of mechanism behavior is inherited from the frozen 0.5 surface:
the 0.6 record says that adaptation is added around that surface but does not
repeat its numeric objective epsilon.  That inherited value is loaded from the
frozen 0.5 preregistration and both digests are bound into the policy identity.

This module never loads a mutable runtime policy.  Callers may inspect the
typed result or generate immutable build-time constants from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "ravel_versions/0.6/ravel-0.6-preregistration.json"
FROZEN_0_5_PREREGISTRATION = ROOT / "ravel_versions/0.5/ravel-0.5-preregistration.json"
EXPECTED_PREREGISTRATION_SHA256 = (
    "26ae0b001355c978dbb2bda57fd7bcd74a3b3d4e46f45fa0b9658d88fcc885a3"
)
EXPECTED_0_5_PREREGISTRATION_SHA256 = (
    "f240c391b92823471132ffce1eeed154b3f03dc2af1e3e1f789690a99eb4cfaa"
)
Q20 = 1_048_576


class PolicyError(ValueError):
    """Raised when an epoch policy is absent, malformed, or mutated."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _q20(value: Decimal) -> int:
    return int((value * Decimal(Q20)).to_integral_value(rounding=ROUND_HALF_UP))


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise PolicyError(f"frozen policy field is missing: {key}")
    return mapping[key]


@dataclass(frozen=True, slots=True)
class FrozenRavel06Policy:
    """The subset of frozen policy consumed by development transactions."""

    preregistration_id: str
    preregistration_sha256: str
    inherited_05_preregistration_sha256: str
    adaptation_epsilon_q20: int
    base_accuracy_floor_q20: int
    retention_accuracy_floor_q20: int
    retention_loss_floor_q20: int
    prediction_degradation_bound_q20: int
    maximum_transition_support_losses: int
    maximum_experts: int
    maximum_births: int
    maximum_retirements: int
    replay_records: int
    maximum_update_passes: int
    maximum_compute_evaluations: int | None
    maximum_compute_ratio_q20: int
    maximum_candidate_identities: int
    representation_floor_mode: str

    @property
    def threshold_identity(self) -> str:
        contract = {
            "preregistration_id": self.preregistration_id,
            "preregistration_sha256": self.preregistration_sha256,
            "inherited_05_preregistration_sha256": self.inherited_05_preregistration_sha256,
            "adaptation_epsilon_q20": self.adaptation_epsilon_q20,
            "base_accuracy_floor_q20": self.base_accuracy_floor_q20,
            "retention_accuracy_floor_q20": self.retention_accuracy_floor_q20,
            "retention_loss_floor_q20": self.retention_loss_floor_q20,
            "prediction_degradation_bound_q20": self.prediction_degradation_bound_q20,
            "maximum_transition_support_losses": self.maximum_transition_support_losses,
            "maximum_experts": self.maximum_experts,
            "maximum_births": self.maximum_births,
            "maximum_retirements": self.maximum_retirements,
            "replay_records": self.replay_records,
            "maximum_update_passes": self.maximum_update_passes,
            "maximum_compute_evaluations": self.maximum_compute_evaluations,
            "maximum_compute_ratio_q20": self.maximum_compute_ratio_q20,
            "maximum_candidate_identities": self.maximum_candidate_identities,
            "representation_floor_mode": self.representation_floor_mode,
        }
        digest = _sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode())
        return f"ravel-0.6-frozen-policy/{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "preregistration_id": self.preregistration_id,
            "preregistration_sha256": self.preregistration_sha256,
            "inherited_05_preregistration_sha256": self.inherited_05_preregistration_sha256,
            "adaptation_epsilon_q20": self.adaptation_epsilon_q20,
            "base_accuracy_floor_q20": self.base_accuracy_floor_q20,
            "retention_accuracy_floor_q20": self.retention_accuracy_floor_q20,
            "retention_loss_floor_q20": self.retention_loss_floor_q20,
            "prediction_degradation_bound_q20": self.prediction_degradation_bound_q20,
            "maximum_transition_support_losses": self.maximum_transition_support_losses,
            "maximum_experts": self.maximum_experts,
            "maximum_births": self.maximum_births,
            "maximum_retirements": self.maximum_retirements,
            "replay_records": self.replay_records,
            "maximum_update_passes": self.maximum_update_passes,
            "maximum_compute_evaluations": self.maximum_compute_evaluations,
            "maximum_compute_ratio_q20": self.maximum_compute_ratio_q20,
            "maximum_candidate_identities": self.maximum_candidate_identities,
            "representation_floor_mode": self.representation_floor_mode,
            "threshold_identity": self.threshold_identity,
        }


def load_frozen_policy(
    preregistration_path: Path = PREREGISTRATION,
    inherited_05_path: Path = FROZEN_0_5_PREREGISTRATION,
) -> FrozenRavel06Policy:
    """Load and validate the frozen policy, rejecting any identity mutation."""

    preregistration_bytes = preregistration_path.read_bytes()
    preregistration_sha = _sha256(preregistration_bytes)
    if preregistration_sha != EXPECTED_PREREGISTRATION_SHA256:
        raise PolicyError(
            "RAVEL 0.6 preregistration identity mismatch: "
            f"expected {EXPECTED_PREREGISTRATION_SHA256}, got {preregistration_sha}"
        )
    inherited_bytes = inherited_05_path.read_bytes()
    inherited_sha = _sha256(inherited_bytes)
    if inherited_sha != EXPECTED_0_5_PREREGISTRATION_SHA256:
        raise PolicyError(
            "inherited RAVEL 0.5 policy identity mismatch: "
            f"expected {EXPECTED_0_5_PREREGISTRATION_SHA256}, got {inherited_sha}"
        )
    try:
        prereg = json.loads(preregistration_bytes)
        inherited = json.loads(inherited_bytes)
    except json.JSONDecodeError as error:
        raise PolicyError(f"frozen policy JSON is malformed: {error}") from error
    if prereg.get("status") != "PREREGISTERED_BEFORE_IMPLEMENTATION":
        raise PolicyError("RAVEL 0.6 preregistration status is not frozen")
    if prereg.get("normative_for_epoch") is not True:
        raise PolicyError("RAVEL 0.6 preregistration is not normative for its epoch")

    budget = _required(_required(prereg, "mechanism"), "budget")
    common = _required(_required(prereg, "hard_gates"), "common")
    gates = {gate["gate_id"]: gate for gate in common}
    for gate_id in (
        "base_holdout_accuracy",
        "base_holdout_retention",
        "retention_loss_floor",
        "old_prediction_retention",
        "transition_unique_support",
        "matched_compute_budget",
    ):
        if gate_id not in gates:
            raise PolicyError(f"frozen common gate is missing: {gate_id}")

    inherited_constants = _required(inherited, "mechanism_constants")
    inherited_epsilon = inherited_constants.get("topology_objective_min_q20")
    if not isinstance(inherited_epsilon, int) or inherited_epsilon < 0:
        raise PolicyError("frozen 0.5 inherited objective epsilon is malformed")
    def numeric_gate(gate_id: str, operator: str) -> Decimal:
        gate = gates[gate_id]
        if gate.get("operator") != operator or not isinstance(gate.get("value"), (int, float)):
            raise PolicyError(f"frozen gate {gate_id} has unexpected operator/value")
        return Decimal(str(gate["value"]))

    return FrozenRavel06Policy(
        preregistration_id=str(_required(prereg, "preregistration_id")),
        preregistration_sha256=preregistration_sha,
        inherited_05_preregistration_sha256=inherited_sha,
        adaptation_epsilon_q20=inherited_epsilon,
        base_accuracy_floor_q20=_q20(numeric_gate("base_holdout_accuracy", "ge")),
        retention_accuracy_floor_q20=_q20(numeric_gate("base_holdout_retention", "ge")),
        retention_loss_floor_q20=_q20(numeric_gate("retention_loss_floor", "ge")),
        prediction_degradation_bound_q20=_q20(numeric_gate("old_prediction_retention", "le")),
        maximum_transition_support_losses=int(numeric_gate("transition_unique_support", "eq")),
        maximum_experts=int(budget["maximum_experts"]),
        maximum_births=int(budget["maximum_births_per_trial"]),
        maximum_retirements=int(budget["maximum_retirements_per_trial"]),
        replay_records=int(budget["replay_records"]),
        maximum_update_passes=int(budget["maximum_objective_tested_update_passes"]),
        maximum_compute_evaluations=None,
        maximum_compute_ratio_q20=_q20(
            numeric_gate("matched_compute_budget", "le")
        ),
        maximum_candidate_identities=int(budget["maximum_candidate_identities"]),
        representation_floor_mode="non_decreasing_from_previous_checkpoint",
    )


def policy_c_header(policy: FrozenRavel06Policy | None = None) -> str:
    """Return deterministic C constants generated from the frozen policy."""

    policy = load_frozen_policy() if policy is None else policy
    maximum_compute = (
        "UINT64_MAX"
        if policy.maximum_compute_evaluations is None
        else f"UINT64_C({policy.maximum_compute_evaluations})"
    )
    return "\n".join(
        (
            "/* generated from frozen RAVEL 0.6 policy; do not edit */",
            f'#define RAVEL06_THRESHOLD_IDENTITY "{policy.threshold_identity}"',
            f"#define RAVEL06_OBJECTIVE_EPSILON_Q20 UINT64_C({policy.adaptation_epsilon_q20})",
            f"#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_C({policy.base_accuracy_floor_q20})",
            f"#define RAVEL06_RETENTION_ACCURACY_FLOOR_Q20 UINT64_C({policy.retention_accuracy_floor_q20})",
            f"#define RAVEL06_RETENTION_LOSS_FLOOR_Q20 INT64_C({policy.retention_loss_floor_q20})",
            f"#define RAVEL06_PREDICTION_DEGRADATION_BOUND_Q20 UINT64_C({policy.prediction_degradation_bound_q20})",
            f"#define RAVEL06_MAX_TRANSITION_SUPPORT_LOSSES {policy.maximum_transition_support_losses}u",
            f"#define RAVEL06_MAX_EXPERTS {policy.maximum_experts}u",
            f"#define RAVEL06_MAX_BIRTHS {policy.maximum_births}u",
            f"#define RAVEL06_MAX_RETIREMENTS {policy.maximum_retirements}u",
            f"#define RAVEL06_REPLAY_RECORDS {policy.replay_records}u",
            f"#define RAVEL06_MAX_UPDATE_PASSES {policy.maximum_update_passes}u",
            f"#define RAVEL06_MAX_COMPUTE_EVALUATIONS {maximum_compute}",
            f"#define RAVEL06_MAX_COMPUTE_RATIO_Q20 UINT64_C({policy.maximum_compute_ratio_q20})",
        )
    )
