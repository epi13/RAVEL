# MNCS-native RAVEL — development evidence record (RRE-1)

Date: 2026-08-24. Scope: first full conversion cycle of RAVEL's reasoning core
into the MNCS language. This is a development record: local bounded evidence
only, retained with exact identities so it can be re-executed and challenged.

## Environment identities

- mncs-language `main` at merge of PRs #61/#62/#63 (compiler identity below is
  content-derived per run):
  - compiler: `mncs:compiler:compiler:f862227638ca7fbc716123d8378cddfef4f76a9ef10ab0e99cc791e65207e45d`
- mncs-language-service: Phase 4 candidate analysis merged to main (PR #3).
- Host: local Linux development machine; no remote execution.

## Language defects found by the conversion — fixed upstream

1. **Profile 0.5 block-opener collision** (`mncs-language` PR #61, commit
   cc2efea). Any `identifier {` sequence was parsed as a record literal, so
   `match name { … }`, `if flag { … }`, and record-initialized
   `iterate … carrying x: T = T { … } { … }` — the bread and butter of RAVEL
   disposition logic — failed to parse under profile 0.5. Fixed with bounded
   lookahead in `primary()`; regression fixture
   `examples/source/profile05-branch-on-names.mncs` + 9-case corpus + parser
   unit test.
2. **Record-typed call arguments rejected by the body reference executor**
   (same PR). `value_matches_type`/`normalize_value` had no Record arm; SSA,
   both reference executors' SSA side, and backends accepted what the body
   executor refused. Records now validate recursively against declared field
   types (nested records included).
3. **Record observations rejected in layered agreement** (PR #63).
   `values_agree` compared only scalar observations; a program returning a
   record could never pass layered validation. Records now compare
   field-by-field recursively.

## Service capabilities added for RAVEL

- **Phase 4 candidate analysis** (`mncs-language-service` PR #3): isolated
  candidate snapshots, language-owned semantic deltas
  (`Program::semantic_diff`), obligation deltas from authoritative generation,
  stale-evidence detection via `Program::invalidation_from`, fail-closed on
  broken baselines/non-elaborating/identical candidates; read-only MCP tool
  `analyze_candidate`. Demonstrated live against `ravel_checkpoint.mncs`: a
  single-token sign change produced exact changed-identity fingerprints
  (block/body/function), unchanged obligation counts, and correct diagnostics
  deltas without touching the workspace baseline.
- Dependency pins moved from the reviewed feature branch to `mncs-language`
  `main`.

## Experiment records

All five modules: backend `mncs-research-bytecode`, translation validator
`backend-lowering-bounded-agreement` = PASS on every module.

| Module | Source artifact identity | Result identity | Cases | Overall |
| --- | --- | --- | --- | --- |
| ravel.core.v1 | `mncs:source:artifact:49c3ae19db94d77622bca5b578414dd7edc40ffa2c24a56941d668f22c0fbb29` | `mncs:language:experiment:result:42382f998449aacf758e6a57ef66828e11b88ce9f22e464a6850a4217d5628ba` | 17/17 met | PASS |
| ravel.loop.v1 | `mncs:source:artifact:2fcd30c768cb231e487c3a111b6907cdd33fdd42318f470c315a5366947101f8` | `mncs:language:experiment:result:3aa0251564615a32607691c1d69c083c5ddd2c153e08c039313679bf281ecc29` | 22/22 met | PASS |
| ravel.checkpoint.v1 | `mncs:source:artifact:3f7a94512e3b7b051ba7db3a5393644fc683d2ed9671e99a5b1f423e017e8f80` | `mncs:language:experiment:result:e7c47b0c33eee3bec6b6ae3017cd20635435eaa499e653f576e2e0b6334b92c3` | 5/5 met | UNKNOWN |
| ravel.memory.v1 | `mncs:source:artifact:9a201fb988c1f2aac8291c1d583adabd3057b2dc13438f3232885dcc80308510` | `mncs:language:experiment:result:ec112263c832a3bfe37b2d95acac3fb6ce7dece54f1fdd79bc6ce43d4f6cd1a6` | 11/11 met | UNKNOWN |
| ravel.task.v1 | `mncs:source:artifact:acb3842a3c34e9d2c65f91693242f1e0853d8818c67899dbeed1675460676026` | `mncs:language:experiment:result:1d964acdf7edd1bd2a053f137707fccfb59df7aa8c206a3cd005e87cf94c649e` | 5/5 met | PASS |

UNKNOWN overall on checkpoint/memory comes from honest unresolved
integer-overflow exact-cost obligations on small i64 arithmetic; every corpus
case met its expectation and layered agreement passed. Results are
deterministic: re-running the same source/corpus/compiler reproduces identical
result identities (verified across independent invocations).

## Legacy differential mapping

No executable differential harness against legacy Python/Rust RAVEL exists yet
(open obligation). What is encoded now is the distilled behavioral contract,
case by case:

| MNCS-native behavior (corpus case) | Legacy reference |
| --- | --- |
| status dominance lattice, FAIL ⊒ UNKNOWN ⊒ PASS (`dominate-*`) | README "Status integrity"; legacy evaluator combine rules |
| commit requires all hard gates PASS (`evaluate-commit`, `disposition-commit`, `tx-commit`) | RAVEL 0.6 preregistration policy gates |
| UNKNOWN never becomes PASS (`combine-unknown-survives`, `disposition-hold`, `attribute-*` UNKNOWN rows) | AUTHORITY_MODEL.md "Separation of confidence and status" |
| rollback preserves baseline + retains negative experience (`tx-rollback-on-failed-gate`, `tx-hold-on-unknown-gate`) | `tools/ravel_0_6_transaction_surface.py`; `tests/test_ravel_0_6_transaction.py` |
| orphan candidate refuses (`tx-refuses-orphan-candidate`) | candidate isolation rules in the 0.6 transaction surface |
| counterexample survives later success (`absorb-success-after-failure-retains-negative`) | KNOWLEDGE_MODEL.md counterexample immutability; negative-memory tests |
| out-of-scope transfer refused as UNTESTED (`transfer-out-of-scope-untested`) | transfer-test discipline in the knowledge model |
| selection partition protected, cannot invent authority (`select-refuses-dirty-fallback`, `select-no-strategy-out-of-scope`) | strategy-selection partition notes in ARCHITECTURE.md |
| task refuses drifted snapshot (`refuse-stale`) | frozen-identity requirements in the 0.6 Fabric observation schema |

## Friction log (language pressure discovered)

1. **No boolean operators** (`&&`, `||`): every conjunction needs helper
   functions or nested ifs. Smallest fix: boolean operator support in source
   profiles; pressure documented instead of ad-hoc workarounds beyond two
   explicit helpers.
2. **No finite equality**: enum discrimination requires match even for simple
   predicates; fine for exhaustiveness but verbose for guards.
3. **Match arm patterns are bare variant names only**: qualified patterns
   (`Type.VARIANT =>`) are rejected; acceptable now, worth revisiting when two
   enums share variant names.
4. **`next` transition must be the final statement** of an iteration body:
   conditional state transitions require extraction into total step functions.
   This forced a *better* factoring here (explicit `tally_step`), but complex
   loops will need conditional transitions eventually.
5. **No strings/bounded collections**: identities are opaque i64 halves bound
   to real digests at host boundaries; evidence sets have fixed arity. The next
   genuine language need after records is bounded collections (typed lists)
   with canonical iteration.
6. **Checked-arithmetic obligations make any non-wrapping arithmetic module
   overall-UNKNOWN** even when all cases pass. Honest, but a widening-intent
   expression (`add.widen<i64>`) would resolve it truthfully.

## Next executable steps

1. Host-side bridge crate: build `TaskContext` values from live
   `mncs-language-service` snapshots and emit them as experiment inputs.
2. Bounded collections in the language (driven by evidence-set aggregation).
3. WASM record realization through block parameters (removes CGN302 refusals
   for checkpoint/loop modules).
4. Executable differential harness vs. legacy Rust knowledge-store flows.
