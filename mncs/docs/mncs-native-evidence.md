# RRE-2 — MNCS-Native RAVEL: linked multi-module program, arithmetic intents, differential evidence

Date: 2026-08-25. Scope: second reconstruction tranche (Phases 2–3, 6–8 of the
MNCS-native plan).

## Environment

- Sibling `mncs-language` main merged at `04bbf12` (explicit wrapping/saturating
  arithmetic intents `+% -% *%` / `+| -| *|`; `MNCS_LIBRARY_PATH` standard-
  library resolution; imported types nameable in field/payload positions).
  Two upstream defects fixed by this tranche's pressure are recorded in that
  repository's development evidence.
- Sibling `mncs-language-service` main at `9256e43`: standard-library roots in
  `StoreResolver`, resident-resolution candidate analysis.
- Compiler identity observed during verification:
  `mncs:compiler:compiler:f862227638ca7fbc716123d8378cddfef4f76a9ef10ab0e99cc791e65207e45d`.

## What changed in RAVEL

1. **Phase 2 — linked program.** The five self-contained Profile 0.5 modules
   became a cooperating Profile 0.6 program under `mncs/workspace/ravel/`:
   shared `ravel.types.v1 SnapshotId`; status lattice consumed from
   `mncs.core.status.v1` (local duplicates deleted); strict booleans replace
   `both`/`either` helpers; task contexts carry typed snapshot identities;
   stale refusals carry payload (`REFUSE_STALE { expected: SnapshotId }`).
2. **Phase 3 — new modules.** `ravel.lifecycle.v1` (promotion state machine),
   `ravel.provider.v1` (fail-closed Forge dispatch), `ravel.budget.v1`
   (refusable spends), `ravel.forge.v1` (request/receipt binding with stale
   refusal). All consume `mncs.core.*` and `ravel.types.v1`.
3. **Arithmetic honesty resolved.** Checkpoint delta application and memory
   counters now use explicit saturating intents; overflow obligations discharge
   as `language-explicit-Saturating-semantics`. Modules that previously
   reported overall UNKNOWN solely from unresolved exact-cost obligations now
   report PASS with zero unresolved obligations.
4. **Backend pressure.** The Forge checker executes every module on research
   bytecode and portable WASM and records C11/LLVM/Cranelift artifact
   realization honestly.

## Verification results (bounded local evidence)

| Module | bytecode | WASM | unresolved obligations |
| --- | --- | --- | --- |
| ravel.core.v1 | PASS | PASS | 0 |
| ravel.loop.v1 | PASS | PASS | 0 |
| ravel.checkpoint.v1 | PASS | PASS | 0 |
| ravel.memory.v1 | PASS | PASS | 0 |
| ravel.task.v1 | PASS | PASS | 0 |
| ravel.lifecycle.v1 | PASS | PASS | 0 |
| ravel.provider.v1 | PASS | PASS | 0 |
| ravel.budget.v1 | PASS | PASS | 0 |
| ravel.forge.v1 | PASS | PASS | 0 |

Artifact realization on C11/LLVM/Cranelift completes for every module
(`completed_with_unresolved_obligations`, scalar envelope); composite execution
is refused there by design and recorded per module in
`build/mncs-ravel/mncs-experiments.json`.

## Executable legacy differential

`tools/ravel_mncs_differential.py` (new) drives equivalent cases through the
legacy Python implementation and the MNCS modules:

- lifecycle edges vs `src/ravel/knowledge.py::promote`: **16/16 AGREE**. The
  harness exposed a genuine divergence: legacy gates
  restricted→supported promotion on `transfer_status == "supported"`;
  `ravel.lifecycle.v1` now refuses that edge identically (reason code 6) and
  carries regression corpus coverage.
- provider receipts vs `src/ravel/providers.py::ForgeAdapter.request`:
  **6/6 AGREE** (unavailability governs as UNKNOWN both sides with matching
  refusal reasons; raw statuses pass through unchanged).
- hard-gate disposition vs `src/ravel/adaptation.py::evaluate_constraints`:
  **6/6 AGREE** over mapped COMMIT/REJECT scenarios.

Overall: **AGREE, 28/28**. Evidence: `build/mncs-ravel/differential.json`.
Scopes without an executable legacy twin are listed in the report
(stale-snapshot refusal, refusable spends, payload-bearing refusals).

## Language friction encountered this tranche

Resolved upstream during this run:

1. No surface syntax for total arithmetic → Profile 0.6 explicit wrapping/
   saturating operators (mncs-language `04bbf12`); obligations discharge by
   semantics.
2. Standard-library resolution impossible for external consumers →
   `MNCS_LIBRARY_PATH` in the research CLI and the language service.
3. Imported types rejected in field/payload type positions → elaborator fix
   (mncs-language `bffbe40`), discovered immediately by `ravel.task.v1`.

Still open (recorded honestly):

4. Scalar backends cannot execute composite values; RAVEL's two executable
   backends remain bytecode + WASM until RFC 0019 aggregate realizations land
   there.
5. No unary boolean negation operator; `bool_not` import is required
   (`mncs.core.logic`). Cosmetic but recurring friction.
6. Match arms have no wildcard; exhaustive finite matches must enumerate every
   variant. Acceptable explicitness today; a bounded `_` remains future work.
7. Candidate analysis covers one document against its dependencies;
   cross-document candidate workspaces remain service roadmap work.

## Non-claims

All results above are bounded local development observations with honest
PASS/UNKNOWN semantics. They establish no universal equivalence, conformance,
independent evaluation, or promotion.
