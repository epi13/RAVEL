# Recursive experience substrate study

This directory contains the executable design boundary for a post-RAVEL-0.6 recursive experience
and causal-learning substrate.

The track addresses a limitation in error-only recursion: structured failures can guide another
candidate, but they do not by themselves preserve successful behavior, distinguish competing causal
explanations, attribute effects to interventions, support delayed lineage credit, or constrain when
a lesson may be reused.

## Contents

- `architecture-profile.json` defines immutable authority, memory classes, six record types, status
  separation, credit classes, controls, hard gates, negative tests, and the claim boundary.
- `reference-records.json` provides linked examples for experience episodes, causal hypotheses,
  interventions, causal attribution, learned principles, and reusable strategies.
- `validate_substrate.py` performs offline semantic validation with only the Python standard library.
- `test_validate_substrate.py` applies deterministic mutations that must fail closed.

Run:

```bash
python studies/recursive-experience-substrate/validate_substrate.py
python studies/recursive-experience-substrate/test_validate_substrate.py
```

or from the repository root:

```bash
make recursive-experience-substrate-check
```

## Key boundary

The substrate stores compact, identity-bearing developmental records. It does not require hidden
reasoning transcripts and does not create a second evaluator. RAVEL supplies the recursively
replaceable mechanism, Forge may supply bounded probes, MNCDS governs development lineage and
feedback eligibility, and MNCS evaluates the frozen implementation claim.

The profile is additive research design. It does not modify frozen RAVEL 0.4 or 0.5 artifacts,
RAVEL 0.6 preregistration or final material, or the existing recursive-architecture comparison
study. Formal MNCS and MNCDS status remain `UNKNOWN`; independent evaluation, protected custody,
and promotion remain unavailable without eligible external evidence.
