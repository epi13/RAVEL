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

---

# RRE-3 — Modernization campaign: generic envelopes, Digest32 identity, five-backend execution, repaired tooling

Date: 2026-09-13. Scope: comprehensive RAVEL reconciliation against the
current `mncs-language` (type-architecture + bounded-data + typed-ABI era).

Historical tranches above are preserved as written; what follows is new
development evidence, not a rewrite of the record.

## Environment

- Sibling `mncs-language` at `095d87c` (TYPE-P-001/002/003 typed ABI
  transport with identity-only nominal resolution; semantic Bool;
  BodyType resolved-type invariant; profiles through 0.16).
- RAVEL working branch `campaign/ravel-modernization-2026-09` from
  `cecd5bb`.
- Compiler identity observed during verification:
  `mncs:compiler:compiler:f862227638ca7fbc716123d8378cddfef4f76a9ef10ab0e99cc791e65207e45d`.

## Source-profile matrix (lowest justified profile per module)

| Module | Profile | Justification |
| --- | --- | --- |
| ravel.types.v1 | 0.6 | shared records, scalar equality; no newer capability consumed |
| ravel.core.v1 | 0.10 | generic `summarize<4>` envelope over imported `[Status; 4]` |
| ravel.loop.v1 | 0.6 | imports + strict booleans + payload sums + capability/effect |
| ravel.checkpoint.v1 | 0.6 | saturating intents + capability; no generics consumed |
| ravel.memory.v1 | 0.6 | saturating intents; scalar promotion gates |
| ravel.task.v1 | 0.6 | imported nominal payloads; logic-lib booleans |
| ravel.lifecycle.v1 | 0.6 | payload sums; exhaustive finite matches |
| ravel.provider.v1 | 0.6 | payload sums; logic-lib booleans; capability |
| ravel.budget.v1 | 0.6 | checked/saturating intents; payload sums |
| ravel.forge.v1 | 0.6 | imported nominal payloads; logic-lib booleans |
| ravel.identity.v1 | 0.10 | alias imports; Digest32/lineage nominal paths |
| ravel.evidence.v1 | 0.10 | generic `summarize_prefix<8>`; imported nominals |

Deliberately not adopted: Profile 0.13 `!`/`==` boolean operators
(`mncs.core.logic.v1` remains the current authoritative boolean vocabulary
and its header still claims that role — no churn for its own sake);
Profile 0.8 vectors/masks (no lane semantics in RAVEL); Profiles
0.11–0.16 iteration/fs/float/span/view features (no RAVEL use case).

## What changed in RAVEL

1. **Core envelope (Phase 4).** `ravel.core.v1` gains `EvidenceEnvelope`
   (`[Status; 4]`), `envelope_summary()` (authoritative generic fold,
   conflict visible in counts), and `envelope_disposition()` (exact legacy
   GateSet semantics through the fold). Corpus 8 → 16 cases.
2. **Identity migration (Phase 3).** `ravel.identity.v1` embeds every
   `ContentDigest` into stdlib `Digest32`, delegates lineage to
   `mncs.core.lineage.v1` (`Root`/`Successor`/`Conflict`), and adds
   staleness verdicts. Scalar `SnapshotId` conventions remain at module
   boundaries (task/forge/checkpoint migration is recorded as follow-up
   work, not silently completed). Corpus 4 → 16 cases, including stale,
   mismatch, dead, lineage-conflict, and replay negatives.
3. **Evidence envelopes (Phase 6).** New `ravel.evidence.v1`: bounded
   8-lane envelopes with provenance snapshot, fail-closed active counts,
   pass-through governing status, all-PASS `committable` (empty envelope
   commits nothing), visible conflict, advisory asks, freshness binding.
   18 corpus cases, all authority-negative paths covered.
4. **Backend progression (Phase 5).** The scalar-envelope limitation is
   obsolete: all five backends execute every module's composite
   entrypoints with identical per-case expectations. The checker promotes
   C11/LLVM/Cranelift into the execution matrix and asserts
   cross-backend agreement per module.
5. **Tooling repair (Phase 9).** `tools/ravel_mncs_check.py` understands
   the current `source-study` shape (completion status + error-severity
   discriminator instead of bare diagnostics absence), probes 0.10
   capabilities (generics over imported nominals), covers all eleven
   executable modules (cross-verified against the workspace; only
   `ravel.types.v1` excluded by design), and asserts a wrong-nominal-type
   program (`ContentDigest` where `Digest32` is expected) is refused
   (`MNE117`/`MNE133`).
6. **Differential verdict (Phase 7).** No new equivalent scopes: legacy
   `checkpoint.py` is a state codec and `memory/` is
   consolidation/clustering — neither is a semantic twin of the MNCS
   transact/promotion gates, so equivalence is not fabricated. The three
   existing scopes re-verify AGREE (28/28, 0 mismatches); newer semantics
   are classified extension-only with direct corpus-invariant coverage.

## Verification results (bounded local evidence)

`python3 tools/ravel_mncs_check.py mncs-experiments` → overall PASS:
ten modules PASS on all five backends (core 16, loop 13, checkpoint 5,
memory 11, task 5, lifecycle 11, provider 10, budget 8, forge 8,
evidence 18 cases each); `ravel.identity.v1` UNKNOWN with 16/16
expectations met on every backend (retained iteration-exact-resource-cost
and view-range-valid obligations — the same classes the stdlib's own
`equal`/`is_zero` folds retain). Cross-backend agreement holds per
module. Coverage cross-check clean; nominal-type negative refused.
Evidence: `build/mncs-ravel/mncs-experiments.json`.
`python3 tools/ravel_mncs_differential.py` → AGREE, 28/28, 0 mismatches.
Evidence: `build/mncs-ravel/differential.json`.

## Canonical witness state

- Language-side expected fingerprint (stale): `1cc17f37…`.
- Untouched old snapshot under the current toolchain: `346e6342…`
  (deterministic ×3). The drift is toolchain-canonical, not source: the
  type-architecture campaign (semantic Bool, resolved-type invariant,
  typed ABI nominal resolution) changed canonical representation after
  the `f934588` rotation.
- Pre-campaign upstream `ravel.core.v1` (linked Profile 0.6 model):
  `83f0f2b4…` (deterministic ×2). Source delta vs the snapshot:
  Profile 0.5 → 0.6, local `Status`/`dominate` → `use
  mncs.core.status.v1` (same 3×3 join, distinct canonical identity).
- Post-campaign `ravel.core.v1` (Profile 0.10 + generic envelope):
  `2fd0d19d…`. Delta vs pre-campaign: profile header, `EvidenceEnvelope`
  record, `envelope_summary` / `envelope_disposition` /
  `hold_unless_resolved` — the legacy surface is byte-identical.
- Resolution is recorded in the campaign report; no fingerprint was
  blessed without these deltas.

## Language-pressure reconciliation

| Previous pressure (RRE-2) | Standing | Current evidence |
| --- | --- | --- |
| total arithmetic surface | RESOLVED, adopted | saturating intents throughout; obligations discharge |
| stdlib resolution for consumers | RESOLVED, adopted | `MNCS_LIBRARY_PATH` linkage in every module |
| imported types in field positions | RESOLVED, adopted | nominal payloads in task/forge/evidence |
| scalar backends cannot execute composites | RESOLVED by this campaign | 5/5 backends execute all composite entrypoints |
| no boolean negation operator | RESOLVED upstream, not adopted | 0.13 `!` exists; logic lib remains authoritative, kept deliberately |
| no match wildcard | REFRAMED (intended) | exhaustive finite matches by design; `_` exists for integer subjects |
| single-document candidate analysis | HISTORICAL (unverified here) | service roadmap; untouched by this campaign |

New pressures are recorded in the campaign report (none blocking; the
`iteration-exact-resource-cost` UNKNOWN on honest bounded traversals is
carried identically by the stdlib's own folds and is therefore an
observation, not a RAVEL defect).

## Non-claims

All results above are bounded local development observations with honest
PASS/UNKNOWN semantics. They establish no universal equivalence,
conformance, independent evaluation, or promotion. Corpus agreement
across five backends is bounded agreement, not proof of
whole-program equivalence.
