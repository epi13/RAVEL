"""Focused tests for the persistent content-keyed plan cache."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ravel.plan_cache import (
    PlanCache,
    cache_key,
    digest_file,
    digest_tree,
    tool_digest,
)


def _material(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "ravel.plan-cache-key/1",
        "source_path": "/tmp/source.mncs",
        "source_sha256": "a" * 64,
        "roots": ["mncs:fn:changed"],
    }
    base.update(overrides)
    return base


def _plan() -> dict[str, object]:
    return {"schema_version": "mncs.verification-plan/1", "plan_id": "p" * 64}


def test_key_is_stable_for_identical_material() -> None:
    assert cache_key(_material()) == cache_key(_material())


def test_key_changes_when_any_input_changes() -> None:
    baseline = cache_key(_material())
    assert cache_key(_material(source_sha256="b" * 64)) != baseline
    assert cache_key(_material(roots=["mncs:fn:other"])) != baseline
    assert cache_key(_material(source_path="/tmp/other.mncs")) != baseline


def test_lookup_miss_then_store_then_hit(tmp_path: Path) -> None:
    cache = PlanCache(directory=tmp_path, enabled=True)
    material = _material()
    key = cache_key(material)
    assert cache.lookup(tmp_path, key, material) is None
    assert cache.misses == 1
    cache.store(tmp_path, key, material, _plan())
    assert cache.stores == 1
    assert cache.lookup(tmp_path, key, material) == _plan()
    assert cache.hits == 1


def test_lookup_rejects_material_mismatch(tmp_path: Path) -> None:
    cache = PlanCache(directory=tmp_path, enabled=True)
    material = _material()
    key = cache_key(material)
    cache.store(tmp_path, key, material, _plan())
    assert cache.lookup(tmp_path, key, _material(roots=["mncs:fn:other"])) is None
    assert cache.misses == 1


def test_lookup_rejects_corrupt_entry(tmp_path: Path) -> None:
    cache = PlanCache(directory=tmp_path, enabled=True)
    material = _material()
    key = cache_key(material)
    (tmp_path / f"{key}.json").write_text("{not json", encoding="utf-8")
    assert cache.lookup(tmp_path, key, material) is None
    assert cache.misses == 1


def test_lookup_rejects_path_escape_key(tmp_path: Path) -> None:
    cache = PlanCache(directory=tmp_path, enabled=True)
    assert cache.lookup(tmp_path, "../escape", _material()) is None
    assert cache.errors == 1


def test_store_enforces_entry_bound(tmp_path: Path) -> None:
    cache = PlanCache(directory=tmp_path, enabled=True, max_entries=2)
    keys = []
    for index in range(4):
        material = _material(source_sha256=f"{index:064d}")
        key = cache_key(material)
        keys.append(key)
        cache.store(tmp_path, key, material, _plan())
    remaining = {path.stem for path in tmp_path.glob("*.json")}
    assert len(remaining) == 2
    assert keys[-1] in remaining


def test_disabled_cache_resolves_no_directory(tmp_path: Path) -> None:
    assert PlanCache(directory=tmp_path, enabled=False).resolve(tmp_path) is None


def test_env_opt_out_disables_default_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAVEL_PLAN_CACHE", "off")
    assert PlanCache().resolve(tmp_path) is None


def test_env_cache_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAVEL_PLAN_CACHE", "on")
    monkeypatch.setenv("RAVEL_PLAN_CACHE_DIR", str(tmp_path / "custom"))
    assert PlanCache().resolve(tmp_path) == tmp_path / "custom"


def test_digest_tree_tracks_content_and_names(tmp_path: Path) -> None:
    root = tmp_path / "libs"
    (root / "a").mkdir(parents=True)
    (root / "a" / "one.mncs").write_text("one", encoding="utf-8")
    baseline = digest_tree(root)
    assert baseline is not None
    (root / "a" / "one.mncs").write_text("two", encoding="utf-8")
    assert digest_tree(root) != baseline
    (root / "a" / "one.mncs").write_text("one", encoding="utf-8")
    assert digest_tree(root) == baseline
    (root / "a" / "two.mncs").write_text("one", encoding="utf-8")
    assert digest_tree(root) != baseline


def test_digest_tree_missing_root_returns_none(tmp_path: Path) -> None:
    assert digest_tree(tmp_path / "absent") is None


def test_digest_file_missing_returns_none(tmp_path: Path) -> None:
    assert digest_file(tmp_path / "absent") is None


def test_tool_digest_memo_reused_until_replaced(tmp_path: Path) -> None:
    binary = tmp_path / "mncs"
    binary.write_bytes(b"v1")
    cache_dir = tmp_path / "cache"
    first = tool_digest(binary, cache_dir=cache_dir)
    assert first.startswith("sha256:")
    assert (_tool_memo(cache_dir)).get(str(binary), {}).get("sha256") in first
    # Same bytes, same marker: memo hit without rehashing.
    with patch("ravel.plan_cache.digest_file", side_effect=AssertionError("rehash")):
        assert tool_digest(binary, cache_dir=cache_dir) == first
    binary.write_bytes(b"v2-longer")
    assert tool_digest(binary, cache_dir=cache_dir) != first


def _tool_memo(cache_dir: Path) -> dict[str, object]:
    return json.loads((cache_dir / ".tool-digests.json").read_text(encoding="utf-8"))


def test_request_plan_serves_repeat_from_cache_without_providers(tmp_path: Path) -> None:
    from ravel.impact import build_verification_plan, request_verification_plan

    source = tmp_path / "source.mncs"
    source.write_text("mncs 0.18; module test;", encoding="utf-8")
    impact = {
        "schema_version": "mncs.semantic-impact/1",
        "graph_identity": "b" * 64,
        "roots": ["mncs:fn:changed"],
        "nodes": [{"identity": "mncs:fn:changed", "kind": "function", "distance": 0}],
        "edges": [],
        "direct_dependents": ["mncs:fn:dependent"],
        "test_identities": ["mncs:test-case:one"],
        "risk_flags": [],
        "complete": True,
        "limitations": [],
        "source_test_inventory": {
            "schema_version": "mncs.test-inventory/1",
            "valid": True,
            "inventory": {
                "subject_identity": "mncs:0.2:program:test",
                "subject_fingerprint": "c" * 64,
                "tests": [
                    {
                        "test_case_identity": "mncs:test-case:one",
                        "function_identity": "mncs:fn:dependent",
                    }
                ],
            },
        },
    }
    expected = build_verification_plan(
        {key: value for key, value in impact.items() if key != "source_test_inventory"},
        impact["source_test_inventory"],
        source_path=source,
    )
    calls = {"planner": 0}

    def fake_planner(**kwargs: object) -> dict[str, object]:
        calls["planner"] += 1
        return dict(expected)

    def fake_run_json(command: object, **kwargs: object) -> object:
        return dict(impact)

    cache = PlanCache(directory=tmp_path / "plan-cache", enabled=True)
    request_kwargs: dict[str, object] = {
        "source_path": source,
        "mncs": "mncs-test-binary",
        "roots": ["mncs:fn:changed"],
        "cwd": tmp_path,
        "plan_cache": cache,
    }
    with (
        patch("ravel.impact._run_json", side_effect=fake_run_json),
        patch("ravel.impact._run_native_planner", side_effect=fake_planner),
    ):
        first = request_verification_plan(**request_kwargs)  # type: ignore[arg-type]
        assert calls["planner"] == 1
        second = request_verification_plan(**request_kwargs)  # type: ignore[arg-type]
        assert calls["planner"] == 1
    assert first == expected
    assert second == expected
    assert cache.hits == 1
    assert cache.stores == 1


def test_request_plan_bypasses_cache_for_oracle_and_obligations(tmp_path: Path) -> None:
    from ravel.impact import request_verification_plan

    source = tmp_path / "source.mncs"
    source.write_text("mncs 0.18; module test;", encoding="utf-8")
    cache = PlanCache(directory=tmp_path / "plan-cache", enabled=True)
    with patch("ravel.impact._run_json", side_effect=AssertionError("no providers")):
        with pytest.raises(AssertionError):
            request_verification_plan(
                source_path=source,
                mncs="mncs-test-binary",
                roots=["mncs:fn:changed"],
                cwd=tmp_path,
                plan_cache=cache,
                allow_python_oracle=True,
            )
    assert cache.skips == 1
    assert cache.hits == 0
    assert cache.stores == 0
    assert list((tmp_path / "plan-cache").glob("*.json")) == [] if (tmp_path / "plan-cache").exists() else True
