# RAVEL 0.4 evidence-hardening contract

## Intended use

RAVEL 0.4 evaluates the existing bounded recursive-expert mechanism under
deterministic synthetic drift. It is an assurance repair, not a foundation-model
or production architecture claim.

## Dataset authority

Every trial has six disjoint, seed-addressed inputs:

1. base training observations;
2. base holdout observations;
3. drift adaptation training observations;
4. untouched drift holdout observations;
5. original-task retention holdout observations; and
6. planning cases.

The drift holdout is never passed to expert birth selection, refinement,
retirement, threshold selection, topology selection, replay selection, or model
selection. The source and evaluator make those operations separate calls.

## Exact routing

Routing may return early only when the routed best distance is strictly lower
than the lower bound for every excluded expert. Equality, malformed data, and
out-of-domain observations cannot certify a shortcut. Valid uncertain
observations fall back to complete scan. Ties choose the lower expert identity.

## Canonical checkpoint

The checkpoint is not a C memory image. It contains:

- an eight-byte magic identifier;
- a big-endian schema version and declared dimensions and topology limits;
- a big-endian payload length;
- a SHA-256 payload digest; and
- a canonical payload using explicit integer widths and signed Q20 fixed-point
  values for retained real-valued fields.

The payload covers expert count, epoch, active and lifecycle status, keys,
reconstruction vectors, action-conditioned prediction vectors, label and action
counts, selected labels, usage/error statistics, retained reconstruction and
prediction statistics, generation, lineage, compiled transition graph, and the
complete routing lattice. Restoration rejects unsupported dimensions or
versions, malformed fields, truncation, oversized payloads, reordered data,
unexpected trailing bytes, invalid graph/routing identities, and digest
mismatch.

Restored behavior is compared over classification, reconstruction and
prediction totals, transition predictions, routing certification and
complete-oracle agreement, planning, model topology, lineage, and the complete
reported evaluation record.

## Planning measurements

Planning reports path found, exact world-state target reached, goal expert
reached, executed path length, calculable optimal path length, regret, graph
disconnection, transition-model error, and state aliasing separately.
Goal-expert equivalence is never named exact success.

## Development disposition

Each trial evaluates every preregistered hard gate. The global development
result is `PASS` only when all eight frozen trials pass. Failures remain evidence
and do not change formal status. Formal MNCS and MNCDS status remain `UNKNOWN`;
promotion remains unauthorized.
