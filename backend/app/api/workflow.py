"""
n8n Workflow API — trigger autonomous LLM builder pipeline,
track runs, and receive callbacks from n8n.
"""

import hmac
import httpx
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import WorkflowRun, WorkflowStatus
from app.schemas.workflow import (
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowCallbackPayload,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])
settings = get_settings()


def _run_to_response(run: WorkflowRun) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=run.id,
        status=run.status.value if hasattr(run.status, "value") else run.status,
        domain=run.domain,
        use_case=run.use_case,
        base_model=run.base_model,
        n8n_execution_id=run.n8n_execution_id,
        config_snapshot=run.config_snapshot,
        result_snapshot=run.result_snapshot,
        error_message=run.error_message,
        created_at=run.created_at.isoformat() if run.created_at else "",
        updated_at=run.updated_at.isoformat() if run.updated_at else "",
    )


@router.post("/trigger", response_model=WorkflowRunResponse, status_code=201)
async def trigger_workflow(
    req: WorkflowRunCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Start a new autonomous LLM builder workflow run."""
    run = WorkflowRun(
        user_id=user_id,
        domain=req.domain,
        use_case=req.use_case,
        base_model=req.base_model,
        status=WorkflowStatus.PENDING,
        config_snapshot={
            "domain": req.domain,
            "use_case": req.use_case,
            "base_model": req.base_model,
        },
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    # Fire webhook to n8n
    webhook_url = settings.N8N_WEBHOOK_URL
    if webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json={
                    "run_id": run.id,
                    "domain": req.domain,
                    "use_case": req.use_case,
                    "base_model": req.base_model or "",
                    "callback_url": f"{settings.FRONTEND_URL.replace('3000', '8000')}/api/workflow/runs/{run.id}/callback",
                })
                if resp.status_code == 200:
                    data = resp.json()
                    run.n8n_execution_id = data.get("executionId") or data.get("execution_id")
                    run.status = WorkflowStatus.SEARCHING
                else:
                    run.status = WorkflowStatus.FAILED
                    run.error_message = f"n8n webhook returned {resp.status_code}"
        except Exception as e:
            run.status = WorkflowStatus.FAILED
            run.error_message = f"Failed to reach n8n: {str(e)}"

    await db.commit()
    await db.refresh(run)
    return _run_to_response(run)


@router.get("/runs", response_model=list[WorkflowRunResponse])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List all workflow runs for the current user."""
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.user_id == user_id)
        .order_by(WorkflowRun.created_at.desc())
    )
    runs = result.scalars().all()
    return [_run_to_response(r) for r in runs]


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get details of a specific workflow run."""
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id, WorkflowRun.user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return _run_to_response(run)


@router.post("/runs/{run_id}/callback")
async def workflow_callback(
    run_id: str,
    payload: WorkflowCallbackPayload,
    db: AsyncSession = Depends(get_db),
    x_callback_secret: str | None = Header(None),
):
    """n8n calls this endpoint to update workflow run status."""
    if not x_callback_secret or not hmac.compare_digest(x_callback_secret, settings.N8N_CALLBACK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid callback secret")

    result = await db.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    # Map status string to enum
    status_map = {
        "searching": WorkflowStatus.SEARCHING,
        "training": WorkflowStatus.TRAINING,
        "deploying": WorkflowStatus.DEPLOYING,
        "completed": WorkflowStatus.COMPLETED,
        "failed": WorkflowStatus.FAILED,
    }
    new_status = status_map.get(payload.status.lower())
    if new_status:
        run.status = new_status

    if payload.n8n_execution_id:
        run.n8n_execution_id = payload.n8n_execution_id

    if payload.result:
        run.result_snapshot = payload.result

    if payload.error:
        run.error_message = payload.error

    await db.commit()
    return {"status": "ok"}
