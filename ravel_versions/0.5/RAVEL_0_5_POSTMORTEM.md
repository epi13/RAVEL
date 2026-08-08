# RAVEL 0.4 postmortem and RAVEL 0.5 correction record

RAVEL 0.4 succeeded at evidence custody and failed its frozen development
protocol. Its immutable record remains:

- execution integrity: `PASS`;
- development result: `FAIL`;
- passing trials: `0`;
- failing trials: `8`;
- formal MNCS status: `UNKNOWN`;
- formal MNCDS status: `UNKNOWN`; and
- promotion authorized: `false`.

No 0.4 source, seed, gate, raw observation, or derived result was changed by the
0.5 work.

## What 0.4 established

RAVEL 0.4 established disjoint adaptation and holdout partitions, complete-field
canonical checkpointing, deliberate corruption detection, deterministic
multi-regime reproduction, honest variance, exact-state planning diagnostics,
and ordered source identity. Those are assurance successes, not mechanism
success.

## Mechanism failures

- Label drift and combined drift overwrote too much base behavior. Label drift
  failed base retention, and combined drift also failed retention.
- Transition drift did not preserve original-task next-observation quality.
- The single transition edge could appear supported for an action that had
  never been observed, making planning overly confident.
- Replay sampled every fourth event rather than protecting declared strata,
  rare support, or historically difficult observations.
- Adaptation forced eight births and four retirements regardless of need.
- Retirement utility omitted retention coverage, transition connectivity, and
  reconstruction/prediction support.
- Residual ranking used incompatible large magnitude constants, so unit scale
  rather than declared importance could dominate topology.
- Exact-state planning was not belief-aware under partial observation.

## Gate-design failures

Four low-drift or already-solved regimes failed because 0.4 required the same
absolute `adapted_gain_over_static >= 0.05` even when little or no accuracy
headroom existed. Label drift also required reconstruction improvement even
though observations were unchanged. The ambiguous regime used exact hidden
state as the capability gate despite deliberately aliased observations.

Those failures remain legitimate failures of the frozen 0.4 protocol. RAVEL
0.5 does not relabel them. It preregisters semantics-specific gates:
non-inferiority and headroom for low drift, label and retention behavior for
label drift, representation behavior for observation drift, transition and
planning behavior for transition drift, joint adaptation and retention for
combined drift, and alias-aware belief-set planning for ambiguity.

## Assurance failures found during 0.5

The 0.4 C executable was still the sole producer of gate booleans, trial
results, and the global result. Several named negative tests were aliases, and
some provenance tests only checked that a digest was nonzero. RAVEL 0.5 moves
all dispositions to an external evaluator and executes distinct raw,
threshold, seed, regime, verdict-injection, manifest, source-substitution,
ordering, omission, build, artifact, and nondeterminism mutations.

The smallest justified follow-up after any preserved 0.5 failure is a new
preregistered development experiment using new development seeds. Final 0.5
seeds, gates, and mechanism code must not be repaired in response to their
one-shot result.

## Post-freeze tooling audit

The first final evidence-generation pass preserved the complete raw trial
observations but found that the external `regime_mutation` fixture selected the
second trial's regime. Because the first two frozen trials share the same
regime, that operation made no change and correctly failed the negative-test
campaign. The fixture was corrected to select the first actually different
declared regime. No executable mechanism, seed, regime, threshold, raw trial
observation, or independently derived trial result changed. Regeneration after
this assurance-tool correction is separately committed and source-manifest
bound.
