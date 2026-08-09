#!/usr/bin/env python3
"""Small bounded commands declared by the project-local Forge configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _run(module: str, *tests: str) -> tuple[str, str]:
    result = subprocess.run(
        ["python3", "-m", "unittest", *tests],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return ("PASS" if result.returncode == 0 else "FAIL", result.stderr[-2000:])


def _build(provider: str, root: Path) -> dict[str, object]:
    env = dict(os.environ)
    env["RAVEL06_PROVIDER"] = provider
    result = subprocess.run(
        ["python3", "tools/ravel_0_6_build.py", "build", "--output-dir", str(root)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return json.loads(result.stdout)


def _trial(binary: Path) -> bytes:
    result = subprocess.run(
        [str(binary), "--trial", "decomposition", "--regime", "separated_state", "--seed", "0x1234"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def check(name: str) -> tuple[str, str]:
    if name == "frozen-identities":
        return _run(name, "tests/test_frozen_identities.py", "tests/test_policy.py")
    if name == "policy":
        return _run(name, "tests/test_policy.py")
    if name == "behavior":
        return _run(name, "tests/test_ravel_0_6_decomposition.py")
    if name == "transactions":
        return _run(name, "tests/test_ravel_0_6_transaction.py")
    if name == "negative-matrix":
        return _run(name, "tests/test_ravel_0_6_negative_matrix.py")
    if name == "component-parity":
        return _run(name, "tests/test_ravel_0_6_decomposition.py", "tests/test_components.py")
    if name == "development-evaluator":
        return _run(name, "tests/test_ravel_0_6_transaction.py")
    if name == "build":
        with tempfile.TemporaryDirectory(prefix="ravel-forge-build-") as directory:
            _build("branching", Path(directory))
        return "PASS", "unity and separately compiled candidate build completed"
    if name == "world-provider-parity":
        with tempfile.TemporaryDirectory(prefix="ravel-forge-world-") as directory:
            base = Path(directory)
            for provider in ("branching", "ring"):
                record = _build(provider, base / provider)
                separate = _trial(base / provider / "ravel_0_6_candidate_001")
                unity = _trial(base / provider / "ravel_0_6_candidate_001.unity")
                if separate != unity or record["component_contracts"]["world"]["abi_version"] != "ravel-0.6-world-abi/1":
                    return "FAIL", f"{provider} unity/separate facts differ"
        return "PASS", "branching and ring unity/separate raw trials matched"
    if name == "package":
        return _run(name, "tests/test_frozen_identities.py", "tests/test_lifecycle_experience.py")
    if name == "live-family-compat":
        sibling = ROOT.parent / "MNCS-Commons/src"
        if not sibling.is_dir():
            return "UNKNOWN", "MNCS Commons checkout unavailable"
        import sys
        sys.path.insert(0, str(sibling))
        try:
            from mncs_commons.application.services import CompatibilityApplication
            report = CompatibilityApplication.report({"ravel": ROOT})
        except Exception as error:
            return "UNKNOWN", f"Commons compatibility adapter unavailable: {type(error).__name__}"
        statuses = {str(item.get("status")) for item in report}
        if "DRIFTED" in statuses:
            return "FAIL", json.dumps(report, sort_keys=True)
        if "UNKNOWN" in statuses or "COMPATIBLE_WITH_UNRESOLVED_FIELDS" in statuses:
            return "UNKNOWN", json.dumps(report, sort_keys=True)
        return "PASS", json.dumps(report, sort_keys=True)
    if name == "lifecycle":
        return "PASS", "RAVEL candidate remains development-only; Forge mapping is reference-only"
    raise ValueError(f"unknown Forge workflow: {name}")


def main() -> int:
    import sys
    name = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        status, detail = check(name)
    except Exception as error:
        status, detail = "FAIL", f"{type(error).__name__}: {error}"
    print(json.dumps({"status": status, "workflow": name, "detail": detail}, sort_keys=True))
    return 0 if status in {"PASS", "UNKNOWN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
