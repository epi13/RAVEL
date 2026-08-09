# Semantic consolidation and retrieval defragmentation

## Status

This document specifies a development prototype. The prototype now has named
scope-compatibility contracts, versioned evidence/experience identity fields,
deterministic source full-text retrieval, append-only proposal lifecycle events,
atomic source batches, and rebuildable relation projections. It does not
establish MNCS or MNCDS conformance, protected custody, production safety, or
validated recursive self-improvement.

## Motivation

Long-running memory systems accumulate duplicated statements, fragmented episodes, superseded conclusions, weak cross-links, and retrieval layouts that no longer match actual access patterns. A vector index can still locate approximate neighbors, but similarity alone does not preserve scope, authority, contradictions, negative evidence, or source identity.

RAVEL therefore separates two related maintenance operations:

1. **Semantic consolidation** reorganizes the logical representation of memory by proposing canonical summaries over compatible records.
2. **Retrieval defragmentation** reorganizes replaceable indexes, caches, shards, graph entry points, or storage pages according to observed co-access.

Neither operation may rewrite authoritative history.

## Invariants

The initial implementation enforces these invariants:

- Source memories are immutable and append-only.
- A consolidation is a new derived record, never an edit to a source record.
- Every proposal lists all member, supporting, contradicting, and superseded identities.
- Similarity cannot cross an incompatible scope boundary.
- Clustering confidence is a retrieval-quality estimate, not evidence authority or formal status.
- Explicit contradictions and negative memories remain retrievable.
- Retrieval layout plans are disposable projections and may be rebuilt from access events.
- No consolidation automatically promotes a principle or strategy.
- No memory operation can convert `UNKNOWN` into `PASS`.

## Architecture

```text
append-only source records
          |
          +------------------------------+
          |                              |
          v                              v
semantic consolidation             access telemetry
cluster compatible records          selected/retrieved IDs
preserve contradictions                  |
propose canonical view                   v
          |                       co-access planner
          v                              |
consolidation proposal                   v
          |                     retrieval layout plan
          +--------------+---------------+
                         |
                         v
              replaceable retrieval layer
        text / vector / graph / cache / page layout
```

The source store remains authoritative. Consolidation proposals and layout plans are projections.

## Semantic consolidation pipeline

### 1. Candidate partitioning

Records are first partitioned by memory class and a named scope-compatibility
contract. The default contract remains exact scope equality; an alternate
contract may be used only when its compatibility rule is explicit and tested.

### 2. Similarity grouping

The reference implementation uses deterministic token-set Jaccard similarity. This is deliberately simple:

- it is inspectable;
- it has no model dependency;
- it creates a measurable baseline; and
- it cannot silently change when an embedding provider changes.

Future embeddings may add candidate edges, but structured scope filters and provenance rules remain mandatory.

### 3. Representative selection

The canonical statement is selected deterministically using status, authority class, source support, timestamp, and logical identity. It is a representative statement, not an assertion that the other members have been disproven or deleted.

### 4. Contradiction preservation

The prototype uses explicit `contradicts` and `supersedes` relationships. It does not guess contradiction from language. A later contradiction detector may propose links, but those links must remain challengeable derived records until governed evaluation accepts them.

### 5. Retrieval keys

High-frequency non-stopword tokens and record tags become deterministic retrieval keys. These keys can seed exact search, graph entry points, or a semantic search query, but they do not establish applicability.

## Retrieval defragmentation

Physical disk defragmentation moved blocks to reduce seek cost. RAVEL's analogous operation is broader because memory can be physically and logically fragmented.

The prototype records query-level access events and counts how often selected memories are used together. Frequently co-selected records become a `RetrievalBucket` suggestion. A future adapter may use those buckets to:

- co-locate rows or blobs on storage pages;
- create cache or prefetch groups;
- choose graph entry points;
- produce shard-affinity hints;
- materialize joint summaries; or
- optimize batch vector reads.

The access planner never changes source content. A layout benchmark must compare candidate layouts under the same workload, cache state, storage medium, and resource budget.

## Record roles

### Source memory

A source record is an authoritative historical object within its declared authority class. It contains identity, memory class, statement, scope, producer, status, provenance, relations, and metadata.

### Consolidation proposal

A proposal contains:

- deterministic proposal identity;
- method version;
- memory class and scope;
- representative statement;
- member identities;
- supporting identities;
- contradicting identities;
- superseded identities;
- retrieval keys;
- clustering confidence; and
- explicit limitations.

### Retrieval layout plan

A layout bucket contains member identities and weighted co-access edges. It is replaceable and should be invalidated or rebuilt when workload behavior changes materially.

## Validation plan

The prototype should be evaluated against a preregistered workload with at least these comparisons:

1. raw chronological retrieval;
2. structured filtering only;
3. structured filtering plus semantic consolidation;
4. structured filtering plus access-layout planning; and
5. the combined approach.

Measure:

- retrieval latency and reads;
- relevant-record recall;
- negative-memory recall;
- contradiction recall;
- incorrect cross-scope merges;
- stale-summary selection;
- index rebuild cost;
- storage overhead;
- downstream verifier choice; and
- downstream task outcome under equal budgets.

A faster result is not sufficient if it hides negative evidence, increases false applicability, or weakens provenance.

## Implementation map

- `src/ravel/memory/models.py` defines source and derived records.
- `src/ravel/memory/store.py` provides an append-only SQLite prototype.
- `src/ravel/memory/consolidation.py` creates deterministic consolidation proposals and access-based layout plans.
- `schemas/consolidation-proposal.schema.json` specifies the portable proposal format.
- `tests/test_consolidation.py` verifies immutability, scope isolation, contradiction retention, determinism, and co-access planning.

## Next steps

1. Bind records to the complete versioned RAVEL evidence and experience schemas.
2. Record query events in the experience store with privacy and retention controls.
3. Add benchmark corpus measurements for retrieval quality, negative recall, and cost.
7. Benchmark physical page, cache, and shard layouts on the planned local and distributed RAVEL environments.
8. Add embedding-assisted candidate generation only after the deterministic baseline is measured.
