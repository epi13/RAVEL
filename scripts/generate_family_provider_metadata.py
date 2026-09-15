#!/usr/bin/env python3
"""Generate Ravel provider facts from the generated MNCS ABI binding.

The generated binding is the local, reviewable projection of the compiler-owned
callable metadata.  This tool reads only its literal identity constants and
the explicit family declaration; it does not infer consumers or scrape source
text.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "commons.mncs.generated-provider-metadata/v1"
GENERATOR_VERSION = "ravel-provider-facts/0.1"
REQUIRED_BINDING_FIELDS = (
    "GENERATOR_VERSION",
    "MODULE_IDENTITY",
    "INTERFACE_IDENTITY",
    "TYPED_CALL_SCHEMA_VERSION",
    "BINDING_CONTENT_IDENTITY",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_binding_metadata(path: Path) -> dict[str, str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        raise ValueError(f"cannot read generated binding {path}: {error}") from error
    values: dict[str, str] = {}
    for statement in tree.body:
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = statement.targets
        elif isinstance(statement, ast.AnnAssign) and statement.target is not None:
            targets = [statement.target]
        for target in targets:
            if not isinstance(target, ast.Name) or target.id not in REQUIRED_BINDING_FIELDS:
                continue
            try:
                value = ast.literal_eval(statement.value)
            except (ValueError, TypeError):
                raise ValueError(f"generated binding {path} has a non-literal {target.id}") from None
            if not isinstance(value, str) or not value:
                raise ValueError(f"generated binding {path} has an invalid {target.id}")
            values[target.id] = value
    missing = [field for field in REQUIRED_BINDING_FIELDS if field not in values]
    if missing:
        raise ValueError(f"generated binding {path} is missing: {', '.join(missing)}")
    if values["TYPED_CALL_SCHEMA_VERSION"] != "mncs.typed-call/1":
        raise ValueError("generated binding uses an unsupported typed-call schema")
    for field in ("INTERFACE_IDENTITY", "BINDING_CONTENT_IDENTITY"):
        if len(values[field]) != 64 or any(character not in "0123456789abcdef" for character in values[field]):
            raise ValueError(f"generated binding {field} must be a lowercase SHA-256 identity")
    return values


def normalize_providers(declaration: dict[str, Any]) -> list[dict[str, str]]:
    if declaration.get("schema_version") != "commons.mncs.semantic-contract-declarations/v1":
        raise ValueError("family declaration has an unsupported schema")
    if declaration.get("repository_id") != "ravel":
        raise ValueError("family declaration repository_id must be ravel")
    providers = declaration.get("provides")
    if not isinstance(providers, list) or not providers:
        raise ValueError("family declaration provides must be a non-empty array")
    fields = ("contract_identity", "contract_revision", "exported_identity", "evidence")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(providers):
        if not isinstance(raw, dict) or any(not isinstance(raw.get(field), str) or not raw[field] for field in fields):
            raise ValueError(f"family declaration provides[{index}] is incomplete")
        identity = raw["contract_identity"]
        if identity in seen:
            raise ValueError(f"family declaration repeats {identity}")
        seen.add(identity)
        evidence = Path(raw["evidence"])
        if evidence.is_absolute() or ".." in evidence.parts:
            raise ValueError(f"family declaration provides[{index}].evidence must be bounded")
        normalized.append({field: raw[field] for field in fields})
    return sorted(normalized, key=lambda item: item["contract_identity"])


def render(binding_path: Path, declaration_path: Path) -> str:
    binding = read_binding_metadata(binding_path)
    declaration = read_object(declaration_path, "family declaration")
    providers = normalize_providers(declaration)
    root = declaration_path.parent
    evidence_digests: dict[str, str] = {}
    for provider in providers:
        evidence_path = root / provider["evidence"]
        if not evidence_path.is_file():
            raise ValueError(f"provider evidence does not exist: {provider['evidence']}")
        evidence_digests[provider["evidence"]] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    evidence_digests = dict(sorted(evidence_digests.items()))
    material = {
        "binding_language": "provider-facts",
        "generator_version": GENERATOR_VERSION,
        "module_identity": binding["MODULE_IDENTITY"],
        "interface_identity": binding["INTERFACE_IDENTITY"],
        "typed_call_schema_version": binding["TYPED_CALL_SCHEMA_VERSION"],
        "binding_content_identity": binding["BINDING_CONTENT_IDENTITY"],
        "providers": providers,
        "evidence_digests": evidence_digests,
    }
    output = {
        "schema_version": SCHEMA,
        "repository_id": "ravel",
        "authority": {
            "kind": "language-owned-abi",
            "module_identity": binding["MODULE_IDENTITY"],
            "interface_identity": binding["INTERFACE_IDENTITY"],
            "typed_call_schema_version": binding["TYPED_CALL_SCHEMA_VERSION"],
            "generator_version": GENERATOR_VERSION,
            "binding_content_identity": binding["BINDING_CONTENT_IDENTITY"],
            "provider_fact_identity": digest(material),
            "evidence_digests": evidence_digests,
        },
        "providers": providers,
    }
    return json.dumps(output, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--binding", type=Path, default=Path("src/ravel/generated/verification_plan.py")
    )
    parser.add_argument(
        "--declaration", type=Path, default=Path("family-semantic-contracts-v1.json")
    )
    parser.add_argument("--output", type=Path, default=Path("family-provider-metadata-v1.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        rendered = render(args.binding.resolve(), args.declaration.resolve())
        if args.check:
            current = args.output.read_text(encoding="utf-8")
            if current != rendered:
                print(f"stale provider metadata: regenerate {args.output}", file=sys.stderr)
                return 1
        else:
            args.output.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"provider metadata error: {error}", file=sys.stderr)
        return 1
    print(digest(json.loads(rendered)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
