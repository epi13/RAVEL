//! Deterministic JSON codec matching Python `json.dumps(..., sort_keys=True,
//! separators=(",", ":"), ensure_ascii=False)`.

use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum CanonicalError {
    #[error("value cannot be represented as canonical JSON")]
    Unrepresentable,
}

/// Serialize a JSON value with sorted object keys and compact separators.
pub fn canonical_json(value: &Value) -> Result<String, CanonicalError> {
    let mut out = String::new();
    write_canonical(value, &mut out)?;
    Ok(out)
}

/// Canonical UTF-8 bytes for hashing and append-only records.
pub fn canonical_to_vec(value: &Value) -> Result<Vec<u8>, CanonicalError> {
    Ok(canonical_json(value)?.into_bytes())
}

fn write_canonical(value: &Value, out: &mut String) -> Result<(), CanonicalError> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => {
            if number.as_f64().is_some_and(|item| !item.is_finite()) {
                return Err(CanonicalError::Unrepresentable);
            }
            out.push_str(&number.to_string());
        }
        Value::String(text) => {
            let encoded =
                serde_json::to_string(text).map_err(|_| CanonicalError::Unrepresentable)?;
            out.push_str(&encoded);
        }
        Value::Array(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_canonical(item, out)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            out.push('{');
            for (index, key) in keys.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                let encoded =
                    serde_json::to_string(*key).map_err(|_| CanonicalError::Unrepresentable)?;
                out.push_str(&encoded);
                out.push(':');
                write_canonical(&map[*key], out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn sorts_keys_and_compacts() {
        let value = json!({"b": 1, "a": {"z": true, "m": [2, 3]}});
        assert_eq!(
            canonical_json(&value).expect("canonical"),
            r#"{"a":{"m":[2,3],"z":true},"b":1}"#
        );
    }
}
