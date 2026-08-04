# Recursive architecture comparison study

This directory defines a bounded, post-RAVEL-0.6 research track for comparing
alternative recursive development architectures under one immutable evaluation
boundary.

The study distinguishes:

- parameter recursion;
- structural recursion;
- policy recursion; and
- portfolio-level recursion across competing proposer architectures.

It does not modify frozen RAVEL epochs or claim that the current repository has
implemented autonomous recursive self-improvement.

## Files

- `study-plan.json` — machine-readable architecture arms, controls, metrics,
  permissions, budgets, stop rules, and required negative tests;
- `validate_study.py` — standard-library validator for the research boundary; and
- `test_validate_study.py` — executable positive and negative fixtures.

## Run

From the repository root:

```console
python studies/recursive-architecture-comparison/validate_study.py
python studies/recursive-architecture-comparison/test_validate_study.py
make recursive-architecture-study-check
```

## Architectures

| ID | Recursive surface | Purpose |
|---|---|---|
| `manual-repair` | none inside generator | Governed human baseline |
| `structural-expert` | parameter and topology | RAVEL-style fixed-policy recursion |
| `candidate-lineage` | implementation replacement | Evidence-guided child candidates |
| `policy-meta` | structural-policy replacement | Test improvement of the improvement policy |
| `governed-portfolio` | budget allocation across proposers | Test competing recursive architectures |

Controls include random proposal, shuffled feedback, diagnostic ablation, and fixed
policy. Every recursive arm is evaluated under the same candidate and operation
budgets before portfolio allocation can adapt.

## Boundary

The recursive surface may never modify evaluator identity, thresholds, partitions,
resource ceilings, final custody, or promotion authority. Candidates are immutable
after evaluation. Descendants are new identities, rejected transactions preserve the
parent byte-for-byte, and failed lineages remain in the record.
