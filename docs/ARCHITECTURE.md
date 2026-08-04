# RAVEL architecture

## Purpose

RAVEL is an adaptive control and learning layer for evidence-driven machine-native development. It sits between an agent that proposes work and the bounded tools that establish facts about that work.

RAVEL should make better decisions over time without being allowed to redefine truth, weaken evaluation, or promote its own candidates.

## System boundary

```text
                         immutable policy and evaluator authority
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

### Evaluator and policy authority

The evaluator establishes dispositions under a preregistered protocol. RAVEL cannot modify:

- the evaluator implementation used for the active trial;
- acceptance thresholds;
- protected partitions or seed identities;
- resource budgets after observing outcomes;
- evidence custody rules;
- promotion authority; or
- historical evidence records.

## Core control loop

A bounded RAVEL episode should follow this sequence:

1. **Observe context.** Bind the candidate, task, environment, constraints, prior knowledge, and current evidence.
2. **Identify uncertainty.** Record what is unknown and which decisions depend on it.
3. **Generate competing hypotheses.** Preserve plausible alternatives and explicit falsifiers.
4. **Select a bounded probe.** Choose the least expensive evidence action likely to distinguish the hypotheses.
5. **Record predictions.** State expected effects, invariants, costs, and acceptable regressions before execution.
6. **Invoke Forge or another provider.** Receive structured observations and witnesses.
7. **Evaluate without reinterpretation.** Preserve raw verifier status and derive a separate hypothesis disposition.
8. **Choose the next action.** Repair, gather more evidence, abstain, reject, or freeze the candidate.
9. **Record the episode.** Store identities, actions, outcomes, costs, and unresolved alternatives.
10. **Extract provisional knowledge.** Create principles or strategies only when attribution and scope support them.
11. **Test transfer.** Reuse remains restricted until separate contexts support the declared scope.

## Separation of statuses

RAVEL must not collapse different state spaces into one score.

Examples include:

- verifier status: `PASS | FAIL | UNKNOWN`;
- episode outcome: `success | error | neutral | abstention`;
- hypothesis disposition: `open | supported | challenged | rejected | inconclusive`;
- principle maturity: `provisional | supported | challenged | rejected | retired`;
- transfer status: `untested | failed | partial | supported`;
- strategy reuse status: `untested | restricted | supported | retired`; and
- candidate disposition under its governing protocol.

A supported hypothesis does not convert a failed verifier into a pass. A successful episode does not establish a supported transferable principle.

## Forge interface

The first RAVEL–Forge interface should be narrow. A verifier request should contain:

- request identity;
- candidate and artifact identities;
- verifier contract identity and version;
- bounded question;
- required witness form;
- resource budget;
- timeout and cancellation policy;
- environmental assumptions; and
- requested determinism level.

A verifier response should contain:

- request and provider identities;
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

The relevant question is not whether RAVEL can produce a better result once. It is whether a declared policy improves outcomes, cost, calibration, retention, and transfer without weakening evaluation.

## Trust boundary

RAVEL is not trusted merely because it is the intelligence layer. It must be able to say:

- no supported explanation exists;
- available evidence is insufficient;
- the candidate remains `UNKNOWN`;
- a learned principle does not transfer;
- a strategy should be retired; or
- no adaptation is safer than the proposed change.

Abstention is a valid and learnable outcome.

## Initial implementation order

1. Define versioned evidence and experience schemas.
2. Build an append-only local experience store.
3. Add a small Forge adapter for a handful of micro-verifiers.
4. Implement deterministic evidence-gap and verifier-selection rules.
5. Add causal hypothesis and intervention records.
6. Add negative-memory retrieval.
7. Compare static and adaptive routing under equal budgets.
8. Add transfer gates before broad strategy reuse.
9. Add distributed scheduling only after local semantics are stable.
10. Consider learned routing models only after the rule-based baseline is measurable.
