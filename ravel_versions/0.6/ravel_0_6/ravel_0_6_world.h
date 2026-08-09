#ifndef RAVEL_0_6_WORLD_H
#define RAVEL_0_6_WORLD_H

#include <stdint.h>

#define RAVEL06_WORLD_ABI_VERSION "ravel-0.6-world-abi/1"
#define RAVEL06_WORLD_ABI_NUMERIC 1u
#define RAVEL06_WORLD_STATES 64u
#define RAVEL06_WORLD_ACTIONS 4u
#define RAVEL06_WORLD_D 8u

typedef struct {
    int amplitude;
    uint8_t transition_drift;
    uint8_t ambiguous;
} Ravel06WorldConfig;

typedef struct {
    int16_t center[RAVEL06_WORLD_STATES][RAVEL06_WORLD_D];
    uint8_t label[RAVEL06_WORLD_STATES];
    uint8_t base_next[RAVEL06_WORLD_STATES][RAVEL06_WORLD_ACTIONS];
    uint8_t drift_next[RAVEL06_WORLD_STATES][RAVEL06_WORLD_ACTIONS];
} Ravel06World;

const char *ravel06_world_provider_id(void);
int ravel06_world_init(Ravel06World *world, const Ravel06WorldConfig *config);
int ravel06_world_reset(Ravel06World *world);
int ravel06_world_observe(const Ravel06World *world, uint8_t state,
                          int16_t out[RAVEL06_WORLD_D]);
int ravel06_world_transition(const Ravel06World *world, uint8_t state,
                             uint8_t action, uint8_t drift, uint8_t *target);

#endif
