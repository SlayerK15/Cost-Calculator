from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.api.subscription import require_tier
from app.models.models import (
    User, UserTier, LLMModel, ModelSource,
    ModelConfig, ModelConfigVersion, QuantizationMethod, MergeMethod,
)
from app.schemas.builder import (
    ModelConfigCreate, ModelConfigUpdate, ModelConfigResponse,
    ModelConfigVersionResponse, SpecsCalculationResponse,
    HFModelResult, HFAdapterResult,
)
from app.services.builder_service import (
    calculate_effective_specs, resolve_base_model_specs,
    search_hf_models, search_hf_adapters, snapshot_config,
)

router = APIRouter(prefix="/builder", tags=["model-builder"])


# ── CRUD ──

@router.post("/configs", response_model=ModelConfigResponse)
async def create_config(
    data: ModelConfigCreate,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    config = ModelConfig(
        user_id=user.id,
        name=data.name,
        description=data.description,
        base_model_id=data.base_model_id,
        base_model_hf_id=data.base_model_hf_id,
        adapter_hf_id=data.adapter_hf_id,
        is_merge=data.is_merge,
        merge_method=MergeMethod(data.merge_method) if data.merge_method else None,
        merge_models_json=[m.model_dump() for m in data.merge_models] if data.merge_models else None,
        quantization_method=QuantizationMethod(data.quantization_method),
        system_prompt=data.system_prompt,
        default_temperature=data.default_temperature,
        default_top_p=data.default_top_p,
        default_max_tokens=data.default_max_tokens,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


@router.get("/configs", response_model=list[ModelConfigResponse])
async def list_configs(
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelConfig)
        .where(ModelConfig.user_id == user.id)
        .order_by(ModelConfig.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/configs/{config_id}", response_model=ModelConfigResponse)
async def get_config(
    config_id: str,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.put("/configs/{config_id}", response_model=ModelConfigResponse)
async def update_config(
    config_id: str,
    data: ModelConfigUpdate,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle merge_models -> merge_models_json
    if "merge_models" in update_data:
        models_raw = update_data.pop("merge_models")
        config.merge_models_json = [m.model_dump() if hasattr(m, "model_dump") else m for m in models_raw] if models_raw else None

    # Handle merge_method enum
    if "merge_method" in update_data:
        val = update_data.pop("merge_method")
        config.merge_method = MergeMethod(val) if val else None

    # Handle quantization_method enum
    if "quantization_method" in update_data:
        val = update_data.pop("quantization_method")
        config.quantization_method = QuantizationMethod(val) if val else QuantizationMethod.NONE

    for key, value in update_data.items():
        setattr(config, key, value)

    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(config)
    return {"message": "Config deleted"}


# ── Versioning ──

@router.post("/configs/{config_id}/save-version", response_model=ModelConfigVersionResponse)
async def save_version(
    config_id: str,
    change_summary: str = "",
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    config.version += 1
    snapshot = snapshot_config(config)

    version = ModelConfigVersion(
        config_id=config.id,
        version=config.version,
        snapshot_json=snapshot,
        change_summary=change_summary or None,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


@router.get("/configs/{config_id}/versions", response_model=list[ModelConfigVersionResponse])
async def list_versions(
    config_id: str,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Config not found")

    result = await db.execute(
        select(ModelConfigVersion)
        .where(ModelConfigVersion.config_id == config_id)
        .order_by(ModelConfigVersion.version.desc())
    )
    return result.scalars().all()


# ── Specs Calculation ──

@router.post("/configs/{config_id}/calculate-specs", response_model=SpecsCalculationResponse)
async def calculate_specs(
    config_id: str,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    # Resolve base model specs
    base_params_b = None
    base_precision = "fp16"
    base_context = 4096

    if config.base_model_id:
        model_result = await db.execute(
            select(LLMModel).where(LLMModel.id == config.base_model_id)
        )
        base_model = model_result.scalar_one_or_none()
        if base_model:
            base_params_b = base_model.parameters_billion
            base_precision = base_model.precision.value if base_model.precision else "fp16"
            base_context = base_model.context_length or 4096

    base_specs = await resolve_base_model_specs(
        base_model_hf_id=config.base_model_hf_id,
        base_model_params_b=base_params_b,
        base_precision=base_precision,
        base_context_length=base_context,
    )

    quant_method = config.quantization_method.value if config.quantization_method else "none"
    specs = calculate_effective_specs(
        parameters_billion=base_specs["parameters_billion"],
        precision=base_specs["precision"],
        context_length=base_specs["context_length"],
        quantization_method=quant_method,
        has_adapter=bool(config.adapter_hf_id),
        is_merge=config.is_merge,
        merge_model_count=len(config.merge_models_json) if config.merge_models_json else 0,
    )

    # Persist computed specs on the config
    config.effective_parameters_billion = specs["effective_parameters_billion"]
    config.effective_precision = specs["effective_precision"]
    config.effective_context_length = specs["effective_context_length"]
    config.estimated_vram_gb = specs["estimated_vram_gb"]
    await db.flush()

    return SpecsCalculationResponse(**specs)


# ── HuggingFace Search ──

@router.get("/models/search", response_model=list[HFModelResult])
async def search_models(
    q: str,
    user: User = Depends(require_tier(UserTier.PRO)),
):
    results = await search_hf_models(q)
    return [HFModelResult(**r) for r in results]


@router.get("/adapters/search", response_model=list[HFAdapterResult])
async def search_adapters(
    q: str,
    user: User = Depends(require_tier(UserTier.PRO)),
):
    results = await search_hf_adapters(q)
    return [HFAdapterResult(**r) for r in results]


# ── Promote to Model Library ──

@router.post("/configs/{config_id}/to-model")
async def promote_to_model(
    config_id: str,
    user: User = Depends(require_tier(UserTier.PRO)),
    db: AsyncSession = Depends(get_db),
):
    """Convert a model config into an LLMModel in the user's library."""
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id,
            ModelConfig.user_id == user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    if not config.effective_parameters_billion:
        raise HTTPException(
            status_code=400,
            detail="Run calculate-specs first to compute effective parameters.",
        )

    from app.models.models import Precision

    precision_map = {
        "fp32": Precision.FP32,
        "fp16": Precision.FP16,
        "bf16": Precision.BF16,
        "int8": Precision.INT8,
        "int4": Precision.INT4,
    }

    model = LLMModel(
        user_id=user.id,
        name=f"{config.name} (v{config.version})",
        source=ModelSource.COMPOSED,
        huggingface_id=config.base_model_hf_id,
        parameters_billion=config.effective_parameters_billion,
        precision=precision_map.get(config.effective_precision, Precision.FP16),
        context_length=config.effective_context_length or 4096,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)

    return {
        "message": f"Model '{model.name}' added to your library.",
        "model_id": model.id,
    }
