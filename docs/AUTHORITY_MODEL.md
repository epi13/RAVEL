# RAVEL authority model

## Foundational rule

RAVEL operates under the authority of the Machine-Native Complexity Standard (MNCS) and the Machine-Native Complexity Development Standard (MNCDS).

The governing relationship is:

```text
MNCS defines authority
        |
        v
MNCDS operationalizes that authority for development
        |
        +--> Forge executes bounded verification
        |
        +--> RAVEL reasons, remembers, proposes, and learns
        |
        +--> agents and implementations produce candidates
```

A compact statement is:

> **MNCS defines authority. MNCDS operationalizes it. Forge executes it. RAVEL reasons and learns beneath it.**

MNCS and MNCDS are not peer tools in the RAVEL control loop. They define the contracts, evidence semantics, status meanings, development boundaries, and permitted transitions under which the loop is valid.

## MNCS

MNCS is the ultimate technical authority for machine-native claims within this project family.

It defines or governs:

- contract identity and scope;
- evidence identity and required witnesses;
- provenance and custody distinctions;
- conformance and claim boundaries;
- status semantics such as `PASS`, `FAIL`, and `UNKNOWN`;
- separation of observations, interpretations, and dispositions;
- authority boundaries between candidates, verifiers, evaluators, and governing rules; and
- what may and may not be inferred from available evidence.

MNCS answers:

> What constitutes a valid machine-native claim, and what evidence is required to support it?

No RAVEL policy, Forge provider, agent confidence score, memory record, or favorable development result may override an MNCS-governed status or broaden a claim beyond its evidence.

## MNCDS

MNCDS applies MNCS authority to machine-directed development.

It governs or structures:

- decomposition and task boundaries;
- development stages and candidate lifecycles;
- verifier placement and evidence flow;
- implementation and artifact boundaries;
- failure, rollback, and abstention behavior;
- development-state transitions; and
- how machine-generated work remains inspectable and governable under MNCS.

MNCDS answers:

> How should a machine-native system be developed so that its artifacts and decisions remain valid under MNCS?

MNCDS does not supersede MNCS. It operationalizes MNCS for development.

## Forge

Forge is a bounded execution and verification substrate operating under MNCS/MNCDS contracts.

Forge may:

- invoke compilers, analyzers, tests, and micro-verifiers;
- collect structured observations and witnesses;
- validate artifact identity and contract conditions;
- expose normalized provider-neutral results; and
- refuse invalid requests or status transitions.

Forge does not define the meaning of MNCS or MNCDS. A Forge result has authority only within its declared contract, scope, environment, evidence, and limitations.

A valid Forge result therefore binds at least:

- verifier and provider identity;
- governing contract and version;
- candidate and artifact identities;
- environment identity;
- raw observations;
- witness or counterexample identity;
- resource and completeness limits; and
- the resulting MNCS/MNCDS-governed status.

Forge executes delegated checks. It is not sovereign over the standard that gives those checks meaning.

## RAVEL

RAVEL is an adaptive reasoning, memory, and evidence-orchestration layer beneath MNCS/MNCDS authority.

RAVEL may:

- retrieve prior experience;
- form competing hypotheses;
- identify evidence gaps;
- select bounded probes and Forge verifiers;
- propose candidates and interventions;
- compare strategies;
- track uncertainty and cost;
- record experience and counterexamples;
- synthesize provisional principles; and
- recommend later actions or transfer tests.

RAVEL may not:

- redefine an MNCS or MNCDS status;
- weaken a governing contract after observing an outcome;
- convert `UNKNOWN` into `PASS`;
- rewrite raw verifier observations;
- alter protected evaluation partitions or thresholds;
- exempt itself or a favored candidate from required verification;
- treat its own confidence as conformance evidence;
- promote repository-local evidence into a stronger custody or authority class; or
- broaden a learned principle beyond its supported scope.

RAVEL is a proposer and learner, not the ultimate technical authority.

## Agent and candidate implementations

Agents, models, tools, and generated implementations create candidate work.

They may produce:

- plans;
- source code;
- hypotheses;
- repairs;
- tests;
- explanations; and
- proposed contracts or evidence requests.

They cannot establish the validity of their own output merely by generating it or by modifying the tests used to evaluate it.

## Control loop

The governing loop is:

```text
MNCS/MNCDS contracts and invariants
                 |
                 v
RAVEL retrieves experience and proposes an action
                 |
                 v
agent or mechanism produces a candidate
                 |
                 v
Forge executes MNCS/MNCDS-governed verification
                 |
                 v
observations receive a valid bounded disposition
                 |
                 v
RAVEL records the experience and adapts its strategy
```

MNCS/MNCDS governs every stage. RAVEL can improve its selection and learning policy, but it cannot redefine what evidence or status means.

## Separation of confidence and status

RAVEL confidence and MNCS/MNCDS status are orthogonal.

```text
RAVEL confidence: 99.8%
MNCS disposition: UNKNOWN
```

This is valid when RAVEL strongly expects success but the required evidence is unavailable.

```text
RAVEL confidence: 42%
MNCS disposition: PASS
```

This is also valid when conclusive contract-bound evidence exists despite RAVEL's uncertainty.

RAVEL confidence guides action selection. It does not determine conformance.

## Memory implications

RAVEL memory is an advisory store of accurately typed experience, not a database of self-declared truth.

It may retain:

- raw observations;
- successful and failed episodes;
- open, rejected, and supported hypotheses;
- interventions and predictions;
- causal attributions;
- provisional principles;
- restricted and retired strategies;
- counterexamples; and
- unresolved alternatives.

Every reusable record should preserve its governing MNCS/MNCDS contract, evidence identities, scope, status, evaluator identity where applicable, and known limitations.

A memory record such as "this strategy worked repeatedly" is not equivalent to an MNCS claim that the strategy is conformant or universally reusable.

## Status integrity

The following state spaces must remain distinct:

- verifier status;
- candidate disposition;
- episode outcome;
- hypothesis disposition;
- principle maturity;
- transfer status;
- strategy reuse status;
- custody class; and
- formal MNCS/MNCDS conformance.

No favorable state in one space may silently promote another.

Examples:

- a successful episode does not establish conformance;
- a supported hypothesis does not convert a failed verifier into a pass;
- repeated local success does not establish transfer;
- a Forge provider success does not establish broader system promotion; and
- a RAVEL strategy may remain useful while its formal conformance is `UNKNOWN`.

## Foundational invariant

The RAVEL architecture should preserve this invariant across all future implementations:

> **RAVEL may remember any accurately typed experience, but only MNCS/MNCDS-governed evidence can establish the status and permitted use of that experience.**

This invariant applies whether RAVEL is implemented in C, Rust, an MNCS-oriented representation, or a distributed system, and whether Forge uses local micro-verifiers, external analyzers, or cluster execution providers.
