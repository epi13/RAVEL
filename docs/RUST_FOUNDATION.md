# RAVEL Rust foundation

This document records the decision that **Rust is the canonical future
implementation language for RAVEL**. It does not rewrite historical C or Python
evidence, freeze candidate-001, or authorize promotion.

## Why Rust now

The existing C lineage (0.1–0.6 candidate-001) and the Python control-plane
scaffolding remain the evidence-bearing record of how RAVEL got here. They are
not discarded.

They are also not the right long-term home for the next RAVEL phases
(knowledge lifecycle, compaction, retention, and data curation). Those phases
need:

- explicit ownership of identities, scopes, and fail-closed status;
- append-only records that cannot be mutated by a later projection;
- a language that can sit beside MNCS's Rust validator and language-evidence
  Wave One (`Rust 1.97.1`, edition 2024) without inventing a third runtime;
- an interchange that C and Python can still prove against.

The authority invariant is unchanged:

> RAVEL may remember any accurately typed experience, but only MNCS/MNCDS-governed
> evidence can establish the status and permitted use of that experience.

That invariant is implementation-independent. Rust is how new RAVEL behavior
should be written; it is not a new source of authority.

## What this foundation contains

The Cargo workspace at the repository root:

| Crate | Responsibility |
|---|---|
| `ravel-contracts` | Versioned schema IDs, status vocabulary, rejection reasons, canonical JSON, digests |
| `ravel-memory` | Existing memory-record types and an append-only JSONL store |
| `ravel-core` | Adaptation, checkpoint, worlds, planning, frozen policy, lifecycle, experience, C-observation evaluation, fail-closed Forge boundary |
| `ravel-cli` | `ravel-rs` JSON interchange used by Forge and Python parity tests |

Contract identities introduced or bound here:

- `ravel-rust-foundation/0.1`
- `ravel-interchange/0.1`
- `ravel-canonical-json/1`

Unchanged inherited identities:

- `ravel-0.6-mechanism-checkpoint/0.1`
- `ravel-0.6-candidate-ledger/0.1`
- `ravel-0.6-world-abi/1`
- `ravel-0.6-checkpoint-abi/1`
- `ravel-0.6-transaction/0.1`
- `ravel-0.6-matched-compute/0.1`
- `ravel-fabric-workload/0.1`
- `ravel-fabric-observation/0.1`

## What remains C and Python

- Frozen 0.4 and 0.5 source, manifests, and `FAIL` evidence stay byte-identical.
- Candidate-001 remains generated C. The separately compiled world and
  checkpoint ABIs stay C contracts.
- Python remains the 0.6 development adapter: Fabric `LocalController`,
  optional MNCS receipt/bundle delegation, Forge check orchestration, and the
  historical unittest corpus.
- Python is a compatibility and evidence runner, not the future implementation
  home.

## Cross-language proof

`ravel-rs interchange` accepts a versioned envelope. Python
`ravel.rust_bridge` and `tests/test_rust_parity.py` send the same inputs to
Rust and compare discrete results:

- constraint reason codes and accept/reject;
- frozen policy `threshold_identity`;
- toy-world plan actions and `UNKNOWN` routes;
- canonical checkpoint bytes;
- C transaction observation evaluation;
- advisory experience class (`negative` vs `episodic`).

Forge workflows `rust-build`, `rust-test`, `rust-python-parity`, and
`rust-c-parity` record those proofs as development observations. They are not
independent evaluation and do not promote 0.6.

## Sibling boundaries

- **Forge** executes declared commands. The new workflows are project-local;
  Forge does not become a RAVEL evaluator.
- **Fabric** remains a Python sibling. Rust ingests
  `ravel-fabric-observation/0.1` by reference and stores Fabric PASS as
  advisory `UNKNOWN`.
- **MNCS** remains authority. RAVEL does not depend on `mncs-validator-rs` and
  does not reimplement receipt or bundle construction.
- **Commons** continues to translate 0.6 development records without deciding
  what RAVEL learns. The Rust foundation contract is an additional recognized
  family identity, not a promotion claim.

## Next phase, not this one

The first knowledge-store milestone now lives in `ravel-memory`:

- fail-closed `ravel-knowledge-lifecycle/0.1` promotion;
- semantic consolidation and retrieval-layout planning;
- retention that compact-by-proposal and never deletes sources;
- content-addressed artifacts; and
- inspectable curation reports.

Vector indexes, learned routing, and automated promotion remain out of scope.

Still not part of this milestone:

- selection evaluation of candidate-001;
- external custody or R6-06 claims.
