"""
Model Recommender Service.

Matches user requirements (use case, budget, provider) against a curated
catalog of open-source models and returns the best options with cost estimates.
"""

from app.services.cost_engine.calculator import estimate_cost


MODEL_CATALOG = [
    {
        "name": "TinyLlama 1.1B",
        "parameters_billion": 1.1,
        "context_length": 2048,
        "tags": ["general", "chat", "edge"],
        "quality_tier": "good",
    },
    {
        "name": "Phi-3 Mini 3.8B",
        "parameters_billion": 3.8,
        "context_length": 4096,
        "tags": ["general", "coding", "reasoning", "chat"],
        "quality_tier": "good",
    },
    {
        "name": "Mistral 7B",
        "parameters_billion": 7.3,
        "context_length": 32768,
        "tags": ["general", "coding", "chat", "instruction-following"],
        "quality_tier": "great",
    },
    {
        "name": "Llama 3.1 8B",
        "parameters_billion": 8,
        "context_length": 131072,
        "tags": ["general", "coding", "chat", "reasoning", "instruction-following"],
        "quality_tier": "great",
    },
    {
        "name": "Gemma 2 9B",
        "parameters_billion": 9.2,
        "context_length": 8192,
        "tags": ["general", "chat", "reasoning"],
        "quality_tier": "great",
    },
    {
        "name": "Qwen2 7B",
        "parameters_billion": 7.6,
        "context_length": 131072,
        "tags": ["general", "coding", "multilingual", "chat"],
        "quality_tier": "great",
    },
    {
        "name": "Phi-3 Medium 14B",
        "parameters_billion": 14,
        "context_length": 4096,
        "tags": ["general", "coding", "reasoning"],
        "quality_tier": "great",
    },
    {
        "name": "Gemma 2 27B",
        "parameters_billion": 27,
        "context_length": 8192,
        "tags": ["general", "chat", "reasoning", "summarization"],
        "quality_tier": "excellent",
    },
    {
        "name": "Mixtral 8x7B",
        "parameters_billion": 46.7,
        "context_length": 32768,
        "tags": ["general", "coding", "chat", "multilingual"],
        "quality_tier": "excellent",
    },
    {
        "name": "Llama 3.1 70B",
        "parameters_billion": 70,
        "context_length": 131072,
        "tags": ["general", "coding", "chat", "reasoning", "instruction-following", "summarization"],
        "quality_tier": "excellent",
    },
    {
        "name": "Qwen2 72B",
        "parameters_billion": 72,
        "context_length": 131072,
        "tags": ["general", "coding", "multilingual", "reasoning"],
        "quality_tier": "excellent",
    },
    {
        "name": "Mistral Large 123B",
        "parameters_billion": 123,
        "context_length": 32768,
        "tags": ["general", "coding", "reasoning", "multilingual"],
        "quality_tier": "excellent",
    },
    {
        "name": "Llama 3.1 405B",
        "parameters_billion": 405,
        "context_length": 131072,
        "tags": ["general", "coding", "reasoning", "instruction-following"],
        "quality_tier": "excellent",
    },
]

QUALITY_ORDER = {"good": 0, "great": 1, "excellent": 2}


def recommend_models(
    use_case: str,
    max_budget_monthly: float,
    cloud_provider: str | None = None,
    precision: str = "fp16",
    min_context_length: int = 4096,
) -> list[dict]:
    """
    Find the best models for a use case within a budget.
    Returns up to 5 results sorted by quality then cost.
    """
    use_case_lower = use_case.lower().strip()

    # Filter by use case tag and context length
    candidates = []
    for model in MODEL_CATALOG:
        if not any(use_case_lower in t for t in model["tags"]):
            continue
        if model["context_length"] < min_context_length:
            continue
        candidates.append(model)

    if not candidates:
        # Fallback: return all models within budget
        candidates = [m for m in MODEL_CATALOG if m["context_length"] >= min_context_length]

    # For each candidate, estimate cost on specified provider(s)
    providers = [cloud_provider] if cloud_provider else ["aws", "gcp", "azure"]
    results = []

    for model in candidates:
        best_result = None
        for prov in providers:
            est = estimate_cost(
                parameters_billion=model["parameters_billion"],
                precision=precision,
                context_length=min(model["context_length"], 4096),  # practical serving context
                cloud_provider=prov,
                expected_qps=1.0,
                hours_per_day=24,
                days_per_month=30,
            )
            if est is None:
                continue
            if est.total_cost_monthly > max_budget_monthly:
                continue
            if best_result is None or est.total_cost_monthly < best_result["monthly_cost"]:
                best_result = {
                    "model_name": model["name"],
                    "parameters_billion": model["parameters_billion"],
                    "quality_tier": model["quality_tier"],
                    "tags": model["tags"],
                    "cloud_provider": prov,
                    "instance_type": est.instance_type,
                    "gpu_type": est.gpu_type,
                    "gpu_count": est.gpu_count,
                    "vram_required_gb": est.vram_required_gb,
                    "monthly_cost": est.total_cost_monthly,
                    "recommendation": est.recommendation,
                }
        if best_result:
            results.append(best_result)

    # Sort by quality descending, then cost ascending
    results.sort(
        key=lambda r: (-QUALITY_ORDER.get(r["quality_tier"], 0), r["monthly_cost"])
    )

    return results[:5]
