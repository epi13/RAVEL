#!/usr/bin/env python3
"""Run the preserved 0.4 digest utility against its relocated case root."""

from __future__ import annotations

import sys
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = CASE_ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

import ravel_source_digest as digest  # noqa: E402
from path_compat import build_manifest as compat_build_manifest  # noqa: E402

digest.CASE_ROOT = CASE_ROOT
digest.build_manifest = lambda spec_path: compat_build_manifest(
    spec_path, CASE_ROOT, REPOSITORY_ROOT, digest
)

raise SystemExit(digest.main())
