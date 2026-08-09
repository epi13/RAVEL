#!/usr/bin/env python3
"""Run RAVEL 0.6 behavioral fixtures and bounded mutation checks."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

from ravel_0_6_seed_candidate import (
    FROZEN_SOURCE,
    NEW_PLANNER_CONTEXT,
    NEW_SEED_FUNCTION,
    OLD_PLANNER_CONTEXT,
    OLD_SEED_FUNCTION,
    build_candidate_source,
)

ROOT = Path(__file__).resolve().parents[1]
HARNESS = Path(__file__).with_name("ravel_0_6_behavioral_fixtures.c")


def compile_and_run(source: Path, directory: Path) -> tuple[int, dict[str, object] | None]:
    binary = directory / (source.stem + ".bin")
    command = [
        "cc",
        "-std=c11",
        "-O0",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        f'-DRAVEL_06_CANDIDATE_SOURCE="{source}"',
        str(HARNESS),
        "-lm",
        "-o",
        str(binary),
    ]
    built = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if built.returncode != 0:
        raise AssertionError(f"fixture compile failed for {source}: {built.stderr}")
    run = subprocess.run([str(binary)], cwd=ROOT, text=True, capture_output=True, check=False)
    payload = json.loads(run.stdout) if run.stdout.strip() else None
    return run.returncode, payload


def expect_pass(source: Path, directory: Path) -> dict[str, object]:
    status, payload = compile_and_run(source, directory)
    if status != 0 or payload is None:
        raise AssertionError(f"behavioral fixture unexpectedly failed for {source}: {payload}")
    if payload.get("slot_one_route") != 1 or payload.get("birth_support_reset") != 1:
        raise AssertionError(f"behavioral fixture facts are not both true: {payload}")
    return payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ravel-0.6-fixtures-") as name:
        directory = Path(name)
        frozen = directory / "ravel_0_5.c"
        candidate = directory / "ravel_0_6_candidate_001.c"
        mutated_planner = directory / "mutated_planner.c"
        mutated_birth = directory / "mutated_birth.c"
        frozen.write_bytes(FROZEN_SOURCE.read_bytes())
        candidate.write_text(build_candidate_source(FROZEN_SOURCE.read_bytes()), encoding="utf-8")
        mutated_planner.write_text(
            candidate.read_text(encoding="utf-8").replace(NEW_PLANNER_CONTEXT, OLD_PLANNER_CONTEXT, 1),
            encoding="utf-8",
        )
        mutated_birth.write_text(
            candidate.read_text(encoding="utf-8").replace(NEW_SEED_FUNCTION, OLD_SEED_FUNCTION, 1),
            encoding="utf-8",
        )
        candidate_payload = expect_pass(candidate, directory)
        frozen_status, frozen_payload = compile_and_run(frozen, directory)
        planner_status, planner_payload = compile_and_run(mutated_planner, directory)
        birth_status, birth_payload = compile_and_run(mutated_birth, directory)
        if frozen_status == 0 or planner_status == 0 or birth_status == 0:
            raise AssertionError(
                "0.5 behavior or a reverted correction unexpectedly passed: "
                f"frozen={frozen_payload} planner={planner_payload} birth={birth_payload}"
            )
        print(
            json.dumps(
                {
                    "schema": "ravel-0.6-behavioral-fixtures-result/1",
                    "candidate": candidate_payload,
                    "frozen_0_5": frozen_payload,
                    "mutated_planner": planner_payload,
                    "mutated_birth": birth_payload,
                    "candidate_pass": True,
                    "negative_pass": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
