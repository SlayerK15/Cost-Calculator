"""
Pricing API — webhook endpoints for n8n to push live prices,
and public endpoints for the frontend to check pricing freshness.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select, delete

from app.core.database import async_session
from app.core.config import get_settings
from app.models.models import LiveGPUPrice, LiveAPIPrice

router = APIRouter(prefix="/pricing", tags=["pricing"])

settings = get_settings()

# Simple webhook secret — n8n includes this in the header
WEBHOOK_SECRET = settings.SECRET_KEY


# ── Schemas ──

class GPUPriceUpdate(BaseModel):
    provider: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    vram_per_gpu_gb: float
    total_vram_gb: float
    cost_per_hour: float
    spot_price_per_hour: float | None = None
    region: str = "us-east-1"
    storage_cost_per_gb_month: float = 0.08
    bandwidth_cost_per_gb: float = 0.09
    vcpus: int = 0
    ram_gb: float = 0


class APIPriceUpdate(BaseModel):
    provider: str
    model: str
    input_cost_per_million: float
    output_cost_per_million: float


class BulkGPUPriceUpdate(BaseModel):
    prices: list[GPUPriceUpdate]
    source: str = "n8n"


class BulkAPIPriceUpdate(BaseModel):
    prices: list[APIPriceUpdate]
    source: str = "n8n"


class PricingStatus(BaseModel):
    gpu_prices_count: int
    api_prices_count: int
    gpu_last_updated: str | None
    api_last_updated: str | None
    using_live_prices: bool


# ── Webhook Endpoints (n8n pushes prices here) ──

def _verify_webhook(secret: str | None):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@router.post("/webhook/gpu-prices")
async def update_gpu_prices(
    data: BulkGPUPriceUpdate,
    x_webhook_secret: str | None = Header(None),
):
    """n8n pushes GPU instance pricing here. Replaces all prices for the given provider."""
    _verify_webhook(x_webhook_secret)

    if not data.prices:
        raise HTTPException(status_code=400, detail="No prices provided")

    provider = data.prices[0].provider.lower()
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        # Delete old prices for this provider
        await session.execute(
            delete(LiveGPUPrice).where(LiveGPUPrice.provider == provider)
        )

        # Insert new prices
        for p in data.prices:
            session.add(LiveGPUPrice(
                provider=p.provider.lower(),
                instance_type=p.instance_type,
                gpu_type=p.gpu_type,
                gpu_count=p.gpu_count,
                vram_per_gpu_gb=p.vram_per_gpu_gb,
                total_vram_gb=p.total_vram_gb,
                cost_per_hour=p.cost_per_hour,
                spot_price_per_hour=p.spot_price_per_hour,
                region=p.region,
                storage_cost_per_gb_month=p.storage_cost_per_gb_month,
                bandwidth_cost_per_gb=p.bandwidth_cost_per_gb,
                vcpus=p.vcpus,
                ram_gb=p.ram_gb,
                source=data.source,
                fetched_at=now,
            ))

        await session.commit()

    return {"status": "ok", "provider": provider, "count": len(data.prices)}


@router.post("/webhook/api-prices")
async def update_api_prices(
    data: BulkAPIPriceUpdate,
    x_webhook_secret: str | None = Header(None),
):
    """n8n pushes API provider pricing here. Replaces all API prices."""
    _verify_webhook(x_webhook_secret)

    if not data.prices:
        raise HTTPException(status_code=400, detail="No prices provided")

    now = datetime.now(timezone.utc)

    async with async_session() as session:
        # Delete all old API prices
        await session.execute(delete(LiveAPIPrice))

        for p in data.prices:
            session.add(LiveAPIPrice(
                provider=p.provider,
                model=p.model,
                input_cost_per_million=p.input_cost_per_million,
                output_cost_per_million=p.output_cost_per_million,
                source=data.source,
                fetched_at=now,
            ))

        await session.commit()

    return {"status": "ok", "count": len(data.prices)}


# ── Public Endpoints ──

@router.get("/status", response_model=PricingStatus)
async def get_pricing_status():
    """Check if live pricing is available and when it was last updated."""
    async with async_session() as session:
        gpu_result = await session.execute(
            select(LiveGPUPrice).order_by(LiveGPUPrice.fetched_at.desc()).limit(1)
        )
        gpu_latest = gpu_result.scalar_one_or_none()

        api_result = await session.execute(
            select(LiveAPIPrice).order_by(LiveAPIPrice.fetched_at.desc()).limit(1)
        )
        api_latest = api_result.scalar_one_or_none()

        gpu_count_result = await session.execute(select(LiveGPUPrice))
        gpu_count = len(gpu_count_result.scalars().all())

        api_count_result = await session.execute(select(LiveAPIPrice))
        api_count = len(api_count_result.scalars().all())

    return PricingStatus(
        gpu_prices_count=gpu_count,
        api_prices_count=api_count,
        gpu_last_updated=gpu_latest.fetched_at.isoformat() if gpu_latest else None,
        api_last_updated=api_latest.fetched_at.isoformat() if api_latest else None,
        using_live_prices=gpu_count > 0,
    )


@router.post("/refresh")
async def refresh_prices():
    """Manually trigger a price refresh."""
    from app.services.price_fetcher import refresh_all_prices
    result = await refresh_all_prices()
    return {"status": "ok", **result}


@router.get("/gpu")
async def list_gpu_prices():
    """List all live GPU prices."""
    async with async_session() as session:
        result = await session.execute(
            select(LiveGPUPrice).order_by(LiveGPUPrice.provider, LiveGPUPrice.cost_per_hour)
        )
        prices = result.scalars().all()

    return [
        {
            "provider": p.provider,
            "instance_type": p.instance_type,
            "gpu_type": p.gpu_type,
            "gpu_count": p.gpu_count,
            "total_vram_gb": p.total_vram_gb,
            "cost_per_hour": p.cost_per_hour,
            "spot_price_per_hour": p.spot_price_per_hour,
            "region": p.region,
            "fetched_at": p.fetched_at.isoformat() if p.fetched_at else None,
        }
        for p in prices
    ]


@router.get("/api-providers")
async def list_api_prices():
    """List all live API provider prices."""
    async with async_session() as session:
        result = await session.execute(
            select(LiveAPIPrice).order_by(LiveAPIPrice.provider, LiveAPIPrice.model)
        )
        prices = result.scalars().all()

    return [
        {
            "provider": p.provider,
            "model": p.model,
            "input_cost_per_million": p.input_cost_per_million,
            "output_cost_per_million": p.output_cost_per_million,
            "fetched_at": p.fetched_at.isoformat() if p.fetched_at else None,
        }
        for p in prices
    ]
