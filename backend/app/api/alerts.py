"""Cost Alerts API — budget tracking and threshold alerts for managed deployments."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import random

from app.core.database import get_db
from app.models.models import CostAlert, ManagedDeployment, UserTier
from app.api.subscription import require_tier

router = APIRouter(prefix="/alerts", tags=["cost-alerts"])


# ── Schemas ──

class AlertCreate(BaseModel):
    managed_deployment_id: str
    monthly_budget_usd: float
    alert_threshold_pct: float = 80.0


class AlertUpdate(BaseModel):
    monthly_budget_usd: Optional[float] = None
    alert_threshold_pct: Optional[float] = None


class AlertResponse(BaseModel):
    id: str
    managed_deployment_id: str
    monthly_budget_usd: float
    alert_threshold_pct: float
    current_spend_usd: float
    alert_triggered: bool
    alert_triggered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──

@router.post("/create", response_model=AlertResponse)
async def create_alert(
    data: AlertCreate,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Create a cost alert for a managed deployment."""
    # Verify managed deployment exists
    result = await db.execute(
        select(ManagedDeployment).where(
            ManagedDeployment.id == data.managed_deployment_id,
            ManagedDeployment.user_id == user.id,
        )
    )
    managed = result.scalar_one_or_none()
    if not managed:
        raise HTTPException(status_code=404, detail="Managed deployment not found")

    # Check for existing alert
    existing = await db.execute(
        select(CostAlert).where(
            CostAlert.managed_deployment_id == data.managed_deployment_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Alert already exists for this deployment")

    alert = CostAlert(
        managed_deployment_id=data.managed_deployment_id,
        monthly_budget_usd=data.monthly_budget_usd,
        alert_threshold_pct=data.alert_threshold_pct,
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)

    return _to_response(alert, managed)


@router.get("/list", response_model=list[AlertResponse])
async def list_alerts(
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """List all cost alerts for the user's managed deployments."""
    # Get user's managed deployments
    dep_result = await db.execute(
        select(ManagedDeployment.id).where(ManagedDeployment.user_id == user.id)
    )
    dep_ids = [r[0] for r in dep_result.all()]

    if not dep_ids:
        return []

    result = await db.execute(
        select(CostAlert).where(CostAlert.managed_deployment_id.in_(dep_ids))
    )
    alerts = result.scalars().all()

    responses = []
    for alert in alerts:
        dep_r = await db.execute(
            select(ManagedDeployment).where(ManagedDeployment.id == alert.managed_deployment_id)
        )
        managed = dep_r.scalar_one_or_none()
        if managed:
            responses.append(_to_response(alert, managed))

    return responses


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    data: AlertUpdate,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Update alert thresholds."""
    alert, managed = await _get_alert(alert_id, user.id, db)

    if data.monthly_budget_usd is not None:
        alert.monthly_budget_usd = data.monthly_budget_usd
    if data.alert_threshold_pct is not None:
        alert.alert_threshold_pct = data.alert_threshold_pct

    # Re-evaluate trigger
    current_spend = _simulate_spend(managed)
    threshold_amount = alert.monthly_budget_usd * (alert.alert_threshold_pct / 100)
    if current_spend >= threshold_amount and not alert.alert_triggered:
        alert.alert_triggered = True
        alert.alert_triggered_at = datetime.now(timezone.utc)
    elif current_spend < threshold_amount:
        alert.alert_triggered = False
        alert.alert_triggered_at = None

    await db.flush()
    await db.refresh(alert)
    return _to_response(alert, managed)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cost alert."""
    alert, _ = await _get_alert(alert_id, user.id, db)
    await db.delete(alert)
    await db.flush()
    return {"message": "Alert deleted"}


# ── Helpers ──

async def _get_alert(alert_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(select(CostAlert).where(CostAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    dep_result = await db.execute(
        select(ManagedDeployment).where(
            ManagedDeployment.id == alert.managed_deployment_id,
            ManagedDeployment.user_id == user_id,
        )
    )
    managed = dep_result.scalar_one_or_none()
    if not managed:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert, managed


def _simulate_spend(managed: ManagedDeployment) -> float:
    """Simulate current monthly spend based on hourly cost and uptime."""
    hourly = managed.estimated_hourly_cost or 3.0
    # Simulate ~10-20 days of usage in the current month
    hours_used = random.uniform(240, 480)
    return round(hourly * hours_used, 2)


def _to_response(alert: CostAlert, managed: ManagedDeployment) -> AlertResponse:
    current_spend = _simulate_spend(managed)
    return AlertResponse(
        id=alert.id,
        managed_deployment_id=alert.managed_deployment_id,
        monthly_budget_usd=alert.monthly_budget_usd,
        alert_threshold_pct=alert.alert_threshold_pct,
        current_spend_usd=current_spend,
        alert_triggered=alert.alert_triggered,
        alert_triggered_at=alert.alert_triggered_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )
