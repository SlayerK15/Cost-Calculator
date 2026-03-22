from pydantic import BaseModel
from typing import Optional


class CreateShareRequest(BaseModel):
    estimate: dict
    api_comparison: Optional[dict] = None
    model_name: str
    cloud_provider: str
    total_cost_monthly: float


class CreateShareResponse(BaseModel):
    share_token: str
    share_url: str


class SharedEstimateResponse(BaseModel):
    share_token: str
    estimate: dict
    api_comparison: Optional[dict] = None
    model_name: str
    cloud_provider: str
    total_cost_monthly: float
    views_count: int
    created_at: str


class SaveEstimateRequest(BaseModel):
    label: str
    estimate: dict
    model_name: str
    cloud_provider: str
    total_cost_monthly: float
    parameters_billion: Optional[float] = None


class SavedEstimateResponse(BaseModel):
    id: str
    label: str
    model_name: str
    cloud_provider: str
    total_cost_monthly: float
    parameters_billion: Optional[float] = None
    created_at: str
