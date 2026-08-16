#!/usr/bin/env python3
"""Run the persistent-controller RAVEL Fabric agent from a source checkout."""

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
main = import_module("ravel.fabric_agent").main

if __name__ == "__main__":
    raise SystemExit(main())
