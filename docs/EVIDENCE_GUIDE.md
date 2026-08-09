# RAVEL evidence guide

RAVEL separates protocol, implementation, observations, interpretation, identity,
and authority. A file that reports a passing check does not automatically prove
that the mechanism passed its frozen study or that the study has independent or
protected evidence.

## Evidence layers

### 1. Scope and preregistration

Examples: `ravel_versions/0.6/RAVEL_0_6_SCOPE.md`,
`ravel_versions/0.6/RAVEL_0_6_PREREGISTRATION.md`, and
`ravel_versions/0.6/ravel-0.6-preregistration.json`.

These files define the question, candidate limits, partitions, seeds, gates,
change rules, and claim boundaries before evaluation. They establish the
protocol, not the outcome.

### 2. Readable contract

Examples: `ravel_versions/0.4/RAVEL_0_4_CONTRACT.md` and
`ravel_versions/0.5/RAVEL_0_5_CONTRACT.md`.

The contract explains required behavior and limits in human-readable form. It is
an authority surface for review, but it does not prove the source implements the
contract.

### 3. Mechanism source

Examples: `ravel_versions/0.4/ravel_0_4.c` and
`ravel_versions/0.5/ravel_0_5.c`.

The maintained source defines the executable mechanism. For a generated 0.6
candidate, the generator, frozen input identity, transformation rules, and output
identity are all part of the implementation story.

### 4. Raw observations

Examples: `ravel_versions/0.4/ravel-0.4-raw-observations.json` and
`ravel_versions/0.5/ravel-0.5-raw-observations.json`.

These records should contain facts emitted by the executable, such as counts,
checksums, predictions, topology, resource measurements, and integrity facts.
They should not silently declare their own authoritative verdict when an
external evaluator is responsible for deriving it.

### 5. Evaluator-derived evidence

Examples: `ravel_versions/0.5/ravel-0.5-trial-evidence.json` and
`ravel_versions/0.5/ravel-0.5-negative-evidence.json`.

The evaluator checks the frozen matrix, validates record structure, derives
metrics, applies hard gates, rejects contradictions, and preserves failures. The
evaluator can establish whether the supplied observations satisfy the declared
protocol; it cannot establish protected custody or organizational independence
merely because it is a separate program.

### 6. Source and execution identity

Examples: `ravel_versions/0.4/ravel-0.4-source-manifest.json` and
`ravel_versions/0.5/ravel-0.5-source-and-execution-manifest.json`.

These records bind ordered files, digests, compiler or execution details, and
other identity facts. They answer which implementation and execution surface the
evidence refers to. They are why renaming or moving frozen files may be a
material change rather than harmless cleanup.

### 7. Assurance case

Examples: `ravel_versions/0.4/ravel-0.4-assurance-case.json` and
`ravel_versions/0.5/ravel-0.5-assurance-case.json`.

The assurance case combines the available facts into a bounded disposition. It
should retain limitations, `UNKNOWN` conditions, failed gates, and explicit
non-promotion fields.

### 8. Human-readable results and postmortems

Examples: `ravel_versions/0.4/RAVEL_0_4_RESULTS.md`,
`ravel_versions/0.5/RAVEL_0_5_RESULTS.md`, and
`ravel_versions/0.5/RAVEL_0_5_POSTMORTEM.md`.

These files explain the evidence to readers. They are useful summaries, but the
underlying JSON and source identities remain the auditable basis.

### 9. Runtime observations

Example: `ravel_versions/0.5/ravel-0.5-runtime-observations.json`.

Wall-clock timing is host-specific and non-normative. Deterministic expert,
operation, or evaluation counts are the canonical work measures unless a
separate protocol explicitly defines cross-host performance evidence.

For RAVEL 0.6 development, `ravel.policy` binds the machine-readable
preregistration digest (and the explicitly inherited frozen 0.5 objective
constant) into the generated C threshold identity. The matched-compute record
contains raw candidate/comparator work counts and an integer ratio; the
candidate does not emit a formal compute PASS. The Python parser independently
reconstructs the ratio, and an absent comparator remains `UNKNOWN`.

## Distinct result questions

RAVEL reports several different questions that must not be collapsed:

| Question | Typical value |
|---|---|
| Did the executable run and produce structurally valid observations? | execution integrity |
| Did a trial satisfy every frozen mechanism gate? | per-trial result |
| Did every required trial satisfy the aggregate rule? | development result |
| Is the source and execution identity complete and verified? | identity assurance |
| Was evaluation protected from the developer and independently operated? | custody and independence |
| Does the package satisfy formal MNCS or MNCDS requirements? | formal status |
| Is release or promotion authorized? | governance disposition |

A `PASS` in one row does not imply `PASS` in another.

## Preserved RAVEL outcomes

- RAVEL 0.4: execution produced evidence, but zero of eight frozen trials passed
  all gates; development result `FAIL`.
- RAVEL 0.5: execution integrity `PASS`; 24 of 32 trials passed; the all-trials
  development result remains `FAIL`.
- RAVEL 0.6: preregistered development and candidate preparation exist, but
  selection, future-final evaluation, protected custody, independent operation,
  formal conformance, and promotion remain `UNKNOWN` or unauthorized.

## What repository-local evidence cannot manufacture

Repository-local source, hashes, signatures, containers, test runners, and
separate evaluator programs cannot by themselves establish:

- protection from a user with root or repository administration access;
- future-final seed secrecy from the developer;
- organizational independence;
- independent custody or witness authority;
- uncontaminated real-world data;
- production safety or operational readiness; or
- governance approval.

Those claims require external facts and actors, not stronger wording around
local files.

## Review checklist

Before accepting a RAVEL result or modifying the directory, verify:

1. the exact epoch and candidate identity;
2. the applicable preregistration and contract;
3. whether the source is maintained or generated;
4. whether raw observations are unchanged and complete;
5. which evaluator derived the result;
6. whether negative and mutation evidence is retained;
7. whether manifests bind every required file and execution fact;
8. whether failures and `UNKNOWN` conditions remain visible; and
9. whether the proposed change affects a frozen identity or claim boundary.
