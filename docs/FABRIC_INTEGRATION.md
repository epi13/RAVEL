# RAVEL and MNCS Fabric

RAVEL uses MNCS Forge and Fabric as sibling layers:

```text
RAVEL semantic question
        -> Forge declared development workflow
        -> Fabric bounded JobPlan/execution record
        -> MNCS receipt and resource facts
        -> RAVEL scoped advisory experience
```

## Current live integration: persistent controller

`FabricPersistentBackend` in `src/ravel/fabric_persistent.py` is the preferred
live-development path. It consumes Fabric through the public
`FabricClient.connect(controller.sock)` boundary and deliberately does **not**
load or own:

- worker host/port endpoints,
- CA files, client certificates, or client keys,
- TrustStore state,
- worker registry files,
- worker bundle-cache paths,
- placement state, or
- controller execution ledgers.

Those remain Fabric-owned. RAVEL supplies a development-only semantic workload,
an immutable MNCS execution bundle, required capabilities, and opaque provenance.
Fabric owns admission, controller-side bundle transfer, placement, worker
execution, raw records, receipts, and detached execution state.

A minimal configuration is:

```toml
[fabric]
mode = "persistent-controller"
socket_path = "~/.local/state/mncs-fabric/controller.sock"
client_identity = "ravel"
timeout = 5.0
```

See
[`config/ravel-fabric-persistent.example.toml`](../config/ravel-fabric-persistent.example.toml).

The config parser is intentionally narrow. Worker endpoints and trust material
are rejected if they are added to the persistent config. This prevents RAVEL
from silently regaining responsibilities that belong to Fabric.

### Synchronous and detached execution

The backend supports both forms:

```python
from ravel.fabric_persistent import FabricPersistentBackend, FabricPersistentConfig

backend = FabricPersistentBackend(
    "build/fabric-live",
    FabricPersistentConfig.load("config/ravel-fabric-persistent.toml"),
)

report = backend.execute_provider_parity("branching")
```

For long-running work RAVEL can submit and disconnect:

```python
submission = backend.submit_provider_parity("branching")
print(submission.work_id)

status = backend.execution_status(submission)
report = backend.collect_submission(submission)
```

Detached submission metadata is written under
`<workspace>/fabric-submissions/`. A later RAVEL process can recover it with
`load_submission(work_id)` or collect the final evidence with
`collect_work_id(work_id)`. Fabric remains the source of truth for execution
state; the RAVEL metadata is only the provenance needed to interpret the
returned evidence.

No model is hard-coded into the adapter. `submit_provider_parity()` accepts an
optional Fabric `model` and `role`, while the default leaves model/worker
selection to the surrounding MNCS policy and Fabric capability inventory.

### Live RAVEL consumer agent

`ravel-fabric-agent` (or `python3 tools/ravel_fabric_agent.py` from a checkout)
provides the bounded long-running consumer process. It performs three jobs only:

1. reports controller/fleet readiness through Fabric's public consumer API;
2. optionally submits one branching and one ring development bootstrap probe; and
3. watches RAVEL's own detached work and retains completed Fabric evidence
   references under the RAVEL state directory.

It does **not** poll controller ledgers directly, inspect worker secrets, ingest
arbitrary MNCS experiments, resubmit work on a timer, or grant evaluator status.
The bootstrap operation is idempotent with respect to RAVEL's retained provider
submissions, so restarting the agent does not create an endless stream of jobs.

From the standard controller layout no config file is required:

```bash
python3 tools/ravel_fabric_agent.py doctor
python3 tools/ravel_fabric_agent.py run --bootstrap --interval 30
```

The default socket is `~/.local/state/mncs-fabric/controller.sock` and the
default RAVEL-owned state root is `~/.local/state/ravel/fabric-live`. A custom
config may still be supplied with `--config` or `RAVEL_FABRIC_CONFIG`.

Because the current 0.6 provider probe bundles a binary compiled on the
controller, its Fabric workload is explicitly constrained to the producing OS
and architecture in addition to `python`. This prevents, for example, a Linux
ELF candidate from being placed on a Windows worker merely because both expose
Python. Cross-platform RAVEL probes require platform-native build artifacts; the
adapter does not pretend otherwise.

### Authority and evidence boundary

Fabric outcomes remain execution evidence. They are never promoted into a RAVEL
evaluator verdict. Persistent reports therefore keep:

```text
Fabric execution outcome       PASS / FAIL / UNKNOWN
Fabric reconciliation          UNKNOWN unless Fabric exposes it publicly
RAVEL evaluator authority      separate
promotion / selection authority not asserted
```

RAVEL explicitly refuses to reimplement Fabric reconciliation in the consumer
process. If the persistent public API does not expose a Fabric-owned
reconciliation result, the RAVEL report says `UNKNOWN` rather than fabricating
independence.

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

## Historical local reference backend

`FabricLocalBackend` remains available for reproducible local development and
negative-matrix testing. It uses Fabric's public `FabricService`,
`LocalController`, `LocalWorker`, manifest, receipt, challenge/replay, and
reconciliation APIs. It builds a bounded development-only artifact and runs the
branching and ring provider parity task on two logical workers. These workers
share a process and host, so the report labels the scope
`local-in-process-replication` and keeps independence `UNKNOWN`.

The local command is:

```bash
python3 tools/ravel_fabric_reference.py --workspace build/fabric-reference --json
```

The project-local Forge workflow `fabric-reference` invokes the same command.
The `fabric-negative` workflow tests capability mismatch (`UNKNOWN`), wrong
manifest and corrupt record (`FAIL`), idempotent duplicate request, and
conflicting replay. A first valid challenge consumption is `PASS`; consuming
the same challenge again is a Fabric `FAIL` and is retained rather than hidden.

## Legacy direct-network boundary

`FabricNetworkBackend` and `FabricNetworkConfig` are retained for historical
compatibility and targeted network-reference testing. They directly describe
TLS workers and require pre-staged bundles. They are **not** the preferred live
fleet path now that Fabric exposes a persistent controller consumer API.

New live integrations should use `FabricPersistentBackend` instead of teaching
RAVEL worker endpoints, trust material, or bundle staging.

The legacy report keeps these facts separate:

```text
bundle verified       PASS
bundle pre-staged     PASS (local artifact root)
archive executed      UNKNOWN
receipt/archive probe FAIL (legacy Fabric receipt binds its artifact manifest)
Fabric reconciliation PASS (Fabric question only)
RAVEL evaluator       separate; normally UNKNOWN
```

Fabric execution is not a sandbox, independent evaluation, protected custody,
MNCS/MNCDS conformance, or promotion authority. Selection and future-final
material remain outside this development adapter.
