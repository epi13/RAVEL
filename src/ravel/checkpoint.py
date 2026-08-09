"""Canonical checkpoint codec for decomposed development state."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any

from .mechanism_state import ExpertState, MechanismState


class CheckpointError(ValueError):
    """Raised for malformed or identity-inconsistent checkpoints."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class CheckpointCodec:
    schema = "ravel-0.6-mechanism-checkpoint/0.1"

    def encode(self, state: MechanismState) -> bytes:
        payload = {"schema": self.schema, "state": asdict(state)}
        return _canonical(payload)

    def identity(self, checkpoint: bytes) -> str:
        return "sha256:" + hashlib.sha256(checkpoint).hexdigest()

    def decode(self, checkpoint: bytes) -> MechanismState:
        try:
            payload = json.loads(checkpoint)
            if payload["schema"] != self.schema:
                raise CheckpointError("checkpoint schema mismatch")
            raw = payload["state"]
            experts = tuple(
                ExpertState(
                    lineage=expert["lineage"],
                    labels=tuple(expert["labels"]),
                    supported_actions=tuple(expert["supported_actions"]),
                )
                for expert in raw["experts"]
            )
            state = MechanismState(
                experts=experts,
                epoch=raw["epoch"],
                births=raw["births"],
                retirements=raw["retirements"],
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise CheckpointError("checkpoint is malformed") from error
        if self.encode(state) != checkpoint:
            raise CheckpointError("checkpoint is not canonical")
        return state
