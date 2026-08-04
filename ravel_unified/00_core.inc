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
#define STATES 64u
#define ACTIONS 4u
#define MAXE 96u
#define BASE_E 64u
#define INIT_E 8u
#define ROUTE_K 8u
#define CELLS 256u
#define NTRAIN 32768u
#define NHOLD 8192u
#define NADAPT 16384u
#define NREPLAY 8192u
#define ADAPT_BIRTHS 24u
#define ADAPT_TARGET 80u
#define GROW_PER_ROUND 8u
#define REFINE_FINAL 5u
#define REFINE_ADAPT 6u
#define LO (-64)
#define HI 63
#define PLAN_CASES 512u
#define PLAN_LIMIT 32u

/* One event supplies all learning surfaces: present, action, label, next observation. */
typedef struct {
    int8_t x[D];
    int8_t nx[D];
    uint8_t action;
    uint8_t label;
    uint8_t state;
    uint8_t next_state;
} Event;

typedef struct {
    double key[D];               /* retrieval key + compressed present-state representation */
    double decode[D];            /* reconstruction program */
    double next[ACTIONS][D];     /* action-conditioned world-model program */
    uint32_t labels[CLASSES];
    uint32_t action_count[ACTIONS];
    uint32_t count;
    uint32_t errors;
    double reconstruction_sse;
    double prediction_sse;
    uint8_t label;
    uint8_t active;
    uint16_t generation;
    uint64_t lineage;
} Expert;

typedef struct {
    uint16_t id[ROUTE_K];
    double excluded_lb;
} Cell;

typedef struct {
    Expert e[MAXE];
    uint16_t n;
    uint16_t next_graph[MAXE][ACTIONS];
    uint64_t epoch;
    uint64_t digest;
} Model;

typedef struct {
    uint64_t samples;
    uint64_t correct;
    uint64_t exact_mismatches;
    uint64_t certified;
    uint64_t expert_evaluations;
    double reconstruction_sse;
    double prediction_sse;
    uint64_t transition_correct;
    uint64_t checksum;
} Eval;

typedef struct {
    uint64_t samples;
    uint64_t expert_evaluations;
    uint64_t certified;
    uint64_t births;
    uint64_t retired;
    uint64_t lineage_digest;
} TrainMetric;

typedef struct {
    uint64_t cases;
    uint64_t solved;
    uint64_t exact_goals;
    uint64_t expansions;
    uint64_t checksum;
} PlanMetric;

static uint64_t rng_state = UINT64_C(0x524156454c553033);
static int8_t world_c[STATES][D];
static uint8_t world_y[STATES];
static uint8_t world_next[STATES][ACTIONS];
static Event train_set[NTRAIN];
static Event hold_set[NHOLD];
static Event adapt_set[NADAPT];
static Event replay_set[NREPLAY];
static Event adapt_mix[NADAPT + NREPLAY];
static uint16_t assignment[NTRAIN > (NADAPT + NREPLAY) ? NTRAIN : (NADAPT + NREPLAY)];

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

static uint8_t majority(const uint32_t counts[CLASSES]) {
    uint8_t best = 0u;
    for (uint8_t y = 1u; y < CLASSES; ++y) {
        if (counts[y] > counts[best]) best = y;
    }
    return best;
}

static void make_world(void) {
    for (uint32_t s = 0; s < STATES; ++s) {
        for (uint32_t d = 0; d < 6u; ++d) world_c[s][d] = (int8_t)(((s >> d) & 1u) ? 42 : -42);
        world_c[s][6] = (int8_t)(-36 + 24 * (int)((s * 5u + (s >> 2)) & 3u));
        world_c[s][7] = (int8_t)(-36 + 24 * (int)((s * 3u + (s >> 1)) & 3u));
        world_y[s] = (uint8_t)(((s * 29u) ^ (s >> 1) ^ (s >> 3)) & 7u);
        world_next[s][0] = (uint8_t)((s + 1u) & 63u);
        world_next[s][1] = (uint8_t)((s + 63u) & 63u);
        world_next[s][2] = (uint8_t)(s ^ 8u);
        world_next[s][3] = (uint8_t)(s ^ 32u);
    }
