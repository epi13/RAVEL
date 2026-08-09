/* Behavioral fixtures compiled against either frozen 0.5 or candidate 001. */
#ifndef RAVEL_06_CANDIDATE_SOURCE
#error "compile with -DRAVEL_06_CANDIDATE_SOURCE=\"path\""
#endif

#define main ravel_candidate_main
#include RAVEL_06_CANDIDATE_SOURCE
#undef main

static void fixture_model(Model *model, const Event *event) {
    memset(model, 0, sizeof *model);
    model->n = 3u;
    seed_expert(&model->e[0], event, UINT64_C(0x101), 0u, 0u);
    seed_expert(&model->e[1], event, UINT64_C(0x102), 0u, 0u);
    seed_expert(&model->e[2], event, UINT64_C(0x103), 0u, 0u);
    for (uint16_t expert = 0u; expert < model->n; ++expert) {
        for (uint32_t action = 0u; action < ACTIONS; ++action) {
            for (uint32_t slot = 0u; slot < TRANSITION_TOP_K; ++slot) {
                model->next_graph[expert][action][slot] = INVALID_EXPERT;
                model->next_graph_support[expert][action][slot] = 0u;
            }
        }
    }
}

static int slot_one_route_fixture(const Event *event) {
    Model model;
    fixture_model(&model, event);
    model.next_graph[0][0][1] = 1u;
    model.next_graph_support[0][0][1] = TRANSITION_SUPPORT_MIN;
    model.next_graph[1][0][0] = 2u;
    model.next_graph_support[1][0][0] = TRANSITION_SUPPORT_MIN;
    uint8_t actions[PLAN_LIMIT] = {0};
    uint32_t used = 0u;
    uint64_t expansions = 0u;
    uint64_t unknown = 0u;
    return plan_actions(&model, 0u, 2u, actions, &used, &expansions, &unknown) &&
           used == 2u && actions[0] == 0u && actions[1] == 0u;
}

static int birth_support_fixture(const Event *event) {
    Model model;
    fixture_model(&model, event);
    model.n = 1u;
    Expert *parent = &model.e[0];
    parent->count = 77u;
    parent->errors = 11u;
    parent->labels[(event->label + 1u) % CLASSES] = 9u;
    parent->action_count[(event->action + 1u) % ACTIONS] = 6u;
    parent->transition_target[(event->action + 1u) % ACTIONS][0] = 0u;
    parent->transition_support[(event->action + 1u) % ACTIONS][0] = 6u;
    seed_adaptation_expert(&model, 1u, event, 19u);
    model.n = 2u;
    compile_graph(&model);
    const Expert *child = &model.e[1];
    uint32_t unrelated_action = (event->action + 1u) % ACTIONS;
    int unrelated_support_absent =
        child->count == 1u &&
        child->action_count[unrelated_action] == 0u &&
        child->transition_target[unrelated_action][0] == INVALID_EXPERT &&
        child->transition_support[unrelated_action][0] == 0u;
    int unsupported_action_unknown =
        child->action_count[unrelated_action] < TRANSITION_SUPPORT_MIN &&
        model.next_graph[1][unrelated_action][0] == INVALID_EXPERT;
    return unrelated_support_absent && unsupported_action_unknown;
}

int main(void) {
    Event event;
    memset(&event, 0, sizeof event);
    event.action = 0u;
    event.label = 1u;
    event.x[0] = 3;
    event.nx[0] = 4;
    int slot_one = slot_one_route_fixture(&event);
    int birth = birth_support_fixture(&event);
    uint64_t checksum = mix64((uint64_t)slot_one ^
                              ((uint64_t)birth << 8) ^
                              UINT64_C(0x5236303346495854));
    printf("{\"schema\":\"ravel-0.6-behavioral-fixtures/1\","
           "\"slot_one_route\":%d,\"birth_support_reset\":%d,"
           "\"checksum\":\"%016" PRIx64 "\"}\n",
           slot_one, birth, checksum);
    return (slot_one && birth) ? 0 : 1;
}
