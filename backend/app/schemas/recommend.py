from pydantic import BaseModel
from typing import Optional


class RecommendRequest(BaseModel):
    use_case: str  # "coding", "chat", "reasoning", "general", "multilingual"
    max_budget_monthly: float
    cloud_provider: Optional[str] = None  # None = check all
    precision: str = "fp16"
    min_context_length: int = 4096


class RecommendationResult(BaseModel):
    model_name: str
    parameters_billion: float
    quality_tier: str  # "good", "great", "excellent"
    tags: list[str]
    cloud_provider: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    vram_required_gb: float
    monthly_cost: float
    recommendation: str


class RecommendResponse(BaseModel):
    use_case: str
    budget: float
    results: list[RecommendationResult]
