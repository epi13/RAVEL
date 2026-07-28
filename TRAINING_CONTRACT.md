# RAVEL-T 0.2 readable training contract

## Intended use

RAVEL-T 0.2 is a deterministic mechanism study for recursive expert formation. It tests whether one bounded structure can serve simultaneously as model parameters, retrieval memory, routing geometry, training state, and computational budget.

It is not a general-purpose trainer or evidence that the method scales to neural foundation models.

## Task and data boundary

The development task is supervised classification over eight signed integer dimensions. A frozen synthetic teacher contains 64 separated latent regions and eight labels. Development and holdout samples use distinct fixed seeds.

The teacher construction is repository-visible. The holdout is therefore untouched by the training procedure but is not independently protected evidence.

## Recursive training behavior

Training begins with eight experts selected from development data. Each training round must:

1. build a routing lattice from the current expert centroids;
2. route every development sample through the same exact certificate and fallback authority used for inference;
3. update the selected expert's centroid and label statistics;
4. rank expert shards by unresolved classification error;
5. split bounded high-error shards into two child experts;
6. assign each child a deterministic lineage identity; and
7. rebuild the lattice before the next round.

The resulting loop is recursive: current experts determine routing; routing determines training shards; shard errors determine child experts; child experts regenerate the router; the regenerated router changes the next training observations.

## Machine-owned surface

The implementation may machine-manage:

- expert count between 8 and 64;
- expert centroids and labels;
- shard assignments;
- split order and child parameters;
- routing-lattice contents;
- exact-routing workload allocation; and
- lineage identities.

These artifacts are expected to be regenerated rather than manually maintained.

## Human authority surface

The recursive procedure must not alter:

- the development and holdout generators or seeds;
- the full-scan nearest-expert oracle;
- the exact route-certificate rule;
- the maximum of 64 experts;
- the maximum of eight births per growth round;
- tie-breaking behavior;
- development gates;
- formal-status fields; or
- the prohibition on automatic promotion.

A routed result is accepted only when it exactly agrees with the full-scan expert identity. Uncertainty spends more computation.

## Baselines

The same development data and holdout are evaluated against:

- a fixed eight-expert conventional nearest-centroid learner; and
- a flat 64-expert conventional learner initialized directly and refined by full scans.

Training expert-evaluation counts include initialization and refinement work.

## Preregistered development gates

The recursive candidate passes this repository-visible development protocol only when all are true:

- exactly 64 final experts and 56 successful child births;
- zero routed-versus-full-scan expert mismatches on holdout;
- holdout accuracy at least 0.95;
- holdout accuracy no more than 0.01 below the flat 64-expert baseline;
- holdout accuracy at least 0.20 above the fixed eight-expert baseline; and
- no more than 16 mean expert evaluations per holdout sample.

## Rollback and failure behavior

The full-scan implementation is the inference rollback. The fixed-topology learner is the training rollback. A failed gate produces development `FAIL`; it must not be rewritten as success by changing thresholds after observation.

## Claim boundary

A development `PASS` applies only to this deterministic synthetic mechanism study. It does not establish protected-holdout independence, real-data generalization, gradient-training compatibility, accelerator behavior, distributed training, continual-learning safety, resistance to data poisoning, production benefit, or formal MNCS/MNCDS conformance.

Formal MNCS and MNCDS status remain `UNKNOWN`, and promotion remains unauthorized.
