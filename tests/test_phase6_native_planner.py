from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_ROOT = Path("/home/epi13/Documents/Projects/mncs-language")
COMMONS_ROOT = Path("/home/epi13/Documents/Projects/MNCS-Commons")


def runtime() -> Path:
    configured = os.environ.get("MNCS_BINARY")
    if configured:
        return Path(configured)
    return LANGUAGE_ROOT / "target" / "debug" / "mncs"


def run_native(request: dict[str, object]) -> dict[str, object]:
    binary = runtime()
    if not binary.is_file():
        raise unittest.SkipTest(f"MNCS runtime is not built: {binary}")
    with tempfile.TemporaryDirectory(prefix="ravel-phase6-", dir=ROOT) as directory:
        work = Path(directory)
        request_path = work / "request.json"
        decision_path = work / "decision.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        command = [
            str(binary),
            "run-app",
            str(ROOT / "native-applications" / "ravel-planner.json"),
            "--library",
            str(LANGUAGE_ROOT / "library"),
            "--library",
            str(COMMONS_ROOT / "src" / "mncs_commons" / "mesh"),
            "--grant-structured",
            "ravel_artifact",
            "--",
            request_path.relative_to(ROOT).as_posix(),
            decision_path.relative_to(ROOT).as_posix(),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        return json.loads(decision_path.read_text(encoding="utf-8"))


def request_with_ids(ids: list[str]) -> dict[str, object]:
    base = json.loads(
        (ROOT / "examples" / "native-planner" / "request.json").read_text(
            encoding="utf-8"
        )
    )
    base["impact"]["test_identities"] = ids
    base["inventory"]["test_case_identities"] = ids
    return base


class Phase6NativePlannerTests(unittest.TestCase):
    def test_native_selection_materializes_more_than_eight_ids(self) -> None:
        ids = [f"mncs:test-case:phase6:{index:02d}" for index in range(9)]
        decision = run_native(request_with_ids(ids))
        self.assertTrue(decision["inventory_join_complete"])
        self.assertEqual(decision["joinable_test_count"], 9)
        self.assertEqual(decision["selected_test_identities"], ids)

    def test_native_selection_rejects_duplicate_ids_fail_closed(self) -> None:
        ids = ["mncs:test-case:phase6:duplicate"] * 2
        decision = run_native(request_with_ids(ids))
        self.assertFalse(decision["inventory_join_complete"])
        self.assertEqual(decision["selected_test_identities"], [])

    def test_native_selection_rejects_missing_inventory_join_fail_closed(self) -> None:
        impact_ids = ["mncs:test-case:phase6:present", "mncs:test-case:phase6:missing"]
        request = request_with_ids(impact_ids)
        request["inventory"]["test_case_identities"] = [impact_ids[0]]
        decision = run_native(request)
        self.assertFalse(decision["inventory_join_complete"])
        self.assertEqual(decision["selected_test_identities"], [])


if __name__ == "__main__":
    unittest.main()
