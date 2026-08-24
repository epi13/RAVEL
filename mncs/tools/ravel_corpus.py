#!/usr/bin/env python3
"""Reusable corpus builder for MNCS-native RAVEL experiments.

Emits ExecutionCorpus JSON (schema 0.1) matching mncs-model's serde format:
values are externally tagged enums whose payloads are structs, e.g.
{"integer": {"value": .., "type": {"bits": 32, "signed": true}}},
{"boolean": {"value": true}},
{"finite": {"type_identity": .., "variant_identity": .., "discriminant": ..}},
{"record": {"type_identity": .., "name": .., "fields": [[name, value], ...]}}.
"""

import json


def integer(value, bits=32, signed=True):
    return {"integer": {"value": value, "type": {"bits": bits, "signed": signed}}}


def boolean(value):
    return {"boolean": {"value": value}}


class Finite:
    def __init__(self, module, name, variants):
        self.module = module
        self.name = name
        self.variants = variants

    def __getattr__(self, variant):
        discriminant = self.variants.index(variant)
        return {
            "finite": {
                "type_identity": f"mncs:0.2:finite-type:{self.module}::{self.name}",
                "variant_identity": f"mncs:0.2:finite-type-placeholder",
                "discriminant": discriminant,
            }
        }


def finite(module, type_name, variant_name, discriminant):
    return {
        "finite": {
            "type_identity": f"mncs:0.2:finite-type:{module}::{type_name}",
            "variant_identity": f"mncs:0.2:finite-variant:{module}::{type_name}::{variant_name}",
            "discriminant": discriminant,
        }
    }


def record(module, type_name, canonical_fields_hash, pairs):
    """pairs: list of (field_name, encoded_value) in canonical (sorted) order."""
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{module}::{type_name}::{canonical_fields_hash}",
            "name": type_name,
            "fields": [[name, value] for name, value in pairs],
        }
    }


def fields_hash(pairs):
    """Canonical field identity fragment: sorted 'name:type;' pairs, URL-encoded."""
    import urllib.parse

    joined = "".join(f"{n}:{t};" for n, t in sorted(pairs))
    return urllib.parse.quote(joined, safe="")


def case(case_id, module, function, arguments, expected=None, step_budget=1024):
    entry = {
        "id": case_id,
        "request": {
            "schema_version": "0.1",
            "target": {"module": module, "function": function},
            "arguments": list(arguments),
            "step_budget": step_budget,
        },
    }
    if expected is not None:
        if not isinstance(expected, list):
            expected = [expected]
        entry["expected"] = expected
    return entry


def emit(path, name, cases):
    document = {"schema_version": "0.1", "name": name, "cases": cases}
    with open(path, "w") as handle:
        json.dump(document, handle, indent=1)
        handle.write("\n")
    print(f"wrote {path}: {len(cases)} cases")
