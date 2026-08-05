# RAVEL — Recursive Adaptive Vector Execution Lattice

RAVEL is a machine-native research architecture that treats routing, retrieval,
representation, training state, temporal memory, planning, lifecycle, and bounded
computation as one connected mechanism.

This directory contains several historical and active research epochs. The files
are intentionally evidence-heavy, and some frozen artifacts must retain their
existing paths and identities. The navigation layer below separates the project
by purpose without rewriting or relocating those historical records.

> **Current status:** RAVEL 0.4 and 0.5 retain development `FAIL` results. RAVEL
> 0.6 is preregistered and has a reproducible candidate-001 derivation, but it has
> not been selected, finally evaluated, independently attested, or authorized for
> promotion. Formal MNCS and MNCDS status remain `UNKNOWN`.

## Start here

| Goal | Entry point |
|---|---|
| Understand the project at a glance | [Version history](docs/VERSION_HISTORY.md) |
| Find source, contracts, evidence, and plans | [Project map](docs/PROJECT_MAP.md) |
| Understand what each evidence file proves | [Evidence guide](docs/EVIDENCE_GUIDE.md) |
| Browse the RAVEL documentation set | [Documentation hub](docs/README.md) |
| Understand evaluator and generation scripts | [Tooling guide](tools/README.md) |
| Review the architectural idea and exclusions | [Architecture gaps](ARCHITECTURE_GAPS.md) |
| Continue bounded 0.6 development | [RAVEL 0.6 next steps](RAVEL_0_6_NEXT_STEPS.md) |

## Project shape

```text
case-studies/ravel/
├── README.md                 # landing page
├── docs/                     # human navigation and explanatory guides
├── tools/                    # evaluators, evidence builders, and digest tools
├── ravel_unified/            # maintained 0.3 split implementation units
├── ravel*.c                  # versioned mechanism implementations
├── *_CONTRACT.md             # readable behavioral authority
├── RAVEL_*                   # results, postmortems, scopes, and plans
├── ravel-*.json              # protocols, observations, manifests, and assurance
└── Makefile                  # local build, verification, and evidence targets
```

The top-level RAVEL directory remains partly flat on purpose. Versioned source,
preregistrations, observations, manifests, and assurance records are linked by
exact filenames and digests. Moving them merely for appearance could invalidate
historical identity or make prior evidence harder to reproduce. New explanatory
documentation belongs under `docs/`; executable support tooling belongs under
`tools/`.

## Epoch status

| Epoch | Primary purpose | Preserved status |
|---|---|---|
| RAVEL 0.1 | Exact conditional inference | Favorable bounded development observation |
| RAVEL-T 0.2 | Recursive training and expert birth | Favorable bounded development observation |
| RAVEL-U 0.3 | Unified expert architecture | Favorable historical observations with documented evaluation caveats |
| RAVEL 0.4 | Evidence and checkpoint hardening | Development `FAIL` — 0 of 8 frozen trials passed all gates |
| RAVEL 0.5 | Mechanism correction and evaluator separation | Development `FAIL` — 24 of 32 trials passed; all-trials gate failed |
| RAVEL 0.6 | Retention-constrained adaptation epoch | Preregistered; candidate-001 derivation prepared; selection and final evaluation `UNKNOWN` |

Detailed results, limitations, and links are collected in
[docs/VERSION_HISTORY.md](docs/VERSION_HISTORY.md).

## Common verification commands

From the repository root:

```bash
make ravel-test
make ravel-training-check
make ravel-unified-check
make ravel-0.4-check
make ravel-0.5-check
```

From this directory:

```bash
make all
make 0.4-compiler-matrix
make 0.4-sanitizers
make 0.5-negative-test
make 0.5-manifest-negative-test
make 0.5-compiler-matrix
make 0.5-sanitizers
```

Commands ending in `-check`, `-test`, `-compiler-matrix`, or `-sanitizers` are
verification-oriented. Commands ending in `-evidence` or `-runtime` can rewrite
repository-visible development records; review [tools/README.md](tools/README.md)
before using them.

Requirements vary by epoch but generally include a C11 compiler, Python 3, the C
math library, and Make.

## Reading order for each epoch

For version 0.4 or later, use this order:

1. scope or preregistration;
2. readable contract;
3. maintained or generated mechanism source;
4. raw observations;
5. evaluator-derived trial and negative evidence;
6. source/execution manifest;
7. assurance case;
8. generated results and postmortem;
9. next-epoch development plan.

This order keeps protocol, implementation, observations, interpretation, and
claim authority separate.

## MNCS boundary

- **Human control plane:** intended use, event contract, external authority,
  limits, gates, and exclusions.
- **Machine execution plane:** expert keys, decoders, classifiers, next-state
  programs, router, transition graph, topology, replay assignments, and lineage.
- **Evidence plane:** oracle agreement, accuracy, reconstruction, prediction,
  transition, planning, lifecycle, checkpoint, checksums, and limitations.
- **Development-control plane:** fixed seeds, partitions, candidate limits,
  immutable thresholds, and non-promotion fields.
- **Operational-control plane:** complete-scan fallback, checkpoint restoration,
  model identity, source replacement, and rollback behavior.

## Claim boundary

RAVEL is a bounded deterministic research study with both favorable and
unfavorable results. It does not establish general intelligence, foundation-model
performance, language or multimodal generation, causal reasoning, real-data
generalization, production safety, independent evaluation, protected custody, or
formal conformance.

Historical RAVEL 0.1–0.3 studies recorded favorable development observations.
RAVEL 0.4 and 0.5 preserve failed frozen development outcomes. RAVEL 0.6 remains
a development epoch. Promotion is unauthorized pending appropriate external,
protected, and independently evaluated evidence.

## Origin

The name, architecture, algorithms, and initial implementations were created by
**GPT-5.6 Thinking** in response to Alexander Collamore's challenge to design an
AI/ML foundation that fully embraces Machine-Native Complexity. Alexander
Collamore is the repository steward.
