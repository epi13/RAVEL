/*
 * RAVEL 0.5 -- bounded adaptive-mechanism correction experiment.
 *
 * This is maintained C11 source. No source generator is claimed.
 * It emits observations and integrity facts, never development verdicts.
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
#define MAX_ADAPT_BIRTHS 16u
#define MAX_ADAPT_RETIREMENTS 4u
#define TRANSITION_TOP_K 2u
#define TRANSITION_SUPPORT_MIN 2u
#define TOPOLOGY_OBJECTIVE_MIN_Q20 105u
#define BIRTH_RESIDUAL_MIN_Q20 188744u
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
#define REGIMES 8u
#define LO (-64)
#define HI 63
#define Q20_SCALE 1048576.0
#define CHECKPOINT_SCHEMA 5u
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
    uint8_t source_domain;
} Event;

typedef struct {
    double key[D];
    double decode[D];
    double next[ACTIONS][D];
    uint32_t labels[CLASSES];
    uint32_t action_count[ACTIONS];
    uint16_t transition_target[ACTIONS][TRANSITION_TOP_K];
    uint32_t transition_support[ACTIONS][TRANSITION_TOP_K];
    uint32_t count;
    uint32_t errors;
    double reconstruction_sse;
    double prediction_sse;
    uint8_t label;
    uint8_t active;
    uint8_t lifecycle;
    uint8_t anchored;
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
    uint16_t next_graph[MAXE][ACTIONS][TRANSITION_TOP_K];
    uint32_t next_graph_support[MAXE][ACTIONS][TRANSITION_TOP_K];
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
    uint64_t reconstruction_sse_q20;
    uint64_t prediction_sse_q20;
    uint64_t prediction_samples;
    uint64_t transition_correct;
    uint64_t transition_supported;
    uint64_t transition_unknown;
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
    uint64_t rejected_births;
    uint64_t rejected_retirements;
} TrainMetric;

typedef struct {
    uint32_t selected;
    uint32_t unique;
    uint32_t labels_covered;
    uint32_t actions_covered;
    uint32_t states_covered;
    uint32_t experts_covered;
    uint32_t transition_pairs_covered;
    uint32_t rare_cases_selected;
    uint32_t high_loss_cases_selected;
    uint64_t selection_checksum;
} ReplayMetric;

typedef struct {
    uint32_t accepted_births;
    uint32_t rejected_births;
    uint32_t accepted_retirements;
    uint32_t rejected_retirements;
    uint32_t birth_event_index[MAX_ADAPT_BIRTHS];
    uint32_t birth_score_q20[MAX_ADAPT_BIRTHS];
    uint8_t birth_dominant_channel[MAX_ADAPT_BIRTHS];
    uint64_t retired_lineage[MAX_ADAPT_RETIREMENTS];
    uint32_t objective_before_q20;
    uint32_t objective_after_q20;
} TopologyTrace;

typedef struct {
    uint64_t cases;
    uint64_t path_found;
    uint64_t exact_state_targets;
    uint64_t goal_expert_targets;
    uint64_t belief_set_targets;
    uint64_t executed_path_length;
    uint64_t optimal_path_length;
    uint64_t path_length_regret;
    uint64_t graph_disconnection_failures;
    uint64_t no_supported_edge_failures;
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
    uint8_t use_replay;
    uint8_t use_retirement;
    uint8_t routed;
    uint8_t recursive_births;
    uint8_t random_births;
    uint8_t replay_policy;
    uint8_t protect_base;
    uint8_t matched_work;
} VariantConfig;

typedef struct {
    double classification;
    double reconstruction;
    double prediction;
    double novelty;
    double inverse_support;
    double uncertainty;
    double action_coverage;
    double retention_risk;
    double total;
    uint8_t dominant_channel;
} Residual;

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

static const TrialSpec regime_specs[REGIMES] = {
    {NULL, "separated_state", 0u, 42, 5, 5, 0, 0, 0, 0},
    {NULL, "partially_overlapping_observations", 0u, 22, 7, 7, 0, 0, 0, 0},
    {NULL, "increased_observation_noise", 0u, 42, 13, 19, 0, 0, 0, 0},
    {NULL, "label_drift", 0u, 42, 5, 5, 1, 0, 0, 0},
    {NULL, "observation_drift", 0u, 42, 5, 7, 0, 1, 0, 0},
    {NULL, "transition_drift", 0u, 42, 5, 5, 0, 0, 1, 0},
    {NULL, "combined_observation_and_label_drift", 0u, 34, 7, 11, 1, 1, 0, 0},
    {NULL, "partially_observed_ambiguous", 0u, 30, 9, 11, 1, 1, 1, 1}
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

static int q20_checked(double v, int64_t *out) {
    if (out == NULL || !isfinite(v)) return 0;
    if (v > (double)INT64_MAX / Q20_SCALE ||
        v < (double)INT64_MIN / Q20_SCALE) return 0;
    *out = (int64_t)llround(v * Q20_SCALE);
    return 1;
}

static int64_t q20(double v) {
    int64_t out = 0;
    if (!q20_checked(v, &out)) return v < 0.0 ? INT64_MIN : INT64_MAX;
    return out;
}

static double from_q20(int64_t v) {
    return (double)v / Q20_SCALE;
}

static int bytes_equal(const uint8_t *a, const uint8_t *b, size_t n) {
    if (a == NULL || b == NULL) return 0;
    uint8_t difference = 0u;
    for (size_t i = 0; i < n; ++i) difference |= (uint8_t)(a[i] ^ b[i]);
    return difference == 0u;
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
        ev->source_domain > 1u ||
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
        out[i].source_domain = drift ? 1u : 0u;
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
        e->next[ev->action][d] = (double)ev->nx[d];
    }
    for (uint32_t a = 0; a < ACTIONS; ++a) {
        for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
            e->transition_target[a][k] = INVALID_EXPERT;
        }
    }
    e->label = ev->label;
    e->active = 1u;
    e->lifecycle = lifecycle;
    e->anchored = lifecycle == 0u ? 1u : 0u;
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
        uint32_t transition_count[MAXE][ACTIONS][MAXE] = {{{0}}};
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
            uint64_t target_evaluations = 0u;
            uint16_t target = full_nearest(data[i].nx, m, &target_evaluations);
            tm->expert_evaluations += target_evaluations;
            if (target != INVALID_EXPERT) {
                ++transition_count[j][data[i].action][target];
            }
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
            for (uint32_t a = 0; a < ACTIONS; ++a) {
                for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                    uint16_t best = INVALID_EXPERT;
                    uint32_t best_support = 0u;
                    for (uint16_t target = 0; target < m->n; ++target) {
                        uint32_t support = transition_count[j][a][target];
                        int already = 0;
                        for (uint32_t prior = 0; prior < k; ++prior) {
                            if (m->e[j].transition_target[a][prior] == target) already = 1;
                        }
                        if (!already && (support > best_support ||
                            (support == best_support && support != 0u &&
                             (best == INVALID_EXPERT || target < best)))) {
                            best = target;
                            best_support = support;
                        }
                    }
                    m->e[j].transition_target[a][k] = best;
                    m->e[j].transition_support[a][k] = best_support;
                }
            }
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

static void refine_protected(Model *m, const Event *data, uint32_t count,
                             uint32_t iterations, int routed, TrainMetric *tm) {
    Expert anchors[MAXE];
    uint8_t anchored[MAXE] = {0};
    for (uint16_t j = 0; j < m->n; ++j) {
        if (m->e[j].anchored) {
            anchors[j] = m->e[j];
            anchored[j] = 1u;
        }
    }
    for (uint32_t iteration = 0; iteration < iterations; ++iteration) {
        refine(m, data, count, 1u, routed, NULL, tm);
        for (uint16_t j = 0; j < m->n; ++j) {
            if (anchored[j]) m->e[j] = anchors[j];
        }
        build_lattice(m);
    }
}

static double clamp01(double value) {
    if (!isfinite(value) || value <= 0.0) return 0.0;
    return value >= 1.0 ? 1.0 : value;
}

static double split_score(const Expert *e) {
    if (e->count < 2u) return -1.0;
    double classification = (double)e->errors / (double)e->count;
    double reconstruction = sqrt(e->reconstruction_sse /
                                 ((double)e->count * (double)D)) /
                            (double)(HI - LO);
    double prediction = sqrt(e->prediction_sse /
                             ((double)e->count * (double)D)) /
                        (double)(HI - LO);
    double support = (double)e->count / ((double)e->count + 32.0);
    return (clamp01(classification) + clamp01(reconstruction) +
            clamp01(prediction) + clamp01(support)) / 4.0;
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

static Residual event_residual(const Model *m, const Event *event) {
    Residual residual = {0};
    uint64_t evaluations = 0u;
    uint16_t expert = full_nearest(event->x, m, &evaluations);
    if (expert == INVALID_EXPERT) {
        residual.total = 1.0;
        return residual;
    }
    const Expert *e = &m->e[expert];
    residual.classification = e->label == event->label ? 0.0 : 1.0;
    double reconstruction = 0.0;
    double prediction = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double rv = (double)event->x[d] - e->decode[d];
        reconstruction += rv * rv;
        if (e->action_count[event->action] >= TRANSITION_SUPPORT_MIN) {
            double pv = (double)event->nx[d] - e->next[event->action][d];
            prediction += pv * pv;
        }
    }
    residual.reconstruction =
        clamp01(sqrt(reconstruction / (double)D) / (double)(HI - LO));
    residual.prediction = e->action_count[event->action] < TRANSITION_SUPPORT_MIN
        ? 1.0
        : clamp01(sqrt(prediction / (double)D) / (double)(HI - LO));
    residual.novelty =
        clamp01(sqrt(dist_x(event->x, e) / (double)D) / (double)(HI - LO));
    residual.inverse_support = 1.0 / (1.0 + (double)e->count / 8.0);
    uint32_t first = 0u, second = 0u;
    for (uint32_t label = 0; label < CLASSES; ++label) {
        uint32_t support = e->labels[label];
        if (support > first) { second = first; first = support; }
        else if (support > second) second = support;
    }
    residual.uncertainty = e->count == 0u
        ? 1.0
        : 1.0 - (double)(first - second) / (double)e->count;
    residual.action_coverage =
        1.0 / (1.0 + (double)e->action_count[event->action] / 4.0);
    residual.retention_risk =
        e->anchored && e->label != event->label ? 1.0 : 0.0;
    const double channels[8] = {
        residual.classification, residual.reconstruction, residual.prediction,
        residual.novelty, residual.inverse_support, residual.uncertainty,
        residual.action_coverage, residual.retention_risk
    };
    double best = -1.0;
    for (uint8_t channel = 0u; channel < 8u; ++channel) {
        double value = clamp01(channels[channel]);
        residual.total += value / 8.0;
        if (value > best) {
            best = value;
            residual.dominant_channel = channel;
        }
    }
    return residual;
}

static uint32_t model_objective_q20(const Model *m, const Event *adapt,
                                    uint32_t adapt_count, const Event *replay,
                                    uint32_t replay_count) {
    double quality = 0.0;
    uint32_t samples = 0u;
    for (uint32_t i = 0; i < adapt_count; ++i) {
        quality += 1.0 - event_residual(m, &adapt[i]).total;
        ++samples;
    }
    for (uint32_t i = 0; i < replay_count; ++i) {
        quality += 1.0 - event_residual(m, &replay[i]).total;
        ++samples;
    }
    if (samples == 0u) return 0u;
    int64_t encoded = q20(quality / (double)samples);
    if (encoded < 0) return 0u;
    if (encoded > (int64_t)UINT32_MAX) return UINT32_MAX;
    return (uint32_t)encoded;
}

static void seed_adaptation_expert(Model *m, uint16_t id,
                                   const Event *event, uint32_t event_index) {
    uint64_t evaluations = 0u;
    uint16_t parent = full_nearest(event->x, m, &evaluations);
    Expert seeded;
    if (parent != INVALID_EXPERT) seeded = m->e[parent];
    else memset(&seeded, 0, sizeof seeded);
    for (uint32_t d = 0; d < D; ++d) {
        seeded.key[d] = (double)event->x[d];
        seeded.decode[d] = (double)event->x[d];
        seeded.next[event->action][d] = (double)event->nx[d];
    }
    memset(seeded.labels, 0, sizeof seeded.labels);
    seeded.labels[event->label] = 1u;
    seeded.label = event->label;
    seeded.active = 1u;
    seeded.lifecycle = 1u;
    seeded.anchored = 0u;
    seeded.generation = parent == INVALID_EXPERT
        ? (uint16_t)(m->epoch + 1u)
        : (uint16_t)(m->e[parent].generation + 1u);
    seeded.lineage =
        mix64(UINT64_C(0x4144415054424952) ^ m->epoch ^ id ^ event_index ^
              (parent == INVALID_EXPERT ? 0u : m->e[parent].lineage));
    m->e[id] = seeded;
}

static int add_adaptation_experts(Model *m, const Event *adapt, uint32_t adapt_count,
                                  const Event *mix, uint32_t mix_count,
                                  const Event *replay, uint32_t replay_count,
                                  int random_births, TrainMetric *tm,
                                  TopologyTrace *trace) {
    if (m->n >= MAXE || adapt_count == 0u) return 0;
    uint8_t selected[ADAPT_TRAIN_N] = {0};
    uint32_t objective = model_objective_q20(m, adapt, adapt_count, replay, replay_count);
    trace->objective_before_q20 = objective;
    for (uint16_t attempt = 0; attempt < MAX_ADAPT_BIRTHS && m->n < MAXE; ++attempt) {
        uint32_t best = UINT32_MAX;
        Residual best_residual = {0};
        if (random_births) {
            uint32_t start = (uint32_t)(mix64(m->epoch ^ attempt) % adapt_count);
            for (uint32_t offset = 0; offset < adapt_count; ++offset) {
                uint32_t index = (start + offset) % adapt_count;
                if (!selected[index]) {
                    best = index;
                    best_residual = event_residual(m, &adapt[index]);
                    break;
                }
            }
        } else {
            for (uint32_t i = 0; i < adapt_count; ++i) {
                if (selected[i] || !event_valid(&adapt[i])) continue;
                Residual residual = event_residual(m, &adapt[i]);
                if (best == UINT32_MAX || residual.total > best_residual.total ||
                    (residual.total == best_residual.total && i < best)) {
                    best = i;
                    best_residual = residual;
                }
            }
        }
        if (best == UINT32_MAX ||
            (uint32_t)q20(best_residual.total) < BIRTH_RESIDUAL_MIN_Q20) break;
        selected[best] = 1u;
        Model candidate = *m;
        uint16_t id = candidate.n;
        seed_adaptation_expert(&candidate, id, &adapt[best], best);
        ++candidate.n;
        Model seeded_candidate = candidate;
        uint32_t seeded_objective =
            model_objective_q20(&seeded_candidate, adapt, adapt_count,
                                replay, replay_count);
        TrainMetric candidate_metric = {0};
        refine_protected(&candidate, mix, mix_count, 2u, 1, &candidate_metric);
        uint32_t candidate_objective =
            model_objective_q20(&candidate, adapt, adapt_count, replay, replay_count);
        if (seeded_objective > candidate_objective) {
            candidate = seeded_candidate;
            candidate_objective = seeded_objective;
            candidate_metric = (TrainMetric){0};
        }
        if (candidate_objective > objective + TOPOLOGY_OBJECTIVE_MIN_Q20) {
            *m = candidate;
            objective = candidate_objective;
            tm->expert_evaluations += candidate_metric.expert_evaluations;
            tm->samples += candidate_metric.samples;
            tm->certified += candidate_metric.certified;
            ++tm->births;
            uint32_t slot = trace->accepted_births++;
            trace->birth_event_index[slot] = best;
            trace->birth_score_q20[slot] = (uint32_t)q20(best_residual.total);
            trace->birth_dominant_channel[slot] = best_residual.dominant_channel;
        } else {
            ++tm->rejected_births;
            ++trace->rejected_births;
        }
    }
    trace->objective_after_q20 = objective;
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
    for (uint16_t expert = 0; expert < m->n; ++expert) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                uint16_t *target = &m->e[expert].transition_target[action][k];
                if (*target == victim) {
                    *target = INVALID_EXPERT;
                    m->e[expert].transition_support[action][k] = 0u;
                } else if (victim != last && *target == last) {
                    *target = victim;
                }
            }
        }
    }
    return 1;
}

static uint64_t replay_loss_key(const Model *m, const Event *event, uint32_t index) {
    uint64_t score = (uint64_t)(uint32_t)q20(event_residual(m, event).total);
    return (score << 32) | (uint64_t)(UINT32_MAX - index);
}

static uint32_t select_replay(const Model *base, const Event *base_train,
                              uint32_t count, uint8_t policy, Event *replay,
                              ReplayMetric *metric) {
    uint8_t selected[BASE_TRAIN_N] = {0};
    uint32_t state_action_frequency[STATES][ACTIONS] = {{0}};
    uint16_t assignment[BASE_TRAIN_N];
    uint64_t loss_key[BASE_TRAIN_N];
    uint64_t checksum = UINT64_C(1469598103934665603);
    for (uint32_t i = 0; i < count; ++i) {
        ++state_action_frequency[base_train[i].state][base_train[i].action];
        uint64_t evaluations = 0u;
        assignment[i] = full_nearest(base_train[i].x, base, &evaluations);
        loss_key[i] = replay_loss_key(base, &base_train[i], i);
    }
    uint32_t used = 0u;
    if (policy == 2u) {
        for (uint32_t i = 0; i < REPLAY_N && i < count; ++i) {
            uint32_t index = (i * 4u) % count;
            if (!selected[index]) {
                selected[index] = 1u;
                replay[used++] = base_train[index];
            }
        }
    } else if (policy == 1u) {
        for (uint32_t state = 0; state < STATES && used < REPLAY_N; ++state) {
            for (uint32_t action = 0; action < ACTIONS && used < REPLAY_N; ++action) {
                uint32_t best = UINT32_MAX;
                for (uint32_t i = 0; i < count; ++i) {
                    if (!selected[i] && base_train[i].state == state &&
                        base_train[i].action == action &&
                        (best == UINT32_MAX || loss_key[i] > loss_key[best])) best = i;
                }
                if (best != UINT32_MAX) {
                    selected[best] = 1u;
                    replay[used++] = base_train[best];
                }
            }
        }
        for (uint16_t expert = 0; expert < base->n && used < REPLAY_N; ++expert) {
            uint32_t best = UINT32_MAX;
            for (uint32_t i = 0; i < count; ++i) {
                if (!selected[i] && assignment[i] == expert &&
                    (best == UINT32_MAX || loss_key[i] > loss_key[best])) best = i;
            }
            if (best != UINT32_MAX) {
                selected[best] = 1u;
                replay[used++] = base_train[best];
            }
        }
        while (used < REPLAY_N && used < count) {
            uint32_t best = UINT32_MAX;
            for (uint32_t i = 0; i < count; ++i) {
                if (!selected[i] &&
                    (best == UINT32_MAX || loss_key[i] > loss_key[best])) best = i;
            }
            if (best == UINT32_MAX) break;
            selected[best] = 1u;
            replay[used++] = base_train[best];
        }
    }
    uint8_t labels[CLASSES] = {0}, actions[ACTIONS] = {0}, states[STATES] = {0};
    uint8_t experts[MAXE] = {0};
    uint8_t pairs[STATES][ACTIONS] = {{0}};
    for (uint32_t i = 0; i < count; ++i) if (selected[i]) {
        labels[base_train[i].label] = 1u;
        actions[base_train[i].action] = 1u;
        states[base_train[i].state] = 1u;
        pairs[base_train[i].state][base_train[i].action] = 1u;
        if (assignment[i] < MAXE) experts[assignment[i]] = 1u;
        if (state_action_frequency[base_train[i].state][base_train[i].action] <= 2u) {
            ++metric->rare_cases_selected;
        }
        checksum ^= i;
        checksum *= UINT64_C(1099511628211);
    }
    uint32_t order[BASE_TRAIN_N];
    for (uint32_t i = 0; i < count; ++i) order[i] = i;
    for (uint32_t i = 0; i < count; ++i) {
        uint32_t best = i;
        for (uint32_t j = i + 1u; j < count; ++j) {
            if (loss_key[order[j]] > loss_key[order[best]]) best = j;
        }
        uint32_t swap = order[i]; order[i] = order[best]; order[best] = swap;
    }
    for (uint32_t rank = 0; rank < 32u && rank < count; ++rank) {
        if (selected[order[rank]]) ++metric->high_loss_cases_selected;
    }
    for (uint32_t i = 0; i < CLASSES; ++i) metric->labels_covered += labels[i];
    for (uint32_t i = 0; i < ACTIONS; ++i) metric->actions_covered += actions[i];
    for (uint32_t i = 0; i < STATES; ++i) {
        metric->states_covered += states[i];
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            metric->transition_pairs_covered += pairs[i][a];
        }
    }
    for (uint32_t i = 0; i < MAXE; ++i) metric->experts_covered += experts[i];
    metric->selected = used;
    metric->unique = used;
    metric->selection_checksum = checksum;
    return used;
}

static int retirement_safe(const Model *m, uint16_t victim) {
    if (victim >= m->n || m->e[victim].lifecycle != 1u ||
        m->e[victim].anchored) return 0;
    for (uint32_t label = 0; label < CLASSES; ++label) {
        if (m->e[victim].labels[label] == 0u) continue;
        uint32_t providers = 0u;
        for (uint16_t j = 0; j < m->n; ++j) {
            if (j != victim && m->e[j].labels[label] != 0u) ++providers;
        }
        if (providers == 0u) return 0;
    }
    for (uint32_t action = 0; action < ACTIONS; ++action) {
        if (m->e[victim].action_count[action] == 0u) continue;
        uint32_t providers = 0u;
        for (uint16_t j = 0; j < m->n; ++j) {
            if (j != victim && m->e[j].action_count[action] >= TRANSITION_SUPPORT_MIN) {
                ++providers;
            }
        }
        if (providers == 0u) return 0;
    }
    for (uint16_t j = 0; j < m->n; ++j) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                if (m->next_graph[j][action][k] == victim &&
                    m->next_graph_support[j][action][k] >= TRANSITION_SUPPORT_MIN) return 0;
            }
        }
    }
    return 1;
}

static void consider_retirements(Model *m, const Event *adapt, uint32_t adapt_count,
                                 const Event *replay, uint32_t replay_count,
                                 TrainMetric *tm, TopologyTrace *trace) {
    for (uint32_t attempt = 0; attempt < MAX_ADAPT_RETIREMENTS; ++attempt) {
        uint16_t victim = INVALID_EXPERT;
        uint32_t lowest_support = UINT32_MAX;
        for (uint16_t j = 0; j < m->n; ++j) {
            if (m->e[j].lifecycle != 1u || m->e[j].anchored) continue;
            uint32_t support = m->e[j].count;
            if (victim == INVALID_EXPERT || support < lowest_support ||
                (support == lowest_support && m->e[j].lineage > m->e[victim].lineage)) {
                victim = j;
                lowest_support = support;
            }
        }
        if (victim == INVALID_EXPERT) break;
        if (!retirement_safe(m, victim)) {
            ++tm->rejected_retirements;
            ++trace->rejected_retirements;
            break;
        }
        uint32_t before = model_objective_q20(m, adapt, adapt_count, replay, replay_count);
        Model candidate = *m;
        uint64_t lineage = candidate.e[victim].lineage;
        if (!remove_expert(&candidate, victim, 1)) break;
        build_lattice(&candidate);
        uint32_t after =
            model_objective_q20(&candidate, adapt, adapt_count, replay, replay_count);
        if (after + TOPOLOGY_OBJECTIVE_MIN_Q20 >= before) {
            *m = candidate;
            ++tm->retired;
            uint32_t slot = trace->accepted_retirements++;
            trace->retired_lineage[slot] = lineage;
        } else {
            ++tm->rejected_retirements;
            ++trace->rejected_retirements;
            break;
        }
    }
}

static int adapt_model(Model *m, const Event *base_train, const Event *adapt_train,
                       const VariantConfig *config, TrainMetric *tm,
                       ReplayMetric *replay_metric, TopologyTrace *topology) {
    Event replay[REPLAY_N];
    Event mix[ADAPT_TRAIN_N + REPLAY_N];
    uint32_t replay_count = 0u;
    if (config->use_replay) {
        replay_count = select_replay(m, base_train, BASE_TRAIN_N,
                                     config->replay_policy, replay, replay_metric);
    }
    for (uint32_t i = 0; i < ADAPT_TRAIN_N; ++i) mix[i] = adapt_train[i];
    for (uint32_t i = 0; i < replay_count; ++i) mix[ADAPT_TRAIN_N + i] = replay[i];
    uint32_t mix_count = ADAPT_TRAIN_N + replay_count;
    if (config->recursive_births &&
        !add_adaptation_experts(m, adapt_train, ADAPT_TRAIN_N, mix, mix_count,
                                replay, replay_count, config->random_births,
                                tm, topology)) return 0;
    if (config->protect_base) {
        refine_protected(m, mix, mix_count, config->matched_work ? 4u : 2u,
                         config->routed, tm);
    } else {
        refine(m, mix, mix_count, config->matched_work ? 4u : 2u,
               config->routed, NULL, tm);
    }
    if (config->use_retirement) {
        consider_retirements(m, adapt_train, ADAPT_TRAIN_N,
                             replay, replay_count, tm, topology);
    }
    topology->objective_after_q20 =
        model_objective_q20(m, adapt_train, ADAPT_TRAIN_N, replay, replay_count);
    ++m->epoch;
    return 1;
}

static uint16_t nearest_vector(const double vector[D], const Model *m) {
    double best_distance = DBL_MAX;
    uint16_t best = INVALID_EXPERT;
    for (uint16_t expert = 0; expert < m->n; ++expert) {
        double distance = 0.0;
        for (uint32_t d = 0; d < D; ++d) {
            double delta = vector[d] - m->e[expert].key[d];
            distance += delta * delta;
        }
        if (better(distance, expert, best_distance, best)) {
            best_distance = distance;
            best = expert;
        }
    }
    return best;
}

static void compile_graph(Model *m) {
    for (uint16_t j = 0; j < m->n; ++j) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                uint16_t target = INVALID_EXPERT;
                uint32_t support = 0u;
                if (k == 0u) {
                    target = nearest_vector(m->e[j].next[action], m);
                    support = m->e[j].action_count[action];
                } else {
                    for (uint32_t observed = 0; observed < TRANSITION_TOP_K; ++observed) {
                        uint16_t candidate =
                            m->e[j].transition_target[action][observed];
                        if (candidate != m->next_graph[j][action][0]) {
                            target = candidate;
                            support =
                                m->e[j].transition_support[action][observed];
                            break;
                        }
                    }
                }
                uint32_t primary_support =
                    m->e[j].action_count[action];
                if (m->e[j].action_count[action] < TRANSITION_SUPPORT_MIN ||
                    support < TRANSITION_SUPPORT_MIN || target >= m->n) {
                    m->next_graph[j][action][k] = INVALID_EXPERT;
                    m->next_graph_support[j][action][k] = 0u;
                } else if (k == 0u || support * 2u >= primary_support) {
                    m->next_graph[j][action][k] = target;
                    m->next_graph_support[j][action][k] = support;
                } else {
                    m->next_graph[j][action][k] = INVALID_EXPERT;
                    m->next_graph_support[j][action][k] = 0u;
                }
            }
        }
    }
    for (uint16_t j = m->n; j < MAXE; ++j) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                m->next_graph[j][action][k] = INVALID_EXPERT;
                m->next_graph_support[j][action][k] = 0u;
            }
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
        int64_t reconstruction_quantized = 0;
        int64_t prediction_quantized = 0;
        int transition_supported =
            m->e[got].action_count[data[i].action] >= TRANSITION_SUPPORT_MIN &&
            m->next_graph[got][data[i].action][0] < m->n;
        for (uint32_t d = 0; d < D; ++d) {
            double rv = (double)data[i].x[d] - m->e[got].decode[d];
            out.reconstruction_sse += rv * rv;
            reconstruction_quantized += q20(rv * rv);
            if (transition_supported) {
                double pv =
                    (double)data[i].nx[d] - m->e[got].next[data[i].action][d];
                out.prediction_sse += pv * pv;
                prediction_quantized += q20(pv * pv);
            }
        }
        if (reconstruction_quantized < 0 ||
            UINT64_MAX - out.reconstruction_sse_q20 <
                (uint64_t)reconstruction_quantized) {
            ++out.rejected;
            continue;
        }
        out.reconstruction_sse_q20 += (uint64_t)reconstruction_quantized;
        uint16_t predicted_next = INVALID_EXPERT;
        uint16_t observed_next = INVALID_EXPERT;
        if (transition_supported) {
            predicted_next = m->next_graph[got][data[i].action][0];
            uint64_t next_evaluations = 0u;
            observed_next = full_nearest(data[i].nx, m, &next_evaluations);
            if (prediction_quantized < 0 ||
                UINT64_MAX - out.prediction_sse_q20 <
                    (uint64_t)prediction_quantized) {
                ++out.rejected;
                continue;
            }
            out.prediction_sse_q20 += (uint64_t)prediction_quantized;
            ++out.prediction_samples;
            ++out.transition_supported;
            if (predicted_next == observed_next) ++out.transition_correct;
        } else {
            ++out.transition_unknown;
        }
        ++out.samples;
        out.classification_checksum ^= mix64(((uint64_t)got << 48) ^
                                             ((uint64_t)m->e[got].label << 32) ^ i);
        out.reconstruction_checksum ^= mix64((uint64_t)reconstruction_quantized ^ i);
        out.prediction_checksum ^=
            mix64((uint64_t)prediction_quantized ^ ((uint64_t)i << 16) ^
                  (transition_supported ? UINT64_C(0x53555050) : UINT64_C(0x554e4b4e)));
        out.transition_checksum ^= mix64(((uint64_t)predicted_next << 32) ^ observed_next ^ i);
    }
    return out;
}

static int plan_actions(const Model *m, uint16_t start, uint16_t goal,
                        uint8_t actions[PLAN_LIMIT], uint32_t *used,
                        uint64_t *expansions, uint64_t *unknown_actions) {
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
            int supported = 0;
            for (uint32_t k = 0; k < 1u; ++k) {
                uint16_t next = m->next_graph[current][action][k];
                if (next >= m->n) continue;
                supported = 1;
                if (!seen[next]) {
                    seen[next] = 1u;
                    parent[next] = current;
                    parent_action[next] = action;
                    queue[tail++] = next;
                }
            }
            if (!supported) ++*unknown_actions;
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
        uint64_t unknown_actions = 0u;
        if (!plan_actions(m, start_expert, goal_expert, actions, &used,
                          &out.expansions, &unknown_actions)) {
            if (unknown_actions != 0u) ++out.no_supported_edge_failures;
            else ++out.graph_disconnection_failures;
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
        int alias_equivalent = 1;
        for (uint32_t d = 0; d < D; ++d) {
            if (world->center[current][d] != world->center[goal_state][d]) {
                alias_equivalent = 0;
            }
        }
        int belief_goal = exact || alias_equivalent || expert_goal;
        if (exact) {
            ++out.exact_state_targets;
            if (optimal != UINT32_MAX && used >= optimal) out.path_length_regret += used - optimal;
        }
        if (expert_goal) ++out.goal_expert_targets;
        if (belief_goal) ++out.belief_set_targets;
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

static void bb_q20(ByteBuffer *b, double value) {
    int64_t encoded = 0;
    if (!q20_checked(value, &encoded)) {
        b->ok = 0;
        return;
    }
    bb_i64(b, encoded);
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
    static const uint8_t magic[8] = {'R', 'A', 'V', 'E', 'L', '0', '5', 0};
    if (m == NULL || m->n == 0u || m->n > MAXE) return 0;
    ByteBuffer payload = {{0}, 0u, 1};
    bb_u16(&payload, m->n);
    bb_u64(&payload, m->epoch);
    bb_u16(&payload, TRANSITION_TOP_K);
    bb_u16(&payload, TRANSITION_SUPPORT_MIN);
    for (uint16_t j = 0; j < m->n; ++j) {
        const Expert *e = &m->e[j];
        bb_u16(&payload, j);
        bb_u8(&payload, e->active);
        bb_u8(&payload, e->lifecycle);
        bb_u8(&payload, e->anchored);
        bb_u16(&payload, e->generation);
        bb_u8(&payload, e->label);
        bb_u64(&payload, e->lineage);
        for (uint32_t d = 0; d < D; ++d) bb_q20(&payload, e->key[d]);
        for (uint32_t d = 0; d < D; ++d) bb_q20(&payload, e->decode[d]);
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t d = 0; d < D; ++d) bb_q20(&payload, e->next[a][d]);
        }
        for (uint32_t y = 0; y < CLASSES; ++y) bb_u32(&payload, e->labels[y]);
        for (uint32_t a = 0; a < ACTIONS; ++a) bb_u32(&payload, e->action_count[a]);
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                bb_u16(&payload, e->transition_target[a][k]);
                bb_u32(&payload, e->transition_support[a][k]);
            }
        }
        bb_u32(&payload, e->count);
        bb_u32(&payload, e->errors);
        bb_q20(&payload, e->reconstruction_sse);
        bb_q20(&payload, e->prediction_sse);
    }
    for (uint16_t j = 0; j < m->n; ++j) {
        bb_u16(&payload, j);
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                bb_u16(&payload, m->next_graph[j][a][k]);
                bb_u32(&payload, m->next_graph_support[j][a][k]);
            }
        }
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
    static const uint8_t magic[8] = {'R', 'A', 'V', 'E', 'L', '0', '5', 0};
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
        !bytes_equal(got_magic, magic, sizeof magic) ||
        schema != CHECKPOINT_SCHEMA || dimensions != D || classes != CLASSES ||
        actions != ACTIONS || states != STATES || maximum != MAXE ||
        route_width != ROUTE_K || cells != CELLS ||
        byte_order != UINT32_C(0x01020304) ||
        payload_length > CHECKPOINT_MAX - CHECKPOINT_HEADER ||
        size != CHECKPOINT_HEADER + (size_t)payload_length) return 0;
    sha256_bytes(bytes + CHECKPOINT_HEADER, payload_length, actual_digest);
    if (!bytes_equal(expected_digest, actual_digest, sizeof expected_digest)) return 0;
    ByteReader payload = {
        bytes + CHECKPOINT_HEADER, payload_length, 0u, 1
    };
    Model model;
    memset(&model, 0, sizeof model);
    model.n = br_u16(&payload);
    model.epoch = br_u64(&payload);
    uint16_t transition_top_k = br_u16(&payload);
    uint16_t transition_support_min = br_u16(&payload);
    if (!payload.ok || model.n == 0u || model.n > MAXE ||
        transition_top_k != TRANSITION_TOP_K ||
        transition_support_min != TRANSITION_SUPPORT_MIN) return 0;
    for (uint16_t j = 0; j < model.n; ++j) {
        Expert *e = &model.e[j];
        if (br_u16(&payload) != j) return 0;
        e->active = br_u8(&payload);
        e->lifecycle = br_u8(&payload);
        e->anchored = br_u8(&payload);
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
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                e->transition_target[a][k] = br_u16(&payload);
                e->transition_support[a][k] = br_u32(&payload);
                if ((e->transition_target[a][k] != INVALID_EXPERT &&
                     e->transition_target[a][k] >= model.n) ||
                    (e->transition_support[a][k] == 0u &&
                     e->transition_target[a][k] != INVALID_EXPERT)) return 0;
            }
        }
        e->count = br_u32(&payload);
        e->errors = br_u32(&payload);
        e->reconstruction_sse = from_q20(br_i64(&payload));
        e->prediction_sse = from_q20(br_i64(&payload));
        if (!payload.ok || e->active != 1u || e->lifecycle > 1u ||
            e->anchored > 1u || e->anchored != (uint8_t)(e->lifecycle == 0u) ||
            e->label >= CLASSES || e->lineage == 0u || e->errors > e->count) return 0;
    }
    for (uint16_t j = 0; j < model.n; ++j) {
        if (br_u16(&payload) != j) return 0;
        for (uint32_t a = 0; a < ACTIONS; ++a) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                model.next_graph[j][a][k] = br_u16(&payload);
                model.next_graph_support[j][a][k] = br_u32(&payload);
                uint16_t target = model.next_graph[j][a][k];
                uint32_t support = model.next_graph_support[j][a][k];
                if ((target == INVALID_EXPERT && support != 0u) ||
                    (target != INVALID_EXPERT &&
                     (target >= model.n || support < TRANSITION_SUPPORT_MIN))) return 0;
            }
        }
    }
    uint16_t take = model.n < ROUTE_K ? model.n : ROUTE_K;
    for (uint16_t cell = 0; cell < CELLS; ++cell) {
        if (br_u16(&payload) != cell) return 0;
        for (uint16_t i = 0; i < ROUTE_K; ++i) {
            uint16_t id = br_u16(&payload);
            model.routing[cell].id[i] = id;
            if ((i < take && id >= model.n) || (i >= take && id != INVALID_EXPERT)) return 0;
            if (i < take) {
                for (uint16_t k = 0; k < i; ++k) {
                    if (model.routing[cell].id[k] == id) return 0;
                }
            }
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

static int checkpoint_memory_roundtrip(Model *model, Model *restored,
                                       size_t *checkpoint_size) {
    ByteBuffer checkpoint;
    if (!serialize_checkpoint(model, &checkpoint)) return 0;
    for (size_t i = 0; i < sizeof model->identity; ++i) {
        model->identity[i] = checkpoint.data[32u + i];
    }
    if (!deserialize_checkpoint(checkpoint.data, checkpoint.len, restored)) return 0;
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
           a->reconstruction_sse_q20 == b->reconstruction_sse_q20 &&
           a->prediction_sse_q20 == b->prediction_sse_q20 &&
           a->prediction_samples == b->prediction_samples &&
           a->transition_correct == b->transition_correct &&
           a->transition_supported == b->transition_supported &&
           a->transition_unknown == b->transition_unknown &&
           a->classification_checksum == b->classification_checksum &&
           a->reconstruction_checksum == b->reconstruction_checksum &&
           a->prediction_checksum == b->prediction_checksum &&
           a->transition_checksum == b->transition_checksum;
}

static int plan_equal(const PlanMetric *a, const PlanMetric *b) {
    return a->cases == b->cases &&
           a->path_found == b->path_found &&
           a->exact_state_targets == b->exact_state_targets &&
           a->goal_expert_targets == b->goal_expert_targets &&
           a->belief_set_targets == b->belief_set_targets &&
           a->executed_path_length == b->executed_path_length &&
           a->optimal_path_length == b->optimal_path_length &&
           a->path_length_regret == b->path_length_regret &&
           a->graph_disconnection_failures == b->graph_disconnection_failures &&
           a->no_supported_edge_failures == b->no_supported_edge_failures &&
           a->transition_model_failures == b->transition_model_failures &&
           a->state_aliasing_failures == b->state_aliasing_failures &&
           a->expansions == b->expansions &&
           a->checksum == b->checksum;
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
    bb_u64(&b, evaluation->reconstruction_sse_q20);
    bb_u64(&b, evaluation->prediction_sse_q20);
    bb_u64(&b, evaluation->prediction_samples);
    bb_u64(&b, evaluation->transition_correct);
    bb_u64(&b, evaluation->transition_supported);
    bb_u64(&b, evaluation->transition_unknown);
    bb_u64(&b, evaluation->classification_checksum);
    bb_u64(&b, evaluation->reconstruction_checksum);
    bb_u64(&b, evaluation->prediction_checksum);
    bb_u64(&b, evaluation->transition_checksum);
    bb_u64(&b, planning->cases);
    bb_u64(&b, planning->path_found);
    bb_u64(&b, planning->exact_state_targets);
    bb_u64(&b, planning->goal_expert_targets);
    bb_u64(&b, planning->belief_set_targets);
    bb_u64(&b, planning->executed_path_length);
    bb_u64(&b, planning->optimal_path_length);
    bb_u64(&b, planning->path_length_regret);
    bb_u64(&b, planning->graph_disconnection_failures);
    bb_u64(&b, planning->no_supported_edge_failures);
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
    return bytes_equal(expected->identity, restored->identity, 32u) &&
           eval_equal(expected_eval, restored_eval) &&
           plan_equal(expected_plan, restored_plan) &&
           bytes_equal(expected_behavior, restored_behavior, 32u);
}

static int valid_model_mutation_detected(const Model *original, const Model *mutated) {
    ByteBuffer checkpoint;
    Model restored;
    if (!serialize_checkpoint(mutated, &checkpoint)) return 1;
    if (!deserialize_checkpoint(checkpoint.data, checkpoint.len, &restored)) return 1;
    return !bytes_equal(original->identity, restored.identity,
                        sizeof original->identity);
}

typedef struct {
    int retrieval_key;
    int reconstruction;
    int next_observation;
    int label;
    int label_count;
    int lineage;
    int transition_graph;
    int transition_support;
    int anchored_status;
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
    mutated.next_graph[0][0][0] =
        (uint16_t)((mutated.next_graph[0][0][0] + 1u) % mutated.n);
    result.transition_graph = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    ++mutated.e[0].transition_support[0][0];
    result.transition_support = valid_model_mutation_detected(original, &mutated);
    mutated = *original;
    mutated.e[0].anchored ^= 1u;
    result.anchored_status = valid_model_mutation_detected(original, &mutated);

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
                !bytes_equal(original->identity, restored.identity,
                             sizeof original->identity);
        }
    }
    return result;
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
            bytes_equal(first_checkpoint.data, second_checkpoint.data,
                        first_checkpoint.len);
    }
    return result;
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

static double prediction_rmse(const Eval *e) {
    return e->prediction_samples == 0u ? DBL_MAX :
        sqrt(((double)e->prediction_sse_q20 / Q20_SCALE) /
             (double)(e->prediction_samples * D));
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
    TopologyTrace capacity_topology = {0};
    result.birth_beyond_capacity_rejected =
        !add_adaptation_experts(&capacity, adapt_train, ADAPT_TRAIN_N,
                                adapt_train, ADAPT_TRAIN_N, NULL, 0u, 0,
                                &capacity_tm, &capacity_topology) &&
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
    VariantConfig no_replay = {
        .use_replay = 0u, .use_retirement = 0u, .routed = 1u,
        .recursive_births = 1u, .random_births = 0u,
        .replay_policy = 0u, .protect_base = 0u, .matched_work = 1u
    };
    Model label_model = *base;
    TrainMetric label_tm = {0};
    ReplayMetric label_replay = {0};
    TopologyTrace label_topology = {0};
    int label_adapted = adapt_model(&label_model, base_train, poisoned_labels,
                                    &no_replay, &label_tm, &label_replay,
                                    &label_topology);
    canonicalize_model(&label_model);
    Eval label_retention = evaluate(&label_model, retention, RETENTION_N, 1);
    result.poisoned_labels_fail_gate =
        label_adapted && eval_accuracy(&label_retention) < 0.70;
    Model replay_model = *base;
    TrainMetric replay_tm = {0};
    ReplayMetric replay_coverage = {0};
    TopologyTrace replay_topology = {0};
    VariantConfig balanced = no_replay;
    balanced.use_replay = 1u;
    balanced.replay_policy = 1u;
    balanced.protect_base = 1u;
    int replay_adapted = adapt_model(&replay_model, base_train, poisoned_labels,
                                     &balanced, &replay_tm, &replay_coverage,
                                     &replay_topology);
    canonicalize_model(&replay_model);
    Eval replay_retention = evaluate(&replay_model, retention, RETENTION_N, 1);
    result.replay_removal_fail_gate =
        replay_adapted && eval_accuracy(&replay_retention) >
            eval_accuracy(&label_retention);

    Event catastrophic[ADAPT_TRAIN_N];
    for (uint32_t i = 0; i < ADAPT_TRAIN_N; ++i) {
        catastrophic[i] = poisoned_labels[ADAPT_TRAIN_N - i - 1u];
        catastrophic[i].label =
            (uint8_t)((catastrophic[i].label + 2u) % CLASSES);
    }
    Model catastrophic_model = *base;
    TrainMetric catastrophic_tm = {0};
    refine(&catastrophic_model, catastrophic, ADAPT_TRAIN_N, 12u, 1, NULL,
           &catastrophic_tm);
    ++catastrophic_model.epoch;
    canonicalize_model(&catastrophic_model);
    Eval catastrophic_retention =
        evaluate(&catastrophic_model, retention, RETENTION_N, 1);
    Model base_for_retention = *base;
    Eval base_retention =
        evaluate(&base_for_retention, retention, RETENTION_N, 1);
    result.catastrophic_forgetting_fail_gate =
        catastrophic_tm.expert_evaluations > 0u &&
        eval_accuracy(&catastrophic_retention) <
            eval_accuracy(&base_retention);

    Model transition_model = *base;
    TrainMetric transition_tm = {0};
    ReplayMetric transition_replay = {0};
    TopologyTrace transition_topology = {0};
    int transition_adapted =
        adapt_model(&transition_model, base_train, poisoned_transitions,
                    &no_replay, &transition_tm, &transition_replay,
                    &transition_topology);
    canonicalize_model(&transition_model);
    Eval transition_eval = evaluate(&transition_model, drift_hold, DRIFT_HOLD_N, 1);
    result.poisoned_transitions_fail_gate =
        transition_adapted && prediction_rmse(&transition_eval) > 24.0;
    return result;
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
    for (size_t i = 0; i < sizeof m->identity; ++i) {
        m->identity[i] = checkpoint.data[32u + i];
    }
    return checkpoint.len;
}

static void print_eval_json(const Eval *e) {
    printf("{\"samples\":%" PRIu64 ",\"rejected\":%" PRIu64
           ",\"correct\":%" PRIu64
           ",\"reconstruction_sse_q20\":%" PRIu64
           ",\"prediction_sse_q20\":%" PRIu64
           ",\"prediction_samples\":%" PRIu64
           ",\"transition_correct\":%" PRIu64
           ",\"transition_supported\":%" PRIu64
           ",\"transition_unknown\":%" PRIu64
           ",\"routing_certification_count\":%" PRIu64
           ",\"routed_complete_mismatches\":%" PRIu64
           ",\"expert_evaluations\":%" PRIu64
           ",\"classification_checksum\":\"%016" PRIx64 "\""
           ",\"reconstruction_checksum\":\"%016" PRIx64 "\""
           ",\"prediction_checksum\":\"%016" PRIx64 "\""
           ",\"transition_checksum\":\"%016" PRIx64 "\"}",
           e->samples, e->rejected, e->correct,
           e->reconstruction_sse_q20, e->prediction_sse_q20,
           e->prediction_samples, e->transition_correct,
           e->transition_supported, e->transition_unknown,
           e->certified, e->exact_mismatches,
           e->expert_evaluations, e->classification_checksum,
           e->reconstruction_checksum, e->prediction_checksum, e->transition_checksum);
}

static void print_plan_json(const PlanMetric *p) {
    printf("{\"cases\":%" PRIu64 ",\"path_found\":%" PRIu64
           ",\"exact_world_state_target_reached\":%" PRIu64
           ",\"goal_expert_reached\":%" PRIu64
           ",\"belief_set_target_reached\":%" PRIu64
           ",\"executed_path_length\":%" PRIu64
           ",\"optimal_path_length\":%" PRIu64
           ",\"path_length_regret\":%" PRIu64
           ",\"graph_disconnection_failures\":%" PRIu64
           ",\"no_supported_edge_failures\":%" PRIu64
           ",\"transition_model_error_failures\":%" PRIu64
           ",\"state_aliasing_failures\":%" PRIu64
           ",\"expansions\":%" PRIu64 ",\"checksum\":\"%016" PRIx64 "\"}",
           p->cases, p->path_found, p->exact_state_targets,
           p->goal_expert_targets, p->belief_set_targets,
           p->executed_path_length, p->optimal_path_length, p->path_length_regret,
           p->graph_disconnection_failures, p->no_supported_edge_failures,
           p->transition_model_failures,
           p->state_aliasing_failures, p->expansions, p->checksum);
}

static void print_variant_json(const char *name, Model *m, const Eval *drift,
                               const Eval *retention, const PlanMetric *planning,
                               uint64_t training_evaluations, int comma) {
    size_t checkpoint_size = model_checkpoint_size(m);
    printf("        \"%s\":{\"expert_count\":%u,\"training_evaluations\":%" PRIu64
           ",\"checkpoint_size_bytes\":%zu,\"drift_holdout\":",
           name, m->n, training_evaluations, checkpoint_size);
    print_eval_json(drift);
    printf(",\"retention_holdout\":");
    print_eval_json(retention);
    printf(",\"planning\":");
    print_plan_json(planning);
    printf("}%s\n", comma ? "," : "");
}

static void print_mutations_json(const MutationResult *m) {
    printf("{\"retrieval_key_component\":%s,\"reconstruction_component\":%s,"
           "\"next_observation_component\":%s,\"label\":%s,\"label_count\":%s,"
           "\"lineage\":%s,\"transition_graph_edge\":%s,\"transition_support\":%s,"
           "\"anchored_status\":%s,\"payload_byte\":%s,"
           "\"checkpoint_truncation\":%s,\"appended_unexpected_byte\":%s,"
           "\"incorrect_schema_version\":%s,\"checkpoint_substitution\":%s}",
           m->retrieval_key ? "true" : "false",
           m->reconstruction ? "true" : "false",
           m->next_observation ? "true" : "false",
           m->label ? "true" : "false",
           m->label_count ? "true" : "false",
           m->lineage ? "true" : "false",
           m->transition_graph ? "true" : "false",
           m->transition_support ? "true" : "false",
           m->anchored_status ? "true" : "false",
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
    (void)expected;
    printf("    \"%s\":{\"observed\":%s}%s\n",
           id, observed ? "true" : "false",
           comma ? "," : "");
}


typedef struct {
    Model model;
    TrainMetric adaptation_metric;
    ReplayMetric replay_metric;
    TopologyTrace topology;
    Eval drift;
    Eval retention;
    PlanMetric planning;
    int adaptation_ok;
} VariantObservation;

static int event_equal(const Event *a, const Event *b) {
    if (a->action != b->action || a->label != b->label ||
        a->state != b->state || a->next_state != b->next_state ||
        a->source_domain != b->source_domain) return 0;
    for (uint32_t d = 0; d < D; ++d) {
        if (a->x[d] != b->x[d] || a->nx[d] != b->nx[d]) return 0;
    }
    return 1;
}

static void print_replay_json(const ReplayMetric *metric) {
    printf("{\"selected\":%u,\"unique\":%u,\"labels_covered\":%u,"
           "\"actions_covered\":%u,\"states_covered\":%u,"
           "\"assigned_experts_covered\":%u,\"transition_pairs_covered\":%u,"
           "\"rare_cases_selected\":%u,\"high_loss_cases_selected\":%u,"
           "\"selection_checksum\":\"%016" PRIx64 "\"}",
           metric->selected, metric->unique, metric->labels_covered,
           metric->actions_covered, metric->states_covered,
           metric->experts_covered, metric->transition_pairs_covered,
           metric->rare_cases_selected, metric->high_loss_cases_selected,
           metric->selection_checksum);
}

static void print_topology_json(const TopologyTrace *trace,
                                const TrainMetric *metric) {
    printf("{\"accepted_births\":%u,\"rejected_births\":%u,"
           "\"accepted_retirements\":%u,\"rejected_retirements\":%u,"
           "\"objective_before_q20\":%u,\"objective_after_q20\":%u,"
           "\"births\":[",
           trace->accepted_births, trace->rejected_births,
           trace->accepted_retirements, trace->rejected_retirements,
           trace->objective_before_q20, trace->objective_after_q20);
    for (uint32_t i = 0; i < trace->accepted_births; ++i) {
        printf("{\"event_index\":%u,\"normalized_score_q20\":%u,"
               "\"dominant_channel\":%u}%s",
               trace->birth_event_index[i], trace->birth_score_q20[i],
               trace->birth_dominant_channel[i],
               i + 1u < trace->accepted_births ? "," : "");
    }
    printf("],\"retired_lineages\":[");
    for (uint32_t i = 0; i < trace->accepted_retirements; ++i) {
        printf("\"%016" PRIx64 "\"%s", trace->retired_lineage[i],
               i + 1u < trace->accepted_retirements ? "," : "");
    }
    printf("],\"training_observations\":{\"expert_evaluations\":%" PRIu64
           ",\"samples\":%" PRIu64 ",\"certified\":%" PRIu64
           ",\"births\":%" PRIu64 ",\"retired\":%" PRIu64
           ",\"rejected_births\":%" PRIu64
           ",\"rejected_retirements\":%" PRIu64 "}}",
           metric->expert_evaluations, metric->samples, metric->certified,
           metric->births, metric->retired, metric->rejected_births,
           metric->rejected_retirements);
}

static void observe_adapted_variant(
    VariantObservation *out, const Model *base, const Event *base_train,
    const Event *adapt_train, const Event *drift_hold, const Event *retention,
    const World *world, const TrialSpec *spec, uint64_t planning_seed,
    const VariantConfig *config) {
    memset(out, 0, sizeof *out);
    out->model = *base;
    out->adaptation_ok =
        adapt_model(&out->model, base_train, adapt_train, config,
                    &out->adaptation_metric, &out->replay_metric, &out->topology);
    canonicalize_model(&out->model);
    out->drift = evaluate(&out->model, drift_hold, DRIFT_HOLD_N, config->routed);
    out->retention =
        evaluate(&out->model, retention, RETENTION_N, config->routed);
    out->planning =
        evaluate_planning(&out->model, world, spec, planning_seed, 1);
}

static void print_variant_observation(const char *name,
                                      VariantObservation *observation,
                                      uint64_t base_training_evaluations,
                                      int comma) {
    print_variant_json(name, &observation->model, &observation->drift,
                       &observation->retention, &observation->planning,
                       base_training_evaluations +
                           observation->adaptation_metric.expert_evaluations,
                       comma);
}

static uint32_t count_unsupported_graph_violations(const Model *model) {
    uint32_t violations = 0u;
    for (uint16_t expert = 0; expert < model->n; ++expert) {
        for (uint32_t action = 0; action < ACTIONS; ++action) {
            for (uint32_t k = 0; k < TRANSITION_TOP_K; ++k) {
                int insufficient =
                    model->e[expert].action_count[action] <
                        TRANSITION_SUPPORT_MIN ||
                    model->next_graph_support[expert][action][k] <
                        TRANSITION_SUPPORT_MIN;
                if (insufficient &&
                    model->next_graph[expert][action][k] != INVALID_EXPERT) {
                    ++violations;
                }
            }
        }
    }
    return violations;
}

static const TrialSpec *find_regime(const char *name) {
    for (uint32_t i = 0; i < REGIMES; ++i) {
        if (strcmp(name, regime_specs[i].regime) == 0) return &regime_specs[i];
    }
    return NULL;
}

static int safe_identifier(const char *value) {
    if (value == NULL || *value == '\0') return 0;
    for (const unsigned char *p = (const unsigned char *)value; *p != 0u; ++p) {
        int valid = (*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
                    (*p >= '0' && *p <= '9') || *p == '-' || *p == '_';
        if (!valid) return 0;
    }
    return 1;
}

static void print_trial_header(const TrialSpec *spec,
                               uint64_t base_train_seed,
                               uint64_t base_hold_seed,
                               uint64_t adapt_train_seed,
                               uint64_t drift_hold_seed,
                               uint64_t retention_seed,
                               uint64_t planning_seed) {
    printf("{\n  \"schema\":\"ravel-raw-trial/0.5\",\n"
           "  \"trial_id\":\"%s\",\"regime\":\"%s\","
           "\"seed\":\"0x%016" PRIx64 "\",\n"
           "  \"dataset_seeds\":{\"base_training\":\"0x%016" PRIx64
           "\",\"base_holdout\":\"0x%016" PRIx64
           "\",\"drift_adaptation_training\":\"0x%016" PRIx64
           "\",\"drift_holdout\":\"0x%016" PRIx64
           "\",\"original_task_retention_holdout\":\"0x%016" PRIx64
           "\",\"planning_cases\":\"0x%016" PRIx64 "\"},\n",
           spec->trial_id, spec->regime, spec->seed,
           base_train_seed, base_hold_seed, adapt_train_seed,
           drift_hold_seed, retention_seed, planning_seed);
    printf("  \"dataset_sizes\":{\"base_training\":%u,\"base_holdout\":%u,"
           "\"drift_adaptation_training\":%u,\"drift_holdout\":%u,"
           "\"original_task_retention_holdout\":%u,\"planning_cases\":%u},\n",
           BASE_TRAIN_N, BASE_HOLD_N, ADAPT_TRAIN_N, DRIFT_HOLD_N,
           RETENTION_N, PLAN_N);
}

static int run_trial(const char *trial_id, const char *regime,
                     uint64_t seed, const char *variant_filter) {
    const TrialSpec *profile = find_regime(regime);
    if (profile == NULL || !safe_identifier(trial_id)) return 2;
    TrialSpec spec = *profile;
    spec.trial_id = trial_id;
    spec.seed = seed;
    World world;
    Event base_train[BASE_TRAIN_N], base_hold[BASE_HOLD_N];
    Event adapt_train[ADAPT_TRAIN_N], drift_hold[DRIFT_HOLD_N];
    Event retention[RETENTION_N];
    make_world(&world, &spec);
    uint64_t base_train_seed = mix64(seed ^ UINT64_C(0x4241534554524149));
    uint64_t base_hold_seed = mix64(seed ^ UINT64_C(0x42415345484f4c44));
    uint64_t adapt_train_seed = mix64(seed ^ UINT64_C(0x414441505454524e));
    uint64_t drift_hold_seed = mix64(seed ^ UINT64_C(0x4452494654484f4c));
    uint64_t retention_seed = mix64(seed ^ UINT64_C(0x524554454e54494f));
    uint64_t planning_seed = mix64(seed ^ UINT64_C(0x504c414e43415345));
    make_dataset(&world, &spec, base_train, BASE_TRAIN_N, base_train_seed, 0);
    make_dataset(&world, &spec, base_hold, BASE_HOLD_N, base_hold_seed, 0);
    make_dataset(&world, &spec, adapt_train, ADAPT_TRAIN_N, adapt_train_seed, 1);
    make_dataset(&world, &spec, drift_hold, DRIFT_HOLD_N, drift_hold_seed, 1);
    make_dataset(&world, &spec, retention, RETENTION_N, retention_seed, 0);

    Model base;
    TrainMetric base_metric = {0};
    train_recursive(&base, base_train, BASE_TRAIN_N, &base_metric);
    canonicalize_model(&base);
    (void)model_checkpoint_size(&base);
    Eval base_hold_eval = evaluate(&base, base_hold, BASE_HOLD_N, 1);
    Eval static_drift_eval = evaluate(&base, drift_hold, DRIFT_HOLD_N, 1);
    Eval static_retention_eval = evaluate(&base, retention, RETENTION_N, 1);
    PlanMetric static_plan =
        evaluate_planning(&base, &world, &spec, planning_seed, 1);

    VariantConfig candidate_config = {
        .use_replay = 1u, .use_retirement = 1u, .routed = 1u,
        .recursive_births = 1u, .random_births = 0u,
        .replay_policy = 1u, .protect_base = 1u, .matched_work = 1u
    };
    VariantObservation candidate;
    observe_adapted_variant(&candidate, &base, base_train, adapt_train,
                            drift_hold, retention, &world, &spec,
                            planning_seed, &candidate_config);
    Eval adaptation_training_eval =
        evaluate(&candidate.model, adapt_train, ADAPT_TRAIN_N, 1);

    Model restored;
    size_t checkpoint_size = 0u;
    int checkpoint_ok = candidate.adaptation_ok &&
        checkpoint_memory_roundtrip(&candidate.model, &restored, &checkpoint_size);
    Eval restored_adaptation = checkpoint_ok
        ? evaluate(&restored, adapt_train, ADAPT_TRAIN_N, 1) : (Eval){0};
    Eval restored_drift = checkpoint_ok
        ? evaluate(&restored, drift_hold, DRIFT_HOLD_N, 1) : (Eval){0};
    Eval restored_retention = checkpoint_ok
        ? evaluate(&restored, retention, RETENTION_N, 1) : (Eval){0};
    PlanMetric restored_plan = checkpoint_ok
        ? evaluate_planning(&restored, &world, &spec, planning_seed, 1)
        : (PlanMetric){0};
    int checkpoint_identity = checkpoint_ok &&
        bytes_equal(candidate.model.identity, restored.identity, 32u);
    int checkpoint_behavior = checkpoint_ok &&
        eval_equal(&adaptation_training_eval, &restored_adaptation) &&
        eval_equal(&candidate.drift, &restored_drift) &&
        eval_equal(&candidate.retention, &restored_retention) &&
        plan_equal(&candidate.planning, &restored_plan) &&
        checkpoint_equivalent(&candidate.model, &restored, &candidate.drift,
                              &restored_drift, &candidate.planning,
                              &restored_plan);
    MutationResult mutations = checkpoint_mutations(&candidate.model);
    LineageResult lineage = lineage_invariants(base_train);
    char model_identity[65], behavior_identity[65];
    uint8_t behavior[32];
    digest_hex(candidate.model.identity, model_identity);
    behavior_digest(&candidate.model, &candidate.drift,
                    &candidate.planning, behavior);
    digest_hex(behavior, behavior_identity);

    print_trial_header(&spec, base_train_seed, base_hold_seed, adapt_train_seed,
                       drift_hold_seed, retention_seed, planning_seed);
    printf("  \"checkpoint_format\":{\"magic_hex\":\"524156454c303500\","
           "\"schema_version\":%u,\"byte_order\":\"big_endian\","
           "\"real_encoding\":\"signed_q20_int64\",\"payload_digest\":\"sha256\","
           "\"transition_top_k\":%u,\"transition_support_min\":%u},\n",
           CHECKPOINT_SCHEMA, TRANSITION_TOP_K, TRANSITION_SUPPORT_MIN);
    printf("  \"candidate\":{\"adaptation_completed\":%s,\"expert_count\":%u,"
           "\"base_training_evaluations\":%" PRIu64
           ",\"adaptation_training_evaluations\":%" PRIu64
           ",\"checkpoint_size_bytes\":%zu,\"model_identity\":\"%s\","
           "\"behavior_identity\":\"%s\",\"base_holdout\":",
           candidate.adaptation_ok ? "true" : "false", candidate.model.n,
           base_metric.expert_evaluations,
           candidate.adaptation_metric.expert_evaluations,
           checkpoint_size, model_identity, behavior_identity);
    print_eval_json(&base_hold_eval);
    printf(",\"adaptation_training\":");
    print_eval_json(&adaptation_training_eval);
    printf(",\"static_model_drift_holdout\":");
    print_eval_json(&static_drift_eval);
    printf(",\"adapted_model_drift_holdout\":");
    print_eval_json(&candidate.drift);
    printf(",\"base_holdout_retention\":");
    print_eval_json(&candidate.retention);
    printf(",\"planning\":");
    print_plan_json(&candidate.planning);
    printf(",\"replay\":");
    print_replay_json(&candidate.replay_metric);
    printf(",\"topology\":");
    print_topology_json(&candidate.topology, &candidate.adaptation_metric);
    printf("},\n");
    printf("  \"integrity\":{\"checkpoint_roundtrip\":%s,"
           "\"checkpoint_identity_match\":%s,\"checkpoint_behavior_match\":%s,"
           "\"checkpoint_mutations\":",
           checkpoint_ok ? "true" : "false",
           checkpoint_identity ? "true" : "false",
           checkpoint_behavior ? "true" : "false");
    print_mutations_json(&mutations);
    printf(",\"lineage_invariants\":");
    print_lineage_json(&lineage);
    printf(",\"unsupported_graph_edge_violations\":%u},\n",
           count_unsupported_graph_violations(&candidate.model));

    printf("  \"comparisons\":{\n");
    int printed = 0;
#define WANT_VARIANT(name) \
    (variant_filter == NULL || strcmp(variant_filter, (name)) == 0)
#define BEGIN_VARIANT() do { if (printed) printf(",\n"); printed = 1; } while (0)
    if (WANT_VARIANT("ravel_0_5_candidate")) {
        BEGIN_VARIANT();
        print_variant_observation("ravel_0_5_candidate", &candidate,
                                  base_metric.expert_evaluations, 0);
    }
    Model fixed8;
    TrainMetric fixed8_metric = {0};
    train_flat(&fixed8, 8u, base_train, &fixed8_metric, 0);
    if (WANT_VARIANT("fixed_8_expert")) {
        Eval drift = evaluate(&fixed8, drift_hold, DRIFT_HOLD_N, 0);
        Eval old = evaluate(&fixed8, retention, RETENTION_N, 0);
        PlanMetric plan =
            evaluate_planning(&fixed8, &world, &spec, planning_seed, 1);
        BEGIN_VARIANT();
        print_variant_json("fixed_8_expert", &fixed8, &drift, &old, &plan,
                           fixed8_metric.expert_evaluations, 0);
    }
    Model flat64;
    TrainMetric flat64_metric = {0};
    train_flat(&flat64, 64u, base_train, &flat64_metric, 0);
    if (WANT_VARIANT("flat_64_expert_complete_scan")) {
        Eval flat_drift = evaluate(&flat64, drift_hold, DRIFT_HOLD_N, 0);
        Eval flat_old = evaluate(&flat64, retention, RETENTION_N, 0);
        PlanMetric flat_plan =
            evaluate_planning(&flat64, &world, &spec, planning_seed, 1);
        BEGIN_VARIANT();
        print_variant_json("flat_64_expert_complete_scan", &flat64,
                           &flat_drift, &flat_old, &flat_plan,
                           flat64_metric.expert_evaluations, 0);
    }
    if (WANT_VARIANT("fixed_topology_64_expert_routed")) {
        Eval flat_drift = evaluate(&flat64, drift_hold, DRIFT_HOLD_N, 1);
        Eval flat_old = evaluate(&flat64, retention, RETENTION_N, 1);
        PlanMetric flat_plan =
            evaluate_planning(&flat64, &world, &spec, planning_seed, 1);
        BEGIN_VARIANT();
        print_variant_json("fixed_topology_64_expert_routed", &flat64,
                           &flat_drift, &flat_old, &flat_plan,
                           flat64_metric.expert_evaluations, 0);
    }
    if (WANT_VARIANT("nearest_centroid_16_no_recursive_births")) {
        Model centroid;
        TrainMetric metric = {0};
        train_flat(&centroid, 16u, base_train, &metric, 0);
        Eval drift = evaluate(&centroid, drift_hold, DRIFT_HOLD_N, 0);
        Eval old = evaluate(&centroid, retention, RETENTION_N, 0);
        PlanMetric plan =
            evaluate_planning(&centroid, &world, &spec, planning_seed, 1);
        BEGIN_VARIANT();
        print_variant_json("nearest_centroid_16_no_recursive_births",
                           &centroid, &drift, &old, &plan,
                           metric.expert_evaluations, 0);
    }
    if (WANT_VARIANT("no_adaptation_static")) {
        BEGIN_VARIANT();
        print_variant_json("no_adaptation_static", &base, &static_drift_eval,
                           &static_retention_eval, &static_plan,
                           base_metric.expert_evaluations, 0);
    }
    const struct {
        const char *name;
        VariantConfig config;
    } adapted_variants[] = {
        {"ravel_without_replay",
         {0u, 1u, 1u, 1u, 0u, 0u, 1u, 1u}},
        {"ravel_without_retirement_matched_work",
         {1u, 0u, 1u, 1u, 0u, 1u, 1u, 1u}},
        {"ravel_complete_scan_without_certification",
         {1u, 1u, 0u, 1u, 0u, 1u, 1u, 1u}},
        {"ravel_no_birth_same_replay_iterations",
         {1u, 0u, 1u, 0u, 0u, 1u, 1u, 1u}},
        {"ravel_random_births",
         {1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u}},
        {"periodic_replay_policy",
         {1u, 1u, 1u, 1u, 0u, 2u, 1u, 1u}}
    };
    for (size_t v = 0; v < sizeof adapted_variants / sizeof adapted_variants[0]; ++v) {
        if (!WANT_VARIANT(adapted_variants[v].name)) continue;
        VariantObservation observation;
        observe_adapted_variant(&observation, &base, base_train, adapt_train,
                                drift_hold, retention, &world, &spec,
                                planning_seed, &adapted_variants[v].config);
        BEGIN_VARIANT();
        print_variant_observation(adapted_variants[v].name, &observation,
                                  base_metric.expert_evaluations, 0);
    }
    if (WANT_VARIANT("matched_compute_fixed_topology")) {
        VariantConfig matched = {
            1u, 0u, 1u, 0u, 0u, 1u, 1u, 1u
        };
        VariantObservation observation;
        observe_adapted_variant(&observation, &base, base_train, adapt_train,
                                drift_hold, retention, &world, &spec,
                                planning_seed, &matched);
        uint32_t repeats = 0u;
        while (observation.adaptation_metric.expert_evaluations <
                   candidate.adaptation_metric.expert_evaluations &&
               repeats++ < 8u) {
            ReplayMetric extra_replay = {0};
            TopologyTrace extra_topology = {0};
            (void)adapt_model(&observation.model, base_train, adapt_train,
                              &matched, &observation.adaptation_metric,
                              &extra_replay, &extra_topology);
        }
        canonicalize_model(&observation.model);
        observation.drift =
            evaluate(&observation.model, drift_hold, DRIFT_HOLD_N, 1);
        observation.retention =
            evaluate(&observation.model, retention, RETENTION_N, 1);
        observation.planning =
            evaluate_planning(&observation.model, &world, &spec,
                              planning_seed, 1);
        BEGIN_VARIANT();
        print_variant_observation("matched_compute_fixed_topology",
                                  &observation,
                                  base_metric.expert_evaluations, 0);
    }
    if (WANT_VARIANT("matched_expert_count_capacity")) {
        Model matched_capacity;
        TrainMetric metric = {0};
        train_flat(&matched_capacity, candidate.model.n, base_train, &metric, 0);
        Eval drift = evaluate(&matched_capacity, drift_hold, DRIFT_HOLD_N, 1);
        Eval old = evaluate(&matched_capacity, retention, RETENTION_N, 1);
        PlanMetric plan =
            evaluate_planning(&matched_capacity, &world, &spec, planning_seed, 1);
        BEGIN_VARIANT();
        print_variant_json("matched_expert_count_capacity", &matched_capacity,
                           &drift, &old, &plan,
                           metric.expert_evaluations, 0);
    }
#undef BEGIN_VARIANT
#undef WANT_VARIANT
    printf("\n  }\n}\n");
    return 0;
}

static void run_self_tests(void) {
    TrialSpec spec = regime_specs[0];
    spec.trial_id = "self-test";
    spec.seed = UINT64_C(0x0505de7e10a11a55);
    World world;
    Event base_train[BASE_TRAIN_N], adapt_train[ADAPT_TRAIN_N];
    Event retention[RETENTION_N], drift_hold[DRIFT_HOLD_N];
    make_world(&world, &spec);
    make_dataset(&world, &spec, base_train, BASE_TRAIN_N,
                 mix64(spec.seed ^ 1u), 0);
    make_dataset(&world, &spec, adapt_train, ADAPT_TRAIN_N,
                 mix64(spec.seed ^ 2u), 1);
    make_dataset(&world, &spec, retention, RETENTION_N,
                 mix64(spec.seed ^ 3u), 0);
    make_dataset(&world, &spec, drift_hold, DRIFT_HOLD_N,
                 mix64(spec.seed ^ 4u), 1);
    Model base;
    TrainMetric base_metric = {0};
    train_recursive(&base, base_train, BASE_TRAIN_N, &base_metric);
    canonicalize_model(&base);
    NegativeResult negative =
        run_negative_tests(&base, base_train, retention, adapt_train, drift_hold);

    Event first[REPLAY_N], second[REPLAY_N], sparse[REPLAY_N];
    ReplayMetric first_metric = {0}, second_metric = {0}, sparse_metric = {0};
    uint32_t first_count =
        select_replay(&base, base_train, BASE_TRAIN_N, 1u, first, &first_metric);
    uint32_t second_count =
        select_replay(&base, base_train, BASE_TRAIN_N, 1u, second, &second_metric);
    int deterministic = first_count == second_count;
    for (uint32_t i = 0; i < first_count && deterministic; ++i) {
        if (!event_equal(&first[i], &second[i])) deterministic = 0;
    }
    Event sparse_input[16];
    for (uint32_t i = 0; i < 16u; ++i) {
        sparse_input[i] = base_train[i % 2u];
        sparse_input[i].state = (uint8_t)(i % 2u);
        sparse_input[i].action = (uint8_t)(i % 2u);
    }
    uint32_t sparse_count =
        select_replay(&base, sparse_input, 16u, 1u, sparse, &sparse_metric);

    Model residual_model;
    memset(&residual_model, 0, sizeof residual_model);
    residual_model.n = 1u;
    seed_expert(&residual_model.e[0], &base_train[0],
                mix64(UINT64_C(0x524553494455414c)), 0u, 0u);
    residual_model.e[0].count = 64u;
    residual_model.e[0].labels[base_train[0].label] = 64u;
    for (uint32_t action = 0; action < ACTIONS; ++action) {
        residual_model.e[0].action_count[action] = 16u;
    }
    Event classification_fixture = base_train[0];
    classification_fixture.label =
        (uint8_t)((classification_fixture.label + 1u) % CLASSES);
    Residual base_residual = event_residual(&residual_model, &base_train[0]);
    Residual classification_residual =
        event_residual(&residual_model, &classification_fixture);
    Event reconstruction_fixture = base_train[0];
    reconstruction_fixture.x[0] =
        clamp_domain((int)reconstruction_fixture.x[0] + 24);
    Residual reconstruction_residual =
        event_residual(&residual_model, &reconstruction_fixture);
    Event prediction_fixture = base_train[0];
    for (uint32_t d = 0; d < D; ++d) {
        prediction_fixture.nx[d] = clamp_domain(-(int)prediction_fixture.nx[d]);
    }
    Residual prediction_residual =
        event_residual(&residual_model, &prediction_fixture);
    Model novelty_model = residual_model;
    novelty_model.e[0].key[0] += 32.0;
    Residual novelty_residual =
        event_residual(&novelty_model, &base_train[0]);
    Model support_model = residual_model;
    support_model.e[0].count = 0u;
    Residual support_residual =
        event_residual(&support_model, &base_train[0]);
    Model uncertainty_model = residual_model;
    memset(uncertainty_model.e[0].labels, 0,
           sizeof uncertainty_model.e[0].labels);
    uncertainty_model.e[0].labels[0] = 32u;
    uncertainty_model.e[0].labels[1] = 32u;
    Residual uncertainty_residual =
        event_residual(&uncertainty_model, &base_train[0]);
    Model action_model = residual_model;
    action_model.e[0].action_count[base_train[0].action] = 0u;
    Residual action_residual =
        event_residual(&action_model, &base_train[0]);
    Event retention_risk_fixture = base_train[0];
    retention_risk_fixture.label =
        (uint8_t)((retention_risk_fixture.label + 1u) % CLASSES);
    Residual retention_risk_residual =
        event_residual(&residual_model, &retention_risk_fixture);

    Model unsupported = base;
    unsupported.e[0].action_count[0] = 0u;
    unsupported.e[0].transition_target[0][0] = 0u;
    unsupported.e[0].transition_support[0][0] = 0u;
    compile_graph(&unsupported);
    int unsupported_unknown =
        unsupported.next_graph[0][0][0] == INVALID_EXPERT;
    Model ambiguous = base;
    ambiguous.e[0].action_count[0] = 5u;
    for (uint32_t d = 0; d < D; ++d) {
        ambiguous.e[0].next[0][d] = ambiguous.e[0].key[d];
    }
    ambiguous.e[0].transition_target[0][0] = 1u;
    ambiguous.e[0].transition_support[0][0] = 3u;
    ambiguous.e[0].transition_target[0][1] = 0u;
    ambiguous.e[0].transition_support[0][1] = 2u;
    compile_graph(&ambiguous);
    int top_k_retained =
        ambiguous.next_graph[0][0][0] == 0u &&
        ambiguous.next_graph[0][0][1] == 1u;
    Model retirement_fixture;
    memset(&retirement_fixture, 0, sizeof retirement_fixture);
    retirement_fixture.n = 1u;
    seed_expert(&retirement_fixture.e[0], &adapt_train[0],
                mix64(UINT64_C(0x5254495245)), 1u, 1u);
    retirement_fixture.e[0].labels[adapt_train[0].label] = 1u;
    retirement_fixture.e[0].count = 1u;
    int unique_retirement_rejected = !retirement_safe(&retirement_fixture, 0u);
    Model retirement_checkpoint;
    memset(&retirement_checkpoint, 0, sizeof retirement_checkpoint);
    retirement_checkpoint.n = 10u;
    for (uint16_t expert = 0; expert < retirement_checkpoint.n; ++expert) {
        seed_expert(&retirement_checkpoint.e[expert], &adapt_train[expert],
                    mix64(UINT64_C(0x5245544348505400) ^ expert), 1u, 1u);
        retirement_checkpoint.e[expert].count = 4u;
        retirement_checkpoint.e[expert].action_count[0] = 4u;
    }
    retirement_checkpoint.e[0].transition_target[0][0] = 1u;
    retirement_checkpoint.e[0].transition_support[0][0] = 3u;
    retirement_checkpoint.e[9].transition_target[0][0] = 9u;
    retirement_checkpoint.e[9].transition_support[0][0] = 3u;
    int retirement_removed =
        remove_expert(&retirement_checkpoint, 1u, 1);
    canonicalize_model(&retirement_checkpoint);
    Model retirement_restored;
    size_t retirement_checkpoint_size = 0u;
    int retirement_checkpoint_valid =
        retirement_removed &&
        retirement_checkpoint.e[0].transition_target[0][0] == INVALID_EXPERT &&
        retirement_checkpoint.e[0].transition_support[0][0] == 0u &&
        retirement_checkpoint.e[1].transition_target[0][0] == 1u &&
        checkpoint_memory_roundtrip(&retirement_checkpoint,
                                    &retirement_restored,
                                    &retirement_checkpoint_size) &&
        retirement_checkpoint_size > 0u;
    Model nonfinite = base;
    nonfinite.e[0].key[0] = NAN;
    ByteBuffer nonfinite_checkpoint;
    int nonfinite_rejected = !serialize_checkpoint(&nonfinite, &nonfinite_checkpoint);
    nonfinite = base;
    nonfinite.e[0].key[0] = DBL_MAX;
    int overflow_rejected = !serialize_checkpoint(&nonfinite, &nonfinite_checkpoint);

    printf("{\n  \"schema\":\"ravel-self-test-observations/0.5\",\n"
           "  \"fixtures\":{\n");
    print_negative_case("malformed_observation", "evaluator_derives",
                        negative.malformed_observation_rejected, 1);
    print_negative_case("out_of_domain_value", "evaluator_derives",
                        negative.out_of_domain_fallback, 1);
    print_negative_case("empty_expert_assignment", "evaluator_derives",
                        negative.empty_assignment_rejected, 1);
    print_negative_case("degenerate_expert_assignment", "evaluator_derives",
                        negative.degenerate_assignment_rejected, 1);
    print_negative_case("duplicate_expert", "evaluator_derives",
                        negative.duplicate_expert_rejected, 1);
    print_negative_case("tied_distance", "evaluator_derives",
                        negative.tied_distance_lower_id, 1);
    print_negative_case("routing_lower_bound_equality", "evaluator_derives",
                        negative.lower_bound_equality_fallback, 1);
    print_negative_case("maximum_expert_capacity", "evaluator_derives",
                        negative.maximum_capacity_preserved, 1);
    print_negative_case("birth_beyond_capacity", "evaluator_derives",
                        negative.birth_beyond_capacity_rejected, 1);
    print_negative_case("wrong_lifecycle_retirement", "evaluator_derives",
                        negative.wrong_lifecycle_retirement_rejected, 1);
    print_negative_case("poisoned_adaptation_labels", "evaluator_derives",
                        negative.poisoned_labels_fail_gate, 1);
    print_negative_case("poisoned_transition_observations", "evaluator_derives",
                        negative.poisoned_transitions_fail_gate, 1);
    print_negative_case("replay_removal_experiment", "evaluator_derives",
                        negative.replay_removal_fail_gate, 1);
    print_negative_case("catastrophic_forgetting_experiment", "evaluator_derives",
                        negative.catastrophic_forgetting_fail_gate, 1);
    print_negative_case("balanced_replay_determinism", "evaluator_derives",
                        deterministic, 1);
    print_negative_case("balanced_replay_no_duplicates", "evaluator_derives",
                        first_metric.selected == first_metric.unique, 1);
    print_negative_case("balanced_replay_coverage", "evaluator_derives",
                        first_metric.labels_covered == CLASSES &&
                            first_metric.actions_covered == ACTIONS &&
                            first_metric.states_covered == STATES, 1);
    print_negative_case("balanced_replay_sparse_strata", "evaluator_derives",
                        sparse_count <= 16u && sparse_metric.unique == sparse_count, 1);
    print_negative_case("classification_residual_fixture", "evaluator_derives",
                        classification_residual.classification >
                            base_residual.classification &&
                            classification_residual.total > base_residual.total, 1);
    print_negative_case("reconstruction_residual_fixture", "evaluator_derives",
                        reconstruction_residual.reconstruction >
                            base_residual.reconstruction &&
                            reconstruction_residual.total > base_residual.total, 1);
    print_negative_case("prediction_residual_fixture", "evaluator_derives",
                        prediction_residual.prediction > base_residual.prediction &&
                            prediction_residual.total > base_residual.total, 1);
    print_negative_case("novelty_residual_fixture", "evaluator_derives",
                        novelty_residual.novelty > base_residual.novelty &&
                            novelty_residual.total > base_residual.total, 1);
    print_negative_case("inverse_support_residual_fixture", "evaluator_derives",
                        support_residual.inverse_support >
                            base_residual.inverse_support &&
                            support_residual.total > base_residual.total, 1);
    print_negative_case("uncertainty_residual_fixture", "evaluator_derives",
                        uncertainty_residual.uncertainty >
                            base_residual.uncertainty &&
                            uncertainty_residual.total > base_residual.total, 1);
    print_negative_case("action_coverage_residual_fixture", "evaluator_derives",
                        action_residual.action_coverage >
                            base_residual.action_coverage &&
                            action_residual.total > base_residual.total, 1);
    print_negative_case("retention_risk_residual_fixture", "evaluator_derives",
                        retention_risk_residual.retention_risk >
                            base_residual.retention_risk &&
                            retention_risk_residual.total > base_residual.total, 1);
    print_negative_case("unsupported_action_unknown", "evaluator_derives",
                        unsupported_unknown, 1);
    print_negative_case("top_k_transition_ambiguity", "evaluator_derives",
                        top_k_retained, 1);
    print_negative_case("retirement_unique_support_safety", "evaluator_derives",
                        unique_retirement_rejected, 1);
    print_negative_case("retirement_checkpoint_remap", "evaluator_derives",
                        retirement_checkpoint_valid, 1);
    print_negative_case("non_finite_serialization", "evaluator_derives",
                        nonfinite_rejected, 1);
    print_negative_case("overflow_serialization", "evaluator_derives",
                        overflow_rejected, 0);
    printf("  },\n  \"replay_observations\":");
    print_replay_json(&first_metric);
    printf(",\n  \"sparse_replay_observations\":");
    print_replay_json(&sparse_metric);
    printf("\n}\n");
}

static void usage(const char *program) {
    fprintf(stderr,
            "usage: %s --trial ID --regime NAME --seed HEX [--variant NAME]\n"
            "       %s --self-test\n"
            "       %s --list-regimes\n",
            program, program, program);
}

int main(int argc, char **argv) {
    const char *trial_id = NULL;
    const char *regime = NULL;
    const char *variant = NULL;
    uint64_t seed = 0u;
    int have_seed = 0;
    int self_test = 0;
    int list_regimes = 0;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--trial") == 0 && i + 1 < argc) {
            trial_id = argv[++i];
        } else if (strcmp(argv[i], "--regime") == 0 && i + 1 < argc) {
            regime = argv[++i];
        } else if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) {
            char *end = NULL;
            seed = strtoull(argv[++i], &end, 0);
            have_seed = end != NULL && *end == '\0';
        } else if (strcmp(argv[i], "--variant") == 0 && i + 1 < argc) {
            variant = argv[++i];
        } else if (strcmp(argv[i], "--self-test") == 0) {
            self_test = 1;
        } else if (strcmp(argv[i], "--list-regimes") == 0) {
            list_regimes = 1;
        } else {
            usage(argv[0]);
            return 2;
        }
    }
    if (list_regimes) {
        for (uint32_t i = 0; i < REGIMES; ++i) {
            puts(regime_specs[i].regime);
        }
        return 0;
    }
    if (self_test) {
        run_self_tests();
        return 0;
    }
    if (trial_id == NULL || regime == NULL || !have_seed) {
        usage(argv[0]);
        return 2;
    }
    return run_trial(trial_id, regime, seed, variant);
}
