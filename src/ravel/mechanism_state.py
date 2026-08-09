"""State surface that deliberately excludes evaluators and authority."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpertState:
    lineage: str
    labels: tuple[int, ...]
    supported_actions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MechanismState:
    experts: tuple[ExpertState, ...]
    epoch: int = 0
    births: int = 0
    retirements: int = 0

    def __post_init__(self) -> None:
        if self.epoch < 0 or self.births < 0 or self.retirements < 0:
            raise ValueError("mechanism counters must be non-negative")
        if len({expert.lineage for expert in self.experts}) != len(self.experts):
            raise ValueError("expert lineage must be unique")

    def proposed(self, *, experts: tuple[ExpertState, ...], births: int = 0, retirements: int = 0) -> "MechanismState":
        return MechanismState(
            experts=experts,
            epoch=self.epoch + 1,
            births=self.births + births,
            retirements=self.retirements + retirements,
        )
