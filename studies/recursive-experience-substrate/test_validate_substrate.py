#!/usr/bin/env python3
"""Exercise positive and negative recursive experience substrate fixtures."""

from __future__ import annotations

from validate_substrate import (
    PROFILE_PATH,
    RECORDS_PATH,
    ExperienceValidationError,
    load_object,
    mutated_fixture,
    validate_profile,
    validate_records,
)

MUTATIONS = (
    "evaluator-authority-expansion",
    "error-only-memory",
    "deleted-failure-memory",
    "post-hoc-hypothesis",
    "unsupported-principle",
    "strategy-without-failure-modes",
    "global-reuse-without-transfer",
    "attribution-without-credit-class",
    "aggregate-only-causal-promotion",
    "future-final-early-access",
)


def main() -> int:
    profile = load_object(PROFILE_PATH)
    bundle = load_object(RECORDS_PATH)
    validate_profile(profile)
    validate_records(profile, bundle)

    for mutation in MUTATIONS:
        candidate_profile, candidate_bundle = mutated_fixture(profile, bundle, mutation)
        try:
            validate_profile(candidate_profile)
            validate_records(candidate_profile, candidate_bundle)
        except ExperienceValidationError:
            continue
        raise AssertionError(f"negative fixture unexpectedly passed: {mutation}")

    print(f"recursive experience negative fixtures: PASS ({len(MUTATIONS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
