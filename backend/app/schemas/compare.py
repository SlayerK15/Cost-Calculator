from pydantic import BaseModel, Field


class CompareModelEntry(BaseModel):
    name: str = "Custom Model"
    parameters_billion: float
    precision: str = "fp16"
    context_length: int = 4096


class CompareModelsRequest(BaseModel):
    models: list[CompareModelEntry] = Field(..., min_length=2, max_length=4)
    cloud_provider: str = "aws"
    expected_qps: float = 1.0
    hours_per_day: int = 24
    days_per_month: int = 30


class ModelComparisonEntry(BaseModel):
    model_name: str
    parameters_billion: float
    precision: str
    vram_required_gb: float
    gpu_type: str
    gpu_count: int
    instance_type: str
    cost_per_hour: float
    total_cost_monthly: float
    compute_cost_monthly: float
    storage_cost_monthly: float
    recommendation: str


class CompareModelsResponse(BaseModel):
    cloud_provider: str
    comparisons: list[ModelComparisonEntry]
