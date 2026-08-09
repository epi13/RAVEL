"""Deterministic transition compilation independent of a world implementation."""

from __future__ import annotations

from dataclasses import dataclass

from .world import WorldProvider, WorldTransition


@dataclass(frozen=True, slots=True)
class CompiledTransitions:
    provider_id: str
    edges: tuple[WorldTransition, ...]

    def outgoing(self, source: int, action: int) -> tuple[WorldTransition, ...]:
        return tuple(
            edge for edge in self.edges if edge.source == source and edge.action == action
        )


class TransitionCompiler:
    """Compile and canonically order provider observations; no evaluator state."""

    def compile(self, provider: WorldProvider) -> CompiledTransitions:
        states = set(provider.states())
        actions = set(provider.actions())
        edges: list[WorldTransition] = []
        for state in sorted(states):
            for action in sorted(actions):
                for edge in provider.transitions(state, action):
                    if edge.source != state or edge.action != action or edge.target not in states:
                        raise ValueError("provider returned an out-of-domain transition")
                    if edge.support < 1:
                        raise ValueError("transition support must be positive")
                    edges.append(edge)
        return CompiledTransitions(
            provider_id=provider.provider_id,
            edges=tuple(sorted(edges, key=lambda item: (-item.support, item.source, item.action, item.target))),
        )
