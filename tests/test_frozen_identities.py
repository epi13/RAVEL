from __future__ import annotations

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


FROZEN_IDENTITIES = {
    "ravel_versions/0.4/ravel_0_4.c": "5243022245bce97b2e3be6dd46e397d33445c25469b8ce9a364c6a104e757cd4",
    "ravel_versions/0.4/ravel-0.4-source-manifest.json": "c3b590a93313c929ef667f7c41100eb51a130c5015b2b2b7789bb6bf2033d768",
    "ravel_versions/0.4/ravel-0.4-trial-evidence.json": "a5ffbfdbf2f46274413edf0644df2afa36df27da629c777bcf59b1f6e79066aa",
    "ravel_versions/0.5/ravel_0_5.c": "1a8466ea1805811873c461fb891aaeaec18f6c9e7491b5ea7bd09bf698be102d",
    "ravel_versions/0.5/ravel-0.5-source-and-execution-manifest.json": "18006006db509269ee374a39133bb25d8452edc0fe0103a43fa92c5660fd89d0",
    "ravel_versions/0.5/ravel-0.5-trial-evidence.json": "9ffefe97e5331b65e5b998f9c2d3aac91cdf9cca246a377ca421a3bef0ba0e80",
}


class FrozenIdentityTests(unittest.TestCase):
    def test_historical_source_and_evidence_identities_are_unchanged(self) -> None:
        for relative, expected in FROZEN_IDENTITIES.items():
            with self.subTest(path=relative):
                digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(digest, expected)


if __name__ == "__main__":
    unittest.main()
