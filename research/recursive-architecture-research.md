# Recursive Architecture Research

## Purpose

MNCS and RAVEL currently exercise two different forms of recursion:

- MNCDS records bounded evidence-guided development across frozen candidate epochs;
- RAVEL recursively changes expert population structure through routing, error, birth,
  replay, retirement, and topology rebuilding.

Both are useful, but neither yet demonstrates a system that improves the policy
responsible for improvement. This research track moves the recursive surface from
in-place mutation toward **evidence-governed candidate replacement** while preserving
an immutable evaluator, fixed limits, explicit lineage, and rollback.

This document is a research design, not a normative requirement, a change to frozen
RAVEL evidence, or authorization to promote a candidate.

## Current interpretation

The existing two-epoch analyzer study is best understood as a governed improvement
fixture. A developer observes epoch-one disagreements and writes an improved epoch-two
analyzer. The study validates identity, partitions, thresholds, retained failures, and
selection records. It does not claim autonomous recursive generation.

RAVEL-T contains a stronger endogenous loop: current experts determine routing,
routing determines training shards, shard error causes child birth, and the child
population regenerates the router. This demonstrates structural recursion, but the
birth, replay, retirement, planning, and acceptance policies remain externally fixed.

The next research question is therefore not merely whether recursive structures can
add capacity. It is whether bounded evidence can guide replacement of the policy that
controls adaptation without allowing the recursive system to rewrite its judge.

## Three recursion layers

A recursive architecture should declare which layer it owns.

| Layer | Machine-owned behavior | Required external boundary |
|---|---|---|
| Parameter loop | Update expert parameters, statistics, or local memories | Evaluator, limits, and promotion |
| Structural loop | Birth, split, merge, retire, replay, route, and rebuild topology | Partitions, hard gates, resource ceilings, rollback |
| Policy loop | Propose replacements for structural adaptation policy | Evaluator identity, thresholds, final custody, and release authority |

A claim about one layer must not be presented as evidence for a stronger layer.

## Core design: recursive candidate replacement

The active candidate never rewrites itself in place. It may emit structured failure
records and propose one or more separately identified descendants.

```text
active candidate
  -> raw observations
  -> immutable evaluator
  -> structured failure and uncertainty record
  -> bounded proposer
  -> child candidate with parent identity and predicted effects
  -> transactional evaluation
       accept: child becomes next active candidate
       reject: parent remains byte-identical
       unknown: retain both without promotion
```

Every candidate must have:

- a unique content identity;
- one or more parent identities;
- a bounded change description;
- the evidence used to justify the proposal;
- predicted metric effects recorded before evaluation;
- actual effects derived by the evaluator;
- resource consumption;
- an accept, reject, or `UNKNOWN` disposition; and
- a rollback target.

The proposer may modify candidate implementation and declared adaptation policy. It
must not modify evaluator code, evaluator configuration, hard gates, partitions,
resource ceilings, custody records, or promotion authority.

## Architecture portfolio

A single recursive mechanism can overfit its own representation of failure. The study
therefore compares several architectures under equal candidate and compute budgets.

### A0 — governed manual repair

A human reads structured evidence and writes the next candidate. This is the practical
baseline and resembles the current recursive-analyzer study.

### A1 — structural expert recursion

The adaptation policy is fixed, but the mechanism may change expert count, lineage,
routing, replay assignments, and retirement within bounds. This resembles RAVEL-T and
later RAVEL structural adaptation.

### A2 — lineage candidate replacement

A bounded proposer generates child implementations from parent evidence. The evaluator
remains immutable, and every accepted child atomically replaces its parent.

### A3 — policy meta-recursion

The proposer may replace the structural policy itself: birth eligibility, replay
allocation, retirement utility, transition preservation, belief planning, and
transactional acceptance. The implementation still cannot alter evaluation authority.

### A4 — governed architecture portfolio

Several proposer architectures generate candidates in parallel. A budget allocator may
shift future candidate slots toward architectures with better preregistered improvement
per cost, but it cannot change gates or retroactively discard failed lineages.

This portfolio is intentionally included as a potentially novel direction. It treats
recursive improvement as a population of competing development architectures rather
than a single self-referential loop.

## Recursion governor

A separate recursion governor enforces process invariants. It is not an optimizer and
must not select a candidate based on hidden criteria.

The governor checks:

- evaluator, threshold, partition, and resource-policy identities remain fixed;
- candidate lineage is acyclic and append-only;
- rejected transactions preserve the parent checkpoint byte-for-byte;
- candidate and compute budgets are not exceeded;
- predictions are recorded before observations are opened;
- failures and `UNKNOWN`s are retained;
- final material is unavailable until the selected candidate is frozen;
- no same-candidate repair uses selection or final observations;
- repeated equivalent patches do not masquerade as architectural novelty; and
- stopping rules trigger on budget exhaustion, unsafe authority expansion, stagnation,
  evaluator gaming, or unresolved integrity failure.

The governor should emit machine-readable reason codes rather than a prose-only report.

## Controls that test whether recursion is doing useful work

A better final candidate alone does not establish that recursive feedback caused the
improvement. The comparison must include controls.

### Random-proposal control

Generate bounded candidate changes without access to failure diagnostics. This measures
benefit from search volume alone.

### Shuffled-feedback control

Give a proposer valid failure records from another candidate or a shuffled mapping
between failures and affected components. If this performs similarly to correct
feedback, the claimed recursive signal is weak.

### Feedback-ablation control

Provide aggregate scores but remove structured diagnostics and lineage history. This
measures whether detailed evidence contributes beyond scalar optimization.

### Fixed-policy control

Allow parameter and structural recursion but prohibit policy replacement. This isolates
the value of the policy loop.

### Equal-budget architecture tournament

Each architecture receives the same candidate slots, wall-independent operation count,
and evaluation budget before any adaptive budget allocation is allowed.

## Predictive accountability

Before a child is evaluated, the proposer records:

- which failure codes it intends to address;
- which metrics should improve, remain invariant, or may regress;
- the maximum acceptable regression;
- expected resource change;
- affected implementation surfaces; and
- a falsifier that would show the proposal rationale was wrong.

The evaluator then scores both candidate performance and proposal calibration. A system
that improves while repeatedly predicting the wrong effects may be searching, but it is
not yet demonstrating reliable evidence-guided recursion.

## Recursion health metrics

In addition to task performance, the study records:

- improvement per evaluated candidate;
- improvement per bounded operation;
- accepted-update rate;
- rejected-update rollback equality;
- lineage depth and branching factor;
- duplicate or near-equivalent candidate rate;
- prediction calibration;
- transfer-regime performance;
- retention and transition-support preservation;
- evaluator disagreement and `UNKNOWN` rate;
- concentration of candidate generation in one architecture;
- evidence reuse depth;
- time-to-stagnation; and
- authority-violation attempts.

No single aggregate score should hide a hard-gate failure. Pareto and per-dimension
reporting remain necessary.

## Architecture-comparison test shape

The first implementation should use a bounded synthetic environment and several
independently written mechanism adapters. The purpose is to test the recursive process,
not to claim general AI capability.

Each architecture receives:

1. the same frozen development environments;
2. the same candidate and operation budgets;
3. the same evaluator and hard gates;
4. distinct selection material;
5. an untouched transfer environment unavailable during candidate generation; and
6. a future final partition held outside the development loop.

Suggested task families include:

- structural source analysis with direct, alias, and dynamic-call ambiguity;
- RAVEL-style classification and representation drift;
- transition-support and planning drift;
- composed-system contract changes requiring partial revalidation; and
- resource-constrained routing where a shortcut is only allowed with an exact fallback.

Using multiple task families reduces the chance that one architecture wins merely
because the benchmark mirrors its internal representation.

## Required negative tests

The executable study validator must reject or fail fixtures for:

- proposer access to evaluator code or configuration;
- threshold mutation after observing results;
- final-partition access before candidate freeze;
- in-place mutation of an evaluated candidate;
- missing or cyclic parent identities;
- deleted rejected candidates;
- post-hoc prediction records;
- candidate-budget overflow;
- resource-policy mutation;
- selection evidence reused for same-candidate repair;
- a rejected update that changes the parent checkpoint;
- a portfolio allocator that silently removes a failing architecture; and
- a claimed recursive architecture without a random or shuffled-feedback control.

## Relationship to RAVEL 0.6

RAVEL 0.6 should remain narrow and complete its preregistered retention-constrained
adaptation work. Transactional updates, structured rejection reasons, separated
mechanism/environment interfaces, candidate identities, and append-only lifecycle
records are prerequisites for later policy recursion.

The architecture-comparison study is a separate post-0.6 track. It may consume frozen
RAVEL results as design evidence, but it must not alter 0.6 gates, candidates, or final
material.

## Relationship to MNCS and MNCDS

- MNCDS records candidate generation, lineage, feedback eligibility, selection,
  authority separation, and retained failures.
- MNCS evaluates the frozen candidate and its bounded claim.
- RAVEL or another mechanism supplies the recursively replaceable execution and
  adaptation surface.
- The recursion governor enforces development invariants but cannot create independent
  custody, organizational independence, or promotion authority.

This separates machine-owned improvement from human and institutional authority without
requiring the execution plane to remain human-readable.

## Phased implementation

### Phase 1 — profile and validator

Define machine-readable architecture profiles, authority permissions, controls,
metrics, stop rules, and negative fixtures. Validate these artifacts in repository CI.

### Phase 2 — deterministic comparison harness

Implement equal-budget candidate lineages on small synthetic tasks. Include manual,
random, shuffled-feedback, fixed-policy, lineage-replacement, policy-recursive, and
portfolio arms.

### Phase 3 — RAVEL adapter

Expose RAVEL mechanism state and adaptation policy through narrow candidate interfaces.
Use transactional replacement and preserve frozen prior epochs.

### Phase 4 — heterogeneous architecture tests

Run the same MNCDS development protocol against multiple mechanism architectures and
provider environments. Compare transfer behavior and recursion health, not merely final
accuracy.

### Phase 5 — externally held final evaluation

Freeze the selected candidate, evaluator, and identities before an external custodian
opens final material. Absence of this evidence remains `UNKNOWN`.

## Claim boundary

This research track can establish whether a bounded recursive development process
outperforms controls within declared tasks and budgets. It cannot by itself establish
general recursive self-improvement, autonomous scientific discovery, foundation-model
scaling, production safety, protected custody, organizational independence, formal
conformance, or promotion.
