"""Optional resource-aware placement policy with no ML runtime dependency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Literal, Protocol


class DevicePolicy(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"


class OffloadPolicy(str, Enum):
    NONE = "none"
    SEQUENTIAL_CPU = "sequential-cpu"


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    device: DevicePolicy = DevicePolicy.AUTO
    offload: OffloadPolicy = OffloadPolicy.NONE
    gpu_reserve_bytes: int = 0
    maximum_vram_bytes: int | None = None
    allow_cpu_fallback: bool = True
    allow_oom_recovery: bool = True


@dataclass(frozen=True, slots=True)
class ProviderFootprint:
    parameter_bytes: int
    workspace_bytes: int
    peak_module_bytes: int
    dtype: str


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    cuda_discovered: bool
    cuda_kernel_works: bool
    free_vram_bytes: int
    total_vram_bytes: int
    available_cpu_bytes: int
    dtype_supported: bool
    process_rss_bytes: int


@dataclass(frozen=True, slots=True)
class PlacementDecision:
    device: DevicePolicy
    offload: OffloadPolicy
    reason: str
    peak_vram_reservation: int
    parameter_residency: str
    total_memory_note: str


@dataclass(frozen=True, slots=True)
class ExecutionExperience:
    """Scoped observation suitable for RAVEL memory, never a universal rule."""

    provider_id: str
    model_id: str
    task_class: str
    device: DevicePolicy
    offload: OffloadPolicy
    dtype: str
    memory_budget_bytes: int | None
    runtime_ms: float | None
    outcome: Literal["success", "failure", "unknown"]
    verifier_status: Literal["PASS", "FAIL", "UNKNOWN"]
    evidence_quality: str
    oom: bool = False

    def __post_init__(self) -> None:
        if not self.provider_id or not self.model_id or not self.task_class:
            raise ValueError("execution experience identity and task scope are required")
        if self.memory_budget_bytes is not None and self.memory_budget_bytes < 0:
            raise ValueError("memory_budget_bytes must be non-negative")
        if self.runtime_ms is not None and self.runtime_ms < 0:
            raise ValueError("runtime_ms must be non-negative")


class ResourceBackend(Protocol):
    def snapshot(self, dtype: str) -> ResourceSnapshot: ...

    def execute(self, placement: PlacementDecision, operation: Callable[[], object]) -> object: ...


class CudaOutOfMemory(RuntimeError):
    """Optional backend signal used for one bounded placement recovery."""


def _cuda_usable(snapshot: ResourceSnapshot) -> bool:
    return snapshot.cuda_discovered and snapshot.cuda_kernel_works and snapshot.dtype_supported


def choose_placement(
    policy: RuntimePolicy,
    footprint: ProviderFootprint,
    snapshot: ResourceSnapshot,
) -> PlacementDecision:
    """Choose placement from observations; discovery alone never proves execution."""

    required_full = footprint.parameter_bytes + footprint.workspace_bytes
    reserve = max(policy.gpu_reserve_bytes, 0)
    available = max(snapshot.free_vram_bytes - reserve, 0)
    if policy.maximum_vram_bytes is not None:
        available = min(available, max(policy.maximum_vram_bytes - reserve, 0))
    usable = _cuda_usable(snapshot)
    if policy.device == DevicePolicy.CPU:
        return PlacementDecision(
            DevicePolicy.CPU,
            OffloadPolicy.NONE,
            "cpu_requested",
            0,
            "system-ram",
            "CPU placement avoids accelerator residency; it is not an algorithmic result.",
        )
    if usable and policy.offload == OffloadPolicy.NONE and required_full <= available:
        return PlacementDecision(
            DevicePolicy.CUDA,
            OffloadPolicy.NONE,
            "full_cuda_fits_observed_budget",
            required_full,
            "cuda",
            "Parameters remain resident on CUDA for this placement.",
        )
    sequential_required = footprint.peak_module_bytes + footprint.workspace_bytes
    if usable and policy.offload == OffloadPolicy.SEQUENTIAL_CPU:
        if sequential_required <= available and footprint.parameter_bytes <= snapshot.available_cpu_bytes:
            return PlacementDecision(
                DevicePolicy.CUDA,
                OffloadPolicy.SEQUENTIAL_CPU,
                "sequential_cpu_offload_fits_observed_budget",
                sequential_required,
                "system-ram-between-module-executions",
                "Sequential offload trades VRAM for system RAM; total memory is not reduced.",
            )
    if usable and policy.device == DevicePolicy.AUTO and sequential_required <= available:
        return PlacementDecision(
            DevicePolicy.CUDA,
            OffloadPolicy.SEQUENTIAL_CPU,
            "auto_selected_sequential_cpu_offload",
            sequential_required,
            "system-ram-between-module-executions",
            "Sequential offload trades VRAM for system RAM; total memory is not reduced.",
        )
    if policy.allow_cpu_fallback:
        return PlacementDecision(
            DevicePolicy.CPU,
            OffloadPolicy.NONE,
            "cuda_unavailable_or_budget_insufficient_cpu_fallback",
            0,
            "system-ram",
            "Fallback is a scoped execution observation, not evidence of superiority.",
        )
    return PlacementDecision(
        DevicePolicy.CUDA,
        policy.offload,
        "cuda_required_but_observed_requirements_unmet",
        0,
        "unknown",
        "Execution must fail closed if the requested placement cannot be established.",
    )


def execute_with_bounded_recovery(
    backend: ResourceBackend,
    policy: RuntimePolicy,
    footprint: ProviderFootprint,
    operation: Callable[[], object],
) -> tuple[object, PlacementDecision, bool]:
    """Execute once, then allow at most one sequential/CPU recovery."""

    snapshot = backend.snapshot(footprint.dtype)
    placement = choose_placement(policy, footprint, snapshot)
    try:
        return backend.execute(placement, operation), placement, False
    except CudaOutOfMemory:
        if not policy.allow_oom_recovery or placement.device != DevicePolicy.CUDA:
            raise
        recovery_policy = RuntimePolicy(
            device=DevicePolicy.AUTO,
            offload=OffloadPolicy.SEQUENTIAL_CPU,
            gpu_reserve_bytes=policy.gpu_reserve_bytes,
            maximum_vram_bytes=policy.maximum_vram_bytes,
            allow_cpu_fallback=policy.allow_cpu_fallback,
            allow_oom_recovery=False,
        )
        recovery = choose_placement(recovery_policy, footprint, snapshot)
        return backend.execute(recovery, operation), recovery, True
