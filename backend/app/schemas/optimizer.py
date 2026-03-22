from pydantic import BaseModel
from typing import Optional


class OptimizationSuggestion(BaseModel):
    type: str  # "precision", "spot", "rightsize", "provider_switch", "autoscaling", "reserved"
    title: str
    description: str
    current_cost: float
    optimized_cost: float
    savings_monthly: float
    savings_pct: float
    tradeoff: str


class OptimizationReport(BaseModel):
    current_monthly_cost: float
    optimizations: list[OptimizationSuggestion]
    total_potential_savings: float
    best_optimized_cost: float


class ForecastDay(BaseModel):
    date: str
    projected_cost: float


class ForecastResult(BaseModel):
    projected_monthly_cost: float
    current_monthly_cost: float
    change_pct: float
    daily_forecast: list[ForecastDay]
    confidence: str  # "low", "medium", "high"
