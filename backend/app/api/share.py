"""Shareable estimates and saved bookmarks API."""

import secrets
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import SharedEstimate, SavedEstimate
from app.schemas.share import (
    CreateShareRequest,
    CreateShareResponse,
    SharedEstimateResponse,
    SaveEstimateRequest,
    SavedEstimateResponse,
)

router = APIRouter(tags=["sharing"])


# ── Shareable Estimates ──

@router.post("/share/create", response_model=CreateShareResponse)
async def create_share(req: CreateShareRequest, db: AsyncSession = Depends(get_db)):
    """Create a shareable link for an estimate. No auth required."""
    token = secrets.token_urlsafe(8)

    shared = SharedEstimate(
        share_token=token,
        estimate_snapshot=req.estimate,
        api_comparison_snapshot=req.api_comparison,
        model_name=req.model_name,
        cloud_provider=req.cloud_provider,
        total_cost_monthly=req.total_cost_monthly,
    )
    db.add(shared)
    await db.commit()

    return CreateShareResponse(
        share_token=token,
        share_url=f"/share/{token}",
    )


@router.get("/share/{token}", response_model=SharedEstimateResponse)
async def get_shared_estimate(token: str, db: AsyncSession = Depends(get_db)):
    """Get a shared estimate by token. Public, no auth."""
    result = await db.execute(
        select(SharedEstimate).where(SharedEstimate.share_token == token)
    )
    shared = result.scalar_one_or_none()
    if not shared:
        raise HTTPException(status_code=404, detail="Shared estimate not found")

    # Increment view count
    shared.views_count = (shared.views_count or 0) + 1
    await db.commit()

    return SharedEstimateResponse(
        share_token=shared.share_token,
        estimate=shared.estimate_snapshot,
        api_comparison=shared.api_comparison_snapshot,
        model_name=shared.model_name,
        cloud_provider=shared.cloud_provider,
        total_cost_monthly=shared.total_cost_monthly,
        views_count=shared.views_count,
        created_at=shared.created_at.isoformat(),
    )


# ── Saved Estimates (Bookmarks) ──

@router.post("/saved/estimates", response_model=SavedEstimateResponse)
async def save_estimate(
    req: SaveEstimateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Save an estimate to the user's bookmarks."""
    saved = SavedEstimate(
        user_id=user_id,
        label=req.label,
        estimate_snapshot=req.estimate,
        model_name=req.model_name,
        cloud_provider=req.cloud_provider,
        total_cost_monthly=req.total_cost_monthly,
        parameters_billion=req.parameters_billion,
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)

    return SavedEstimateResponse(
        id=saved.id,
        label=saved.label,
        model_name=saved.model_name,
        cloud_provider=saved.cloud_provider,
        total_cost_monthly=saved.total_cost_monthly,
        parameters_billion=saved.parameters_billion,
        created_at=saved.created_at.isoformat(),
    )


@router.get("/saved/estimates", response_model=list[SavedEstimateResponse])
async def list_saved_estimates(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all saved estimates for the current user."""
    result = await db.execute(
        select(SavedEstimate)
        .where(SavedEstimate.user_id == user_id)
        .order_by(SavedEstimate.created_at.desc())
    )
    saved_list = result.scalars().all()
    return [
        SavedEstimateResponse(
            id=s.id,
            label=s.label,
            model_name=s.model_name,
            cloud_provider=s.cloud_provider,
            total_cost_monthly=s.total_cost_monthly,
            parameters_billion=s.parameters_billion,
            created_at=s.created_at.isoformat(),
        )
        for s in saved_list
    ]


@router.delete("/saved/estimates/{estimate_id}")
async def delete_saved_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved estimate."""
    result = await db.execute(
        select(SavedEstimate)
        .where(SavedEstimate.id == estimate_id, SavedEstimate.user_id == user_id)
    )
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved estimate not found")

    await db.delete(saved)
    await db.commit()
    return {"message": "Deleted"}
