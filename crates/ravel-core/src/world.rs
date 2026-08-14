//! Bounded world-provider surface for RAVEL development fixtures.

use ravel_contracts::schema::{TOY_BRANCHING_PROVIDER, TOY_RING_PROVIDER};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct WorldTransition {
    pub source: i64,
    pub action: i64,
    pub target: i64,
    pub support: i64,
}

pub trait WorldProvider {
    fn provider_id(&self) -> &'static str;
    fn states(&self) -> Vec<i64>;
    fn actions(&self) -> Vec<i64>;
    fn observe(&self, state: i64) -> Option<Vec<i64>>;
    fn transitions(&self, state: i64, action: i64) -> Vec<WorldTransition>;
}

#[derive(Debug, Default, Clone, Copy)]
pub struct ToyBranchingWorld;

impl WorldProvider for ToyBranchingWorld {
    fn provider_id(&self) -> &'static str {
        TOY_BRANCHING_PROVIDER
    }

    fn states(&self) -> Vec<i64> {
        vec![0, 1, 2, 3]
    }

    fn actions(&self) -> Vec<i64> {
        vec![0, 1, 2]
    }

    fn observe(&self, state: i64) -> Option<Vec<i64>> {
        match state {
            0 => Some(vec![0, 0]),
            1 => Some(vec![1, 0]),
            2 => Some(vec![2, 0]),
            3 => Some(vec![3, 0]),
            _ => None,
        }
    }

    fn transitions(&self, state: i64, action: i64) -> Vec<WorldTransition> {
        match (state, action) {
            (0, 0) => vec![
                WorldTransition {
                    source: 0,
                    action: 0,
                    target: 2,
                    support: 2,
                },
                WorldTransition {
                    source: 0,
                    action: 0,
                    target: 1,
                    support: 1,
                },
            ],
            (1, 1) => vec![WorldTransition {
                source: 1,
                action: 1,
                target: 3,
                support: 2,
            }],
            (2, 2) => vec![WorldTransition {
                source: 2,
                action: 2,
                target: 2,
                support: 2,
            }],
            _ => Vec::new(),
        }
    }
}

#[derive(Debug, Default, Clone, Copy)]
pub struct ToyRingWorld;

impl WorldProvider for ToyRingWorld {
    fn provider_id(&self) -> &'static str {
        TOY_RING_PROVIDER
    }

    fn states(&self) -> Vec<i64> {
        vec![0, 1, 2, 3, 4]
    }

    fn actions(&self) -> Vec<i64> {
        vec![0, 1]
    }

    fn observe(&self, state: i64) -> Option<Vec<i64>> {
        match state {
            0 => Some(vec![0, 1]),
            1 => Some(vec![1, 1]),
            2 => Some(vec![2, 1]),
            3 => Some(vec![3, 1]),
            4 => Some(vec![4, 1]),
            _ => None,
        }
    }

    fn transitions(&self, state: i64, action: i64) -> Vec<WorldTransition> {
        if self.observe(state).is_none() || !self.actions().contains(&action) {
            return Vec::new();
        }
        let target = (state + if action == 0 { 1 } else { 2 }).rem_euclid(5);
        vec![WorldTransition {
            source: state,
            action,
            target,
            support: 1,
        }]
    }
}

pub fn provider_by_id(provider_id: &str) -> Option<Box<dyn WorldProvider>> {
    match provider_id {
        TOY_BRANCHING_PROVIDER | "branching" => Some(Box::new(ToyBranchingWorld)),
        TOY_RING_PROVIDER | "ring" => Some(Box::new(ToyRingWorld)),
        _ => None,
    }
}
