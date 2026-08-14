//! Bounded deterministic planner over compiled transition interfaces.

use crate::transition::CompiledTransitions;
use ravel_contracts::status::PlanStatus;
use serde::{Deserialize, Serialize};
use std::collections::{HashSet, VecDeque};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum PlanError {
    #[error("maximum_steps must be non-negative")]
    NegativeBudget,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanResult {
    pub status: PlanStatus,
    pub actions: Vec<i64>,
    pub visited: Vec<i64>,
    pub reason: String,
}

pub fn plan(
    graph: &CompiledTransitions,
    start: i64,
    goal: i64,
    maximum_steps: i64,
) -> Result<PlanResult, PlanError> {
    if maximum_steps < 0 {
        return Err(PlanError::NegativeBudget);
    }
    let mut queue = VecDeque::from([(start, Vec::<i64>::new())]);
    let mut seen = HashSet::from([start]);
    let mut visited = Vec::new();
    while let Some((state, actions)) = queue.pop_front() {
        visited.push(state);
        if state == goal {
            return Ok(PlanResult {
                status: PlanStatus::Pass,
                actions,
                visited,
                reason: "route_found".into(),
            });
        }
        if actions.len() as i64 >= maximum_steps {
            continue;
        }
        let mut available: Vec<i64> = graph
            .edges
            .iter()
            .filter(|edge| edge.source == state)
            .map(|edge| edge.action)
            .collect();
        available.sort_unstable();
        available.dedup();
        for action in available {
            for edge in graph.outgoing(state, action) {
                if seen.contains(&edge.target) {
                    continue;
                }
                seen.insert(edge.target);
                let mut next_actions = actions.clone();
                next_actions.push(action);
                queue.push_back((edge.target, next_actions));
            }
        }
    }
    Ok(PlanResult {
        status: PlanStatus::Unknown,
        actions: Vec::new(),
        visited,
        reason: "route_unavailable".into(),
    })
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;
    use crate::transition::TransitionCompiler;
    use crate::world::{ToyBranchingWorld, ToyRingWorld, WorldProvider};

    #[test]
    fn branching_provider_requires_lower_ranked_transition() {
        let graph = TransitionCompiler::compile(&ToyBranchingWorld).expect("compile");
        let result = plan(&graph, 0, 3, 32).expect("plan");
        assert_eq!(result.status, PlanStatus::Pass);
        assert_eq!(result.actions, vec![0, 1]);
        assert_eq!(result.reason, "route_found");
    }

    #[test]
    fn provider_substitution_changes_identity_not_compiler() {
        let first = TransitionCompiler::compile(&ToyBranchingWorld).expect("compile");
        let second = TransitionCompiler::compile(&ToyRingWorld).expect("compile");
        assert_ne!(first.provider_id, second.provider_id);
        assert_ne!(first.edges, second.edges);
        assert_eq!(
            plan(&second, 0, 3, 32).expect("plan").status,
            PlanStatus::Pass
        );
    }

    #[test]
    fn unsupported_route_is_unknown() {
        let graph = TransitionCompiler::compile(&ToyBranchingWorld).expect("compile");
        let result = plan(&graph, 2, 3, 1).expect("plan");
        assert_eq!(result.status, PlanStatus::Unknown);
        assert_eq!(result.reason, "route_unavailable");
    }

    #[test]
    fn provider_ids_are_stable() {
        assert_eq!(ToyBranchingWorld.provider_id(), "ravel-toy-branching/1");
        assert_eq!(ToyRingWorld.provider_id(), "ravel-toy-ring/1");
    }
}
