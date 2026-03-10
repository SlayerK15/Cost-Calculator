"""Playground API — simulate model inference with cost/latency estimates."""

import random
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import ModelConfig, LLMModel, UserTier
from app.api.subscription import require_tier

router = APIRouter(prefix="/playground", tags=["playground"])


class SimulateRequest(BaseModel):
    config_id: str
    prompt: str


class ModelInfo(BaseModel):
    name: str
    parameters_billion: float | None
    quantization: str
    context_length: int


class SimulateResponse(BaseModel):
    response_text: str
    tokens_used: int
    estimated_latency_ms: float
    estimated_cost_per_request: float
    model_info: ModelInfo


# Simulated response fragments for realistic output
RESPONSE_TEMPLATES = [
    "Based on the analysis, the key factors to consider are the computational requirements and memory constraints. "
    "The model architecture leverages attention mechanisms that scale quadratically with sequence length, "
    "making efficient inference crucial for production workloads.",
    "The implementation follows a transformer-based architecture with multi-head attention. "
    "Key optimizations include KV-cache management, continuous batching, and tensor parallelism "
    "across multiple GPUs for reduced latency.",
    "Looking at the deployment configuration, the recommended approach involves containerized serving "
    "with vLLM as the inference engine. This provides continuous batching, PagedAttention for memory "
    "efficiency, and support for quantized models.",
    "The cost-performance tradeoff depends on several factors: model size, quantization level, "
    "expected throughput, and latency requirements. For production workloads, consider using "
    "AWQ or GPTQ quantization to reduce VRAM usage while maintaining quality.",
]


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_inference(
    data: SimulateRequest,
    user=Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    """Simulate model inference with estimated metrics."""
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == data.config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    # Get base model info
    params_b = config.effective_parameters_billion or 7.0
    context_len = config.effective_context_length or 4096
    quant = config.quantization_method.value if config.quantization_method else "none"

    # Estimate tokens in prompt
    prompt_tokens = max(1, len(data.prompt.split()) * 1.3)

    # Simulate response length (varies by model size)
    response_tokens = int(random.gauss(180, 60))
    response_tokens = max(30, min(config.default_max_tokens or 512, response_tokens))

    total_tokens = int(prompt_tokens + response_tokens)

    # Estimate latency based on model size and quantization
    quant_speedup = {"none": 1.0, "gptq": 1.4, "awq": 1.5, "bnb_int8": 1.2, "bnb_int4": 1.8}
    base_latency = params_b * 15  # ~15ms per billion params as baseline
    latency = base_latency * (response_tokens / 100) / quant_speedup.get(quant, 1.0)
    latency += random.gauss(0, latency * 0.1)  # Add noise
    latency = max(50, latency)

    # Estimate cost per request (based on GPU hourly cost and throughput)
    tokens_per_second = 40 / (params_b / 7)  # Rough estimate
    tokens_per_second *= quant_speedup.get(quant, 1.0)
    request_seconds = total_tokens / tokens_per_second
    hourly_cost = 3.0  # Approximate GPU cost
    cost_per_request = (request_seconds / 3600) * hourly_cost

    # Generate simulated response
    response_text = random.choice(RESPONSE_TEMPLATES)

    return SimulateResponse(
        response_text=response_text,
        tokens_used=total_tokens,
        estimated_latency_ms=round(latency, 1),
        estimated_cost_per_request=round(cost_per_request, 6),
        model_info=ModelInfo(
            name=config.name,
            parameters_billion=params_b,
            quantization=quant,
            context_length=context_len,
        ),
    )
