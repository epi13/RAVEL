# RAVEL — Recursive Adaptive Vector Execution Lattice

RAVEL is a machine-native research architecture that treats AI/ML inference as one combined problem of **routing, retrieval, compression, and bounded computation**.

Its foundational claim is that a model, memory store, router, and compute scheduler should not be four separate systems. A stored unit should simultaneously be:

- a compressed region of behavior;
- a retrieval target;
- an executable expert;
- a routing destination; and
- a measured unit of computational cost.

The long-term system records successful inference traces, compiles repeated traces into compact executable kernels, places those kernels into a generated routing lattice, and retires kernels that become dominated on quality, cost, or coverage. Familiar requests collapse into cheap retrieval-plus-execution. Unfamiliar requests automatically spend more compute.

## Epoch-1 execution capsule

The first mechanism proof contains 256 generated quantized experts. A query is routed into one of 256 lattice cells. The cell retrieves 24 candidate experts and carries a mathematical lower bound for every excluded expert.

The candidate returns early only when the best routed expert is **strictly closer than any excluded expert could possibly be**. Otherwise it scans the excluded experts and becomes the complete oracle. Ties and uncertainty therefore fall back rather than being promoted to success.

```text
query
  -> generated lattice cell
  -> retrieve 24 compressed experts
  -> execute candidates
  -> exact lower-bound certificate
       PASS: return
       UNKNOWN: scan excluded experts
```

## Initial development result

The checked-in capsule produced:

| Workload | Queries | Mismatches | Certified rate | Mean experts | Evaluation reduction |
|---|---:|---:|---:|---:|---:|
| Familiar, near stored experts | 100,000 | 0 | 100.000% | 24.000 | 90.625% |
| Uniform control | 25,000 | 0 | 2.236% | 250.812 | 2.026% |

The control result is intentional: unfamiliar traffic receives nearly full computation because the shortcut cannot be justified.

## Run

```bash
make test
make evidence
```

Requirements: a C11 compiler and Make.

## MNCS boundary

- **Human control plane:** this README, `CONTRACT.md`, exact fallback, benefit thresholds, and exclusions.
- **Machine execution plane:** generated expert vectors and routing lattice.
- **Evidence plane:** paired candidate/oracle workloads and exact mismatch counts.
- **Development-control plane:** fixed generator seed, frozen constants, and preregistered gates.
- **Operational-control plane:** the complete full-scan oracle remains the rollback implementation.

The local experiment records a development `PASS`. Formal MNCS and MNCDS status remain `UNKNOWN` pending protected workloads, independent evaluation, cross-host reproduction, legitimate learned baselines, and lifecycle evidence.

## Claim boundary

RAVEL does not establish a solution to intelligence, generalization, training, or production inference. It demonstrates one foundational mechanism: exact conditional compute over a generated compressed expert lattice.

## Origin

The name, architecture, algorithm, repository setup, and initial implementation were created by **GPT-5.6 Thinking** in response to Alexander Collamore's challenge to design an AI/ML foundation that fully embraces Machine-Native Complexity. Alexander Collamore is the repository steward.

A fuller standalone repository package includes the separated generator, API, tests, threat model, assurance case, and generated artifacts.