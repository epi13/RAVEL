# Selective MNCS verification

RAVEL is the bounded selection layer for the MNCS development loop. It does
not parse source or rebuild dependency graphs. `ravel-impact` asks the pinned
MNCS compiler for `mncs.semantic-impact/1`, joins the compiler-owned test
inventory, and emits `mncs.verification-plan/1` for `mncs-test`.

```text
compiler semantic graph
        ↓ bounded impact projection
RAVEL selection policy
        ↓ digest-bound plan
mncs-test exact test-case execution
        ↓ check/result/evidence references
Forge and Actions orchestration
```

The transport contract is family-owned by MNCS-Commons at
`src/mncs_commons/verification_plan.py` and
`schemas/mncs-verification-plan-1.schema.json`. RAVEL does not carry a second
schema or vocabulary. Its normal entrypoint invokes the MNCS-native
`ravel.verification_policy::choose` policy module through the typed
`SelectionInput` host boundary (`mncs.typed-call/1`); the small
Python policy function remains only as a compatibility adapter for callers
that cannot provide the native runtime. Plan identity is lower-case SHA-256 of
canonical JSON with `plan_id` removed.

The policy is deliberately fail-closed:

- a known implementation root with no dependent edges selects the changed
  item's compiler identities;
- direct dependents select the compiler-reported affected test cases;
- explicit contract, type, parser, serialization, effect, ABI, profile,
  fixture, or cross-repository changes carry a typed escalation reason;
- unknown roots, truncated neighborhoods, and unjoinable tests escalate to a
  repository or family boundary rather than pretending a narrow proof exists.

The plan binds the exact source digest, subject identity/fingerprint, graph
identity, selected test-case identities, level, risk flags, escalation reasons,
and proof stop condition. A source/module test inventory is not a
`repository_canonical` proof: that level requires a repository-scoped executor
and canonical-suite evidence. A `family` plan is routing evidence until the
family proof boundary is established. `mncs-test` rejects stale plans and does
not broaden selection implicitly. The full impact graph remains retrievable as
a compiler artifact, but the normal reasoning interface is the compact plan.

Cross-repository contract changes use the Commons digest-bound family overlay:
the local compiler graph supplies semantic impact, while the overlay supplies
declared producer/consumer edges with contract identity, revision, consuming
identity, provenance, and edge fingerprint. RAVEL selects only the declared
consumer repositories. An incomplete overlay adds
`cross_repository_graph_incomplete` and keeps the plan non-stopping.

Plan provenance records the source, semantic graph, inventory subject, family
graph, selected identities, and contract revision so Actions receipts and
Forge can invalidate only evidence whose dependencies changed.

Example:

```bash
ravel-impact tests/self_suite.mncs \
  --mncs /path/to/mncs \
  --library /path/to/mncs-language/library \
  --root 'mncs:0.2:function:tests.self_suite::arithmetic' \
  --output .mncs/verification-plan.json
mncs-test run --verification-plan .mncs/verification-plan.json ...
```

When a family graph is supplied from a specific Commons checkout, pass that
checkout explicitly with `--commons-root`. This binds graph loading, plan
identity, and plan validation to the same contract snapshot; Forge supplies
the option automatically during post-repair replanning.

`ravel-impact` remains the process/filesystem adapter around compiler and
inventory commands. Selection policy is deterministic and native in the normal
path; the adapter does not become semantic authority merely because it
serializes or validates the result.

For MNCS source paths, the compiler can return semantic impact and its
compiler-owned source test inventory from one front-end session with
`mncs impact --include-test-inventory`. RAVEL consumes that inventory from the
same response and does not launch a second cold source compilation. When a
repository provides a canonical external verification-obligation inventory,
that inventory supplies repository verification selection directly; source
test inventory remains separate evidence about compiler-recognized local
tests and is not required to plan the repository obligations.
