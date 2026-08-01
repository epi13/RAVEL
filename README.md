# RAVEL — Recursive Adaptive Vector Execution Lattice

RAVEL is a machine-native research architecture that treats AI/ML as one combined problem of routing, retrieval, compression, representation, training state, temporal memory, planning, lifecycle, and bounded computation.

Its foundational claim is that a model, memory store, router, trainer, world model, planner, and compute scheduler should not be separate systems. A stored expert should simultaneously be a retrieval key, compressed representation, executable predictor, training shard, transition-memory node, planning destination, lineage object, and measured unit of computation.

Human readability is relocated into contracts, evaluator authority, evidence, provenance, and rollback. The 0.3 split C translation unit is maintained source: no reproducible higher-level generator was included in the repository or reviewed pull-request history.

## RAVEL 0.1 — exact conditional inference

The first capsule generates 256 quantized experts and retrieves 24 candidates per familiar query. A strict lower-bound certificate permits early return only when every excluded expert is provably unable to win. Otherwise execution becomes the complete oracle.

| Workload | Queries | Mismatches | Certified rate | Mean experts | Reduction |
|---|---:|---:|---:|---:|---:|
| Familiar | 100,000 | 0 | 100.000% | 24.000 | 90.625% |
| Uniform control | 25,000 | 0 | 2.236% | 250.812 | 2.026% |

## RAVEL-T 0.2 — recursive training

The current experts build the exact router; routed assignments update the experts; unresolved error ranks overloaded shards; bounded splits compile children; child lineage rebuilds the next router.

| Implementation | Holdout accuracy | Mean experts | Training evaluations |
|---|---:|---:|---:|
| RAVEL-T recursive 8→64 | 100.000% | 8.000 | 4,144,248 |
| Fixed eight-expert | 22.461% | 8.000 | 3,538,944 |
| Flat 64-expert | 100.000% | 64.000 | 87,031,808 |

## RAVEL-U 0.3 — unified architecture

RAVEL-U closes the component gap. One expert population now owns:

- retrieval and exact conditional compute;
- compressed state representation and reconstruction;
- label prediction;
- action-conditioned next-observation prediction;
- temporal-memory graph compilation;
- bounded planning over the learned graph;
- error-driven expert birth;
- replay-backed continual adaptation;
- low-utility child retirement; and
- checkpoint identity and behavioral rollback verification.

The synthetic world contains 64 states, four actions, eight labels, and eight-dimensional observations. Semantic drift changes both observations and labels for 16 states. The frozen model is evaluated before adaptation, then RAVEL proposes 24 drift experts, retires eight low-utility duplicates, rebuilds the router and transition graph, and re-evaluates drift, retention, planning, and checkpoint behavior.

### Unified development result

| Measure | Result |
|---|---:|
| Base holdout accuracy | 96.826% |
| Static model on semantic drift | 71.899% |
| Adapted model on semantic drift | 100.000% |
| Original-task retention after adaptation | 96.704% |
| Adapted transition accuracy | 99.292% |
| Adapted planning target success | 505 / 512 |
| Routed-versus-complete mismatches | 0 |
| Mean routed experts | 8.000 |
| Adaptation births / retirements | 24 / 8 |
| Checkpoint identity and evaluation match | PASS |

The expert is now simultaneously a key, representation, decoder, classifier, world-model fragment, transition node, replay shard, planning node, lineage object, and compute unit. See `ARCHITECTURE_GAPS.md` for what was missing and why raw modality adapters, use policy, protected evaluation, external effects, and promotion authority intentionally remain outside the recursive surface.

The historical `100.000%` adapted drift value above was measured on the same
`adapt_set` used for adaptation. It is an adaptation-training observation, not
an untouched drift-holdout result. Likewise, the historical planning
`exact_goals` field measured goal-expert equivalence rather than exact
world-state equality. RAVEL 0.4 preserves these facts instead of relabeling the
0.3 evidence.

## RAVEL 0.4 — evidence hardening

RAVEL 0.4 repairs assurance rather than expanding the architecture. It adds:

- disjoint base training, base holdout, drift adaptation training, untouched
  drift holdout, original-task retention holdout, and planning inputs;
- eight frozen seeds covering separated, overlapping, noisy, label-drift,
  observation-drift, transition-drift, combined, and ambiguous regimes;
- canonical big-endian Q20 checkpoints with a versioned header and SHA-256
  payload identity instead of raw C memory images;
- complete restored classification, reconstruction, prediction, transition,
  routing, planning, topology, lineage, and reported-metric comparison;
- deliberate field, payload, truncation, append, schema, and substitution
  checkpoint mutations;
- exact-state planning measurements distinct from goal-expert equivalence;
- reconstruction and next-observation prediction gates;
- five bounded baselines, five ablations, negative/adversarial tests, aggregate
  variance, and preserved failures; and
- an ordered, script-generated source manifest and assurance digest.

The frozen 0.4 experiment records development `FAIL`; no seeds, regimes, or
gates were removed to obtain a favorable result. See
`RAVEL_0_4_RESULTS.md` for generated per-trial failures and aggregates, and
`ravel-0.4-assurance-case.json` for the bounded assurance disposition.

## RAVEL 0.5 — adaptive-mechanism correction

RAVEL 0.5 keeps the 0.4 evidence package immutable and corrects the mechanism
and assurance split. The C harness now emits raw integer observations and
integrity facts only. A separate Python evaluator verifies the frozen trial and
partition matrix, derives every metric and hard gate, and rejects executable
verdicts, malformed records, contradictions, and mutations.

Mechanism changes include deterministic stratified replay, anchored base
experts, optional objective-tested births and retirements, eight normalized
residual channels, support-bearing top-two transitions, unknown unsupported
actions, retirement safety checks, and alias-aware belief-set planning.
Comparisons add matched work, expert count, and capacity, while retaining the
0.4 baselines and ablations.

The one-shot 0.5 final validation used 32 fresh trials: four seeds for each of
the eight frozen regime families. Execution integrity is `PASS`; 24 trials
passed and eight failed, so the frozen all-trials development result is
`FAIL`. All separated, overlap, noise, and observation-drift trials passed.
Failures remained in label gain (three trials), transition prediction retention
(one), combined exact planning (one), and ambiguous belief/planning or
efficiency (three). These failures were not used to change the mechanism,
seeds, regimes, or gates.

The candidate improved mean drift-holdout accuracy over the matched-compute
fixed-topology comparison while using fewer mean training evaluations, but the
complete paired Pareto results are mixed. No superiority claim is made. See
`RAVEL_0_5_RESULTS.md`, `RAVEL_0_5_POSTMORTEM.md`, and
`ravel-0.5-assurance-case.json`.

## Run

```bash
make test
make training-check
make unified-check
make 0.4-check
make 0.5-check
```

To rewrite repository-visible development evidence:

```bash
make evidence
make training-evidence
make unified-evidence
make 0.4-evidence
make 0.5-evidence
```

Requirements: a C11 compiler, the C math library, and Make.

## Files

- `ravel.c`, `CONTRACT.md`, `evidence.json` — exact conditional inference;
- `ravel_train.c`, `TRAINING_CONTRACT.md`, `training-*.json` — recursive training;
- `ravel_unified.c` and `ravel_unified/*.inc` — maintained 0.3 split C source;
- `ARCHITECTURE_GAPS.md` — architectural audit and intentional external boundary;
- `UNIFIED_CONTRACT.md` — unified readable authority and gates;
- `unified-preregistration.json` — frozen protocol;
- `unified-evidence.json` — deterministic observations;
- `unified-threat-model.json` — threats and residual UNKNOWNs; and
- `unified-assurance-case.json` — historical bounded non-promotion record;
- `ravel_0_4.c` and `RAVEL_0_4_CONTRACT.md` — hardened maintained execution and
  readable authority;
- `ravel-0.4-preregistration.json` — frozen seeds, regimes, partitions, and gates;
- `ravel-0.4-raw-observations.json`, `ravel-0.4-trial-evidence.json`, and
  `ravel-0.4-negative-evidence.json` — executable raw and derived evidence;
- `ravel-0.4-source-manifest.json` — ordered implementation identity; and
- `ravel-0.4-assurance-case.json` — historical 0.4 non-promotion record;
- `ravel_0_5.c`, `RAVEL_0_5_CONTRACT.md`, and
  `ravel-0.5-preregistration.json` — maintained 0.5 mechanism and frozen
  authority;
- `tools/ravel_0_5_evaluator.py` and `tools/ravel_0_5_evidence.py` —
  independent derivation and deterministic evidence tooling;
- `ravel-0.5-raw-observations.json`, `ravel-0.5-trial-evidence.json`, and
  `ravel-0.5-negative-evidence.json` — raw and independently derived 0.5
  records; and
- `ravel-0.5-source-and-execution-manifest.json` and
  `ravel-0.5-assurance-case.json` — bound build/source identity and current
  bounded non-promotion record; and
- `ravel-0.5-runtime-observations.json` — host-specific, non-normative timing
  observations; canonical comparisons use deterministic operation counts.

## MNCS boundary

- **Human control plane:** intended use, event contract, external authority, limits, gates, and exclusions.
- **Machine execution plane:** expert keys, decoders, classifiers, next-state programs, router, transition graph, topology, replay assignments, and lineage.
- **Evidence plane:** exact-oracle agreement, accuracy, reconstruction, prediction, transition, planning, lifecycle, checkpoint, checksums, and limitations.
- **Development-control plane:** fixed seeds, partitions, birth and retirement budgets, immutable thresholds, and non-promotion fields.
- **Operational-control plane:** complete-scan fallback, checkpoint restoration, model identity, and replacement of maintained execution source.

Historical RAVEL 0.1–0.3 studies recorded favorable development observations.
RAVEL 0.4 records development `FAIL` with zero of eight trials passing. RAVEL
0.5 records development `FAIL` with 24 of 32 trials passing. Formal MNCS and
MNCDS status remain `UNKNOWN`; promotion is unauthorized pending independent
protected real-data evaluation, adversarial continual-learning studies, learned
modality adapters, cross-host reproduction, accelerator and distributed
evidence, and operational release controls.

## Claim boundary

RAVEL is a bounded deterministic research study with both favorable and
unfavorable results. It does not establish general intelligence,
foundation-model performance, language or multimodal generation, causal
reasoning, real-data generalization, production safety, or formal conformance.

## Origin

The name, architecture, algorithms, and initial implementations were created by **GPT-5.6 Thinking** in response to Alexander Collamore's challenge to design an AI/ML foundation that fully embraces Machine-Native Complexity. Alexander Collamore is the repository steward.
