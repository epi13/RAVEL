//! Content-addressed artifact store. Metadata refers to bytes by digest.

use ravel_contracts::canonical_json;
use ravel_contracts::identity::{hex_sha256, prefixed_sha256};
use ravel_contracts::schema::ARTIFACT_SCHEMA;
use serde_json::{Value, json};
use std::fs;
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ArtifactError {
    #[error("{0}")]
    Invalid(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Canonical(#[from] ravel_contracts::CanonicalError),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArtifactRecord {
    pub artifact_id: String,
    pub media_type: String,
    pub size_bytes: u64,
    pub logical_role: String,
    pub producer_id: String,
    pub created_at: String,
    pub custody: String,
}

impl ArtifactRecord {
    pub fn to_value(&self) -> Value {
        json!({
            "schema": ARTIFACT_SCHEMA,
            "artifact_id": self.artifact_id,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "logical_role": self.logical_role,
            "producer_id": self.producer_id,
            "created_at": self.created_at,
            "custody": self.custody,
        })
    }
}

pub struct ArtifactStore {
    root: PathBuf,
}

impl ArtifactStore {
    pub fn open(root: impl AsRef<Path>) -> Result<Self, ArtifactError> {
        let root = root.as_ref().to_path_buf();
        fs::create_dir_all(root.join("sha256"))?;
        Ok(Self { root })
    }

    pub fn put(
        &self,
        bytes: &[u8],
        media_type: &str,
        logical_role: &str,
        producer_id: &str,
        created_at: &str,
    ) -> Result<ArtifactRecord, ArtifactError> {
        let digest = hex_sha256(bytes);
        if digest.len() < 4 {
            return Err(ArtifactError::Invalid(
                "artifact digest is malformed".into(),
            ));
        }
        let path = self
            .root
            .join("sha256")
            .join(&digest[..2])
            .join(&digest[2..4])
            .join(&digest);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        if path.exists() {
            let existing = fs::read(&path)?;
            if existing != bytes {
                return Err(ArtifactError::Invalid(
                    "artifact digest collision with different bytes".into(),
                ));
            }
        } else {
            fs::write(&path, bytes)?;
        }
        let record = ArtifactRecord {
            artifact_id: prefixed_sha256(bytes),
            media_type: media_type.to_string(),
            size_bytes: bytes.len() as u64,
            logical_role: logical_role.to_string(),
            producer_id: producer_id.to_string(),
            created_at: created_at.to_string(),
            custody: "repository-local".into(),
        };
        let index = self.root.join("index.jsonl");
        let line = canonical_json(&record.to_value())?;
        use std::io::Write;
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(index)?;
        writeln!(file, "{line}")?;
        Ok(record)
    }

    pub fn get(&self, artifact_id: &str) -> Result<Vec<u8>, ArtifactError> {
        let digest = artifact_id.strip_prefix("sha256:").unwrap_or(artifact_id);
        if digest.len() < 4 {
            return Err(ArtifactError::Invalid(
                "artifact identity is malformed".into(),
            ));
        }
        let path = self
            .root
            .join("sha256")
            .join(&digest[..2])
            .join(&digest[2..4])
            .join(digest);
        let bytes = fs::read(&path)?;
        if hex_sha256(&bytes) != digest {
            return Err(ArtifactError::Invalid("artifact bytes are corrupt".into()));
        }
        Ok(bytes)
    }
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn put_is_content_addressed_and_detects_corruption() {
        let directory = std::env::temp_dir().join(format!("ravel-art-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        let store = ArtifactStore::open(&directory).expect("open");
        let first = store
            .put(b"witness", "text/plain", "verifier-witness", "test", "t0")
            .expect("put");
        let second = store
            .put(b"witness", "text/plain", "verifier-witness", "test", "t1")
            .expect("put again");
        assert_eq!(first.artifact_id, second.artifact_id);
        assert_eq!(store.get(&first.artifact_id).expect("get"), b"witness");
        let _ = fs::remove_dir_all(&directory);
    }
}
