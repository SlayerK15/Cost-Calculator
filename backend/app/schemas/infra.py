from pydantic import BaseModel, Field
from typing import Optional


class InfraGenerateRequest(BaseModel):
    """Request to generate infrastructure deployment files."""
    model_name: str = Field(..., description="Model name (e.g. 'Llama-3-70B')")
    parameters_billion: float = Field(..., gt=0, description="Model size in billions of parameters")
    precision: str = Field(default="fp16", description="Model precision: fp16, bf16, int8, int4")
    context_length: int = Field(default=4096, ge=512, le=131072)
    cloud_provider: str = Field(..., description="Cloud provider: aws, gcp, azure")
    iac_language: str = Field(
        default="terraform",
        description="Infrastructure-as-Code language: terraform, cloudformation, kubernetes, pulumi",
    )
    region: str = Field(default="us-east-1", description="Cloud region")
    gpu_count: int = Field(default=1, ge=1, le=16)
    replicas: int = Field(default=1, ge=1, le=20)
    enable_monitoring: bool = Field(default=True)
    enable_autoscaling: bool = Field(default=True)
    custom_requirements: str = Field(default="", description="Free-text custom requirements for the agent")


class InfraFileEntry(BaseModel):
    filename: str
    content: str
    language: str  # terraform, yaml, dockerfile, json, bash, python, typescript


class InfraGenerateResponse(BaseModel):
    deployment_id: str
    cloud_provider: str
    iac_language: str
    region: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    estimated_monthly_cost: float
    files: list[InfraFileEntry]
    quickstart: str
    summary: str


class InfraSearchRequest(BaseModel):
    """Search for cloud instance types, GPU pricing, or best practices."""
    query: str = Field(..., description="Search query about cloud infrastructure")
    cloud_provider: Optional[str] = Field(default=None, description="Filter by provider")


class InfraSearchResult(BaseModel):
    source: str
    title: str
    snippet: str
    relevance: float


class InfraSearchResponse(BaseModel):
    query: str
    results: list[InfraSearchResult]
