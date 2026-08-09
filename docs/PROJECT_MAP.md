# RAVEL project map

Project-level metadata stays at the repository root. Version-bound source and
evidence are grouped under `ravel_versions/`; historical manifest path strings
remain unchanged and are resolved by the versioned compatibility runners.

## Implementations and authority

| Epoch | Implementation | Contract or authority |
|---|---|---|
| 0.1 | `ravel_versions/baseline/ravel.c` | `ravel_versions/baseline/CONTRACT.md` |
| 0.2 | `ravel_versions/training/ravel_train.c` | `ravel_versions/training/TRAINING_CONTRACT.md` |
| 0.3 | `ravel_versions/unified/ravel_unified.c` plus its `.inc` files | `ravel_versions/unified/UNIFIED_CONTRACT.md` |
| 0.4 | `ravel_versions/0.4/ravel_0_4.c` | `ravel_versions/0.4/RAVEL_0_4_CONTRACT.md` |
| 0.5 | `ravel_versions/0.5/ravel_0_5.c` | `ravel_versions/0.5/RAVEL_0_5_CONTRACT.md` |
| 0.6 | Candidate source is derived by `tools/ravel_0_6_seed_candidate.py` | `ravel_versions/0.6/RAVEL_0_6_SCOPE.md` and preregistration |

Candidate-001 development builds are orchestrated by
`tools/ravel_0_6_build.py`; generated source and binaries are temporary
development material, not maintained source or final evidence. Behavioral
facts are produced by `tools/ravel_0_6_behavioral_fixtures.py`.

Build binaries are local outputs and are removed by `make clean`.

## Protocol, evidence, and identity

The baseline, training, and unified records live beside their implementation in
`ravel_versions/baseline/`, `ravel_versions/training/`, and
`ravel_versions/unified/`. The 0.4, 0.5, and 0.6 directories each contain their
scope or preregistration, contracts, source, observations, manifests, assurance
records, limitations, and results or development material.

The source identity records are:

| Epoch | Identity records |
|---|---|
| 0.4 | `ravel_versions/0.4/ravel-0.4-source-manifest-spec.json` and `ravel_versions/0.4/ravel-0.4-source-manifest.json` |
| 0.5 | `ravel_versions/0.5/ravel-0.5-source-manifest-spec.json` and `ravel_versions/0.5/ravel-0.5-source-and-execution-manifest.json` |

The manifest contents retain their historical logical paths. The compatibility
runners map those identities to their current physical locations without
regenerating the frozen records.

## Documentation and tooling

- [Version history](VERSION_HISTORY.md) explains each epoch and preserves its
  recorded outcomes.
- [Evidence guide](EVIDENCE_GUIDE.md) explains the evidence layers and claim
  boundaries.
- [Architecture gaps](ARCHITECTURE_GAPS.md) records the early design gaps.
- [`../tools/README.md`](../tools/README.md) documents evaluators, digest tools,
  mutation checks, runtime capture, and 0.6 candidate derivation.
- `src/ravel/adaptation.py` provides the tested retention-transaction boundary.
- `src/ravel/providers.py` and `src/ravel/resources.py` provide optional,
  replaceable Forge/runtime protocols without heavy ML dependencies.
- `src/ravel/world.py`, `src/ravel/transition.py`, and `src/ravel/planning.py`
  provide deterministic provider/compiler/planner surfaces with two toy worlds.
- `src/ravel/mechanism_state.py` and `src/ravel/checkpoint.py` define the
  evaluator-free state and canonical checkpoint boundary.
- `src/ravel/lifecycle.py` provides development-only append-only candidate
  freeze/selection infrastructure; it has not consumed selection data.
- `src/ravel/experience.py` binds scoped execution outcomes to advisory memory,
  retaining negative and `UNKNOWN` outcomes.
- `src/ravel/policy.py` is the fail-closed frozen 0.6 policy loader; generated
  C constants carry its threshold identity.
- `src/ravel/matched_compute.py` validates raw development comparator counts and
  ratios without producing formal authority.
- `tools/ravel_0_6_decompose.py` losslessly emits generated C component units
  and a unity wrapper; `ravel_versions/0.6/ravel_0_6/README.md` documents the
  current unity-build limitation.
- [`MIGRATION.md`](MIGRATION.md) records the standalone extraction provenance.

## Build and verification entry points

From the repository root, the main checks are:

- `make test`
- `make training-check`
- `make unified-check`
- `make 0.4-check`
- `make 0.5-check`

Additional compiler-matrix, sanitizer, runtime, checkpoint, lineage, negative,
and mutation targets remain available in the root Makefile.

## Placement rule

Cross-version explanation belongs under `docs/`; executable support tooling stays
under `tools/`; version-bound material belongs under `ravel_versions/`. Physical
moves of historical artifacts are acceptable only when their bytes and recorded
logical identities remain intact. Recorded `FAIL`, `UNKNOWN`, and non-promotion
outcomes are not rewritten.
