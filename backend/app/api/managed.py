from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.models import (
    ManagedDeployment, ManagedDeploymentStatus,
    CloudCredential, CredentialStatus, Deployment,
    UserTier, CloudProvider, DeploymentMetric,
)
from app.api.subscription import require_tier
from app.services.monitoring_service import generate_metrics_snapshot, generate_time_series, generate_scaling_events

router = APIRouter(prefix="/managed", tags=["managed-deployment"])


# ── Schemas ──

class ManagedDeployRequest(BaseModel):
    deployment_id: str  # reference to self-deploy configs
    credential_id: str
    autoscaling_enabled: bool = False
    min_replicas: int = 1
    max_replicas: int = 3
    target_gpu_utilization: float = 0.7


class ManagedDeployResponse(BaseModel):
    id: str
    deployment_id: Optional[str]
    credential_id: str
    status: str
    cloud_provider: str
    region: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    cluster_endpoint: Optional[str]
    autoscaling_enabled: bool
    min_replicas: int
    max_replicas: int
    target_gpu_utilization: float
    health_status: str
    estimated_hourly_cost: float
    total_cost_incurred: float
    uptime_seconds: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScaleRequest(BaseModel):
    min_replicas: Optional[int] = None
    max_replicas: Optional[int] = None
    target_gpu_utilization: Optional[float] = None
    autoscaling_enabled: Optional[bool] = None


class MetricsResponse(BaseModel):
    current: dict
    time_series: list[dict]
    summary: dict
    scaling_events: list[dict] = []


# ── Endpoints ──

@router.post("/deploy", response_model=ManagedDeployResponse)
async def create_managed_deployment(
    data: ManagedDeployRequest,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Create a managed cloud deployment from existing deploy configs."""
    # Verify credential exists and is valid
    cred_result = await db.execute(
        select(CloudCredential).where(
            CloudCredential.id == data.credential_id,
            CloudCredential.user_id == user.id,
        )
    )
    cred = cred_result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Cloud credential not found")
    if cred.status != CredentialStatus.VALID:
        raise HTTPException(status_code=400, detail="Credential must be validated before deploying")

    # Verify self-deploy config exists
    dep_result = await db.execute(
        select(Deployment).where(
            Deployment.id == data.deployment_id,
            Deployment.user_id == user.id,
        )
    )
    deployment = dep_result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment config not found")

    # Calculate estimated cost
    from app.services.cost_engine.gpu_catalog import get_instances_for_provider
    hourly_cost = 3.0  # default
    provider_name = deployment.cloud_provider.value if deployment.cloud_provider else "aws"
    for inst in get_instances_for_provider(provider_name):
        if inst.instance_type == deployment.instance_type:
            hourly_cost = inst.cost_per_hour
            break

    managed = ManagedDeployment(
        user_id=user.id,
        deployment_id=deployment.id,
        credential_id=cred.id,
        status=ManagedDeploymentStatus.PROVISIONING_INFRA,
        cloud_provider=deployment.cloud_provider,
        region=deployment.region,
        instance_type=deployment.instance_type,
        gpu_type=deployment.gpu_type,
        gpu_count=deployment.gpu_count,
        autoscaling_enabled=data.autoscaling_enabled,
        min_replicas=data.min_replicas,
        max_replicas=data.max_replicas,
        target_gpu_utilization=data.target_gpu_utilization,
        estimated_hourly_cost=hourly_cost,
        cluster_endpoint=f"https://llm-managed-{deployment.id[:8]}.cloud.example.com",
    )
    db.add(managed)
    await db.flush()

    # Simulate provisioning completion
    managed.status = ManagedDeploymentStatus.RUNNING
    managed.health_status = "healthy"
    managed.last_health_check = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(managed)

    return _to_response(managed)


@router.get("/list", response_model=list[ManagedDeployResponse])
async def list_managed_deployments(
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """List all managed deployments."""
    result = await db.execute(
        select(ManagedDeployment)
        .where(ManagedDeployment.user_id == user.id)
        .order_by(ManagedDeployment.created_at.desc())
    )
    return [_to_response(m) for m in result.scalars().all()]


@router.get("/{managed_id}", response_model=ManagedDeployResponse)
async def get_managed_deployment(
    managed_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Get managed deployment details."""
    managed = await _get_managed(managed_id, user.id, db)
    return _to_response(managed)


@router.get("/{managed_id}/metrics", response_model=MetricsResponse)
async def get_metrics(
    managed_id: str,
    hours: int = 24,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Get metrics for a managed deployment."""
    managed = await _get_managed(managed_id, user.id, db)

    current = generate_metrics_snapshot(
        gpu_count=managed.gpu_count,
        status=managed.status.value,
        autoscaling_enabled=managed.autoscaling_enabled,
        min_replicas=managed.min_replicas,
        max_replicas=managed.max_replicas,
        cost_per_hour=managed.estimated_hourly_cost,
    )

    time_series = generate_time_series(
        hours=hours,
        interval_minutes=15,
        gpu_count=managed.gpu_count,
        cost_per_hour=managed.estimated_hourly_cost,
    )

    # Summary
    total_requests = sum(p["requests_count"] for p in time_series)
    total_tokens = sum(p["tokens_generated"] for p in time_series)
    total_cost = sum(p["cost_usd"] for p in time_series)
    avg_latency = sum(p["avg_latency_ms"] for p in time_series) / max(1, len(time_series))
    avg_gpu = sum(p["gpu_utilization"] for p in time_series) / max(1, len(time_series))

    scaling_events = generate_scaling_events(hours) if managed.autoscaling_enabled else []

    return MetricsResponse(
        current=current,
        time_series=time_series,
        summary={
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 2),
            "avg_latency_ms": round(avg_latency, 1),
            "avg_gpu_utilization": round(avg_gpu, 3),
            "uptime_hours": hours,
        },
        scaling_events=scaling_events,
    )


@router.post("/{managed_id}/scale")
async def scale_deployment(
    managed_id: str,
    data: ScaleRequest,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Update scaling configuration."""
    managed = await _get_managed(managed_id, user.id, db)

    if data.min_replicas is not None:
        managed.min_replicas = data.min_replicas
    if data.max_replicas is not None:
        managed.max_replicas = data.max_replicas
    if data.target_gpu_utilization is not None:
        managed.target_gpu_utilization = data.target_gpu_utilization
    if data.autoscaling_enabled is not None:
        managed.autoscaling_enabled = data.autoscaling_enabled

    await db.flush()
    await db.refresh(managed)
    return {"message": "Scaling configuration updated", "deployment": _to_response(managed)}


@router.post("/{managed_id}/stop")
async def stop_managed_deployment(
    managed_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Stop a running managed deployment."""
    managed = await _get_managed(managed_id, user.id, db)

    if managed.status not in (ManagedDeploymentStatus.RUNNING, ManagedDeploymentStatus.SCALING):
        raise HTTPException(status_code=400, detail=f"Cannot stop deployment in {managed.status.value} state")

    managed.status = ManagedDeploymentStatus.STOPPED
    managed.health_status = "stopped"
    await db.flush()
    return {"message": "Deployment stopped", "status": "stopped"}


@router.post("/{managed_id}/start")
async def start_managed_deployment(
    managed_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Restart a stopped managed deployment."""
    managed = await _get_managed(managed_id, user.id, db)

    if managed.status != ManagedDeploymentStatus.STOPPED:
        raise HTTPException(status_code=400, detail=f"Can only start stopped deployments")

    managed.status = ManagedDeploymentStatus.RUNNING
    managed.health_status = "healthy"
    managed.last_health_check = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Deployment started", "status": "running"}


@router.post("/{managed_id}/teardown")
async def teardown_deployment(
    managed_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Tear down all infrastructure for a managed deployment."""
    managed = await _get_managed(managed_id, user.id, db)

    managed.status = ManagedDeploymentStatus.TERMINATED
    managed.health_status = "terminated"
    managed.cluster_endpoint = None
    await db.flush()
    return {"message": "Infrastructure torn down", "status": "terminated"}


# ── Helpers ──

async def _get_managed(managed_id: str, user_id: str, db: AsyncSession) -> ManagedDeployment:
    result = await db.execute(
        select(ManagedDeployment).where(
            ManagedDeployment.id == managed_id,
            ManagedDeployment.user_id == user_id,
        )
    )
    managed = result.scalar_one_or_none()
    if not managed:
        raise HTTPException(status_code=404, detail="Managed deployment not found")
    return managed


def _to_response(m: ManagedDeployment) -> ManagedDeployResponse:
    return ManagedDeployResponse(
        id=m.id,
        deployment_id=m.deployment_id,
        credential_id=m.credential_id,
        status=m.status.value,
        cloud_provider=m.cloud_provider.value,
        region=m.region,
        instance_type=m.instance_type,
        gpu_type=m.gpu_type,
        gpu_count=m.gpu_count,
        cluster_endpoint=m.cluster_endpoint,
        autoscaling_enabled=m.autoscaling_enabled,
        min_replicas=m.min_replicas,
        max_replicas=m.max_replicas,
        target_gpu_utilization=m.target_gpu_utilization,
        health_status=m.health_status or "unknown",
        estimated_hourly_cost=m.estimated_hourly_cost or 0,
        total_cost_incurred=m.total_cost_incurred or 0,
        uptime_seconds=m.uptime_seconds or 0,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
