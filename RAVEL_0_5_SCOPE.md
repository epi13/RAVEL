# RAVEL 0.5 adaptive-mechanism correction scope

RAVEL 0.5 is a bounded correction to the synthetic recursive-expert study. It
uses RAVEL 0.4 as historical development information but does not rewrite the
0.4 mechanism, seeds, gates, or evidence.

## In scope

- move every hard-gate, trial, aggregate, and development disposition into an
  independent Python evaluator;
- emit raw integer observations and integrity facts from the C harness;
- freeze four fresh validation seeds for each of the eight existing regime
  families after mechanism development;
- replace periodic replay with deterministic stratified replay covering labels,
  actions, source states, assigned experts, transition support, rare events, and
  high-loss events;
- make expert births and retirements optional, bounded, and dependent only on
  adaptation-training and replay measurements;
- use normalized, separately recorded residual channels with deterministic
  tie-breaking;
- anchor base experts while allowing separate adaptation experts;
- represent unsupported transitions as unknown and retain two supported
  transition targets where ambiguity is observed;
- separate exact state, goal expert, belief-set, graph-disconnection,
  unsupported-edge, transition-error, and aliasing planning measurements;
- protect rare coverage, transition connectivity, reconstruction and prediction
  support, lifecycle, lineage, and topology uniqueness during retirement;
- add matched-work, matched-count, matched-capacity, replay-policy, no-birth,
  and no-retirement comparisons with paired per-seed and Pareto reporting; and
- bind source, evaluator, evidence tooling, build flags, schemas, CI, and
  maintained provenance into one ordered source and execution manifest.

## Out of scope

RAVEL 0.5 does not add language modeling, multimodal generation, learned
real-world perception, external side effects, deployment authorization,
production rollback, distributed training, accelerator claims, or a formal
conformance claim.

All evidence is repository-visible development evidence. Formal MNCS status is
`UNKNOWN`; formal MNCDS status is `UNKNOWN`; promotion is unauthorized.
