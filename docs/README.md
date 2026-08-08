# RAVEL documentation hub

This directory is the human-navigation layer for the standalone RAVEL project.
It does not replace versioned contracts, preregistrations, raw observations,
manifests, or assurance records under `../ravel_versions/`.

## Guides

- [Version history](VERSION_HISTORY.md) — what changed in each epoch, preserved
  results, and current development status.
- [Project map](PROJECT_MAP.md) — where to find implementations, contracts,
  evidence, manifests, plans, and tooling.
- [Evidence guide](EVIDENCE_GUIDE.md) — how the evidence layers relate and what
  conclusions they do and do not support.

## Authoritative material remains versioned

Use the guides above to locate the authoritative files, then read those files
directly. In particular:

- Markdown contracts define readable behavioral authority;
- preregistration JSON defines frozen protocol and gates;
- C source defines the maintained mechanism for its epoch;
- raw observation JSON records executable output;
- evaluator-derived evidence records interpretation of those observations;
- source and execution manifests bind identity;
- assurance cases state the bounded disposition and unresolved limitations.

Documentation may summarize those records but must not silently upgrade their
claims.

## Placement rule

Add explanatory, cross-version, or navigational material here. Keep executable
support scripts under `../tools/`. Keep version-bound contracts, source,
preregistrations, observations, manifests, and assurance records under
`../ravel_versions/` unless a new epoch explicitly defines a different layout
and identity scheme.
