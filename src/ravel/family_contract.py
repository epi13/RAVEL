"""Adapters to the canonical MNCS-Commons family transport contracts."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


def _commons_module() -> ModuleType:
    configured = os.environ.get("MNCS_COMMONS_ROOT")
    candidates = [Path(configured)] if configured else []
    candidates.append(Path(__file__).resolve().parents[3] / "MNCS-Commons")
    for root in candidates:
        source = root / "src"
        module_path = source / "mncs_commons" / "verification_plan.py"
        if module_path.is_file():
            name = "_mncs_commons_verification_plan_canonical"
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


def plan_identity(value: Mapping[str, Any]) -> str:
    return _commons_module().plan_identity(value)


def contract_vocab() -> tuple[tuple[str, ...], set[str]]:
    module = _commons_module()
    return tuple(module.VERIFICATION_LEVELS), set(module.ESCALATION_REASONS)


def validate_plan(value: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return _commons_module().validate_plan(value, **kwargs)
    except ValueError:
        raise
    except RuntimeError:
        raise


def load_family_graph(path: Path) -> dict[str, Any]:
    return _commons_module_from_graph().load_graph(path)


def _commons_module_from_graph() -> ModuleType:
    verification_module = _commons_module()
    module_path = Path(verification_module.__file__).with_name("family_graph.py")
    name = "_mncs_commons_family_graph_canonical"
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


def consumers_for(
    graph: Mapping[str, Any], *, producer_repository: str, contract_identity: str | None = None
) -> list[dict[str, Any]]:
    return _commons_module_from_graph().consumers_for(
        graph,
        producer_repository=producer_repository,
        contract_identity=contract_identity,
    )
