#!/usr/bin/env python3
"""Run the bounded local Fabric reference matrix for RAVEL development."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ravel.fabric import FabricError, FabricLocalBackend, _aggregate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("build/fabric-reference"),
        help="temporary workspace for generated artifacts and Fabric records",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args()
    backend = FabricLocalBackend(args.workspace)
    if not backend.available:
        report = {
            "schema": "ravel-fabric-reference-run/0.1",
            "status": "UNKNOWN",
            "authority": "development-only",
            "reason": "Fabric capability unavailable",
            "detail": backend.unavailable_reason,
        }
        print(json.dumps(report, sort_keys=True))
        return 0

    reports = []
    run_workspace = Path(tempfile.mkdtemp(prefix="run-", dir=args.workspace))
    try:
        backend = FabricLocalBackend(run_workspace)
        for provider in ("branching", "ring"):
            try:
                reports.append(backend.execute_provider_parity(provider).to_dict())
            except FabricError as error:
                reports.append({"provider": provider, "status": "UNKNOWN", "reason": str(error)})
    finally:
        shutil.rmtree(run_workspace, ignore_errors=True)
    status = _aggregate(
        [str(report.get("fabric_status", report.get("status", "UNKNOWN"))) for report in reports]
    )
    report = {
        "schema": "ravel-fabric-reference-run/0.1",
        "backend_identity": backend.backend_identity,
        "status": status,
        "authority": "development-only",
        "semantics": "Fabric observations are diagnostic evidence, not evaluator authority",
        "providers": reports,
        "selection_material": "not-dispatched",
        "final_material": "not-dispatched",
    }
    print(json.dumps(report, sort_keys=True, indent=2 if args.json else None))
    return 0 if status in {"PASS", "UNKNOWN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
