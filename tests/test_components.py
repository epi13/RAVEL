from __future__ import annotations

import unittest

from ravel.checkpoint import CheckpointCodec, CheckpointError
from ravel.mechanism_state import ExpertState, MechanismState
from ravel.planning import plan
from ravel.transition import TransitionCompiler
from ravel.world import ToyBranchingWorld, ToyRingWorld


class ComponentTests(unittest.TestCase):
    def test_branching_provider_requires_lower_ranked_transition(self) -> None:
        graph = TransitionCompiler().compile(ToyBranchingWorld())
        result = plan(graph, start=0, goal=3)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.actions, (0, 1))
        self.assertEqual(result.reason, "route_found")

    def test_provider_substitution_changes_identity_not_compiler(self) -> None:
        compiler = TransitionCompiler()
        first = compiler.compile(ToyBranchingWorld())
        second = compiler.compile(ToyRingWorld())
        self.assertNotEqual(first.provider_id, second.provider_id)
        self.assertNotEqual(first.edges, second.edges)
        self.assertEqual(plan(second, start=0, goal=3).status, "PASS")

    def test_unsupported_route_is_unknown(self) -> None:
        graph = TransitionCompiler().compile(ToyBranchingWorld())
        result = plan(graph, start=2, goal=3, maximum_steps=1)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.reason, "route_unavailable")

    def test_checkpoint_round_trip_is_canonical_and_detects_corruption(self) -> None:
        state = MechanismState(
            experts=(ExpertState("lineage-a", (1,), (0,)),),
            epoch=2,
            births=1,
        )
        codec = CheckpointCodec()
        checkpoint = codec.encode(state)
        self.assertEqual(codec.decode(checkpoint), state)
        self.assertEqual(codec.encode(codec.decode(checkpoint)), checkpoint)
        with self.assertRaises(CheckpointError):
            codec.decode(checkpoint + b" ")


if __name__ == "__main__":
    unittest.main()
