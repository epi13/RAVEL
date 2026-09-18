# Family provider metadata

Ravel's `family-provider-metadata-v1.json` is generated from the checked-in
MNCS-generated binding at `src/ravel/generated/verification_policy.py` and the
explicit `family-semantic-contracts-v1.json` provider declaration.

The binding contributes the compiler-owned module, interface, typed-call
schema, and binding content identities. The declaration remains the
human-reviewable source of provider ownership; consumer relationships are not
inferred. The generated artifact also records the digest of its provider
evidence file.

Validate it with:

```sh
python scripts/generate_family_provider_metadata.py --check
PYTHONPATH=scripts python scripts/test_family_provider_metadata.py
```

Changing the callable interface or generated binding identity makes the
checked-in provider facts stale and fails CI until the artifact is regenerated.
