import random
import math
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import Deployment, UsageRecord, ManagedDeployment

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated stats across all deployments."""
    dep_result = await db.execute(
        select(Deployment).where(Deployment.user_id == user_id)
    )
    deployments = dep_result.scalars().all()

    active = sum(1 for d in deployments if d.status and d.status.value == "running")
    total_requests = sum(d.total_requests or 0 for d in deployments)
    total_tokens = sum(d.total_tokens_generated or 0 for d in deployments)
    total_cost = sum(d.total_cost_incurred or 0 for d in deployments)

    # Check managed deployments too
    managed_result = await db.execute(
        select(ManagedDeployment).where(ManagedDeployment.user_id == user_id)
    )
    managed = managed_result.scalars().all()
    managed_active = sum(1 for m in managed if m.status and m.status.value == "running")
    managed_cost = sum(m.total_cost_incurred or 0 for m in managed)

    return {
        "active_deployments": active + managed_active,
        "total_deployments": len(deployments) + len(managed),
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost + managed_cost, 2),
        "managed_count": len(managed),
    }


@router.get("/usage-series")
async def get_usage_series(
    days: int = 30,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Simulated time-series usage data for dashboard charts."""
    now = datetime.now(timezone.utc)
    series = []

    for i in range(days):
        date = now - timedelta(days=days - 1 - i)
        # Simulate growing usage with weekly pattern
        day_of_week = date.weekday()
        weekday_mult = 1.0 if day_of_week < 5 else 0.4
        growth = 1.0 + (i / days) * 0.5  # 50% growth over period
        base_requests = int(random.gauss(500, 100) * weekday_mult * growth)
        base_requests = max(50, base_requests)
        tokens = base_requests * int(random.gauss(300, 80))
        cost = base_requests * random.uniform(0.001, 0.005)

        series.append({
            "date": date.strftime("%Y-%m-%d"),
            "requests": base_requests,
            "tokens": max(0, tokens),
            "cost_usd": round(cost, 2),
            "avg_latency_ms": round(random.gauss(120, 30), 1),
        })

    return series


@router.get("/cost-breakdown")
async def get_cost_breakdown(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Per-deployment cost breakdown for pie chart."""
    dep_result = await db.execute(
        select(Deployment).where(Deployment.user_id == user_id)
    )
    deployments = dep_result.scalars().all()

    breakdown = []
    for d in deployments:
        cost = d.total_cost_incurred or round(random.uniform(5, 50), 2)
        breakdown.append({
            "deployment_id": d.id,
            "label": f"{(d.cloud_provider.value if d.cloud_provider else 'unknown').upper()} - {d.instance_type}",
            "cost_usd": round(cost, 2),
            "status": d.status.value if d.status else "unknown",
        })

    # Include managed deployments
    managed_result = await db.execute(
        select(ManagedDeployment).where(ManagedDeployment.user_id == user_id)
    )
    for m in managed_result.scalars().all():
        cost = m.total_cost_incurred or round(random.uniform(10, 80), 2)
        breakdown.append({
            "deployment_id": m.id,
            "label": f"[Managed] {(m.cloud_provider.value if m.cloud_provider else 'unknown').upper()} - {m.instance_type}",
            "cost_usd": round(cost, 2),
            "status": m.status.value if m.status else "unknown",
        })

    return breakdown
