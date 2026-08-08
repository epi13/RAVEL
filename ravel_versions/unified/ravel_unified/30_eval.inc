    for (uint16_t j = 0; j < m->n; ++j) {
        for (uint32_t a = 0; a < ACTIONS; ++a) m->next_graph[j][a] = nearest_vec(m->e[j].next[a], m);
    }
}

static uint64_t model_digest(const Model *m) {
    uint64_t h = mix64(m->n ^ (m->epoch << 32));
    for (uint16_t j = 0; j < m->n; ++j) {
        uint64_t q = m->e[j].lineage ^ ((uint64_t)m->e[j].label << 56) ^ m->e[j].count;
        for (uint32_t d = 0; d < D; ++d) {
            int64_t v = (int64_t)llround(m->e[j].key[d] * 1024.0);
            q ^= mix64((uint64_t)v ^ ((uint64_t)d << 48));
        }
        for (uint32_t a = 0; a < ACTIONS; ++a) q ^= mix64(((uint64_t)m->next_graph[j][a] << 32) ^ a);
        h ^= mix64(q ^ j);
    }
    return h;
}

static Eval evaluate(const Model *m, const Event *data, uint32_t count) {
    Eval out = {0}; Cell cells[CELLS]; build_lattice(m, cells);
    for (uint32_t i = 0; i < count; ++i) {
        uint16_t got = routed_nearest(data[i].x, m, cells, &out.expert_evaluations, &out.certified);
        uint64_t oe = 0u; uint16_t oracle = full_nearest(data[i].x, m, &oe);
        if (got != oracle) ++out.exact_mismatches;
        if (m->e[got].label == data[i].label) ++out.correct;
        double pred[D];
        for (uint32_t d = 0; d < D; ++d) {
            double rv = (double)data[i].x[d] - m->e[got].decode[d]; out.reconstruction_sse += rv * rv;
            pred[d] = m->e[got].next[data[i].action][d];
            double pv = (double)data[i].nx[d] - pred[d]; out.prediction_sse += pv * pv;
        }
        uint16_t next_e = nearest_vec(pred, m);
        uint64_t ne = 0u; uint16_t true_next_e = full_nearest(data[i].nx, m, &ne);
        if (next_e == true_next_e) ++out.transition_correct;
        ++out.samples;
        out.checksum ^= mix64(((uint64_t)got << 48) ^ ((uint64_t)next_e << 32) ^ ((uint64_t)m->e[got].label << 24) ^ i);
    }
    return out;
}

static int plan_actions(const Model *m, uint16_t start, uint16_t goal, uint8_t actions[PLAN_LIMIT], uint32_t *used, uint64_t *expansions) {
    uint16_t queue[MAXE], parent[MAXE], parent_action[MAXE]; uint8_t seen[MAXE];
    memset(seen, 0, sizeof seen); for (uint16_t i = 0; i < MAXE; ++i) { parent[i] = UINT16_MAX; parent_action[i] = UINT16_MAX; }
    uint16_t qh = 0u, qt = 0u; queue[qt++] = start; seen[start] = 1u;
    while (qh < qt) {
        uint16_t cur = queue[qh++]; ++*expansions;
        if (cur == goal) break;
        for (uint16_t a = 0; a < ACTIONS; ++a) {
            uint16_t nx = m->next_graph[cur][a];
            if (!seen[nx]) { seen[nx] = 1u; parent[nx] = cur; parent_action[nx] = a; queue[qt++] = nx; }
        }
    }
    if (!seen[goal]) return 0;
    uint8_t rev[PLAN_LIMIT]; uint32_t n = 0u; uint16_t cur = goal;
    while (cur != start && n < PLAN_LIMIT) { rev[n++] = (uint8_t)parent_action[cur]; cur = parent[cur]; }
    if (cur != start) return 0;
    for (uint32_t i = 0; i < n; ++i) actions[i] = rev[n - 1u - i];
    *used = n; return 1;
}

static PlanMetric evaluate_planning(const Model *m, int drift) {
    PlanMetric pm = {0}; rng_state = UINT64_C(0x504c414e484f4c44) ^ (uint64_t)drift;
    Cell cells[CELLS]; build_lattice(m, cells);
    for (uint32_t i = 0; i < PLAN_CASES; ++i) {
        uint8_t s = (uint8_t)(rng_u32() % STATES), g = (uint8_t)(rng_u32() % STATES);
        int8_t sx[D], gx[D]; observation(s, drift, sx); observation(g, drift, gx);
        uint64_t ev = 0u, cert = 0u;
        uint16_t se = routed_nearest(sx, m, cells, &ev, &cert);
        uint16_t ge = routed_nearest(gx, m, cells, &ev, &cert);
        uint8_t acts[PLAN_LIMIT]; uint32_t used = 0u;
        ++pm.cases;
        if (!plan_actions(m, se, ge, acts, &used, &pm.expansions)) continue;
        ++pm.solved;
        uint8_t cur = s;
        for (uint32_t k = 0; k < used; ++k) cur = world_next[cur][acts[k]];
        int8_t fx[D]; for (uint32_t d = 0; d < D; ++d) {
            int shift = (drift && cur < 16u) ? (d == 6u ? 18 : d == 7u ? -18 : 0) : 0;
            fx[d] = clamp_i8((int)world_c[cur][d] + shift);
        }
        uint16_t fe = routed_nearest(fx, m, cells, &ev, &cert);
        if (fe == ge) ++pm.exact_goals;
        pm.checksum ^= mix64(((uint64_t)se << 48) ^ ((uint64_t)ge << 32) ^ ((uint64_t)fe << 16) ^ used ^ i);
    }
    return pm;
}

static int checkpoint_roundtrip(const Model *m, Model *out) {
    const char *path = "ravel-unified-checkpoint.bin";
    FILE *f = fopen(path, "wb"); if (f == NULL) return 0;
    size_t wrote = fwrite(m, sizeof *m, 1u, f); int ok = fclose(f) == 0 && wrote == 1u;
    if (!ok) { remove(path); return 0; }
    f = fopen(path, "rb"); if (f == NULL) { remove(path); return 0; }
    size_t read = fread(out, sizeof *out, 1u, f); ok = fclose(f) == 0 && read == 1u;
    remove(path); return ok;
}

static void print_eval(const char *name, const Eval *e, uint16_t experts, int comma) {
    double acc = (double)e->correct / e->samples;
    double cert = (double)e->certified / e->samples;
    double mean = (double)e->expert_evaluations / e->samples;
    double rrmse = sqrt(e->reconstruction_sse / (double)(e->samples * D));
    double prmse = sqrt(e->prediction_sse / (double)(e->samples * D));
    double tr = (double)e->transition_correct / e->samples;
    printf("    \"%s\":{\"experts\":%u,\"samples\":%" PRIu64 ",\"accuracy\":%.9f,\"exact_mismatches\":%" PRIu64 ",\"certified_rate\":%.9f,\"mean_experts\":%.6f,\"reconstruction_rmse\":%.9f,\"next_prediction_rmse\":%.9f,\"transition_accuracy\":%.9f,\"checksum\":\"%016" PRIx64 "\"}%s\n",
           name, experts, e->samples, acc, e->exact_mismatches, cert, mean, rrmse, prmse, tr, e->checksum, comma ? "," : "");
}

int main(void) {
    make_world();
    make_dataset(train_set, NTRAIN, UINT64_C(0x747261696e550001), 0);
    make_dataset(hold_set, NHOLD, UINT64_C(0x686f6c6455000001), 0);
    make_dataset(adapt_set, NADAPT, UINT64_C(0x6164617074550001), 1);

    Model base; TrainMetric base_tm = {0}; train_base(&base, &base_tm); compile_graph(&base); base.digest = model_digest(&base);
    Eval base_hold = evaluate(&base, hold_set, NHOLD);
    Eval static_drift = evaluate(&base, adapt_set, NADAPT);
    PlanMetric base_plan = evaluate_planning(&base, 0);

    Model adapted = base; TrainMetric adapt_tm = {0}; adapt_model(&adapted, &adapt_tm); compile_graph(&adapted); adapted.digest = model_digest(&adapted);
    Eval adapted_drift = evaluate(&adapted, adapt_set, NADAPT);
    Eval retained_hold = evaluate(&adapted, hold_set, NHOLD);
    PlanMetric adapted_plan = evaluate_planning(&adapted, 1);

    Model restored; int checkpoint_ok = checkpoint_roundtrip(&adapted, &restored);
    uint64_t restored_digest = checkpoint_ok ? model_digest(&restored) : 0u;
    Eval restored_eval = checkpoint_ok ? evaluate(&restored, adapt_set, NADAPT) : (Eval){0};

    double base_acc = (double)base_hold.correct / base_hold.samples;
    double drift_static_acc = (double)static_drift.correct / static_drift.samples;
    double drift_adapt_acc = (double)adapted_drift.correct / adapted_drift.samples;
    double retain_acc = (double)retained_hold.correct / retained_hold.samples;
    double transition = (double)adapted_drift.transition_correct / adapted_drift.samples;
    double plan_success = (double)adapted_plan.exact_goals / adapted_plan.cases;
    int pass = base.n == BASE_E && adapted.n == ADAPT_TARGET &&
               base_hold.exact_mismatches == 0u && adapted_drift.exact_mismatches == 0u &&
               base_acc >= 0.95 && drift_adapt_acc >= 0.95 && drift_adapt_acc >= drift_static_acc + 0.20 &&
               retain_acc >= 0.90 && transition >= 0.95 && plan_success >= 0.90 &&
               checkpoint_ok && restored_digest == adapted.digest && restored_eval.checksum == adapted_drift.checksum;

    printf("{\n  \"schema\":\"ravel-unified-evidence/0.3\",\n");
    printf("  \"architecture\":{\"event_dimensions\":%u,\"classes\":%u,\"actions\":%u,\"world_states\":%u,\"route_width\":%u},\n", D, CLASSES, ACTIONS, STATES, ROUTE_K);
    printf("  \"base_training\":{\"initial_experts\":%u,\"final_experts\":%u,\"births\":%" PRIu64 ",\"samples_processed\":%" PRIu64 ",\"expert_evaluations\":%" PRIu64 ",\"certified_routes\":%" PRIu64 ",\"model_digest\":\"%016" PRIx64 "\"},\n",
           INIT_E, base.n, base_tm.births, base_tm.samples, base_tm.expert_evaluations, base_tm.certified, base.digest);
    printf("  \"continual_adaptation\":{\"births\":%" PRIu64 ",\"retired\":%" PRIu64 ",\"final_experts\":%u,\"samples_processed\":%" PRIu64 ",\"expert_evaluations\":%" PRIu64 ",\"certified_routes\":%" PRIu64 ",\"model_digest\":\"%016" PRIx64 "\"},\n",
           adapt_tm.births, adapt_tm.retired, adapted.n, adapt_tm.samples, adapt_tm.expert_evaluations, adapt_tm.certified, adapted.digest);
    printf("  \"evaluation\":{\n");
    print_eval("base_holdout", &base_hold, base.n, 1);
    print_eval("static_on_drift", &static_drift, base.n, 1);
    print_eval("adapted_on_drift", &adapted_drift, adapted.n, 1);
    print_eval("adapted_retention", &retained_hold, adapted.n, 0);
    printf("  },\n");
    printf("  \"planning\":{\"base\":{\"cases\":%" PRIu64 ",\"solved\":%" PRIu64 ",\"exact_goals\":%" PRIu64 ",\"expansions\":%" PRIu64 ",\"checksum\":\"%016" PRIx64 "\"},\"adapted\":{\"cases\":%" PRIu64 ",\"solved\":%" PRIu64 ",\"exact_goals\":%" PRIu64 ",\"expansions\":%" PRIu64 ",\"checksum\":\"%016" PRIx64 "\"}},\n",
           base_plan.cases, base_plan.solved, base_plan.exact_goals, base_plan.expansions, base_plan.checksum,
           adapted_plan.cases, adapted_plan.solved, adapted_plan.exact_goals, adapted_plan.expansions, adapted_plan.checksum);
    printf("  \"checkpoint\":{\"roundtrip\":%s,\"digest_match\":%s,\"evaluation_match\":%s},\n",
           checkpoint_ok ? "true" : "false", restored_digest == adapted.digest ? "true" : "false", restored_eval.checksum == adapted_drift.checksum ? "true" : "false");
    printf("  \"gates\":{\"base_accuracy_at_least_0_95\":%s,\"adapted_drift_accuracy_at_least_0_95\":%s,\"drift_gain_at_least_0_20\":%s,\"retention_at_least_0_90\":%s,\"transition_accuracy_at_least_0_95\":%s,\"planning_success_at_least_0_90\":%s,\"exact_routing\":%s,\"checkpoint_reproducible\":%s},\n",
           base_acc >= 0.95 ? "true" : "false", drift_adapt_acc >= 0.95 ? "true" : "false", drift_adapt_acc >= drift_static_acc + 0.20 ? "true" : "false", retain_acc >= 0.90 ? "true" : "false", transition >= 0.95 ? "true" : "false", plan_success >= 0.90 ? "true" : "false", (base_hold.exact_mismatches == 0u && adapted_drift.exact_mismatches == 0u) ? "true" : "false", (checkpoint_ok && restored_digest == adapted.digest && restored_eval.checksum == adapted_drift.checksum) ? "true" : "false");
    printf("  \"development_result\":\"%s\",\n  \"formal_mncs_status\":\"UNKNOWN\",\n  \"formal_mncds_status\":\"UNKNOWN\",\n  \"promotion_authorized\":false\n}\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
