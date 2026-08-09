from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.ravel_0_6_build import BuildError, build, derive
from tools.ravel_0_6_seed_candidate import FROZEN_SOURCE, SeedError, build_candidate_source
from tools.ravel_0_6_build import C_CHECKPOINT_HEADER, C_CHECKPOINT_IMPLEMENTATION, sha256_bytes


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
            self.assertTrue(record["generator"]["transaction_surface"]["sha256"])
            self.assertTrue(record["generator"]["policy_source"]["sha256"])
            self.assertEqual(record["policy"]["preregistration_sha256"], "26ae0b001355c978dbb2bda57fd7bcd74a3b3d4e46f45fa0b9658d88fcc885a3")
            self.assertEqual(record["environment_provider"]["provider_id"], "ravel-toy-branching-c/1")
            checkpoint = record["component_contracts"]["checkpoint"]
            self.assertEqual(checkpoint["header_sha256"], sha256_bytes(C_CHECKPOINT_HEADER.read_bytes()))
            self.assertEqual(checkpoint["implementation_sha256"], sha256_bytes(C_CHECKPOINT_IMPLEMENTATION.read_bytes()))
            self.assertEqual(len(record["generated_components"]), 10)
            self.assertTrue(record["mechanism_components"])
            self.assertTrue(record["compiler"]["argv"])
            self.assertEqual(record["execution"]["status"], "NOT_RUN")
            self.assertEqual(record["build"]["exit_status"], 0)
            self.assertFalse(record["authoritative_evidence"])


if __name__ == "__main__":
    unittest.main()
