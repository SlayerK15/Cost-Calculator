"""
GPU catalog with specs and cloud pricing for AWS, GCP, and Azure.
Hardcoded fallback prices (early 2025). Live prices from n8n override these.
"""

from dataclasses import dataclass


@dataclass
class GPUSpec:
    name: str
    vram_gb: float
    memory_bandwidth_gbps: float
    fp16_tflops: float


@dataclass
class CloudInstance:
    provider: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    vram_per_gpu_gb: float
    total_vram_gb: float
    vcpus: int
    ram_gb: float
    cost_per_hour: float
    region: str
    storage_cost_per_gb_month: float
    bandwidth_cost_per_gb: float
    spot_price_per_hour: float | None = None


# ── GPU Specifications ──
GPU_SPECS: dict[str, GPUSpec] = {
    "A100_80GB": GPUSpec("A100 80GB", 80, 2039, 312),
    "A100_40GB": GPUSpec("A100 40GB", 40, 1555, 312),
    "H100_80GB": GPUSpec("H100 80GB", 80, 3350, 989),
    "A10G_24GB": GPUSpec("A10G 24GB", 24, 600, 125),
    "L4_24GB": GPUSpec("L4 24GB", 24, 300, 121),
    "T4_16GB": GPUSpec("T4 16GB", 16, 320, 65),
    "V100_16GB": GPUSpec("V100 16GB", 16, 900, 125),
    "L40S_48GB": GPUSpec("L40S 48GB", 48, 864, 362),
}

# ── Hardcoded Fallback Instances (used when no live prices available) ──

AWS_INSTANCES: list[CloudInstance] = [
    CloudInstance("aws", "p5.48xlarge", "H100_80GB", 8, 80, 640, 192, 2048, 98.32, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "p4d.24xlarge", "A100_40GB", 8, 40, 320, 96, 1152, 32.77, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "p4de.24xlarge", "A100_80GB", 8, 80, 640, 96, 1152, 40.97, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g5.xlarge", "A10G_24GB", 1, 24, 24, 4, 16, 1.006, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g5.2xlarge", "A10G_24GB", 1, 24, 24, 8, 32, 1.212, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g5.4xlarge", "A10G_24GB", 1, 24, 24, 16, 64, 1.624, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g5.12xlarge", "A10G_24GB", 4, 24, 96, 48, 192, 5.672, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g5.48xlarge", "A10G_24GB", 8, 24, 192, 192, 768, 16.288, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g6.xlarge", "L4_24GB", 1, 24, 24, 4, 16, 0.8048, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g6.2xlarge", "L4_24GB", 1, 24, 24, 8, 32, 0.9776, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g6.12xlarge", "L4_24GB", 4, 24, 96, 48, 192, 4.6016, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g4dn.xlarge", "T4_16GB", 1, 16, 16, 4, 16, 0.526, "us-east-1", 0.08, 0.09),
    CloudInstance("aws", "g4dn.12xlarge", "T4_16GB", 4, 16, 64, 48, 192, 3.912, "us-east-1", 0.08, 0.09),
]

GCP_INSTANCES: list[CloudInstance] = [
    CloudInstance("gcp", "a3-highgpu-8g", "H100_80GB", 8, 80, 640, 208, 1872, 101.22, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "a2-ultragpu-1g", "A100_80GB", 1, 80, 80, 12, 170, 5.07, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "a2-highgpu-1g", "A100_40GB", 1, 40, 40, 12, 85, 3.67, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "a2-highgpu-2g", "A100_40GB", 2, 40, 80, 24, 170, 7.35, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "a2-highgpu-4g", "A100_40GB", 4, 40, 160, 48, 340, 14.69, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "a2-highgpu-8g", "A100_40GB", 8, 40, 320, 96, 680, 29.39, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "g2-standard-4", "L4_24GB", 1, 24, 24, 4, 16, 0.7211, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "g2-standard-8", "L4_24GB", 1, 24, 24, 8, 32, 0.8535, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "g2-standard-24", "L4_24GB", 2, 24, 48, 24, 96, 2.3838, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "g2-standard-48", "L4_24GB", 4, 24, 96, 48, 192, 4.7677, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "n1-standard-4-t4", "T4_16GB", 1, 16, 16, 4, 15, 0.545, "us-central1", 0.04, 0.12),
    CloudInstance("gcp", "n1-standard-8-t4", "T4_16GB", 1, 16, 16, 8, 30, 0.735, "us-central1", 0.04, 0.12),
]

AZURE_INSTANCES: list[CloudInstance] = [
    CloudInstance("azure", "Standard_ND96amsr_A100_v4", "A100_80GB", 8, 80, 640, 96, 1900, 32.77, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_ND96asr_v4", "A100_40GB", 8, 40, 320, 96, 900, 27.20, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NC24ads_A100_v4", "A100_80GB", 1, 80, 80, 24, 220, 3.67, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NC48ads_A100_v4", "A100_80GB", 2, 80, 160, 48, 440, 7.35, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NV36ads_A10_v5", "A10G_24GB", 1, 24, 24, 36, 440, 1.80, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NV72ads_A10_v5", "A10G_24GB", 2, 24, 48, 72, 880, 3.60, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NC4as_T4_v3", "T4_16GB", 1, 16, 16, 4, 28, 0.526, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NC8as_T4_v3", "T4_16GB", 1, 16, 16, 8, 56, 0.752, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NC16as_T4_v3", "T4_16GB", 1, 16, 16, 16, 110, 1.204, "eastus", 0.05, 0.087),
    CloudInstance("azure", "Standard_NC64as_T4_v3", "T4_16GB", 4, 16, 64, 64, 440, 4.352, "eastus", 0.05, 0.087),
]

# ── Hardcoded fallback catalog ──
_FALLBACK_INSTANCES: dict[str, list[CloudInstance]] = {
    "aws": AWS_INSTANCES,
    "gcp": GCP_INSTANCES,
    "azure": AZURE_INSTANCES,
}

# ── In-memory cache for live prices (populated from DB) ──
_live_instances_cache: dict[str, list[CloudInstance]] = {}
_cache_timestamp: float = 0
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _load_live_prices_sync():
    """Try to load live prices from DB into cache. Non-blocking fallback to hardcoded."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — schedule the load
            return  # Will use fallback; async version loads on next call
    except RuntimeError:
        pass


async def load_live_prices():
    """Load live GPU prices from DB into the in-memory cache."""
    import time
    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.models import LiveGPUPrice

    global _live_instances_cache, _cache_timestamp

    now = time.time()
    if _live_instances_cache and (now - _cache_timestamp) < _CACHE_TTL_SECONDS:
        return  # Cache still fresh

    try:
        async with async_session() as session:
            result = await session.execute(select(LiveGPUPrice))
            rows = result.scalars().all()

        if not rows:
            _live_instances_cache = {}
            _cache_timestamp = now
            return

        by_provider: dict[str, list[CloudInstance]] = {}
        for r in rows:
            inst = CloudInstance(
                provider=r.provider,
                instance_type=r.instance_type,
                gpu_type=r.gpu_type,
                gpu_count=r.gpu_count,
                vram_per_gpu_gb=r.vram_per_gpu_gb,
                total_vram_gb=r.total_vram_gb,
                vcpus=r.vcpus or 0,
                ram_gb=r.ram_gb or 0,
                cost_per_hour=r.cost_per_hour,
                region=r.region or "us-east-1",
                storage_cost_per_gb_month=r.storage_cost_per_gb_month or 0.08,
                bandwidth_cost_per_gb=r.bandwidth_cost_per_gb or 0.09,
                spot_price_per_hour=r.spot_price_per_hour,
            )
            by_provider.setdefault(r.provider, []).append(inst)

        _live_instances_cache = by_provider
        _cache_timestamp = now
    except Exception:
        # If DB fails, keep using whatever we had
        pass


def get_instances_for_provider(provider: str) -> list[CloudInstance]:
    """Get instances for a provider. Uses live prices if available, else hardcoded fallback."""
    p = provider.lower()
    if p in _live_instances_cache and _live_instances_cache[p]:
        return _live_instances_cache[p]
    return _FALLBACK_INSTANCES.get(p, [])


def get_all_instances() -> list[CloudInstance]:
    result = []
    for provider in ["aws", "gcp", "azure"]:
        result.extend(get_instances_for_provider(provider))
    return result


def is_using_live_prices(provider: str) -> bool:
    p = provider.lower()
    return p in _live_instances_cache and len(_live_instances_cache[p]) > 0
