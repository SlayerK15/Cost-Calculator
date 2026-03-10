"""
Builder service: computes effective specs, searches HuggingFace, manages versions.
"""

import httpx
import json
from typing import Optional

from app.services.cost_engine.calculator import calculate_vram, BYTES_PER_PARAM
from app.services.model_profiler import ModelProfiler, KNOWN_MODELS


# Map quantization methods to effective precision for VRAM calculation
QUANT_TO_PRECISION = {
    "none": None,  # use base model precision
    "gptq": "int4",
    "awq": "int4",
    "bnb_int8": "int8",
    "bnb_int4": "int4",
}


async def resolve_base_model_specs(
    base_model_hf_id: Optional[str] = None,
    base_model_params_b: Optional[float] = None,
    base_precision: str = "fp16",
    base_context_length: int = 4096,
) -> dict:
    """Resolve base model specs from HF ID or provided values."""
    if base_model_hf_id:
        # Check known models first
        if base_model_hf_id in KNOWN_MODELS:
            info = KNOWN_MODELS[base_model_hf_id]
            return {
                "parameters_billion": info["parameters_billion"],
                "precision": base_precision,
                "context_length": info["context_length"],
            }

        # Try HuggingFace API
        try:
            profiler = ModelProfiler()
            info = await profiler.profile_huggingface_model(base_model_hf_id)
            return {
                "parameters_billion": info.get("parameters_billion", base_model_params_b or 7),
                "precision": base_precision,
                "context_length": info.get("context_length", base_context_length),
            }
        except Exception:
            pass

    return {
        "parameters_billion": base_model_params_b or 7,
        "precision": base_precision,
        "context_length": base_context_length,
    }


def calculate_effective_specs(
    parameters_billion: float,
    precision: str,
    context_length: int,
    quantization_method: str = "none",
    has_adapter: bool = False,
    adapter_rank: int = 16,
    is_merge: bool = False,
    merge_model_count: int = 0,
) -> dict:
    """
    Calculate effective specs for a composed model configuration.

    Returns effective params, precision, VRAM estimate, and breakdown.
    """
    # Effective precision after quantization
    effective_precision = QUANT_TO_PRECISION.get(quantization_method)
    if effective_precision is None:
        effective_precision = precision

    # Base VRAM
    vram = calculate_vram(parameters_billion, effective_precision, context_length)
    base_vram_gb = vram.total_gb

    # Adapter overhead: LoRA adds ~1-5% of base params depending on rank
    adapter_overhead_gb = 0.0
    if has_adapter:
        # LoRA overhead: rank * 2 * num_layers * hidden_dim * 2 bytes
        # Rough estimate: ~2-5% of model weights
        adapter_fraction = min(0.05, adapter_rank * 0.003)
        adapter_overhead_gb = vram.model_weights_gb * adapter_fraction

    # Merge: no extra VRAM at inference — merging happens at build time
    # The resulting model has the same parameter count as the base

    total_vram = base_vram_gb + adapter_overhead_gb

    return {
        "effective_parameters_billion": round(parameters_billion, 2),
        "effective_precision": effective_precision,
        "effective_context_length": context_length,
        "estimated_vram_gb": round(total_vram, 2),
        "adapter_overhead_gb": round(adapter_overhead_gb, 2),
        "base_vram_gb": round(base_vram_gb, 2),
    }


async def search_hf_models(query: str, limit: int = 20) -> list[dict]:
    """Search HuggingFace for text-generation models."""
    url = "https://huggingface.co/api/models"
    params = {
        "search": query,
        "pipeline_tag": "text-generation",
        "sort": "downloads",
        "direction": "-1",
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            models = resp.json()
            return [
                {
                    "model_id": m.get("modelId", m.get("id", "")),
                    "name": m.get("modelId", m.get("id", "")).split("/")[-1],
                    "author": m.get("author", ""),
                    "downloads": m.get("downloads", 0),
                    "likes": m.get("likes", 0),
                    "pipeline_tag": m.get("pipeline_tag", ""),
                }
                for m in models
            ]
    except Exception:
        return []


async def search_hf_adapters(query: str, limit: int = 20) -> list[dict]:
    """Search HuggingFace for LoRA adapters."""
    url = "https://huggingface.co/api/models"
    params = {
        "search": query,
        "filter": "lora",
        "sort": "downloads",
        "direction": "-1",
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            models = resp.json()
            return [
                {
                    "adapter_id": m.get("modelId", m.get("id", "")),
                    "name": m.get("modelId", m.get("id", "")).split("/")[-1],
                    "author": m.get("author", ""),
                    "base_model": m.get("cardData", {}).get("base_model", None) if isinstance(m.get("cardData"), dict) else None,
                    "downloads": m.get("downloads", 0),
                    "likes": m.get("likes", 0),
                }
                for m in models
            ]
    except Exception:
        return []


def snapshot_config(config) -> dict:
    """Serialize a ModelConfig to a JSON-safe dict for versioning."""
    return {
        "name": config.name,
        "description": config.description,
        "base_model_id": config.base_model_id,
        "base_model_hf_id": config.base_model_hf_id,
        "adapter_hf_id": config.adapter_hf_id,
        "is_merge": config.is_merge,
        "merge_method": config.merge_method.value if config.merge_method else None,
        "merge_models_json": config.merge_models_json,
        "quantization_method": config.quantization_method.value if config.quantization_method else "none",
        "system_prompt": config.system_prompt,
        "default_temperature": config.default_temperature,
        "default_top_p": config.default_top_p,
        "default_max_tokens": config.default_max_tokens,
        "effective_parameters_billion": config.effective_parameters_billion,
        "effective_precision": config.effective_precision,
        "effective_context_length": config.effective_context_length,
        "estimated_vram_gb": config.estimated_vram_gb,
        "pipeline_json": config.pipeline_json,
    }
