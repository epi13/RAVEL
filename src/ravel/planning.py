"""Bounded deterministic planner over compiled transition interfaces."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from .transition import CompiledTransitions


PlanStatus = Literal["PASS", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class PlanResult:
    status: PlanStatus
    actions: tuple[int, ...]
    visited: tuple[int, ...]
    reason: str


def plan(
    graph: CompiledTransitions,
    *,
    start: int,
    goal: int,
    maximum_steps: int = 32,
) -> PlanResult:
    if maximum_steps < 0:
        raise ValueError("maximum_steps must be non-negative")
    queue: deque[tuple[int, tuple[int, ...]]] = deque([(start, ())])
    seen = {start}
    visited: list[int] = []
    while queue:
        state, actions = queue.popleft()
        visited.append(state)
        if state == goal:
            return PlanResult("PASS", actions, tuple(visited), "route_found")
        if len(actions) >= maximum_steps:
            continue
        for action in sorted({edge.action for edge in graph.edges if edge.source == state}):
            for edge in graph.outgoing(state, action):
                if edge.target in seen:
                    continue
                seen.add(edge.target)
                queue.append((edge.target, actions + (action,)))
    return PlanResult("UNKNOWN", (), tuple(visited), "route_unavailable")
