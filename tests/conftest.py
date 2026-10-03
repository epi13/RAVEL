"""Pytest session defaults for the RAVEL suite.

The persistent plan cache is disabled unless a test opts in explicitly:
mock-based planning tests must exercise the provider path they patch,
never a real cache entry from an earlier test or a developer machine.
"""

from __future__ import annotations

import os

os.environ.setdefault("RAVEL_PLAN_CACHE", "off")
