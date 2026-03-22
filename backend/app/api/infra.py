"""Infrastructure Agent API — generate multi-cloud deployment files."""

from fastapi import APIRouter

from app.schemas.infra import (
    InfraGenerateRequest,
    InfraGenerateResponse,
    InfraSearchRequest,
    InfraSearchResponse,
)
from app.services.infra_agent import generate_infra, search_cloud_infra

router = APIRouter(prefix="/infra", tags=["infra"])


@router.post("/generate", response_model=InfraGenerateResponse)
async def generate_deployment_files(req: InfraGenerateRequest):
    """
    Generate deployment files for the specified model, cloud provider,
    and IaC language. Returns Dockerfile, K8s YAML, IaC config, CI/CD
    pipeline, and quickstart instructions.

    Supports: terraform (default), cloudformation (AWS only), pulumi, kubernetes.
    """
    return generate_infra(req)


@router.post("/search", response_model=InfraSearchResponse)
async def search_infrastructure(req: InfraSearchRequest):
    """
    Search cloud GPU instances, pricing, and deployment best practices.
    Uses the platform's real-time cost engine and GPU catalog.
    """
    return search_cloud_infra(req)
