"""Bounded world-provider surface for RAVEL development fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WorldTransition:
    source: int
    action: int
    target: int
    support: int


class WorldProvider(Protocol):
    provider_id: str

    def states(self) -> tuple[int, ...]: ...

    def actions(self) -> tuple[int, ...]: ...

    def observe(self, state: int) -> tuple[int, ...]: ...

    def transitions(self, state: int, action: int) -> tuple[WorldTransition, ...]: ...


class ToyBranchingWorld:
    """Independent toy world with a lower-ranked edge required by one route."""

    provider_id = "ravel-toy-branching/1"
    _observations = {0: (0, 0), 1: (1, 0), 2: (2, 0), 3: (3, 0)}
    _edges = {
        (0, 0): (WorldTransition(0, 0, 2, 2), WorldTransition(0, 0, 1, 1)),
        (1, 1): (WorldTransition(1, 1, 3, 2),),
        (2, 2): (WorldTransition(2, 2, 2, 2),),
    }

    def states(self) -> tuple[int, ...]:
        return tuple(sorted(self._observations))

    def actions(self) -> tuple[int, ...]:
        return (0, 1, 2)

    def observe(self, state: int) -> tuple[int, ...]:
        return self._observations[state]

    def transitions(self, state: int, action: int) -> tuple[WorldTransition, ...]:
        return self._edges.get((state, action), ())


class ToyRingWorld:
    """A separately defined provider proving mechanism/provider substitution."""

    provider_id = "ravel-toy-ring/1"
    _observations = {0: (0, 1), 1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (4, 1)}

    def states(self) -> tuple[int, ...]:
        return tuple(sorted(self._observations))

    def actions(self) -> tuple[int, ...]:
        return (0, 1)

    def observe(self, state: int) -> tuple[int, ...]:
        return self._observations[state]

    def transitions(self, state: int, action: int) -> tuple[WorldTransition, ...]:
        if state not in self._observations or action not in self.actions():
            return ()
        target = (state + (1 if action == 0 else 2)) % len(self._observations)
        return (WorldTransition(state, action, target, 1),)
