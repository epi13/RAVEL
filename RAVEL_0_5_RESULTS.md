# RAVEL 0.5 generated results

Generated deterministically from raw observations by the independent evaluator.

## Final validation outcomes

| Trial | Regime | Result | Failed gates |
|---|---|---:|---|
| validation-separated-01 | separated_state | PASS | none |
| validation-separated-02 | separated_state | PASS | none |
| validation-separated-03 | separated_state | PASS | none |
| validation-separated-04 | separated_state | PASS | none |
| validation-overlap-01 | partially_overlapping_observations | PASS | none |
| validation-overlap-02 | partially_overlapping_observations | PASS | none |
| validation-overlap-03 | partially_overlapping_observations | PASS | none |
| validation-overlap-04 | partially_overlapping_observations | PASS | none |
| validation-noise-01 | increased_observation_noise | PASS | none |
| validation-noise-02 | increased_observation_noise | PASS | none |
| validation-noise-03 | increased_observation_noise | PASS | none |
| validation-noise-04 | increased_observation_noise | PASS | none |
| validation-label-01 | label_drift | PASS | none |
| validation-label-02 | label_drift | FAIL | label_gain |
| validation-label-03 | label_drift | FAIL | label_gain |
| validation-label-04 | label_drift | FAIL | label_gain |
| validation-observation-01 | observation_drift | PASS | none |
| validation-observation-02 | observation_drift | PASS | none |
| validation-observation-03 | observation_drift | PASS | none |
| validation-observation-04 | observation_drift | PASS | none |
| validation-transition-01 | transition_drift | PASS | none |
| validation-transition-02 | transition_drift | PASS | none |
| validation-transition-03 | transition_drift | PASS | none |
| validation-transition-04 | transition_drift | FAIL | old_prediction_retention |
| validation-combined-01 | combined_observation_and_label_drift | PASS | none |
| validation-combined-02 | combined_observation_and_label_drift | FAIL | combined_exact_planning |
| validation-combined-03 | combined_observation_and_label_drift | PASS | none |
| validation-combined-04 | combined_observation_and_label_drift | PASS | none |
| validation-ambiguous-01 | partially_observed_ambiguous | PASS | none |
| validation-ambiguous-02 | partially_observed_ambiguous | FAIL | planning_path_found, ambiguous_belief_success, ambiguous_belief_gain |
| validation-ambiguous-03 | partially_observed_ambiguous | FAIL | ambiguous_belief_gain |
| validation-ambiguous-04 | partially_observed_ambiguous | FAIL | conditional_inference_efficiency |

## Paired baseline and ablation summary

All deltas are arithmetic means of per-seed candidate-minus-variant differences. A positive accuracy delta favors the candidate; a negative work or size delta uses fewer resources. Pareto counts use drift, retention, reconstruction, prediction, exact and belief-set planning, inference and training evaluations, expert count, and checkpoint size.

| Variant | Drift accuracy delta | Retention delta | Training-evaluation delta | Inference-evaluation delta | Candidate dominates | Variant dominates | Mixed | Equivalent |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_8_expert | 0.713501 | 0.767700 | 1583627.69 | 337.44 | 0 | 0 | 32 | 0 |
| fixed_topology_64_expert_routed | 0.049194 | -0.014038 | -910836.31 | 80.19 | 0 | 0 | 32 | 0 |
| flat_64_expert_complete_scan | 0.049194 | -0.014038 | -910836.31 | -13998.56 | 0 | 0 | 32 | 0 |
| matched_compute_fixed_topology | 0.098999 | 0.031372 | -123297.31 | -268.06 | 0 | 0 | 32 | 0 |
| matched_expert_count_capacity | 0.049194 | -0.014038 | -1559252.31 | -73.59 | 2 | 0 | 30 | 0 |
| nearest_centroid_16_no_recursive_births | 0.664185 | 0.693726 | 1423883.69 | -1710.56 | 0 | 0 | 32 | 0 |
| no_adaptation_static | 0.098999 | 0.031372 | 1110754.69 | -268.06 | 0 | 1 | 31 | 0 |
| periodic_replay_policy | -0.000244 | -0.000366 | 9001.66 | -34.16 | 6 | 3 | 22 | 1 |
| ravel_0_5_candidate | 0.000000 | 0.000000 | 0.00 | 0.00 | 0 | 0 | 0 | 32 |
| ravel_complete_scan_without_certification | 0.000000 | 0.000000 | -194224.53 | -16102.56 | 32 | 0 | 0 | 0 |
| ravel_no_birth_same_replay_iterations | 0.098999 | 0.031372 | 884012.69 | -268.06 | 0 | 1 | 31 | 0 |
| ravel_random_births | 0.098633 | 0.031860 | 869180.69 | -268.06 | 0 | 1 | 31 | 0 |
| ravel_without_replay | -0.000488 | 0.000122 | 321343.47 | -174.91 | 0 | 2 | 30 | 0 |
| ravel_without_retirement_matched_work | -0.000122 | 0.000244 | 0.00 | -27.97 | 3 | 0 | 2 | 27 |

## Disposition

Development result: `FAIL`. Passing trials: 24; failing trials: 8.

Comparisons are paired by seed and include Pareto relationships. Mixed results are not interpreted as superiority. Wall-clock observations are non-normative.

Formal MNCS status: `UNKNOWN`. Formal MNCDS status: `UNKNOWN`. Promotion remains unauthorized.
