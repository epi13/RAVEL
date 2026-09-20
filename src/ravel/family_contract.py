"""Adapters to the canonical MNCS-Commons family transport contracts."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


def _module_name(prefix: str, module_path: Path) -> str:
    """Keep independently selected Commons checkouts isolated in one process."""

    identity = hashlib.sha256(str(module_path.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{identity}"


def _commons_module(*, commons_root: Path | None = None) -> ModuleType:
    if commons_root is not None:
        candidates = [Path(commons_root)]
    else:
        configured = os.environ.get("MNCS_COMMONS_ROOT")
        candidates = [Path(configured)] if configured else []
        candidates.append(Path(__file__).resolve().parents[3] / "MNCS-Commons")
    for root in candidates:
        source = root / "src"
        module_path = source / "mncs_commons" / "verification_plan.py"
        if module_path.is_file():
            name = _module_name("_mncs_commons_verification_plan_canonical", module_path)
            existing = sys.modules.get(name)
            if existing is not None:
                return existing
            spec = importlib.util.spec_from_file_location(name, module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"cannot load canonical verification-plan module: {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
    raise RuntimeError(
        "the canonical MNCS-Commons verification-plan contract is unavailable; "
        "set MNCS_COMMONS_ROOT to a checked-out Commons repository"
    )


def plan_identity(value: Mapping[str, Any], *, commons_root: Path | None = None) -> str:
    return _commons_module(commons_root=commons_root).plan_identity(value)


def contract_vocab(*, commons_root: Path | None = None) -> tuple[tuple[str, ...], set[str]]:
    module = _commons_module(commons_root=commons_root)
    return tuple(module.VERIFICATION_LEVELS), set(module.ESCALATION_REASONS)


def validate_plan(
    value: Any, *, commons_root: Path | None = None, **kwargs: Any
) -> dict[str, Any]:
    try:
        return _commons_module(commons_root=commons_root).validate_plan(value, **kwargs)
    except ValueError:
        raise
    except RuntimeError:
        raise


def load_family_graph(path: Path, *, commons_root: Path | None = None) -> dict[str, Any]:
    return _commons_module_from_graph(commons_root=commons_root).load_graph(path)


def default_family_graph_path(*, commons_root: Path | None = None) -> Path | None:
    """Locate the checked-in Commons graph without regenerating it."""

    if commons_root is not None:
        candidate = Path(commons_root) / "family" / "semantic-edges-v1.json"
        return candidate if candidate.is_file() else None
    configured = os.environ.get("MNCS_FAMILY_GRAPH_PATH")
    candidates = [Path(configured)] if configured else []
    configured_root = os.environ.get("MNCS_COMMONS_ROOT")
    if configured_root:
        candidates.append(Path(configured_root) / "family" / "semantic-edges-v1.json")
    candidates.append(
        Path(__file__).resolve().parents[3]
        / "MNCS-Commons"
        / "family"
        / "semantic-edges-v1.json"
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _commons_module_from_graph(*, commons_root: Path | None = None) -> ModuleType:
    verification_module = _commons_module(commons_root=commons_root)
    module_path = Path(verification_module.__file__).with_name("family_graph.py")
    name = _module_name("_mncs_commons_family_graph_canonical", module_path)
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical family-graph module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _commons_obligation_module(*, commons_root: Path | None = None) -> ModuleType:
    verification_module = _commons_module(commons_root=commons_root)
    module_path = Path(verification_module.__file__).with_name("obligation_plan.py")
    name = _module_name("_mncs_commons_obligation_plan_canonical", module_path)
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    if not module_path.is_file():
        raise RuntimeError(f"canonical MNCS-Commons obligation-plan contract is unavailable: {module_path}")
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical obligation-plan module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_obligation_inventory(
    value: Any, *, commons_root: Path | None = None, repository: str | None = None
) -> dict[str, Any]:
    return _commons_obligation_module(commons_root=commons_root).validate_inventory(
        value, repository=repository
    )


def obligation_inventory_identity(value: Mapping[str, Any], *, commons_root: Path | None = None) -> str:
    return _commons_obligation_module(commons_root=commons_root).inventory_identity(value)


def obligation_plan_identity(value: Mapping[str, Any], *, commons_root: Path | None = None) -> str:
    return _commons_obligation_module(commons_root=commons_root).obligation_plan_identity(value)


def validate_obligation_plan(value: Any, *, commons_root: Path | None = None) -> dict[str, Any]:
    return _commons_obligation_module(commons_root=commons_root).validate_obligation_plan(value)


def consumers_for(
    graph: Mapping[str, Any],
    *,
    producer_repository: str,
    contract_identity: str | None = None,
    commons_root: Path | None = None,
) -> list[dict[str, Any]]:
    return _commons_module_from_graph(commons_root=commons_root).consumers_for(
        graph,
        producer_repository=producer_repository,
        contract_identity=contract_identity,
    )
