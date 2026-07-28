# RAVEL-U 0.3 unified architecture contract

## Intended use

RAVEL-U is a bounded research architecture for testing whether one recursively managed expert population can provide exact retrieval, compressed representation, reconstruction, classification, action-conditioned prediction, temporal memory, planning, continual adaptation, lifecycle compression, and checkpoint rollback under one deterministic protocol.

## Event contract

Each event contains an eight-dimensional signed observation, one of four actions, one of eight labels, and the next observation. The declared value range is `[-64, 63]` in every dimension.

## Expert contract

Every active expert contains one retrieval key, one reconstruction vector, four action-conditioned next-observation vectors, a label distribution, usage and error statistics, generation metadata, and lineage identity. The compiled transition graph maps each expert and action to the expert nearest its predicted next observation.

## Routing authority

The generated lattice evaluates eight candidates. It may return early only when the selected distance is strictly lower than the mathematical lower bound for every excluded expert. Equality, malformed input, or insufficient separation requires the complete scan. Routed and complete scans must select the same expert.

## Recursive development authority

The mutable execution plane may update expert parameters, rank overloaded shards, create bounded child experts, rebuild routing and transition structures, replay retained events, and retire low-utility adaptation children. It may not change data seeds, partitions, topology limits, evaluator behavior, gates, formal-status fields, or promotion authority.

## Required behavior

The same learned expert store must support:

1. exact retrieval relative to the full-scan oracle;
2. label prediction;
3. observation reconstruction;
4. action-conditioned next-observation prediction;
5. transition-graph compilation;
6. bounded graph planning;
7. semantic-drift adaptation with replay;
8. bounded expert birth and retirement; and
9. checkpoint restoration with matching identity and evaluation behavior.

## Development gates

- base holdout accuracy at least 0.95;
- adapted drift accuracy at least 0.95;
- adapted drift gain over the static model at least 0.20;
- original-task retention after adaptation at least 0.90;
- adapted transition accuracy at least 0.95;
- adapted planning target success at least 0.90;
- zero routed-versus-complete expert mismatches; and
- checkpoint digest and evaluation checksum equality.

## External authority

Modality adapters, data collection, use policy, protected evaluation, external effects, deployment, release signing, and formal conformance decisions remain outside the recursive model.

## Claim boundary

A development `PASS` establishes only that the frozen deterministic capsule passed this synthetic protocol. It does not establish foundation-model capability, real-data generalization, production safety, independent holdout custody, distributed training, accelerator performance, or formal MNCS/MNCDS conformance.
