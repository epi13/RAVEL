# RAVEL

**Adaptive learning, reasoning, and evidence orchestration for machine-native software engineering.**

RAVEL — the **Recursive Adaptive Vector Execution Lattice** — is an experimental intelligence layer for evidence-driven software development. It coordinates bounded tools and verifiers, interprets their results, records validated experience, and uses that experience to improve later decisions.

RAVEL operates beneath the technical authority of the Machine-Native Complexity Standard (MNCS) and the Machine-Native Complexity Development Standard (MNCDS). It is not intended to replace a language model, compiler, static analyzer, test framework, or the MNCS Forge. Its role is to decide what evidence should be gathered, what action should follow, and what experience should be retained for later use without redefining the governing status of that evidence.

> **Project status:** RAVEL is research software. Historical RAVEL 0.4 and 0.5 results remain development `FAIL`; RAVEL 0.6 candidate-001 now has a reproducible build, an integrated development transaction path, behavioral fixtures, modular Python surfaces, and lifecycle scaffolding. It has not been frozen, selection-evaluated, independently evaluated, or promoted. Formal MNCS/MNCDS conformance, independent attestation, protected custody, production safety, and general recursive self-improvement remain `UNKNOWN`.

## Place in the MNCS ecosystem

| Component | Primary responsibility |
|---|---|
| **MNCS** | Ultimate technical authority for machine-native contracts, evidence, status semantics, conformance, and claim boundaries |
| **MNCDS** | Operationalizes MNCS authority for decomposition, candidate lifecycles, evidence flow, and machine-directed development |
| **Forge** | Executes bounded MNCS/MNCDS-governed compilers, analyzers, tests, micro-verifiers, and evidence collection |
| **RAVEL** | Selects, combines, remembers, and learns from bounded evidence without redefining its governing status |
| **Agent/model** | Produces plans, code, hypotheses, explanations, and candidate repairs |

A useful conceptual flow is:

```text
MNCS: technical authority, contracts, evidence semantics, status
                              |
                              v
MNCDS: development structure and operational governance
                              |
                              v
agent/model -> RAVEL -> Forge -> compiler/runtime/analyzer/environment
 candidate     strategy  bounded           observations and witnesses
 generation    memory    verification
```

A compact statement is:

> **MNCS defines authority. MNCDS operationalizes it. Forge executes it. RAVEL reasons and learns beneath it.**

Forge answers: **What can be established about this candidate under the governing contract right now?**

RAVEL answers: **What should be checked next, what should change, and what experience should guide the next action?**

See [`docs/AUTHORITY_MODEL.md`](docs/AUTHORITY_MODEL.md) for the full authority boundary.

## Learning loop

RAVEL treats learning as structured, validated experience rather than an automatic model-weight update:

```text
context
  -> hypothesis
  -> bounded action or intervention
  -> Forge evidence
  -> MNCS/MNCDS-governed disposition
  -> causal attribution
  -> provisional principle
  -> transfer test
  -> reusable strategy
```

Failed interventions, rejected hypotheses, regressions, abstentions, and counterexamples are retained as first-class negative knowledge. A successful result does not automatically become a general rule, and RAVEL confidence cannot convert `UNKNOWN` into `PASS`.

## Knowledge model

RAVEL separates at least five memory classes:

- **Episodic:** what happened in a bounded context.
- **Causal:** competing explanations, probes, interventions, and attribution.
- **Semantic:** provisional principles supported across attributed episodes.
- **Procedural:** reusable strategies with triggers, preconditions, and failure modes.
- **Negative:** failed repairs, rejected hypotheses, regressions, and prohibited reuse contexts.

Embeddings may assist retrieval, but they are not the authoritative knowledge representation. Reusable knowledge must retain identity, provenance, scope, falsifiers, counterexamples, evaluator identity, governing MNCS/MNCDS contracts, and formal status distinctions.

RAVEL memory is advisory. It may influence proposals and evidence requests, but only MNCS/MNCDS-governed evidence may establish the status and permitted use of retained experience.

See [`docs/KNOWLEDGE_MODEL.md`](docs/KNOWLEDGE_MODEL.md) for the proposed storage architecture.

## Architectural principles

1. **MNCS/MNCDS remains authoritative.** RAVEL, Forge providers, agents, and memory records cannot redefine governing contracts, evidence semantics, or status.
2. **Raw evidence remains unchanged.** RAVEL may interpret evidence but cannot rewrite verifier observations or convert `UNKNOWN` into `PASS`.
3. **Evaluation remains external to the candidate.** A candidate cannot promote itself by changing its evaluator, gates, partitions, or custody rules.
4. **Predictions precede outcomes.** Expected effects and acceptable regressions are recorded before evaluation.
5. **Knowledge remains scoped.** Local success does not imply global transfer.
6. **Negative memory is preserved.** Failure records are not discarded merely because a later candidate succeeds.
7. **RAVEL itself is evaluated.** Routing and adaptation policies compete under equal budgets and immutable governing evaluation.
8. **Private chain-of-thought is not a dependency.** Stored records contain compact claims, alternatives, witnesses, and outcomes rather than hidden reasoning transcripts.

## Repository extraction

RAVEL originated inside [`epi13/machine-native-complexity-standard`](https://github.com/epi13/machine-native-complexity-standard). The standalone repository should preserve that provenance and the identity of frozen evidence.

The recommended extraction is history-preserving rather than a manual file copy. See [`docs/MIGRATION.md`](docs/MIGRATION.md) for the exact boundary, source commit, and migration sequence.

## Current repository plan

1. Establish the standalone architecture, authority model, and knowledge model.
2. Extract `case-studies/ravel/` with its Git history and preserve frozen artifact identities.
3. Import the recursive-architecture and recursive-experience research tracks that currently live outside the case-study directory.
4. Add standalone CI and repair repository-root assumptions.
5. Update MNCS to reference RAVEL as a sibling project without deleting historical evidence prematurely.
6. Develop the Forge interface and MNCS/MNCDS-governed evidence and knowledge schemas before adding broad autonomy.

The current 0.6 implementation status is recorded in
[`ravel_versions/0.6/RAVEL_0_6_IMPLEMENTATION_STATUS.md`](ravel_versions/0.6/RAVEL_0_6_IMPLEMENTATION_STATUS.md).
Optional provider/resource protocols in `src/ravel/providers.py` and
`src/ravel/resources.py` record scoped execution observations without claiming
algorithmic superiority. The bounded component surfaces in `src/ravel/world.py`,
`src/ravel/transition.py`, `src/ravel/planning.py`, `src/ravel/checkpoint.py`,
and `src/ravel/mechanism_state.py` provide deterministic provider substitution
and checkpoint fixtures; they do not replace the historical 0.5 source.

## Non-goals

RAVEL is not currently claiming:

- authority to redefine MNCS or MNCDS;
- general intelligence or autonomous scientific discovery;
- unrestricted recursive self-improvement;
- foundation-model training or replacement;
- production safety or certification;
- independent evaluation or protected evidence custody;
- automatic promotion from a successful development result; or
- that a graph, vector index, or larger context window alone constitutes learning.

## Origin

RAVEL was initiated by Alexander Collamore as part of the Machine-Native Complexity project family. Its early implementation and evidence history remain in the MNCS repository until the history-preserving extraction is completed and verified.
