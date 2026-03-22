"""Side-by-side model comparison API."""

from fastapi import APIRouter, HTTPException
from app.schemas.compare import (
    CompareModelsRequest,
    CompareModelsResponse,
    ModelComparisonEntry,
)
from app.services.cost_engine.calculator import estimate_cost

router = APIRouter(prefix="/compare", tags=["comparison"])


@router.post("/models", response_model=CompareModelsResponse)
async def compare_models(req: CompareModelsRequest):
    """Compare 2-4 models side by side on cost and specs."""
    comparisons = []
    for entry in req.models:
        result = estimate_cost(
            parameters_billion=entry.parameters_billion,
            precision=entry.precision,
            context_length=entry.context_length,
            cloud_provider=req.cloud_provider,
            expected_qps=req.expected_qps,
            hours_per_day=req.hours_per_day,
            days_per_month=req.days_per_month,
        )
        if result is None:
            comparisons.append(ModelComparisonEntry(
                model_name=entry.name,
                parameters_billion=entry.parameters_billion,
                precision=entry.precision,
                vram_required_gb=0,
                gpu_type="N/A",
                gpu_count=0,
                instance_type="N/A",
                cost_per_hour=0,
                total_cost_monthly=0,
                compute_cost_monthly=0,
                storage_cost_monthly=0,
                recommendation="No suitable GPU found for this configuration.",
            ))
        else:
            billable_hours = req.hours_per_day * req.days_per_month
            cost_per_hour = round(result.compute_cost_monthly / max(billable_hours, 1), 4)
            comparisons.append(ModelComparisonEntry(
                model_name=entry.name,
                parameters_billion=entry.parameters_billion,
                precision=entry.precision,
                vram_required_gb=result.vram_required_gb,
                gpu_type=result.gpu_type,
                gpu_count=result.gpu_count,
                instance_type=result.instance_type,
                cost_per_hour=cost_per_hour,
                total_cost_monthly=result.total_cost_monthly,
                compute_cost_monthly=result.compute_cost_monthly,
                storage_cost_monthly=result.storage_cost_monthly,
                recommendation=result.recommendation,
            ))

    return CompareModelsResponse(
        cloud_provider=req.cloud_provider,
        comparisons=comparisons,
    )
