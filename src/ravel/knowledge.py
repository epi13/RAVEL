"""Fail-closed knowledge promotion. Rust is the canonical implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


STAGES = {
    "observation": ("episode",),
    "episode": ("open_hypothesis", "retired"),
    "open_hypothesis": ("intervention", "counterexample", "retired"),
    "intervention": ("attribution", "counterexample", "retired"),
    "attribution": ("provisional_principle", "counterexample", "retired"),
    "provisional_principle": ("transfer_tested_principle", "counterexample", "retired"),
    "transfer_tested_principle": ("restricted_strategy", "counterexample", "retired"),
    "restricted_strategy": ("supported_strategy", "counterexample", "retired"),
    "supported_strategy": ("counterexample", "retired"),
    "counterexample": (),
    "retired": (),
}


class KnowledgeError(ValueError):
    """Raised when a knowledge transition would skip evidence or rewrite status."""


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    record_id: str
    stage: str
    statement: str
    scope: Mapping[str, str]
    parent_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evaluation_status: str | None = None
    transfer_status: str = "untested"
    attribution: str | None = None
    producer_id: str = "ravel-knowledge"
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["scope"] = dict(self.scope)
        payload["parent_ids"] = list(self.parent_ids)
        payload["evidence_ids"] = list(self.evidence_ids)
        return payload


def promote(
    current: KnowledgeRecord,
    *,
    next_stage: str,
    next_id: str,
    statement: str,
    evidence_ids: tuple[str, ...] = (),
    evaluation_status: str | None = None,
    transfer_status: str = "untested",
    attribution: str | None = None,
    created_at: str,
) -> KnowledgeRecord:
    """Create the next knowledge record or fail closed."""

    if next_stage not in STAGES.get(current.stage, ()):
        raise KnowledgeError(
            f"invalid knowledge transition: {current.stage}->{next_stage}"
        )
    if current.stage == "episode" and next_stage == "supported_strategy":
        raise KnowledgeError("an episode cannot directly become a global strategy")
    if next_stage == "provisional_principle" and attribution != "supported":
        raise KnowledgeError(
            "a successful intervention cannot become a principle without supported attribution"
        )
    if next_stage == "transfer_tested_principle" and not evidence_ids:
        raise KnowledgeError("an untested principle cannot authorize transfer")
    if next_stage == "supported_strategy" and transfer_status != "supported":
        raise KnowledgeError("an untested principle cannot authorize broad reuse")
    if current.evaluation_status == "UNKNOWN" and evaluation_status == "PASS":
        raise KnowledgeError("knowledge promotion cannot convert UNKNOWN into PASS")
    if next_stage == "counterexample" and not evidence_ids:
        raise KnowledgeError("a failed transfer test must remain linked to the principle")
    return KnowledgeRecord(
        record_id=next_id,
        stage=next_stage,
        statement=statement,
        scope=dict(current.scope),
        parent_ids=(current.record_id,),
        evidence_ids=evidence_ids,
        evaluation_status=evaluation_status,
        transfer_status=transfer_status,
        attribution=attribution,
        producer_id=current.producer_id,
        created_at=created_at,
    )
