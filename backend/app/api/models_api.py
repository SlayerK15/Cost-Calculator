from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.config import get_settings
from app.models.models import LLMModel, ModelSource, Precision
from app.schemas.models import (
    ModelCreateHuggingFace,
    ModelCreateCustomUpload,
    ModelResponse,
)
from app.services.model_profiler import ModelProfiler

router = APIRouter(prefix="/models", tags=["models"])
settings = get_settings()


@router.get("/popular", response_model=list[dict])
async def get_popular_models():
    """Return curated list of popular open-source models."""
    profiler = ModelProfiler(hf_token=settings.HF_TOKEN)
    return profiler.get_popular_models()


@router.post("/huggingface", response_model=ModelResponse)
async def add_huggingface_model(
    data: ModelCreateHuggingFace,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add a model from Hugging Face."""
    profiler = ModelProfiler(hf_token=settings.HF_TOKEN)

    try:
        info = await profiler.profile_huggingface_model(data.huggingface_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    model = LLMModel(
        user_id=user_id,
        name=info["name"],
        source=ModelSource.HUGGINGFACE,
        huggingface_id=data.huggingface_id,
        parameters_billion=info.get("parameters_billion"),
        precision=Precision(data.precision),
        context_length=data.context_length or info.get("context_length", 4096),
        architecture=info.get("architecture"),
        is_parameters_estimated=info.get("is_parameters_estimated", False),
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


@router.post("/upload", response_model=ModelResponse)
async def add_custom_model(
    data: ModelCreateCustomUpload,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Register a custom uploaded model."""
    profiler = ModelProfiler()

    params_b = data.parameters_billion
    is_estimated = False

    if params_b is None:
        estimation = profiler.estimate_custom_model_params(
            data.file_size_bytes, data.precision
        )
        params_b = estimation["parameters_billion"]
        is_estimated = True

    model = LLMModel(
        user_id=user_id,
        name=data.name,
        source=ModelSource.CUSTOM_UPLOAD,
        file_size_bytes=data.file_size_bytes,
        parameters_billion=params_b,
        precision=Precision(data.precision),
        context_length=data.context_length,
        is_parameters_estimated=is_estimated,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


@router.get("/", response_model=list[ModelResponse])
async def list_models(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all models for the current user."""
    result = await db.execute(
        select(LLMModel).where(LLMModel.user_id == user_id).order_by(LLMModel.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific model."""
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id, LLMModel.user_id == user_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a model."""
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id, LLMModel.user_id == user_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await db.delete(model)
    return {"status": "deleted"}
