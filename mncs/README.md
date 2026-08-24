# MNCS-Native RAVEL

RAVEL reconstructed **in the MNCS language itself**: the reasoning core of
RAVEL — status dominance, evidence combination, candidate disposition, the
learning loop, checkpointed transactions, memory promotion, negative-knowledge
retention, task/snapshot binding — expressed as Source Profile 0.5 programs
with logical record values, verified by language-owned bounded experiments,
and inspected through `mncs-language-service`.

The legacy Python/Rust implementations under `ravel_versions/`, `crates/`,
`src/`, and `tools/` remain the historical and compatibility surfaces. They are
behavioral references for this reconstruction, not its architecture.

## Status

**Implemented / exercised (research).** Five coherent modules run end to end
through semantic → HIR → SSA → backend realization with layered agreement
validation on every module. All experiments are local development evidence;
nothing here is independently evaluated, frozen, promoted, or production
software.

## Layout

```text
mncs/
  workspace/                  one file = one self-contained MNCS module
    ravel_core.mncs           status lattice, evidence combination, dispositions
    ravel_loop.mncs           hypothesis → prediction → observation → attribution
                              → commit-eligibility / negative retention
    ravel_checkpoint.mncs     immutable checkpoints, candidates, commit/rollback
    ravel_memory.mncs         promotion lifecycle, transfer tests, counterexamples
    ravel_task.mncs           task context bound to Language Service snapshot identities
  corpus/                     typed corpora with expected values per case
  tools/                      corpus generators + Forge check entry point
  docs/                       this document set
```

## Module semantics

### ravel.core.v1

`Status { PASS, FAIL, UNKNOWN }` with the MNCS dominance join (`FAIL` ⊒
`UNKNOWN` ⊒ `PASS`) proven over the full 3×3 finite domain; `EvidenceRef`
records combining by dominance; four-gate `disposition()` where any `FAIL`
rejects, unresolved gates hold, and only all-PASS commits; advisory confidence
ranking that never alters governing status. The authority boundary is
structural: there is no function in this module that can turn UNKNOWN into
PASS.

### ravel.loop.v1

The learning loop as pure logic over records: `Hypothesis` carries a falsifiable
predicted status; `attribute(predicted, observed)` yields CONFIRMED / REFUTED /
INCONCLUSIVE with UNKNOWN always inconclusive; `evaluate()` requires hard gates
all-PASS **and** a confirmed prediction for commit eligibility (a candidate can
never certify itself) and retains negative experience whenever the observation
failed or the prediction was refuted. The evidence request is declared with
`capability ravel_evidence_request` and an `observe` effect authorized by it,
so authority is part of the program, not a comment.

### ravel.checkpoint.v1

Transactional adaptation: `Checkpoint` values are immutable; `apply()`
constructs candidate state functionally; `transact()` commits only when gates
are clean, the observation passed, **and** the candidate names its parent
checkpoint (orphan candidates are refused); every other path rolls back to the
untouched baseline. Rollback is structural value selection — isolation does not
depend on defensive sequencing.

### ravel.memory.v1

Promotion lifecycle: episodic support accumulates via `absorb_support()`;
counterexamples accumulate via `absorb_counterexample()`; `promotable()`
requires ≥2 supports and zero counterexamples; `transfer_test()` refuses
out-of-scope use as UNTESTED rather than guessing; `select()` demotes strategies
whose principles carry counterexamples and can only choose among offered
strategies. `absorb_success_after_failure()` makes explicit that later success
adds support but can never decrement a counterexample: negative evidence
survives every positive outcome.

### ravel.task.v1

Task contexts bind reasoning to exact semantic state: `TaskContext` carries
fragments of the resident `mncs-language-service` snapshot identity;
`plan_request()` refuses stale contexts (snapshot drift), out-of-authority or
off-subject requests, and over-budget requests — each refusal explicit and
typed (`REFUSE_STALE`, `REFUSE_AUTHORITY`, `REFUSE_BUDGET`). A refused request
still names the dead context so callers can see which semantic state was
abandoned.

## Verification

Each module is executed by the language-owned experiment flow:

```bash
cargo run -p mncs-cli -- experiment run mncs/workspace/ravel_loop.mncs \
  --backend mncs-research-bytecode --corpus mncs/corpus/ravel-loop-corpus.json
```

Every corpus case carries expected values (including nested record outcomes);
the built-in `backend-lowering-bounded-agreement` translation validator must
judge PASS across body / SSA / backend layers before the Forge check accepts a
module. Overall statuses are reported honestly: modules whose checked integer
arithmetic leaves exact-cost obligations unresolved report UNKNOWN overall even
when every case matches.

Regenerate corpora with `python3 mncs/tools/gen_*.py`; run all checks with:

```bash
python3 tools/ravel_mncs_check.py mncs-experiments
```

(registered as Forge workflow `mncs-experiments`; requires the sibling
`mncs-language` checkout).

## Backend matrix (observed 2026-08-24)

| Construct | research bytecode | portable WASM | LLVM / C11 / Cranelift |
| --- | --- | --- | --- |
| records intra-function | executes | executes | refuse (envelope) |
| record-typed call params/results | executes | refuse CGN302 | refuse (envelope) |
| records through iterate state | executes | refuse CGN302 | refuse (envelope) |
| finite enums + exhaustive match | executes | executes | scalar envelope |
| bounded iteration | executes | executes | scalar envelope |

WASM refusals are correct behavior: the capability envelope is preserved and no
realization approximates unsupported semantics. Extending record realizations
to WASM block parameters and scalar backends remains open language work
(mncs-language roadmap item 1 under "Immediate next work").

## Relationship to the Language Service

Development of these modules used `mncs-language-service` as the resident
semantic layer: workspace status, structured diagnostics, symbol inventory,
subject descriptions with capabilities/effects/obligations, semantic
dependencies, obligation inventories, and context packets were queried against
this workspace during authoring. The service's Phase 4 candidate analysis
(`analyze_candidate`) was driven by this conversion and returns identity-bound
semantic/obligation deltas plus language-computed stale evidence for proposed
changes to these files — without mutating the baseline.

Inside the language, `ravel.task.v1` models what RAVEL consumes from the
service: snapshot-identity fragments, authority domains, budgets, and typed
refusals. The host-side bridge (building TaskContext values from live service
snapshots and feeding them into experiments) remains future work and is the
next integration step.

## Explicit non-claims

- Bounded-corpus behavioral agreement only; no universal equivalence.
- No independent evaluation, protected custody, promotion, or conformance.
- Legacy differential coverage is encoded at the level of distilled behavioral
  contracts (see `docs/mncs-native-evidence.md`); no executable differential
  harness against legacy Python/RVEL runs exists yet.
- Overall UNKNOWN statuses on some modules are honest unresolved obligations,
  not hidden failures.
