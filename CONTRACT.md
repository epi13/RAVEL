# RAVEL 0.1 readable contract

## Intended use

RAVEL 0.1 is a research component for exact conditional dispatch over a generated store of quantized experts. It tests whether a machine-generated routing lattice can reduce expert evaluations on familiar inputs while preserving the result of a complete reference scan.

## Input and reference behavior

A query contains eight signed 8-bit values. The declared in-domain range is `[-64, 63]` in every dimension.

For every expert, the reference computes squared Euclidean distance between the query and expert centroid. It selects the minimum distance, resolving equal distances in favor of the lower expert identifier. It executes the selected expert as an integer dot product plus bias.

## Candidate authority

The candidate retrieves 24 generated experts from one lattice cell. It may return without a complete scan only when the routed winner's distance is strictly lower than the precomputed minimum possible distance of every excluded expert.

Equality is not accepted. Uncertain or out-of-domain requests must scan every excluded expert before returning.

Candidate output must exactly match the reference for expert identity, distance, and execution score.

## Invariants

1. Routing uncertainty never counts as success.
2. Out-of-domain values force fallback.
3. Each expert is evaluated at most once per query.
4. Candidate work is bounded between 24 and 256 expert evaluations.
5. Tie behavior is deterministic and reference-equivalent.
6. The complete oracle remains available as rollback.

## Development gates

On the declared familiar workload:

- zero output mismatches;
- at least 95% certified routes; and
- no more than 32 mean expert evaluations.

The uniform control workload requires exactness but does not require acceleration. Refusing unjustified shortcuts is expected.

## Claim boundary

This experiment is not a trained foundation model, production inference server, proof of generalization, or formal MNCS/MNCDS claim. Formal status remains `UNKNOWN` until independent protected evaluation and lifecycle evidence exist.
