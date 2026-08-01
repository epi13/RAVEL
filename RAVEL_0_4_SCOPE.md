# RAVEL 0.4 evidence-hardening scope

RAVEL 0.4 is a bounded repair release for the existing synthetic RAVEL-U
mechanism study. It does not add a new model class or broaden the intended use.

## Repairs in scope

- replace raw-C-struct checkpointing with a versioned canonical format;
- bind checkpoint identity to every retained behavioral and topology field;
- compare restored classification, reconstruction, prediction, transition,
  routing, planning, topology, lineage, and reported evaluation measurements;
- correct sibling generation metadata and test repeated descendant splitting;
- separate drift adaptation training from untouched drift holdout evaluation;
- execute eight frozen deterministic trials covering eight synthetic regimes;
- report exact-state and expert-equivalence planning outcomes separately;
- add reconstruction and prediction gates;
- compare bounded baselines and ablations without a superiority claim;
- exercise malformed, adversarial, mutation, provenance, and nondeterminism
  failure paths; and
- bind the assurance record to an ordered, machine-verified source manifest.

## Historical audit

RAVEL-U 0.3 adapted on `adapt_set` and then reported adapted performance on that
same array. Its `100%` adapted drift score was therefore an adaptation-training
observation, not an untouched drift-holdout result. RAVEL 0.4 retains the 0.3
evidence as historical evidence and does not relabel that observation.

The 0.3 checkpoint used `fwrite(sizeof(Model))` and omitted decoder and
action-conditioned prediction vectors from `model_digest()`. Its behavioral
checksum also omitted reconstruction and prediction measurements. The 0.4
checkpoint and mutation campaign replace that assurance mechanism.

The 0.3 entrypoint described split `.inc` files as generated, but neither the
repository nor the reviewed pull-request history contains a generator or
higher-level generation specification. RAVEL 0.4 therefore records those files
as maintained split C source. It does not invent a generator to support the old
description.

The 0.3 assurance digest was incorrect. RAVEL 0.4 adds an ordered manifest and a
repository script that calculates and verifies implementation identity. The
historical 0.3 assurance record receives an explicit audit correction rather
than being silently replaced.

## Evidence boundary

All 0.4 evidence is repository-visible development evidence. It is not
independent protected evidence. Synthetic results do not establish real-data
generalization. Deterministic reproduction does not establish
cross-organizational reproduction. Exact routing equivalence does not establish
overall model correctness. Checkpoint reproducibility does not authorize a
production rollback.

Formal MNCS status is `UNKNOWN`. Formal MNCDS status is `UNKNOWN`. Promotion is
unauthorized.
