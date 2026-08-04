# RAVEL version history

This document gives a concise reading path across the RAVEL epochs. It preserves
the published outcomes and points to the version-bound files that carry the
actual contracts, observations, and dispositions.

## RAVEL 0.1 — exact conditional inference

**Question:** Can a quantized expert router return early only when excluded
experts are provably unable to win, while falling back to the complete oracle
otherwise?

**Primary files:** `ravel.c`, `CONTRACT.md`, and `evidence.json`.

The study generated 256 experts and retrieved 24 candidates per familiar query.
Historical development observations reported zero mismatches, complete
certification on the familiar workload, and a mean of 24 evaluated experts.
Uniform control queries frequently required fallback toward the complete scan.

**Status:** favorable bounded development observation; not formal conformance or
production evidence.

## RAVEL-T 0.2 — recursive training

**Question:** Can routed assignments, unresolved error, bounded splits, and child
lineage recursively build a more capable expert population?

**Primary files:** `ravel_train.c`, `TRAINING_CONTRACT.md`, and the
`training-*.json` records.

The recursive 8-to-64 study historically reached the same reported holdout
accuracy as the flat 64-expert comparison while using substantially fewer
training evaluations. The fixed eight-expert comparison retained lower reported
accuracy.

**Status:** favorable bounded development observation; not a general training or
continual-learning claim.

## RAVEL-U 0.3 — unified architecture

**Question:** Can one expert population simultaneously own retrieval,
representation, classification, action-conditioned prediction, transition
memory, bounded planning, adaptation, retirement, lineage, and checkpoint
identity?

**Primary files:** `ravel_unified.c`, `ravel_unified/*.inc`,
`UNIFIED_CONTRACT.md`, `unified-preregistration.json`,
`unified-evidence.json`, `unified-threat-model.json`, and
`unified-assurance-case.json`.

The synthetic world contained 64 states, four actions, eight labels, and
8-dimensional observations. Historical development output reported strong base
accuracy, complete adapted-set drift accuracy, high transition accuracy, bounded
planning success, exact routed-versus-complete agreement, and checkpoint
restoration agreement.

Two caveats are preserved:

- the historical adapted drift value was measured on the same `adapt_set` used
  for adaptation rather than an untouched drift holdout; and
- the historical `exact_goals` field measured goal-expert equivalence rather
  than exact world-state equality.

**Status:** favorable historical observations with known evaluation limitations.

## RAVEL 0.4 — evidence hardening

**Question:** What happens when partitions, checkpoint encoding, negative tests,
planning measurements, baselines, ablations, and source identity are hardened
without removing unfavorable cases?

**Primary files:**

- `ravel_0_4.c`;
- `RAVEL_0_4_CONTRACT.md`;
- `ravel-0.4-preregistration.json`;
- `ravel-0.4-raw-observations.json`;
- `ravel-0.4-trial-evidence.json`;
- `ravel-0.4-negative-evidence.json`;
- `ravel-0.4-source-manifest.json`;
- `ravel-0.4-assurance-case.json`; and
- `RAVEL_0_4_RESULTS.md`.

RAVEL 0.4 introduced disjoint training, adaptation, holdout, retention, and
planning partitions; canonical checkpoint encoding; complete restored-behavior
comparison; mutation fixtures; exact-state planning; additional gates;
comparison systems; and ordered source identity.

All eight frozen trials failed at least one required gate. No seeds, regimes, or
gates were removed to improve the result.

**Status:** development `FAIL` — 0 of 8 trials passed all gates.

## RAVEL 0.5 — mechanism correction and evaluator separation

**Question:** Can mechanism changes and an independently written evaluator close
the most important 0.4 defects without weakening the frozen evidence boundary?

**Primary files:**

- `ravel_0_5.c`;
- `RAVEL_0_5_CONTRACT.md`;
- `ravel-0.5-preregistration.json`;
- `tools/ravel_0_5_evaluator.py`;
- `tools/ravel_0_5_evidence.py`;
- `ravel-0.5-raw-observations.json`;
- `ravel-0.5-trial-evidence.json`;
- `ravel-0.5-negative-evidence.json`;
- `ravel-0.5-source-and-execution-manifest.json`;
- `ravel-0.5-assurance-case.json`;
- `RAVEL_0_5_RESULTS.md`; and
- `RAVEL_0_5_POSTMORTEM.md`.

Mechanism changes included stratified replay, anchored base experts,
objective-tested lifecycle changes, normalized residual channels,
support-bearing top-two transitions, explicit unknown actions, retirement safety,
and belief-set planning. The C executable emitted raw observations while the
Python evaluator derived metrics and gates.

The frozen 32-trial validation produced execution integrity `PASS`; 24 trials
passed and eight failed. Failures remained in label gain, transition prediction
retention, combined exact planning, and ambiguous belief/planning or efficiency.
The all-trials requirement therefore failed.

The candidate improved some paired means relative to matched comparisons, but
the Pareto results were mixed and no superiority claim was made.

**Status:** development `FAIL` — 24 of 32 trials passed; aggregate all-trials gate
failed.

## RAVEL 0.6 — preregistered retention-constrained development

**Question:** Can retention-constrained adaptation improve label and combined
drift while preserving original-task and transition support under an explicitly
separated development and selection lifecycle?

**Primary files:**

- `RAVEL_0_6_SCOPE.md`;
- `RAVEL_0_6_PREREGISTRATION.md`;
- `ravel-0.6-preregistration.json`;
- `ravel-0.6-threat-model.json`;
- `ravel-0.6-development-record.json`;
- `ravel-0.6-limitations.md`;
- `tools/ravel_0_6_seed_candidate.py`; and
- `RAVEL_0_6_NEXT_STEPS.md`.

The epoch was preregistered before implementation. Development, selection,
retention, transition-retention, planning, and future-final partitions have
distinct identities. Future-final seed material is intentionally absent.

Candidate-001 can now be derived reproducibly from the exact frozen 0.5 source.
The derivation corrects two bounded issues:

1. planning traverses both supported transition targets rather than only slot
   zero; and
2. a newly born adaptation expert receives support only from its spawning event
   rather than inheriting unrelated empirical support from its parent.

This is development preparation only. Candidate-001 has not been selected,
frozen as final, independently evaluated, or promotion-authorized.

**Status:** preregistered development; selection, future-final evaluation,
protected custody, independent operation, formal MNCS/MNCDS status, and promotion
remain `UNKNOWN` or unauthorized.

## Cross-version claim boundary

RAVEL shows how a machine-native architecture and its evidence system can evolve
through explicit epochs while preserving failed results and historical caveats.
It does not establish general intelligence, language-model performance,
real-world generalization, production safety, protected evaluation, or formal
conformance.
