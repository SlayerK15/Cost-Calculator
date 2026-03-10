"""
Model Profiler Service.

Handles:
- Fetching model metadata from Hugging Face
- Inferring parameters from file size for custom uploads
- (Future) Spinning up GPU containers for auto-profiling
"""

import math
import httpx
from typing import Optional

from app.services.cost_engine.calculator import BYTES_PER_PARAM


# Common model families and their known architectures
KNOWN_MODELS: dict[str, dict] = {
    "meta-llama/Llama-2-7b": {"parameters_billion": 7, "architecture": "LlamaForCausalLM", "context_length": 4096},
    "meta-llama/Llama-2-13b": {"parameters_billion": 13, "architecture": "LlamaForCausalLM", "context_length": 4096},
    "meta-llama/Llama-2-70b": {"parameters_billion": 70, "architecture": "LlamaForCausalLM", "context_length": 4096},
    "meta-llama/Meta-Llama-3-8B": {"parameters_billion": 8, "architecture": "LlamaForCausalLM", "context_length": 8192},
    "meta-llama/Meta-Llama-3-70B": {"parameters_billion": 70, "architecture": "LlamaForCausalLM", "context_length": 8192},
    "meta-llama/Meta-Llama-3.1-8B": {"parameters_billion": 8, "architecture": "LlamaForCausalLM", "context_length": 131072},
    "meta-llama/Meta-Llama-3.1-70B": {"parameters_billion": 70, "architecture": "LlamaForCausalLM", "context_length": 131072},
    "meta-llama/Meta-Llama-3.1-405B": {"parameters_billion": 405, "architecture": "LlamaForCausalLM", "context_length": 131072},
    "mistralai/Mistral-7B-v0.1": {"parameters_billion": 7.3, "architecture": "MistralForCausalLM", "context_length": 32768},
    "mistralai/Mixtral-8x7B-v0.1": {"parameters_billion": 46.7, "architecture": "MixtralForCausalLM", "context_length": 32768},
    "mistralai/Mistral-Large-Instruct-2407": {"parameters_billion": 123, "architecture": "MistralForCausalLM", "context_length": 32768},
    "google/gemma-2-9b": {"parameters_billion": 9.2, "architecture": "Gemma2ForCausalLM", "context_length": 8192},
    "google/gemma-2-27b": {"parameters_billion": 27, "architecture": "Gemma2ForCausalLM", "context_length": 8192},
    "Qwen/Qwen2-7B": {"parameters_billion": 7.6, "architecture": "Qwen2ForCausalLM", "context_length": 131072},
    "Qwen/Qwen2-72B": {"parameters_billion": 72, "architecture": "Qwen2ForCausalLM", "context_length": 131072},
    "microsoft/phi-3-mini-4k-instruct": {"parameters_billion": 3.8, "architecture": "PhiForCausalLM", "context_length": 4096},
    "microsoft/phi-3-medium-4k-instruct": {"parameters_billion": 14, "architecture": "PhiForCausalLM", "context_length": 4096},
}


class ModelProfiler:
    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token

    async def profile_huggingface_model(self, model_id: str) -> dict:
        """Fetch model info from Hugging Face API."""
        # Check known models first
        if model_id in KNOWN_MODELS:
            info = KNOWN_MODELS[model_id]
            return {
                "name": model_id.split("/")[-1],
                "source": "huggingface",
                "huggingface_id": model_id,
                "parameters_billion": info["parameters_billion"],
                "architecture": info["architecture"],
                "context_length": info["context_length"],
                "is_parameters_estimated": False,
            }

        # Query HF API
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://huggingface.co/api/models/{model_id}",
                headers=headers,
            )

        if resp.status_code != 200:
            raise ValueError(f"Model '{model_id}' not found on Hugging Face (status {resp.status_code})")

        data = resp.json()
        config = data.get("config", {})
        safetensors = data.get("safetensors", {})

        # Try to extract parameter count
        params_b = None
        is_estimated = False

        # Method 1: safetensors metadata
        if safetensors and "total" in safetensors:
            params_b = safetensors["total"] / 1e9

        # Method 2: model card / tags
        if params_b is None:
            for tag in data.get("tags", []):
                if tag.startswith("params:"):
                    try:
                        params_b = float(tag.split(":")[1]) / 1e9
                    except ValueError:
                        pass

        # Method 3: estimate from siblings (file sizes)
        if params_b is None:
            total_size = 0
            for sibling in data.get("siblings", []):
                fname = sibling.get("rfilename", "")
                if fname.endswith((".safetensors", ".bin", ".pt")):
                    size = sibling.get("size", 0)
                    total_size += size
            if total_size > 0:
                params_b = total_size / 2.0 / 1e9  # Assume FP16
                is_estimated = True

        # Extract architecture
        architecture = None
        if config:
            architectures = config.get("architectures", [])
            if architectures:
                architecture = architectures[0]

        # Extract context length
        context_length = 4096
        if config:
            for key in ("max_position_embeddings", "n_positions", "max_seq_len", "seq_length"):
                if key in config:
                    context_length = config[key]
                    break

        return {
            "name": data.get("modelId", model_id).split("/")[-1],
            "source": "huggingface",
            "huggingface_id": model_id,
            "parameters_billion": round(params_b, 2) if params_b else None,
            "architecture": architecture,
            "context_length": context_length,
            "is_parameters_estimated": is_estimated,
        }

    def estimate_custom_model_params(
        self, file_size_bytes: int, precision: str = "fp16"
    ) -> dict:
        """Infer parameter count from file size for uploaded models."""
        bpp = BYTES_PER_PARAM.get(precision, 2.0)
        params = file_size_bytes / bpp
        params_billion = params / 1e9

        return {
            "parameters_billion": round(params_billion, 2),
            "is_parameters_estimated": True,
            "estimation_method": f"file_size / {bpp} bytes_per_param ({precision})",
            "file_size_gb": round(file_size_bytes / (1024 ** 3), 2),
        }

    def get_popular_models(self) -> list[dict]:
        """Return a curated list of popular open-source models."""
        models = []
        for model_id, info in KNOWN_MODELS.items():
            models.append({
                "id": model_id,
                "name": model_id.split("/")[-1],
                "organization": model_id.split("/")[0],
                "parameters_billion": info["parameters_billion"],
                "architecture": info["architecture"],
                "context_length": info["context_length"],
            })
        return sorted(models, key=lambda m: m["parameters_billion"])
