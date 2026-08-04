# RAVEL

**Adaptive learning, reasoning, and evidence orchestration for machine-native software engineering.**

RAVEL — the **Recursive Adaptive Vector Execution Lattice** — is an experimental intelligence layer for evidence-driven software development. It coordinates bounded tools and verifiers, interprets their results, records validated experience, and uses that experience to improve later decisions.

RAVEL is not intended to replace a language model, compiler, static analyzer, test framework, or the MNCS Forge. Its role is to decide what evidence should be gathered, what the evidence means within a declared scope, what action should follow, and what knowledge is safe to retain for reuse.

> **Project status:** RAVEL is research software. Historical RAVEL 0.4 and 0.5 results remain development `FAIL`; RAVEL 0.6 is preregistered but not finally evaluated or promoted. Formal MNCS/MNCDS conformance, independent attestation, protected custody, production safety, and general recursive self-improvement remain `UNKNOWN`.

## Place in the MNCS ecosystem

| Component | Primary responsibility |
|---|---|
| **MNCS** | Defines machine-native contracts, evidence, status, and complexity boundaries |
| **MNCDS** | Applies those ideas to decomposition and machine-directed development structure |
| **Forge** | Executes compilers, analyzers, tests, micro-verifiers, and evidence collection |
| **RAVEL** | Selects, interprets, combines, remembers, and learns from bounded evidence |
| **Agent/model** | Produces plans, code, hypotheses, explanations, and candidate repairs |

A useful conceptual flow is:

```text
agent or model
      |
      v
RAVEL: strategy, memory, evidence routing, adaptation
      |
      v
Forge: deterministic tools, micro-verifiers, tests, witnesses
      |
      v
compiler / runtime / analyzer / environment evidence
```

Forge answers: **What can be established about this candidate right now?**

RAVEL answers: **What should be checked next, what should change, and what can safely be learned from the result?**

## Learning loop

RAVEL treats learning as structured, validated experience rather than an automatic model-weight update:

```text
context
  -> hypothesis
  -> bounded action or intervention
  -> Forge evidence
  -> evaluator disposition
  -> causal attribution
  -> provisional principle
  -> transfer test
  -> reusable strategy
```

Failed interventions, rejected hypotheses, regressions, abstentions, and counterexamples are retained as first-class negative knowledge. A successful result does not automatically become a general rule.

## Knowledge model

RAVEL separates at least five memory classes:

- **Episodic:** what happened in a bounded context.
- **Causal:** competing explanations, probes, interventions, and attribution.
- **Semantic:** provisional principles supported across attributed episodes.
- **Procedural:** reusable strategies with triggers, preconditions, and failure modes.
- **Negative:** failed repairs, rejected hypotheses, regressions, and prohibited reuse contexts.

Embeddings may assist retrieval, but they are not the authoritative knowledge representation. Reusable knowledge must retain identity, provenance, scope, falsifiers, counterexamples, evaluator authority, and promotion status.

See [`docs/KNOWLEDGE_MODEL.md`](docs/KNOWLEDGE_MODEL.md) for the proposed storage architecture.

## Architectural principles

1. **Evidence remains authoritative.** RAVEL may interpret evidence but cannot rewrite verifier results.
2. **Evaluation remains external to the candidate.** A candidate cannot promote itself by changing its evaluator, gates, partitions, or custody rules.
3. **Predictions precede outcomes.** Expected effects and acceptable regressions are recorded before evaluation.
4. **Knowledge remains scoped.** Local success does not imply global transfer.
5. **Negative memory is preserved.** Failure records are not discarded merely because a later candidate succeeds.
6. **RAVEL itself is evaluated.** Routing and adaptation policies compete under equal budgets and immutable evaluation.
7. **Private chain-of-thought is not a dependency.** Stored records contain compact claims, alternatives, witnesses, and outcomes rather than hidden reasoning transcripts.

## Repository extraction

RAVEL originated inside [`epi13/machine-native-complexity-standard`](https://github.com/epi13/machine-native-complexity-standard). The standalone repository should preserve that provenance and the identity of frozen evidence.

The recommended extraction is history-preserving rather than a manual file copy. See [`MIGRATION.md`](MIGRATION.md) for the exact boundary, source commit, and migration sequence.

## Current repository plan

1. Establish the standalone architecture and knowledge model.
2. Extract `case-studies/ravel/` with its Git history and preserve frozen artifact identities.
3. Import the recursive-architecture and recursive-experience research tracks that currently live outside the case-study directory.
4. Add standalone CI and repair repository-root assumptions.
5. Update MNCS to reference RAVEL as a sibling project without deleting historical evidence prematurely.
6. Develop the Forge interface and evidence/knowledge schemas before adding broad autonomy.

## Non-goals

RAVEL is not currently claiming:

- general intelligence or autonomous scientific discovery;
- unrestricted recursive self-improvement;
- foundation-model training or replacement;
- production safety or certification;
- independent evaluation or protected evidence custody;
- automatic promotion from a successful development result; or
- that a graph, vector index, or larger context window alone constitutes learning.

## Origin

RAVEL was initiated by Alexander Collamore as part of the Machine-Native Complexity project family. Its early implementation and evidence history remain in the MNCS repository until the history-preserving extraction is completed and verified.
