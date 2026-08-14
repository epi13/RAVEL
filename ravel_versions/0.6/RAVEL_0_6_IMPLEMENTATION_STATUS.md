# RAVEL 0.6 implementation status

This is a development status record, not RAVEL 0.6 evaluation evidence.

## Implemented and tested

- **R6-01 foundation:** candidate `ravel-0.6-candidate-001` is generated from
  the exact frozen 0.5 source identity. The temporary build record binds the
  frozen source, generator, generated source, compiler/version/argv, selected
  environment-key identities, worktree status, stdout, stderr, and exit
  status. Generated source is explicitly development-only.
- **Frozen policy source of truth:** `ravel.policy` validates the frozen 0.6
  preregistration and the explicitly inherited frozen 0.5 objective constant,
  derives transaction limits, and binds a deterministic threshold identity.
  The 0.6 record declares no numeric absolute compute cap or representation
  number; those remain explicit relative/`UNKNOWN` contract fields.
- **R6-02 integrated development transaction:** candidate-001 now wraps its
  existing adaptation primitive in a copy-before-evaluate transaction. The
  trial path records raw objective, retention, representation, prediction,
  transition-support, topology, replay, pass, and compute observations, then
  commits only when every hard gate passes. Rejection reasons use the Python
  vocabulary where the surfaces overlap, and rejected candidates restore the
  previous checkpoint byte-for-byte. This is a development mechanism
  disposition, not MNCS/MNCDS authority or a final evaluator.
- **R6-02 policy and matched-compute integration:** the C transaction uses the
  digest-bound two-pass, exact-256 replay, separate retention-floor/loss, and
  frozen ratio constants. Development trials emit raw candidate and
  fixed-topology work counts with a reconstructible ratio; Python derives the
  ratio independently without trusting the C disposition.
- **R6-03 behavioral fixtures:** a compiled harness reaches a goal only through
  transition slot one and checks that a born child has only spawning-event
  support. The candidate passes; frozen 0.5 and each reverted correction fail.
  Outputs are integer facts plus stable checksums. A C transaction mutation
  fixture also forces a retention gate failure and observes rollback.
- **R6-04 physical extraction and providers:** the generated source is
  losslessly emitted as ten component units plus a deterministic unity wrapper.
  The world/provider surface is now separately compiled under
  `ravel-0.6-world-abi/1`; branching and ring implement the same fixed-size
  init/reset/observe/transition contract. Provider selection is a linked object
  choice, not a mechanism source macro.
- **R6-04 bounded surfaces:** `world`, `transition`, `planning`,
  `mechanism_state`, and `checkpoint` provide dependency-free, deterministic
  interfaces with two independently defined toy providers. These surfaces
  reproduce the tested slot-one/unknown-route behaviors and detect checkpoint
  corruption. The generated C candidate now has an explicit transaction and
  observation surface. The checkpoint byte-comparison boundary is now compiled
  as a separate object under `ravel-0.6-checkpoint-abi/1`; unity and separate
  binaries are parity-tested. Build records now retain contract header,
  implementation/provider source, object, compile argv, compiler, dependency,
  unity-source, separate-binary, and unity-binary identities. Transition,
  planning, adaptation, and driver surfaces remain unity units.
- **Forge boundary and evaluator:** the project-local `mncs-forge.toml`
  declares bounded build, behavior, transaction, negative-matrix, parity,
  evaluator, bundle, package, lifecycle, and family-compatibility workflows.
  Its separate `ravel-0.6-forge-development-policy.json` is a project-scoped
  readiness plan only; it explicitly does not consume selection data.
  Forge 0.1.0a2 executed all declared workflows in a fresh local development
  ledger. Twelve bounded workflows were `PASS`; live family compatibility was
  `UNKNOWN` because sibling producer checkouts were unavailable. `ravel.development_evaluator` now reports
  mechanism, execution-integrity, matched-compute, evidence-completeness,
  provider, receipt, bundle, and aggregate statuses. Identity drift, malformed
  evidence, and missing required observations remain `UNKNOWN`; genuine hard
  mechanism failures remain `FAIL`.
- **MNCS evidence delegation:** `ravel.mncs_receipts` delegates receipt building
  and validation to optional MNCS Fabric/validator packages and carries only an
  explicitly observed execution record. Verifier `PASS`/`FAIL` never supplies
  exit code, argv, termination, streams, enforcement, or bundle-use facts.
  `ravel.mncs_bundles` delegates immutable bundle construction, archive
  validation, and receipt binding to MNCS; the local Forge runner is not claimed
  to have executed from a bundle unless it actually reports that fact.
- **R6-05 lifecycle infrastructure:** `ravel.lifecycle.CandidateLedger` is an
  append-only, hash-chained, gap-resistant development ledger with the
  preregistered candidate limit, freeze identities, partition separation,
  rejection retention, and a guard preventing selection feedback from entering
  the same candidate. No selection partition has been consumed.
- **Execution experience:** `ravel.experience.ExperienceRecord` converts raw,
  scoped execution outcomes into advisory episodic or negative memory records.
  It preserves `UNKNOWN`, rejection reasons, resource observations, and
  provenance rather than promoting remembered outcomes.
- **Execution-to-memory integration:** raw C development transaction records
  convert into uniquely identified, scoped advisory memory. Accepted raw
  executions remain `UNKNOWN` until governed disposition exists; rejected and
  unavailable outcomes remain negative and deterministic retrieval includes
  them.
- **Fabric development substrate:** `ravel.fabric` now defines the
  `ravel-fabric-workload/0.1` and `ravel-fabric-observation/0.1` boundaries,
  executes a bounded branching/ring provider-parity matrix through Fabric's
  public local controller/worker service, retains Fabric record/receipt/bundle
  identities, exercises challenge/replay and conflicting-request handling, and
  imports observations into advisory negative/`UNKNOWN` memory. Reconciliation
  is explicitly local in-process replication; it is not independence or final
  evaluation. The TLS-only network adapter is implemented but unavailable
  without operator trust material and pre-staged bundles.

## Not yet implemented or externally unavailable

- **Append-only memory log:** `ravel-memory-log/0.1` is a hash-chained JSONL
  log. Historical entries are never rewritten. Incomplete tails fail closed
  unless `TailPolicy::IgnoreIncompleteLastLine` is explicit. Projections are
  rebuilt on load. Curation counts typed proposals, not substring matches.

- **Interchange 0.2:** operation execution uses `operation_outcome=OK|ERROR`.
  `PASS/FAIL/UNKNOWN` remain evidentiary. `0.1` is rejected as an unsupported
  version.

- **Knowledge store milestone:** Rust now owns fail-closed knowledge promotion
  (`ravel-knowledge-record/0.1`), semantic consolidation / retrieval-layout
  parity with Python, compaction that never deletes sources, a content-addressed
  artifact store, and a curation report. Forge workflow `knowledge-lifecycle`
  proves the discrete surfaces. This does not authorize transfer, selection, or
  MNCS promotion.

- **Rust foundation:** the repository now has a Cargo workspace
  (`ravel-contracts`, `ravel-memory`, `ravel-core`, `ravel-cli`) under
  `ravel-rust-foundation/0.1`. Rust is the canonical future implementation
  language. Forge workflows `rust-build`, `rust-test`, `rust-python-parity`,
  and `rust-c-parity` prove discrete C/Python/Rust agreement for adaptation
  reasons, frozen policy identity, toy-world planning, canonical checkpoints,
  C transaction evaluation, and advisory experience class. This does not
  replace candidate-001 C, freeze the candidate, or create MNCS authority.

- The C-side trial is connected to `ravel.c_observations` through the versioned
  JSON record and shared reason vocabulary, with accepted and negative-path
  cross-checks. The parser/evaluator remains advisory and does not create
  formal evidence status; missing external disposition remains `UNKNOWN`.
- Additional separately compiled C ABI contracts, full cross-project evaluator
  lifecycle integration, and an absolute compute budget remain incomplete or
  are not declared by the frozen contract. Forge/RAVEL lifecycle mapping is
  reference-only and does not collapse the two state machines. Observation /
  reporting remains the next safe C extraction candidate after dependency review.
- The project-local Forge configuration now declares Fabric capability,
  reference, negative-matrix, and family-compatibility-lock workflows. The
  local Fabric path is optional for package import and ordinary CI.
- R6-05 selection evaluation and promotion logic have not been consumed. The
  ledger is infrastructure only; no candidate is frozen or selected by it.
- R6-06 external final custody/evaluation remains unavailable and `UNKNOWN`.

The 0.6 candidate remains unfrozen, unselected, unpromoted, and unauthorized
to alter evaluator identity, thresholds, partitions, evidence custody, or
formal MNCS/MNCDS status.
