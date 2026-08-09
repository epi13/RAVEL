# RAVEL and MNCS Fabric

RAVEL uses MNCS Forge and Fabric as sibling layers:

```text
RAVEL semantic question
        -> Forge declared development workflow
        -> Fabric bounded JobPlan/execution record
        -> MNCS receipt and resource facts
        -> RAVEL scoped advisory experience
```

## Versioned RAVEL contracts

`ravel-fabric-workload/0.1` is RAVEL's semantic request. It binds the candidate,
experiment, question kind, logical and Fabric manifest bundle identities,
capabilities, resource budget, replication count, provider, development
partition, and Forge workflow. It is not a Fabric `JobPlan`, evaluator result,
promotion request, or selection/final input.

`ravel-fabric-observation/0.1` is a reference to immutable Fabric evidence. It
retains workload, request, worker, record, receipt, bundle, challenge/replay,
result, provider, and resource identities plus Fabric outcome/reason codes. It
does not duplicate the raw execution record and is explicitly
`development observation; not evaluator authority`.

The report schema is
[`ravel-0.6-fabric-observation.schema.json`](../ravel_versions/0.6/ravel-0.6-fabric-observation.schema.json).
The compatibility snapshot is
[`ravel-0.6-family-compatibility-lock.json`](../ravel_versions/0.6/ravel-0.6-family-compatibility-lock.json);
it is evidence about inspected public contracts, not an installation lockfile.

## Local reference backend

`FabricLocalBackend` uses Fabric's public `FabricService`, `LocalController`,
`LocalWorker`, manifest, receipt, challenge/replay, and reconciliation APIs. It
builds a bounded development-only artifact and runs the branching and ring
provider parity task on two logical workers. These workers share a process and
host, so the report labels the scope `local-in-process-replication` and keeps
independence `UNKNOWN`.

The local command is:

```bash
python3 tools/ravel_fabric_reference.py --workspace build/fabric-reference --json
```

The project-local Forge workflow `fabric-reference` invokes the same command.
The `fabric-negative` workflow tests capability mismatch (`UNKNOWN`), wrong
manifest and corrupt record (`FAIL`), idempotent duplicate request, and
conflicting replay. A first valid challenge consumption is `PASS`; consuming
the same challenge again is a Fabric `FAIL` and is retained rather than hidden.

## Network boundary

`FabricNetworkBackend` is optional and TLS-only. `FabricNetworkConfig` requires
operator-supplied CA, client certificate/key, trust store, worker endpoint,
capabilities, and an exact pre-staged Fabric manifest identity. The checked-in
[`ravel-fabric.example.toml`](../config/ravel-fabric.example.toml) contains only
placeholders. RAVEL does not use SSH as a dispatch protocol, does not add a
plaintext fallback, and does not claim native bundle transfer until Fabric
exposes and verifies it.

The report therefore keeps these facts separate:

```text
bundle verified       PASS
bundle pre-staged     PASS (local artifact root)
archive executed      UNKNOWN
receipt/archive probe FAIL (Fabric receipt currently binds its artifact manifest)
Fabric reconciliation PASS (Fabric question only)
RAVEL evaluator       separate; normally UNKNOWN
```

The receipt/archive probe is retained as a negative compatibility observation;
it is not rewritten as an official execution binding. Native Fabric bundle
transfer and a receipt adapter that binds the MNCS archive remain a sibling
capability boundary.

Fabric execution is not a sandbox, independent evaluation, protected custody,
MNCS/MNCDS conformance, or promotion authority. Selection and future-final
material are rejected by the workload contract and are not dispatched.
