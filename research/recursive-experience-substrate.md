# Recursive experience and causal-learning substrate

## Purpose

A recursive architecture does not improve merely because failures are fed back into it. Error
feedback identifies where behavior was unacceptable, but it does not establish what caused the
failure, which intervention changed the outcome, whether the explanation transfers, or what should
remain unchanged.

This research track defines a bounded, machine-readable experience substrate for RAVEL and other
MNCS-governed recursive systems. It sits between raw observations and recursive candidate
replacement:

```text
observations
  -> structured experience episodes
  -> competing causal hypotheses
  -> bounded diagnostic and counterfactual probes
  -> intervention candidates with predicted effects
  -> immutable evaluation
  -> causal attribution
  -> provisional learned principles
  -> transfer tests
  -> reusable adaptation strategies
```

The substrate is a post-RAVEL-0.6 research direction. It does not modify frozen RAVEL 0.4 or 0.5
artifacts, the RAVEL 0.6 preregistration, or the existing recursive-architecture comparison study.
It is design material, not evidence that general recursive self-improvement has occurred.

## Problem: error-only recursion

An error-only loop can repeatedly correct symptoms while failing to improve the process that
interprets experience. Common failure modes include:

- adding capacity whenever an error occurs, even when routing or representation is the cause;
- optimizing a scalar score without identifying which mechanism changed it;
- forgetting rejected repairs and repeating equivalent failures;
- learning only from negative events while discarding successful routes, abstentions, and stable
  invariants;
- assigning all credit to the immediate child even when an earlier candidate enabled later gains;
- treating correlation across candidate generations as causal attribution;
- promoting a local lesson into a global strategy without transfer evidence; and
- allowing the adaptation system to rewrite its evaluator, thresholds, partitions, or resource
  limits.

The objective is therefore not to add a larger feedback buffer. It is to create an inspectable
substrate that distinguishes observation, explanation, intervention, attribution, generalization,
and reuse.

## Design principles

1. **Observations are not explanations.** Raw errors and successes enter as episodes. Causal claims
   require explicit hypotheses and falsifiers.
2. **Hypotheses compete.** A favored explanation must retain plausible alternatives until bounded
   probes or interventions distinguish them.
3. **Predictions precede evaluation.** Expected improvements, invariants, regressions, and resource
   changes are recorded before the child is evaluated.
4. **Success, failure, neutrality, and abstention are retained.** The system must learn what should
   remain unchanged and when declining to adapt is beneficial.
5. **Evaluation authority remains immutable.** Experience records cannot modify the evaluator,
   thresholds, partitions, resource policy, custody, or promotion authority.
6. **Lessons remain provisional.** A learned principle is not globally reusable until transfer tests
   support its declared scope.
7. **Negative memory is first-class.** Failed interventions, rejected hypotheses, regressions, and
   known strategy failure modes remain retrievable.
8. **Credit follows lineage.** Immediate, enabling, delayed-descendant, transfer, retention, and
   negative downstream effects remain distinct.
9. **Bounded records replace hidden narratives.** The substrate stores compact claims, identities,
   witnesses, alternatives, and falsifiers. It does not require or preserve private chain-of-thought
   transcripts.
10. **Recursive learning does not create authority.** Repository-local success does not establish
    conformance, protected custody, independence, certification, or promotion.

## Memory classes

The substrate separates five memory classes.

| Class | Purpose |
|---|---|
| Episodic | Exact bounded events, routes, predictions, actions, outcomes, candidate identities, and costs |
| Causal | Competing explanations, probes, interventions, attribution, alternatives, and falsifiers |
| Semantic | Generalized principles supported across attributed episodes or candidate lineages |
| Procedural | Reusable adaptation strategies with triggers, preconditions, scope, and known failure modes |
| Negative | Failed repairs, rejected hypotheses, regressions, counterexamples, and contexts where reuse is prohibited |

These classes may share storage infrastructure, but they must not collapse into one undifferentiated
score or embedding. Every reusable object must preserve its source identities and declared scope.

## Record vocabulary

### `experience_episode`

A bounded observation of system behavior. Episodes include successful, erroneous, neutral, and
abstaining outcomes.

Required fields include:

- episode identity;
- candidate and context identities;
- observation identity;
- outcome class;
- route or participating mechanism identities;
- prediction and actual outcome;
- bounded resource cost; and
- normalized anomalies or notable invariants.

An episode records what happened. It does not assert why it happened.

### `causal_hypothesis`

A falsifiable explanation derived from one or more episodes.

It binds:

- a compact statement;
- supporting episode identities;
- competing hypothesis identities;
- required diagnostic or counterfactual probe identities;
- a falsifier;
- proof that it was recorded before intervention; and
- an independent disposition such as `open`, `supported`, `challenged`, `rejected`, or
  `inconclusive`.

A hypothesis disposition is not an MNCS or verifier status.

### `intervention_record`

A proposed change intended to test or act on a hypothesis.

It binds:

- the hypothesis;
- parent and child candidate identities;
- the bounded operation;
- affected mechanism surfaces;
- predicted effects and maximum acceptable regressions;
- resource budget; and
- rollback target.

An intervention must remain a separate candidate transaction. Evaluated parents are never edited in
place.

### `causal_attribution`

The evaluator-derived relationship between an intervention and observed effects.

It records:

- intervention identity;
- actual metric and resource effects;
- hypothesis disposition;
- alternative explanations that remain viable;
- credit classes; and
- evaluator identity.

Attribution may be `inconclusive`. Improvement alone does not require the architecture to pretend it
understands the cause.

### `learned_principle`

A generalized but falsifiable lesson synthesized from one or more causal attributions.

It contains:

- a compact statement;
- declared mechanism and context scope;
- supporting attribution identities;
- known counterexample episode identities;
- maturity such as `provisional`, `supported`, `challenged`, `rejected`, or `retired`;
- transfer status; and
- a falsifier.

A principle with `transfer_status: untested` cannot authorize global reuse.

### `strategy_record`

A reusable adaptation procedure derived from one or more principles.

It binds:

- triggering conditions;
- recommended intervention class;
- preconditions;
- known failure modes;
- applicability scope; and
- reuse status.

Strategies are suggestions for candidate generation. They do not bypass transactional evaluation,
resource limits, or hard gates.

## Status separation

The substrate intentionally contains several orthogonal state spaces:

- episode outcome: `success | error | neutral | abstention`;
- hypothesis disposition: `open | supported | challenged | rejected | inconclusive`;
- principle maturity: `provisional | supported | challenged | rejected | retired`;
- transfer status: `untested | failed | partial | supported`;
- strategy reuse status: `untested | restricted | supported | retired`;
- candidate disposition: accept, reject, or `UNKNOWN` under the governing development protocol; and
- verifier or evaluator status: `PASS | FAIL | UNKNOWN` where those protocols apply.

No diagnostic interpretation may rewrite a verifier result. No supported hypothesis converts a
candidate or MNCS result into `PASS`.

## Diagnostic and counterfactual probes

The experience substrate should consume bounded, identity-bearing probes rather than large prose
reports. Examples for RAVEL include:

- whether transition-aware routing would change the selected expert for one bounded event;
- which retained transition becomes unsupported after a proposed retirement;
- whether an observed gain survives when replay frequency is held constant;
- whether a child expert adds unique support or duplicates an existing expert;
- whether representation similarity and behavioral equivalence disagree;
- whether the same intervention succeeds under a second environment provider; and
- whether the apparent benefit disappears under shuffled episode-to-hypothesis mapping.

Forge micro-verifiers are a natural provider-neutral mechanism for such probes. The stable object is
the bounded question and witness, not Clang, LLVM, Joern, a sanitizer, or a RAVEL-specific analyzer
brand.

## Learning from success and non-action

A useful recursive system must preserve more than errors.

Successful episodes reveal:

- routes that remain correct under drift;
- invariants that should not be disturbed;
- expert specializations worth preserving;
- interventions that transferred beyond their original context; and
- cases where a supposedly obsolete structure still protects rare behavior.

Neutral and abstention episodes reveal:

- changes that consumed resources without changing behavior;
- situations where adaptation was unnecessary;
- cases where evidence was insufficient and non-action avoided damage; and
- contexts in which the safest strategy is to request more evidence.

The executable profile therefore requires all four outcome classes and includes a success-memory
ablation control. An architecture that performs similarly after successful experience is removed has
not demonstrated that it uses positive experience.

## Lineage-aware credit assignment

Candidate effects may be delayed. A representation change in candidate 2 may enable routing gains in
candidate 3 and safe retirement in candidate 4. The substrate therefore distinguishes:

- **immediate credit** — direct parent-to-child effect;
- **enabling credit** — infrastructure or representation that permits a later improvement;
- **delayed-descendant credit** — effect first observed deeper in the lineage;
- **transfer credit** — effect preserved in an unseen environment or task regime;
- **retention credit** — preservation of required prior behavior; and
- **negative-downstream credit** — later regressions enabled by an earlier intervention.

Credit remains explicit and bounded. A single hidden reward must not absorb all causal interpretation.

## Retrieval and reuse

Experience retrieval should be query-driven. A candidate proposer may request episodes, hypotheses,
principles, or strategies by declared context, mechanism surface, anomaly, lineage, transfer state,
or failure mode.

Reuse must bind:

- candidate and context lineage;
- supporting record identities;
- principle scope;
- current transfer state;
- known counterexamples;
- applicable resource and authority policy; and
- the strategy's known failure modes.

When context matching or dependency completeness is uncertain, reuse remains `UNKNOWN` or restricted.
The system may propose a diagnostic probe instead of applying the strategy.

## Policy recursion

The substrate enables a stronger policy-recursive loop:

```text
current adaptation policy
  -> experience episodes
  -> causal hypotheses about adaptation behavior
  -> diagnostic probes and controlled interventions
  -> attributed outcomes
  -> principles about when adaptation policies work
  -> candidate replacement for the adaptation policy
```

The recursively replaceable policy may include birth eligibility, replay allocation, retirement
utility, routing equivalence, transition preservation, planning, hypothesis selection, diagnostic
selection, and strategy retrieval. It may not replace the evaluator, governor, hard gates,
partitions, resource ceilings, custody, or promotion authority.

## Required controls

A credible study must include at least:

- **shuffled-attribution control** — preserve valid records but break intervention-to-outcome
  alignment;
- **success-memory ablation** — remove successful episodes while retaining failures;
- **negative-memory ablation** — remove failed strategies and rejected hypotheses;
- **transfer holdout** — test principles and strategies in an unavailable development context; and
- **aggregate-only feedback control** — expose scores without episodes, hypotheses, or attribution.

These controls distinguish useful experience synthesis from search volume, scalar optimization, or
memorization of local failures.

## Required negative tests

The validator must reject profiles or record bundles that allow:

- evaluator, threshold, partition, or resource-policy mutation;
- error-only memory;
- deletion of failed or rejected experience;
- hypotheses created after intervention results are known;
- principles without supporting attributions or falsifiers;
- strategies without known failure modes;
- global reuse without transfer support;
- causal attribution without a declared credit class;
- aggregate scores alone promoting a causal claim; or
- access to future-final material before candidate freeze.

## Relationship to RAVEL 0.6

RAVEL 0.6 should remain focused on transactional retention-constrained adaptation, behavioral
fixtures, mechanism/environment separation, candidate lineage, and correctly partitioned evaluation.
Those capabilities are prerequisites for reliable experience records.

This substrate is a separate post-0.6 track. It may consume frozen RAVEL results as design evidence,
but it cannot alter prior sources, evidence, gates, dispositions, or final material.

## Relationship to the recursive architecture study

The existing recursive-architecture comparison defines manual, structural, candidate-lineage,
policy-meta, and governed-portfolio arms under equal budgets. This substrate supplies a richer
feedback object for future versions of those arms.

The existing study plan remains unchanged. A later preregistration may compare:

- structured errors only;
- complete episodes without causal synthesis;
- episodes plus hypotheses and interventions;
- full attribution, principle, and strategy reuse; and
- policy recursion over the experience-processing mechanism itself.

## Relationship to MNCS, MNCDS, and Forge

- **RAVEL** supplies the recursively replaceable mechanism and adaptation policy.
- **Forge micro-debugging** supplies bounded diagnostic and counterfactual probes.
- **MNCDS** records candidate generation, feedback eligibility, lineage, predictions, selection,
  retained failures, and same-epoch repair restrictions.
- **MNCS** evaluates the frozen implementation claim.
- **The recursion governor** enforces immutable authority, budgets, append-only lineage, and stopping
  rules.

These roles remain separate. The experience substrate does not become a second evaluator or
normative conformance authority.

## Phased implementation

### Phase 1 — vocabulary and validator

Commit the machine-readable profile, reference records, semantic validator, and deterministic
negative fixtures.

### Phase 2 — bounded episode collection

Emit successful, erroneous, neutral, and abstaining episodes from a deterministic synthetic RAVEL
fixture. Preserve exact candidate, context, route, and observation identities.

### Phase 3 — hypothesis and probe lifecycle

Add explicit competing hypotheses and bounded Forge-compatible diagnostic probes. Require hypotheses
and predictions before intervention evaluation.

### Phase 4 — attribution and delayed credit

Implement controlled interventions, attribution records, alternative explanations, and lineage-aware
credit classes.

### Phase 5 — principle and strategy transfer study

Synthesize provisional principles and strategies, evaluate them on held-out contexts, and compare
against shuffled, aggregate-only, success-ablation, and negative-memory-ablation controls.

### Phase 6 — policy-recursive comparison

Allow bounded candidate replacement of the hypothesis, probe-selection, attribution, and strategy
reuse policy while preserving immutable external authority.

## Claim boundary

This track can test whether structured experience, causal accountability, and transfer-gated reuse
improve bounded recursive development under declared tasks and budgets. It cannot establish general
recursive self-improvement, general causal understanding, foundation-model self-training,
autonomous scientific discovery, real-world safety, independent evaluation, protected custody,
formal conformance, certification, or promotion.
