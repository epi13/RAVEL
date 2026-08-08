# What prevented RAVEL from being a unified architecture

RAVEL 0.1 unified exact routing, retrieval, compressed experts, and conditional inference. RAVEL-T 0.2 added recursive expert birth and training. Those versions were still components rather than an architecture because the learned unit did not also own representation, reconstruction, action-conditioned prediction, temporal memory, planning, continual adaptation, retirement, checkpoint identity, and rollback equivalence.

RAVEL-U 0.3 closes that bounded architectural gap. One expert now simultaneously acts as:

- a retrieval key;
- a compressed representation of a state region;
- a reconstruction program;
- a classifier;
- an action-conditioned next-state predictor;
- a node in learned temporal memory;
- a planning destination;
- a training and replay shard;
- a lineage-bearing lifecycle object; and
- a measured unit of computational cost.

The same expert population builds the exact routing lattice, receives training assignments, identifies unresolved error, creates children, compiles its transition graph, supplies plans, adapts to semantic drift, and retires low-utility duplicate children. RAVEL 0.3 intended checkpoint restoration to reproduce both identity and behavior, but its digest and checksum were incomplete. RAVEL 0.4 supplies complete-field canonical identity, restored measurement comparison, and corruption tests.

## Intentionally external

RAVEL is not made safer or more complete by allowing the recursive execution plane to rewrite everything. The following remain outside its authority:

- raw modality adapters and data acquisition;
- intended-use and prohibited-use policy;
- evaluator, seeds, partitions, thresholds, and promotion decision;
- authorization for external effects;
- protected evidence custody;
- release signing and deployment;
- rollback approval; and
- formal MNCS or MNCDS status.

These are control surfaces, not missing intelligence components. Moving them into the recursive model would remove the independent boundary needed to evaluate, contain, replace, or retire it.

## Remaining scale gaps

RAVEL-U is a deterministic synthetic mechanism proof. It does not yet establish learned tokenization, language or multimodal generation, stochastic world modeling, gradient-scale optimization, distributed execution, long-horizon credit assignment, causal identification, protected real-data generalization, adversarial robustness, or production safety. Those are the next experimental domains, not hidden claims of this capsule.
