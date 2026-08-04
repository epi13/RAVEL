# RAVEL knowledge model

## The storage problem

RAVEL cannot become a useful learning layer by storing a growing pile of transcripts, source files, embeddings, or scalar rewards. Those forms may be useful inputs or indexes, but none of them independently preserve why a result was accepted, where it applies, what contradicted it, or which authority evaluated it.

The primary stored object should therefore be **validated engineering experience with explicit identity and scope**.

RAVEL knowledge should answer questions such as:

- What happened?
- Under which candidate, environment, contract, and budget?
- What explanations were considered?
- What was predicted before the intervention?
- Which evidence distinguished the explanations?
- What changed and what remained invariant?
- Which evaluator assigned the disposition?
- What counterexamples or unresolved alternatives remain?
- Where may the lesson be reused?
- What would falsify it?

## Authoritative records and derived indexes

RAVEL should separate authoritative records from replaceable retrieval structures.

```text
append-only records + content-addressed artifacts
                       |
                       +--> graph projection
                       +--> relational/materialized views
                       +--> search index
                       +--> optional vector index
                       +--> working-memory cache
```

The append-only records and content-addressed artifacts are the durable source of truth. Graphs, SQL views, embeddings, summaries, scores, and caches are derived projections that may be rebuilt.

This prevents an index update from silently changing historical knowledge.

## Memory classes

### Episodic memory

A bounded record of one event or attempt.

Examples:

- a verifier invocation;
- a compilation failure;
- a successful repair;
- a neutral intervention;
- a correct abstention;
- a routing decision; or
- a candidate evaluation.

An episode records what happened. It does not claim why it happened.

### Causal memory

Falsifiable explanations and interventions that connect episodes.

It includes:

- competing hypotheses;
- diagnostic probes;
- counterfactual probes;
- predicted effects;
- actual effects;
- viable alternatives;
- causal attribution; and
- attribution confidence or inconclusiveness.

### Semantic memory

Generalized principles supported by attributed episodes.

A principle must include:

- a compact statement;
- declared scope;
- supporting attributions;
- known counterexamples;
- maturity;
- transfer status; and
- a falsifier.

### Procedural memory

Reusable strategies for acting on recurring conditions.

A strategy includes:

- triggering conditions;
- required preconditions;
- recommended intervention class;
- expected evidence sequence;
- resource assumptions;
- rollback procedure;
- known failure modes;
- prohibited contexts; and
- reuse status.

### Negative memory

Failures and boundaries that must remain retrievable.

It includes:

- failed repairs;
- rejected hypotheses;
- regressions;
- contradicted principles;
- invalid evidence combinations;
- unsafe or ineffective strategies;
- contexts where transfer failed; and
- known attempts to weaken evaluation.

Negative memory should not be reduced to a penalty score. The system needs the identity and mechanism of the failure so it can avoid semantically equivalent repetitions.

## Core record vocabulary

### `artifact`

A content-addressed source file, binary, trace, checkpoint, dataset partition, report, or witness.

Minimum fields:

```json
{
  "artifact_id": "sha256:...",
  "media_type": "application/json",
  "size_bytes": 0,
  "logical_role": "verifier-witness",
  "producer_id": "...",
  "created_at": "...",
  "custody": "repository-local"
}
```

### `context`

The bounded environment in which an episode occurred.

It binds:

- task identity;
- candidate identity;
- source and binary identities;
- environment/provider identities;
- contract versions;
- available tools;
- resource budget;
- policy identity; and
- relevant prior knowledge identities.

### `experience_episode`

A factual event record.

```json
{
  "episode_id": "episode:...",
  "context_id": "context:...",
  "action_id": "action:...",
  "observation_ids": ["observation:..."],
  "outcome": "success",
  "resource_cost": {},
  "notable_invariants": [],
  "anomalies": []
}
```

### `causal_hypothesis`

A preregistered, falsifiable explanation.

It binds a statement, supporting episodes, competing hypotheses, required probes, predicted observations, falsifier, authoring policy, and disposition.

### `intervention_record`

A proposed change that tests or acts on a hypothesis.

It binds parent and child candidates, affected surfaces, predicted effects, maximum acceptable regressions, resource budget, and rollback target.

### `causal_attribution`

An evaluator-derived relationship between an intervention and observed effects.

Attribution may be `inconclusive`; a favorable metric movement does not require a fabricated causal explanation.

### `learned_principle`

A scoped, falsifiable lesson synthesized from causal attributions.

### `strategy_record`

A reusable procedure derived from one or more principles.

### `counterexample`

A first-class record showing that a hypothesis, principle, or strategy failed or ceased to apply in a particular context.

### `evaluation_record`

The immutable disposition assigned under a declared evaluator protocol. Diagnostic interpretation and evaluator status remain separate.

## Identity and provenance

Every authoritative record should be immutable after finalization. Corrections are represented by new records that supersede or challenge earlier records rather than editing history in place.

Records should bind:

- globally unique logical identity;
- schema and version;
- content digest;
- parent or source identities;
- producer identity;
- evaluator identity where applicable;
- timestamps as metadata, not sole identity;
- repository and commit identity;
- environment and provider identity;
- declared scope; and
- custody class.

Content addressing is useful for artifacts, but logical identities are still needed because two records with identical bytes may have different roles, custody, or evaluation contexts.

## Proposed storage layers

### 1. Append-only event store

Begin with a simple local store using SQLite or line-delimited canonical JSON plus an index. The first implementation should favor inspectability and deterministic export over scale.

Recommended responsibilities:

- immutable record insertion;
- schema validation;
- parent/reference integrity;
- monotonic sequence assignment;
- transaction boundaries;
- supersession links;
- custody and authority metadata; and
- deterministic export.

### 2. Content-addressed artifact store

Store large evidence separately by digest:

```text
artifacts/sha256/ab/cd/<full-digest>
```

Metadata records refer to artifacts by digest and role. The store should detect corruption and avoid duplicate bytes.

### 3. Relational and graph projections

A relational view is useful for filtering by status, version, provider, task, cost, and date. A graph projection is useful for traversing:

```text
episode -> hypothesis -> intervention -> attribution
        -> principle -> strategy -> reuse episode
```

The graph is a projection, not the source of truth. It must be rebuildable from authoritative records.

### 4. Text and vector retrieval

Full-text search and embeddings may help locate semantically similar records. Retrieval results must resolve back to authoritative identities before they influence action.

Embeddings should not erase:

- status distinctions;
- negative records;
- source lineage;
- evaluator authority;
- applicability scope; or
- transfer limitations.

A high similarity score is a retrieval hint, not evidence of applicability.

### 5. Working memory

RAVEL may maintain a short-lived task workspace containing selected records, summaries, open hypotheses, evidence gaps, and current budgets. Working memory is disposable and must not silently become durable knowledge.

Durable promotion requires an explicit record transition.

## Promotion lifecycle

A useful lifecycle is:

```text
observation
  -> episode
  -> open hypothesis
  -> intervention
  -> attribution
  -> provisional principle
  -> transfer tested principle
  -> restricted strategy
  -> supported reusable strategy
```

Each transition requires evidence and authority appropriate to the new claim. Skipping stages should fail closed.

Example constraints:

- an episode cannot directly become a global strategy;
- a successful intervention cannot become causal attribution without evaluator support;
- an untested principle cannot authorize broad reuse;
- a failed transfer test must remain linked to the principle;
- a retired strategy remains retrievable; and
- external promotion requires evidence that repository-local development cannot create by itself.

## Retrieval policy

Retrieval should combine structured constraints with semantic search.

A safe order is:

1. filter by compatible schema and contract versions;
2. filter by mechanism and environment scope;
3. include negative records and counterexamples;
4. exclude retired or prohibited strategies unless requested for analysis;
5. rank by causal support, transfer support, recency where relevant, and semantic similarity;
6. return source identities and limitations with every result; and
7. require a new evaluation before reuse changes a candidate.

RAVEL should be able to retrieve the closest failure even when a success record is semantically more attractive.

## Knowledge compaction

Compaction should create new summary records without deleting source records. A summary must list its supporting and contradicting identities.

Possible compaction units include:

- repeated equivalent episodes;
- stable invariants across a candidate lineage;
- clusters of rejected hypotheses;
- strategy performance by context family; and
- provider-specific diagnostic details summarized behind a normalized contract.

Compaction must preserve enough source identity to reconstruct and challenge the summary.

## Chain-of-thought boundary

RAVEL does not need private chain-of-thought transcripts as durable memory. It should store inspectable products of reasoning:

- claims;
- alternatives;
- predictions;
- falsifiers;
- selected actions;
- evidence;
- outcomes;
- attribution; and
- uncertainty.

This creates a useful learning substrate without depending on hidden narrative traces that are difficult to verify, compare, or safely expose.

## First implementation milestone

The first knowledge-store milestone should support:

- canonical JSON schemas for core record types;
- SQLite-backed immutable insertion;
- content-addressed artifact storage;
- parent/reference validation;
- exact structured queries;
- negative-memory retrieval;
- deterministic export and replay;
- a rebuildable graph projection; and
- one end-to-end Forge episode from hypothesis through evaluation.

Vector retrieval, distributed storage, learned policy routing, and automated compaction should wait until the authoritative record semantics are stable and testable.
