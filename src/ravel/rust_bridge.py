"""Optional subprocess bridge to the Rust foundation CLI.

Rust is the canonical future implementation. This module does not re-derive
authority; it asks ``ravel-rs`` the same interchange question the Python
surfaces already answer and compares discrete results.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
INTERCHANGE_SCHEMA = "ravel-interchange/0.1"
FOUNDATION_CONTRACT = "ravel-rust-foundation/0.1"


class RustFoundationUnavailable(RuntimeError):
    """Raised when the Rust CLI cannot be built or executed."""


def _cargo() -> str:
    cargo = shutil.which("cargo")
    if cargo is None:
        raise RustFoundationUnavailable("cargo is not available")
    return cargo


def rust_binary() -> Path:
    """Build ``ravel-rs`` if needed and return its path."""

    target = ROOT / "target" / "debug" / "ravel-rs"
    command = [_cargo(), "build", "-q", "-p", "ravel-cli"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "RAVEL_ROOT": str(ROOT)},
    )
    if result.returncode != 0 or not target.is_file():
        detail = (result.stderr or result.stdout)[-2000:]
        raise RustFoundationUnavailable(detail or "ravel-rs build failed")
    return target


def interchange(surface: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Send one versioned interchange envelope to the Rust CLI."""

    envelope = {
        "schema": INTERCHANGE_SCHEMA,
        "surface": surface,
        "input": dict(payload or {}),
    }
    result = subprocess.run(
        [str(rust_binary()), "interchange"],
        cwd=ROOT,
        input=json.dumps(envelope, sort_keys=True, separators=(",", ":")),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "RAVEL_ROOT": str(ROOT)},
    )
    if result.returncode != 0:
        raise RustFoundationUnavailable(result.stdout or result.stderr or "ravel-rs failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RustFoundationUnavailable("ravel-rs did not emit JSON") from error
    if not isinstance(value, dict):
        raise RustFoundationUnavailable("ravel-rs emitted a non-object")
    return value


def identity() -> dict[str, Any]:
    result = subprocess.run(
        [str(rust_binary()), "identity"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "RAVEL_ROOT": str(ROOT)},
    )
    if result.returncode != 0:
        raise RustFoundationUnavailable(result.stdout or result.stderr or "identity failed")
    return json.loads(result.stdout)
