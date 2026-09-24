"""Deterministic RAVEL obligation/evidence projection.

The native RAVEL policy still owns verification level, escalation vocabulary,
and proof boundary. This module performs the bounded, identity-based join from
that decision to a repository-owned obligation inventory. It never executes a
provider and never upgrades evidence to PASS.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

try:
    from .family_contract import (
        obligation_inventory_identity,
        obligation_plan_identity,
        validate_obligation_inventory,
        validate_obligation_plan,
    )
except ImportError:  # direct script execution
    from family_contract import (  # type: ignore
        obligation_inventory_identity,
        obligation_plan_identity,
        validate_obligation_inventory,
        validate_obligation_plan,
    )


ACTIVE_LIFECYCLES = {"permanent", "transitional"}
ORDINARY_EXCLUDED_LIFECYCLES = {"scheduled", "reference_only", "retired"}
NATIVE_KERNEL_SCHEMA = "mncs.ravel-obligation-kernel/1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _repository_root(source_path: Path, inventory_path: Path) -> Path | None:
    inventory_resolved = inventory_path.resolve()
    for parent in (source_path.resolve().parent, *source_path.resolve().parents):
        project_path = parent / ".mncs" / "project.json"
        project = _read_json(project_path)
        verification = project.get("verification") if project else None
        declared = verification.get("obligation_inventory") if isinstance(verification, Mapping) else None
        if isinstance(declared, str) and (parent / declared).resolve() == inventory_resolved:
            return parent
    return None


def _declared_path_fingerprint(root: Path, paths: Sequence[str]) -> tuple[str, bool, list[str]]:
    files: dict[str, str] = {}
    complete = True
    visited = 0
    excluded = {".git", "target", "node_modules", "__pycache__", ".pytest_cache"}
    for raw in sorted(set(paths)):
        candidate = (root / raw).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            complete = False
            continue
        if not candidate.exists():
            complete = False
            continue
        if candidate.is_file():
            candidates = [candidate]
        elif candidate.is_dir():
            candidates = []
            for directory, child_dirs, child_files in os.walk(candidate):
                child_dirs[:] = sorted(name for name in child_dirs if name not in excluded)
                for name in sorted(child_files):
                    candidates.append(Path(directory) / name)
                    visited += 1
                    if visited > 50000:
                        return _digest(files), False, sorted(files)
        else:
            complete = False
            continue
        for file_path in candidates:
            try:
                relative = file_path.relative_to(root).as_posix()
                files[relative] = hashlib.sha256(file_path.read_bytes()).hexdigest()
            except (OSError, ValueError):
                complete = False
    return _digest(files), complete, sorted(files)


def _tool_identity(argv: Sequence[str], *, cwd: Path) -> str | None:
    if not argv:
        return None
    tool = argv[0]
    probes: list[list[str]] = []
    if tool == "cargo":
        probes = [["cargo", "--version"], ["rustc", "--version"]]
    elif Path(tool).name.startswith("python"):
        probes = [[tool, "--version"]]
    else:
        probes = [[tool, "--version"]]
    values: list[str] = []
    for command in probes:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        output = (result.stdout or result.stderr).strip()
        if result.returncode != 0 or not output:
            return None
        values.append(output)
    return "; ".join(values)


def _cargo_metadata(root: Path, *, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = subprocess.run(
            ["cargo", "metadata", "--format-version", "1"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=min(max(timeout, 1), 120),
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if result.returncode != 0:
        return None, None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, None
    return (value, result.stderr) if isinstance(value, dict) else (None, None)


def _cargo_package_name(argv: Sequence[str]) -> str | None:
    for index, value in enumerate(argv):
        if value in {"--package", "-p"} and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith("--package="):
            return value.partition("=")[2]
    return None


def _cargo_closure_paths(metadata: Mapping[str, Any], package_name: str) -> list[str] | None:
    packages = metadata.get("packages")
    nodes = metadata.get("resolve", {}).get("nodes") if isinstance(metadata.get("resolve"), Mapping) else None
    if not isinstance(packages, list) or not isinstance(nodes, list):
        return None
    by_id = {item.get("id"): item for item in packages if isinstance(item, Mapping) and item.get("id")}
    workspace_ids = set(metadata.get("workspace_members", []))
    named = [
        item for item in packages
        if isinstance(item, Mapping) and item.get("name") == package_name and item.get("id") in workspace_ids
    ]
    if len(named) != 1:
        return None
    node_by_id = {item.get("id"): item for item in nodes if isinstance(item, Mapping)}
    pending = [str(named[0]["id"])]
    closure: set[str] = set()
    while pending:
        package_id = pending.pop()
        if package_id in closure:
            continue
        closure.add(package_id)
        node = node_by_id.get(package_id)
        deps = node.get("deps", []) if isinstance(node, Mapping) else []
        if not isinstance(deps, list):
            return None
        for dependency in deps:
            dependency_id = dependency.get("pkg") if isinstance(dependency, Mapping) else None
            if dependency_id in workspace_ids and dependency_id not in closure:
                pending.append(str(dependency_id))
    paths: set[str] = {"Cargo.toml", "Cargo.lock"}
    for package_id in closure:
        package = by_id.get(package_id)
        manifest_path = package.get("manifest_path") if isinstance(package, Mapping) else None
        if not isinstance(manifest_path, str):
            return None
        manifest = Path(manifest_path)
        try:
            relative = manifest.parent.relative_to(Path(str(metadata.get("workspace_root", ""))))
        except ValueError:
            return None
        paths.add(relative.as_posix())
    root = Path(str(metadata.get("workspace_root", "")))
    for path in ("rust-toolchain", "rust-toolchain.toml", ".cargo"):
        if (root / path).exists():
            paths.add(path)
    return sorted(paths)


def build_repository_context(
    *,
    source_path: Path,
    inventory_path: Path,
    inventory_document: Mapping[str, Any],
    mncs: str | Path,
    cwd: Path,
    libraries: Sequence[Path],
    timeout: float,
) -> dict[str, Any]:
    """Project the repository-owned closure declarations for a canonical plan.

    Project self-tests become executor-bound obligations; repository-canonical
    inventory rows remain the authority for MNCS obligations. Test sources are
    queried by their declared paths and remain explicitly source_module scoped.
    """

    root = _repository_root(source_path, inventory_path)
    if root is None:
        return {"requested": True, "complete": False, "impact_complete": False, "unknown_root": True}
    project_path = root / ".mncs" / "project.json"
    project = _read_json(project_path) or {}
    try:
        inventory = validate_obligation_inventory(dict(inventory_document))
    except ValueError:
        return {"requested": True, "complete": False, "impact_complete": False, "unknown_root": True}
    repository_identity = project.get("repository")
    verification_metadata = project.get("verification") if isinstance(project.get("verification"), Mapping) else {}
    declared_inventory = verification_metadata.get("obligation_inventory")
    runner_identity = verification_metadata.get("test_runner_identity")
    complete = bool(
        isinstance(repository_identity, str)
        and repository_identity == inventory.get("repository")
        and isinstance(declared_inventory, str)
        and (root / declared_inventory).resolve() == inventory_path.resolve()
        and isinstance(runner_identity, str)
        and runner_identity
    )
    try:
        revision_process = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            check=False, timeout=10, stdin=subprocess.DEVNULL,
        )
        revision = revision_process.stdout.strip() if revision_process.returncode == 0 else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        revision = "unknown"
    if revision == "unknown":
        complete = False

    metadata, _ = _cargo_metadata(root, timeout=timeout)
    if metadata is None:
        complete = False
    contracts = project.get("contracts", {})
    project_tests = contracts.get("tests", []) if isinstance(contracts, Mapping) else []
    providers = contracts.get("provides", []) if isinstance(contracts, Mapping) else []
    if not isinstance(project_tests, list):
        project_tests = []
        complete = False
    if not isinstance(providers, list):
        providers = []
        complete = False
    fingerprint_sources: dict[str, list[str]] = {}
    for provider in providers:
        if not isinstance(provider, Mapping) or not isinstance(provider.get("contract"), str):
            continue
        sources = provider.get("fingerprint_sources", [])
        if isinstance(sources, list):
            fingerprint_sources[provider["contract"]] = [item for item in sources if isinstance(item, str)]

    compiler_test_inventories: list[dict[str, Any]] = []
    canonical_obligations: list[dict[str, Any]] = []
    required_identities: list[str] = []
    declared_tests: list[dict[str, Any]] = []
    repository_evidence: list[dict[str, Any]] = []
    tool_versions: dict[str, str] = {}
    environment = dict(os.environ)
    if libraries:
        environment["MNCS_LIBRARY_PATH"] = os.pathsep.join(str(item.resolve()) for item in libraries)

    raw_obligations = inventory.get("obligations", [])
    for raw in raw_obligations:
        if not isinstance(raw, Mapping) or raw.get("scope") != "repository_canonical":
            continue
        obligation = dict(raw)
        identity = obligation.get("identity")
        if isinstance(identity, str):
            required_identities.append(identity)
        executor = dict(obligation.get("executor", {}))
        sources = executor.get("source_paths", [])
        if executor.get("kind") == "native_first_class_test":
            if not isinstance(sources, list) or not sources:
                complete = False
            resolved_sources: list[str] = []
            test_ids: set[str] = set()
            raw_library_paths = executor.get("library_paths", [])
            if not isinstance(raw_library_paths, list):
                complete = False
                raw_library_paths = []
            resolved_libraries: list[Path] = []
            external_library_names: list[str] = []
            for library_path in raw_library_paths:
                if not isinstance(library_path, str):
                    complete = False
                    continue
                resolved_library = (root / library_path).resolve()
                try:
                    relative_workspace = resolved_library.relative_to(root.parent.resolve()).as_posix()
                except ValueError:
                    complete = False
                    continue
                if not resolved_library.is_dir():
                    complete = False
                    continue
                external_library_names.append(relative_workspace)
                resolved_libraries.append(resolved_library)
            for raw_path in sources if isinstance(sources, list) else []:
                if not isinstance(raw_path, str):
                    complete = False
                    continue
                path = (root / raw_path).resolve()
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    complete = False
                    continue
                resolved_sources.append(relative)
                try:
                    source_environment = dict(environment)
                    if resolved_libraries:
                        configured = source_environment.get("MNCS_LIBRARY_PATH", "")
                        source_environment["MNCS_LIBRARY_PATH"] = os.pathsep.join(
                            [*([configured] if configured else []), *(str(path) for path in resolved_libraries)]
                        )
                    inventory_result = subprocess.run(
                        [str(mncs), "test-inventory", str(path)], cwd=root, env=source_environment,
                        capture_output=True, text=True, check=False, timeout=timeout, stdin=subprocess.DEVNULL,
                    )
                    document = json.loads(inventory_result.stdout) if inventory_result.returncode == 0 else None
                except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                    document = None
                inner = document.get("inventory") if isinstance(document, Mapping) else None
                tests = inner.get("tests") if isinstance(inner, Mapping) else None
                if not isinstance(document, Mapping) or document.get("valid") is not True or not isinstance(tests, list):
                    complete = False
                    continue
                stable_tests = [
                    item for item in tests
                    if isinstance(item, Mapping)
                    and isinstance(item.get("test_case_identity"), str)
                    and item.get("test_case_identity")
                ]
                if len(stable_tests) != len(tests):
                    complete = False
                test_ids.update(str(item["test_case_identity"]) for item in stable_tests)
                inventory_material = {
                    "subject_identity": inner.get("subject_identity"),
                    "subject_fingerprint": inner.get("subject_fingerprint"),
                    "test_case_identities": sorted(str(item["test_case_identity"]) for item in stable_tests),
                }
                compiler_test_inventories.append({
                    "path": relative,
                    "scope": "source_module",
                    "identity": _digest(inventory_material),
                    "test_case_identities": inventory_material["test_case_identities"],
                })
            executor["source_paths"] = sorted(set(resolved_sources))
            executor["library_paths"] = list(raw_library_paths)
            executor["test_case_identities"] = sorted(test_ids)
            verifier = executor.get("verifier_identity") or "mncs-test-runner/0.2.0"
            executor["verifier_identity"] = verifier
            invalidation, paths_complete, invalidated_paths = _declared_path_fingerprint(
                root, [item for item in obligation.get("invalidation_dependencies", []) if isinstance(item, str)]
            )
            external_libraries_identity, libraries_complete, _ = _declared_path_fingerprint(
                root.parent,
                external_library_names,
            ) if external_library_names else (_digest([]), True, [])
            complete = complete and libraries_complete
            invalidation = _digest({"declared_dependencies": invalidation, "external_executor_libraries": external_libraries_identity})
            complete = complete and paths_complete
            derived = {
                "definition_identity": _digest(raw),
                "subject_identity": str((obligation.get("subjects") or [identity])[0]),
                "subject_fingerprint": _digest({"identity": identity, "invalidation": invalidation}),
                "executor_identity": _digest({"provider": executor.get("provider"), "kind": executor.get("kind"), "entrypoint": executor.get("entrypoint"), "source_paths": executor.get("source_paths"), "library_paths": executor.get("library_paths"), "test_case_identities": executor.get("test_case_identities"), "verifier_identity": verifier}),
                "verifier_identity": _digest({"verifier": verifier, "runner": runner_identity}),
                "invalidation_identity": invalidation,
            }
            obligation.update(derived)
            obligation["executor"] = executor
            repository_evidence.append({"identity": identity, **derived, "dependency_paths": invalidated_paths})
            canonical_obligations.append(obligation)

    seen_test_names: set[str] = set()
    for raw_test in project_tests:
        if not isinstance(raw_test, Mapping) or raw_test.get("obligation") != "self":
            continue
        name = raw_test.get("test")
        if not isinstance(name, str) or not name or name in seen_test_names:
            complete = False
            continue
        seen_test_names.add(name)
        identity = f"{repository_identity}.project-test.{name}"
        required_identities.append(identity)
        command = raw_test.get("command")
        argv = command.get("argv") if isinstance(command, Mapping) else None
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
            complete = False
            continue
        timeout_seconds = command.get("timeout_seconds", raw_test.get("timeout_seconds"))
        if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 3600:
            complete = False
            continue
        tool_version = _tool_identity(argv, cwd=root)
        if tool_version is None:
            complete = False
            tool_version = "unavailable"
        tool_versions[argv[0]] = tool_version
        covers = raw_test.get("covers", [])
        dependency_paths = sorted({
            path
            for contract in covers if isinstance(contract, str)
            for path in fingerprint_sources.get(contract, [])
        })
        explicit_dependencies = raw_test.get("invalidation_dependencies", [])
        if isinstance(explicit_dependencies, list):
            dependency_paths = sorted(set(dependency_paths + [item for item in explicit_dependencies if isinstance(item, str)]))
        for argument in argv[1:]:
            if not argument.startswith("-") and (root / argument).exists():
                dependency_paths.append(argument)
        dependency_paths = sorted(set(dependency_paths))
        if argv[0] == "cargo":
            package = _cargo_package_name(argv)
            package_paths = _cargo_closure_paths(metadata, package) if metadata and package else None
            if package_paths is None:
                complete = False
                package_paths = []
            dependency_paths = sorted(set(dependency_paths + package_paths))
        invalidation, paths_complete, invalidated_paths = _declared_path_fingerprint(root, dependency_paths)
        complete = complete and paths_complete
        executor = {
            "provider": "mncs-test",
            "kind": "external_integration",
            "entrypoint": f"project-test:{name}",
            "argv": argv,
            "working_directory": ".",
            "timeout_seconds": timeout_seconds,
            "target_identity": _cargo_package_name(argv) or name,
            "verifier_identity": tool_version,
        }
        definition = {"project_test": dict(raw_test), "repository": repository_identity, "runner_identity": runner_identity}
        subject_identity = f"mncs.repository-test:{repository_identity}:{name}"
        derived = {
            "definition_identity": _digest(definition),
            "subject_identity": subject_identity,
            "subject_fingerprint": _digest({"subject": subject_identity, "invalidation": invalidation}),
            "executor_identity": _digest(executor),
            "verifier_identity": _digest({"verifier": tool_version, "runner": runner_identity}),
            "invalidation_identity": invalidation,
        }
        canonical_obligations.append({
            "identity": identity,
            "title": f"Repository self-test: {name}",
            "guarantee_domain": "integration",
            "evidence_role": "canonical_regression",
            "lifecycle": "permanent",
            "scope": "repository_canonical",
            "subjects": [subject_identity],
            "invalidation_dependencies": dependency_paths,
            "executor": executor,
            "evidence_identity": {"subject_fields": ["repository_fingerprint", "subject_fingerprint"], "definition_fields": ["definition_identity"], "execution_fields": ["executor_identity", "verifier_identity", "invalidation_identity"]},
            **derived,
        })
        repository_evidence.append({"identity": identity, **derived, "dependency_paths": invalidated_paths})
        declared_tests.append({"identity": identity, "name": name, "command": argv})

    duplicate_identities = len(required_identities) != len(set(required_identities))
    if duplicate_identities:
        complete = False
    compiler_inventory_identity = _digest(compiler_test_inventories)
    repository_inventory_identity = _digest({
        "repository": repository_identity,
        "project_revision": project.get("revision"),
        "test_runner_identity": runner_identity,
        "inventory": inventory,
        "project_tests": declared_tests,
        "compiler_test_inventories": compiler_test_inventories,
    })
    repository_fingerprint = _digest({
        "repository": repository_identity,
        "project_revision": project.get("revision"),
        "test_runner_identity": runner_identity,
        "inventory_identity": repository_inventory_identity,
        "compiler_test_inventory_identity": compiler_inventory_identity,
    })
    return {
        "requested": True,
        "complete": complete,
        "impact_complete": False,
        "unknown_root": True,
        "identity": repository_identity if isinstance(repository_identity, str) else "unknown",
        "revision": revision,
        "fingerprint": repository_fingerprint,
        "inventory_identity": repository_inventory_identity,
        "required_obligation_identities": list(dict.fromkeys(required_identities)),
        "obligations": canonical_obligations,
        "compiler_test_inventories": compiler_test_inventories,
        "project_tests": declared_tests,
        "obligation_identities": repository_evidence,
        "tool_versions": tool_versions,
    }


def _strings(value: Any) -> list[str]:
    return sorted({item for item in value if isinstance(item, str) and item}) if isinstance(value, list) else []


def _ordered_strings(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def _compiler_tests(inventory_document: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(inventory_document, Mapping):
        return []
    inventory = inventory_document.get("inventory")
    tests = inventory.get("tests") if isinstance(inventory, Mapping) else None
    return [item for item in tests if isinstance(item, dict)] if isinstance(tests, list) else []


def _test_case_identities(obligation: Mapping[str, Any], compiler_inventory: Mapping[str, Any] | None) -> list[str]:
    executor = obligation.get("executor", {})
    explicit = _strings(executor.get("test_case_identities")) if isinstance(executor, Mapping) else []
    declaration_ids = set(_strings(executor.get("declaration_identities"))) if isinstance(executor, Mapping) else set()
    subjects = set(_strings(obligation.get("subjects")))
    dependencies = set(_strings(obligation.get("invalidation_dependencies")))
    selected: set[str] = set(explicit)
    for test in _compiler_tests(compiler_inventory):
        if "*" in declaration_ids:
            if isinstance(test.get("test_case_identity"), str):
                selected.add(test["test_case_identity"])
        elif declaration_ids and test.get("declaration_identity") in declaration_ids:
            if isinstance(test.get("test_case_identity"), str):
                selected.add(test["test_case_identity"])
        elif test.get("function_identity") in subjects or test.get("function_identity") in dependencies:
            if isinstance(test.get("test_case_identity"), str):
                selected.add(test["test_case_identity"])
    return sorted(selected)


def _matches_impact(obligation: Mapping[str, Any], impact: Mapping[str, Any]) -> bool:
    tokens = set(
        _strings(impact.get("roots"))
        + _strings(impact.get("direct_dependents"))
        + _strings(impact.get("test_identities"))
        + [
            item.get("identity")
            for item in impact.get("nodes", [])
            if isinstance(item, Mapping) and isinstance(item.get("identity"), str)
        ]
    )
    subjects = set(_strings(obligation.get("subjects")))
    dependencies = set(_strings(obligation.get("invalidation_dependencies")))
    if "*" in subjects or "*" in dependencies:
        return True
    if tokens.intersection(subjects | dependencies):
        return True
    domains = set(_strings(impact.get("guarantee_domains")))
    return obligation.get("guarantee_domain") in domains and bool(tokens)


def _source_identity(verification_plan: Mapping[str, Any]) -> tuple[str | None, str | None]:
    source = verification_plan.get("source")
    if not isinstance(source, Mapping):
        return None, None
    subject_identity = source.get("subject_identity")
    subject_fingerprint = source.get("subject_fingerprint")
    return (
        subject_identity if isinstance(subject_identity, str) else None,
        subject_fingerprint if isinstance(subject_fingerprint, str) else None,
    )


def _evidence_state(
    obligation_identity: str,
    current_evidence: Sequence[Mapping[str, Any]],
    *,
    subject_identity: str | None,
    subject_fingerprint: str | None,
    inventory_identity: str,
) -> tuple[str, str, list[str], list[dict[str, Any]]]:
    related = [
        dict(item)
        for item in current_evidence
        if item.get("obligation_identity") == obligation_identity
    ]
    if not related:
        return "new_execution_required", "no identity-bound evidence is available", [], []
    exact: list[dict[str, Any]] = []
    for item in related:
        if subject_identity and item.get("subject_identity") not in (None, subject_identity):
            continue
        if subject_fingerprint and item.get("subject_fingerprint") not in (None, subject_fingerprint):
            continue
        if item.get("definition_identity") not in (None, inventory_identity):
            continue
        exact.append(item)
    statuses = {item.get("status") for item in exact}
    identities = sorted(
        item["evidence_identity"]
        for item in exact
        if isinstance(item.get("evidence_identity"), str)
    )
    if len(statuses) > 1:
        return "contradictory", "identity-bound evidence has contradictory verdicts", identities, exact
    if exact and statuses == {"PASS"}:
        return "current", "current identity-bound PASS evidence can be reused", identities, exact
    if exact and statuses == {"FAIL"}:
        return "escalation_required", "current identity-bound evidence is FAIL", identities, exact
    if exact and statuses == {"UNKNOWN"}:
        return "escalation_required", "current identity-bound evidence is UNKNOWN", identities, exact
    return "stale", "evidence exists but its subject or definition identity is stale", identities, related


def build_obligation_plan(
    verification_plan: Mapping[str, Any],
    obligation_inventory: Mapping[str, Any],
    *,
    source_path: Path,
    compiler_inventory: Mapping[str, Any] | None = None,
    current_evidence: Sequence[Mapping[str, Any]] = (),
    commons_root: Path | None = None,
) -> dict[str, Any]:
    """Explicit Python differential oracle for the native obligation kernel.

    Normal RAVEL planning calls :func:`build_native_obligation_plan`. This
    implementation remains available only so parity tests can compare the
    canonical native decisions with the historical transport implementation.
    """

    normalized_inventory = validate_obligation_inventory(
        dict(obligation_inventory), commons_root=commons_root
    )
    impact = verification_plan.get("impact")
    if not isinstance(impact, Mapping):
        raise ValueError("verification plan impact is unavailable")
    source_sha256 = verification_plan.get("source", {}).get("sha256") if isinstance(verification_plan.get("source"), Mapping) else None
    if not isinstance(source_sha256, str):
        raise ValueError("verification plan source sha256 is unavailable")
    subject_identity, subject_fingerprint = _source_identity(verification_plan)
    impact_domains = _strings(impact.get("guarantee_domains")) or ["semantic"]
    change_kinds = _strings(impact.get("change_kinds"))
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reasons: set[str] = set()
    for obligation in normalized_inventory["obligations"]:
        lifecycle = obligation["lifecycle"]
        if lifecycle in ORDINARY_EXCLUDED_LIFECYCLES:
            excluded.append(
                {
                    "identity": obligation["identity"],
                    "lifecycle": lifecycle,
                    "reason": "lifecycle is not part of ordinary verification",
                }
            )
            continue
        if lifecycle not in ACTIVE_LIFECYCLES:
            excluded.append(
                {
                    "identity": obligation["identity"],
                    "lifecycle": lifecycle,
                    "reason": "inventory lifecycle is not executable",
                }
            )
            continue
        if not _matches_impact(obligation, impact):
            excluded.append(
                {
                    "identity": obligation["identity"],
                    "lifecycle": lifecycle,
                    "reason": "no compiler-owned subject, dependency, or guarantee-domain intersection",
                }
            )
            continue
        status, reason, evidence_ids, _ = _evidence_state(
            obligation["identity"],
            current_evidence,
            subject_identity=subject_identity,
            subject_fingerprint=subject_fingerprint,
            inventory_identity=obligation_inventory_identity(normalized_inventory, commons_root=commons_root),
        )
        if status in {"stale", "contradictory", "escalation_required"}:
            reasons.add({"stale": "evidence_stale", "contradictory": "evidence_contradictory", "escalation_required": "evidence_escalation_required"}[status])
        test_case_ids = _test_case_identities(obligation, compiler_inventory)
        if obligation["executor"]["kind"] == "native_first_class_test" and not test_case_ids:
            status = "selection_unresolved"
            reason = "native obligation has no current compiler test-case identity"
            reasons.add("obligation_selection_unresolved")
        selected.append(
            {
                "identity": obligation["identity"],
                "status": status,
                "lifecycle": lifecycle,
                "guarantee_domain": obligation["guarantee_domain"],
                "evidence_role": obligation["evidence_role"],
                "reason": reason,
                "evidence_identities": evidence_ids,
                "test_case_identities": test_case_ids,
                "executor": obligation["executor"],
            }
        )
    if not selected:
        reasons.add("obligation_selection_unresolved")
    if not bool(verification_plan.get("proof", {}).get("sufficient_to_stop")):
        reasons.add("verification_plan_not_sufficient")
    plan_selection = verification_plan.get("selection", {})
    if isinstance(plan_selection, Mapping):
        reasons.update(_strings(plan_selection.get("escalation_reasons")))
    required = [item["identity"] for item in selected]
    needs_execution = [
        item["identity"]
        for item in selected
        if item["status"] in {"new_execution_required", "stale", "selection_unresolved", "escalation_required", "contradictory"}
    ]
    sufficient = bool(verification_plan.get("proof", {}).get("sufficient_to_stop")) and bool(selected) and not needs_execution and not reasons.intersection(
        {"obligation_selection_unresolved", "evidence_stale", "evidence_contradictory", "evidence_escalation_required", "verification_plan_not_sufficient"}
    )
    payload: dict[str, Any] = {
        "schema_version": "mncs.verification-obligation-plan/1",
        "verification_plan_id": str(verification_plan.get("plan_id", "")),
        "source": {
            "path": str(source_path.resolve()),
            "sha256": source_sha256,
        },
        "impact_identity": str(impact.get("graph_identity", "")),
        "impact": {
            "guarantee_domains": sorted(set(impact_domains)),
            "change_kinds": change_kinds,
            "roots": _strings(impact.get("roots")),
        },
        "inventory": {
            "repository": normalized_inventory["repository"],
            "revision": normalized_inventory["revision"],
            "identity": obligation_inventory_identity(normalized_inventory, commons_root=commons_root),
        },
        "obligations": selected,
        "excluded": excluded,
        "evidence": [dict(item) for item in current_evidence],
        "stop": {
            "sufficient_to_stop": sufficient,
            "required_obligation_identities": required,
            "new_execution_required": needs_execution,
            "escalation_reasons": sorted(reasons),
            "boundary": str(verification_plan.get("proof", {}).get("boundary", {}).get("claimed_scope", "unknown")),
        },
    }
    payload["obligation_plan_id"] = obligation_plan_identity(payload, commons_root=commons_root)
    return validate_obligation_plan(payload, commons_root=commons_root)


def _native_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _native_executor(executor: Mapping[str, Any]) -> dict[str, Any]:
    argv = executor.get("argv")
    result = {
        "provider": _native_text(executor.get("provider")),
        "kind": _native_text(executor.get("kind")),
        "entrypoint": _native_text(executor.get("entrypoint")),
        "declaration_identities": _strings(executor.get("declaration_identities")),
        "test_case_identities": _strings(executor.get("test_case_identities")),
        "source_paths": _strings(executor.get("source_paths")),
        "library_paths": _strings(executor.get("library_paths")),
        "verifier_identity": _native_text(executor.get("verifier_identity")),
        "target_identity": _native_text(executor.get("target_identity")),
        "argv": _ordered_strings(argv),
        "working_directory": _native_text(executor.get("working_directory")),
        "timeout_seconds": int(executor.get("timeout_seconds", 0)),
    }
    return result


def _clean_selected_obligation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    for field in (
        "definition_identity",
        "subject_identity",
        "subject_fingerprint",
        "executor_identity",
        "verifier_identity",
        "invalidation_identity",
    ):
        if not result.get(field):
            result.pop(field, None)
    executor = result.get("executor")
    if isinstance(executor, Mapping):
        normalized = dict(executor)
        for field in ("verifier_identity", "target_identity", "working_directory"):
            if not normalized.get(field):
                normalized.pop(field, None)
        for field in ("argv", "timeout_seconds"):
            if field == "argv" and not normalized.get(field):
                normalized.pop(field, None)
            if field == "timeout_seconds" and not normalized.get(field):
                normalized.pop(field, None)
        result["executor"] = normalized
    return result


def _native_obligation_request(
    verification_plan: Mapping[str, Any],
    normalized_inventory: Mapping[str, Any],
    *,
    impact: Mapping[str, Any],
    compiler_inventory: Mapping[str, Any] | None,
    current_evidence: Sequence[Mapping[str, Any]],
    commons_root: Path | None,
    repository_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_identity, source_fingerprint = _source_identity(verification_plan)
    tests = _compiler_tests(compiler_inventory)
    nodes = impact.get("nodes", [])
    node_identities = [
        item.get("identity")
        for item in nodes
        if isinstance(item, Mapping) and isinstance(item.get("identity"), str)
    ]
    obligations = []
    for item in normalized_inventory["obligations"]:
        obligations.append(
            {
                "identity": item["identity"],
                "lifecycle": item["lifecycle"],
                "scope": item.get("scope", "local"),
                "guarantee_domain": item["guarantee_domain"],
                "evidence_role": item["evidence_role"],
                "definition_identity": _native_text(item.get("definition_identity")),
                "subject_identity": _native_text(item.get("subject_identity")),
                "subject_fingerprint": _native_text(item.get("subject_fingerprint")),
                "executor_identity": _native_text(item.get("executor_identity")),
                "verifier_identity": _native_text(item.get("verifier_identity")),
                "invalidation_identity": _native_text(item.get("invalidation_identity")),
                "subjects": list(item["subjects"]),
                "invalidation_dependencies": list(item["invalidation_dependencies"]),
                "executor": _native_executor(item["executor"]),
            }
        )
    compiler_tests = [
        {
            "declaration_identity": _native_text(item.get("declaration_identity")),
            "test_case_identity": _native_text(item.get("test_case_identity")),
            "function_identity": _native_text(item.get("function_identity")),
        }
        for item in tests
    ]
    evidence = []
    for item in current_evidence:
        status = item.get("status")
        if status not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ValueError(f"unsupported evidence status for native obligation planning: {status!r}")
        evidence.append(
            {
                "obligation_identity": _native_text(item.get("obligation_identity")),
                "evidence_identity": _native_text(item.get("evidence_identity")),
                "status": status,
                "subject_identity": _native_text(item.get("subject_identity")),
                "subject_fingerprint": _native_text(item.get("subject_fingerprint")),
                "definition_identity": _native_text(item.get("definition_identity")),
                "repository_identity": _native_text(item.get("repository_identity")),
                "repository_revision": _native_text(item.get("repository_revision")),
                "repository_fingerprint": _native_text(item.get("repository_fingerprint")),
                "executor_identity": _native_text(item.get("executor_identity")),
                "verifier_identity": _native_text(item.get("verifier_identity")),
                "invalidation_identity": _native_text(item.get("invalidation_identity")),
                "reason": _native_text(item.get("reason")),
            }
        )
    proof = verification_plan.get("proof")
    proof_mapping = proof if isinstance(proof, Mapping) else {}
    boundary = proof_mapping.get("boundary")
    boundary_mapping = boundary if isinstance(boundary, Mapping) else {}
    selection = verification_plan.get("selection")
    selection_mapping = selection if isinstance(selection, Mapping) else {}
    impact_domains = _strings(impact.get("guarantee_domains")) or ["semantic"]
    repository = repository_context if isinstance(repository_context, Mapping) else {}
    required_repository_identities = _strings(repository.get("required_obligation_identities"))
    return {
        "schema_version": "mncs.ravel-obligation-kernel-request/1",
        "inventory_identity": obligation_inventory_identity(normalized_inventory, commons_root=commons_root),
        "subject_identity": source_identity or "",
        "subject_fingerprint": source_fingerprint or "",
        "proof_sufficient_to_stop": bool(proof_mapping.get("sufficient_to_stop")),
        "boundary": _native_text(boundary_mapping.get("claimed_scope")) or "unknown",
        "repository_scope_requested": bool(repository.get("requested", False)),
        "repository_scope_complete": bool(repository.get("complete", False)),
        "repository_impact_complete": bool(repository.get("impact_complete", False)),
        "repository_unknown_root": bool(repository.get("unknown_root", True)),
        "repository_identity": _native_text(repository.get("identity")),
        "repository_revision": _native_text(repository.get("revision")),
        "repository_fingerprint": _native_text(repository.get("fingerprint")),
        "repository_inventory_identity": _native_text(repository.get("inventory_identity")),
        "required_repository_obligation_identities": required_repository_identities,
        "impact_roots": _strings(impact.get("roots")),
        "impact_direct_dependents": _strings(impact.get("direct_dependents")),
        "impact_test_identities": _strings(impact.get("test_identities")),
        "impact_node_identities": sorted(set(node_identities)),
        "impact_guarantee_domains": impact_domains,
        "selection_escalation_reasons": _strings(selection_mapping.get("escalation_reasons")),
        "obligations": obligations,
        "compiler_tests": compiler_tests,
        "evidence": evidence,
    }


def build_native_obligation_plan(
    verification_plan: Mapping[str, Any],
    obligation_inventory: Mapping[str, Any],
    *,
    source_path: Path,
    mncs: str | Path,
    cwd: Path,
    libraries: Sequence[Path] = (),
    timeout: float = 180.0,
    compiler_inventory: Mapping[str, Any] | None = None,
    current_evidence: Sequence[Mapping[str, Any]] = (),
    commons_root: Path | None = None,
    repository_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the canonical native RAVEL obligation kernel through transport."""

    normalized_inventory = validate_obligation_inventory(
        dict(obligation_inventory), commons_root=commons_root
    )
    if repository_context is not None:
        repository_obligations = repository_context.get("obligations", [])
        if not isinstance(repository_obligations, list):
            raise ValueError("repository canonical obligations must be an array")
        normalized_inventory["obligations"] = [
            *[item for item in normalized_inventory["obligations"] if item.get("scope") != "repository_canonical"],
            *[dict(item) for item in repository_obligations if isinstance(item, Mapping)],
        ]
        identities = [item.get("identity") for item in normalized_inventory["obligations"]]
        if any(not isinstance(identity, str) for identity in identities) or len(identities) != len(set(identities)):
            raise ValueError("repository canonical obligation identities are missing or duplicated")
    impact = verification_plan.get("impact")
    if not isinstance(impact, Mapping):
        raise ValueError("verification plan impact is unavailable")
    source = verification_plan.get("source")
    source_sha256 = source.get("sha256") if isinstance(source, Mapping) else None
    if not isinstance(source_sha256, str):
        raise ValueError("verification plan source sha256 is unavailable")
    request = _native_obligation_request(
        verification_plan,
        normalized_inventory,
        impact=impact,
        compiler_inventory=compiler_inventory,
        current_evidence=current_evidence,
        commons_root=commons_root,
        repository_context=repository_context,
    )
    descriptor = Path(__file__).resolve().parents[2] / "native-applications" / "ravel-obligation-planner.json"
    if not descriptor.is_file():
        raise ValueError(f"native RAVEL obligation planner descriptor is unavailable: {descriptor}")
    try:
        descriptor_value = json.loads(descriptor.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"native RAVEL obligation planner descriptor is invalid: {error}") from error
    declared_libraries = descriptor_value.get("libraries", []) if isinstance(descriptor_value, Mapping) else []
    if not isinstance(declared_libraries, list) or not all(isinstance(item, str) for item in declared_libraries):
        raise ValueError("native RAVEL obligation planner descriptor has an invalid library list")
    declared_library_paths = {
        (descriptor.parent / item).resolve()
        for item in declared_libraries
    }
    base = cwd.resolve()
    try:
        with tempfile.TemporaryDirectory(prefix=".ravel-obligation-native-", dir=base) as directory:
            work = Path(directory)
            request_path = work / "obligation-request.json"
            output_path = work / "obligation-kernel.json"
            request_path.write_text(
                json.dumps(request, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )
            command = [str(mncs), "run-app", str(descriptor)]
            command.extend(("--step-budget", "1048576"))
            for library in libraries:
                resolved_library = library.resolve()
                overlaps_declared_library = any(
                    resolved_library == declared
                    or resolved_library in declared.parents
                    or declared in resolved_library.parents
                    for declared in declared_library_paths
                )
                if not overlaps_declared_library:
                    command.extend(("--library", str(resolved_library)))
            command.extend(
                (
                    "--grant-structured",
                    "ravel_artifact",
                    "--",
                    os.path.relpath(request_path, base),
                    os.path.relpath(output_path, base),
                )
            )
            completed = subprocess.run(
                command,
                cwd=base,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            if completed.returncode != 0:
                raise ValueError(
                    "native RAVEL obligation planner failed: "
                    + (completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
                )
            kernel = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"native RAVEL obligation planner unavailable: {error}") from error
    if not isinstance(kernel, Mapping) or kernel.get("schema_version") != NATIVE_KERNEL_SCHEMA:
        raise ValueError("native RAVEL obligation planner returned an invalid kernel document")
    selected = kernel.get("obligations")
    excluded = kernel.get("excluded")
    stop = kernel.get("stop")
    if not isinstance(selected, list) or not isinstance(excluded, list) or not isinstance(stop, Mapping):
        raise ValueError("native RAVEL obligation planner returned an incomplete kernel document")
    normalized_impact_domains = _strings(impact.get("guarantee_domains")) or ["semantic"]
    change_kinds = _strings(impact.get("change_kinds"))
    payload: dict[str, Any] = {
        "schema_version": "mncs.verification-obligation-plan/1",
        "verification_plan_id": str(verification_plan.get("plan_id", "")),
        "source": {"path": str(source_path.resolve()), "sha256": source_sha256},
        "impact_identity": str(impact.get("graph_identity", "")),
        "impact": {
            "guarantee_domains": normalized_impact_domains,
            "change_kinds": change_kinds,
            "roots": _strings(impact.get("roots")),
        },
        "inventory": {
            "repository": normalized_inventory["repository"],
            "revision": normalized_inventory["revision"],
            "identity": obligation_inventory_identity(normalized_inventory, commons_root=commons_root),
        },
        "obligations": [
            _clean_selected_obligation(item)
            for item in selected
            if isinstance(item, Mapping)
        ],
        "excluded": [dict(item) for item in excluded],
        "evidence": [dict(item) for item in current_evidence],
        "stop": {
            "sufficient_to_stop": bool(stop.get("sufficient_to_stop")),
            "required_obligation_identities": list(stop.get("required_obligation_identities", [])),
            "new_execution_required": list(stop.get("new_execution_required", [])),
            "escalation_reasons": list(stop.get("escalation_reasons", [])),
            "boundary": _native_text(stop.get("boundary")) or "unknown",
        },
    }
    if repository_context is not None and bool(repository_context.get("requested")):
        payload["repository"] = {
            "identity": str(repository_context.get("identity", "")),
            "revision": str(repository_context.get("revision", "unknown")),
            "fingerprint": str(repository_context.get("fingerprint", "")),
            "inventory_identity": str(repository_context.get("inventory_identity", "")),
            "scope": "repository_canonical",
            "complete": bool(stop.get("repository_complete")),
            "required_obligation_identities": list(repository_context.get("required_obligation_identities", [])),
            "selected_obligation_identities": list(stop.get("selected_repository_obligation_identities", [])),
            "missing_obligation_identities": list(stop.get("missing_repository_obligation_identities", [])),
            "compiler_test_inventories": [
                dict(item)
                for item in repository_context.get("compiler_test_inventories", [])
                if isinstance(item, Mapping)
            ],
        }
    payload["obligation_plan_id"] = obligation_plan_identity(payload, commons_root=commons_root)
    return validate_obligation_plan(payload, commons_root=commons_root)


def load_current_evidence(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    import json

    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, Mapping):
        value = value.get("evidence", [])
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError("current evidence must be an array or an object with an evidence array")
    return [dict(item) for item in value]
