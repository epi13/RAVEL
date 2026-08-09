from __future__ import annotations

import unittest
from pathlib import Path
import sys

from ravel.mncs_receipts import build_validated_receipt
from ravel.providers import RawEvidence


RAW = RawEvidence(
    "ravel-receipt-request",
    "forge-provider",
    "UNKNOWN",
    {"operation": "inspect"},
    None,
    ("sha256:" + "b" * 64,),
    "local-forge",
    {},
)


class MncsReceiptTests(unittest.TestCase):
    def test_delegated_receipt_validation_is_not_authority(self) -> None:
        observed = {}

        def builder(record):
            observed.update(record)
            return {"schema_version": "0.1-experimental", "receipt_identity": "sha256:receipt"}

        class Report:
            valid = True
            issues = []

        result = build_validated_receipt(
            RAW,
            builder=builder,
            validator=lambda value, target: Report(),
        )
        self.assertEqual(result.validation_status, "PASS")
        self.assertEqual(result.reason_code, "mncs_receipt_structurally_valid")
        self.assertEqual(observed["candidate_identity"], "sha256:" + "b" * 64)
        self.assertIn("not assurance", result.limitations[0])

    def test_missing_optional_receipt_builder_is_unknown(self) -> None:
        result = build_validated_receipt(RAW, builder=lambda record: (_ for _ in ()).throw(RuntimeError()))
        self.assertEqual(result.validation_status, "UNKNOWN")
        self.assertEqual(result.reason_code, "mncs_receipt_builder_failed")

    def test_local_mncs_builder_and_validator_when_available(self) -> None:
        root = Path(__file__).resolve().parents[2]
        fabric_src = root / "mncs-fabric/src"
        mncs_src = root / "machine-native-complexity-standard/src"
        if not (fabric_src.is_dir() and mncs_src.is_dir()):
            self.skipTest("local MNCS sibling sources unavailable")
        sys.path.insert(0, str(fabric_src))
        sys.path.insert(0, str(mncs_src))
        try:
            from mncs_fabric.receipts import build_execution_receipt
            from mncs_validator.execution_receipt import validate_execution_receipt_value
        except ImportError:
            self.skipTest("local MNCS receipt packages unavailable")
        result = build_validated_receipt(
            RAW,
            builder=build_execution_receipt,
            validator=validate_execution_receipt_value,
        )
        self.assertEqual(result.validation_status, "PASS")
        self.assertEqual(result.reason_code, "mncs_receipt_structurally_valid")


if __name__ == "__main__":
    unittest.main()
