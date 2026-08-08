# RAVEL 0.6 preregistration

This document is the readable companion to
`ravel-0.6-preregistration.json`. The JSON record is the structured
development authority for epoch `ravel.retention-constrained-adaptation.epoch-1`.
It is preregistration, not evidence that the mechanism exists or works.

## Frozen baseline and permitted recursion

RAVEL 0.5 candidate `ravel-0.5-candidate-1` is the immutable baseline. Its
source digest is
`201e0373cc8d8f2fb26f284f44b0f87a5751a047d91556213b7aa7bf07e26fa4`
and its source/execution manifest SHA-256 is
`18006006db509269ee374a39133bb25d8452edc0fe0103a43fa92c5660fd89d0`.
Its development result remains `FAIL`, formal MNCS and MNCDS status remain
`UNKNOWN`, and promotion remains unauthorized.

The following final 0.5 findings may inform a new epoch:

- three label-drift trials failed the frozen label-gain gate;
- one transition-drift trial failed original-task prediction retention;
- one combined-drift trial failed exact-state planning;
- ambiguous trials failed belief/path planning or conditional-inference
  efficiency gates;
- paired Pareto comparisons were mixed; and
- the complete 0.5 assurance and provenance limitations remain applicable.

These are recursive design inputs only. They are not 0.6 final evidence and
must not be relabeled as such.

## Authority and identities

The intended first implementation identity is
`ravel-0.6-candidate-001`; every material implementation change after any
material evaluation increments the candidate identity. The generator is a
repository-controlled development actor. The evaluator must be a separately
maintained program that consumes raw observations and derives gates without
trusting executable verdicts. This separation does not create organizational
independence.

Development and selection seeds are distinct and deterministically derived.
Retention, transition-retention, and planning inputs use separate domain tags
within each trial. Future final seed material is deliberately absent. It must
be obtained after candidate freeze, preferably by an external custodian, and
must never be disclosed to the development generator. Until that happens,
protected custody and independent evaluation are `UNKNOWN`.

## Mechanism and budget

The candidate may add retention constraints around the existing 0.5
adaptation surface. Replay remains stratified and bounded to 256 records.
Each proposed update is measured on adaptation objectives plus development-only
retention and transition-support probes. An update is accepted only if it
improves the declared adaptation objective, preserves the retention floors,
and does not remove uniquely supported transitions. Rejection leaves the prior
state unchanged.

The epoch permits at most 16 births, four retirements, two objective-tested
update passes, 80 experts, eight candidate implementations before a new
preregistration revision, and 1.10 times matched fixed-topology training
evaluations. Thresholds may not be changed in response to selection or final
observations.

## Primary gates

Every selected label-drift and combined-drift trial must satisfy:

- base holdout accuracy at least `0.85`;
- retained original-task accuracy at least `0.90`;
- retained accuracy loss from base no worse than `-0.10`;
- original-task prediction RMSE degradation at most `1.0`;
- no routed-versus-complete mismatch;
- capacity, compute, replay, checkpoint, lineage, and transition-support
  integrity gates.

Label drift additionally requires adapted drift accuracy at least `0.60` and
gain over static of at least `0.04`. Combined drift requires adapted accuracy
at least `0.65`, gain at least `0.05`, non-worsening reconstruction and
prediction, transition-accuracy loss no worse than `-0.15`, and exact-state
planning at least `0.50`. These retain the relevant 0.5 meanings rather than
weakening gates to fit known failures.

Selection requires every selection trial to pass all primary gates. If none
does, the epoch stops with no selected candidate. Ties are resolved by the
frozen lexicographic policy in the JSON record, never by future final results.

## Final boundary and stopping

After selection, source, evaluator, manifest, compiler profiles, thresholds,
partitions, and the candidate are frozen before a final seed request. Final
evaluation is one-shot. Its observations cannot repair the same candidate
epoch. A material change starts a new candidate identity and, when it changes
the hypothesis, thresholds, evaluator, or partitions, a new epoch or explicit
preregistration revision.

Any malformed, missing, unsupported, timed-out, crashed, identity-drifted, or
unavailable required material yields `UNKNOWN`, never `PASS`. `FAIL` dominates
`UNKNOWN`, which dominates `PASS`. Regardless of future development results,
formal MNCS and MNCDS status remain separate and require their own complete
evidence and governance. Promotion defaults to `false`.
