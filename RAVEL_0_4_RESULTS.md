# RAVEL 0.4 generated results

This file is generated from canonical raw observations. It is not an independent attestation.

## Frozen trial outcomes

| Trial | Regime | Result | Failed gates |
|---|---|---:|---|
| trial-01-separated | separated_state | FAIL | adapted_gain_over_static |
| trial-02-overlap | partially_overlapping_observations | FAIL | adapted_gain_over_static |
| trial-03-noise | increased_observation_noise | FAIL | adapted_gain_over_static |
| trial-04-label | label_drift | FAIL | base_holdout_retention, adapted_reconstruction_improvement |
| trial-05-observation | observation_drift | FAIL | adapted_gain_over_static |
| trial-06-transition | transition_drift | FAIL | adapted_gain_over_static, retention_prediction |
| trial-07-combined | combined_observation_and_label_drift | FAIL | base_holdout_retention |
| trial-08-ambiguous | partially_observed_ambiguous | FAIL | exact_world_state_target_rate |

## Candidate aggregates

| Metric | Minimum | Median | Maximum | Mean | Population SD |
|---|---:|---:|---:|---:|---:|
| base_holdout_accuracy | 0.937500000 | 0.988281250 | 1.000000000 | 0.980957031 | 0.020710264 |
| adaptation_training_accuracy | 0.962890625 | 1.000000000 | 1.000000000 | 0.988037109 | 0.015729554 |
| static_model_drift_holdout_accuracy | 0.613281250 | 0.955078125 | 0.992187500 | 0.842285156 | 0.167865810 |
| adapted_model_drift_holdout_accuracy | 0.933593750 | 1.000000000 | 1.000000000 | 0.985351562 | 0.022333197 |
| base_holdout_retention | 0.671875000 | 1.000000000 | 1.000000000 | 0.904296875 | 0.135865080 |
| base_reconstruction_rmse | 3.249159843 | 4.779562945 | 9.256042033 | 5.290470095 | 1.792634061 |
| adapted_drift_reconstruction_rmse | 3.268650797 | 4.714815610 | 11.722196472 | 5.595161787 | 2.701052029 |
| base_prediction_rmse | 5.274702577 | 9.068426947 | 15.803773847 | 9.351916128 | 3.336964137 |
| adapted_drift_prediction_rmse | 5.210900214 | 7.561135692 | 15.132556407 | 9.089436322 | 3.791884802 |
| planning_exact_state_rate | 0.296875000 | 0.945312500 | 1.000000000 | 0.867187500 | 0.222210354 |
| planning_path_found_rate | 0.968750000 | 1.000000000 | 1.000000000 | 0.996093750 | 0.010334966 |
| expert_count | 68.000000000 | 68.000000000 | 68.000000000 | 68.000000000 | 0.000000000 |
| training_evaluations | 184288.000000000 | 198176.500000000 | 248728.000000000 | 201902.500000000 | 19212.060339797 |
| checkpoint_size_bytes | 39438.000000000 | 39438.000000000 | 39438.000000000 | 39438.000000000 | 0.000000000 |

## Interpretation

Development result: `FAIL`. Passing trials: 0; failing trials: 8.

Baseline and ablation results are mixed. No superiority claim is made. Per-variant wall-clock observations remain `UNKNOWN` in canonical evidence; deterministic operation counts are compared instead.

Formal MNCS status remains `UNKNOWN`. Formal MNCDS status remains `UNKNOWN`. Promotion is unauthorized.
