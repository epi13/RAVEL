"""Locate optional MNCS-family checkouts without requiring installation."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]

SIBLING_SOURCES = {
    "mncs-fabric": "mncs-fabric",
    "mncs_validator": "machine-native-complexity-standard",
    "mncs_commons": "MNCS-Commons",
    "mncs_forge": "mncs-forge-mcp",
}


def sibling_src(name: str) -> Path | None:
    """Return the ``src`` directory of a sibling checkout if it exists."""

    relative = SIBLING_SOURCES.get(name, name)
    candidate = ROOT.parent / relative / "src"
    return candidate if candidate.is_dir() else None


def ensure_sibling_src(*names: str) -> None:
    """Prepend sibling source trees so optional packages import locally."""

    for name in names:
        path = sibling_src(name)
        if path is not None and str(path) not in sys.path:
            sys.path.insert(0, str(path))
