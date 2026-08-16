"""Bounded long-running RAVEL consumer for the persistent MNCS Fabric service."""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .fabric import FabricError, _identity
from .fabric_persistent import (
    FabricPersistentBackend,
    FabricPersistentConfig,
    FabricPersistentSubmission,
)

AGENT_SCHEMA = "ravel-fabric-agent-state/0.1"
TERMINAL_STATES = {"COMPLETED", "COMPLETE", "DONE", "FAILED", "CANCELLED", "CANCELED"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _state_root() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def _execution_state(status: Mapping[str, Any]) -> str:
    for key in ("state", "status", "outcome"):
        value = status.get(key)
        if isinstance(value, str) and value:
            return value.upper()
    result = status.get("result")
    if isinstance(result, Mapping):
        return _execution_state(result)
    return "UNKNOWN"


@dataclass(slots=True)
class FabricAgent:
    backend: FabricPersistentBackend
    workspace: Path
    replication_count: int = 1
    report_root: Path = field(init=False)
    heartbeat_path: Path = field(init=False)

    def __post_init__(self) -> None:
        if self.replication_count < 1:
            raise FabricError("agent replication_count must be at least one")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.report_root = self.workspace / "fabric-reports"
        self.report_root.mkdir(parents=True, exist_ok=True)
        self.heartbeat_path = self.workspace / "agent-heartbeat.json"

    def _report_path(self, work_id: str) -> Path:
        digest = _identity({"fabric_work_id": work_id})[7:]
        return self.report_root / f"{digest}.json"

    def _bootstrap(self) -> list[dict[str, Any]]:
        existing = {submission.provider_identity for submission in self.backend.submissions()}
        created: list[dict[str, Any]] = []
        for provider in ("branching", "ring"):
            if provider in existing:
                continue
            submission = self.backend.submit_provider_parity(
                provider,
                replication_count=self.replication_count,
            )
            created.append(
                {
                    "provider": provider,
                    "work_id": submission.work_id,
                    "state": submission.accepted_state,
                }
            )
        return created

    def _observe_submission(self, submission: FabricPersistentSubmission) -> dict[str, Any]:
        status = dict(self.backend.execution_status(submission))
        state = _execution_state(status)
        observation: dict[str, Any] = {
            "work_id": submission.work_id,
            "provider": submission.provider_identity,
            "state": state,
            "report_written": False,
        }
        report_path = self._report_path(submission.work_id)
        if state in TERMINAL_STATES and not report_path.exists():
            try:
                report = self.backend.collect_submission(submission)
            except Exception as error:  # noqa: BLE001
                observation["collection"] = "UNKNOWN"
                observation["collection_reason"] = type(error).__name__
            else:
                _atomic_json(
                    report_path,
                    {
                        "schema": "ravel-fabric-agent-report/0.1",
                        "collected_at": _utc_now(),
                        "fabric_work_id": submission.work_id,
                        "report": report.to_dict(),
                        "authority": "development-only",
                        "semantics": "retained Fabric evidence reference; not evaluator authority",
                    },
                )
                observation["report_written"] = True
                observation["fabric_status"] = report.fabric_status
        elif report_path.exists():
            observation["report_written"] = True
        return observation

    def tick(self, *, bootstrap: bool = False) -> dict[str, Any]:
        health = dict(self.backend.health())
        created: list[dict[str, Any]] = []
        if bootstrap and health.get("eligible_workers"):
            created = self._bootstrap()
        submissions = [self._observe_submission(item) for item in self.backend.submissions()]
        state = {
            "schema": AGENT_SCHEMA,
            "observed_at": _utc_now(),
            "health": health,
            "bootstrap_submissions": created,
            "submissions": submissions,
            "authority": "consumer-only",
            "semantics": (
                "RAVEL watches only its own detached Fabric development work; "
                "it does not own fleet state or infer evaluator authority"
            ),
        }
        _atomic_json(self.heartbeat_path, state)
        return state

    def run(self, *, interval_seconds: float, bootstrap: bool = False, once: bool = False) -> int:
        if interval_seconds < 1 or interval_seconds > 3600:
            raise FabricError("agent interval must be within [1, 3600] seconds")
        stopping = False

        def stop(_signum: int, _frame: object) -> None:
            nonlocal stopping
            stopping = True

        prior_int = signal.signal(signal.SIGINT, stop)
        prior_term = signal.signal(signal.SIGTERM, stop)
        try:
            first = True
            while not stopping:
                state = self.tick(bootstrap=bootstrap and first)
                print(json.dumps(state, sort_keys=True), flush=True)
                first = False
                if once:
                    break
                deadline = time.monotonic() + interval_seconds
                while not stopping and time.monotonic() < deadline:
                    time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
        finally:
            signal.signal(signal.SIGINT, prior_int)
            signal.signal(signal.SIGTERM, prior_term)
            self.backend.close()
        return 0


def _config(path: str | None) -> FabricPersistentConfig:
    return FabricPersistentConfig.load(path) if path else FabricPersistentConfig.default()


def _backend(args: argparse.Namespace) -> FabricPersistentBackend:
    workspace = Path(args.workspace).expanduser().resolve()
    return FabricPersistentBackend(workspace, _config(args.config))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get("RAVEL_FABRIC_CONFIG"),
        help="persistent Fabric TOML; defaults to the standard per-user controller socket",
    )
    parser.add_argument(
        "--workspace",
        default=str(_state_root() / "ravel" / "fabric-live"),
        help="RAVEL-owned local state directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check the public persistent-controller boundary")
    run = subparsers.add_parser("run", help="watch RAVEL's detached Fabric work")
    run.add_argument("--bootstrap", action="store_true", help="submit one branching and one ring development probe if absent")
    run.add_argument("--once", action="store_true", help="perform one bounded agent tick and exit")
    run.add_argument("--interval", type=float, default=30.0, help="poll interval in seconds (1..3600)")
    run.add_argument("--replicas", type=int, default=1, help="bootstrap replica count")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backend = _backend(args)
    try:
        if args.command == "doctor":
            health = dict(backend.health())
            print(json.dumps(health, sort_keys=True, indent=2))
            return 0 if health.get("outcome") == "PASS" else 2
        agent = FabricAgent(backend, Path(args.workspace).expanduser().resolve(), args.replicas)
        return agent.run(interval_seconds=args.interval, bootstrap=args.bootstrap, once=args.once)
    except (FabricError, OSError) as error:
        print(json.dumps({"outcome": "UNKNOWN", "reason": type(error).__name__, "detail": str(error)}))
        backend.close()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
