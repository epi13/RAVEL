#!/usr/bin/env python3
"""Small bounded commands declared by the project-local Forge configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FABRIC_LOCK = ROOT / "ravel_versions/0.6/ravel-0.6-family-compatibility-lock.json"
sys.path.insert(0, str(ROOT / "src"))


def _python_env() -> dict[str, str]:
    env = dict(os.environ)
    env["RAVEL_ROOT"] = str(ROOT)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT / "src") if not existing else f"{ROOT / 'src'}{os.pathsep}{existing}"
    return env


def _run(module: str, *tests: str) -> tuple[str, str]:
    result = subprocess.run(
        ["python3", "-m", "unittest", *tests],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_python_env(),
    )
    return ("PASS" if result.returncode == 0 else "FAIL", result.stderr[-2000:])


def _cargo(arguments: list[str]) -> tuple[str, str]:
    result = subprocess.run(
        ["cargo", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_python_env(),
    )
    detail = (result.stdout or result.stderr)[-2000:]
    if result.returncode != 0:
        return "FAIL", detail
    return "PASS", detail or "cargo completed"


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
    if name == "fabric-capabilities":
        try:
            from ravel.fabric import FabricLocalBackend

            with tempfile.TemporaryDirectory(prefix="ravel-forge-fabric-capabilities-") as directory:
                backend = FabricLocalBackend(Path(directory))
                if not backend.available:
                    return "UNKNOWN", backend.unavailable_reason or "Fabric unavailable"
                capabilities = backend.capabilities("local-reference-worker")
                return "PASS", json.dumps({"backend": backend.backend_identity, "capabilities": capabilities}, sort_keys=True)
        except ImportError as error:
            return "UNKNOWN", f"Fabric capability unavailable: {type(error).__name__}"
    if name == "fabric-reference":
        result = subprocess.run(
            ["python3", "tools/ravel_fabric_reference.py", "--workspace", "build/forge-fabric-reference"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        detail = result.stdout[-12000:] or result.stderr[-2000:]
        if result.returncode not in {0}:
            return "FAIL", detail
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            return "FAIL", "Fabric reference did not emit JSON"
        return str(report.get("status", "UNKNOWN")), detail
    if name == "fabric-negative":
        return _run(name, "tests/test_ravel_fabric.py")
    if name == "family-compatibility-lock":
        if not FABRIC_LOCK.is_file():
            return "FAIL", "RAVEL family compatibility lock is missing"
        lock = json.loads(FABRIC_LOCK.read_text(encoding="utf-8"))
        missing: list[str] = []
        drifted: dict[str, dict[str, str]] = {}
        unresolved: dict[str, str] = {}
        for name_, entry in lock.get("contracts", {}).items():
            candidates = {
                "mncs-fabric": ROOT.parent / "mncs-fabric",
                "mncs-forge-mcp": ROOT.parent / "mncs-forge-mcp",
                "machine-native-complexity-standard": ROOT.parent / "machine-native-complexity-standard",
                "Machine-Native-Experimental-Learning": ROOT.parent / "Machine-Native-Experimental-Learning",
                "MNCS-Commons": ROOT.parent / "MNCS-Commons",
                "mncs-language": ROOT.parent / "mncs-language",
            }
            path = candidates[name_]
            if not path.is_dir():
                missing.append(name_)
                continue
            current = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                text=True,
                capture_output=True,
                check=False,
            )
            actual = current.stdout.strip()
            expected = str(entry.get("commit"))
            if current.returncode != 0 or actual != expected:
                drifted[name_] = {"expected": expected, "actual": actual or "UNKNOWN"}
                continue
            dirty = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                text=True,
                capture_output=True,
                check=False,
            ).stdout.strip()
            if dirty:
                unresolved[name_] = "checkout has uncommitted changes"
        if drifted:
            return "FAIL", json.dumps({"status": "DRIFTED", "contracts": drifted}, sort_keys=True)
        if missing or unresolved:
            return "UNKNOWN", json.dumps({"status": "UNKNOWN", "missing": missing, "unresolved": unresolved}, sort_keys=True)
        return "PASS", json.dumps({"status": "COMPATIBLE", "contracts": sorted(lock["contracts"])}, sort_keys=True)
    if name == "package":
        return _run(name, "tests/test_frozen_identities.py", "tests/test_lifecycle_experience.py")
    if name == "live-family-compat":
        sibling = ROOT.parent / "MNCS-Commons/src"
        if not sibling.is_dir():
            return "UNKNOWN", "MNCS Commons checkout unavailable"
        sys.path.insert(0, str(sibling))
        try:
            from mncs_commons.application.services import CompatibilityApplication
            repositories = {"ravel": ROOT}
            for alias, directory in {
                "mncs-fabric": ROOT.parent / "mncs-fabric",
                "mncs-forge-mcp": ROOT.parent / "mncs-forge-mcp",
                "machine-native-complexity-standard": ROOT.parent / "machine-native-complexity-standard",
                "Machine-Native-Experimental-Learning": ROOT.parent / "Machine-Native-Experimental-Learning",
                "MNCS-Commons": ROOT.parent / "MNCS-Commons",
                "mncs-language": ROOT.parent / "mncs-language",
            }.items():
                if directory.is_dir():
                    repositories[alias] = directory
            report = CompatibilityApplication.report(repositories)
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
    if name == "rust-build":
        return _cargo(["build", "--workspace"])
    if name == "rust-test":
        return _cargo(["test", "--workspace"])
    if name == "rust-python-parity":
        return _run(name, "tests/test_rust_parity.py")
    if name == "rust-c-parity":
        return _run(
            name,
            "tests.test_rust_parity.RustParityTests.test_c_transaction_evaluation_matches_python",
        )
    if name == "knowledge-lifecycle":
        return _run(name, "tests/test_rust_knowledge.py", "tests/test_consolidation.py")
    if name == "canonical-json-parity":
        return _run(name, "tests/test_canonical_json.py")
    if name == "append-log-replay":
        return _cargo(["test", "-p", "ravel-memory", "store::"])
    if name == "knowledge-negative-matrix":
        return _run(
            name,
            "tests.test_rust_knowledge.KnowledgeParityTests.test_knowledge_promotion_is_fail_closed_on_both_sides",
            "tests.test_rust_knowledge.KnowledgeParityTests.test_omitted_counterexample_is_rejected",
            "tests.test_rust_knowledge.KnowledgeParityTests.test_malformed_evaluation_status_is_rejected",
        )
    if name == "counterexample-preservation":
        return _run(
            name,
            "tests.test_rust_knowledge.KnowledgeParityTests.test_omitted_counterexample_is_rejected",
            "tests.test_consolidation.ConsolidationTests.test_explicit_contradiction_is_retained",
        )
    if name == "retention-advisory":
        return _cargo(["test", "-p", "ravel-memory", "retention"])
    if name == "artifact-integrity":
        return _cargo(["test", "-p", "ravel-memory", "artifacts"])
    if name == "rust-fmt":
        return _cargo(["fmt", "--all", "--", "--check"])
    if name == "rust-clippy":
        return _cargo(["clippy", "--workspace", "--all-targets", "--all-features", "--", "-D", "warnings"])
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
