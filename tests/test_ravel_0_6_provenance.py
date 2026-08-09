from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.ravel_0_6_build import BuildError, build, derive
from tools.ravel_0_6_seed_candidate import FROZEN_SOURCE, SeedError, build_candidate_source


class CandidateProvenanceTests(unittest.TestCase):
    def test_repeated_derivation_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.c"
            second = root / "second.c"
            self.assertEqual(derive(first), derive(second))
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_frozen_source_mutation_is_rejected(self) -> None:
        mutated = FROZEN_SOURCE.read_bytes() + b"\n/* mutation */\n"
        with self.assertRaises(SeedError):
            build_candidate_source(mutated)

    def test_stale_generated_outputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "candidate.c"
            output.write_text("stale", encoding="utf-8")
            with self.assertRaises(BuildError):
                derive(output)
            build_dir = root / "build"
            build_dir.mkdir()
            (build_dir / "ravel_0_6_candidate_001.c").write_text("stale", encoding="utf-8")
            with self.assertRaises(BuildError):
                build(build_dir)

    def test_build_record_binds_generator_compiler_and_raw_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            record = build(Path(directory))
            self.assertEqual(record["candidate_id"], "ravel-0.6-candidate-001")
            self.assertTrue(record["generator"]["sha256"])
            self.assertTrue(record["compiler"]["argv"])
            self.assertEqual(record["build"]["exit_status"], 0)
            self.assertFalse(record["authoritative_evidence"])


if __name__ == "__main__":
    unittest.main()
