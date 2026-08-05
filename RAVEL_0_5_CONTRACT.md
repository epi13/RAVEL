# RAVEL 0.5 adaptive-mechanism correction contract

## Authorities and data separation

The maintained C11 executable is an observation source, not the assurance
authority. It receives one preregistered trial ID, regime, and seed and emits
raw integer counts, Q20 squared-error accumulators, checksums, topology traces,
replay coverage, checkpoint mutation observations, and lineage observations.
It does not emit hard gates, trial results, aggregate results, a global
development result, MNCS or MNCDS status, or promotion disposition.

The independent Python evaluator loads the frozen preregistration, verifies the
complete trial matrix and partition derivations, rejects malformed or
contradictory records, derives all floating metrics from raw accumulators,
applies the only threshold authority, and derives trial, aggregate, and global
results.

Each trial uses six independently seeded partitions:

1. 1,024 base-training observations;
2. 256 base-holdout observations;
3. 512 drift-adaptation-training observations;
4. 256 untouched drift-holdout observations;
5. 256 original-task-retention-holdout observations; and
6. 64 planning cases.

Drift and retention holdouts are forbidden inputs to replay selection, expert
birth, refinement, retirement, thresholds, topology, or model selection.

## Replay and protected behavior

Balanced replay deterministically selects at most 256 unique base-training
events. It first covers source-state/action pairs, then assigned experts, then
fills by normalized historical loss. Evidence records label, action, state,
expert, transition-pair, rare-case, high-loss, uniqueness, and checksum facts.
Sparse strata are retained without inventing duplicates.

Base experts are anchored. Adaptation refinement may update separate adaptation
experts but restores anchored base parameters after each mixture pass. Replay
therefore constrains adaptation while the original recursive base remains an
explicit protected reference.

## Adaptive topology

Birth proposals are ranked by the arithmetic mean of eight bounded `[0, 1]`
channels: classification residual, reconstruction residual, supported
next-observation residual, novelty, inverse support, uncertainty, missing
action coverage, and anchored-retention risk. No channel receives a magnitude
multiplier. Equal totals choose the lower event index.

A proposal is accepted only when its adaptation-training plus replay objective
improves by the frozen Q20 minimum. Zero through sixteen births are allowed.
Zero through four retirements are allowed. Retirement is rejected for anchored
experts, rare label/action coverage, supported transition connectivity,
lineage/topology uniqueness, reconstruction or prediction support, or a
measurable protected replay/adaptation objective loss.

No holdout observation participates in a topology decision. Every accepted
birth records the source event, normalized score, and dominant channel; every
retirement records lineage. Rejections are counted.

## Transitions and planning

Every expert/action transition stores up to two target experts with integer
support. Support below two is unknown. Unsupported actions never inherit a seed
event prediction and never become graph edges.

Planning separately reports path found, exact world state reached, goal expert
reached, belief-set target reached, executed and optimal length, regret, graph
disconnection, unsupported edge, transition-model error, and state aliasing.
The ambiguous regime gates belief-set success; exact hidden-state success stays
visible as a diagnostic.

## Checkpoint and routing integrity

The version-5 checkpoint is an in-memory, canonical, length-delimited,
big-endian record with an eight-byte magic, explicit limits and widths, signed
Q20 real encoding, and SHA-256 payload digest. It covers all expert behavior,
transition support, routing, topology, statistics, generation, lineage,
anchoring, and compiled graph fields. Restoration rejects malformed,
truncated, appended, substituted, unsupported, non-finite, or overflowing
records.

Routed evaluation must have zero disagreement with complete scan. Equality at
the routing lower bound falls back to complete scan; tied distances choose the
lower expert ID.

## Disposition

Every hard gate is preregistered by regime. The global result follows the frozen
per-trial and per-regime rule. Evidence reproduction, integrity success, and
the development result are separate fields. A development failure remains
evidence and cannot change formal MNCS or MNCDS status from `UNKNOWN` or
authorize promotion.
