# RAVEL — Recursive Adaptive Vector Execution Lattice

RAVEL is a machine-native research architecture that treats AI/ML as one combined problem of routing, retrieval, compression, representation, training state, temporal memory, planning, lifecycle, and bounded computation.

Its foundational claim is that a model, memory store, router, trainer, world model, planner, and compute scheduler should not be separate systems. A stored expert should simultaneously be a retrieval key, compressed representation, executable predictor, training shard, transition-memory node, planning destination, lineage object, and measured unit of computation.

Human readability is relocated into contracts, evaluator authority, evidence, regeneration, and rollback. The generated execution plane is expected to be replaced as a unit rather than routinely hand-maintained.

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

## Run

```bash
make test
make training-check
make unified-check
```

To rewrite repository-visible development evidence:

```bash
make evidence
make training-evidence
make unified-evidence
```

Requirements: a C11 compiler, the C math library, and Make.

## Files

- `ravel.c`, `CONTRACT.md`, `evidence.json` — exact conditional inference;
- `ravel_train.c`, `TRAINING_CONTRACT.md`, `training-*.json` — recursive training;
- `ravel_unified.c` and `ravel_unified/*.inc` — generated unified execution shards;
- `ARCHITECTURE_GAPS.md` — architectural audit and intentional external boundary;
- `UNIFIED_CONTRACT.md` — unified readable authority and gates;
- `unified-preregistration.json` — frozen protocol;
- `unified-evidence.json` — deterministic observations;
- `unified-threat-model.json` — threats and residual UNKNOWNs; and
- `unified-assurance-case.json` — bounded non-promotion record.

## MNCS boundary

- **Human control plane:** intended use, event contract, external authority, limits, gates, and exclusions.
- **Machine execution plane:** expert keys, decoders, classifiers, next-state programs, router, transition graph, topology, replay assignments, and lineage.
- **Evidence plane:** exact-oracle agreement, accuracy, reconstruction, prediction, transition, planning, lifecycle, checkpoint, checksums, and limitations.
- **Development-control plane:** fixed seeds, partitions, birth and retirement budgets, immutable thresholds, and non-promotion fields.
- **Operational-control plane:** complete-scan fallback, checkpoint restoration, model identity, and replacement of the generated execution shards.

The repository-visible studies record development `PASS`. Formal MNCS and MNCDS status remain `UNKNOWN`; promotion is unauthorized pending independent protected real-data evaluation, adversarial continual-learning studies, learned modality adapters, cross-host reproduction, accelerator and distributed evidence, and operational release controls.

## Claim boundary

RAVEL-U is a favorable deterministic mechanism proof. It does not establish general intelligence, foundation-model performance, language or multimodal generation, causal reasoning, real-data generalization, production safety, or formal conformance.

## Origin

The name, architecture, algorithms, and initial implementations were created by **GPT-5.6 Thinking** in response to Alexander Collamore's challenge to design an AI/ML foundation that fully embraces Machine-Native Complexity. Alexander Collamore is the repository steward.
