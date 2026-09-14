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
and proof stop condition. `mncs-test` rejects stale plans and does not broaden
selection implicitly. The full impact graph remains retrievable as a compiler
artifact, but the normal reasoning interface is the compact plan.

Example:

```bash
ravel-impact tests/self_suite.mncs \
  --mncs /path/to/mncs \
  --library /path/to/mncs-language/library \
  --root 'mncs:0.2:function:tests.self_suite::arithmetic' \
  --output .mncs/verification-plan.json
mncs-test run --verification-plan .mncs/verification-plan.json ...
```

`ravel-impact` is a transport adapter around compiler and inventory commands;
selection policy is deterministic and no outside-language implementation is
claimed as semantic authority.
