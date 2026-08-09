# RAVEL 0.6 Codex implementation queue

This document converts the post-0.5 technical review into bounded development
work for RAVEL 0.6. It is operational guidance, not a change to the frozen 0.6
preregistration, and it does not authorize a result or promotion.

## Immutable boundaries

A Codex agent working from this queue must preserve all of the following:

- do not edit or relabel RAVEL 0.4 or 0.5 source, seeds, evidence, manifests,
  gates, results, or dispositions;
- do not use RAVEL 0.5 final observations as RAVEL 0.6 final evidence;
- do not obtain, derive, or inspect future-final RAVEL 0.6 seed material;
- do not weaken gates after observing development or selection outcomes;
- do not describe repository-local executable separation as independent
  operation, protected custody, or organizational independence; and
- retain `UNKNOWN` and failed results without converting them to `PASS`.

## Completed bounded preparation

The first 0.6 development seed is now derived reproducibly from the exact frozen
0.5 source by `tools/ravel_0_6_seed_candidate.py`.

The derivation completes two small, reviewable corrections:

1. **Use both supported transition targets in planning.** The 0.5 graph stores
   two support-bearing targets per expert/action, but its BFS traverses only
   target zero. Candidate 001 traverses all `TRANSITION_TOP_K` slots in stable
   slot order.
2. **Remove inherited empirical support from adaptation births.** A new
   adaptation expert no longer copies parent counts, errors, action counts,
   transition targets, transition support, or unused action predictions. It
   begins with only the spawning event's label, action, observation, and
   next-observation support while retaining deterministic generation and
   lineage derivation.

The generator refuses any source whose SHA-256 differs from the frozen 0.5
identity and requires every transformation to match exactly once. Tests verify
source identity, transformation semantics, deterministic output, read-only
checking, and strict C11 compilation.

These corrections produce development source only. Candidate 001 is now
integrated into a local development trial path, but remains unselected,
unfrozen, and unevaluated for preregistered selection/final purposes.

## Current bounded implementation status

Candidate-001 is now integrated as a reproducible temporary development build
by `tools/ravel_0_6_build.py`. Its trial path wraps the existing adaptation
primitive in an all-hard-gates copy/observe/commit transaction and emits raw
structured observations with stable rejection reasons. The frozen policy is
loaded once at generation time, and matched-compute work is emitted as a
separate raw development record. A compiled behavioral harness verifies both
corrections and fails against frozen 0.5 behavior and bounded reverted
mutations. Python component surfaces and the generated C unity extraction
provide two independent providers, deterministic planning, canonical
checkpoints, and an append-only development candidate ledger. The checkpoint
byte-comparison operation is separately compiled under
`ravel-0.6-checkpoint-abi/1`; the unity binary remains a parity oracle. An
optional concrete Forge CLI adapter and delegated MNCS receipt validation
preserve external boundaries. These are
implementation and local development observations only; no selection or final
material has been consumed. See `RAVEL_0_6_IMPLEMENTATION_STATUS.md` for the
exact boundary.

### Queue disposition after the current iteration

- **R6-01:** provenance/build foundation complete; generated component and
  policy identities are now included in temporary build records.
- **R6-02:** integrated for the local development transaction and matched raw
  comparator; the frozen contract has no numeric absolute compute cap, so that
  separate gate remains undeclared rather than invented.
- **R6-03:** behavioral and C/Python negative fixtures complete for declared
  constraints; source-constant mutations are intentionally distinguished from
  Python frozen-policy mutations and remain manifest-detectable.
- **R6-04:** checkpoint and world/provider boundaries are separately compiled
  and parity-tested against unity for both branching and ring. Transition,
  planning, adaptation, and driver surfaces remain unity units. The next safe
  ABI candidate is observation/reporting, after dependency review.
- **R6-05:** ledger infrastructure is hardened and exercised only with
  development fixtures. Candidate-001 remains unfrozen because further
  implementation changes are still expected.
- **R6-06:** external custody and evaluation remain unavailable/`UNKNOWN`.

The next logical implementation task is to review and, if independently
falsifiable, promote the observation/reporting boundary. Do not freeze
candidate-001 or consume selection partitions until further implementation,
policy parity, and the full development trial matrix are stable.

## Codex next steps

Perform the following tasks in order. Treat each material post-evaluation change
as the next candidate identity required by the preregistration.

### R6-01 — Integrate candidate 001 without weakening provenance

**Goal:** Make the derived source an explicit, reproducible RAVEL 0.6
development candidate.

**Work:**

- add a dedicated 0.6 build target that generates into a temporary or declared
  generated-source location;
- bind the frozen 0.5 input identity, generator identity, generated source
  identity, compiler executable, compiler version, argv, environment-key names,
  stdout, stderr, and exit status;
- record that 0.6 source is generated while 0.5 remains directly maintained and
  immutable;
- add clean-worktree and stale-output checks; and
- ensure no generated 0.6 artifact is mistaken for final evidence.

**Acceptance:**

- two clean derivations are byte-identical;
- source substitution, generator substitution, stale output, omitted input,
  ordering, and build-command mutations fail;
- candidate identity is exactly `ravel-0.6-candidate-001`; and
- all 0.4 and 0.5 source and evidence digests remain unchanged.

### R6-02 — Implement transactional retention-constrained adaptation

**Goal:** Replace the soft blended acceptance decision with the preregistered
all-constraints transaction.

**Work:**

- evaluate each proposed birth, refinement, retirement, or combined update on a
  copy of the preceding model;
- require the declared adaptation improvement epsilon;
- require base-task accuracy and representation floors;
- require original-task prediction degradation to remain inside its bound;
- reject any update that removes uniquely supported transition behavior;
- enforce expert, birth, retirement, replay, pass, and compute budgets; and
- when any condition fails, retain the preceding model byte-for-byte and record
  a structured rejection reason.

**Acceptance:**

- a rejected update has an identical checkpoint digest before and after;
- every hard condition has a distinct negative fixture;
- no metric may compensate numerically for failure of another hard condition;
- the raw executable emits observations and reason codes, never its own
  development verdict; and
- the independent evaluator alone derives gate and aggregate results.

### R6-03 — Add behavioral regression fixtures for both review corrections

**Goal:** Demonstrate behavior rather than relying only on source inspection.

**Work:**

- construct a graph where the only valid route to a goal uses transition slot
  one and prove bounded planning reaches it;
- construct a parent with unrelated labels, actions, counts, errors, and
  transitions, birth a child, and prove the child claims only spawning-event
  support before refinement;
- prove unsupported child actions remain unknown;
- prove deterministic edge order and tie breaking; and
- mutate either correction back to the 0.5 behavior and require the fixture to
  fail.

**Acceptance:**

- both fixtures fail against the corresponding 0.5 behavior;
- both pass against candidate 001;
- fixture outputs are raw integer facts with stable checksums; and
- the evaluator rejects missing, duplicated, or contradictory fixture results.

### R6-04 — Separate mechanism, environment, planning, and evidence surfaces

**Goal:** Reduce the coupling created by the single 0.5 translation unit without
changing the frozen 0.5 record.

**Work:**

- define narrow interfaces for events/world providers, mechanism state,
  transition compilation, planning, checkpoint encoding, and observation
  emission;
- move the synthetic world behind the provider interface;
- keep deterministic allocation and bounded memory;
- provide a second independently written toy environment fixture; and
- bind all maintained and generated units in source/execution identity.

**Acceptance:**

- the mechanism builds against both environment providers without conditional
  edits to its core;
- provider substitution changes only declared provider identities and evidence;
- no holdout or evaluator authority enters the mechanism interface; and
- the split implementation reproduces candidate behavior before any further
  mechanism change.

### R6-05 — Execute the preregistered development and selection lifecycle

**Goal:** Use the already declared partitions and candidate limit correctly.

**Work:**

- run development trials only on development partitions;
- freeze each candidate identity before its selection evaluation;
- prevent selection observations from becoming same-candidate repair input;
- retain all candidates, failures, resource measurements, and rejection reasons;
  and
- stop after candidate 008 unless a new preregistration revision or epoch is
  created.

**Acceptance:**

- development, selection, retention, transition-retention, and planning
  identities are distinct and verified;
- the candidate ledger is append-only and gap-free;
- selection evidence cannot alter the evaluated candidate; and
- no future-final seed or observation exists in repository-controlled
  development material.

### R6-06 — Obtain external final custody and evaluation

**Goal:** Address the evidence gap that local code cannot manufacture.

**Work requiring a human/external actor:**

- assign a final-seed custodian and final evaluator distinct from the
  development generator;
- freeze candidate, evaluator, thresholds, commands, and identities before the
  final material is opened;
- run the one-shot final evaluation outside the development account's custody;
- retain raw observations, failures, `UNKNOWN`s, contamination facts, resource
  limits, signatures, and timestamps; and
- report mechanism result, execution integrity, MNCS status, MNCDS status, and
  promotion authorization as separate fields.

**Acceptance:**

- custody and evaluator records identify actors, conflicts, reviewed artifacts,
  dates, and exact identities;
- development operators cannot access final material before candidate freeze;
- final evidence is not used for same-epoch repair; and
- absence of eligible external evidence remains `UNKNOWN`, never locally
  synthesized `PASS`.

## Later research tracks, not 0.6 completion criteria

Do not fold these into the narrow 0.6 hypothesis merely to enlarge the claim:

- real-data representation and distribution-shift studies;
- language or multimodal adapters;
- stochastic or probabilistic transition models;
- long-horizon planning and credit assignment;
- heterogeneous-host, accelerator, and distributed execution;
- operational monitoring, authorization, signed releases, and rollback drills;
  and
- comparison with externally implemented continual-learning systems.

Each requires its own contract, preregistration, evidence boundary, and claim
language.

## Recommended Codex completion report

For every task, report:

1. exact files and candidate identity changed;
2. frozen identities checked before work;
3. tests and mutation tests executed;
4. observed failures and unresolved `UNKNOWN`s;
5. whether material evaluation occurred;
6. whether a new candidate identity was required; and
7. an explicit statement that no conformance, independence, custody, or
   promotion claim was created unless external evidence actually establishes it.
