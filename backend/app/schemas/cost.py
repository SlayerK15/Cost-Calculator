from pydantic import BaseModel
from typing import Optional


class CostEstimateRequest(BaseModel):
    model_id: str
    cloud_provider: str  # aws, gcp, azure
    expected_qps: float = 1.0
    avg_tokens_per_request: int = 512
    hours_per_day: int = 24
    days_per_month: int = 30
    autoscaling_enabled: bool = False
    min_replicas: int = 1
    max_replicas: int = 3


class PublicCostEstimateRequest(BaseModel):
    """Estimate request that doesn't require auth — takes model params directly."""
    model_name: str = "Custom Model"
    parameters_billion: float
    precision: str = "fp16"
    context_length: int = 4096
    cloud_provider: str = "aws"
    expected_qps: float = 1.0
    avg_tokens_per_request: int = 512
    hours_per_day: int = 24
    days_per_month: int = 30
    autoscaling_enabled: bool = False
    min_replicas: int = 1
    max_replicas: int = 3


class GPURecommendation(BaseModel):
    gpu_type: str
    gpu_count: int
    instance_type: str
    vram_per_gpu_gb: float
    total_vram_gb: float
    cost_per_hour: float


class CostBreakdown(BaseModel):
    compute_cost_monthly: float
    storage_cost_monthly: float
    bandwidth_cost_monthly: float
    idle_cost_monthly: float
    kv_cache_overhead_cost: float
    total_cost_monthly: float


class ScalingScenario(BaseModel):
    name: str
    description: str
    replicas: int
    total_monthly_cost: float
    cost_per_request: float


class CostEstimateResponse(BaseModel):
    id: str
    model_name: str
    cloud_provider: str
    vram_required_gb: float
    recommended_gpu: GPURecommendation
    cost_breakdown: CostBreakdown
    scaling_scenarios: list[ScalingScenario]
    optimized_config: Optional[dict] = None
    recommendation: str


class MultiCloudComparison(BaseModel):
    model_id: str
    model_name: str
    estimates: list[CostEstimateResponse]


# ── API Provider Pricing (for comparison) ──

class APIProviderPlan(BaseModel):
    provider: str
    model: str
    input_cost_per_million: float
    output_cost_per_million: float
    monthly_cost: float
    cost_per_request: float


class APIProviderComparison(BaseModel):
    monthly_requests: int
    monthly_input_tokens: int
    monthly_output_tokens: int
    avg_input_tokens_per_request: int
    avg_output_tokens_per_request: int
    api_providers: list[APIProviderPlan]
    self_hosted_monthly: float
    self_hosted_provider: str
