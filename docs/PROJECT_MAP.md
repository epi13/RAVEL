# RAVEL project map

RAVEL is organized by evidence role and research epoch. The parent directory is
partly flat because historical evidence binds exact paths, filenames, ordering,
and digests. This guide provides logical grouping without relocating frozen
artifacts.

## 1. Landing and cross-version orientation

| File | Purpose |
|---|---|
| `README.md` | Main entry point, status summary, commands, and claim boundary |
| `docs/README.md` | Documentation hub |
| `docs/VERSION_HISTORY.md` | Cross-version development history |
| `docs/EVIDENCE_GUIDE.md` | Evidence-layer and claim interpretation |
| `ARCHITECTURE_GAPS.md` | Why 0.3 unified previously separate mechanism roles and what remained external |

## 2. Mechanism implementations

| Epoch | Implementation |
|---|---|
| 0.1 | `ravel.c` |
| 0.2 | `ravel_train.c` |
| 0.3 | `ravel_unified.c` plus `ravel_unified/*.inc` |
| 0.4 | `ravel_0_4.c` |
| 0.5 | `ravel_0_5.c` |
| 0.6 | Reproducible development source derived by `tools/ravel_0_6_seed_candidate.py`; no selected or final implementation is claimed |

Generated binaries such as `ravel`, `ravel_train`, `ravel_unified_bin`,
`ravel_0_4_bin`, and `ravel_0_5_bin` are build outputs and are removed by the
local clean targets.

## 3. Readable behavioral authority

| Epoch | Contract or authority |
|---|---|
| 0.1 | `CONTRACT.md` |
| 0.2 | `TRAINING_CONTRACT.md` |
| 0.3 | `UNIFIED_CONTRACT.md` |
| 0.4 | `RAVEL_0_4_CONTRACT.md` |
| 0.5 | `RAVEL_0_5_CONTRACT.md` |
| 0.6 | `RAVEL_0_6_SCOPE.md` and `RAVEL_0_6_PREREGISTRATION.md` |

Contracts explain expected behavior, limits, gates, and exclusions. They are not
substitutes for raw observations or source identity.

## 4. Protocol and preregistration

Common protocol files include:

- `unified-preregistration.json` for the historical unified study;
- `ravel-0.4-preregistration.json` for the frozen 0.4 matrix;
- `ravel-0.5-preregistration.json` for the frozen 0.5 matrix; and
- `ravel-0.6-preregistration.json` for the new preregistered epoch.

The 0.6 support set also includes:

- `ravel-0.6-threat-model.json`;
- `ravel-0.6-development-record.json`;
- `ravel-0.6-limitations.md`; and
- `RAVEL_0_6_NEXT_STEPS.md`.

Preregistration files define what may be changed, which partitions and seeds are
permitted, how candidates are identified, and how results are derived.

## 5. Raw observations and derived evidence

### Historical studies

- `evidence.json` and `evidence-actual.json` — 0.1 expected and local actual
  output.
- `training-*.json` — 0.2 protocol and evidence records.
- `unified-evidence.json` — deterministic 0.3 observations.
- `unified-threat-model.json` and `unified-assurance-case.json` — historical
  threats and bounded disposition.

### RAVEL 0.4

- `ravel-0.4-raw-observations.json` — direct executable output;
- `ravel-0.4-trial-evidence.json` — derived per-trial evidence;
- `ravel-0.4-negative-evidence.json` — mutation and adversarial evidence;
- `RAVEL_0_4_RESULTS.md` — generated human-readable results; and
- `ravel-0.4-assurance-case.json` — bounded non-promotion disposition.

### RAVEL 0.5

- `ravel-0.5-raw-observations.json` — direct executable output;
- `ravel-0.5-trial-evidence.json` — evaluator-derived trial evidence;
- `ravel-0.5-negative-evidence.json` — evaluator and mutation evidence;
- `ravel-0.5-runtime-observations.json` — host-specific, non-normative timing;
- `RAVEL_0_5_RESULTS.md` — generated human-readable results;
- `RAVEL_0_5_POSTMORTEM.md` — retained failure analysis; and
- `ravel-0.5-assurance-case.json` — bounded non-promotion disposition.

Read [EVIDENCE_GUIDE.md](EVIDENCE_GUIDE.md) before comparing these layers.

## 6. Source and execution identity

| Epoch | Identity records |
|---|---|
| 0.4 | `ravel-0.4-source-manifest-spec.json` and `ravel-0.4-source-manifest.json` |
| 0.5 | `ravel-0.5-source-manifest-spec.json` and `ravel-0.5-source-and-execution-manifest.json` |

Digest tools under `tools/` validate ordered source identity and assurance-case
bindings. These records are why appearance-only file moves can be semantically
material.

## 7. Evaluators and support tooling

See [`../tools/README.md`](../tools/README.md) for script-level detail.

The main categories are:

- evidence generation and verification;
- independent metric and gate derivation;
- source and execution digest verification;
- runtime observation capture;
- mutation and negative testing; and
- bounded 0.6 candidate source derivation.

## 8. Build and verification entry points

The local `Makefile` exposes version-specific targets. The repository root
`Makefile` forwards the most important checks under names such as:

- `ravel-test`;
- `ravel-training-check`;
- `ravel-unified-check`;
- `ravel-0.4-check`; and
- `ravel-0.5-check`.

Use verification targets before any target that rewrites evidence.

## 9. Where new work belongs

- Cross-version explanation or navigation: `docs/`.
- Evaluator, digest, mutation, or derivation script: `tools/`.
- New epoch source, contract, preregistration, and evidence: use a clearly
  versioned identity and document the complete lifecycle before adding files.
- Historical frozen artifacts: do not rename, regroup, or rewrite merely for
  visual consistency.
