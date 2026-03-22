"""Model recommender API."""

from fastapi import APIRouter
from app.schemas.recommend import RecommendRequest, RecommendResponse, RecommendationResult
from app.services.recommender import recommend_models

router = APIRouter(prefix="/recommend", tags=["recommendations"])


@router.post("/models", response_model=RecommendResponse)
async def get_recommendations(req: RecommendRequest):
    """Find the best models for a use case within a budget. No auth required."""
    results = recommend_models(
        use_case=req.use_case,
        max_budget_monthly=req.max_budget_monthly,
        cloud_provider=req.cloud_provider,
        precision=req.precision,
        min_context_length=req.min_context_length,
    )

    return RecommendResponse(
        use_case=req.use_case,
        budget=req.max_budget_monthly,
        results=[RecommendationResult(**r) for r in results],
    )
