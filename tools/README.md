# RAVEL tooling guide

The scripts in this directory build, verify, mutate, digest, and summarize RAVEL
evidence. They are support tools, not automatic sources of independent custody,
organizational independence, or promotion authority.

The preserved 0.4 and 0.5 modules retain their original case-root assumptions
and bytes. Run `ravel_versions/0.4/run_evidence.py`,
`ravel_versions/0.4/run_source_digest.py`, or
`ravel_versions/0.5/run_evidence.py` through the root Makefile for the relocated
layout; those small runners provide path compatibility without rewriting frozen
modules or historical logical paths.

## Tool categories

| Tool | Role |
|---|---|
| `ravel_0_4_evidence.py` | Generate, verify, and record bounded 0.4 evidence and runtime observations |
| `ravel_source_digest.py` | Verify ordered 0.4 source identity and assurance bindings |
| `ravel_0_5_evaluator.py` | Independently derive 0.5 metrics and hard gates from raw observations |
| `ravel_0_5_evidence.py` | Orchestrate 0.5 generation, verification, mutation tests, development gates, manifest tests, and runtime capture |
| `ravel_0_5_source_digest.py` | Verify 0.5 source and execution identity |
| `ravel_0_6_seed_candidate.py` | Derive bounded 0.6 candidate-001 development source from an exact SHA-256-bound 0.5 input |
| `ravel_0_6_build.py` | Generate and compile candidate-001 in a temporary directory with provenance-bound raw build output |
| `ravel_0_6_behavioral_fixtures.py` | Run compiled slot-one planning and birth-support fixtures plus bounded reverted-correction mutations |

Other support modules in this directory should follow the same separation:
mechanism execution emits facts; evaluators derive results; digest tools bind
identity; orchestration scripts do not silently expand claims.

## Verification before generation

Prefer read-only or temporary-output targets first:

```bash
make 0.4-check
make 0.4-manifest-negative-test
make 0.4-checkpoint-test
make 0.4-lineage-test
make 0.4-negative-test

make 0.5-test
make 0.5-check
make 0.5-development-gates
make 0.5-negative-test
make 0.5-manifest-negative-test
```

The compiler-matrix and sanitizer targets add useful implementation checks:

```bash
make 0.4-compiler-matrix
make 0.4-sanitizers
make 0.5-compiler-matrix
make 0.5-sanitizers
```

## Targets that rewrite evidence

The following targets may replace repository-visible development records:

```bash
make 0.4-evidence
make 0.4-runtime
make 0.5-evidence
make 0.5-runtime
```

Run them only when intentionally updating the applicable epoch. Review the full
diff, confirm the candidate and source identity, and preserve failed or
`UNKNOWN` results.

## RAVEL 0.5 authority split

The 0.5 C executable should emit raw integer observations and integrity facts. It
must not declare the authoritative development verdict. The Python evaluator:

- validates the frozen trial and partition matrix;
- rejects missing, duplicated, malformed, contradictory, or substituted data;
- derives metrics from raw facts;
- applies each hard gate independently;
- preserves all failed trials and reason codes; and
- generates human-readable results from canonical evidence.

A separate program is useful for authority separation, but repository-local
separation alone is not organizational independence or protected evaluation.

## RAVEL 0.6 candidate derivation

`ravel_0_6_seed_candidate.py` is deliberately narrow. It:

- requires the exact frozen 0.5 source digest;
- applies only declared transformations;
- requires each transformation to match exactly once;
- produces deterministic development source;
- supports read-only checking; and
- does not claim selection, final evaluation, or promotion.

The current candidate-001 corrections expand planning traversal to all declared
transition slots and remove inherited empirical support from adaptation births.
See `../ravel_versions/0.6/RAVEL_0_6_NEXT_STEPS.md` for the remaining lifecycle and evidence work.

The corresponding read-only development checks are:

```bash
make -f ravel_versions/0.6/Makefile build
make -f ravel_versions/0.6/Makefile behavioral-test
```

Both produce development observations only. They do not consume selection or
future-final partitions, freeze a candidate, or create evidence of independent
evaluation or promotion.

## Adding or changing a tool

A tooling change should state:

1. which epoch and candidate it applies to;
2. whether it reads or writes evidence;
3. which inputs and executable identities it binds;
4. whether it emits facts or derives verdicts;
5. which malformed or adversarial inputs it rejects;
6. whether its output is deterministic;
7. whether the change invalidates prior manifests or assurance records; and
8. which claims remain outside repository-local authority.

Do not reuse final observations as same-candidate repair input, weaken gates after
observing outcomes, discard failed records, or convert missing external evidence
into `PASS`.
