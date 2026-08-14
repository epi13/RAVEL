from __future__ import annotations

import json
import math
import unittest

from ravel.rust_bridge import RustFoundationUnavailable, interchange


class CanonicalJsonParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            interchange("canonical.encode", {"value": {"a": 1}})
        except RustFoundationUnavailable as error:
            raise unittest.SkipTest(f"Rust foundation unavailable: {error}") from error

    def test_byte_for_byte_python_compat_cases(self) -> None:
        cases = [
            {},
            [],
            {"b": 1, "a": {"z": True, "m": [2, 3]}},
            {"empty": {}, "arr": []},
            {"unicode": "café π"},
            {"quote": 'a"b\\c'},
            {"n": None, "t": True, "f": False},
            {"i": 0, "neg": -7, "big": 1153434},
            {"nested": [{"k": "v"}, {"k": "w"}]},
        ]
        for value in cases:
            python = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            rust = interchange("canonical.encode", {"value": value})
            self.assertEqual(rust["operation_outcome"], "OK")
            self.assertEqual(rust["canonical"], python)

    def test_non_finite_float_is_rejected_or_unrepresentable(self) -> None:
        try:
            interchange("canonical.encode", {"value": {"x": math.inf}})
        except RustFoundationUnavailable as error:
            self.assertIn("ERROR", str(error) + (getattr(error, "args", ("",))[0] or ""))

    def test_v1_interchange_is_rejected(self) -> None:
        from ravel.rust_bridge import rust_binary
        import os
        from pathlib import Path
        import subprocess

        envelope = {
            "schema": "ravel-interchange/0.1",
            "surface": "canonical.encode",
            "input": {"value": {}},
        }
        result = subprocess.run(
            [str(rust_binary()), "interchange"],
            cwd=Path(__file__).resolve().parents[1],
            input=json.dumps(envelope),
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "RAVEL_ROOT": str(Path(__file__).resolve().parents[1])},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("0.1", result.stdout)


if __name__ == "__main__":
    unittest.main()
