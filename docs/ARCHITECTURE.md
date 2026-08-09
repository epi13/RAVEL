# RAVEL architecture

## Purpose

RAVEL is an adaptive control and learning layer for evidence-driven machine-native development. It sits between an agent that proposes work and the bounded tools that establish facts about that work.

RAVEL should make better decisions over time without being allowed to redefine truth, weaken evaluation, or promote its own candidates.

## Governing authority

RAVEL operates beneath the Machine-Native Complexity Standard (MNCS) and the Machine-Native Complexity Development Standard (MNCDS).

```text
MNCS
  defines contracts, evidence semantics, status, conformance, and claim boundaries
                                      |
                                      v
MNCDS
  operationalizes MNCS for decomposition, development, evidence flow, and lifecycle
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
          RAVEL control plane                  Forge/tool plane
      memory, hypotheses, policy          bounded verification and witnesses
                    |                                   |
                    +-----------------+-----------------+
                                      |
                                      v
                          candidate and environment evidence
```

The foundational relationship is:

> **MNCS defines authority. MNCDS operationalizes it. Forge executes it. RAVEL reasons and learns beneath it.**

MNCS and MNCDS are not ordinary peer components in the control loop. They define the rules under which every component participates.

See [`AUTHORITY_MODEL.md`](AUTHORITY_MODEL.md) for the complete authority boundary.

## System boundary

```text
                   MNCS/MNCDS contracts and governing invariants
                                         |
                                         v
agent/model -> RAVEL control plane -> Forge/tool plane -> environment
     ^              |                      |                 |
     |              v                      v                 v
     +------- candidate actions      structured evidence   observations
                    |
                    v
             experience substrate
```

### Agent/model

The model proposes plans, code, hypotheses, repairs, and explanations. It is a candidate generator, not an evidence authority.

### RAVEL

RAVEL performs:

- task and context decomposition;
- evidence-gap identification;
- verifier and tool selection;
- bounded sequencing of probes;
- comparison of competing hypotheses;
- repair-strategy selection;
- confidence and uncertainty tracking;
- experience recording;
- principle and strategy extraction;
- transfer-gate enforcement; and
- policy evaluation under fixed budgets.

RAVEL may recommend actions, but it cannot redefine MNCS/MNCDS status, broaden claims beyond evidence, weaken governing contracts, or treat its confidence as conformance.

### Forge

Forge performs deterministic or tightly bounded operations such as:

- compilation;
- static and dynamic analysis;
- contract checking;
- micro-verification;
- test execution;
- mutation testing;
- trace and telemetry collection;
- artifact identity calculation; and
- structured evidence emission.

Forge should expose evidence through stable provider-neutral contracts. Clang, LLVM, Joern, sanitizers, model checkers, and custom micro-verifiers are providers behind those contracts rather than the architectural identity of the checks.

Forge does not define the meaning of MNCS or MNCDS. Its result has authority only within its governing contract, declared scope, environment, witness, and limitations.

### MNCS/MNCDS-governed evaluation

The evaluator establishes dispositions under a declared MNCS/MNCDS-governed protocol. RAVEL cannot modify:

- the evaluator implementation used for the active trial;
- acceptance thresholds;
- protected partitions or seed identities;
- resource budgets after observing outcomes;
- evidence custody rules;
- formal status semantics;
- conformance or promotion boundaries; or
- historical evidence records.

The evaluator is not a sovereign layer above MNCS. Its authority is delegated and bounded by the governing standard and development protocol.

## Core control loop

A bounded RAVEL episode should follow this sequence:

1. **Bind governing authority.** Identify the applicable MNCS/MNCDS contracts, status semantics, claim boundary, and development protocol.
2. **Observe context.** Bind the candidate, task, environment, constraints, prior knowledge, and current evidence.
3. **Identify uncertainty.** Record what is unknown and which decisions depend on it.
4. **Generate competing hypotheses.** Preserve plausible alternatives and explicit falsifiers.
5. **Select a bounded probe.** Choose the least expensive evidence action likely to distinguish the hypotheses.
6. **Record predictions.** State expected effects, invariants, costs, and acceptable regressions before execution.
7. **Invoke Forge or another provider.** Receive structured observations and witnesses under the governing verifier contract.
8. **Evaluate without reinterpretation.** Preserve raw verifier status and derive a separate hypothesis disposition.
9. **Choose the next action.** Repair, gather more evidence, abstain, reject, or freeze the candidate.
10. **Record the episode.** Store identities, actions, outcomes, costs, governing contracts, and unresolved alternatives.
11. **Extract provisional knowledge.** Create principles or strategies only when attribution and scope support them.
12. **Test transfer.** Reuse remains restricted until separate contexts support the declared scope.

## Implemented reusable foundations

The repository now contains small, dependency-free foundations beneath the
0.6 experiment:

- `ravel.adaptation` performs copy-before-evaluate retention transactions and
  emits stable rejection reason codes without treating raw observations as
  authority.
- `ravel.providers` defines a narrow Forge boundary with capability discovery,
  immutable raw evidence, and fail-closed `UNKNOWN` receipts. It is an adapter,
  not a Forge reimplementation.
- `ravel.resources` separates future provider placement policy from the
  preregistered 0.6 mechanism. Fake backends exercise CPU fallback, CUDA kernel
  probes, VRAM headroom, sequential offload, and bounded OOM recovery.
- `ravel.memory` retains versioned source identities, explicit scope contracts,
  negative-aware full-text retrieval, append-only proposal lifecycle events,
  atomic batches, and rebuildable relation projections.
- `ravel.world`, `ravel.transition`, and `ravel.planning` define replaceable
  environment, deterministic transition-compilation, and bounded planning
  surfaces. `ToyBranchingWorld` and `ToyRingWorld` are independent fixtures;
  provider identity is carried into the compiled projection.
- `ravel.mechanism_state` and `ravel.checkpoint` keep mechanism state separate
  from evaluation and provide canonical round-trip identities with corruption
  detection.
- `ravel.lifecycle` records development candidate state transitions in an
  append-only hash chain. `ravel.experience` turns scoped raw execution into
  advisory episodic or negative memory without promoting status.

The generated candidate-001 C source now has an explicit copy, hard-gate, raw
observation, and rollback surface around the existing adaptation primitive. The
historical monolithic C translation unit has not yet been physically extracted
into separate C translation units; the Python surfaces are the first tested
decomposition boundary, not a claim of completed R6-04 C decomposition.

These modules are tested scaffolding and are not claims that RAVEL 0.6 has been
evaluated, selected, independently evaluated, certified, promoted, or made
production-safe.

## Separation of statuses

RAVEL must not collapse different state spaces into one score.

Examples include:

- MNCS/MNCDS conformance status;
- verifier status: `PASS | FAIL | UNKNOWN`;
- candidate disposition;
- episode outcome: `success | error | neutral | abstention`;
- hypothesis disposition: `open | supported | challenged | rejected | inconclusive`;
- principle maturity: `provisional | supported | challenged | rejected | retired`;
- transfer status: `untested | failed | partial | supported`;
- strategy reuse status: `untested | restricted | supported | retired`; and
- custody or evidence-authority class.

A supported hypothesis does not convert a failed verifier into a pass. A successful episode does not establish a supported transferable principle. A repository-local result does not establish protected custody or formal conformance.

RAVEL confidence and formal status are orthogonal:

```text
RAVEL confidence: 99.8%
MNCS disposition: UNKNOWN
```

and:

```text
RAVEL confidence: 42%
MNCS disposition: PASS
```

are both valid states.

## Forge interface

The first RAVEL–Forge interface should be narrow. A verifier request should contain:

- request identity;
- candidate and artifact identities;
- governing MNCS/MNCDS contract identity and version;
- verifier contract identity and version;
- bounded question;
- required witness form;
- resource budget;
- timeout and cancellation policy;
- environmental assumptions; and
- requested determinism level.

A verifier response should contain:

- request and provider identities;
- governing contract identity;
- raw status;
- structured observations;
- witness or counterexample identity;
- artifact digests;
- execution environment identity;
- resource use;
- completeness limitations; and
- provider diagnostics kept separate from the normalized result.

RAVEL should reason over the normalized contract while retaining provider-specific artifacts for debugging and audit.

## Policy competition

RAVEL's orchestration policy is itself a candidate. Competing policies should be compared under equal:

- task sets;
- MNCS/MNCDS contracts;
- evidence access;
- tool availability;
- compute and time budgets;
- evaluator authority;
- promotion gates; and
- retention requirements.

Useful comparisons include:

- static verifier sequences;
- causal-feedback routing;
- candidate-lineage recursion;
- policy-meta recursion;
- governed portfolios of strategies; and
- ablations that remove memory classes or transfer gates.

The relevant question is not whether RAVEL can produce a better result once. It is whether a declared policy improves outcomes, cost, calibration, retention, and transfer without weakening evaluation or changing the governing authority.

## Authority and trust boundary

RAVEL is not trusted merely because it is the intelligence layer. It must be able to say:

- no supported explanation exists;
- available evidence is insufficient;
- the candidate remains `UNKNOWN`;
- a learned principle does not transfer;
- a strategy should be retired; or
- no adaptation is safer than the proposed change.

Abstention is a valid and learnable outcome.

Forge is also not sovereign. It executes bounded checks whose meaning is supplied by MNCS/MNCDS contracts. A provider cannot establish a broader claim than the contract and evidence allow.

The architectural invariant is:

> **RAVEL may remember any accurately typed experience, but only MNCS/MNCDS-governed evidence can establish the status and permitted use of that experience.**

## Current implementation order

1. Physically extract the tested C transaction, provider, planner, checkpoint,
   and observation surfaces without changing candidate behavior.
2. Extend the tested `ravel.c_observations` cross-language adapter with a full
   C/Python negative-reason matrix without making either side authoritative.
3. Use the append-only candidate ledger for development-only candidate freezes;
   do not consume selection partitions in this repository-local loop.
4. Connect accepted and rejected execution records to the append-only memory
   store and benchmark negative/contradiction retrieval.
5. Use the inspected Forge CLI/provider boundary only through explicit,
   dependency-injected adapters; unavailable capabilities remain `UNKNOWN`.
