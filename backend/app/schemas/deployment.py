from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeployRequest(BaseModel):
    model_id: str
    cloud_provider: str
    instance_type: Optional[str] = None
    gpu_type: Optional[str] = None
    gpu_count: int = 1
    region: str = "us-east-1"
    autoscaling_enabled: bool = False
    min_replicas: int = 1
    max_replicas: int = 3


class DeployFromConfigRequest(BaseModel):
    """Deploy from a builder ModelConfig."""
    config_id: str
    cloud_provider: str
    instance_type: Optional[str] = None
    gpu_type: Optional[str] = None
    gpu_count: Optional[int] = None
    region: str = "us-east-1"


class DeploymentConfigResponse(BaseModel):
    deployment_id: str
    dockerfile: str
    kubernetes_yaml: str
    terraform_config: str
    ci_cd_pipeline: str
    cloudformation: str = ""
    quickstart: str = ""
    merge_config: str = ""


class DeploymentResponse(BaseModel):
    id: str
    model_id: Optional[str]
    cloud_provider: str
    status: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    region: str
    endpoint_url: Optional[str]
    total_requests: int
    total_tokens_generated: int
    total_cost_incurred: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    deployment_id: str
    message: str
    max_tokens: int = 512
    temperature: float = 0.7
    stream: bool = False


class ChatResponse(BaseModel):
    message: ChatMessage
    tokens_used: int
    latency_ms: float


class UsageSummary(BaseModel):
    deployment_id: str
    total_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_cost_usd: float
    avg_latency_ms: float
    requests_today: int
    cost_today: float
