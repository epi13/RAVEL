//! Locate the standalone RAVEL repository without assuming process cwd.

use std::env;
use std::path::{Path, PathBuf};

const MARKERS: [&str; 3] = [
    "ravel_versions/0.6/ravel-0.6-preregistration.json",
    "Cargo.toml",
    "src/ravel/policy.py",
];

pub fn discover_repository_root() -> Option<PathBuf> {
    if let Ok(explicit) = env::var("RAVEL_ROOT") {
        let path = PathBuf::from(explicit);
        if is_repository(&path) {
            return Some(path);
        }
    }
    let mut current = env::current_dir().ok()?;
    loop {
        if is_repository(&current) {
            return Some(current);
        }
        if !current.pop() {
            break;
        }
    }
    None
}

fn is_repository(path: &Path) -> bool {
    MARKERS.iter().all(|marker| path.join(marker).is_file())
}
