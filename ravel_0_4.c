/*
 * RAVEL 0.4 -- bounded evidence-hardening experiment.
 *
 * This is maintained C11 source. No source generator is claimed.
 */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define D 8u
#define CLASSES 8u
#define ACTIONS 4u
#define STATES 64u
#define MAXE 80u
#define BASE_E 64u
#define INIT_E 8u
#define ADAPT_BIRTHS 8u
#define ADAPTED_E 68u
#define ROUTE_K 8u
#define CELLS 256u
#define BASE_TRAIN_N 1024u
#define BASE_HOLD_N 256u
#define ADAPT_TRAIN_N 512u
#define DRIFT_HOLD_N 256u
#define RETENTION_N 256u
#define REPLAY_N 256u
#define PLAN_N 64u
#define PLAN_LIMIT 32u
#define TRIALS 8u
#define LO (-64)
#define HI 63
#define Q20_SCALE 1048576.0
#define CHECKPOINT_SCHEMA 4u
#define CHECKPOINT_HEADER 64u
#define CHECKPOINT_MAX 65536u
#define INVALID_EXPERT UINT16_MAX

typedef struct {
    int16_t x[D];
    int16_t nx[D];
    uint8_t action;
    uint8_t label;
    uint8_t state;
    uint8_t next_state;
} Event;

typedef struct {
    double key[D];
    double decode[D];
    double next[ACTIONS][D];
    uint32_t labels[CLASSES];
    uint32_t action_count[ACTIONS];
    uint32_t count;
    uint32_t errors;
    double reconstruction_sse;
    double prediction_sse;
    uint8_t label;
    uint8_t active;
    uint8_t lifecycle;
    uint16_t generation;
    uint64_t lineage;
} Expert;

typedef struct {
    uint16_t id[ROUTE_K];
    double excluded_lb;
} Cell;

typedef struct {
    Expert e[MAXE];
    Cell routing[CELLS];
    uint16_t next_graph[MAXE][ACTIONS];
    uint16_t n;
    uint64_t epoch;
    uint8_t identity[32];
} Model;

typedef struct {
    uint64_t samples;
    uint64_t rejected;
    uint64_t correct;
    uint64_t exact_mismatches;
    uint64_t certified;
    uint64_t expert_evaluations;
    double reconstruction_sse;
    double prediction_sse;
    uint64_t transition_correct;
    uint64_t classification_checksum;
    uint64_t reconstruction_checksum;
    uint64_t prediction_checksum;
    uint64_t transition_checksum;
} Eval;

typedef struct {
    uint64_t samples;
    uint64_t expert_evaluations;
    uint64_t certified;
    uint64_t births;
    uint64_t retired;
} TrainMetric;

typedef struct {
    uint64_t cases;
    uint64_t path_found;
    uint64_t exact_state_targets;
    uint64_t goal_expert_targets;
    uint64_t executed_path_length;
    uint64_t optimal_path_length;
    uint64_t path_length_regret;
    uint64_t graph_disconnection_failures;
    uint64_t transition_model_failures;
    uint64_t state_aliasing_failures;
    uint64_t expansions;
    uint64_t checksum;
} PlanMetric;

typedef struct {
    int16_t center[STATES][D];
    uint8_t label[STATES];
    uint8_t base_next[STATES][ACTIONS];
    uint8_t drift_next[STATES][ACTIONS];
} World;

typedef struct {
    const char *trial_id;
    const char *regime;
    uint64_t seed;
    int amplitude;
    int base_noise;
    int drift_noise;
    uint8_t label_drift;
    uint8_t observation_drift;
    uint8_t transition_drift;
    uint8_t ambiguous;
} TrialSpec;

typedef struct {
    uint64_t expert_evaluations;
    uint8_t use_replay;
    uint8_t use_retirement;
    uint8_t routed;
    uint8_t recursive_births;
    uint8_t random_births;
} VariantConfig;

typedef struct {
    uint8_t data[CHECKPOINT_MAX];
    size_t len;
    int ok;
} ByteBuffer;

typedef struct {
    const uint8_t *data;
    size_t len;
    size_t pos;
    int ok;
} ByteReader;

typedef struct {
    uint32_t h[8];
    uint64_t bits;
    uint8_t block[64];
    size_t used;
} Sha256;

static const TrialSpec trial_specs[TRIALS] = {
    {"trial-01-separated", "separated_state", UINT64_C(0x0401000000000001), 42, 5, 5, 0, 0, 0, 0},
    {"trial-02-overlap", "partially_overlapping_observations", UINT64_C(0x0402000000000002), 22, 7, 7, 0, 0, 0, 0},
    {"trial-03-noise", "increased_observation_noise", UINT64_C(0x0403000000000003), 42, 13, 19, 0, 0, 0, 0},
    {"trial-04-label", "label_drift", UINT64_C(0x0404000000000004), 42, 5, 5, 1, 0, 0, 0},
    {"trial-05-observation", "observation_drift", UINT64_C(0x0405000000000005), 42, 5, 7, 0, 1, 0, 0},
    {"trial-06-transition", "transition_drift", UINT64_C(0x0406000000000006), 42, 5, 5, 0, 0, 1, 0},
    {"trial-07-combined", "combined_observation_and_label_drift", UINT64_C(0x0407000000000007), 34, 7, 11, 1, 1, 0, 0},
    {"trial-08-ambiguous", "partially_observed_ambiguous", UINT64_C(0x0408000000000008), 30, 9, 11, 1, 1, 1, 1}
};

static uint64_t rng_state;

static uint32_t rng_u32(void) {
    rng_state ^= rng_state >> 12;
    rng_state ^= rng_state << 25;
    rng_state ^= rng_state >> 27;
    return (uint32_t)((rng_state * UINT64_C(2685821657736338717)) >> 32);
}

static uint64_t mix64(uint64_t x) {
    x ^= x >> 30;
    x *= UINT64_C(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x *= UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}

static int16_t clamp_domain(int v) {
    if (v < LO) return (int16_t)LO;
    if (v > HI) return (int16_t)HI;
    return (int16_t)v;
}

static int64_t q20(double v) {
    return (int64_t)llround(v * Q20_SCALE);
}

static double from_q20(int64_t v) {
    return (double)v / Q20_SCALE;
}

static uint32_t rotr32(uint32_t x, uint32_t n) {
    return (x >> n) | (x << (32u - n));
}

static void sha256_transform(Sha256 *s, const uint8_t block[64]) {
    static const uint32_t k[64] = {
        UINT32_C(0x428a2f98), UINT32_C(0x71374491), UINT32_C(0xb5c0fbcf), UINT32_C(0xe9b5dba5),
        UINT32_C(0x3956c25b), UINT32_C(0x59f111f1), UINT32_C(0x923f82a4), UINT32_C(0xab1c5ed5),
        UINT32_C(0xd807aa98), UINT32_C(0x12835b01), UINT32_C(0x243185be), UINT32_C(0x550c7dc3),
        UINT32_C(0x72be5d74), UINT32_C(0x80deb1fe), UINT32_C(0x9bdc06a7), UINT32_C(0xc19bf174),
        UINT32_C(0xe49b69c1), UINT32_C(0xefbe4786), UINT32_C(0x0fc19dc6), UINT32_C(0x240ca1cc),
        UINT32_C(0x2de92c6f), UINT32_C(0x4a7484aa), UINT32_C(0x5cb0a9dc), UINT32_C(0x76f988da),
        UINT32_C(0x983e5152), UINT32_C(0xa831c66d), UINT32_C(0xb00327c8), UINT32_C(0xbf597fc7),
        UINT32_C(0xc6e00bf3), UINT32_C(0xd5a79147), UINT32_C(0x06ca6351), UINT32_C(0x14292967),
        UINT32_C(0x27b70a85), UINT32_C(0x2e1b2138), UINT32_C(0x4d2c6dfc), UINT32_C(0x53380d13),
        UINT32_C(0x650a7354), UINT32_C(0x766a0abb), UINT32_C(0x81c2c92e), UINT32_C(0x92722c85),
        UINT32_C(0xa2bfe8a1), UINT32_C(0xa81a664b), UINT32_C(0xc24b8b70), UINT32_C(0xc76c51a3),
        UINT32_C(0xd192e819), UINT32_C(0xd6990624), UINT32_C(0xf40e3585), UINT32_C(0x106aa070),
        UINT32_C(0x19a4c116), UINT32_C(0x1e376c08), UINT32_C(0x2748774c), UINT32_C(0x34b0bcb5),
        UINT32_C(0x391c0cb3), UINT32_C(0x4ed8aa4a), UINT32_C(0x5b9cca4f), UINT32_C(0x682e6ff3),
        UINT32_C(0x748f82ee), UINT32_C(0x78a5636f), UINT32_C(0x84c87814), UINT32_C(0x8cc70208),
        UINT32_C(0x90befffa), UINT32_C(0xa4506ceb), UINT32_C(0xbef9a3f7), UINT32_C(0xc67178f2)
    };
    uint32_t w[64];
    for (uint32_t i = 0; i < 16u; ++i) {
        w[i] = ((uint32_t)block[i * 4u] << 24) | ((uint32_t)block[i * 4u + 1u] << 16) |
               ((uint32_t)block[i * 4u + 2u] << 8) | (uint32_t)block[i * 4u + 3u];
    }
    for (uint32_t i = 16u; i < 64u; ++i) {
        uint32_t a = w[i - 15u], b = w[i - 2u];
        uint32_t s0 = rotr32(a, 7u) ^ rotr32(a, 18u) ^ (a >> 3);
        uint32_t s1 = rotr32(b, 17u) ^ rotr32(b, 19u) ^ (b >> 10);
        w[i] = w[i - 16u] + s0 + w[i - 7u] + s1;
    }
    uint32_t a = s->h[0], b = s->h[1], c = s->h[2], d = s->h[3];
    uint32_t e = s->h[4], f = s->h[5], g = s->h[6], h = s->h[7];
    for (uint32_t i = 0; i < 64u; ++i) {
        uint32_t s1 = rotr32(e, 6u) ^ rotr32(e, 11u) ^ rotr32(e, 25u);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t t1 = h + s1 + ch + k[i] + w[i];
        uint32_t s0 = rotr32(a, 2u) ^ rotr32(a, 13u) ^ rotr32(a, 22u);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = s0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    s->h[0] += a; s->h[1] += b; s->h[2] += c; s->h[3] += d;
    s->h[4] += e; s->h[5] += f; s->h[6] += g; s->h[7] += h;
}

static void sha256_init(Sha256 *s) {
    static const uint32_t initial[8] = {
        UINT32_C(0x6a09e667), UINT32_C(0xbb67ae85), UINT32_C(0x3c6ef372), UINT32_C(0xa54ff53a),
        UINT32_C(0x510e527f), UINT32_C(0x9b05688c), UINT32_C(0x1f83d9ab), UINT32_C(0x5be0cd19)
    };
    memcpy(s->h, initial, sizeof initial);
    s->bits = 0u;
    s->used = 0u;
}

static void sha256_update(Sha256 *s, const uint8_t *data, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        s->block[s->used++] = data[i];
        if (s->used == 64u) {
            sha256_transform(s, s->block);
            s->bits += 512u;
            s->used = 0u;
        }
    }
}

static void sha256_final(Sha256 *s, uint8_t out[32]) {
    s->bits += (uint64_t)s->used * 8u;
    s->block[s->used++] = 0x80u;
    if (s->used > 56u) {
        while (s->used < 64u) s->block[s->used++] = 0u;
        sha256_transform(s, s->block);
        s->used = 0u;
    }
    while (s->used < 56u) s->block[s->used++] = 0u;
    for (uint32_t i = 0; i < 8u; ++i) s->block[63u - i] = (uint8_t)(s->bits >> (i * 8u));
    sha256_transform(s, s->block);
    for (uint32_t i = 0; i < 8u; ++i) {
        out[i * 4u] = (uint8_t)(s->h[i] >> 24);
        out[i * 4u + 1u] = (uint8_t)(s->h[i] >> 16);
        out[i * 4u + 2u] = (uint8_t)(s->h[i] >> 8);
        out[i * 4u + 3u] = (uint8_t)s->h[i];
    }
}

static void sha256_bytes(const uint8_t *data, size_t n, uint8_t out[32]) {
    Sha256 s;
    sha256_init(&s);
    sha256_update(&s, data, n);
    sha256_final(&s, out);
}

static int event_valid(const Event *ev) {
    if (ev == NULL || ev->action >= ACTIONS || ev->label >= CLASSES ||
        ev->state >= STATES || ev->next_state >= STATES) return 0;
    for (uint32_t d = 0; d < D; ++d) {
        if (ev->x[d] < LO || ev->x[d] > HI || ev->nx[d] < LO || ev->nx[d] > HI) return 0;
    }
    return 1;
}

static void make_world(World *w, const TrialSpec *spec) {
    memset(w, 0, sizeof *w);
    for (uint32_t s = 0; s < STATES; ++s) {
        uint32_t visible = spec->ambiguous ? s / 2u : s;
        for (uint32_t d = 0; d < 6u; ++d) {
            w->center[s][d] = (int16_t)(((visible >> d) & 1u) ? spec->amplitude : -spec->amplitude);
        }
        w->center[s][6] = (int16_t)(-30 + 20 * (int)((visible * 5u + (visible >> 2)) & 3u));
        w->center[s][7] = (int16_t)(-30 + 20 * (int)((visible * 3u + (visible >> 1)) & 3u));
        w->label[s] = (uint8_t)(((visible * 29u) ^ (visible >> 1) ^ (visible >> 3)) & 7u);
        w->base_next[s][0] = (uint8_t)((s + 1u) & 63u);
        w->base_next[s][1] = (uint8_t)((s + 63u) & 63u);
        w->base_next[s][2] = (uint8_t)(s ^ 8u);
        w->base_next[s][3] = (uint8_t)(s ^ 32u);
        for (uint32_t a = 0; a < ACTIONS; ++a) w->drift_next[s][a] = w->base_next[s][a];
        if (spec->transition_drift && s < 24u) {
            w->drift_next[s][0] = (uint8_t)(s ^ 16u);
            w->drift_next[s][2] = (uint8_t)((s + 2u) & 63u);
        }
    }
}

static void make_observation(const World *w, const TrialSpec *spec, uint8_t state,
                             int drift, int noise, int16_t out[D]) {
    for (uint32_t d = 0; d < D; ++d) {
        int shift = 0;
        if (drift && spec->observation_drift && state < 24u) {
            if (d == 6u) shift = 16;
            if (d == 7u) shift = -16;
        }
        int jitter = noise == 0 ? 0 : (int)(rng_u32() % (uint32_t)(2 * noise + 1)) - noise;
        out[d] = clamp_domain((int)w->center[state][d] + shift + jitter);
    }
}

static void make_dataset(const World *w, const TrialSpec *spec, Event *out, uint32_t n,
                         uint64_t seed, int drift) {
    rng_state = seed;
    int noise = drift ? spec->drift_noise : spec->base_noise;
    for (uint32_t i = 0; i < n; ++i) {
        uint8_t s = (uint8_t)(rng_u32() % STATES);
        uint8_t a = (uint8_t)(rng_u32() % ACTIONS);
        const uint8_t (*next)[ACTIONS] = drift ? w->drift_next : w->base_next;
        uint8_t ns = next[s][a];
        out[i].state = s;
        out[i].next_state = ns;
        out[i].action = a;
        out[i].label = (uint8_t)(drift && spec->label_drift && s < 24u
                                     ? ((w->label[s] + 3u) & 7u) : w->label[s]);
        make_observation(w, spec, s, drift, noise, out[i].x);
        make_observation(w, spec, ns, drift, noise, out[i].nx);
    }
}

static double dist_x(const int16_t x[D], const Expert *e) {
    double total = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double delta = (double)x[d] - e->key[d];
        total += delta * delta;
    }
    return total;
}

static double dist_vec(const double a[D], const double b[D]) {
    double total = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double delta = a[d] - b[d];
        total += delta * delta;
    }
    return total;
}

static int better(double d, uint16_t id, double best_d, uint16_t best_id) {
    return d < best_d || (d == best_d && id < best_id);
}

static uint8_t majority(const uint32_t counts[CLASSES]) {
    uint8_t best = 0u;
    for (uint8_t y = 1u; y < CLASSES; ++y) if (counts[y] > counts[best]) best = y;
    return best;
}

static uint16_t cell_id(const int16_t x[D], int *in_domain) {
    uint16_t cell = 0u;
    *in_domain = 1;
    for (uint32_t d = 0; d < D; ++d) if (x[d] < LO || x[d] > HI) *in_domain = 0;
    for (uint32_t d = 0; d < 4u; ++d) {
        int v = ((int)x[d] - LO) / 32;
        if (v < 0) v = 0;
        if (v > 3) v = 3;
        cell = (uint16_t)((cell << 2) | (uint16_t)v);
    }
    return cell;
}

static double axis_lb(double c, double lo, double hi) {
    if (c < lo) { double v = lo - c; return v * v; }
    if (c > hi) { double v = c - hi; return v * v; }
    return 0.0;
}

static void build_lattice(Model *m) {
    for (uint32_t b = 0; b < CELLS; ++b) {
        double distances[MAXE];
        uint16_t ids[MAXE];
        for (uint16_t j = 0; j < m->n; ++j) {
            double lower = 0.0;
            for (uint32_t d = 0; d < 4u; ++d) {
                uint32_t shift = 2u * (3u - d);
                uint32_t v = (b >> shift) & 3u;
                double lo = (double)(LO + 32 * (int)v);
                lower += axis_lb(m->e[j].key[d], lo, lo + 31.0);
            }
            distances[j] = lower;
            ids[j] = j;
        }
        uint16_t take = m->n < ROUTE_K ? m->n : ROUTE_K;
        uint16_t need = m->n > ROUTE_K ? (uint16_t)(ROUTE_K + 1u) : m->n;
        for (uint16_t i = 0; i < need; ++i) {
            uint16_t best = i;
            for (uint16_t j = (uint16_t)(i + 1u); j < m->n; ++j) {
                if (better(distances[j], ids[j], distances[best], ids[best])) best = j;
            }
            double td = distances[i]; distances[i] = distances[best]; distances[best] = td;
            uint16_t ti = ids[i]; ids[i] = ids[best]; ids[best] = ti;
        }
        for (uint16_t i = 0; i < ROUTE_K; ++i) m->routing[b].id[i] = INVALID_EXPERT;
        for (uint16_t i = 0; i < take; ++i) m->routing[b].id[i] = ids[i];
        m->routing[b].excluded_lb = m->n > ROUTE_K ? distances[ROUTE_K] : DBL_MAX;
    }
}

static uint16_t full_nearest(const int16_t x[D], const Model *m, uint64_t *evaluations) {
    if (m->n == 0u) return INVALID_EXPERT;
    double best_d = DBL_MAX;
    uint16_t best = INVALID_EXPERT;
    for (uint16_t j = 0; j < m->n; ++j) {
        double d = dist_x(x, &m->e[j]);
        ++*evaluations;
        if (better(d, j, best_d, best)) { best_d = d; best = j; }
    }
    return best;
}

static uint16_t routed_nearest(const int16_t x[D], const Model *m, uint64_t *evaluations,
                               uint64_t *certified) {
    if (m->n == 0u) return INVALID_EXPERT;
    int in_domain = 0;
    uint16_t cell = cell_id(x, &in_domain);
    uint8_t seen[MAXE] = {0};
    double best_d = DBL_MAX;
    uint16_t best = INVALID_EXPERT;
    uint16_t take = m->n < ROUTE_K ? m->n : ROUTE_K;
    for (uint16_t i = 0; i < take; ++i) {
        uint16_t j = m->routing[cell].id[i];
        if (j >= m->n) return INVALID_EXPERT;
        seen[j] = 1u;
        double d = dist_x(x, &m->e[j]);
        ++*evaluations;
        if (better(d, j, best_d, best)) { best_d = d; best = j; }
    }
    if (in_domain && best_d < m->routing[cell].excluded_lb) {
        ++*certified;
        return best;
    }
    for (uint16_t j = 0; j < m->n; ++j) if (!seen[j]) {
        double d = dist_x(x, &m->e[j]);
        ++*evaluations;
        if (better(d, j, best_d, best)) { best_d = d; best = j; }
    }
    return best;
}

static void seed_expert(Expert *e, const Event *ev, uint64_t lineage, uint16_t generation,
                        uint8_t lifecycle) {
    memset(e, 0, sizeof *e);
    for (uint32_t d = 0; d < D; ++d) {
        e->key[d] = (double)ev->x[d];
        e->decode[d] = (double)ev->x[d];
        for (uint32_t a = 0; a < ACTIONS; ++a) e->next[a][d] = (double)ev->nx[d];
    }
    e->label = ev->label;
    e->active = 1u;
    e->lifecycle = lifecycle;
    e->generation = generation;
    e->lineage = lineage;
}

static void init_farthest(Model *m, uint16_t n, const Event *data, uint32_t count,
                          TrainMetric *tm) {
    memset(m, 0, sizeof *m);
    m->n = n;
    seed_expert(&m->e[0], &data[0], mix64(UINT64_C(0x524156454c040001)), 0u, 0u);
    for (uint16_t k = 1; k < n; ++k) {
        double farthest = -1.0;
        uint32_t far_i = 0u;
        for (uint32_t i = 0; i < count; ++i) {
            double nearest = DBL_MAX;
            for (uint16_t j = 0; j < k; ++j) {
                double d = dist_x(data[i].x, &m->e[j]);
                ++tm->expert_evaluations;
                if (d < nearest) nearest = d;
            }
            if (nearest > farthest) { farthest = nearest; far_i = i; }
        }
        seed_expert(&m->e[k], &data[far_i], mix64(m->e[0].lineage ^ k), 0u, 0u);
    }
    build_lattice(m);
}

static void refine(Model *m, const Event *data, uint32_t count, uint32_t iterations,
                   int routed, uint16_t *assignments, TrainMetric *tm) {
    for (uint32_t iteration = 0; iteration < iterations; ++iteration) {
        double key_sum[MAXE][D] = {{0}};
        double decode_sum[MAXE][D] = {{0}};
        double next_sum[MAXE][ACTIONS][D] = {{{0}}};
        uint32_t counts[MAXE] = {0};
        uint32_t labels[MAXE][CLASSES] = {{0}};
        uint32_t action_count[MAXE][ACTIONS] = {{0}};
        uint32_t errors[MAXE] = {0};
        double reconstruction_sse[MAXE] = {0};
        double prediction_sse[MAXE] = {0};
        build_lattice(m);
        for (uint32_t i = 0; i < count; ++i) {
            if (!event_valid(&data[i])) continue;
            uint16_t j = routed
                ? routed_nearest(data[i].x, m, &tm->expert_evaluations, &tm->certified)
                : full_nearest(data[i].x, m, &tm->expert_evaluations);
            if (j == INVALID_EXPERT) continue;
            ++tm->samples;
            if (assignments != NULL) assignments[i] = j;
            ++counts[j];
            ++labels[j][data[i].label];
            ++action_count[j][data[i].action];
            if (m->e[j].label != data[i].label) ++errors[j];
            for (uint32_t d = 0; d < D; ++d) {
                double x = (double)data[i].x[d], nx = (double)data[i].nx[d];
                key_sum[j][d] += x;
                decode_sum[j][d] += x;
                next_sum[j][data[i].action][d] += nx;
                double rv = x - m->e[j].decode[d];
                double pv = nx - m->e[j].next[data[i].action][d];
                reconstruction_sse[j] += rv * rv;
                prediction_sse[j] += pv * pv;
            }
        }
        for (uint16_t j = 0; j < m->n; ++j) {
            m->e[j].count = counts[j];
            m->e[j].errors = errors[j];
            m->e[j].reconstruction_sse = reconstruction_sse[j];
            m->e[j].prediction_sse = prediction_sse[j];
            memcpy(m->e[j].labels, labels[j], sizeof labels[j]);
            memcpy(m->e[j].action_count, action_count[j], sizeof action_count[j]);
            if (counts[j] == 0u) continue;
            for (uint32_t d = 0; d < D; ++d) {
                m->e[j].key[d] = key_sum[j][d] / (double)counts[j];
                m->e[j].decode[d] = decode_sum[j][d] / (double)counts[j];
            }
            m->e[j].label = majority(labels[j]);
            for (uint32_t a = 0; a < ACTIONS; ++a) if (action_count[j][a] != 0u) {
                for (uint32_t d = 0; d < D; ++d) {
                    m->e[j].next[a][d] = next_sum[j][a][d] / (double)action_count[j][a];
                }
            }
        }
    }
    build_lattice(m);
}

static double split_score(const Expert *e) {
    if (e->count < 2u) return -1.0;
    return (double)e->errors * 1e12 + e->prediction_sse * 1e3 +
           e->reconstruction_sse + (double)e->count;
}

static int split_one(Model *m, uint16_t parent, uint16_t child, const Event *data,
                     uint32_t count, const uint16_t *assignments, uint32_t round) {
    if (parent >= m->n || child >= MAXE || assignments == NULL) return 0;
    uint32_t first = UINT32_MAX;
    for (uint32_t i = 0; i < count; ++i) if (assignments[i] == parent) { first = i; break; }
    if (first == UINT32_MAX) return 0;
    uint32_t a = first, b = first;
    double farthest = -1.0;
    for (uint32_t i = 0; i < count; ++i) if (assignments[i] == parent) {
        double d = 0.0;
        for (uint32_t k = 0; k < D; ++k) {
            double delta = (double)data[i].x[k] - data[first].x[k];
            d += delta * delta;
        }
        if (d > farthest) { farthest = d; a = i; }
    }
    farthest = -1.0;
    for (uint32_t i = 0; i < count; ++i) if (assignments[i] == parent) {
        double d = 0.0;
        for (uint32_t k = 0; k < D; ++k) {
            double delta = (double)data[i].x[k] - data[a].x[k];
            d += delta * delta;
        }
        if (d > farthest) { farthest = d; b = i; }
    }
    if (a == b) return 0;
    uint64_t original_lineage = m->e[parent].lineage;
    uint16_t original_generation = m->e[parent].generation;
    uint8_t lifecycle = m->e[parent].lifecycle;
    uint16_t child_generation = (uint16_t)(original_generation + 1u);
    seed_expert(&m->e[parent], &data[a],
                mix64(original_lineage ^ ((uint64_t)round << 32) ^ UINT64_C(0xa5)),
                child_generation, lifecycle);
    seed_expert(&m->e[child], &data[b],
                mix64(original_lineage ^ ((uint64_t)round << 32) ^ UINT64_C(0x5a)),
                child_generation, lifecycle);
    return m->e[parent].lineage != m->e[child].lineage;
}

static void train_recursive(Model *m, const Event *data, uint32_t count, TrainMetric *tm) {
    uint16_t assignments[BASE_TRAIN_N];
    init_farthest(m, INIT_E, data, count, tm);
    uint32_t round = 0u;
    while (m->n < BASE_E) {
        refine(m, data, count, 1u, 1, assignments, tm);
        uint16_t order[MAXE];
        for (uint16_t j = 0; j < m->n; ++j) order[j] = j;
        for (uint16_t i = 0; i < m->n; ++i) {
            uint16_t best = i;
            for (uint16_t j = (uint16_t)(i + 1u); j < m->n; ++j) {
                double x = split_score(&m->e[order[j]]);
                double y = split_score(&m->e[order[best]]);
                if (x > y || (x == y && order[j] < order[best])) best = j;
            }
            uint16_t tmp = order[i]; order[i] = order[best]; order[best] = tmp;
        }
        uint16_t target = (uint16_t)((BASE_E - m->n) < 8u ? (BASE_E - m->n) : 8u);
        uint16_t made = 0u;
        uint16_t old_n = m->n;
        for (uint16_t i = 0; i < old_n && made < target; ++i) {
            if (split_one(m, order[i], (uint16_t)(old_n + made), data, count,
                          assignments, round)) {
                ++made;
                ++tm->births;
            }
        }
        if (made == 0u) break;
        m->n = (uint16_t)(old_n + made);
        ++round;
    }
    refine(m, data, count, 3u, 1, NULL, tm);
    ++m->epoch;
}

static int add_adaptation_experts(Model *m, const Event *data, uint32_t count,
                                  int random_births, TrainMetric *tm) {
    if (m->n > MAXE || ADAPT_BIRTHS > MAXE - m->n) return 0;
    double score[ADAPT_TRAIN_N];
    uint8_t selected[ADAPT_TRAIN_N] = {0};
    build_lattice(m);
    for (uint32_t i = 0; i < count; ++i) {
        if (!event_valid(&data[i])) return 0;
        uint64_t evaluations = 0u, certified = 0u;
        uint16_t j = routed_nearest(data[i].x, m, &evaluations, &certified);
        if (j == INVALID_EXPERT) return 0;
        tm->expert_evaluations += evaluations;
        tm->certified += certified;
        ++tm->samples;
        double prediction = 0.0;
        for (uint32_t d = 0; d < D; ++d) {
            double delta = (double)data[i].nx[d] - m->e[j].next[data[i].action][d];
            prediction += delta * delta;
        }
        score[i] = (m->e[j].label != data[i].label ? 1e12 : 0.0) + prediction;
    }
    for (uint16_t birth = 0; birth < ADAPT_BIRTHS; ++birth) {
        uint32_t best = UINT32_MAX;
        double best_score = -DBL_MAX;
        if (random_births) {
            uint32_t start = (uint32_t)(mix64(m->epoch ^ birth) % count);
            for (uint32_t k = 0; k < count; ++k) {
                uint32_t i = (start + k) % count;
                if (!selected[i]) { best = i; break; }
            }
        } else {
            for (uint32_t i = 0; i < count; ++i) if (!selected[i]) {
                double separation = DBL_MAX;
                for (uint16_t j = 0; j < m->n; ++j) {
                    double d = dist_x(data[i].x, &m->e[j]);
                    if (d < separation) separation = d;
                }
                double candidate = score[i] + separation * 1e6;
                if (candidate > best_score ||
                    (candidate == best_score && (best == UINT32_MAX || i < best))) {
                    best_score = candidate;
                    best = i;
                }
            }
        }
        if (best == UINT32_MAX) return 0;
        selected[best] = 1u;
        uint16_t id = m->n;
        seed_expert(&m->e[id], &data[best],
                    mix64(UINT64_C(0x4144415054424952) ^ m->epoch ^ id ^ best),
                    (uint16_t)(m->epoch + 1u), 1u);
        ++m->n;
        ++tm->births;
    }
    build_lattice(m);
    return 1;
}

static int duplicate_experts(const Model *m) {
    for (uint16_t i = 0; i < m->n; ++i) {
        for (uint16_t j = (uint16_t)(i + 1u); j < m->n; ++j) {
            if (m->e[i].lineage == m->e[j].lineage) return 1;
            int same = m->e[i].label == m->e[j].label;
            for (uint32_t d = 0; d < D && same; ++d) {
                if (q20(m->e[i].key[d]) != q20(m->e[j].key[d])) same = 0;
            }
            if (same) return 1;
        }
    }
    return 0;
}

static int remove_expert(Model *m, uint16_t victim, int adaptation_only) {
    if (victim >= m->n) return 0;
    if (adaptation_only && m->e[victim].lifecycle != 1u) return 0;
    uint16_t last = (uint16_t)(m->n - 1u);
    if (victim != last) m->e[victim] = m->e[last];
    memset(&m->e[last], 0, sizeof m->e[last]);
    --m->n;
    return 1;
}

static int retire_adaptation_to(Model *m, uint16_t target, const Event *data,
                                uint32_t count, TrainMetric *tm) {
    while (m->n > target) {
        uint16_t victim = INVALID_EXPERT;
        double lowest = DBL_MAX;
        for (uint16_t j = 0; j < m->n; ++j) if (m->e[j].lifecycle == 1u) {
            double utility = (double)m->e[j].count * 1e9 -
                             (double)m->e[j].errors * 1e12 - m->e[j].prediction_sse;
            if (victim == INVALID_EXPERT || utility < lowest ||
                (utility == lowest && j > victim)) {
                victim = j;
                lowest = utility;
            }
        }
        if (victim == INVALID_EXPERT || !remove_expert(m, victim, 1)) return 0;
        ++tm->retired;
        refine(m, data, count, 1u, 1, NULL, tm);
    }
    return 1;
}

static int adapt_model(Model *m, const Event *base_train, const Event *adapt_train,
                       const VariantConfig *config, TrainMetric *tm) {
    Event mix[ADAPT_TRAIN_N + REPLAY_N];
    uint32_t mix_n = ADAPT_TRAIN_N;
    memcpy(mix, adapt_train, sizeof(Event) * ADAPT_TRAIN_N);
    if (config->use_replay) {
        for (uint32_t i = 0; i < REPLAY_N; ++i) {
            mix[ADAPT_TRAIN_N + i] = base_train[(i * 4u) % BASE_TRAIN_N];
        }
        mix_n += REPLAY_N;
    }
    if (config->recursive_births &&
        !add_adaptation_experts(m, adapt_train, ADAPT_TRAIN_N, config->random_births, tm)) {
        return 0;
    }
    refine(m, mix, mix_n, 4u, config->routed, NULL, tm);
    if (config->use_retirement && m->n > ADAPTED_E &&
        !retire_adaptation_to(m, ADAPTED_E, mix, mix_n, tm)) return 0;
    ++m->epoch;
    return 1;
}

static uint16_t nearest_vector(const double vector[D], const Model *m) {
    double best_d = DBL_MAX;
    uint16_t best = INVALID_EXPERT;
    for (uint16_t j = 0; j < m->n; ++j) {
        double d = dist_vec(vector, m->e[j].key);
        if (better(d, j, best_d, best)) { best_d = d; best = j; }
    }
    return best;
}

static void compile_graph(Model *m) {
    for (uint16_t j = 0; j < m->n; ++j) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            m->next_graph[j][action] = nearest_vector(m->e[j].next[action], m);
        }
    }
    for (uint16_t j = m->n; j < MAXE; ++j) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            m->next_graph[j][action] = INVALID_EXPERT;
        }
    }
}

static void canonicalize_model(Model *m) {
    for (uint16_t j = 0; j < m->n; ++j) {
        for (uint32_t d = 0; d < D; ++d) {
            m->e[j].key[d] = from_q20(q20(m->e[j].key[d]));
            m->e[j].decode[d] = from_q20(q20(m->e[j].decode[d]));
            for (uint32_t a = 0; a < ACTIONS; ++a) {
                m->e[j].next[a][d] = from_q20(q20(m->e[j].next[a][d]));
            }
        }
        m->e[j].reconstruction_sse = from_q20(q20(m->e[j].reconstruction_sse));
        m->e[j].prediction_sse = from_q20(q20(m->e[j].prediction_sse));
    }
    build_lattice(m);
    for (uint32_t b = 0; b < CELLS; ++b) {
        if (m->routing[b].excluded_lb != DBL_MAX) {
            m->routing[b].excluded_lb = from_q20(q20(m->routing[b].excluded_lb));
        }
    }
    compile_graph(m);
}

static Eval evaluate(const Model *m, const Event *data, uint32_t count, int routed) {
    Eval out = {0};
    for (uint32_t i = 0; i < count; ++i) {
        if (!event_valid(&data[i])) { ++out.rejected; continue; }
        uint16_t got = routed
            ? routed_nearest(data[i].x, m, &out.expert_evaluations, &out.certified)
            : full_nearest(data[i].x, m, &out.expert_evaluations);
        uint64_t oracle_evaluations = 0u;
        uint16_t oracle = full_nearest(data[i].x, m, &oracle_evaluations);
        if (got == INVALID_EXPERT || oracle == INVALID_EXPERT) { ++out.rejected; continue; }
        if (got != oracle) ++out.exact_mismatches;
        if (m->e[got].label == data[i].label) ++out.correct;
        double predicted[D];
        int64_t reconstruction_quantized = 0;
        int64_t prediction_quantized = 0;
        for (uint32_t d = 0; d < D; ++d) {
            double rv = (double)data[i].x[d] - m->e[got].decode[d];
            double pv = (double)data[i].nx[d] - m->e[got].next[data[i].action][d];
            out.reconstruction_sse += rv * rv;
            out.prediction_sse += pv * pv;
            reconstruction_quantized += q20(rv * rv);
            prediction_quantized += q20(pv * pv);
            predicted[d] = m->e[got].next[data[i].action][d];
        }
        uint16_t predicted_next = nearest_vector(predicted, m);
        uint64_t next_evaluations = 0u;
        uint16_t observed_next = full_nearest(data[i].nx, m, &next_evaluations);
        if (predicted_next == observed_next) ++out.transition_correct;
        ++out.samples;
        out.classification_checksum ^= mix64(((uint64_t)got << 48) ^
                                             ((uint64_t)m->e[got].label << 32) ^ i);
        out.reconstruction_checksum ^= mix64((uint64_t)reconstruction_quantized ^ i);
        out.prediction_checksum ^= mix64((uint64_t)prediction_quantized ^ ((uint64_t)i << 16));
        out.transition_checksum ^= mix64(((uint64_t)predicted_next << 32) ^ observed_next ^ i);
    }
    return out;
}

static int plan_actions(const Model *m, uint16_t start, uint16_t goal,
                        uint8_t actions[PLAN_LIMIT], uint32_t *used, uint64_t *expansions) {
    if (start >= m->n || goal >= m->n) return 0;
    uint16_t queue[MAXE], parent[MAXE], parent_action[MAXE];
    uint8_t seen[MAXE] = {0};
    for (uint16_t i = 0; i < MAXE; ++i) {
        parent[i] = INVALID_EXPERT;
        parent_action[i] = INVALID_EXPERT;
    }
    uint16_t head = 0u, tail = 0u;
    queue[tail++] = start;
    seen[start] = 1u;
    while (head < tail) {
        uint16_t current = queue[head++];
        ++*expansions;
        if (current == goal) break;
        for (uint16_t action = 0; action < ACTIONS; ++action) {
            uint16_t next = m->next_graph[current][action];
            if (next >= m->n) return 0;
            if (!seen[next]) {
                seen[next] = 1u;
                parent[next] = current;
                parent_action[next] = action;
                queue[tail++] = next;
            }
        }
    }
    if (!seen[goal]) return 0;
    uint8_t reverse[PLAN_LIMIT];
    uint32_t n = 0u;
    uint16_t current = goal;
    while (current != start && n < PLAN_LIMIT) {
        reverse[n++] = (uint8_t)parent_action[current];
        current = parent[current];
    }
    if (current != start) return 0;
    for (uint32_t i = 0; i < n; ++i) actions[i] = reverse[n - i - 1u];
    *used = n;
    return 1;
}

static uint32_t optimal_world_path(const uint8_t transitions[STATES][ACTIONS],
                                   uint8_t start, uint8_t goal) {
    uint8_t queue[STATES], seen[STATES] = {0};
    uint16_t distance[STATES] = {0};
    uint16_t head = 0u, tail = 0u;
    queue[tail++] = start;
    seen[start] = 1u;
    while (head < tail) {
        uint8_t current = queue[head++];
        if (current == goal) return distance[current];
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            uint8_t next = transitions[current][action];
            if (!seen[next]) {
                seen[next] = 1u;
                distance[next] = (uint16_t)(distance[current] + 1u);
                queue[tail++] = next;
            }
        }
    }
    return UINT32_MAX;
}

static PlanMetric evaluate_planning(const Model *m, const World *world,
                                    const TrialSpec *spec, uint64_t seed, int drift) {
    PlanMetric out = {0};
    rng_state = seed;
    const uint8_t (*transitions)[ACTIONS] = drift ? world->drift_next : world->base_next;
    for (uint32_t i = 0; i < PLAN_N; ++i) {
        uint8_t start_state = (uint8_t)(rng_u32() % STATES);
        uint8_t goal_state = (uint8_t)(rng_u32() % STATES);
        int16_t start_observation[D], goal_observation[D];
        make_observation(world, spec, start_state, drift, 0, start_observation);
        make_observation(world, spec, goal_state, drift, 0, goal_observation);
        uint64_t evaluations = 0u, certified = 0u;
        uint16_t start_expert = routed_nearest(start_observation, m, &evaluations, &certified);
        uint16_t goal_expert = routed_nearest(goal_observation, m, &evaluations, &certified);
        uint8_t actions[PLAN_LIMIT];
        uint32_t used = 0u;
        ++out.cases;
        uint32_t optimal = optimal_world_path(transitions, start_state, goal_state);
        if (optimal != UINT32_MAX) out.optimal_path_length += optimal;
        if (!plan_actions(m, start_expert, goal_expert, actions, &used, &out.expansions)) {
            ++out.graph_disconnection_failures;
            continue;
        }
        ++out.path_found;
        out.executed_path_length += used;
        uint8_t current = start_state;
        for (uint32_t step = 0; step < used; ++step) current = transitions[current][actions[step]];
        int16_t final_observation[D];
        make_observation(world, spec, current, drift, 0, final_observation);
        uint16_t final_expert = routed_nearest(final_observation, m, &evaluations, &certified);
        int exact = current == goal_state;
        int expert_goal = final_expert == goal_expert;
        if (exact) {
            ++out.exact_state_targets;
            if (optimal != UINT32_MAX && used >= optimal) out.path_length_regret += used - optimal;
        }
        if (expert_goal) ++out.goal_expert_targets;
        if (!exact && expert_goal) ++out.state_aliasing_failures;
        if (!exact && !expert_goal) ++out.transition_model_failures;
        out.checksum ^= mix64(((uint64_t)start_state << 56) ^ ((uint64_t)goal_state << 48) ^
                              ((uint64_t)current << 40) ^ ((uint64_t)start_expert << 24) ^
                              ((uint64_t)goal_expert << 8) ^ used ^ i);
    }
    return out;
}

static void bb_bytes(ByteBuffer *b, const uint8_t *data, size_t n) {
    if (!b->ok || n > CHECKPOINT_MAX - b->len) { b->ok = 0; return; }
    memcpy(b->data + b->len, data, n);
    b->len += n;
}

static void bb_u8(ByteBuffer *b, uint8_t v) {
    bb_bytes(b, &v, 1u);
}

static void bb_u16(ByteBuffer *b, uint16_t v) {
    uint8_t bytes[2] = {(uint8_t)(v >> 8), (uint8_t)v};
    bb_bytes(b, bytes, sizeof bytes);
}

static void bb_u32(ByteBuffer *b, uint32_t v) {
    uint8_t bytes[4] = {
        (uint8_t)(v >> 24), (uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v
    };
    bb_bytes(b, bytes, sizeof bytes);
}

static void bb_u64(ByteBuffer *b, uint64_t v) {
    uint8_t bytes[8];
    for (uint32_t i = 0; i < 8u; ++i) bytes[7u - i] = (uint8_t)(v >> (i * 8u));
    bb_bytes(b, bytes, sizeof bytes);
}

static void bb_i64(ByteBuffer *b, int64_t v) {
    bb_u64(b, (uint64_t)v);
}

static void br_bytes(ByteReader *r, uint8_t *out, size_t n) {
    if (!r->ok || n > r->len - r->pos) { r->ok = 0; return; }
    memcpy(out, r->data + r->pos, n);
    r->pos += n;
}

static uint8_t br_u8(ByteReader *r) {
    uint8_t out = 0u;
    br_bytes(r, &out, 1u);
    return out;
}

static uint16_t br_u16(ByteReader *r) {
    uint8_t bytes[2] = {0};
    br_bytes(r, bytes, sizeof bytes);
    return (uint16_t)(((uint16_t)bytes[0] << 8) | bytes[1]);
}

static uint32_t br_u32(ByteReader *r) {
    uint8_t bytes[4] = {0};
    br_bytes(r, bytes, sizeof bytes);
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | bytes[3];
}

static uint64_t br_u64(ByteReader *r) {
    uint8_t bytes[8] = {0};
    br_bytes(r, bytes, sizeof bytes);
    uint64_t out = 0u;
    for (uint32_t i = 0; i < 8u; ++i) out = (out << 8) | bytes[i];
    return out;
}

static int64_t br_i64(ByteReader *r) {
    return (int64_t)br_u64(r);
}

static int serialize_checkpoint(const Model *m, ByteBuffer *checkpoint) {
    static const uint8_t magic[8] = {'R', 'A', 'V', 'E', 'L', '0', '4', 0};
    if (m == NULL || m->n == 0u || m->n > MAXE) return 0;
    ByteBuffer payload = {{0}, 0u, 1};
    bb_u16(&payload, m->n);
    bb_u64(&payload, m->epoch);
    for (uint16_t j = 0; j < m->n; ++j) {
        const Expert *e = &m->e[j];
        bb_u16(&payload, j);
        bb_u8(&payload, e->active);
        bb_u8(&payload, e->lifecycle);
        bb_u16(&payload, e->generation);
        bb_u8(&payload, e->label);
        bb_u64(&payload, e->lineage);
        for (uint32_t d = 0; d < D; ++d) bb_i64(&payload, q20(e->key[d]));
        for (uint32_t d = 0; d < D; ++d) bb_i64(&payload, q20(e->decode[d]));
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t d = 0; d < D; ++d) bb_i64(&payload, q20(e->next[a][d]));
        }
        for (uint32_t y = 0; y < CLASSES; ++y) bb_u32(&payload, e->labels[y]);
        for (uint32_t a = 0; a < ACTIONS; ++a) bb_u32(&payload, e->action_count[a]);
        bb_u32(&payload, e->count);
        bb_u32(&payload, e->errors);
        bb_i64(&payload, q20(e->reconstruction_sse));
        bb_i64(&payload, q20(e->prediction_sse));
    }
    for (uint16_t j = 0; j < m->n; ++j) {
        bb_u16(&payload, j);
        for (uint32_t a = 0; a < ACTIONS; ++a) bb_u16(&payload, m->next_graph[j][a]);
    }
    for (uint16_t cell = 0; cell < CELLS; ++cell) {
        bb_u16(&payload, cell);
        for (uint32_t i = 0; i < ROUTE_K; ++i) bb_u16(&payload, m->routing[cell].id[i]);
        int64_t lower = m->routing[cell].excluded_lb == DBL_MAX
                            ? INT64_MAX : q20(m->routing[cell].excluded_lb);
        bb_i64(&payload, lower);
    }
    if (!payload.ok || payload.len > UINT32_MAX) return 0;
    uint8_t digest[32];
    sha256_bytes(payload.data, payload.len, digest);
    *checkpoint = (ByteBuffer){{0}, 0u, 1};
    bb_bytes(checkpoint, magic, sizeof magic);
    bb_u16(checkpoint, CHECKPOINT_SCHEMA);
    bb_u16(checkpoint, D);
    bb_u16(checkpoint, CLASSES);
    bb_u16(checkpoint, ACTIONS);
    bb_u16(checkpoint, STATES);
    bb_u16(checkpoint, MAXE);
    bb_u16(checkpoint, ROUTE_K);
    bb_u16(checkpoint, CELLS);
    bb_u32(checkpoint, UINT32_C(0x01020304));
    bb_u32(checkpoint, (uint32_t)payload.len);
    bb_bytes(checkpoint, digest, sizeof digest);
    if (checkpoint->len != CHECKPOINT_HEADER) return 0;
    bb_bytes(checkpoint, payload.data, payload.len);
    return checkpoint->ok;
}

static int deserialize_checkpoint(const uint8_t *bytes, size_t size, Model *out) {
    static const uint8_t magic[8] = {'R', 'A', 'V', 'E', 'L', '0', '4', 0};
    if (bytes == NULL || out == NULL || size < CHECKPOINT_HEADER || size > CHECKPOINT_MAX) return 0;
    ByteReader header = {bytes, size, 0u, 1};
    uint8_t got_magic[8], expected_digest[32], actual_digest[32];
    br_bytes(&header, got_magic, sizeof got_magic);
    uint16_t schema = br_u16(&header);
    uint16_t dimensions = br_u16(&header);
    uint16_t classes = br_u16(&header);
    uint16_t actions = br_u16(&header);
    uint16_t states = br_u16(&header);
    uint16_t maximum = br_u16(&header);
    uint16_t route_width = br_u16(&header);
    uint16_t cells = br_u16(&header);
    uint32_t byte_order = br_u32(&header);
    uint32_t payload_length = br_u32(&header);
    br_bytes(&header, expected_digest, sizeof expected_digest);
    if (!header.ok || header.pos != CHECKPOINT_HEADER ||
        memcmp(got_magic, magic, sizeof magic) != 0 ||
        schema != CHECKPOINT_SCHEMA || dimensions != D || classes != CLASSES ||
        actions != ACTIONS || states != STATES || maximum != MAXE ||
        route_width != ROUTE_K || cells != CELLS ||
        byte_order != UINT32_C(0x01020304) ||
        payload_length > CHECKPOINT_MAX - CHECKPOINT_HEADER ||
        size != CHECKPOINT_HEADER + (size_t)payload_length) return 0;
    sha256_bytes(bytes + CHECKPOINT_HEADER, payload_length, actual_digest);
    if (memcmp(expected_digest, actual_digest, sizeof expected_digest) != 0) return 0;
    ByteReader payload = {
        bytes + CHECKPOINT_HEADER, payload_length, 0u, 1
    };
    Model model;
    memset(&model, 0, sizeof model);
    model.n = br_u16(&payload);
    model.epoch = br_u64(&payload);
    if (!payload.ok || model.n == 0u || model.n > MAXE) return 0;
    for (uint16_t j = 0; j < model.n; ++j) {
        Expert *e = &model.e[j];
        if (br_u16(&payload) != j) return 0;
        e->active = br_u8(&payload);
        e->lifecycle = br_u8(&payload);
        e->generation = br_u16(&payload);
        e->label = br_u8(&payload);
        e->lineage = br_u64(&payload);
        for (uint32_t d = 0; d < D; ++d) e->key[d] = from_q20(br_i64(&payload));
        for (uint32_t d = 0; d < D; ++d) e->decode[d] = from_q20(br_i64(&payload));
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t d = 0; d < D; ++d) e->next[a][d] = from_q20(br_i64(&payload));
        }
        for (uint32_t y = 0; y < CLASSES; ++y) e->labels[y] = br_u32(&payload);
        for (uint32_t a = 0; a < ACTIONS; ++a) e->action_count[a] = br_u32(&payload);
        e->count = br_u32(&payload);
        e->errors = br_u32(&payload);
        e->reconstruction_sse = from_q20(br_i64(&payload));
        e->prediction_sse = from_q20(br_i64(&payload));
        if (!payload.ok || e->active != 1u || e->lifecycle > 1u ||
            e->label >= CLASSES || e->lineage == 0u || e->errors > e->count) return 0;
    }
    for (uint16_t j = 0; j < model.n; ++j) {
        if (br_u16(&payload) != j) return 0;
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            model.next_graph[j][a] = br_u16(&payload);
            if (model.next_graph[j][a] >= model.n) return 0;
        }
    }
    uint16_t take = model.n < ROUTE_K ? model.n : ROUTE_K;
    for (uint16_t cell = 0; cell < CELLS; ++cell) {
        if (br_u16(&payload) != cell) return 0;
        for (uint16_t i = 0; i < ROUTE_K; ++i) {
            uint16_t id = br_u16(&payload);
            model.routing[cell].id[i] = id;
            if ((i < take && id >= model.n) || (i >= take && id != INVALID_EXPERT)) return 0;
            for (uint16_t k = 0; k < i; ++k) if (model.routing[cell].id[k] == id) return 0;
        }
        int64_t lower = br_i64(&payload);
        model.routing[cell].excluded_lb = lower == INT64_MAX ? DBL_MAX : from_q20(lower);
        if (model.n > ROUTE_K && lower == INT64_MAX) return 0;
        if (model.n <= ROUTE_K && lower != INT64_MAX) return 0;
    }
    if (!payload.ok || payload.pos != payload.len) return 0;
    memcpy(model.identity, expected_digest, sizeof model.identity);
    *out = model;
    return 1;
}

static int checkpoint_file_roundtrip(Model *model, Model *restored, size_t *checkpoint_size) {
    const char *path = "ravel-0.4-checkpoint.bin";
    ByteBuffer checkpoint;
    if (!serialize_checkpoint(model, &checkpoint)) return 0;
    memcpy(model->identity, checkpoint.data + 32u, sizeof model->identity);
    FILE *file = fopen(path, "wb");
    if (file == NULL) return 0;
    size_t wrote = fwrite(checkpoint.data, 1u, checkpoint.len, file);
    int ok = wrote == checkpoint.len && fclose(file) == 0;
    if (!ok) { remove(path); return 0; }
    file = fopen(path, "rb");
    if (file == NULL) { remove(path); return 0; }
    uint8_t bytes[CHECKPOINT_MAX + 1u];
    size_t read = fread(bytes, 1u, sizeof bytes, file);
    int read_ok = !ferror(file) && fclose(file) == 0;
    remove(path);
    if (!read_ok || read > CHECKPOINT_MAX ||
        !deserialize_checkpoint(bytes, read, restored)) return 0;
    *checkpoint_size = checkpoint.len;
    return 1;
}

static int eval_equal(const Eval *a, const Eval *b) {
    return a->samples == b->samples && a->rejected == b->rejected &&
           a->correct == b->correct && a->exact_mismatches == b->exact_mismatches &&
           a->certified == b->certified &&
           a->expert_evaluations == b->expert_evaluations &&
           a->reconstruction_sse == b->reconstruction_sse &&
           a->prediction_sse == b->prediction_sse &&
           a->transition_correct == b->transition_correct &&
           a->classification_checksum == b->classification_checksum &&
           a->reconstruction_checksum == b->reconstruction_checksum &&
           a->prediction_checksum == b->prediction_checksum &&
           a->transition_checksum == b->transition_checksum;
}

static int plan_equal(const PlanMetric *a, const PlanMetric *b) {
    return memcmp(a, b, sizeof *a) == 0;
}

static void behavior_digest(const Model *m, const Eval *evaluation,
                            const PlanMetric *planning, uint8_t out[32]) {
    ByteBuffer b = {{0}, 0u, 1};
    bb_bytes(&b, m->identity, sizeof m->identity);
    bb_u64(&b, evaluation->samples);
    bb_u64(&b, evaluation->rejected);
    bb_u64(&b, evaluation->correct);
    bb_u64(&b, evaluation->exact_mismatches);
    bb_u64(&b, evaluation->certified);
    bb_u64(&b, evaluation->expert_evaluations);
    bb_i64(&b, q20(evaluation->reconstruction_sse));
    bb_i64(&b, q20(evaluation->prediction_sse));
    bb_u64(&b, evaluation->transition_correct);
    bb_u64(&b, evaluation->classification_checksum);
    bb_u64(&b, evaluation->reconstruction_checksum);
    bb_u64(&b, evaluation->prediction_checksum);
    bb_u64(&b, evaluation->transition_checksum);
    bb_u64(&b, planning->cases);
    bb_u64(&b, planning->path_found);
    bb_u64(&b, planning->exact_state_targets);
    bb_u64(&b, planning->goal_expert_targets);
    bb_u64(&b, planning->executed_path_length);
    bb_u64(&b, planning->optimal_path_length);
    bb_u64(&b, planning->path_length_regret);
    bb_u64(&b, planning->graph_disconnection_failures);
    bb_u64(&b, planning->transition_model_failures);
    bb_u64(&b, planning->state_aliasing_failures);
    bb_u64(&b, planning->expansions);
    bb_u64(&b, planning->checksum);
    sha256_bytes(b.data, b.len, out);
}

static int checkpoint_equivalent(const Model *expected, const Model *restored,
                                 const Eval *expected_eval, const Eval *restored_eval,
                                 const PlanMetric *expected_plan,
                                 const PlanMetric *restored_plan) {
    uint8_t expected_behavior[32], restored_behavior[32];
    behavior_digest(expected, expected_eval, expected_plan, expected_behavior);
    behavior_digest(restored, restored_eval, restored_plan, restored_behavior);
    return memcmp(expected->identity, restored->identity, 32u) == 0 &&
           eval_equal(expected_eval, restored_eval) &&
           plan_equal(expected_plan, restored_plan) &&
           memcmp(expected_behavior, restored_behavior, 32u) == 0;
}

static int valid_model_mutation_detected(const Model *original, const Model *mutated) {
    ByteBuffer checkpoint;
    Model restored;
    if (!serialize_checkpoint(mutated, &checkpoint) ||
        !deserialize_checkpoint(checkpoint.data, checkpoint.len, &restored)) return 0;
    return memcmp(original->identity, restored.identity, sizeof original->identity) != 0;
}

typedef struct {
    int retrieval_key;
    int reconstruction;
    int next_observation;
    int label;
    int label_count;
    int lineage;
    int transition_graph;
    int payload_byte;
    int truncation;
    int appended_byte;
    int schema_version;
    int checkpoint_substitution;
} MutationResult;

static MutationResult checkpoint_mutations(const Model *original) {
    MutationResult result = {0};
    Model mutated = *original;
    mutated.e[0].key[0] += from_q20(1);
    result.retrieval_key = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    mutated.e[0].decode[0] += from_q20(1);
    result.reconstruction = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    mutated.e[0].next[0][0] += from_q20(1);
    result.next_observation = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    mutated.e[0].label = (uint8_t)((mutated.e[0].label + 1u) % CLASSES);
    result.label = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    ++mutated.e[0].labels[0];
    result.label_count = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    mutated.e[0].lineage ^= UINT64_C(0x1);
    result.lineage = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    mutated.next_graph[0][0] = (uint16_t)((mutated.next_graph[0][0] + 1u) % mutated.n);
    result.transition_graph = valid_model_mutation_detected(original, &mutated);

    ByteBuffer checkpoint;
    if (serialize_checkpoint(original, &checkpoint)) {
        ByteBuffer corrupt = checkpoint;
        corrupt.data[CHECKPOINT_HEADER + 3u] ^= 0x01u;
        Model restored;
        result.payload_byte = !deserialize_checkpoint(corrupt.data, corrupt.len, &restored);
        result.truncation = !deserialize_checkpoint(checkpoint.data, checkpoint.len - 1u, &restored);
        corrupt = checkpoint;
        corrupt.data[corrupt.len++] = 0u;
        result.appended_byte = !deserialize_checkpoint(corrupt.data, corrupt.len, &restored);
        corrupt = checkpoint;
        corrupt.data[8] = 0u;
        corrupt.data[9] = (uint8_t)(CHECKPOINT_SCHEMA + 1u);
        result.schema_version = !deserialize_checkpoint(corrupt.data, corrupt.len, &restored);
        mutated = *original;
        mutated.epoch += 1u;
        ByteBuffer substitute;
        if (serialize_checkpoint(&mutated, &substitute) &&
            deserialize_checkpoint(substitute.data, substitute.len, &restored)) {
            result.checkpoint_substitution =
                memcmp(original->identity, restored.identity, sizeof original->identity) != 0;
        }
    }
    return result;
}

static int mutation_result_pass(const MutationResult *m) {
    return m->retrieval_key && m->reconstruction && m->next_observation &&
           m->label && m->label_count && m->lineage && m->transition_graph &&
           m->payload_byte && m->truncation && m->appended_byte &&
           m->schema_version && m->checkpoint_substitution;
}

typedef struct {
    int sibling_generation_equality;
    int parent_child_increment;
    int lineage_uniqueness;
    int repeated_descendant_increment;
    int no_lineage_reuse;
    int deterministic_topology;
} LineageResult;

static LineageResult lineage_invariants(const Event *data) {
    LineageResult result = {0};
    Model model;
    memset(&model, 0, sizeof model);
    model.n = 1u;
    seed_expert(&model.e[0], &data[0], mix64(UINT64_C(0x1122334455667788)), 4u, 0u);
    uint16_t assignments[BASE_TRAIN_N];
    for (uint32_t i = 0; i < BASE_TRAIN_N; ++i) assignments[i] = 0u;
    uint16_t original_generation = model.e[0].generation;
    int first_split = split_one(&model, 0u, 1u, data, BASE_TRAIN_N, assignments, 17u);
    if (first_split) {
        model.n = 2u;
        result.sibling_generation_equality =
            model.e[0].generation == model.e[1].generation;
        result.parent_child_increment =
            model.e[0].generation == (uint16_t)(original_generation + 1u);
        result.lineage_uniqueness = model.e[0].lineage != model.e[1].lineage;
        for (uint32_t i = 0; i < BASE_TRAIN_N; ++i) assignments[i] = 1u;
        uint16_t descendant_generation = model.e[1].generation;
        if (split_one(&model, 1u, 2u, data, BASE_TRAIN_N, assignments, 18u)) {
            model.n = 3u;
            result.repeated_descendant_increment =
                model.e[1].generation == (uint16_t)(descendant_generation + 1u) &&
                model.e[2].generation == model.e[1].generation;
            result.no_lineage_reuse = 1;
            for (uint16_t i = 0; i < model.n; ++i) {
                for (uint16_t j = (uint16_t)(i + 1u); j < model.n; ++j) {
                    if (model.e[i].lineage == model.e[j].lineage) result.no_lineage_reuse = 0;
                }
            }
        }
    }
    Model first, second;
    TrainMetric first_tm = {0}, second_tm = {0};
    train_recursive(&first, data, BASE_TRAIN_N, &first_tm);
    train_recursive(&second, data, BASE_TRAIN_N, &second_tm);
    canonicalize_model(&first);
    canonicalize_model(&second);
    ByteBuffer first_checkpoint, second_checkpoint;
    if (serialize_checkpoint(&first, &first_checkpoint) &&
        serialize_checkpoint(&second, &second_checkpoint)) {
        result.deterministic_topology =
            first_checkpoint.len == second_checkpoint.len &&
            memcmp(first_checkpoint.data, second_checkpoint.data, first_checkpoint.len) == 0;
    }
    return result;
}

static int lineage_result_pass(const LineageResult *r) {
    return r->sibling_generation_equality && r->parent_child_increment &&
           r->lineage_uniqueness && r->repeated_descendant_increment &&
           r->no_lineage_reuse && r->deterministic_topology;
}

typedef struct {
    int malformed_observation_rejected;
    int out_of_domain_fallback;
    int empty_assignment_rejected;
    int degenerate_assignment_rejected;
    int duplicate_expert_rejected;
    int tied_distance_lower_id;
    int lower_bound_equality_fallback;
    int maximum_capacity_preserved;
    int birth_beyond_capacity_rejected;
    int wrong_lifecycle_retirement_rejected;
    int poisoned_labels_fail_gate;
    int poisoned_transitions_fail_gate;
    int replay_removal_fail_gate;
    int catastrophic_forgetting_fail_gate;
} NegativeResult;

static double eval_accuracy(const Eval *e) {
    return e->samples == 0u ? 0.0 : (double)e->correct / (double)e->samples;
}

static double reconstruction_rmse(const Eval *e) {
    return e->samples == 0u ? DBL_MAX : sqrt(e->reconstruction_sse / (double)(e->samples * D));
}

static double prediction_rmse(const Eval *e) {
    return e->samples == 0u ? DBL_MAX : sqrt(e->prediction_sse / (double)(e->samples * D));
}

static NegativeResult run_negative_tests(const Model *base, const Event *base_train,
                                         const Event *retention, const Event *adapt_train,
                                         const Event *drift_hold) {
    NegativeResult result = {0};
    Event malformed = adapt_train[0];
    malformed.action = ACTIONS;
    result.malformed_observation_rejected = !event_valid(&malformed);

    int16_t out_of_domain[D] = {100, 0, 0, 0, 0, 0, 0, 0};
    uint64_t evaluations = 0u, certified = 0u;
    uint16_t fallback = routed_nearest(out_of_domain, base, &evaluations, &certified);
    result.out_of_domain_fallback =
        fallback != INVALID_EXPERT && certified == 0u && evaluations == base->n;

    Model empty;
    memset(&empty, 0, sizeof empty);
    evaluations = 0u;
    result.empty_assignment_rejected =
        full_nearest(base_train[0].x, &empty, &evaluations) == INVALID_EXPERT;

    Model degenerate;
    memset(&degenerate, 0, sizeof degenerate);
    degenerate.n = 1u;
    seed_expert(&degenerate.e[0], &base_train[0], mix64(1u), 0u, 0u);
    Event identical[2] = {base_train[0], base_train[0]};
    uint16_t assignments[2] = {0u, 0u};
    result.degenerate_assignment_rejected =
        !split_one(&degenerate, 0u, 1u, identical, 2u, assignments, 0u);

    Model duplicate = *base;
    duplicate.e[1] = duplicate.e[0];
    result.duplicate_expert_rejected = duplicate_experts(&duplicate);

    Model tie;
    memset(&tie, 0, sizeof tie);
    tie.n = 2u;
    seed_expert(&tie.e[0], &base_train[0], mix64(2u), 0u, 0u);
    tie.e[1] = tie.e[0];
    tie.e[1].lineage = mix64(3u);
    evaluations = 0u;
    result.tied_distance_lower_id =
        full_nearest(base_train[0].x, &tie, &evaluations) == 0u;

    Model equality = *base;
    int in_domain = 0;
    uint16_t cell = cell_id(base_train[0].x, &in_domain);
    double routed_best = DBL_MAX;
    for (uint16_t i = 0; i < ROUTE_K; ++i) {
        uint16_t candidate = equality.routing[cell].id[i];
        double distance = dist_x(base_train[0].x, &equality.e[candidate]);
        if (distance < routed_best) routed_best = distance;
    }
    equality.routing[cell].excluded_lb = routed_best;
    evaluations = 0u; certified = 0u;
    (void)routed_nearest(base_train[0].x, &equality, &evaluations, &certified);
    result.lower_bound_equality_fallback =
        in_domain && certified == 0u && evaluations == equality.n;

    Model capacity = *base;
    while (capacity.n < MAXE) {
        seed_expert(&capacity.e[capacity.n], &adapt_train[capacity.n % ADAPT_TRAIN_N],
                    mix64(UINT64_C(0x4341504143495459) ^ capacity.n), 1u, 1u);
        ++capacity.n;
    }
    result.maximum_capacity_preserved = capacity.n == MAXE;
    TrainMetric capacity_tm = {0};
    result.birth_beyond_capacity_rejected =
        !add_adaptation_experts(&capacity, adapt_train, ADAPT_TRAIN_N, 0, &capacity_tm) &&
        capacity.n == MAXE;

    Model lifecycle = *base;
    result.wrong_lifecycle_retirement_rejected = !remove_expert(&lifecycle, 0u, 1);

    Event poisoned_labels[ADAPT_TRAIN_N];
    Event poisoned_transitions[ADAPT_TRAIN_N];
    for (uint32_t i = 0; i < ADAPT_TRAIN_N; ++i) {
        poisoned_labels[i] = base_train[i % BASE_TRAIN_N];
        poisoned_labels[i].label = (uint8_t)((poisoned_labels[i].label + 1u) % CLASSES);
        poisoned_transitions[i] = adapt_train[i];
        for (uint32_t d = 0; d < D; ++d) {
            poisoned_transitions[i].nx[d] =
                clamp_domain(-(int)poisoned_transitions[i].nx[d]);
        }
    }
    VariantConfig no_replay = {0u, 0u, 0u, 1u, 0u, 0u};
    Model label_model = *base;
    TrainMetric label_tm = {0};
    int label_adapted = adapt_model(&label_model, base_train, poisoned_labels, &no_replay, &label_tm);
    canonicalize_model(&label_model);
    Eval label_retention = evaluate(&label_model, retention, RETENTION_N, 1);
    result.poisoned_labels_fail_gate =
        label_adapted && eval_accuracy(&label_retention) < 0.70;
    result.replay_removal_fail_gate = result.poisoned_labels_fail_gate;
    result.catastrophic_forgetting_fail_gate = result.poisoned_labels_fail_gate;

    Model transition_model = *base;
    TrainMetric transition_tm = {0};
    int transition_adapted =
        adapt_model(&transition_model, base_train, poisoned_transitions, &no_replay, &transition_tm);
    canonicalize_model(&transition_model);
    Eval transition_eval = evaluate(&transition_model, drift_hold, DRIFT_HOLD_N, 1);
    result.poisoned_transitions_fail_gate =
        transition_adapted && prediction_rmse(&transition_eval) > 24.0;
    return result;
}

static int negative_result_pass(const NegativeResult *r) {
    return r->malformed_observation_rejected && r->out_of_domain_fallback &&
           r->empty_assignment_rejected && r->degenerate_assignment_rejected &&
           r->duplicate_expert_rejected && r->tied_distance_lower_id &&
           r->lower_bound_equality_fallback && r->maximum_capacity_preserved &&
           r->birth_beyond_capacity_rejected &&
           r->wrong_lifecycle_retirement_rejected &&
           r->poisoned_labels_fail_gate && r->poisoned_transitions_fail_gate &&
           r->replay_removal_fail_gate && r->catastrophic_forgetting_fail_gate;
}

static void digest_hex(const uint8_t digest[32], char out[65]) {
    static const char hex[] = "0123456789abcdef";
    for (uint32_t i = 0; i < 32u; ++i) {
        out[i * 2u] = hex[digest[i] >> 4];
        out[i * 2u + 1u] = hex[digest[i] & 15u];
    }
    out[64] = '\0';
}

static void train_flat(Model *m, uint16_t experts, const Event *base_train,
                       TrainMetric *tm, int routed) {
    init_farthest(m, experts, base_train, BASE_TRAIN_N, tm);
    refine(m, base_train, BASE_TRAIN_N, 4u, routed, NULL, tm);
    ++m->epoch;
    canonicalize_model(m);
}

static size_t model_checkpoint_size(Model *m) {
    ByteBuffer checkpoint;
    if (!serialize_checkpoint(m, &checkpoint)) return 0u;
    memcpy(m->identity, checkpoint.data + 32u, sizeof m->identity);
    return checkpoint.len;
}

static void print_eval_json(const Eval *e) {
    printf("{\"samples\":%" PRIu64 ",\"rejected\":%" PRIu64
           ",\"accuracy\":%.9f,\"reconstruction_rmse\":%.9f"
           ",\"next_observation_prediction_rmse\":%.9f"
           ",\"transition_accuracy\":%.9f,\"routing_certification_count\":%" PRIu64
           ",\"complete_oracle_agreement\":%" PRIu64
           ",\"routed_complete_mismatches\":%" PRIu64
           ",\"expert_evaluations\":%" PRIu64
           ",\"classification_checksum\":\"%016" PRIx64 "\""
           ",\"reconstruction_checksum\":\"%016" PRIx64 "\""
           ",\"prediction_checksum\":\"%016" PRIx64 "\""
           ",\"transition_checksum\":\"%016" PRIx64 "\"}",
           e->samples, e->rejected, eval_accuracy(e), reconstruction_rmse(e),
           prediction_rmse(e),
           e->samples == 0u ? 0.0 : (double)e->transition_correct / (double)e->samples,
           e->certified, e->samples - e->exact_mismatches, e->exact_mismatches,
           e->expert_evaluations, e->classification_checksum,
           e->reconstruction_checksum, e->prediction_checksum, e->transition_checksum);
}

static void print_plan_json(const PlanMetric *p) {
    printf("{\"cases\":%" PRIu64 ",\"path_found\":%" PRIu64
           ",\"exact_world_state_target_reached\":%" PRIu64
           ",\"goal_expert_reached\":%" PRIu64
           ",\"executed_path_length\":%" PRIu64
           ",\"optimal_path_length\":%" PRIu64
           ",\"path_length_regret\":%" PRIu64
           ",\"graph_disconnection_failures\":%" PRIu64
           ",\"transition_model_error_failures\":%" PRIu64
           ",\"state_aliasing_failures\":%" PRIu64
           ",\"expansions\":%" PRIu64 ",\"checksum\":\"%016" PRIx64 "\"}",
           p->cases, p->path_found, p->exact_state_targets, p->goal_expert_targets,
           p->executed_path_length, p->optimal_path_length, p->path_length_regret,
           p->graph_disconnection_failures, p->transition_model_failures,
           p->state_aliasing_failures, p->expansions, p->checksum);
}

static void print_variant_json(const char *name, Model *m, const Eval *drift,
                               const Eval *retention, const PlanMetric *planning,
                               uint64_t training_evaluations, int comma) {
    size_t checkpoint_size = model_checkpoint_size(m);
    printf("        \"%s\":{\"expert_count\":%u,\"training_evaluations\":%" PRIu64
           ",\"drift_holdout_accuracy\":%.9f,\"retention_accuracy\":%.9f"
           ",\"reconstruction_rmse\":%.9f,\"prediction_rmse\":%.9f"
           ",\"planning_exact_state_rate\":%.9f"
           ",\"expert_evaluations\":%" PRIu64 ",\"checkpoint_size_bytes\":%zu"
           ",\"runtime_observation_non_normative\":{\"status\":\"UNKNOWN\","
           "\"reason\":\"excluded_from_canonical_deterministic_evidence\"}}%s\n",
           name, m->n, training_evaluations, eval_accuracy(drift), eval_accuracy(retention),
           reconstruction_rmse(drift), prediction_rmse(drift),
           planning->cases == 0u ? 0.0 :
               (double)planning->exact_state_targets / (double)planning->cases,
           drift->expert_evaluations, checkpoint_size, comma ? "," : "");
}

static void print_mutations_json(const MutationResult *m) {
    printf("{\"retrieval_key_component\":%s,\"reconstruction_component\":%s,"
           "\"next_observation_component\":%s,\"label\":%s,\"label_count\":%s,"
           "\"lineage\":%s,\"transition_graph_edge\":%s,\"payload_byte\":%s,"
           "\"checkpoint_truncation\":%s,\"appended_unexpected_byte\":%s,"
           "\"incorrect_schema_version\":%s,\"checkpoint_substitution\":%s}",
           m->retrieval_key ? "true" : "false",
           m->reconstruction ? "true" : "false",
           m->next_observation ? "true" : "false",
           m->label ? "true" : "false",
           m->label_count ? "true" : "false",
           m->lineage ? "true" : "false",
           m->transition_graph ? "true" : "false",
           m->payload_byte ? "true" : "false",
           m->truncation ? "true" : "false",
           m->appended_byte ? "true" : "false",
           m->schema_version ? "true" : "false",
           m->checkpoint_substitution ? "true" : "false");
}

static void print_lineage_json(const LineageResult *r) {
    printf("{\"sibling_generation_equality\":%s,\"parent_child_generation_increment\":%s,"
           "\"lineage_uniqueness\":%s,\"repeated_descendant_splitting\":%s,"
           "\"no_accidental_lineage_reuse\":%s,\"deterministic_topology_reproduction\":%s}",
           r->sibling_generation_equality ? "true" : "false",
           r->parent_child_increment ? "true" : "false",
           r->lineage_uniqueness ? "true" : "false",
           r->repeated_descendant_increment ? "true" : "false",
           r->no_lineage_reuse ? "true" : "false",
           r->deterministic_topology ? "true" : "false");
}

static void print_negative_case(const char *id, const char *expected, int observed, int comma) {
    printf("    \"%s\":{\"expected_disposition\":\"%s\",\"observed\":%s,\"pass\":%s}%s\n",
           id, expected, observed ? "true" : "false", observed ? "true" : "false",
           comma ? "," : "");
}

int main(void) {
    int all_trials_pass = 1;
    int execution_integrity = 1;
    uint32_t passing_trials = 0u, failing_trials = 0u;
    NegativeResult negative = {0};
    LineageResult lineage = {0};
    int have_global_tests = 0;

    printf("{\n  \"schema\":\"ravel-raw-observations/0.4\",\n");
    printf("  \"preregistration\":\"ravel-0.4-preregistration.json\",\n");
    printf("  \"checkpoint_format\":{\"magic\":\"RAVEL04\\\\u0000\",\"schema_version\":%u,"
           "\"byte_order\":\"big_endian\",\"real_encoding\":\"signed_q20_int64\","
           "\"payload_digest\":\"sha256\",\"maximum_bytes\":%u},\n",
           CHECKPOINT_SCHEMA, CHECKPOINT_MAX);
    printf("  \"trials\":[\n");

    for (uint32_t trial = 0; trial < TRIALS; ++trial) {
        const TrialSpec *spec = &trial_specs[trial];
        World world;
        Event base_train[BASE_TRAIN_N], base_hold[BASE_HOLD_N];
        Event adapt_train[ADAPT_TRAIN_N], drift_hold[DRIFT_HOLD_N];
        Event retention[RETENTION_N];
        make_world(&world, spec);
        uint64_t base_train_seed = mix64(spec->seed ^ UINT64_C(0x4241534554524149));
        uint64_t base_hold_seed = mix64(spec->seed ^ UINT64_C(0x42415345484f4c44));
        uint64_t adapt_train_seed = mix64(spec->seed ^ UINT64_C(0x414441505454524e));
        uint64_t drift_hold_seed = mix64(spec->seed ^ UINT64_C(0x4452494654484f4c));
        uint64_t retention_seed = mix64(spec->seed ^ UINT64_C(0x524554454e54494f));
        uint64_t planning_seed = mix64(spec->seed ^ UINT64_C(0x504c414e43415345));
        make_dataset(&world, spec, base_train, BASE_TRAIN_N, base_train_seed, 0);
        make_dataset(&world, spec, base_hold, BASE_HOLD_N, base_hold_seed, 0);
        make_dataset(&world, spec, adapt_train, ADAPT_TRAIN_N, adapt_train_seed, 1);
        make_dataset(&world, spec, drift_hold, DRIFT_HOLD_N, drift_hold_seed, 1);
        make_dataset(&world, spec, retention, RETENTION_N, retention_seed, 0);

        Model base;
        TrainMetric base_tm = {0};
        train_recursive(&base, base_train, BASE_TRAIN_N, &base_tm);
        canonicalize_model(&base);
        (void)model_checkpoint_size(&base);
        Eval base_hold_eval = evaluate(&base, base_hold, BASE_HOLD_N, 1);
        Eval static_drift_eval = evaluate(&base, drift_hold, DRIFT_HOLD_N, 1);

        Model adapted = base;
        TrainMetric adapt_tm = {0};
        VariantConfig candidate_config = {0u, 1u, 1u, 1u, 1u, 0u};
        int adaptation_ok =
            adapt_model(&adapted, base_train, adapt_train, &candidate_config, &adapt_tm);
        canonicalize_model(&adapted);
        Model restored;
        size_t checkpoint_size = 0u;
        int checkpoint_ok =
            adaptation_ok && checkpoint_file_roundtrip(&adapted, &restored, &checkpoint_size);
        Eval adaptation_training_eval = evaluate(&adapted, adapt_train, ADAPT_TRAIN_N, 1);
        Eval adapted_drift_eval = evaluate(&adapted, drift_hold, DRIFT_HOLD_N, 1);
        Eval retention_eval = evaluate(&adapted, retention, RETENTION_N, 1);
        PlanMetric adapted_plan =
            evaluate_planning(&adapted, &world, spec, planning_seed, 1);
        Eval restored_adaptation_training = checkpoint_ok
            ? evaluate(&restored, adapt_train, ADAPT_TRAIN_N, 1) : (Eval){0};
        Eval restored_drift = checkpoint_ok
            ? evaluate(&restored, drift_hold, DRIFT_HOLD_N, 1) : (Eval){0};
        Eval restored_retention = checkpoint_ok
            ? evaluate(&restored, retention, RETENTION_N, 1) : (Eval){0};
        PlanMetric restored_plan = checkpoint_ok
            ? evaluate_planning(&restored, &world, spec, planning_seed, 1) : (PlanMetric){0};
        int checkpoint_identity =
            checkpoint_ok && memcmp(adapted.identity, restored.identity, 32u) == 0;
        int checkpoint_adaptation_training =
            checkpoint_ok && eval_equal(&adaptation_training_eval,
                                        &restored_adaptation_training);
        int checkpoint_drift =
            checkpoint_ok && eval_equal(&adapted_drift_eval, &restored_drift);
        int checkpoint_retention =
            checkpoint_ok && eval_equal(&retention_eval, &restored_retention);
        int checkpoint_planning =
            checkpoint_ok && plan_equal(&adapted_plan, &restored_plan);
        int checkpoint_behavior =
            checkpoint_ok &&
            checkpoint_equivalent(&adapted, &restored, &adapted_drift_eval,
                                  &restored_drift, &adapted_plan, &restored_plan) &&
            checkpoint_adaptation_training && checkpoint_retention;
        MutationResult mutations = checkpoint_mutations(&adapted);
        int mutations_pass = mutation_result_pass(&mutations);

        if (!have_global_tests) {
            lineage = lineage_invariants(base_train);
            negative = run_negative_tests(&base, base_train, retention, adapt_train, drift_hold);
            have_global_tests = 1;
        }
        int lineage_pass = lineage_result_pass(&lineage);

        double base_accuracy = eval_accuracy(&base_hold_eval);
        double adaptation_training_accuracy = eval_accuracy(&adaptation_training_eval);
        double static_drift_accuracy = eval_accuracy(&static_drift_eval);
        double adapted_drift_accuracy = eval_accuracy(&adapted_drift_eval);
        double retention_accuracy = eval_accuracy(&retention_eval);
        double base_reconstruction = reconstruction_rmse(&base_hold_eval);
        double static_reconstruction = reconstruction_rmse(&static_drift_eval);
        double adapted_reconstruction = reconstruction_rmse(&adapted_drift_eval);
        double retention_reconstruction = reconstruction_rmse(&retention_eval);
        double base_prediction = prediction_rmse(&base_hold_eval);
        double static_prediction = prediction_rmse(&static_drift_eval);
        double adapted_prediction = prediction_rmse(&adapted_drift_eval);
        double retention_prediction = prediction_rmse(&retention_eval);
        double exact_state_rate = (double)adapted_plan.exact_state_targets / adapted_plan.cases;
        double path_found_rate = (double)adapted_plan.path_found / adapted_plan.cases;
        int exact_routing =
            base_hold_eval.exact_mismatches == 0u &&
            static_drift_eval.exact_mismatches == 0u &&
            adaptation_training_eval.exact_mismatches == 0u &&
            adapted_drift_eval.exact_mismatches == 0u &&
            retention_eval.exact_mismatches == 0u;
        int trial_pass =
            adapted.n == ADAPTED_E &&
            base_accuracy >= 0.75 &&
            adaptation_training_accuracy >= 0.70 &&
            adapted_drift_accuracy >= 0.70 &&
            adapted_drift_accuracy >= static_drift_accuracy + 0.05 &&
            retention_accuracy >= 0.70 &&
            exact_routing &&
            base_reconstruction <= 18.0 &&
            adapted_reconstruction <= 18.0 &&
            static_reconstruction - adapted_reconstruction >= 0.25 &&
            retention_reconstruction - base_reconstruction <= 4.0 &&
            base_prediction <= 24.0 &&
            adapted_prediction <= 24.0 &&
            static_prediction - adapted_prediction >= 0.25 &&
            retention_prediction - base_prediction <= 5.0 &&
            exact_state_rate >= 0.60 &&
            path_found_rate >= 0.70 &&
            checkpoint_identity && checkpoint_behavior &&
            mutations_pass && lineage_pass;
        if (trial_pass) ++passing_trials;
        else { ++failing_trials; all_trials_pass = 0; }
        if (!checkpoint_ok || !checkpoint_identity || !checkpoint_behavior ||
            !mutations_pass || !lineage_pass) execution_integrity = 0;

        char model_identity[65], behavior_identity[65];
        uint8_t behavior[32];
        digest_hex(adapted.identity, model_identity);
        behavior_digest(&adapted, &adapted_drift_eval, &adapted_plan, behavior);
        digest_hex(behavior, behavior_identity);

        printf("    {\n      \"trial_id\":\"%s\",\"regime\":\"%s\",\"seed\":\"0x%016" PRIx64 "\",\n",
               spec->trial_id, spec->regime, spec->seed);
        printf("      \"dataset_seeds\":{\"base_training\":\"0x%016" PRIx64
               "\",\"base_holdout\":\"0x%016" PRIx64
               "\",\"drift_adaptation_training\":\"0x%016" PRIx64
               "\",\"drift_holdout\":\"0x%016" PRIx64
               "\",\"original_task_retention_holdout\":\"0x%016" PRIx64
               "\",\"planning_cases\":\"0x%016" PRIx64 "\"},\n",
               base_train_seed, base_hold_seed, adapt_train_seed, drift_hold_seed,
               retention_seed, planning_seed);
        printf("      \"candidate\":{\"expert_count\":%u,\"base_births\":%" PRIu64
               ",\"adaptation_births\":%" PRIu64 ",\"adaptation_retirements\":%" PRIu64
               ",\"training_evaluations\":%" PRIu64 ",\"checkpoint_size_bytes\":%zu,"
               "\"model_identity\":\"%s\",\"behavior_identity\":\"%s\",\n",
               adapted.n, base_tm.births, adapt_tm.births, adapt_tm.retired,
               base_tm.expert_evaluations + adapt_tm.expert_evaluations,
               checkpoint_size, model_identity, behavior_identity);
        printf("        \"base_holdout\":"); print_eval_json(&base_hold_eval); printf(",\n");
        printf("        \"adaptation_training\":"); print_eval_json(&adaptation_training_eval); printf(",\n");
        printf("        \"static_model_drift_holdout\":"); print_eval_json(&static_drift_eval); printf(",\n");
        printf("        \"adapted_model_drift_holdout\":"); print_eval_json(&adapted_drift_eval); printf(",\n");
        printf("        \"base_holdout_retention\":"); print_eval_json(&retention_eval); printf(",\n");
        printf("        \"planning\":"); print_plan_json(&adapted_plan); printf("},\n");
        printf("      \"checkpoint_verification\":{\"roundtrip\":%s,\"identity_match\":%s,"
               "\"adaptation_training_evaluation_match\":%s,\"drift_holdout_evaluation_match\":%s,"
               "\"retention_evaluation_match\":%s,\"planning_match\":%s,"
               "\"complete_behavior_match\":%s,\"mutations\":",
               checkpoint_ok ? "true" : "false", checkpoint_identity ? "true" : "false",
               checkpoint_adaptation_training ? "true" : "false",
               checkpoint_drift ? "true" : "false",
               checkpoint_retention ? "true" : "false",
               checkpoint_planning ? "true" : "false",
               checkpoint_behavior ? "true" : "false");
        print_mutations_json(&mutations);
        printf("},\n      \"lineage_invariants\":"); print_lineage_json(&lineage); printf(",\n");

        printf("      \"comparisons\":{\n");
        Eval candidate_comparison_drift = adapted_drift_eval;
        Eval candidate_comparison_retention = retention_eval;
        print_variant_json("ravel_0_4_candidate", &adapted, &candidate_comparison_drift,
                           &candidate_comparison_retention, &adapted_plan,
                           base_tm.expert_evaluations + adapt_tm.expert_evaluations, 1);

        Model fixed8;
        TrainMetric fixed8_tm = {0};
        train_flat(&fixed8, 8u, base_train, &fixed8_tm, 0);
        Eval fixed8_drift = evaluate(&fixed8, drift_hold, DRIFT_HOLD_N, 0);
        Eval fixed8_retention = evaluate(&fixed8, retention, RETENTION_N, 0);
        PlanMetric fixed8_plan = evaluate_planning(&fixed8, &world, spec, planning_seed, 1);
        print_variant_json("fixed_8_expert", &fixed8, &fixed8_drift, &fixed8_retention,
                           &fixed8_plan, fixed8_tm.expert_evaluations, 1);

        Model flat64;
        TrainMetric flat64_tm = {0};
        train_flat(&flat64, 64u, base_train, &flat64_tm, 0);
        Eval flat64_drift = evaluate(&flat64, drift_hold, DRIFT_HOLD_N, 0);
        Eval flat64_retention = evaluate(&flat64, retention, RETENTION_N, 0);
        PlanMetric flat64_plan = evaluate_planning(&flat64, &world, spec, planning_seed, 1);
        print_variant_json("flat_64_expert_complete_scan", &flat64, &flat64_drift,
                           &flat64_retention, &flat64_plan, flat64_tm.expert_evaluations, 1);

        Eval routed64_drift = evaluate(&flat64, drift_hold, DRIFT_HOLD_N, 1);
        Eval routed64_retention = evaluate(&flat64, retention, RETENTION_N, 1);
        print_variant_json("fixed_topology_64_expert_routed", &flat64, &routed64_drift,
                           &routed64_retention, &flat64_plan, flat64_tm.expert_evaluations, 1);

        Model centroid16;
        TrainMetric centroid16_tm = {0};
        train_flat(&centroid16, 16u, base_train, &centroid16_tm, 0);
        Eval centroid16_drift = evaluate(&centroid16, drift_hold, DRIFT_HOLD_N, 0);
        Eval centroid16_retention = evaluate(&centroid16, retention, RETENTION_N, 0);
        PlanMetric centroid16_plan =
            evaluate_planning(&centroid16, &world, spec, planning_seed, 1);
        print_variant_json("nearest_centroid_16_no_recursive_births", &centroid16,
                           &centroid16_drift, &centroid16_retention, &centroid16_plan,
                           centroid16_tm.expert_evaluations, 1);

        PlanMetric static_plan = evaluate_planning(&base, &world, spec, planning_seed, 1);
        Eval static_retention = evaluate(&base, retention, RETENTION_N, 1);
        print_variant_json("no_adaptation_static", &base, &static_drift_eval,
                           &static_retention, &static_plan, base_tm.expert_evaluations, 1);

        Model no_replay_model = base;
        TrainMetric no_replay_tm = {0};
        VariantConfig no_replay_config = {0u, 0u, 1u, 1u, 1u, 0u};
        (void)adapt_model(&no_replay_model, base_train, adapt_train,
                          &no_replay_config, &no_replay_tm);
        canonicalize_model(&no_replay_model);
        Eval no_replay_drift = evaluate(&no_replay_model, drift_hold, DRIFT_HOLD_N, 1);
        Eval no_replay_retention = evaluate(&no_replay_model, retention, RETENTION_N, 1);
        PlanMetric no_replay_plan =
            evaluate_planning(&no_replay_model, &world, spec, planning_seed, 1);
        print_variant_json("ravel_without_replay", &no_replay_model, &no_replay_drift,
                           &no_replay_retention, &no_replay_plan,
                           base_tm.expert_evaluations + no_replay_tm.expert_evaluations, 1);

        Model no_retirement_model = base;
        TrainMetric no_retirement_tm = {0};
        VariantConfig no_retirement_config = {0u, 1u, 0u, 1u, 1u, 0u};
        (void)adapt_model(&no_retirement_model, base_train, adapt_train,
                          &no_retirement_config, &no_retirement_tm);
        canonicalize_model(&no_retirement_model);
        Eval no_retirement_drift =
            evaluate(&no_retirement_model, drift_hold, DRIFT_HOLD_N, 1);
        Eval no_retirement_retention =
            evaluate(&no_retirement_model, retention, RETENTION_N, 1);
        PlanMetric no_retirement_plan =
            evaluate_planning(&no_retirement_model, &world, spec, planning_seed, 1);
        print_variant_json("ravel_without_retirement", &no_retirement_model,
                           &no_retirement_drift, &no_retirement_retention,
                           &no_retirement_plan,
                           base_tm.expert_evaluations + no_retirement_tm.expert_evaluations, 1);

        Model complete_scan_model = base;
        TrainMetric complete_scan_tm = {0};
        VariantConfig complete_scan_config = {0u, 1u, 1u, 0u, 1u, 0u};
        (void)adapt_model(&complete_scan_model, base_train, adapt_train,
                          &complete_scan_config, &complete_scan_tm);
        canonicalize_model(&complete_scan_model);
        Eval complete_scan_drift =
            evaluate(&complete_scan_model, drift_hold, DRIFT_HOLD_N, 0);
        Eval complete_scan_retention =
            evaluate(&complete_scan_model, retention, RETENTION_N, 0);
        PlanMetric complete_scan_plan =
            evaluate_planning(&complete_scan_model, &world, spec, planning_seed, 1);
        print_variant_json("ravel_complete_scan_without_certification", &complete_scan_model,
                           &complete_scan_drift, &complete_scan_retention,
                           &complete_scan_plan,
                           base_tm.expert_evaluations + complete_scan_tm.expert_evaluations, 1);

        Model fixed_topology_model = flat64;
        TrainMetric fixed_topology_tm = {0};
        VariantConfig fixed_topology_config = {0u, 1u, 0u, 1u, 0u, 0u};
        (void)adapt_model(&fixed_topology_model, base_train, adapt_train,
                          &fixed_topology_config, &fixed_topology_tm);
        canonicalize_model(&fixed_topology_model);
        Eval fixed_topology_drift =
            evaluate(&fixed_topology_model, drift_hold, DRIFT_HOLD_N, 1);
        Eval fixed_topology_retention =
            evaluate(&fixed_topology_model, retention, RETENTION_N, 1);
        PlanMetric fixed_topology_plan =
            evaluate_planning(&fixed_topology_model, &world, spec, planning_seed, 1);
        print_variant_json("ravel_fixed_topology_without_recursive_births",
                           &fixed_topology_model, &fixed_topology_drift,
                           &fixed_topology_retention, &fixed_topology_plan,
                           flat64_tm.expert_evaluations +
                               fixed_topology_tm.expert_evaluations, 1);

        Model random_birth_model = base;
        TrainMetric random_birth_tm = {0};
        VariantConfig random_birth_config = {0u, 1u, 1u, 1u, 1u, 1u};
        (void)adapt_model(&random_birth_model, base_train, adapt_train,
                          &random_birth_config, &random_birth_tm);
        canonicalize_model(&random_birth_model);
        Eval random_birth_drift =
            evaluate(&random_birth_model, drift_hold, DRIFT_HOLD_N, 1);
        Eval random_birth_retention =
            evaluate(&random_birth_model, retention, RETENTION_N, 1);
        PlanMetric random_birth_plan =
            evaluate_planning(&random_birth_model, &world, spec, planning_seed, 1);
        print_variant_json("ravel_random_births", &random_birth_model,
                           &random_birth_drift, &random_birth_retention,
                           &random_birth_plan,
                           base_tm.expert_evaluations + random_birth_tm.expert_evaluations, 0);
        printf("      },\n");

        printf("      \"hard_gates\":{\"expected_topology\":%s,"
               "\"base_holdout_accuracy\":%s,\"adaptation_training_accuracy\":%s,"
               "\"adapted_drift_holdout_accuracy\":%s,\"adapted_gain_over_static\":%s,"
               "\"base_holdout_retention\":%s,\"exact_routing\":%s,"
               "\"base_reconstruction_rmse\":%s,\"adapted_reconstruction_rmse\":%s,"
               "\"adapted_reconstruction_improvement\":%s,"
               "\"retention_reconstruction\":%s,\"base_prediction_rmse\":%s,"
               "\"adapted_prediction_rmse\":%s,\"adapted_prediction_improvement\":%s,"
               "\"retention_prediction\":%s,\"exact_world_state_target_rate\":%s,"
               "\"path_found_rate\":%s,\"checkpoint_identity\":%s,"
               "\"checkpoint_behavior\":%s,\"checkpoint_mutations\":%s,"
               "\"lineage_and_topology\":%s},\n",
               adapted.n == ADAPTED_E ? "true" : "false",
               base_accuracy >= 0.75 ? "true" : "false",
               adaptation_training_accuracy >= 0.70 ? "true" : "false",
               adapted_drift_accuracy >= 0.70 ? "true" : "false",
               adapted_drift_accuracy >= static_drift_accuracy + 0.05 ? "true" : "false",
               retention_accuracy >= 0.70 ? "true" : "false",
               exact_routing ? "true" : "false",
               base_reconstruction <= 18.0 ? "true" : "false",
               adapted_reconstruction <= 18.0 ? "true" : "false",
               static_reconstruction - adapted_reconstruction >= 0.25 ? "true" : "false",
               retention_reconstruction - base_reconstruction <= 4.0 ? "true" : "false",
               base_prediction <= 24.0 ? "true" : "false",
               adapted_prediction <= 24.0 ? "true" : "false",
               static_prediction - adapted_prediction >= 0.25 ? "true" : "false",
               retention_prediction - base_prediction <= 5.0 ? "true" : "false",
               exact_state_rate >= 0.60 ? "true" : "false",
               path_found_rate >= 0.70 ? "true" : "false",
               checkpoint_identity ? "true" : "false",
               checkpoint_behavior ? "true" : "false",
               mutations_pass ? "true" : "false",
               lineage_pass ? "true" : "false");
        printf("      \"trial_result\":\"%s\"\n    }%s\n",
               trial_pass ? "PASS" : "FAIL", trial + 1u < TRIALS ? "," : "");
    }

    int negative_pass = negative_result_pass(&negative);
    if (!negative_pass) execution_integrity = 0;
    printf("  ],\n  \"negative_tests\":{\n");
    print_negative_case("malformed_observation", "reject",
                        negative.malformed_observation_rejected, 1);
    print_negative_case("out_of_domain_value", "fall_back",
                        negative.out_of_domain_fallback, 1);
    print_negative_case("empty_expert_assignment", "reject",
                        negative.empty_assignment_rejected, 1);
    print_negative_case("degenerate_expert_assignment", "reject",
                        negative.degenerate_assignment_rejected, 1);
    print_negative_case("duplicate_expert", "reject",
                        negative.duplicate_expert_rejected, 1);
    print_negative_case("tied_distance", "preserve_non_promotion",
                        negative.tied_distance_lower_id, 1);
    print_negative_case("routing_lower_bound_equality", "fall_back",
                        negative.lower_bound_equality_fallback, 1);
    print_negative_case("maximum_expert_capacity", "preserve_non_promotion",
                        negative.maximum_capacity_preserved, 1);
    print_negative_case("birth_beyond_capacity", "reject",
                        negative.birth_beyond_capacity_rejected, 1);
    print_negative_case("wrong_lifecycle_retirement", "reject",
                        negative.wrong_lifecycle_retirement_rejected, 1);
    print_negative_case("poisoned_adaptation_labels", "fail_a_gate",
                        negative.poisoned_labels_fail_gate, 1);
    print_negative_case("poisoned_transition_observations", "fail_a_gate",
                        negative.poisoned_transitions_fail_gate, 1);
    print_negative_case("replay_removal", "fail_a_gate",
                        negative.replay_removal_fail_gate, 1);
    print_negative_case("catastrophic_forgetting_condition", "fail_a_gate",
                        negative.catastrophic_forgetting_fail_gate, 0);
    printf("  },\n");
    printf("  \"trial_summary\":{\"declared\":%u,\"passing\":%u,\"failing\":%u,"
           "\"pass_rule\":\"all_8_trials_pass\"},\n",
           TRIALS, passing_trials, failing_trials);
    printf("  \"execution_integrity\":\"%s\",\n",
           execution_integrity ? "PASS" : "FAIL");
    printf("  \"development_result\":\"%s\",\n",
           all_trials_pass ? "PASS" : "FAIL");
    printf("  \"formal_mncs_status\":\"UNKNOWN\",\n"
           "  \"formal_mncds_status\":\"UNKNOWN\",\n"
           "  \"promotion_authorized\":false\n}\n");
    return execution_integrity ? 0 : 1;
}
