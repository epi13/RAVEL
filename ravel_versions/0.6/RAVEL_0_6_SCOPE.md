# RAVEL 0.6 retention-constrained adaptation scope

RAVEL 0.6 is a new, preregistered development epoch. It may use the frozen
RAVEL 0.5 final observations as cross-epoch design information, but it may not
alter 0.5 or reuse its final material as 0.6 final evaluation.

## Primary hypothesis

A retention-constrained adaptation policy using stratified replay protection,
objective-tested updates, and transition-support preservation can improve
label-drift and combined-drift holdout performance while preserving base-task
retention and original-task next-observation prediction within frozen bounds.

The hypothesis is narrow. It is not “make all trials pass.” Ambiguous
belief-planning and broad efficiency superiority are secondary diagnostics and
non-promotion observations, not primary selection objectives.

## In scope

- label drift and combined observation/label drift;
- distinct development, selection, retention, transition-retention, planning,
  and future final-evaluation partitions;
- deterministic development and selection seed derivation;
- retention-protected replay strata and transition-support constraints;
- objective-tested, bounded updates with an explicit reject/no-change outcome;
- matched-compute RAVEL 0.5 and fixed-topology comparisons;
- no-retention-constraint, no-transition-protection, periodic-replay, and
  unconditional-update ablations;
- canonical checkpoints, source identities, mutation tests, and independently
  derived evaluator dispositions; and
- a future one-shot final evaluation whose seed material is obtained only after
  the selected candidate is frozen.

## Out of scope

- modifying or relabeling RAVEL 0.4 or 0.5;
- reusing 0.5 final seeds or evidence as 0.6 final evaluation;
- optimizing against future final material;
- broad ambiguous-belief planning claims or universal efficiency superiority;
- real-world, language, multimodal, distributed, accelerator, deployment, or
  production-safety claims; and
- claims of protected custody, independent evaluation, formal conformance,
  certification, governance approval, or promotion.

No 0.6 implementation or evaluation exists at preregistration time. All
implementation, development, final, MNCS, and MNCDS results therefore remain
`UNKNOWN`, and promotion is unauthorized.
