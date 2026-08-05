#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define D 8u
#define CLASSES 8u
#define TEACHERS 64u
#define MAXE 64u
#define INIT_E 8u
#define ROUTE_K 8u
#define CELLS 256u
#define NTRAIN 32768u
#define NTEST 8192u
#define GROW_PER_ROUND 8u
#define FINAL_REFINE 5u
#define FLAT_REFINE 10u
#define FIXED_REFINE 10u
#define LO (-64)
#define HI 63

typedef struct { int8_t x[D]; uint8_t y; } Sample;
typedef struct {
    double c[D];
    uint32_t labels[CLASSES];
    uint32_t count;
    uint8_t label;
    uint64_t lineage;
} Expert;
typedef struct { uint16_t id[ROUTE_K]; double excluded_lb; } Cell;
typedef struct {
    uint64_t samples;
    uint64_t correct;
    uint64_t exact_mismatches;
    uint64_t certified;
    uint64_t expert_evaluations;
    uint64_t checksum;
} Eval;
typedef struct {
    uint64_t expert_evaluations;
    uint64_t certified;
    uint64_t samples;
    uint64_t splits;
    uint64_t lineage_digest;
} TrainMetric;

static uint64_t rng_state = UINT64_C(0x524156454c54524e);
static int8_t teacher_c[TEACHERS][D];
static uint8_t teacher_y[TEACHERS];
static Sample train_set[NTRAIN];
static Sample test_set[NTEST];
static uint16_t assignment[NTRAIN];

static uint32_t rng_u32(void) {
    rng_state ^= rng_state >> 12;
    rng_state ^= rng_state << 25;
    rng_state ^= rng_state >> 27;
    return (uint32_t)((rng_state * UINT64_C(2685821657736338717)) >> 32);
}

static uint64_t mix64(uint64_t x) {
    x ^= x >> 30; x *= UINT64_C(0xbf58476d1ce4e5b9);
    x ^= x >> 27; x *= UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}

static int8_t clamp_i8(int v) {
    if (v < LO) return (int8_t)LO;
    if (v > HI) return (int8_t)HI;
    return (int8_t)v;
}

static double dist_sample(const Sample *s, const Expert *e) {
    double z = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double q = (double)s->x[d] - e->c[d];
        z += q * q;
    }
    return z;
}

static double dist_vec(const double a[D], const double b[D]) {
    double z = 0.0;
    for (uint32_t d = 0; d < D; ++d) {
        double q = a[d] - b[d];
        z += q * q;
    }
    return z;
}

static uint8_t majority(const uint32_t counts[CLASSES]) {
    uint8_t best = 0;
    for (uint8_t y = 1; y < CLASSES; ++y) {
        if (counts[y] > counts[best]) best = y;
    }
    return best;
}

static void make_teacher(void) {
    for (uint32_t t = 0; t < TEACHERS; ++t) {
        for (uint32_t d = 0; d < 6u; ++d) {
            teacher_c[t][d] = (int8_t)(((t >> d) & 1u) ? 42 : -42);
        }
        teacher_c[t][6] = (int8_t)(-36 + 24 * (int)((t * 5u + (t >> 2)) & 3u));
        teacher_c[t][7] = (int8_t)(-36 + 24 * (int)((t * 3u + (t >> 1)) & 3u));
        teacher_y[t] = (uint8_t)(((t * 29u) ^ (t >> 1) ^ (t >> 3)) & 7u);
    }
}

static void make_dataset(Sample *out, uint32_t n, uint64_t seed) {
    rng_state = seed;
    for (uint32_t i = 0; i < n; ++i) {
        uint32_t t = rng_u32() % TEACHERS;
        out[i].y = teacher_y[t];
        for (uint32_t d = 0; d < D; ++d) {
            int noise = (int)(rng_u32() % 11u) - 5;
            out[i].x[d] = clamp_i8((int)teacher_c[t][d] + noise);
        }
    }
}

static uint16_t cell_id(const Sample *s, int *in_domain) {
    uint16_t b = 0;
    *in_domain = 1;
    for (uint32_t d = 0; d < D; ++d) {
        if (s->x[d] < LO || s->x[d] > HI) *in_domain = 0;
    }
    for (uint32_t d = 0; d < 4u; ++d) {
        int v = ((int)s->x[d] - LO) / 32;
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

static void build_lattice(const Expert e[MAXE], uint16_t n, Cell cells[CELLS]) {
    for (uint32_t b = 0; b < CELLS; ++b) {
        double d[MAXE];
        uint16_t id[MAXE];
        for (uint16_t j = 0; j < n; ++j) {
            double z = 0.0;
            for (uint32_t k = 0; k < 4u; ++k) {
                uint32_t shift = 2u * (3u - k);
                uint32_t v = (b >> shift) & 3u;
                double lo = (double)(LO + 32 * (int)v);
                double hi = lo + 31.0;
                z += axis_lb(e[j].c[k], lo, hi);
            }
            d[j] = z;
            id[j] = j;
        }
        uint16_t take = n < ROUTE_K ? n : ROUTE_K;
        uint16_t need = n > ROUTE_K ? (uint16_t)(ROUTE_K + 1u) : n;
        for (uint16_t i = 0; i < need; ++i) {
            uint16_t m = i;
            for (uint16_t j = (uint16_t)(i + 1u); j < n; ++j) {
                if (d[j] < d[m] || (d[j] == d[m] && id[j] < id[m])) m = j;
            }
            double td = d[i]; d[i] = d[m]; d[m] = td;
            uint16_t ti = id[i]; id[i] = id[m]; id[m] = ti;
        }
        for (uint16_t i = 0; i < ROUTE_K; ++i) cells[b].id[i] = UINT16_MAX;
        for (uint16_t i = 0; i < take; ++i) cells[b].id[i] = id[i];
        cells[b].excluded_lb = n > ROUTE_K ? d[ROUTE_K] : DBL_MAX;
    }
}

static int better(double d, uint16_t id, double best_d, uint16_t best_id) {
    return d < best_d || (d == best_d && id < best_id);
}

static uint16_t full_nearest(const Sample *s, const Expert e[MAXE], uint16_t n, uint64_t *evals) {
    double best_d = DBL_MAX;
    uint16_t best = UINT16_MAX;
    for (uint16_t j = 0; j < n; ++j) {
        double d = dist_sample(s, &e[j]);
        ++*evals;
        if (better(d, j, best_d, best)) { best_d = d; best = j; }
    }
    return best;
}

static uint16_t routed_nearest(const Sample *s, const Expert e[MAXE], uint16_t n,
                               const Cell cells[CELLS], uint64_t *evals, uint64_t *certified) {
    int in_domain = 0;
    uint16_t b = cell_id(s, &in_domain);
    uint8_t seen[MAXE];
    memset(seen, 0, sizeof seen);
    double best_d = DBL_MAX;
    uint16_t best = UINT16_MAX;
    uint16_t take = n < ROUTE_K ? n : ROUTE_K;
    for (uint16_t i = 0; i < take; ++i) {
        uint16_t j = cells[b].id[i];
        assert(j < n);
        seen[j] = 1u;
        double d = dist_sample(s, &e[j]);
        ++*evals;
        if (better(d, j, best_d, best)) { best_d = d; best = j; }
    }
    if (in_domain && best_d < cells[b].excluded_lb) {
        ++*certified;
        return best;
    }
    for (uint16_t j = 0; j < n; ++j) {
        if (!seen[j]) {
            double d = dist_sample(s, &e[j]);
            ++*evals;
            if (better(d, j, best_d, best)) { best_d = d; best = j; }
        }
    }
    return best;
}

static void farthest_init(Expert e[MAXE], uint16_t n, const Sample *data, uint32_t count,
                          uint64_t *evals) {
    memset(e, 0, sizeof(Expert) * MAXE);
    for (uint32_t d = 0; d < D; ++d) e[0].c[d] = (double)data[0].x[d];
    e[0].label = data[0].y;
    e[0].lineage = mix64(UINT64_C(0x524156454c000001));
    for (uint16_t k = 1; k < n; ++k) {
        double far = -1.0;
        uint32_t far_i = 0u;
        for (uint32_t i = 0; i < count; ++i) {
            double nearest = DBL_MAX;
            for (uint16_t j = 0; j < k; ++j) {
                double z = 0.0;
                for (uint32_t d = 0; d < D; ++d) {
                    double v = (double)data[i].x[d] - e[j].c[d];
                    z += v * v;
                }
                ++*evals;
                if (z < nearest) nearest = z;
            }
            if (nearest > far) { far = nearest; far_i = i; }
        }
        for (uint32_t d = 0; d < D; ++d) e[k].c[d] = (double)data[far_i].x[d];
        e[k].label = data[far_i].y;
        e[k].lineage = mix64(e[0].lineage ^ (uint64_t)k);
    }
}

static void refine(Expert e[MAXE], uint16_t n, const Sample *data, uint32_t count,
                   uint32_t iterations, int routed, uint16_t *out_assignment,
                   TrainMetric *metric) {
    Cell cells[CELLS];
    for (uint32_t it = 0; it < iterations; ++it) {
        double sums[MAXE][D];
        uint32_t counts[MAXE];
        uint32_t labels[MAXE][CLASSES];
        memset(sums, 0, sizeof sums);
        memset(counts, 0, sizeof counts);
        memset(labels, 0, sizeof labels);
        if (routed) build_lattice(e, n, cells);
        for (uint32_t i = 0; i < count; ++i) {
            uint16_t j;
            if (routed) {
                j = routed_nearest(&data[i], e, n, cells,
                                   &metric->expert_evaluations, &metric->certified);
            } else {
                j = full_nearest(&data[i], e, n, &metric->expert_evaluations);
            }
            ++metric->samples;
            if (out_assignment != NULL) out_assignment[i] = j;
            ++counts[j];
            ++labels[j][data[i].y];
            for (uint32_t d = 0; d < D; ++d) {
                double v = (double)data[i].x[d];
                sums[j][d] += v;
            }
        }
        for (uint16_t j = 0; j < n; ++j) {
            e[j].count = counts[j];
            memcpy(e[j].labels, labels[j], sizeof e[j].labels);
            if (counts[j] > 0u) {
                for (uint32_t d = 0; d < D; ++d) e[j].c[d] = sums[j][d] / (double)counts[j];
                e[j].label = majority(labels[j]);
            }
        }
    }
}

static double expert_score(const Expert *e) {
    if (e->count < 2u) return -1.0;
    uint32_t max_label = 0u;
    for (uint32_t y = 0; y < CLASSES; ++y) if (e->labels[y] > max_label) max_label = e->labels[y];
    uint32_t errors = e->count - max_label;
    return (double)errors * 1000000000.0 + (double)e->count;
}

static int split_one(Expert e[MAXE], uint16_t parent, uint16_t child,
                     const Sample *data, uint32_t count, const uint16_t *a,
                     uint32_t round) {
    uint32_t first = UINT32_MAX;
    for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) { first = i; break; }
    if (first == UINT32_MAX) return 0;
    uint32_t pa = first;
    double far = -1.0;
    for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) {
        double z = 0.0;
        for (uint32_t d = 0; d < D; ++d) {
            double v = (double)data[i].x[d] - (double)data[first].x[d];
            z += v * v;
        }
        if (z > far) { far = z; pa = i; }
    }
    uint32_t pb = pa;
    far = -1.0;
    for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) {
        double z = 0.0;
        for (uint32_t d = 0; d < D; ++d) {
            double v = (double)data[i].x[d] - (double)data[pa].x[d];
            z += v * v;
        }
        if (z > far) { far = z; pb = i; }
    }
    if (pa == pb) return 0;
    double ca[D], cb[D];
    for (uint32_t d = 0; d < D; ++d) { ca[d] = (double)data[pa].x[d]; cb[d] = (double)data[pb].x[d]; }
    uint32_t la[CLASSES], lb[CLASSES];
    uint32_t na = 0u, nb = 0u;
    for (uint32_t it = 0; it < 8u; ++it) {
        double sa[D] = {0}, sb[D] = {0};
        memset(la, 0, sizeof la); memset(lb, 0, sizeof lb);
        na = 0u; nb = 0u;
        for (uint32_t i = 0; i < count; ++i) if (a[i] == parent) {
            double va[D];
            for (uint32_t d = 0; d < D; ++d) va[d] = (double)data[i].x[d];
            double da = dist_vec(va, ca), db = dist_vec(va, cb);
            int side = da < db || (da == db && pa < pb) ? 0 : 1;
            if (side == 0) {
                ++na; ++la[data[i].y];
                for (uint32_t d = 0; d < D; ++d) sa[d] += va[d];
            } else {
                ++nb; ++lb[data[i].y];
                for (uint32_t d = 0; d < D; ++d) sb[d] += va[d];
            }
        }
        if (na == 0u || nb == 0u) return 0;
        for (uint32_t d = 0; d < D; ++d) { ca[d] = sa[d] / (double)na; cb[d] = sb[d] / (double)nb; }
    }
    uint64_t root = e[parent].lineage;
    memset(&e[parent], 0, sizeof e[parent]);
    memset(&e[child], 0, sizeof e[child]);
    for (uint32_t d = 0; d < D; ++d) { e[parent].c[d] = ca[d]; e[child].c[d] = cb[d]; }
    memcpy(e[parent].labels, la, sizeof la); memcpy(e[child].labels, lb, sizeof lb);
    e[parent].count = na; e[child].count = nb;
    e[parent].label = majority(la); e[child].label = majority(lb);
    e[parent].lineage = mix64(root ^ ((uint64_t)round << 32) ^ UINT64_C(0xa5));
    e[child].lineage = mix64(root ^ ((uint64_t)round << 32) ^ UINT64_C(0x5a));
    return 1;
}

static uint16_t train_recursive(Expert e[MAXE], TrainMetric *metric) {
    uint64_t init_evals = 0u;
    farthest_init(e, INIT_E, train_set, NTRAIN, &init_evals);
    metric->expert_evaluations += init_evals;
    uint16_t n = INIT_E;
    uint32_t round = 0u;
    while (n < MAXE) {
        refine(e, n, train_set, NTRAIN, 1u, 1, assignment, metric);
        uint16_t order[MAXE];
        for (uint16_t j = 0; j < n; ++j) order[j] = j;
        for (uint16_t i = 0; i < n; ++i) {
            uint16_t m = i;
            for (uint16_t j = (uint16_t)(i + 1u); j < n; ++j) {
                double sj = expert_score(&e[order[j]]), sm = expert_score(&e[order[m]]);
                if (sj > sm || (sj == sm && order[j] < order[m])) m = j;
            }
            uint16_t t = order[i]; order[i] = order[m]; order[m] = t;
        }
        uint16_t target = (uint16_t)((MAXE - n) < GROW_PER_ROUND ? (MAXE - n) : GROW_PER_ROUND);
        uint16_t made = 0u;
        for (uint16_t i = 0; i < n && made < target; ++i) {
            uint16_t parent = order[i];
            if (split_one(e, parent, (uint16_t)(n + made), train_set, NTRAIN, assignment, round)) {
                ++made; ++metric->splits;
            }
        }
        if (made == 0u) break;
        n = (uint16_t)(n + made);
        ++round;
    }
    refine(e, n, train_set, NTRAIN, FINAL_REFINE, 1, assignment, metric);
    uint64_t dig = 0u;
    for (uint16_t j = 0; j < n; ++j) dig ^= mix64(e[j].lineage ^ ((uint64_t)e[j].label << 56));
    metric->lineage_digest = dig;
    return n;
}

static void train_flat(Expert e[MAXE], uint16_t n, uint32_t iterations, TrainMetric *metric) {
    uint64_t init_evals = 0u;
    farthest_init(e, n, train_set, NTRAIN, &init_evals);
    metric->expert_evaluations += init_evals;
    refine(e, n, train_set, NTRAIN, iterations, 0, NULL, metric);
}

static Eval evaluate(const Expert e[MAXE], uint16_t n, int routed) {
    Eval out = {0};
    Cell cells[CELLS];
    if (routed) build_lattice(e, n, cells);
    for (uint32_t i = 0; i < NTEST; ++i) {
        uint64_t before = out.expert_evaluations;
        uint16_t got;
        if (routed) got = routed_nearest(&test_set[i], e, n, cells,
                                         &out.expert_evaluations, &out.certified);
        else got = full_nearest(&test_set[i], e, n, &out.expert_evaluations);
        uint64_t ref_evals = 0u;
        uint16_t oracle = full_nearest(&test_set[i], e, n, &ref_evals);
        if (got != oracle) ++out.exact_mismatches;
        if (e[got].label == test_set[i].y) ++out.correct;
        ++out.samples;
        out.checksum ^= mix64(((uint64_t)got << 48) ^ ((uint64_t)e[got].label << 40) ^ i);
        assert(out.expert_evaluations - before >= (uint64_t)(n < ROUTE_K ? n : (routed ? ROUTE_K : n)));
    }
    return out;
}

static void print_eval(const char *name, const Eval *e, uint16_t experts, int comma) {
    double accuracy = (double)e->correct / (double)e->samples;
    double cert = (double)e->certified / (double)e->samples;
    double mean = (double)e->expert_evaluations / (double)e->samples;
    printf("    \"%s\":{\"experts\":%u,\"samples\":%" PRIu64 ",\"accuracy\":%.9f,"
           "\"exact_mismatches\":%" PRIu64 ",\"certified_rate\":%.9f,"
           "\"mean_experts\":%.6f,\"checksum\":\"%016" PRIx64 "\"}%s\n",
           name, experts, e->samples, accuracy, e->exact_mismatches, cert, mean,
           e->checksum, comma ? "," : "");
}

int main(void) {
    make_teacher();
    make_dataset(train_set, NTRAIN, UINT64_C(0x747261696e000001));
    make_dataset(test_set, NTEST, UINT64_C(0x686f6c646f757401));

    Expert recursive[MAXE], fixed[MAXE], flat[MAXE];
    TrainMetric rt = {0}, ft = {0}, flt = {0};
    uint16_t rn = train_recursive(recursive, &rt);
    train_flat(fixed, INIT_E, FIXED_REFINE, &ft);
    train_flat(flat, MAXE, FLAT_REFINE, &flt);

    Eval re = evaluate(recursive, rn, 1);
    Eval fe = evaluate(fixed, INIT_E, 0);
    Eval fle = evaluate(flat, MAXE, 0);

    double racc = (double)re.correct / (double)re.samples;
    double facc = (double)fe.correct / (double)fe.samples;
    double flacc = (double)fle.correct / (double)fle.samples;
    double rmean = (double)re.expert_evaluations / (double)re.samples;
    int pass = rn == MAXE && re.exact_mismatches == 0u && racc >= 0.95 &&
               racc + 0.01 >= flacc && racc - facc >= 0.20 && rmean <= 16.0;

    printf("{\n  \"schema\":\"ravel-training-evidence/0.2\",\n");
    printf("  \"dataset\":{\"train\":%u,\"holdout\":%u,\"dimensions\":%u,"
           "\"latent_regions\":%u,\"classes\":%u},\n", NTRAIN, NTEST, D, TEACHERS, CLASSES);
    printf("  \"training\":{\n");
    printf("    \"recursive\":{\"final_experts\":%u,\"splits\":%" PRIu64
           ",\"samples_processed\":%" PRIu64 ",\"expert_evaluations\":%" PRIu64
           ",\"certified_routes\":%" PRIu64 ",\"lineage_digest\":\"%016" PRIx64 "\"},\n",
           rn, rt.splits, rt.samples, rt.expert_evaluations, rt.certified, rt.lineage_digest);
    printf("    \"fixed8\":{\"expert_evaluations\":%" PRIu64 "},\n", ft.expert_evaluations);
    printf("    \"flat64\":{\"expert_evaluations\":%" PRIu64 "}\n", flt.expert_evaluations);
    printf("  },\n  \"holdout\":{\n");
    print_eval("recursive", &re, rn, 1);
    print_eval("fixed8", &fe, INIT_E, 1);
    print_eval("flat64", &fle, MAXE, 0);
    printf("  },\n  \"development_result\":\"%s\",\n", pass ? "PASS" : "FAIL");
    printf("  \"formal_mncs_status\":\"UNKNOWN\",\n");
    printf("  \"formal_mncds_status\":\"UNKNOWN\",\n");
    printf("  \"promotion_authorized\":false\n}\n");
    return pass ? 0 : 1;
}
