import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import (
    LLMModel, Deployment, DeploymentStatus, CloudProvider,
    ModelConfig, UserTier,
)
from app.schemas.deployment import (
    DeployRequest,
    DeployFromConfigRequest,
    DeploymentConfigResponse,
    DeploymentResponse,
)
from app.services.deployment_generator import DeploymentGenerator, ModelPipeline
from app.services.config_bundler import create_deploy_bundle
from app.services.cost_engine.calculator import estimate_cost, select_gpu_instance, calculate_vram
from app.api.subscription import require_tier

router = APIRouter(prefix="/deploy", tags=["deployment"])


# ── Helper ──

def _pipeline_from_config(cfg: ModelConfig) -> ModelPipeline:
    """Build a ModelPipeline from a ModelConfig ORM row."""
    merge_models = []
    if cfg.merge_models_json:
        try:
            merge_models = json.loads(cfg.merge_models_json) if isinstance(cfg.merge_models_json, str) else cfg.merge_models_json
        except Exception:
            merge_models = []

    return ModelPipeline(
        base_model_hf_id=cfg.base_model_hf_id or "unknown",
        adapter_hf_id=cfg.adapter_hf_id,
        is_merge=cfg.is_merge or False,
        merge_method=cfg.merge_method.value if cfg.merge_method else None,
        merge_models=merge_models,
        quantization_method=cfg.quantization_method.value if cfg.quantization_method else "none",
        system_prompt=cfg.system_prompt,
        default_temperature=cfg.default_temperature or 0.7,
        default_max_tokens=cfg.default_max_tokens or 512,
    )


# ── Generate from a builder ModelConfig (PRO) ──

@router.post("/from-config", response_model=DeploymentConfigResponse)
async def generate_from_config(
    data: DeployFromConfigRequest,
    user=Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    """Generate deploy configs from a builder ModelConfig."""
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == data.config_id,
            ModelConfig.user_id == user.id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Model config not found")

    pipeline = _pipeline_from_config(cfg)
    model_hf_id = cfg.base_model_hf_id or cfg.name

    # Determine GPU sizing
    vram_gb = cfg.estimated_vram_gb or 20.0
    instance = select_gpu_instance(vram_gb, data.cloud_provider)
    if not instance:
        raise HTTPException(status_code=400, detail="No suitable GPU instance found")

    gpu_type = data.gpu_type or instance.gpu_type
    instance_type = data.instance_type or instance.instance_type
    gpu_count = data.gpu_count or instance.gpu_count

    generator = DeploymentGenerator()
    configs = generator.generate_all_configs(
        deployment_id=f"dep-{cfg.id[:8]}",
        model_id=model_hf_id,
        model_name=cfg.name.replace(" ", "-").lower(),
        cloud_provider=data.cloud_provider,
        instance_type=instance_type,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        context_length=cfg.effective_context_length or 4096,
        precision=cfg.effective_precision or "fp16",
        region=data.region,
        pipeline=pipeline,
    )

    # Create deployment record
    deployment = Deployment(
        user_id=user.id,
        model_id=cfg.base_model_id,
        cloud_provider=CloudProvider(data.cloud_provider),
        status=DeploymentStatus.PENDING,
        instance_type=instance_type,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        region=data.region,
        dockerfile=configs["dockerfile"],
        kubernetes_yaml=configs["kubernetes_yaml"],
        terraform_config=configs["terraform_config"],
    )
    db.add(deployment)
    await db.flush()
    await db.refresh(deployment)

    return DeploymentConfigResponse(
        deployment_id=deployment.id,
        dockerfile=configs["dockerfile"],
        kubernetes_yaml=configs["kubernetes_yaml"],
        terraform_config=configs["terraform_config"],
        ci_cd_pipeline=configs["ci_cd_pipeline"],
        cloudformation=configs.get("cloudformation", ""),
        quickstart=configs.get("quickstart", ""),
        merge_config=configs.get("merge_config", ""),
    )


# ── Download ZIP bundle ──

@router.get("/{deployment_id}/bundle")
async def download_bundle(
    deployment_id: str,
    user=Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    """Download all configs as a ZIP bundle."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.user_id == user.id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Reconstruct configs dict from stored fields + regenerate missing ones
    generator = DeploymentGenerator()
    model_name = deployment_id  # fallback
    cloud = deployment.cloud_provider.value if deployment.cloud_provider else "aws"

    configs = {
        "dockerfile": deployment.dockerfile or "",
        "kubernetes_yaml": deployment.kubernetes_yaml or "",
        "terraform_config": deployment.terraform_config or "",
        "ci_cd_pipeline": generator.generate_ci_cd_pipeline(
            deployment_id, cloud, model_name
        ),
        "cloudformation": "",
        "quickstart": generator.generate_quickstart_instructions(
            cloud, deployment_id, model_name,
            deployment.instance_type or "", deployment.gpu_type or "",
            deployment.region or "us-east-1",
        ),
        "merge_config": "",
    }

    zip_bytes = create_deploy_bundle(configs, model_name, cloud)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="deploy-{deployment_id[:8]}.zip"'
        },
    )


# ── Original: generate from LLMModel ──

@router.post("/generate-configs", response_model=DeploymentConfigResponse)
async def generate_deployment_configs(
    data: DeployRequest,
    user=Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    """Generate deployment configuration files without deploying."""
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == data.model_id, LLMModel.user_id == user.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if not model.parameters_billion:
        raise HTTPException(status_code=400, detail="Model parameter count unknown")

    # Determine GPU if not specified
    gpu_type = data.gpu_type
    instance_type = data.instance_type
    gpu_count = data.gpu_count

    if not instance_type:
        precision = model.precision.value if model.precision else "fp16"
        vram = calculate_vram(model.parameters_billion, precision, model.context_length or 4096)
        instance = select_gpu_instance(vram.total_gb, data.cloud_provider)
        if not instance:
            raise HTTPException(status_code=400, detail="No suitable GPU instance found")
        gpu_type = instance.gpu_type
        instance_type = instance.instance_type
        gpu_count = instance.gpu_count

    generator = DeploymentGenerator()
    model_id_or_name = model.huggingface_id or model.name
    is_custom = model.source.value == "custom_upload"

    configs = generator.generate_all_configs(
        deployment_id=f"dep-{model.id[:8]}",
        model_id=model_id_or_name,
        model_name=model.name,
        cloud_provider=data.cloud_provider,
        instance_type=instance_type,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        context_length=model.context_length or 4096,
        precision=model.precision.value if model.precision else "fp16",
        region=data.region,
        is_custom_upload=is_custom,
    )

    # Create deployment record
    deployment = Deployment(
        user_id=user.id,
        model_id=model.id,
        cloud_provider=CloudProvider(data.cloud_provider),
        status=DeploymentStatus.PENDING,
        instance_type=instance_type,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        region=data.region,
        dockerfile=configs["dockerfile"],
        kubernetes_yaml=configs["kubernetes_yaml"],
        terraform_config=configs["terraform_config"],
    )
    db.add(deployment)
    await db.flush()
    await db.refresh(deployment)

    return DeploymentConfigResponse(
        deployment_id=deployment.id,
        dockerfile=configs["dockerfile"],
        kubernetes_yaml=configs["kubernetes_yaml"],
        terraform_config=configs["terraform_config"],
        ci_cd_pipeline=configs["ci_cd_pipeline"],
        cloudformation=configs.get("cloudformation", ""),
        quickstart=configs.get("quickstart", ""),
        merge_config=configs.get("merge_config", ""),
    )


@router.post("/{deployment_id}/start", response_model=DeploymentResponse)
async def start_deployment(
    deployment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Start the deployment process (placeholder)."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id, Deployment.user_id == user_id
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment.status = DeploymentStatus.PROVISIONING
    deployment.endpoint_url = f"https://llm-{deployment_id[:8]}.platform.example.com"
    await db.flush()
    await db.refresh(deployment)

    return deployment


@router.get("/list", response_model=list[DeploymentResponse])
async def list_deployments(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all deployments for the current user."""
    result = await db.execute(
        select(Deployment)
        .where(Deployment.user_id == user_id)
        .order_by(Deployment.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get deployment details."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id, Deployment.user_id == user_id
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


@router.post("/{deployment_id}/stop")
async def stop_deployment(
    deployment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Stop a running deployment."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id, Deployment.user_id == user_id
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment.status = DeploymentStatus.STOPPED
    await db.flush()
    return {"status": "stopped", "deployment_id": deployment_id}
