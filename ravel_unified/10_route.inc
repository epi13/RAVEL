}

static void observation(uint8_t state, int drift, int8_t out[D]) {
    for (uint32_t d = 0; d < D; ++d) {
        int shift = 0;
        if (drift && state < 16u) {
            if (d == 6u) shift = 18;
            if (d == 7u) shift = -18;
        }
        out[d] = clamp_i8((int)world_c[state][d] + shift + (int)(rng_u32() % 11u) - 5);
    }
}

static void make_dataset(Event *out, uint32_t n, uint64_t seed, int drift) {
    rng_state = seed;
    for (uint32_t i = 0; i < n; ++i) {
        uint8_t s = (uint8_t)(rng_u32() % STATES);
        uint8_t a = (uint8_t)(rng_u32() % ACTIONS);
        uint8_t ns = world_next[s][a];
        out[i].state = s;
        out[i].next_state = ns;
        out[i].action = a;
        out[i].label = (uint8_t)(drift && s < 16u ? ((world_y[s] + 3u) & 7u) : world_y[s]);
        observation(s, drift, out[i].x);
        observation(ns, drift, out[i].nx);
    }
}

static double dist_x(const int8_t x[D], const Expert *e) {
    double z = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double v = (double)x[d] - e->key[d];
        z += v * v;
    }
    return z;
}

static double dist_vec(const double a[D], const double b[D]) {
    double z = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double v = a[d] - b[d];
        z += v * v;
    }
    return z;
}

static uint16_t cell_id(const int8_t x[D], int *in_domain) {
    uint16_t b = 0u;
    *in_domain = 1;
    for (uint32_t d = 0; d < D; ++d) if (x[d] < LO || x[d] > HI) *in_domain = 0;
    for (uint32_t d = 0; d < 4u; ++d) {
        int v = ((int)x[d] - LO) / 32;
        if (v < 0) v = 0;
        if (v > 3) v = 3;
        b = (uint16_t)((b << 2) | (uint16_t)v);
    }
    return b;
}

static double axis_lb(double c, double lo, double hi) {
    if (c < lo) { double v = lo - c; return v * v; }
    if (c > hi) { double v = c - hi; return v * v; }
    return 0.0;
}

static int better(double d, uint16_t id, double bd, uint16_t bi) {
    return d < bd || (d == bd && id < bi);
}

static void build_lattice(const Model *m, Cell cells[CELLS]) {
    for (uint32_t b = 0; b < CELLS; ++b) {
        double d[MAXE];
        uint16_t id[MAXE];
        for (uint16_t j = 0; j < m->n; ++j) {
            double z = 0.0;
            for (uint32_t k = 0; k < 4u; ++k) {
                uint32_t shift = 2u * (3u - k);
                uint32_t v = (b >> shift) & 3u;
                double lo = (double)(LO + 32 * (int)v);
                z += axis_lb(m->e[j].key[k], lo, lo + 31.0);
            }
            d[j] = z; id[j] = j;
        }
        uint16_t take = m->n < ROUTE_K ? m->n : ROUTE_K;
        uint16_t need = m->n > ROUTE_K ? (uint16_t)(ROUTE_K + 1u) : m->n;
        for (uint16_t i = 0; i < need; ++i) {
            uint16_t k = i;
            for (uint16_t j = (uint16_t)(i + 1u); j < m->n; ++j) {
                if (d[j] < d[k] || (d[j] == d[k] && id[j] < id[k])) k = j;
            }
            double td = d[i]; d[i] = d[k]; d[k] = td;
            uint16_t ti = id[i]; id[i] = id[k]; id[k] = ti;
        }
        for (uint16_t i = 0; i < ROUTE_K; ++i) cells[b].id[i] = UINT16_MAX;
        for (uint16_t i = 0; i < take; ++i) cells[b].id[i] = id[i];
        cells[b].excluded_lb = m->n > ROUTE_K ? d[ROUTE_K] : DBL_MAX;
    }
}

static uint16_t full_nearest(const int8_t x[D], const Model *m, uint64_t *evals) {
    double bd = DBL_MAX; uint16_t bi = UINT16_MAX;
    for (uint16_t j = 0; j < m->n; ++j) {
        double d = dist_x(x, &m->e[j]);
        ++*evals;
        if (better(d, j, bd, bi)) { bd = d; bi = j; }
    }
    return bi;
}

static uint16_t routed_nearest(const int8_t x[D], const Model *m, const Cell cells[CELLS],
                               uint64_t *evals, uint64_t *certified) {
    int in_domain = 0;
    uint16_t b = cell_id(x, &in_domain);
    uint8_t seen[MAXE]; memset(seen, 0, sizeof seen);
    double bd = DBL_MAX; uint16_t bi = UINT16_MAX;
    uint16_t take = m->n < ROUTE_K ? m->n : ROUTE_K;
    for (uint16_t i = 0; i < take; ++i) {
        uint16_t j = cells[b].id[i]; assert(j < m->n); seen[j] = 1u;
        double d = dist_x(x, &m->e[j]); ++*evals;
        if (better(d, j, bd, bi)) { bd = d; bi = j; }
    }
    if (in_domain && bd < cells[b].excluded_lb) { ++*certified; return bi; }
    for (uint16_t j = 0; j < m->n; ++j) if (!seen[j]) {
        double d = dist_x(x, &m->e[j]); ++*evals;
        if (better(d, j, bd, bi)) { bd = d; bi = j; }
    }
    return bi;
}

static void seed_expert(Expert *e, const Event *ev, uint64_t lineage, uint16_t generation) {
    memset(e, 0, sizeof *e);
    for (uint32_t d = 0; d < D; ++d) {
        e->key[d] = (double)ev->x[d];
        e->decode[d] = (double)ev->x[d];
        for (uint32_t a = 0; a < ACTIONS; ++a) e->next[a][d] = (double)ev->nx[d];
    }
    e->label = ev->label;
    e->lineage = lineage;
    e->generation = generation;
    e->active = 1u;
}

static void farthest_init(Model *m, uint16_t n, const Event *data, uint32_t count, TrainMetric *tm) {
    memset(m, 0, sizeof *m);
    m->n = n;
    seed_expert(&m->e[0], &data[0], mix64(UINT64_C(0x524156454c550001)), 0u);
    for (uint16_t k = 1; k < n; ++k) {
        double far = -1.0; uint32_t fi = 0u;
        for (uint32_t i = 0; i < count; ++i) {
            double near = DBL_MAX;
            for (uint16_t j = 0; j < k; ++j) {
                double d = dist_x(data[i].x, &m->e[j]); ++tm->expert_evaluations;
                if (d < near) near = d;
            }
            if (near > far) { far = near; fi = i; }
        }
        seed_expert(&m->e[k], &data[fi], mix64(m->e[0].lineage ^ k), 0u);
    }
}

static void refine(Model *m, const Event *data, uint32_t count, uint32_t iterations,
                   int routed, uint16_t *out_assignment, TrainMetric *tm) {
    Cell cells[CELLS];
    for (uint32_t it = 0; it < iterations; ++it) {
        double key_sum[MAXE][D], decode_sum[MAXE][D], next_sum[MAXE][ACTIONS][D];
        uint32_t counts[MAXE], labels[MAXE][CLASSES], action_count[MAXE][ACTIONS];
        uint32_t errors[MAXE]; double rsse[MAXE], psse[MAXE];
        memset(key_sum, 0, sizeof key_sum); memset(decode_sum, 0, sizeof decode_sum);
        memset(next_sum, 0, sizeof next_sum); memset(counts, 0, sizeof counts);
        memset(labels, 0, sizeof labels); memset(action_count, 0, sizeof action_count);
