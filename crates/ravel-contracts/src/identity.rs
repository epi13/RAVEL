//! Content identities used by checkpoints, ledgers, and memory records.

use crate::canonical::{CanonicalError, canonical_to_vec};
use serde_json::Value;
use sha2::{Digest, Sha256};

pub fn hex_sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    let mut out = String::with_capacity(digest.len() * 2);
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for byte in digest {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

pub fn prefixed_sha256(bytes: &[u8]) -> String {
    format!("sha256:{}", hex_sha256(bytes))
}

pub fn digest_bytes(bytes: &[u8]) -> String {
    hex_sha256(bytes)
}

pub fn digest_canonical(value: &Value) -> Result<String, CanonicalError> {
    Ok(prefixed_sha256(&canonical_to_vec(value)?))
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn empty_digest_matches_known_sha256() {
        assert_eq!(
            hex_sha256(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }
}
