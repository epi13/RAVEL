"""Fail-closed knowledge promotion. Rust is the canonical implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


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
class AttributionRecord:
    attribution_id: str
    source_intervention_ids: tuple[str, ...]
    evaluator_identity: str
    evidence_ids: tuple[str, ...]
    disposition: str
    scope: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class TransferTestRecord:
    test_id: str
    principle_id: str
    context_identity: str
    evidence_ids: tuple[str, ...]
    outcome: str


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
    attribution_id: str | None = None
    transfer_test_ids: tuple[str, ...] = ()
    challenged_ids: tuple[str, ...] = ()
    producer_id: str = "ravel-knowledge"
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["scope"] = dict(self.scope)
        payload["parent_ids"] = list(self.parent_ids)
        payload["evidence_ids"] = list(self.evidence_ids)
        payload["transfer_test_ids"] = list(self.transfer_test_ids)
        payload["challenged_ids"] = list(self.challenged_ids)
        return payload


def promote(
    current: KnowledgeRecord,
    *,
    next_stage: str,
    next_id: str,
    statement: str,
    evidence_ids: tuple[str, ...] = (),
    evaluation_status: str | None = None,
    attribution: AttributionRecord | None = None,
    transfer_tests: Sequence[TransferTestRecord] = (),
    created_at: str,
) -> KnowledgeRecord:
    """Create the next knowledge record or fail closed."""

    if next_stage not in STAGES.get(current.stage, ()):
        raise KnowledgeError(
            f"invalid knowledge transition: {current.stage}->{next_stage}"
        )
    if current.evaluation_status in {"UNKNOWN", "FAIL"} and evaluation_status == "PASS":
        raise KnowledgeError("knowledge promotion cannot convert FAIL or UNKNOWN into PASS")
    if next_id == current.record_id:
        raise KnowledgeError("promotion must not overwrite its parent")
    if next_stage == "provisional_principle":
        if attribution is None or attribution.disposition != "supported":
            raise KnowledgeError("a principle requires a valid attribution record")
        if dict(attribution.scope) != dict(current.scope):
            raise KnowledgeError("attribution scope must match the parent knowledge scope")
    if next_stage == "transfer_tested_principle" and not transfer_tests:
        raise KnowledgeError("a transfer-tested principle must identify actual transfer tests")
    if next_stage == "supported_strategy":
        contexts = {
            item.context_identity for item in transfer_tests if item.outcome == "supported"
        }
        if len(contexts) < 2:
            raise KnowledgeError(
                "a supported strategy must not be created from one local context"
            )
    if next_stage == "counterexample" and not evidence_ids:
        raise KnowledgeError(
            "a counterexample must remain linked to the knowledge it challenges"
        )
    return KnowledgeRecord(
        record_id=next_id,
        stage=next_stage,
        statement=statement,
        scope=dict(current.scope),
        parent_ids=(current.record_id,),
        evidence_ids=evidence_ids,
        evaluation_status=evaluation_status,
        transfer_status="supported" if next_stage == "supported_strategy" else "untested",
        attribution_id=None if attribution is None else attribution.attribution_id,
        transfer_test_ids=tuple(item.test_id for item in transfer_tests),
        challenged_ids=(current.record_id,) if next_stage == "counterexample" else (),
        producer_id=current.producer_id,
        created_at=created_at,
    )
