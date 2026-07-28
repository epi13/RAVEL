        memset(errors, 0, sizeof errors); memset(rsse, 0, sizeof rsse); memset(psse, 0, sizeof psse);
        if (routed) build_lattice(m, cells);
        for (uint32_t i = 0; i < count; ++i) {
            uint16_t j = routed ? routed_nearest(data[i].x, m, cells, &tm->expert_evaluations, &tm->certified)
                                : full_nearest(data[i].x, m, &tm->expert_evaluations);
            ++tm->samples;
            if (out_assignment != NULL) out_assignment[i] = j;
            ++counts[j]; ++labels[j][data[i].label]; ++action_count[j][data[i].action];
            if (m->e[j].label != data[i].label) ++errors[j];
            for (uint32_t d = 0; d < D; ++d) {
                double x = (double)data[i].x[d], nx = (double)data[i].nx[d];
                key_sum[j][d] += x; decode_sum[j][d] += x;
                next_sum[j][data[i].action][d] += nx;
                double rv = x - m->e[j].decode[d]; rsse[j] += rv * rv;
                double pv = nx - m->e[j].next[data[i].action][d]; psse[j] += pv * pv;
            }
        }
        for (uint16_t j = 0; j < m->n; ++j) {
            m->e[j].count = counts[j]; m->e[j].errors = errors[j];
            m->e[j].reconstruction_sse = rsse[j]; m->e[j].prediction_sse = psse[j];
            memcpy(m->e[j].labels, labels[j], sizeof m->e[j].labels);
            memcpy(m->e[j].action_count, action_count[j], sizeof m->e[j].action_count);
            if (counts[j] > 0u) {
                for (uint32_t d = 0; d < D; ++d) {
                    m->e[j].key[d] = key_sum[j][d] / (double)counts[j];
                    m->e[j].decode[d] = decode_sum[j][d] / (double)counts[j];
                }
                m->e[j].label = majority(labels[j]);
                for (uint32_t a = 0; a < ACTIONS; ++a) if (action_count[j][a] > 0u) {
                    for (uint32_t d = 0; d < D; ++d) m->e[j].next[a][d] = next_sum[j][a][d] / (double)action_count[j][a];
                }
            }
        }
    }
}

static double split_score(const Expert *e) {
    if (e->count < 2u) return -1.0;
    return (double)e->errors * 1e12 + e->prediction_sse * 1e3 + e->reconstruction_sse + (double)e->count;
}

static int split_one(Model *m, uint16_t parent, uint16_t child, const Event *data,
                     uint32_t count, const uint16_t *a, uint32_t round) {
    uint32_t first = UINT32_MAX;
    for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) { first = i; break; }
    if (first == UINT32_MAX) return 0;
    uint32_t pa = first, pb = first; double far = -1.0;
    for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) {
        double z = 0.0; for (uint32_t d = 0; d < D; ++d) { double v = (double)data[i].x[d] - data[first].x[d]; z += v * v; }
        if (z > far) { far = z; pa = i; }
    }
    far = -1.0;
    for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) {
        double z = 0.0; for (uint32_t d = 0; d < D; ++d) { double v = (double)data[i].x[d] - data[pa].x[d]; z += v * v; }
        if (z > far) { far = z; pb = i; }
    }
    if (pa == pb) return 0;
    uint64_t root = m->e[parent].lineage;
    seed_expert(&m->e[parent], &data[pa], mix64(root ^ ((uint64_t)round << 32) ^ UINT64_C(0xa5)), (uint16_t)(m->e[parent].generation + 1u));
    seed_expert(&m->e[child], &data[pb], mix64(root ^ ((uint64_t)round << 32) ^ UINT64_C(0x5a)), (uint16_t)(m->e[parent].generation + 1u));
    return 1;
}

static void train_base(Model *m, TrainMetric *tm) {
    farthest_init(m, INIT_E, train_set, NTRAIN, tm);
    uint32_t round = 0u;
    while (m->n < BASE_E) {
        refine(m, train_set, NTRAIN, 1u, 1, assignment, tm);
        uint16_t order[MAXE]; for (uint16_t j = 0; j < m->n; ++j) order[j] = j;
        for (uint16_t i = 0; i < m->n; ++i) {
            uint16_t k = i;
            for (uint16_t j = (uint16_t)(i + 1u); j < m->n; ++j) {
                double a = split_score(&m->e[order[j]]), b = split_score(&m->e[order[k]]);
                if (a > b || (a == b && order[j] < order[k])) k = j;
            }
            uint16_t t = order[i]; order[i] = order[k]; order[k] = t;
        }
        uint16_t target = (uint16_t)((BASE_E - m->n) < GROW_PER_ROUND ? (BASE_E - m->n) : GROW_PER_ROUND);
        uint16_t made = 0u;
        for (uint16_t i = 0; i < m->n && made < target; ++i) {
            if (split_one(m, order[i], (uint16_t)(m->n + made), train_set, NTRAIN, assignment, round)) { ++made; ++tm->births; }
        }
        if (made == 0u) break;
        m->n = (uint16_t)(m->n + made); ++round;
    }
    refine(m, train_set, NTRAIN, REFINE_FINAL, 1, assignment, tm);
    ++m->epoch;
}

static void birth_drift_experts(Model *m, const Event *data, uint32_t count, TrainMetric *tm) {
    Cell cells[CELLS]; build_lattice(m, cells);
    double score[NADAPT];
    for (uint32_t i = 0; i < count; ++i) {
        uint64_t evals = 0u, cert = 0u;
        uint16_t j = routed_nearest(data[i].x, m, cells, &evals, &cert);
        tm->expert_evaluations += evals; tm->certified += cert; ++tm->samples;
        double p = 0.0;
        for (uint32_t d = 0; d < D; ++d) { double v = (double)data[i].nx[d] - m->e[j].next[data[i].action][d]; p += v * v; }
        score[i] = (m->e[j].label != data[i].label ? 1e12 : 0.0) + p;
    }
    for (uint16_t b = 0; b < ADAPT_BIRTHS && m->n < MAXE; ++b) {
        uint32_t best = 0u; double bs = -1.0;
        for (uint32_t i = 0; i < count; ++i) {
            double separation = DBL_MAX;
            for (uint16_t j = 0; j < m->n; ++j) {
                double d = dist_x(data[i].x, &m->e[j]);
                if (d < separation) separation = d;
            }
            double s = score[i] + separation * 1e6;
            if (s > bs) { bs = s; best = i; }
        }
        seed_expert(&m->e[m->n], &data[best], mix64(UINT64_C(0x4452494654424952) ^ m->n ^ m->epoch), (uint16_t)(m->epoch + 1u));
        ++m->n; ++tm->births; score[best] = -DBL_MAX;
    }
}

static void remove_expert(Model *m, uint16_t victim) {
    assert(victim < m->n);
    uint16_t last = (uint16_t)(m->n - 1u);
    if (victim != last) m->e[victim] = m->e[last];
    memset(&m->e[last], 0, sizeof m->e[last]);
    --m->n;
}

static void retire_to_target(Model *m, const Event *data, uint32_t count, TrainMetric *tm) {
    while (m->n > ADAPT_TARGET) {
        uint16_t victim = BASE_E;
        for (uint16_t j = (uint16_t)(BASE_E + 1u); j < m->n; ++j) {
            const Expert *a = &m->e[j], *b = &m->e[victim];
            double ua = (double)a->count * 1e9 - (double)a->errors * 1e12 - a->prediction_sse;
            double ub = (double)b->count * 1e9 - (double)b->errors * 1e12 - b->prediction_sse;
            if (ua < ub || (ua == ub && j > victim)) victim = j;
        }
        remove_expert(m, victim);
        ++tm->retired;
        refine(m, data, count, 1u, 1, assignment, tm);
    }
}

static void adapt_model(Model *m, TrainMetric *tm) {
    for (uint32_t i = 0; i < NREPLAY; ++i) replay_set[i] = train_set[(i * 4u) % NTRAIN];
    memcpy(adapt_mix, adapt_set, sizeof adapt_set);
    memcpy(adapt_mix + NADAPT, replay_set, sizeof replay_set);
    birth_drift_experts(m, adapt_set, NADAPT, tm);
    refine(m, adapt_mix, NADAPT + NREPLAY, REFINE_ADAPT, 1, assignment, tm);
    retire_to_target(m, adapt_mix, NADAPT + NREPLAY, tm);
    ++m->epoch;
}

static uint16_t nearest_vec(const double v[D], const Model *m) {
    double bd = DBL_MAX; uint16_t bi = UINT16_MAX;
    for (uint16_t j = 0; j < m->n; ++j) {
        double d = dist_vec(v, m->e[j].key);
        if (better(d, j, bd, bi)) { bd = d; bi = j; }
    }
    return bi;
}

static void compile_graph(Model *m) {
