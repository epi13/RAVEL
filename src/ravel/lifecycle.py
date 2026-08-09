"""Append-only RAVEL 0.6 candidate-development lifecycle.

This ledger is development infrastructure only. It freezes identities and
records selection outcomes; it never performs selection and never authorizes
R6-06 custody or promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class LedgerError(ValueError):
    """Raised when an append-only lifecycle invariant would be violated."""


class CandidateState:
    CREATED = "created"
    DEVELOPMENT = "development"
    FROZEN = "candidate_frozen"
    SELECTION = "selection_evaluation"
    SELECTED = "selected"
    REJECTED = "rejected"


_TRANSITIONS = {
    CandidateState.CREATED: {CandidateState.DEVELOPMENT},
    CandidateState.DEVELOPMENT: {CandidateState.FROZEN},
    CandidateState.FROZEN: {CandidateState.SELECTION},
    CandidateState.SELECTION: {CandidateState.SELECTED, CandidateState.REJECTED},
    CandidateState.SELECTED: set(),
    CandidateState.REJECTED: set(),
}


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def candidate_id(number: int) -> str:
    if number < 1:
        raise LedgerError("candidate number must be positive")
    return f"ravel-0.6-candidate-{number:03d}"


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    candidate_id: str
    number: int
    state: str
    source_identity: str | None = None
    evaluator_identity: str | None = None
    threshold_identity: str | None = None
    development_partition: str | None = None
    selection_partition: str | None = None
    selection_result_ref: str | None = None
    rejection_reasons: tuple[str, ...] = ()
    contamination_flag: bool = False


class CandidateLedger:
    """A deterministic JSONL event stream with validated state transitions."""

    def __init__(self, path: str | Path, *, maximum_candidates: int = 8) -> None:
        if maximum_candidates < 1:
            raise LedgerError("maximum_candidates must be positive")
        self.path = Path(path)
        self.maximum_candidates = maximum_candidates

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        events: list[dict[str, Any]] = []
        previous = "0" * 64
        for expected, line in enumerate(lines, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise LedgerError("ledger contains malformed JSON") from error
            if event.get("sequence") != expected:
                raise LedgerError("ledger sequence has a gap or mutation")
            if event.get("previous_digest") != previous:
                raise LedgerError("ledger hash chain is broken")
            unsigned = dict(event)
            digest = unsigned.pop("record_digest", None)
            expected_digest = hashlib.sha256(_canonical(unsigned).encode()).hexdigest()
            if digest != expected_digest:
                raise LedgerError("ledger record digest mismatch")
            previous = digest
            events.append(event)
        return events

    def _current(self) -> dict[str, CandidateRecord]:
        current: dict[str, CandidateRecord] = {}
        for event in self._events():
            payload = event["payload"]
            record = current.get(event["candidate_id"])
            current[event["candidate_id"]] = CandidateRecord(
                candidate_id=event["candidate_id"],
                number=payload.get("number", record.number if record else 0),
                state=event["state"],
                source_identity=payload.get("source_identity", record.source_identity if record else None),
                evaluator_identity=payload.get("evaluator_identity", record.evaluator_identity if record else None),
                threshold_identity=payload.get("threshold_identity", record.threshold_identity if record else None),
                development_partition=payload.get("development_partition", record.development_partition if record else None),
                selection_partition=payload.get("selection_partition", record.selection_partition if record else None),
                selection_result_ref=payload.get("selection_result_ref", record.selection_result_ref if record else None),
                rejection_reasons=tuple(payload.get("rejection_reasons", record.rejection_reasons if record else ())),
                contamination_flag=bool(payload.get("contamination_flag", record.contamination_flag if record else False)),
            )
        ordered = sorted(current.values(), key=lambda item: item.number)
        for expected, record in enumerate(ordered, start=1):
            if record.number != expected or record.candidate_id != candidate_id(expected):
                raise LedgerError("candidate numbering has a gap or identity mutation")
        return current

    def records(self) -> tuple[CandidateRecord, ...]:
        return tuple(sorted(self._current().values(), key=lambda record: record.number))

    def get(self, identifier: str) -> CandidateRecord:
        record = self._current().get(identifier)
        if record is None:
            raise LedgerError(f"unknown candidate: {identifier}")
        return record

    def _append(self, identifier: str, state: str, payload: Mapping[str, Any]) -> None:
        events = self._events()
        current = self._current()
        previous_record = current.get(identifier)
        if previous_record is not None and state != previous_record.state and state not in _TRANSITIONS[previous_record.state]:
            raise LedgerError(f"invalid candidate transition: {previous_record.state}->{state}")
        if previous_record is None and state != CandidateState.CREATED:
            raise LedgerError("candidate must be created before a state transition")
        event = {
            "schema": "ravel-0.6-candidate-ledger/0.1",
            "sequence": len(events) + 1,
            "candidate_id": identifier,
            "state": state,
            "payload": dict(payload),
            "previous_digest": events[-1]["record_digest"] if events else "0" * 64,
        }
        event["record_digest"] = hashlib.sha256(_canonical(event).encode()).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical(event) + "\n")

    def create(self, *, development_partition: str, created_at: str) -> CandidateRecord:
        records = self.records()
        number = len(records) + 1
        if number > self.maximum_candidates:
            raise LedgerError("candidate limit exceeded")
        identifier = candidate_id(number)
        if records and records[-1].number != number - 1:
            raise LedgerError("candidate numbering is not gap-resistant")
        self._append(
            identifier,
            CandidateState.CREATED,
            {"number": number, "development_partition": development_partition, "created_at": created_at},
        )
        return self.get(identifier)

    def begin_development(self, identifier: str) -> CandidateRecord:
        if self.get(identifier).state != CandidateState.CREATED:
            raise LedgerError("candidate cannot re-enter development")
        self._append(identifier, CandidateState.DEVELOPMENT, {})
        return self.get(identifier)

    def freeze(
        self,
        identifier: str,
        *,
        source_identity: str,
        evaluator_identity: str,
        threshold_identity: str,
        selection_partition: str,
    ) -> CandidateRecord:
        values = {
            "source_identity": source_identity,
            "evaluator_identity": evaluator_identity,
            "threshold_identity": threshold_identity,
            "selection_partition": selection_partition,
        }
        if any(not value for value in values.values()):
            raise LedgerError("freeze requires all immutable identities")
        record = self.get(identifier)
        if record.development_partition == selection_partition:
            raise LedgerError("development and selection partitions must differ")
        self._append(identifier, CandidateState.FROZEN, values)
        return self.get(identifier)

    def start_selection(self, identifier: str) -> CandidateRecord:
        return self._transition(identifier, CandidateState.SELECTION)

    def record_selection(
        self,
        identifier: str,
        *,
        selected: bool,
        result_ref: str,
        rejection_reasons: tuple[str, ...] = (),
        contamination_flag: bool = False,
    ) -> CandidateRecord:
        if not result_ref:
            raise LedgerError("selection result reference is required")
        state = CandidateState.SELECTED if selected else CandidateState.REJECTED
        self._append(
            identifier,
            state,
            {
                "selection_result_ref": result_ref,
                "rejection_reasons": list(rejection_reasons),
                "contamination_flag": contamination_flag,
            },
        )
        return self.get(identifier)

    def append_development_feedback(self, identifier: str, *, result_ref: str) -> None:
        if self.get(identifier).state != CandidateState.DEVELOPMENT:
            raise LedgerError("selection or frozen evidence cannot feed the same candidate")
        if not result_ref:
            raise LedgerError("development result reference is required")
        self._append(identifier, CandidateState.DEVELOPMENT, {"feedback_ref": result_ref})

    def _transition(self, identifier: str, state: str) -> CandidateRecord:
        self._append(identifier, state, {})
        return self.get(identifier)
