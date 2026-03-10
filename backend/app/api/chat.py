import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import Deployment, DeploymentStatus, ChatSession, UsageRecord
from app.schemas.deployment import ChatRequest, ChatResponse, ChatMessage, UsageSummary

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to a deployed model."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == data.deployment_id, Deployment.user_id == user_id
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if deployment.status != DeploymentStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Deployment is not running (status: {deployment.status.value})",
        )

    start_time = time.time()

    # In production, this would call the actual vLLM endpoint:
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(
    #         f"{deployment.endpoint_url}/v1/chat/completions",
    #         json={
    #             "model": model_name,
    #             "messages": [{"role": "user", "content": data.message}],
    #             "max_tokens": data.max_tokens,
    #             "temperature": data.temperature,
    #         },
    #         headers={"Authorization": f"Bearer {deployment.api_key}"}
    #     )

    # Simulated response for MVP
    response_text = (
        f"[Simulated response from deployment {deployment.id[:8]}] "
        f"This is a placeholder response. In production, this message would be "
        f"routed to the vLLM server at {deployment.endpoint_url}."
    )
    tokens_used = len(data.message.split()) + len(response_text.split())
    latency_ms = (time.time() - start_time) * 1000

    # Record usage
    usage = UsageRecord(
        user_id=user_id,
        deployment_id=deployment.id,
        tokens_input=len(data.message.split()),
        tokens_output=len(response_text.split()),
        latency_ms=latency_ms,
        cost_usd=tokens_used * 0.000001,  # Placeholder pricing
    )
    db.add(usage)

    # Update deployment stats
    deployment.total_requests += 1
    deployment.total_tokens_generated += tokens_used
    deployment.total_cost_incurred += usage.cost_usd

    return ChatResponse(
        message=ChatMessage(role="assistant", content=response_text),
        tokens_used=tokens_used,
        latency_ms=round(latency_ms, 2),
    )


@router.get("/usage/{deployment_id}", response_model=UsageSummary)
async def get_usage(
    deployment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for a deployment."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id, Deployment.user_id == user_id
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Aggregate usage
    usage_result = await db.execute(
        select(
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.tokens_input), 0).label("total_input"),
            func.coalesce(func.sum(UsageRecord.tokens_output), 0).label("total_output"),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0.0).label("total_cost"),
            func.coalesce(func.avg(UsageRecord.latency_ms), 0.0).label("avg_latency"),
        ).where(UsageRecord.deployment_id == deployment_id)
    )
    row = usage_result.one()

    return UsageSummary(
        deployment_id=deployment_id,
        total_requests=row.total_requests,
        total_tokens_input=row.total_input,
        total_tokens_output=row.total_output,
        total_cost_usd=round(float(row.total_cost), 6),
        avg_latency_ms=round(float(row.avg_latency), 2),
        requests_today=0,  # Simplified for MVP
        cost_today=0.0,
    )
