from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import LLMModel, CostEstimate as CostEstimateModel, CloudProvider
from app.schemas.cost import (
    CostEstimateRequest,
    PublicCostEstimateRequest,
    CostEstimateResponse,
    GPURecommendation,
    CostBreakdown,
    ScalingScenario,
    MultiCloudComparison,
    APIProviderPlan,
    APIProviderComparison,
)
from app.services.cost_engine.calculator import estimate_cost
from app.services.cost_engine.gpu_catalog import load_live_prices

router = APIRouter(prefix="/estimate", tags=["cost-estimation"])

# ── Hardcoded fallback API provider pricing per 1M tokens (early 2025) ──
_FALLBACK_API_PRICING = [
    {"provider": "OpenAI", "model": "GPT-4o", "input": 2.50, "output": 10.00},
    {"provider": "OpenAI", "model": "GPT-4o mini", "input": 0.15, "output": 0.60},
    {"provider": "OpenAI", "model": "o1", "input": 15.00, "output": 60.00},
    {"provider": "OpenAI", "model": "o3-mini", "input": 1.10, "output": 4.40},
    {"provider": "Anthropic", "model": "Claude Sonnet 4", "input": 3.00, "output": 15.00},
    {"provider": "Anthropic", "model": "Claude Opus 4", "input": 15.00, "output": 75.00},
    {"provider": "Anthropic", "model": "Claude Haiku 3.5", "input": 0.80, "output": 4.00},
    {"provider": "Google", "model": "Gemini 2.0 Flash", "input": 0.10, "output": 0.40},
    {"provider": "Google", "model": "Gemini 1.5 Pro", "input": 0.125, "output": 0.375},
    {"provider": "Mistral", "model": "Mistral Large", "input": 2.00, "output": 6.00},
    {"provider": "Mistral", "model": "Mistral Small", "input": 0.10, "output": 0.30},
    {"provider": "DeepSeek", "model": "DeepSeek V3", "input": 0.27, "output": 0.42},
]


async def _get_api_pricing() -> list[dict]:
    """Get API provider pricing — live from DB if available, else hardcoded fallback."""
    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.models import LiveAPIPrice

    try:
        async with async_session() as session:
            result = await session.execute(select(LiveAPIPrice))
            rows = result.scalars().all()

        if rows:
            return [
                {
                    "provider": r.provider,
                    "model": r.model,
                    "input": r.input_cost_per_million,
                    "output": r.output_cost_per_million,
                }
                for r in rows
            ]
    except Exception:
        pass

    return _FALLBACK_API_PRICING


@router.post("/public", response_model=CostEstimateResponse)
async def public_estimate(data: PublicCostEstimateRequest):
    """Free public cost estimate — no auth required, no DB persistence."""
    await load_live_prices()  # Refresh live GPU cache from DB
    cost_result = estimate_cost(
        parameters_billion=data.parameters_billion,
        precision=data.precision,
        context_length=data.context_length,
        cloud_provider=data.cloud_provider,
        expected_qps=data.expected_qps,
        avg_tokens_per_request=data.avg_tokens_per_request,
        hours_per_day=data.hours_per_day,
        days_per_month=data.days_per_month,
        autoscaling_enabled=data.autoscaling_enabled,
        min_replicas=data.min_replicas,
        max_replicas=data.max_replicas,
    )

    if cost_result is None:
        raise HTTPException(
            status_code=400,
            detail=f"No suitable GPU instance found on {data.cloud_provider} for this model.",
        )

    return CostEstimateResponse(
        id="",
        model_name=data.model_name,
        cloud_provider=data.cloud_provider,
        vram_required_gb=cost_result.vram_required_gb,
        recommended_gpu=GPURecommendation(
            gpu_type=cost_result.gpu_type,
            gpu_count=cost_result.gpu_count,
            instance_type=cost_result.instance_type,
            vram_per_gpu_gb=cost_result.total_vram_gb / cost_result.gpu_count,
            total_vram_gb=cost_result.total_vram_gb,
            cost_per_hour=cost_result.compute_cost_monthly / max(data.hours_per_day * data.days_per_month, 1),
        ),
        cost_breakdown=CostBreakdown(
            compute_cost_monthly=cost_result.compute_cost_monthly,
            storage_cost_monthly=cost_result.storage_cost_monthly,
            bandwidth_cost_monthly=cost_result.bandwidth_cost_monthly,
            idle_cost_monthly=cost_result.idle_cost_monthly,
            kv_cache_overhead_cost=cost_result.kv_cache_overhead_cost,
            total_cost_monthly=cost_result.total_cost_monthly,
        ),
        scaling_scenarios=[ScalingScenario(**s) for s in cost_result.scaling_scenarios],
        optimized_config=cost_result.optimized_config,
        recommendation=cost_result.recommendation,
    )


@router.post("/public/compare")
async def public_compare(
    parameters_billion: float,
    model_name: str = "Custom Model",
    precision: str = "fp16",
    context_length: int = 4096,
    expected_qps: float = 1.0,
    avg_tokens_per_request: int = 512,
    hours_per_day: int = 24,
    days_per_month: int = 30,
):
    """Free public multi-cloud comparison — no auth required."""
    await load_live_prices()
    billable_hours = hours_per_day * days_per_month
    estimates = []
    for provider in ["aws", "gcp", "azure"]:
        cost_result = estimate_cost(
            parameters_billion=parameters_billion,
            precision=precision,
            context_length=context_length,
            cloud_provider=provider,
            expected_qps=expected_qps,
            avg_tokens_per_request=avg_tokens_per_request,
            hours_per_day=hours_per_day,
            days_per_month=days_per_month,
        )
        if cost_result:
            estimates.append(CostEstimateResponse(
                id="",
                model_name=model_name,
                cloud_provider=provider,
                vram_required_gb=cost_result.vram_required_gb,
                recommended_gpu=GPURecommendation(
                    gpu_type=cost_result.gpu_type,
                    gpu_count=cost_result.gpu_count,
                    instance_type=cost_result.instance_type,
                    vram_per_gpu_gb=cost_result.total_vram_gb / cost_result.gpu_count,
                    total_vram_gb=cost_result.total_vram_gb,
                    cost_per_hour=cost_result.compute_cost_monthly / max(billable_hours, 1),
                ),
                cost_breakdown=CostBreakdown(
                    compute_cost_monthly=cost_result.compute_cost_monthly,
                    storage_cost_monthly=cost_result.storage_cost_monthly,
                    bandwidth_cost_monthly=cost_result.bandwidth_cost_monthly,
                    idle_cost_monthly=cost_result.idle_cost_monthly,
                    kv_cache_overhead_cost=cost_result.kv_cache_overhead_cost,
                    total_cost_monthly=cost_result.total_cost_monthly,
                ),
                scaling_scenarios=[ScalingScenario(**s) for s in cost_result.scaling_scenarios],
                optimized_config=cost_result.optimized_config,
                recommendation=cost_result.recommendation,
            ))

    return MultiCloudComparison(
        model_id="",
        model_name=model_name,
        estimates=estimates,
    )


@router.post("/public/compare-api-providers", response_model=APIProviderComparison)
async def compare_with_api_providers(data: PublicCostEstimateRequest):
    """Compare self-hosted cost vs API provider pricing (OpenAI, Claude, Gemini, etc.)."""
    await load_live_prices()
    # Calculate self-hosted cost
    cost_result = estimate_cost(
        parameters_billion=data.parameters_billion,
        precision=data.precision,
        context_length=data.context_length,
        cloud_provider=data.cloud_provider,
        expected_qps=data.expected_qps,
        avg_tokens_per_request=data.avg_tokens_per_request,
        hours_per_day=data.hours_per_day,
        days_per_month=data.days_per_month,
        autoscaling_enabled=data.autoscaling_enabled,
        min_replicas=data.min_replicas,
        max_replicas=data.max_replicas,
    )

    if cost_result is None:
        raise HTTPException(status_code=400, detail="No suitable GPU instance found.")

    # Calculate usage volumes based on actual active time
    monthly_requests = int(data.expected_qps * 3600 * data.hours_per_day * data.days_per_month)
    # Use separate input/output tokens if provided, else fall back to avg_tokens_per_request
    avg_input_tokens = data.avg_input_tokens if data.avg_input_tokens > 0 else data.avg_tokens_per_request
    avg_output_tokens = data.avg_output_tokens if data.avg_output_tokens > 0 else max(data.avg_tokens_per_request // 3, 1)
    monthly_input_tokens = monthly_requests * avg_input_tokens
    monthly_output_tokens = monthly_requests * avg_output_tokens

    # Calculate cost for each API provider (live from DB or hardcoded fallback)
    pricing = await _get_api_pricing()
    api_plans = []
    for p in pricing:
        input_cost = (monthly_input_tokens / 1_000_000) * p["input"]
        output_cost = (monthly_output_tokens / 1_000_000) * p["output"]
        total = input_cost + output_cost
        cost_per_req = total / monthly_requests if monthly_requests > 0 else 0
        api_plans.append(APIProviderPlan(
            provider=p["provider"],
            model=p["model"],
            input_cost_per_million=p["input"],
            output_cost_per_million=p["output"],
            monthly_cost=round(total, 2),
            cost_per_request=round(cost_per_req, 6),
        ))

    # Sort by monthly cost
    api_plans.sort(key=lambda x: x.monthly_cost)

    return APIProviderComparison(
        monthly_requests=monthly_requests,
        monthly_input_tokens=monthly_input_tokens,
        monthly_output_tokens=monthly_output_tokens,
        avg_input_tokens_per_request=avg_input_tokens,
        avg_output_tokens_per_request=avg_output_tokens,
        api_providers=api_plans,
        self_hosted_monthly=round(cost_result.total_cost_monthly, 2),
        self_hosted_provider=data.cloud_provider,
    )


@router.post("/", response_model=CostEstimateResponse)
async def create_estimate(
    data: CostEstimateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate a cost estimate for deploying a model."""
    await load_live_prices()
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == data.model_id, LLMModel.user_id == user_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if not model.parameters_billion:
        raise HTTPException(
            status_code=400,
            detail="Model parameter count unknown. Please provide parameters or upload the model for profiling.",
        )

    model_file_gb = None
    if model.file_size_bytes:
        model_file_gb = model.file_size_bytes / (1024 ** 3)

    cost_result = estimate_cost(
        parameters_billion=model.parameters_billion,
        precision=model.precision.value if model.precision else "fp16",
        context_length=model.context_length or 4096,
        cloud_provider=data.cloud_provider,
        expected_qps=data.expected_qps,
        avg_tokens_per_request=data.avg_tokens_per_request,
        hours_per_day=data.hours_per_day,
        days_per_month=data.days_per_month,
        model_file_size_gb=model_file_gb,
        autoscaling_enabled=data.autoscaling_enabled,
        min_replicas=data.min_replicas,
        max_replicas=data.max_replicas,
    )

    if cost_result is None:
        raise HTTPException(
            status_code=400,
            detail=f"No suitable GPU instance found on {data.cloud_provider} for this model. "
                   "The model may be too large for available instances.",
        )

    # Persist estimate
    estimate_record = CostEstimateModel(
        user_id=user_id,
        model_id=model.id,
        cloud_provider=CloudProvider(data.cloud_provider),
        gpu_type=cost_result.gpu_type,
        gpu_count=cost_result.gpu_count,
        instance_type=cost_result.instance_type,
        vram_required_gb=cost_result.vram_required_gb,
        compute_cost_monthly=cost_result.compute_cost_monthly,
        storage_cost_monthly=cost_result.storage_cost_monthly,
        bandwidth_cost_monthly=cost_result.bandwidth_cost_monthly,
        idle_cost_monthly=cost_result.idle_cost_monthly,
        total_cost_monthly=cost_result.total_cost_monthly,
        expected_qps=data.expected_qps,
        avg_tokens_per_request=data.avg_tokens_per_request,
        hours_per_day=data.hours_per_day,
        autoscaling_enabled=data.autoscaling_enabled,
        min_replicas=data.min_replicas,
        max_replicas=data.max_replicas,
        cost_breakdown_json={
            "vram_breakdown": {
                "model_weights_gb": cost_result.vram_breakdown.model_weights_gb,
                "kv_cache_gb": cost_result.vram_breakdown.kv_cache_gb,
                "activation_overhead_gb": cost_result.vram_breakdown.activation_overhead_gb,
                "framework_overhead_gb": cost_result.vram_breakdown.framework_overhead_gb,
            },
            "scaling_scenarios": cost_result.scaling_scenarios,
            "optimized_config": cost_result.optimized_config,
        },
        recommendation=cost_result.recommendation,
    )
    db.add(estimate_record)
    await db.flush()
    await db.refresh(estimate_record)

    return CostEstimateResponse(
        id=estimate_record.id,
        model_name=model.name,
        cloud_provider=data.cloud_provider,
        vram_required_gb=cost_result.vram_required_gb,
        recommended_gpu=GPURecommendation(
            gpu_type=cost_result.gpu_type,
            gpu_count=cost_result.gpu_count,
            instance_type=cost_result.instance_type,
            vram_per_gpu_gb=cost_result.total_vram_gb / cost_result.gpu_count,
            total_vram_gb=cost_result.total_vram_gb,
            cost_per_hour=cost_result.compute_cost_monthly / max(data.hours_per_day * data.days_per_month, 1),
        ),
        cost_breakdown=CostBreakdown(
            compute_cost_monthly=cost_result.compute_cost_monthly,
            storage_cost_monthly=cost_result.storage_cost_monthly,
            bandwidth_cost_monthly=cost_result.bandwidth_cost_monthly,
            idle_cost_monthly=cost_result.idle_cost_monthly,
            kv_cache_overhead_cost=cost_result.kv_cache_overhead_cost,
            total_cost_monthly=cost_result.total_cost_monthly,
        ),
        scaling_scenarios=[
            ScalingScenario(**s) for s in cost_result.scaling_scenarios
        ],
        optimized_config=cost_result.optimized_config,
        recommendation=cost_result.recommendation,
    )


@router.post("/compare", response_model=MultiCloudComparison)
async def compare_providers(
    model_id: str,
    expected_qps: float = 1.0,
    avg_tokens_per_request: int = 512,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Compare costs across all cloud providers for a model."""
    await load_live_prices()
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id, LLMModel.user_id == user_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if not model.parameters_billion:
        raise HTTPException(status_code=400, detail="Model parameter count unknown")

    estimates = []
    for provider in ["aws", "gcp", "azure"]:
        cost_result = estimate_cost(
            parameters_billion=model.parameters_billion,
            precision=model.precision.value if model.precision else "fp16",
            context_length=model.context_length or 4096,
            cloud_provider=provider,
            expected_qps=expected_qps,
            avg_tokens_per_request=avg_tokens_per_request,
        )
        if cost_result:
            estimates.append(CostEstimateResponse(
                id="",
                model_name=model.name,
                cloud_provider=provider,
                vram_required_gb=cost_result.vram_required_gb,
                recommended_gpu=GPURecommendation(
                    gpu_type=cost_result.gpu_type,
                    gpu_count=cost_result.gpu_count,
                    instance_type=cost_result.instance_type,
                    vram_per_gpu_gb=cost_result.total_vram_gb / cost_result.gpu_count,
                    total_vram_gb=cost_result.total_vram_gb,
                    cost_per_hour=cost_result.compute_cost_monthly / (24 * 30),
                ),
                cost_breakdown=CostBreakdown(
                    compute_cost_monthly=cost_result.compute_cost_monthly,
                    storage_cost_monthly=cost_result.storage_cost_monthly,
                    bandwidth_cost_monthly=cost_result.bandwidth_cost_monthly,
                    idle_cost_monthly=cost_result.idle_cost_monthly,
                    kv_cache_overhead_cost=cost_result.kv_cache_overhead_cost,
                    total_cost_monthly=cost_result.total_cost_monthly,
                ),
                scaling_scenarios=[ScalingScenario(**s) for s in cost_result.scaling_scenarios],
                optimized_config=cost_result.optimized_config,
                recommendation=cost_result.recommendation,
            ))

    return MultiCloudComparison(
        model_id=model_id,
        model_name=model.name,
        estimates=estimates,
    )
