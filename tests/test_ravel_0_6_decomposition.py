from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.ravel_0_6_build import build
from tools.ravel_0_6_decompose import split_candidate_source
from tools.ravel_0_6_seed_candidate import FROZEN_SOURCE, build_candidate_source


ROOT = Path(__file__).resolve().parents[1]


def compile_and_run(
    source: Path, binary: Path, extra_flags: tuple[str, ...] = ()
) -> dict[str, object]:
    built = subprocess.run(
        [
            "cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-I", str(ROOT / "ravel_versions/0.6/ravel_0_6"), *extra_flags,
            str(source), str(ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_provider_branching.c"),
            "-lm", "-o", str(binary),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        raise AssertionError(built.stderr)
    result = subprocess.run(
        [str(binary), "--trial", "decomposition", "--regime", "separated_state", "--seed", "0x1234"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def run_binary(binary: Path) -> dict[str, object]:
    result = subprocess.run(
        [str(binary), "--trial", "decomposition", "--regime", "separated_state", "--seed", "0x1234"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class DecompositionTests(unittest.TestCase):
    def test_split_is_lossless_and_unity_wrapper_preserves_behavior(self) -> None:
        source = build_candidate_source(FROZEN_SOURCE.read_bytes())
        pieces = split_candidate_source(source)
        self.assertGreaterEqual(len(pieces), 8)
        self.assertEqual("".join(piece for _, piece in pieces), source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            monolithic = root / "monolithic.c"
            direct_binary = root / "direct"
            monolithic.write_text(source, encoding="utf-8")
            direct = compile_and_run(monolithic, direct_binary)
            record = build(root / "split")
            split_binary = root / "split" / "ravel_0_6_candidate_001"
            split = compile_and_run(
                root / "split" / "ravel_0_6_candidate_001.c", split_binary
            )
            separate = run_binary(split_binary)
            unity = run_binary(root / "split" / "ravel_0_6_candidate_001.unity")
        self.assertEqual(direct, split)
        self.assertEqual(unity, separate)
        self.assertEqual(
            record["generated_source"]["monolithic_sha256"],
            hashlib.sha256(source.encode()).hexdigest(),
        )
        self.assertEqual(len(record["generated_components"]), len(pieces))
        self.assertEqual(record["component_contracts"]["checkpoint"]["abi_version"], "ravel-0.6-checkpoint-abi/1")
        self.assertTrue(record["build"]["candidate_object_sha256"])
        self.assertTrue(record["build"]["checkpoint_object_sha256"])

    def test_real_c_provider_substitution_is_explicit_and_observable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            branching_dir = root / "branching"
            ring_dir = root / "ring"
            old_provider = os.environ.get("RAVEL06_PROVIDER")
            try:
                os.environ["RAVEL06_PROVIDER"] = "branching"
                branching_record = build(branching_dir)
                os.environ["RAVEL06_PROVIDER"] = "ring"
                ring_record = build(ring_dir)
            finally:
                if old_provider is None:
                    os.environ.pop("RAVEL06_PROVIDER", None)
                else:
                    os.environ["RAVEL06_PROVIDER"] = old_provider
            self.assertNotEqual(
                branching_record["environment_provider"]["provider_id"],
                ring_record["environment_provider"]["provider_id"],
            )
            branching = run_binary(branching_dir / "ravel_0_6_candidate_001")
            ring = run_binary(ring_dir / "ravel_0_6_candidate_001")
        self.assertNotEqual(branching["environment_provider_id"], ring["environment_provider_id"])
        self.assertNotEqual(branching["candidate"]["model_identity"], ring["candidate"]["model_identity"])

    def test_world_abi_provider_objects_share_contract_and_wrong_header_fails_closed(self) -> None:
        source = build_candidate_source(FROZEN_SOURCE.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.c"
            candidate.write_text(source, encoding="utf-8")
            for provider in ("branching", "ring"):
                binary = root / provider
                built = subprocess.run(
                    [
                        "cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror", "-pedantic",
                        "-I", str(ROOT / "ravel_versions/0.6/ravel_0_6"), str(candidate),
                        str(ROOT / "ravel_versions/0.6/ravel_0_6" / f"ravel_0_6_provider_{provider}.c"),
                        "-lm", "-o", str(binary),
                    ], cwd=ROOT, text=True, capture_output=True, check=False,
                )
                self.assertEqual(built.returncode, 0, built.stderr)
                trial = run_binary(binary)
                self.assertEqual(trial["environment_provider_id"], f"ravel-toy-{provider}-c/1")

            wrong_include = root / "wrong-header"
            wrong_include.mkdir()
            header = (ROOT / "ravel_versions/0.6/ravel_0_6/ravel_0_6_world.h").read_text()
            wrong_include.joinpath("ravel_0_6_world.h").write_text(
                header.replace("RAVEL06_WORLD_ABI_NUMERIC 1u", "RAVEL06_WORLD_ABI_NUMERIC 2u"),
                encoding="utf-8",
            )
            rejected = subprocess.run(
                [
                    "cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-I", str(wrong_include), "-I", str(ROOT / "ravel_versions/0.6/ravel_0_6"),
                    "-c", str(candidate), "-o", str(root / "wrong.o"),
                ], cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)


if __name__ == "__main__":
    unittest.main()
