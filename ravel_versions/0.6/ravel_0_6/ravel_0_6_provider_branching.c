#include "ravel_0_6_world.h"

#include <string.h>

const char *ravel06_world_provider_id(void) {
    return "ravel-toy-branching-c/1";
}

int ravel06_world_reset(Ravel06World *world) {
    if (world == NULL) return 0;
    memset(world, 0, sizeof *world);
    return 1;
}

int ravel06_world_init(Ravel06World *world, const Ravel06WorldConfig *config) {
    if (world == NULL || config == NULL || config->amplitude < 0) return 0;
    if (!ravel06_world_reset(world)) return 0;
    for (uint32_t state = 0; state < RAVEL06_WORLD_STATES; ++state) {
        uint32_t visible = config->ambiguous != 0u ? state / 2u : state;
        for (uint32_t dimension = 0; dimension < 6u; ++dimension) {
            world->center[state][dimension] = (int16_t)(
                ((visible >> dimension) & 1u) ? config->amplitude : -config->amplitude);
        }
        world->center[state][6] = (int16_t)(-30 + 20 * (int)((visible * 5u + (visible >> 2u)) & 3u));
        world->center[state][7] = (int16_t)(-30 + 20 * (int)((visible * 3u + (visible >> 1u)) & 3u));
        world->label[state] = (uint8_t)(((visible * 29u) ^ (visible >> 1u) ^ (visible >> 3u)) & 7u);
        world->base_next[state][0] = (uint8_t)((state + 1u) & 63u);
        world->base_next[state][1] = (uint8_t)((state + 63u) & 63u);
        world->base_next[state][2] = (uint8_t)(state ^ 8u);
        world->base_next[state][3] = (uint8_t)(state ^ 32u);
        for (uint32_t action = 0; action < RAVEL06_WORLD_ACTIONS; ++action) {
            world->drift_next[state][action] = world->base_next[state][action];
        }
        if (config->transition_drift != 0u && state < 24u) {
            world->drift_next[state][0] = (uint8_t)(state ^ 16u);
            world->drift_next[state][2] = (uint8_t)((state + 2u) & 63u);
        }
    }
    return 1;
}

int ravel06_world_observe(const Ravel06World *world, uint8_t state,
                          int16_t out[RAVEL06_WORLD_D]) {
    if (world == NULL || out == NULL || state >= RAVEL06_WORLD_STATES) return 0;
    memcpy(out, world->center[state], sizeof world->center[state]);
    return 1;
}

int ravel06_world_transition(const Ravel06World *world, uint8_t state,
                             uint8_t action, uint8_t drift, uint8_t *target) {
    if (world == NULL || target == NULL || state >= RAVEL06_WORLD_STATES ||
        action >= RAVEL06_WORLD_ACTIONS) return 0;
    *target = drift != 0u ? world->drift_next[state][action]
                          : world->base_next[state][action];
    return 1;
}
