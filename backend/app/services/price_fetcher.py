"""
Built-in price fetching service.

Replaces the n8n dependency by:
- Fetching real GPU prices from Azure Retail Prices API (free, no auth)
- Seeding curated prices for AWS and GCP
- Seeding up-to-date API provider pricing
- Running on startup + every 6 hours via asyncio background task
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete

from app.core.database import async_session
from app.models.models import LiveGPUPrice, LiveAPIPrice

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 6 * 3600  # 6 hours

# ── GPU type mapping for Azure VM series ──
AZURE_GPU_MAP = {
    "Standard_ND96amsr_A100_v4": ("A100_80GB", 8, 80),
    "Standard_ND96asr_v4": ("A100_40GB", 8, 40),
    "Standard_NC24ads_A100_v4": ("A100_80GB", 1, 80),
    "Standard_NC48ads_A100_v4": ("A100_80GB", 2, 80),
    "Standard_NC96ads_A100_v4": ("A100_80GB", 4, 80),
    "Standard_NV36ads_A10_v5": ("A10G_24GB", 1, 24),
    "Standard_NV72ads_A10_v5": ("A10G_24GB", 2, 24),
    "Standard_NC4as_T4_v3": ("T4_16GB", 1, 16),
    "Standard_NC8as_T4_v3": ("T4_16GB", 1, 16),
    "Standard_NC16as_T4_v3": ("T4_16GB", 1, 16),
    "Standard_NC64as_T4_v3": ("T4_16GB", 4, 16),
}

# Known Azure GPU SKU prefixes to filter
AZURE_GPU_PREFIXES = ("Standard_NC", "Standard_ND", "Standard_NV")


async def fetch_azure_prices() -> list[dict]:
    """Fetch real GPU VM prices from Azure Retail Prices API."""
    base_url = "https://prices.azure.com/api/retail/prices"
    params = {
        "$filter": (
            "serviceName eq 'Virtual Machines' "
            "and armRegionName eq 'eastus' "
            "and priceType eq 'Consumption' "
            "and currencyCode eq 'USD'"
        ),
    }

    instances: dict[str, dict] = {}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            url = base_url
            pages = 0
            while url and pages < 10:
                resp = await client.get(url, params=params if pages == 0 else None)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("Items", []):
                    sku = item.get("armSkuName", "")
                    if not sku or not any(sku.startswith(p) for p in AZURE_GPU_PREFIXES):
                        continue
                    if sku not in AZURE_GPU_MAP:
                        continue
                    # Skip Windows, Low Priority, Spot
                    meter = item.get("meterName", "")
                    if "Windows" in meter or "Low Priority" in meter or "Spot" in meter:
                        continue
                    product_name = item.get("productName", "")
                    if "Windows" in product_name:
                        continue

                    price = item.get("retailPrice", 0)
                    if price <= 0:
                        continue

                    gpu_type, gpu_count, vram_per_gpu = AZURE_GPU_MAP[sku]

                    # Keep cheapest price per SKU (avoid duplicates)
                    if sku in instances and instances[sku]["cost_per_hour"] <= price:
                        continue

                    vcpus = int(item.get("effectiveStartDate", "0").split("T")[0][:4] or 0)
                    instances[sku] = {
                        "provider": "azure",
                        "instance_type": sku,
                        "gpu_type": gpu_type,
                        "gpu_count": gpu_count,
                        "vram_per_gpu_gb": vram_per_gpu,
                        "total_vram_gb": gpu_count * vram_per_gpu,
                        "cost_per_hour": round(price, 4),
                        "region": "eastus",
                        "storage_cost_per_gb_month": 0.05,
                        "bandwidth_cost_per_gb": 0.087,
                        "vcpus": 0,
                        "ram_gb": 0,
                    }

                url = data.get("NextPageLink")
                pages += 1

        result = list(instances.values())
        if result:
            logger.info(f"Azure API: fetched {len(result)} GPU instance prices")
            return result

    except Exception as e:
        logger.warning(f"Azure price fetch failed: {e}")

    # Fallback to curated Azure prices if API fails
    return _get_azure_curated()


def _get_azure_curated() -> list[dict]:
    """Curated Azure GPU instance prices."""
    return [
        {"provider": "azure", "instance_type": "Standard_ND96amsr_A100_v4", "gpu_type": "A100_80GB", "gpu_count": 8, "vram_per_gpu_gb": 80, "total_vram_gb": 640, "cost_per_hour": 32.77, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 96, "ram_gb": 1900},
        {"provider": "azure", "instance_type": "Standard_ND96asr_v4", "gpu_type": "A100_40GB", "gpu_count": 8, "vram_per_gpu_gb": 40, "total_vram_gb": 320, "cost_per_hour": 27.20, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 96, "ram_gb": 900},
        {"provider": "azure", "instance_type": "Standard_NC24ads_A100_v4", "gpu_type": "A100_80GB", "gpu_count": 1, "vram_per_gpu_gb": 80, "total_vram_gb": 80, "cost_per_hour": 3.67, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 24, "ram_gb": 220},
        {"provider": "azure", "instance_type": "Standard_NC48ads_A100_v4", "gpu_type": "A100_80GB", "gpu_count": 2, "vram_per_gpu_gb": 80, "total_vram_gb": 160, "cost_per_hour": 7.35, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 48, "ram_gb": 440},
        {"provider": "azure", "instance_type": "Standard_NV36ads_A10_v5", "gpu_type": "A10G_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 1.80, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 36, "ram_gb": 440},
        {"provider": "azure", "instance_type": "Standard_NV72ads_A10_v5", "gpu_type": "A10G_24GB", "gpu_count": 2, "vram_per_gpu_gb": 24, "total_vram_gb": 48, "cost_per_hour": 3.60, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 72, "ram_gb": 880},
        {"provider": "azure", "instance_type": "Standard_NC4as_T4_v3", "gpu_type": "T4_16GB", "gpu_count": 1, "vram_per_gpu_gb": 16, "total_vram_gb": 16, "cost_per_hour": 0.526, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 4, "ram_gb": 28},
        {"provider": "azure", "instance_type": "Standard_NC8as_T4_v3", "gpu_type": "T4_16GB", "gpu_count": 1, "vram_per_gpu_gb": 16, "total_vram_gb": 16, "cost_per_hour": 0.752, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 8, "ram_gb": 56},
        {"provider": "azure", "instance_type": "Standard_NC16as_T4_v3", "gpu_type": "T4_16GB", "gpu_count": 1, "vram_per_gpu_gb": 16, "total_vram_gb": 16, "cost_per_hour": 1.204, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 16, "ram_gb": 110},
        {"provider": "azure", "instance_type": "Standard_NC64as_T4_v3", "gpu_type": "T4_16GB", "gpu_count": 4, "vram_per_gpu_gb": 16, "total_vram_gb": 64, "cost_per_hour": 4.352, "region": "eastus", "storage_cost_per_gb_month": 0.05, "bandwidth_cost_per_gb": 0.087, "vcpus": 64, "ram_gb": 440},
    ]


def get_aws_curated_prices() -> list[dict]:
    """Curated AWS GPU instance prices (no free public API)."""
    return [
        {"provider": "aws", "instance_type": "p5.48xlarge", "gpu_type": "H100_80GB", "gpu_count": 8, "vram_per_gpu_gb": 80, "total_vram_gb": 640, "cost_per_hour": 98.32, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 192, "ram_gb": 2048},
        {"provider": "aws", "instance_type": "p4d.24xlarge", "gpu_type": "A100_40GB", "gpu_count": 8, "vram_per_gpu_gb": 40, "total_vram_gb": 320, "cost_per_hour": 32.77, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 96, "ram_gb": 1152},
        {"provider": "aws", "instance_type": "p4de.24xlarge", "gpu_type": "A100_80GB", "gpu_count": 8, "vram_per_gpu_gb": 80, "total_vram_gb": 640, "cost_per_hour": 40.97, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 96, "ram_gb": 1152},
        {"provider": "aws", "instance_type": "g5.xlarge", "gpu_type": "A10G_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 1.006, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 4, "ram_gb": 16},
        {"provider": "aws", "instance_type": "g5.2xlarge", "gpu_type": "A10G_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 1.212, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 8, "ram_gb": 32},
        {"provider": "aws", "instance_type": "g5.4xlarge", "gpu_type": "A10G_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 1.624, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 16, "ram_gb": 64},
        {"provider": "aws", "instance_type": "g5.12xlarge", "gpu_type": "A10G_24GB", "gpu_count": 4, "vram_per_gpu_gb": 24, "total_vram_gb": 96, "cost_per_hour": 5.672, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 48, "ram_gb": 192},
        {"provider": "aws", "instance_type": "g5.48xlarge", "gpu_type": "A10G_24GB", "gpu_count": 8, "vram_per_gpu_gb": 24, "total_vram_gb": 192, "cost_per_hour": 16.288, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 192, "ram_gb": 768},
        {"provider": "aws", "instance_type": "g6.xlarge", "gpu_type": "L4_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 0.8048, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 4, "ram_gb": 16},
        {"provider": "aws", "instance_type": "g6.2xlarge", "gpu_type": "L4_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 0.9776, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 8, "ram_gb": 32},
        {"provider": "aws", "instance_type": "g6.12xlarge", "gpu_type": "L4_24GB", "gpu_count": 4, "vram_per_gpu_gb": 24, "total_vram_gb": 96, "cost_per_hour": 4.6016, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 48, "ram_gb": 192},
        {"provider": "aws", "instance_type": "g4dn.xlarge", "gpu_type": "T4_16GB", "gpu_count": 1, "vram_per_gpu_gb": 16, "total_vram_gb": 16, "cost_per_hour": 0.526, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 4, "ram_gb": 16},
        {"provider": "aws", "instance_type": "g4dn.12xlarge", "gpu_type": "T4_16GB", "gpu_count": 4, "vram_per_gpu_gb": 16, "total_vram_gb": 64, "cost_per_hour": 3.912, "region": "us-east-1", "storage_cost_per_gb_month": 0.08, "bandwidth_cost_per_gb": 0.09, "vcpus": 48, "ram_gb": 192},
    ]


def get_gcp_curated_prices() -> list[dict]:
    """Curated GCP GPU instance prices (no free public API)."""
    return [
        {"provider": "gcp", "instance_type": "a3-highgpu-8g", "gpu_type": "H100_80GB", "gpu_count": 8, "vram_per_gpu_gb": 80, "total_vram_gb": 640, "cost_per_hour": 101.22, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 208, "ram_gb": 1872},
        {"provider": "gcp", "instance_type": "a2-ultragpu-1g", "gpu_type": "A100_80GB", "gpu_count": 1, "vram_per_gpu_gb": 80, "total_vram_gb": 80, "cost_per_hour": 5.07, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 12, "ram_gb": 170},
        {"provider": "gcp", "instance_type": "a2-highgpu-1g", "gpu_type": "A100_40GB", "gpu_count": 1, "vram_per_gpu_gb": 40, "total_vram_gb": 40, "cost_per_hour": 3.67, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 12, "ram_gb": 85},
        {"provider": "gcp", "instance_type": "a2-highgpu-2g", "gpu_type": "A100_40GB", "gpu_count": 2, "vram_per_gpu_gb": 40, "total_vram_gb": 80, "cost_per_hour": 7.35, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 24, "ram_gb": 170},
        {"provider": "gcp", "instance_type": "a2-highgpu-4g", "gpu_type": "A100_40GB", "gpu_count": 4, "vram_per_gpu_gb": 40, "total_vram_gb": 160, "cost_per_hour": 14.69, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 48, "ram_gb": 340},
        {"provider": "gcp", "instance_type": "a2-highgpu-8g", "gpu_type": "A100_40GB", "gpu_count": 8, "vram_per_gpu_gb": 40, "total_vram_gb": 320, "cost_per_hour": 29.39, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 96, "ram_gb": 680},
        {"provider": "gcp", "instance_type": "g2-standard-4", "gpu_type": "L4_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 0.7211, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 4, "ram_gb": 16},
        {"provider": "gcp", "instance_type": "g2-standard-8", "gpu_type": "L4_24GB", "gpu_count": 1, "vram_per_gpu_gb": 24, "total_vram_gb": 24, "cost_per_hour": 0.8535, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 8, "ram_gb": 32},
        {"provider": "gcp", "instance_type": "g2-standard-24", "gpu_type": "L4_24GB", "gpu_count": 2, "vram_per_gpu_gb": 24, "total_vram_gb": 48, "cost_per_hour": 2.3838, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 24, "ram_gb": 96},
        {"provider": "gcp", "instance_type": "g2-standard-48", "gpu_type": "L4_24GB", "gpu_count": 4, "vram_per_gpu_gb": 24, "total_vram_gb": 96, "cost_per_hour": 4.7677, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 48, "ram_gb": 192},
        {"provider": "gcp", "instance_type": "n1-standard-4-t4", "gpu_type": "T4_16GB", "gpu_count": 1, "vram_per_gpu_gb": 16, "total_vram_gb": 16, "cost_per_hour": 0.545, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 4, "ram_gb": 15},
        {"provider": "gcp", "instance_type": "n1-standard-8-t4", "gpu_type": "T4_16GB", "gpu_count": 1, "vram_per_gpu_gb": 16, "total_vram_gb": 16, "cost_per_hour": 0.735, "region": "us-central1", "storage_cost_per_gb_month": 0.04, "bandwidth_cost_per_gb": 0.12, "vcpus": 8, "ram_gb": 30},
    ]


def get_api_provider_prices() -> list[dict]:
    """Up-to-date API provider pricing (per 1M tokens)."""
    return [
        {"provider": "OpenAI", "model": "GPT-4o", "input_cost_per_million": 2.50, "output_cost_per_million": 10.00},
        {"provider": "OpenAI", "model": "GPT-4o mini", "input_cost_per_million": 0.15, "output_cost_per_million": 0.60},
        {"provider": "OpenAI", "model": "o1", "input_cost_per_million": 15.00, "output_cost_per_million": 60.00},
        {"provider": "OpenAI", "model": "o3-mini", "input_cost_per_million": 1.10, "output_cost_per_million": 4.40},
        {"provider": "Anthropic", "model": "Claude Sonnet 4", "input_cost_per_million": 3.00, "output_cost_per_million": 15.00},
        {"provider": "Anthropic", "model": "Claude Opus 4", "input_cost_per_million": 15.00, "output_cost_per_million": 75.00},
        {"provider": "Anthropic", "model": "Claude Haiku 3.5", "input_cost_per_million": 0.80, "output_cost_per_million": 4.00},
        {"provider": "Google", "model": "Gemini 2.0 Flash", "input_cost_per_million": 0.10, "output_cost_per_million": 0.40},
        {"provider": "Google", "model": "Gemini 1.5 Pro", "input_cost_per_million": 1.25, "output_cost_per_million": 5.00},
        {"provider": "Mistral", "model": "Mistral Large", "input_cost_per_million": 2.00, "output_cost_per_million": 6.00},
        {"provider": "Mistral", "model": "Mistral Small", "input_cost_per_million": 0.20, "output_cost_per_million": 0.60},
        {"provider": "DeepSeek", "model": "DeepSeek V3", "input_cost_per_million": 0.27, "output_cost_per_million": 1.10},
    ]


async def _save_gpu_prices(prices: list[dict], provider: str, source: str):
    """Save GPU prices to DB, replacing old entries for the provider."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        await session.execute(
            delete(LiveGPUPrice).where(LiveGPUPrice.provider == provider)
        )
        for p in prices:
            session.add(LiveGPUPrice(
                provider=p["provider"],
                instance_type=p["instance_type"],
                gpu_type=p["gpu_type"],
                gpu_count=p["gpu_count"],
                vram_per_gpu_gb=p["vram_per_gpu_gb"],
                total_vram_gb=p["total_vram_gb"],
                cost_per_hour=p["cost_per_hour"],
                region=p.get("region", "us-east-1"),
                storage_cost_per_gb_month=p.get("storage_cost_per_gb_month", 0.08),
                bandwidth_cost_per_gb=p.get("bandwidth_cost_per_gb", 0.09),
                vcpus=p.get("vcpus", 0),
                ram_gb=p.get("ram_gb", 0),
                source=source,
                fetched_at=now,
            ))
        await session.commit()


async def _save_api_prices(prices: list[dict], source: str):
    """Save API provider prices to DB, replacing all old entries."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        await session.execute(delete(LiveAPIPrice))
        for p in prices:
            session.add(LiveAPIPrice(
                provider=p["provider"],
                model=p["model"],
                input_cost_per_million=p["input_cost_per_million"],
                output_cost_per_million=p["output_cost_per_million"],
                source=source,
                fetched_at=now,
            ))
        await session.commit()


async def refresh_all_prices():
    """Fetch and store all prices."""
    gpu_total = 0

    # AWS (curated)
    aws = get_aws_curated_prices()
    await _save_gpu_prices(aws, "aws", "built-in")
    gpu_total += len(aws)

    # GCP (curated)
    gcp = get_gcp_curated_prices()
    await _save_gpu_prices(gcp, "gcp", "built-in")
    gpu_total += len(gcp)

    # Azure (live API with curated fallback)
    azure = await fetch_azure_prices()
    await _save_gpu_prices(azure, "azure", "azure-api")
    gpu_total += len(azure)

    # API provider prices
    api_prices = get_api_provider_prices()
    await _save_api_prices(api_prices, "built-in")

    logger.info(
        f"Price refresh complete: {gpu_total} GPU instances, "
        f"{len(api_prices)} API models"
    )
    return {"gpu_count": gpu_total, "api_count": len(api_prices)}


async def start_price_refresh_loop():
    """Background loop: refresh prices on startup, then every 6 hours."""
    # Initial refresh
    try:
        await refresh_all_prices()
    except Exception as e:
        logger.error(f"Initial price refresh failed: {e}")

    # Periodic refresh
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            await refresh_all_prices()
        except Exception as e:
            logger.error(f"Periodic price refresh failed: {e}")
