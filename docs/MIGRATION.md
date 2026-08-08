# RAVEL extraction from MNCS

## Decision

RAVEL should be extracted from the MNCS repository rather than recreated from memory or copied as an unrelated new project. The existing implementation, failed results, preregistrations, evidence records, manifests, contracts, and architectural limitations are part of RAVEL's identity.

A plain drag-and-drop copy would preserve the current bytes but discard the development history that explains why those bytes exist. The preferred migration therefore preserves the Git history of the RAVEL subtree.

## Frozen extraction point

The initial standalone extraction is anchored to:

- Source repository: `epi13/machine-native-complexity-standard`
- Source commit: `c521d47441905b36fc581a1c10e88282c6163f09`
- Primary subtree: `case-studies/ravel/`

The source commit includes the recursive-experience and causal-learning substrate added after the current RAVEL 0.6 preregistration.

## History-preserving procedure

The cleanest approach uses `git filter-repo` to retain only the RAVEL subtree while rewriting it to the root of the new repository.

```bash
git clone https://github.com/epi13/machine-native-complexity-standard.git ravel-extraction
cd ravel-extraction

git checkout c521d47441905b36fc581a1c10e88282c6163f09

git filter-repo \
  --path case-studies/ravel/ \
  --path-rename case-studies/ravel/:

git remote remove origin
git remote add origin https://github.com/epi13/RAVEL.git
git push origin HEAD:agent/import-mncs-history
```

This creates a branch whose history contains only commits that affected the RAVEL subtree. It should then be reviewed and merged through a pull request rather than force-pushed over `main`.

`git filter-repo` is intentionally preferred over `git filter-branch`. It must be installed separately on systems where it is not already available.

## Research currently outside the subtree

Two RAVEL-specific research tracks currently live outside `case-studies/ravel/` and therefore will not be included by the subtree extraction:

- `docs/recursive-architecture-research.md`
- `docs/recursive-experience-substrate.md`
- `studies/recursive-architecture-comparison/`
- `studies/recursive-experience-substrate/`

After the primary history extraction, import these into the standalone repository under:

```text
research/recursive-architecture-research.md
research/recursive-experience-substrate.md
studies/recursive-architecture-comparison/
studies/recursive-experience-substrate/
```

These additions should retain a migration record that names their MNCS source paths and source commit. They may be imported in a second commit or a separate PR so the executable RAVEL history remains easy to audit.

## What should remain unchanged during extraction

The first import should avoid cosmetic restructuring of frozen material. In particular:

- do not rename versioned evidence, manifests, preregistrations, contracts, or source files;
- do not rewrite historical `FAIL` or `UNKNOWN` results;
- do not regenerate evidence merely because repository paths changed;
- do not weaken digests or remove files from ordered source manifests;
- do not relabel development observations as independent or protected evidence; and
- do not delete the MNCS copy until the standalone checks and provenance links are verified.

The initial objective is a faithful extraction, not architectural cleanup.

## Standalone repairs after extraction

Once the history-bearing branch exists, a follow-up commit should:

1. replace case-study framing in the root README with the standalone project description;
2. add a repository-root CI workflow that runs the existing local RAVEL `Makefile` targets;
3. repair links that assume the MNCS documentation tree;
4. add provenance links back to the MNCS source commit;
5. verify every source-manifest and assurance digest before changing layout;
6. identify which root MNCS build targets need equivalents in RAVEL; and
7. document the supported Forge interface separately from the historical mechanism studies.

## MNCS follow-up

Only after the standalone import is reproducible should MNCS receive a separate PR that:

- marks its RAVEL directory as the historical in-repository record;
- links prominently to the standalone RAVEL repository;
- moves new RAVEL development to the standalone repository;
- keeps any frozen evidence required to reproduce old MNCS commits; and
- avoids a submodule until there is a clear reason to bind MNCS builds to a specific RAVEL commit.

A plain link is initially safer than a submodule because MNCS should define standards and integration boundaries without silently making its core checks depend on RAVEL's moving development branch.

## Why not copy everything immediately?

RAVEL contains evidence whose meaning depends on protocol, identity, ordering, and development history. Copying files is acceptable as a temporary snapshot, but it is not the preferred canonical migration because it loses the commit sequence that records failed approaches, evaluator corrections, and frozen decisions. The new repository should begin with that history intact wherever practical.
