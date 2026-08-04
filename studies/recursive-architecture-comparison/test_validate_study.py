#!/usr/bin/env python3
"""Executable positive and negative tests for the recursive study design."""

from __future__ import annotations

from validate_study import StudyValidationError, load_plan, mutated_plan, validate


def expect_failure(plan: dict[str, object], name: str) -> None:
    try:
        validate(plan)
    except StudyValidationError:
        return
    raise AssertionError(f"negative fixture unexpectedly passed: {name}")


def main() -> int:
    plan = load_plan()
    validate(plan)
    for mutation in (
        "evaluator-authority",
        "in-place-mutation",
        "missing-control",
        "duplicate-arm",
        "aggregate-overrides-gate",
        "promotion-authorized",
    ):
        expect_failure(mutated_plan(plan, mutation), mutation)
    print("recursive architecture study fixtures: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
