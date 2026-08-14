//! Deterministic transition compilation independent of a world implementation.

use crate::world::{WorldProvider, WorldTransition};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum TransitionError {
    #[error("provider returned an out-of-domain transition")]
    OutOfDomain,
    #[error("transition support must be positive")]
    NonPositiveSupport,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompiledTransitions {
    pub provider_id: String,
    pub edges: Vec<WorldTransition>,
}

impl CompiledTransitions {
    pub fn outgoing(&self, source: i64, action: i64) -> Vec<WorldTransition> {
        self.edges
            .iter()
            .copied()
            .filter(|edge| edge.source == source && edge.action == action)
            .collect()
    }
}

pub struct TransitionCompiler;

impl TransitionCompiler {
    pub fn compile(provider: &dyn WorldProvider) -> Result<CompiledTransitions, TransitionError> {
        let states = provider.states();
        let actions = provider.actions();
        let mut edges = Vec::new();
        let mut sorted_states = states.clone();
        sorted_states.sort_unstable();
        let mut sorted_actions = actions.clone();
        sorted_actions.sort_unstable();
        for state in sorted_states {
            for action in &sorted_actions {
                for edge in provider.transitions(state, *action) {
                    if edge.source != state
                        || edge.action != *action
                        || !states.contains(&edge.target)
                    {
                        return Err(TransitionError::OutOfDomain);
                    }
                    if edge.support < 1 {
                        return Err(TransitionError::NonPositiveSupport);
                    }
                    edges.push(edge);
                }
            }
        }
        edges.sort_by(|left, right| {
            right
                .support
                .cmp(&left.support)
                .then(left.source.cmp(&right.source))
                .then(left.action.cmp(&right.action))
                .then(left.target.cmp(&right.target))
        });
        Ok(CompiledTransitions {
            provider_id: provider.provider_id().to_string(),
            edges,
        })
    }
}
