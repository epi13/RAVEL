# MNCS-Native RAVEL

RAVEL reconstructed **in the MNCS language itself**: the reasoning core of
RAVEL — status dominance, evidence combination, candidate disposition, the
learning loop, checkpointed transactions, memory promotion, negative-knowledge
retention, task/snapshot binding, the knowledge promotion lifecycle, Forge
provider dispatch, resource accounting, and request/receipt binding — expressed
as a linked Source Profile 0.6 program that consumes `mncs.core`, verified by
language-owned bounded experiments on two executable backends, differentially
checked against the legacy implementation, and inspected through
`mncs-language-service`.

The legacy Python/Rust implementations under `ravel_versions/`, `crates/`,
`src/`, and `tools/` remain the historical and compatibility surfaces. They are
behavioral references for this reconstruction, not its architecture.

## Status

**Implemented / exercised (research).** Nine cooperating MNCS modules form one
linked program: they import each other (`ravel.types.v1`) and the standard
library (`mncs.core.status.v1`, `mncs.core.logic.v1`). Every module runs end to
end through semantic → HIR → SSA → backend realization with layered agreement
validation, **PASS** with zero unresolved obligations on both executable
backends. All experiments are local development evidence; nothing here is
independently evaluated, frozen, promoted, or production software.

## Layout

```text
mncs/
  workspace/ravel/            a linked multi-module program (Profile 0.6)
    types.mncs                ravel.types.v1      shared SnapshotId identity vocabulary
    core.mncs                 ravel.core.v1      status lattice use, evidence combination,
                                                 dispositions (imports mncs.core.status.v1)
    loop.mncs                 ravel.loop.v1      hypothesis → prediction → observation →
                                                 attribution → commit-eligibility / retention
    checkpoint.mncs           ravel.checkpoint.v1 immutable checkpoints, candidates,
                                                 saturating delta application, commit/rollback
    memory.mncs               ravel.memory.v1    promotion gates, transfer tests, counterexamples
    task.mncs                 ravel.task.v1      TaskContext bound to service snapshot identity;
                                                 payload-bearing stale refusals
    lifecycle.mncs            ravel.lifecycle.v1 full promotion state machine, fail-closed edges
    provider.mncs             ravel.provider.v1  Forge capability dispatch; UNAVAILABLE ≠ PASS
    budget.mncs               ravel.budget.v1    refusable spends; saturating plan merging
    forge.mncs                ravel.forge.v1     request/receipt binding; stale receipts refused
  corpus/                     typed corpora with expected values per case
  tools/                      corpus generators + Forge check + differential harness
  docs/                       this document set
```

## Module semantics

### ravel.core.v1

Consumes the authoritative status lattice from `mncs.core.status.v1`
(dominance: `FAIL` ⊒ `UNKNOWN` ⊒ `PASS`); `EvidenceRef` records combining by
dominance; four-gate `disposition()` where any `FAIL` rejects, unresolved gates
hold, and only all-PASS commits; advisory confidence ranking that never alters
governing status. The authority boundary is structural: there is no function in
this module that can turn UNKNOWN into PASS.

### ravel.loop.v1

The learning loop as pure logic over records: `Hypothesis` carries a falsifiable
predicted status; `attribute(predicted, observed)` yields CONFIRMED / REFUTED /
INCONCLUSIVE with UNKNOWN always inconclusive; `evaluate()` requires hard gates
all-PASS **and** a confirmed prediction for commit eligibility (a candidate can
never certify itself) and retains negative experience whenever the observation
failed or the prediction was refuted. Strict boolean operators replace the
pre-0.6 helper predicates. The evidence request is declared with
`capability ravel_evidence_request` and an `observe` effect authorized by it,
so authority is part of the program, not a comment.

### ravel.checkpoint.v1

Transactional adaptation: `Checkpoint` values are immutable; `apply()`
constructs candidate state functionally using **explicit saturating
arithmetic** (`+|`), which discharges overflow obligations by semantics;
`transact()` commits only when gates are clean, the observation passed, **and**
the candidate names its parent checkpoint (orphan candidates are refused);
every other path rolls back to the untouched baseline.

### ravel.memory.v1

Promotion gates: support and counterexample counters accumulate via saturating
increments; `promotable()` requires ≥2 supports and zero counterexamples;
`transfer_test()` refuses out-of-scope use as UNTESTED rather than guessing;
`select()` demotes strategies whose principles carry counterexamples and can
only choose among offered strategies. Counterexamples are never decremented:
negative evidence survives every positive outcome.

### ravel.task.v1

Task contexts bind reasoning to exact semantic state through the shared
`ravel.types.v1 SnapshotId`; `plan_request()` refuses stale contexts — naming
the expected snapshot in the refusal payload — plus out-of-authority,
off-subject, and over-budget requests. A refused request still names its dead
context so callers can see which semantic state was abandoned.

### ravel.lifecycle.v1

The full knowledge promotion state machine as explicit values: every edge is
named; an episode can never skip directly to a global strategy; principle
minting requires supported attribution; transfer testing requires at least one
supporting evidence identity; final strategy promotion requires a *supported*
transfer test; counterexample and retirement stages are terminal. All guards
were aligned case-by-case against the legacy `src/ravel/knowledge.py` state
machine by the differential harness.

### ravel.provider.v1

Fail-closed Forge dispatch: operation mismatch, witness mismatch, or unmet
determinism produce explicit `UNAVAILABLE` receipts whose governed status is
**UNKNOWN** — absence of authority never fabricates PASS. Provider failures
produce `FAILED` receipts whose governed status stays FAIL and are retained as
negative evidence.

### ravel.budget.v1

Refusable resource accounting: overdraw refuses with the untouched budget
returned; negative spends are refused; plans merge by saturating aggregation so
combining plans cannot manufacture unbounded capacity.

### ravel.forge.v1

Request/receipt binding: a receipt must name the same task, obligation, and
snapshot as its request; snapshot drift is refused as its own verdict
(`STALE_RECEIPT`) even when the receipt is favorable; statuses pass through
untouched — an unbound PASS degrades to UNKNOWN, a FAIL remains FAIL.

## Verification

Each module is executed by the language-owned experiment flow:

```bash
MNCS_LIBRARY_PATH=../mncs-language/library \
cargo run -p mncs-cli -- experiment run mncs/workspace/ravel/loop.mncs \
  --backend mncs-portable-wasm-mvp --corpus mncs/corpus/ravel-loop-corpus.json
```

Every corpus case carries expected values (including nested record outcomes and
payload-bearing variants); the built-in translation validators must judge PASS
before the Forge check accepts a result. Overall statuses are honest.

Regenerate corpora with `python3 mncs/tools/gen_*.py`; run all checks with:

```bash
python3 tools/ravel_mncs_check.py mncs-experiments
python3 tools/ravel_mncs_differential.py
```

(registered Forge workflow: `mncs-experiments`; requires the sibling
`mncs-language` checkout; the checker probes toolchains for Profile 0.6
imports, strict booleans, and explicit arithmetic intents before trusting
them).

## Backend matrix (observed 2026-08-25)

| Module | research bytecode | portable WASM | C11 / LLVM / Cranelift |
| --- | --- | --- | --- |
| all nine modules | **PASS** | **PASS** | artifact emitted; execution outside scalar envelope |

Composite values (records, payload sums) execute end to end on research
bytecode and portable WASM. The scalar backends realize artifacts but their
process/object envelope does not admit composite arguments; refusals are
recorded per module as evidence by the checker rather than assumed.

## Legacy differential

`tools/ravel_mncs_differential.py` executes equivalent bounded cases through
the legacy Python implementation and the MNCS modules and compares semantic
outputs per case (explicit scopes; no whole-program equivalence claim):

- lifecycle edges vs `src/ravel/knowledge.py`: **16/16 AGREE** (the harness
  caught and fixed a real divergence in final-promotion transfer gating);
- provider receipts vs `src/ravel/providers.py`: **6/6 AGREE**;
- hard-gate disposition vs `src/ravel/adaptation.py`: **6/6 AGREE**.

Evidence: `build/mncs-ravel/differential.json`.

## Relationship to the Language Service

Development of these modules uses `mncs-language-service` as the resident
semantic layer. Since the Phase 4 candidate-analysis integration, the service
resolves `use` targets against resident workspace documents **and** standard-
library roots exported via `MNCS_LIBRARY_PATH`, so these modules analyze
cleanly in place; `analyze_candidate` elaborates candidates against resident
dependencies, producing identity-bound semantic/obligation deltas without
false unresolvable-import diagnostics.

Inside the language, `ravel.task.v1` models what RAVEL consumes from the
service: snapshot identities, authority domains, budgets, and typed refusals.
The host-side bridge (building TaskContext values from live service snapshots
and feeding them into experiments) remains future work.

## Explicit non-claims

- Bounded-corpus behavioral agreement only; no universal equivalence.
- No independent evaluation, protected custody, promotion, or conformance.
- Legacy differential coverage covers three executable scopes; stale-snapshot
  refusal, refusable budget spends, and payload-bearing refusals have no
  executable legacy twin and are recorded as MNNS-extension scopes.
- Saturating delta/counter semantics are an intentional improvement over the
  legacy's arbitrary-precision integers; agreement cases stay within ranges
  where the two coincide.
