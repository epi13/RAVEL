# Provider and resource runtime boundary

RAVEL can request evidence from a Forge-compatible provider and retain a
scoped execution experience, but Forge remains the evidence executor and MNCS /
MNCDS remains authoritative. `src/ravel/providers.py` is intentionally small:
it exposes capability discovery, a typed evidence request, immutable raw
evidence, and a separate fail-closed receipt. Missing capabilities, provider
crashes, malformed statuses, and identity mismatches become `UNKNOWN`.

`src/ravel/resources.py` is an optional policy layer for future learned
providers. It has no PyTorch, CUDA, Transformers, or model-weight dependency.
It records observations such as:

- `auto`, `cpu`, or `cuda` device policy;
- no offload or sequential CPU offload;
- actual CUDA-kernel and dtype probes supplied by the backend;
- free VRAM, reserve/headroom, maximum VRAM budget, CPU availability, and RSS;
- model parameter, workspace, and peak-module estimates;
- placement reason, peak VRAM reservation, parameter residency, and timing or
  failure observations supplied by the backend.

Sequential CPU offload keeps primary parameters in system RAM between module
executions. It trades VRAM for system RAM; it does not reduce total memory
requirements. A CUDA out-of-memory signal permits at most one recovery decision,
after which the backend either executes the selected fallback or fails closed.

These measurements are scoped empirical experience, not evidence of
algorithmic superiority. A future experience record should bind provider,
model, hardware, task class, device, placement, dtype, budget, runtime, failure
status, evidence quality, and verifier outcome before any strategy reuse.

Standalone RAVEL tests use fake providers and resource backends. Forge is not a
mandatory dependency for the core package, and lack of a GPU does not make the
normal test suite fail.

The local Forge `0.1.0a2` checkout was inspected and exercised for this
iteration. Its current CLI exposes typed project, provider, verifier, candidate,
workflow, bundle, and lifecycle operations; RAVEL's project-local configuration
declares 17 development workflows. The new Fabric capability and family-lock
workflow passed; the family-lock workflow currently remains `UNKNOWN` because
the inspected Fabric checkout has uncommitted sibling changes. The Fabric
reference workflow passed through Forge after the local reference matrix was
repaired. The project-scoped Forge readiness
policy is separate from the frozen RAVEL preregistration and does not consume
selection data. The precedence is `FAIL > UNKNOWN > PASS`.
`ForgeCliProvider` invokes that JSON interface when explicitly configured and
preserves lifecycle rejection as raw `UNKNOWN`. Forge remains optional for the
core package and is not reimplemented by RAVEL.

## Fabric execution substrate

`ravel.fabric.FabricLocalBackend` is the development reference implementation.
It uses only the public MNCS Fabric service/controller/worker boundary and
delegates bundle construction to the official MNCS execution-bundle tooling.
The reference matrix executes both providers with two logical local workers.
Fabric reconciliation passes for matching immutable records; RAVEL records the
replication scope and does not call it independence.

`FabricNetworkBackend` is optional and unavailable without explicit operator
TLS configuration. It requires a matching pre-staged Fabric manifest and never
falls back to SSH or unauthenticated transport. Missing capabilities, missing
trust material, conflicting replays, and incomplete bundle execution facts stay
`UNKNOWN` or `FAIL` according to the governing contract; they are not converted
to RAVEL success.
