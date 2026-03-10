from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MergeModelEntry(BaseModel):
    model_hf_id: str
    weight: float = 0.5


class ModelConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None

    # Base model (one of these)
    base_model_id: Optional[str] = None
    base_model_hf_id: Optional[str] = None

    # LoRA adapter
    adapter_hf_id: Optional[str] = None

    # Merge config
    is_merge: bool = False
    merge_method: Optional[str] = None  # linear, slerp, ties, dare
    merge_models: Optional[list[MergeModelEntry]] = None

    # Quantization
    quantization_method: str = "none"  # none, gptq, awq, bnb_int8, bnb_int4

    # Inference params
    system_prompt: Optional[str] = None
    default_temperature: float = 0.7
    default_top_p: float = 0.9
    default_max_tokens: int = 512


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_model_id: Optional[str] = None
    base_model_hf_id: Optional[str] = None
    adapter_hf_id: Optional[str] = None
    is_merge: Optional[bool] = None
    merge_method: Optional[str] = None
    merge_models: Optional[list[MergeModelEntry]] = None
    quantization_method: Optional[str] = None
    system_prompt: Optional[str] = None
    default_temperature: Optional[float] = None
    default_top_p: Optional[float] = None
    default_max_tokens: Optional[int] = None
    pipeline_json: Optional[dict] = None


class ModelConfigResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    version: int
    base_model_id: Optional[str]
    base_model_hf_id: Optional[str]
    adapter_hf_id: Optional[str]
    is_merge: bool
    merge_method: Optional[str]
    merge_models_json: Optional[list]
    quantization_method: str
    system_prompt: Optional[str]
    default_temperature: float
    default_top_p: float
    default_max_tokens: int
    effective_parameters_billion: Optional[float]
    effective_precision: Optional[str]
    effective_context_length: Optional[int]
    estimated_vram_gb: Optional[float]
    pipeline_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelConfigVersionResponse(BaseModel):
    id: str
    config_id: str
    version: int
    snapshot_json: dict
    change_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SpecsCalculationResponse(BaseModel):
    effective_parameters_billion: float
    effective_precision: str
    effective_context_length: int
    estimated_vram_gb: float
    adapter_overhead_gb: float
    base_vram_gb: float


class HFModelResult(BaseModel):
    model_id: str
    name: str
    author: Optional[str]
    downloads: int
    likes: int
    pipeline_tag: Optional[str]


class HFAdapterResult(BaseModel):
    adapter_id: str
    name: str
    author: Optional[str]
    base_model: Optional[str]
    downloads: int
    likes: int
