//! Canonical checkpoint codec for decomposed development state.

use crate::mechanism::{ExpertState, MechanismState};
use ravel_contracts::canonical::canonical_to_vec;
use ravel_contracts::identity::prefixed_sha256;
use ravel_contracts::schema::CHECKPOINT_SCHEMA;
use serde_json::{Value, json};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum CheckpointError {
    #[error("checkpoint schema mismatch")]
    SchemaMismatch,
    #[error("checkpoint is malformed")]
    Malformed,
    #[error("checkpoint is not canonical")]
    NotCanonical,
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Mechanism(#[from] crate::mechanism::MechanismError),
}

pub struct CheckpointCodec;

impl CheckpointCodec {
    pub fn encode(&self, state: &MechanismState) -> Result<Vec<u8>, CheckpointError> {
        state.validate()?;
        let payload = json!({
            "schema": CHECKPOINT_SCHEMA,
            "state": {
                "experts": state.experts.iter().map(|expert| json!({
                    "lineage": expert.lineage,
                    "labels": expert.labels,
                    "supported_actions": expert.supported_actions,
                })).collect::<Vec<_>>(),
                "epoch": state.epoch,
                "births": state.births,
                "retirements": state.retirements,
            }
        });
        Ok(canonical_to_vec(&payload)?)
    }

    pub fn identity(&self, checkpoint: &[u8]) -> String {
        prefixed_sha256(checkpoint)
    }

    pub fn decode(&self, checkpoint: &[u8]) -> Result<MechanismState, CheckpointError> {
        let payload: Value =
            serde_json::from_slice(checkpoint).map_err(|_| CheckpointError::Malformed)?;
        if payload.get("schema").and_then(Value::as_str) != Some(CHECKPOINT_SCHEMA) {
            return Err(CheckpointError::SchemaMismatch);
        }
        let raw = payload.get("state").ok_or(CheckpointError::Malformed)?;
        let experts = raw
            .get("experts")
            .and_then(Value::as_array)
            .ok_or(CheckpointError::Malformed)?
            .iter()
            .map(|expert| {
                Ok(ExpertState {
                    lineage: expert
                        .get("lineage")
                        .and_then(Value::as_str)
                        .ok_or(CheckpointError::Malformed)?
                        .to_string(),
                    labels: int_list(expert.get("labels").ok_or(CheckpointError::Malformed)?)?,
                    supported_actions: int_list(
                        expert
                            .get("supported_actions")
                            .ok_or(CheckpointError::Malformed)?,
                    )?,
                })
            })
            .collect::<Result<Vec<_>, CheckpointError>>()?;
        let state = MechanismState {
            experts,
            epoch: required_i64(raw, "epoch")?,
            births: required_i64(raw, "births")?,
            retirements: required_i64(raw, "retirements")?,
        };
        state.validate()?;
        if self.encode(&state)? != checkpoint {
            return Err(CheckpointError::NotCanonical);
        }
        Ok(state)
    }
}

fn required_i64(value: &Value, key: &str) -> Result<i64, CheckpointError> {
    value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or(CheckpointError::Malformed)
}

fn int_list(value: &Value) -> Result<Vec<i64>, CheckpointError> {
    value
        .as_array()
        .ok_or(CheckpointError::Malformed)?
        .iter()
        .map(|item| item.as_i64().ok_or(CheckpointError::Malformed))
        .collect()
}

pub fn encode_hex_identity(checkpoint: &[u8]) -> String {
    prefixed_sha256(checkpoint)
}

pub fn canonical_checkpoint_json(state: &MechanismState) -> Result<String, CheckpointError> {
    let bytes = CheckpointCodec.encode(state)?;
    String::from_utf8(bytes).map_err(|_| CheckpointError::Malformed)
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;
    use ravel_contracts::canonical_json;

    #[test]
    fn checkpoint_round_trip_is_canonical_and_detects_corruption() {
        let state = MechanismState {
            experts: vec![ExpertState {
                lineage: "lineage-a".into(),
                labels: vec![1],
                supported_actions: vec![0],
            }],
            epoch: 2,
            births: 1,
            retirements: 0,
        };
        let codec = CheckpointCodec;
        let checkpoint = codec.encode(&state).expect("encode");
        assert_eq!(codec.decode(&checkpoint).expect("decode"), state);
        assert_eq!(
            codec
                .encode(&codec.decode(&checkpoint).expect("decode"))
                .expect("re-encode"),
            checkpoint
        );
        let mut corrupted = checkpoint.clone();
        corrupted.push(b' ');
        assert!(codec.decode(&corrupted).is_err());
        assert_eq!(
            canonical_json(&serde_json::from_slice(&checkpoint).expect("json")).expect("canon"),
            String::from_utf8(checkpoint).expect("utf8")
        );
    }
}
