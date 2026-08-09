"""Generated C surface for the RAVEL 0.6 retention transaction.

This is deliberately injected into candidate-001 rather than compiled into the
frozen 0.5 translation unit.  The old adaptation primitive remains available as
the behavior baseline; the trial path adds a copy, raw-observation, and
all-hard-gates commit boundary.
"""

TRANSACTION_SURFACE = r'''
/* RAVEL 0.6 transaction surface: raw observations plus bounded commit. */
typedef struct {
    uint32_t objective_before_q20;
    uint32_t objective_after_q20;
    uint64_t base_accuracy_before_q20;
    uint64_t base_accuracy_after_q20;
    uint64_t representation_before_q20;
    uint64_t representation_after_q20;
    uint64_t prediction_rmse_before_q20;
    uint64_t prediction_rmse_after_q20;
    uint32_t transition_support_losses;
    uint32_t expert_count;
    uint64_t births;
    uint64_t retirements;
    uint64_t replay_records;
    uint32_t update_passes;
    uint64_t compute_evaluations;
    uint64_t matched_compute_evaluations;
    uint8_t matched_compute_reference_available;
    uint32_t failed_constraint_mask;
    uint8_t committed;
    uint8_t rollback_byte_identical;
    const char *threshold_identity;
    const char *rejection_reason;
} AdaptationTransaction;

enum {
    RAVEL06_FAIL_MECHANISM = 1u << 0,
    RAVEL06_FAIL_OBJECTIVE = 1u << 1,
    RAVEL06_FAIL_BASE_ACCURACY = 1u << 2,
    RAVEL06_FAIL_REPRESENTATION = 1u << 3,
    RAVEL06_FAIL_PREDICTION = 1u << 4,
    RAVEL06_FAIL_TRANSITION_SUPPORT = 1u << 5,
    RAVEL06_FAIL_EXPERT_BUDGET = 1u << 6,
    RAVEL06_FAIL_BIRTH_BUDGET = 1u << 7,
    RAVEL06_FAIL_RETIREMENT_BUDGET = 1u << 8,
    RAVEL06_FAIL_REPLAY_BUDGET = 1u << 9,
    RAVEL06_FAIL_UPDATE_BUDGET = 1u << 10,
    RAVEL06_FAIL_COMPUTE_BUDGET = 1u << 11
};

#define RAVEL06_BASE_ACCURACY_FLOOR_Q20 UINT64_C(891290)
#define RAVEL06_PREDICTION_DEGRADATION_BOUND_Q20 UINT64_C(1048576)
#define RAVEL06_MAX_UPDATE_PASSES 4u
#define RAVEL06_MAX_COMPUTE_EVALUATIONS UINT64_C(2000000)

static uint64_t ravel06_accuracy_q20(const Eval *evaluation) {
    if (evaluation->samples == 0u) return 0u;
    return (evaluation->correct * UINT64_C(1048576)) / evaluation->samples;
}

static uint64_t ravel06_representation_q20(const Eval *evaluation) {
    if (evaluation->samples == 0u) return UINT64_MAX;
    return evaluation->reconstruction_sse_q20 / evaluation->samples;
}

static uint64_t ravel06_prediction_q20(const Eval *evaluation) {
    if (evaluation->prediction_samples == 0u) return UINT64_MAX;
    double value = prediction_rmse(evaluation);
    if (!isfinite(value) || value < 0.0) return UINT64_MAX;
    return (uint64_t)q20(value);
}

static int ravel06_edge_present(const Model *model, uint64_t source_lineage,
                                uint32_t action, uint64_t target_lineage) {
    for (uint16_t source = 0; source < model->n; ++source) {
        if (model->e[source].lineage != source_lineage) continue;
        for (uint32_t slot = 0; slot < TRANSITION_TOP_K; ++slot) {
            uint16_t target = model->next_graph[source][action][slot];
            if (target < model->n &&
                model->next_graph_support[source][action][slot] >=
                    TRANSITION_SUPPORT_MIN &&
                model->e[target].lineage == target_lineage) return 1;
        }
    }
    return 0;
}

static uint32_t ravel06_transition_losses(const Model *previous,
                                          const Model *proposed) {
    uint32_t losses = 0u;
    for (uint16_t source = 0; source < previous->n; ++source) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            for (uint32_t slot = 0; slot < TRANSITION_TOP_K; ++slot) {
                uint16_t target = previous->next_graph[source][action][slot];
                if (target >= previous->n ||
                    previous->next_graph_support[source][action][slot] <
                        TRANSITION_SUPPORT_MIN) continue;
                if (!ravel06_edge_present(proposed, previous->e[source].lineage,
                                          action, previous->e[target].lineage)) {
                    ++losses;
                }
            }
        }
    }
    return losses;
}

static const char *ravel06_rejection_reason(uint32_t mask) {
    if (mask & RAVEL06_FAIL_MECHANISM) return "adaptation_mechanism_failed";
    if (mask & RAVEL06_FAIL_OBJECTIVE) return "adaptation_improvement_below_epsilon";
    if (mask & RAVEL06_FAIL_BASE_ACCURACY) return "base_accuracy_floor";
    if (mask & RAVEL06_FAIL_REPRESENTATION) return "representation_floor";
    if (mask & RAVEL06_FAIL_PREDICTION) return "original_prediction_degradation_bound";
    if (mask & RAVEL06_FAIL_TRANSITION_SUPPORT) return "transition_support_preservation";
    if (mask & RAVEL06_FAIL_EXPERT_BUDGET) return "expert_capacity_budget";
    if (mask & RAVEL06_FAIL_BIRTH_BUDGET) return "birth_budget";
    if (mask & RAVEL06_FAIL_RETIREMENT_BUDGET) return "retirement_budget";
    if (mask & RAVEL06_FAIL_REPLAY_BUDGET) return "replay_budget";
    if (mask & RAVEL06_FAIL_UPDATE_BUDGET) return "update_pass_budget";
    if (mask & RAVEL06_FAIL_COMPUTE_BUDGET) return "compute_budget";
    return "none";
}

static int adapt_model_transaction(
    Model *model, const Event *base_train, const Event *adapt_train,
    const Event *retention, uint32_t retention_count, const VariantConfig *config,
    TrainMetric *metric, ReplayMetric *replay, TopologyTrace *topology,
    AdaptationTransaction *transaction) {
    Model previous = *model;
    Model proposed = *model;
    memset(transaction, 0, sizeof *transaction);
    transaction->threshold_identity = "ravel-0.6-retention-gates/0.1";
    int mechanism_ok = adapt_model(&proposed, base_train, adapt_train, config,
                                   metric, replay, topology);
    canonicalize_model(&proposed);
    transaction->objective_before_q20 = model_objective_q20(
        &previous, adapt_train, ADAPT_TRAIN_N, NULL, 0u);
    transaction->objective_after_q20 = model_objective_q20(
        &proposed, adapt_train, ADAPT_TRAIN_N, NULL, 0u);
    transaction->expert_count = proposed.n;
    transaction->births = metric->births;
    transaction->retirements = metric->retired;
    transaction->replay_records = replay->selected;
    transaction->update_passes = config->matched_work ? 4u : 2u;
    transaction->compute_evaluations = metric->expert_evaluations;
    transaction->matched_compute_evaluations = 0u;
    transaction->matched_compute_reference_available = 0u;

    const Event *gate_data = retention != NULL ? retention : base_train;
    uint32_t gate_count = retention != NULL ? retention_count : BASE_TRAIN_N;
    Eval previous_eval = evaluate(&previous, gate_data, gate_count, config->routed);
    Eval proposed_eval = evaluate(&proposed, gate_data, gate_count, config->routed);
    transaction->base_accuracy_before_q20 = ravel06_accuracy_q20(&previous_eval);
    transaction->base_accuracy_after_q20 = ravel06_accuracy_q20(&proposed_eval);
    transaction->representation_before_q20 =
        ravel06_representation_q20(&previous_eval);
    transaction->representation_after_q20 =
        ravel06_representation_q20(&proposed_eval);
    transaction->prediction_rmse_before_q20 = ravel06_prediction_q20(&previous_eval);
    transaction->prediction_rmse_after_q20 = ravel06_prediction_q20(&proposed_eval);
    transaction->transition_support_losses =
        ravel06_transition_losses(&previous, &proposed);

    uint32_t failed = 0u;
    if (!mechanism_ok) failed |= RAVEL06_FAIL_MECHANISM;
    if (transaction->objective_after_q20 <
        transaction->objective_before_q20 + TOPOLOGY_OBJECTIVE_MIN_Q20) {
        failed |= RAVEL06_FAIL_OBJECTIVE;
    }
    if (transaction->base_accuracy_after_q20 < RAVEL06_BASE_ACCURACY_FLOOR_Q20) {
        failed |= RAVEL06_FAIL_BASE_ACCURACY;
    }
    if (transaction->representation_after_q20 >
        transaction->representation_before_q20) {
        failed |= RAVEL06_FAIL_REPRESENTATION;
    }
    if (transaction->prediction_rmse_before_q20 != UINT64_MAX &&
        transaction->prediction_rmse_after_q20 != UINT64_MAX &&
        transaction->prediction_rmse_after_q20 >
            transaction->prediction_rmse_before_q20 +
                RAVEL06_PREDICTION_DEGRADATION_BOUND_Q20) {
        failed |= RAVEL06_FAIL_PREDICTION;
    }
    if (transaction->transition_support_losses != 0u) {
        failed |= RAVEL06_FAIL_TRANSITION_SUPPORT;
    }
    if (transaction->expert_count > MAXE) failed |= RAVEL06_FAIL_EXPERT_BUDGET;
    if (transaction->births > MAX_ADAPT_BIRTHS) failed |= RAVEL06_FAIL_BIRTH_BUDGET;
    if (transaction->retirements > MAX_ADAPT_RETIREMENTS) {
        failed |= RAVEL06_FAIL_RETIREMENT_BUDGET;
    }
    if (transaction->replay_records > REPLAY_N) failed |= RAVEL06_FAIL_REPLAY_BUDGET;
    if (transaction->update_passes > RAVEL06_MAX_UPDATE_PASSES) {
        failed |= RAVEL06_FAIL_UPDATE_BUDGET;
    }
    if (transaction->compute_evaluations > RAVEL06_MAX_COMPUTE_EVALUATIONS) {
        failed |= RAVEL06_FAIL_COMPUTE_BUDGET;
    }
    transaction->failed_constraint_mask = failed;
    transaction->rejection_reason = ravel06_rejection_reason(failed);
    if (failed == 0u) {
        *model = proposed;
        transaction->committed = 1u;
        transaction->rollback_byte_identical = 0u;
        return 1;
    }
    *model = previous;
    ByteBuffer before_bytes, after_bytes;
    transaction->rollback_byte_identical =
        serialize_checkpoint(&previous, &before_bytes) &&
        serialize_checkpoint(model, &after_bytes) &&
        before_bytes.len == after_bytes.len &&
        bytes_equal(before_bytes.data, after_bytes.data, before_bytes.len);
    return 0;
}

static void print_adaptation_transaction_json(
    const AdaptationTransaction *transaction) {
    printf("{\"committed\":%s,\"threshold_identity\":\"%s\","
           "\"rejection_reason\":\"%s\","
           "\"failed_constraint_mask\":%u,\"rollback_byte_identical\":%s,"
           "\"raw\":{\"objective_before_q20\":%u,"
           "\"objective_after_q20\":%u,\"base_accuracy_before_q20\":%" PRIu64
           ",\"base_accuracy_after_q20\":%" PRIu64
           ",\"representation_before_q20\":%" PRIu64
           ",\"representation_after_q20\":%" PRIu64
           ",\"prediction_rmse_before_q20\":%" PRIu64
           ",\"prediction_rmse_after_q20\":%" PRIu64
           ",\"transition_support_losses\":%u,\"expert_count\":%u"
           ",\"births\":%" PRIu64 ",\"retirements\":%" PRIu64
           ",\"replay_records\":%" PRIu64 ",\"update_passes\":%u"
           ",\"compute_evaluations\":%" PRIu64
           ",\"matched_compute_evaluations\":%" PRIu64
           ",\"matched_compute_reference_available\":%s}}",
           transaction->committed ? "true" : "false",
           transaction->threshold_identity,
           transaction->rejection_reason, transaction->failed_constraint_mask,
           transaction->rollback_byte_identical ? "true" : "false",
           transaction->objective_before_q20, transaction->objective_after_q20,
           transaction->base_accuracy_before_q20,
           transaction->base_accuracy_after_q20,
           transaction->representation_before_q20,
           transaction->representation_after_q20,
           transaction->prediction_rmse_before_q20,
           transaction->prediction_rmse_after_q20,
           transaction->transition_support_losses, transaction->expert_count,
           transaction->births, transaction->retirements,
           transaction->replay_records, transaction->update_passes,
           transaction->compute_evaluations,
           transaction->matched_compute_evaluations,
           transaction->matched_compute_reference_available ? "true" : "false");
}
'''
