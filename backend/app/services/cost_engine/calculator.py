"""
Core cost estimation engine.

Calculates VRAM requirements, selects appropriate GPU instances,
and produces detailed cost breakdowns for deploying LLMs on AWS/GCP/Azure.
"""

import math
from dataclasses import dataclass
from app.services.cost_engine.gpu_catalog import (
    CloudInstance,
    GPU_SPECS,
    get_instances_for_provider,
)


BYTES_PER_PARAM = {
    "fp32": 4.0,
    "fp16": 2.0,
    "bf16": 2.0,
    "int8": 1.0,
    "int4": 0.5,
}

HOURS_PER_MONTH = 730  # average


@dataclass
class VRAMEstimate:
    model_weights_gb: float
    kv_cache_gb: float
    activation_overhead_gb: float
    framework_overhead_gb: float
    total_gb: float


@dataclass
class GPUSelection:
    instance: CloudInstance
    fits: bool
    utilization_pct: float


@dataclass
class CostResult:
    # Instance info
    cloud_provider: str
    instance_type: str
    gpu_type: str
    gpu_count: int
    total_vram_gb: float

    # VRAM
    vram_required_gb: float
    vram_breakdown: VRAMEstimate

    # Monthly costs
    compute_cost_monthly: float
    storage_cost_monthly: float
    bandwidth_cost_monthly: float
    idle_cost_monthly: float
    kv_cache_overhead_cost: float
    total_cost_monthly: float

    # Scaling scenarios
    scaling_scenarios: list[dict]

    # Recommendations
    recommendation: str
    optimized_config: dict


def estimate_parameters_from_file_size(
    file_size_bytes: int, precision: str = "fp16"
) -> float:
    """Estimate parameter count (in billions) from model file size."""
    bytes_per_param = BYTES_PER_PARAM.get(precision, 2.0)
    params = file_size_bytes / bytes_per_param
    return params / 1e9


def calculate_vram(
    parameters_billion: float,
    precision: str,
    context_length: int,
    batch_size: int = 1,
    num_layers: int = None,
    hidden_dim: int = None,
) -> VRAMEstimate:
    """
    Calculate total VRAM requirement for serving a model.

    Components:
    1. Model weights: params * bytes_per_param
    2. KV cache: estimated from context length and model size
    3. Activation memory: temporary buffers during inference
    4. Framework overhead: vLLM/TGI runtime overhead
    """
    bytes_per_param = BYTES_PER_PARAM.get(precision, 2.0)

    # 1. Model weights
    model_weights_bytes = parameters_billion * 1e9 * bytes_per_param
    model_weights_gb = model_weights_bytes / (1024 ** 3)

    # 2. KV cache estimation
    # For transformer models: KV cache ≈ 2 * num_layers * hidden_dim * context_length * batch_size * bytes_per_param
    # If we don't know architecture details, estimate from parameter count
    if num_layers and hidden_dim:
        kv_cache_bytes = (
            2 * num_layers * hidden_dim * context_length * batch_size * bytes_per_param
        )
    else:
        # Heuristic: KV cache is roughly proportional to params and context
        # For a 7B model at 4096 context, KV cache ≈ 1-2GB
        estimated_hidden = int(math.sqrt(parameters_billion * 1e9 / 100))
        estimated_layers = max(int(parameters_billion * 4), 32)
        kv_cache_bytes = (
            2 * estimated_layers * estimated_hidden * context_length * batch_size * 2
        )
    kv_cache_gb = kv_cache_bytes / (1024 ** 3)

    # 3. Activation overhead (~10-20% of model weights during inference)
    activation_overhead_gb = model_weights_gb * 0.15

    # 4. Framework overhead (vLLM/TGI runtime: ~1-3GB)
    framework_overhead_gb = min(3.0, max(1.0, model_weights_gb * 0.05))

    total_gb = model_weights_gb + kv_cache_gb + activation_overhead_gb + framework_overhead_gb

    return VRAMEstimate(
        model_weights_gb=round(model_weights_gb, 2),
        kv_cache_gb=round(kv_cache_gb, 2),
        activation_overhead_gb=round(activation_overhead_gb, 2),
        framework_overhead_gb=round(framework_overhead_gb, 2),
        total_gb=round(total_gb, 2),
    )


def select_gpu_instance(
    vram_required_gb: float,
    provider: str,
    prefer_cost_efficiency: bool = True,
) -> CloudInstance | None:
    """
    Select the cheapest GPU instance that fits the model's VRAM requirements.
    """
    instances = get_instances_for_provider(provider)
    candidates = [i for i in instances if i.total_vram_gb >= vram_required_gb]

    if not candidates:
        return None

    if prefer_cost_efficiency:
        candidates.sort(key=lambda i: i.cost_per_hour)
    else:
        # Sort by VRAM headroom (tightest fit)
        candidates.sort(key=lambda i: i.total_vram_gb - vram_required_gb)

    return candidates[0]


def calculate_storage_cost(
    model_size_gb: float, provider_storage_rate: float
) -> float:
    """Monthly storage cost for model weights + checkpoints."""
    # Model weights + 50% for checkpoints/logs/cache
    total_storage_gb = model_size_gb * 1.5
    return total_storage_gb * provider_storage_rate


def calculate_bandwidth_cost(
    avg_tokens_per_request: int,
    expected_qps: float,
    provider_bandwidth_rate: float,
    hours_per_day: int = 24,
    days_per_month: int = 30,
) -> float:
    """Monthly egress bandwidth cost, scaled to actual active hours."""
    # ~4 bytes per token output, rough estimate
    bytes_per_request = avg_tokens_per_request * 4
    bytes_per_second = bytes_per_request * expected_qps
    active_seconds = hours_per_day * 3600 * days_per_month
    gb_per_month = (bytes_per_second * active_seconds) / (1024 ** 3)
    # First 1GB free on most providers; simplified
    return max(0, gb_per_month - 1) * provider_bandwidth_rate


def calculate_idle_cost(
    cost_per_hour: float,
    hours_per_day: int,
    days_per_month: int = 30,
) -> float:
    """
    Informational: how much you'd waste if the instance ran 24/7 all 30 days
    instead of only hours_per_day × days_per_month.
    Not included in total — helps the user see potential savings.
    """
    full_month_hours = 24 * 30
    active_hours = hours_per_day * days_per_month
    wasted_hours = full_month_hours - active_hours
    if wasted_hours <= 0:
        return 0.0
    return wasted_hours * cost_per_hour


def generate_scaling_scenarios(
    base_cost_monthly: float,
    instance: CloudInstance,
    expected_qps: float,
    autoscaling_enabled: bool,
    min_replicas: int,
    max_replicas: int,
) -> list[dict]:
    """Generate scaling scenarios: baseline, high concurrency, enterprise."""
    scenarios = []

    # Baseline
    scenarios.append({
        "name": "Baseline",
        "description": f"Single instance, {expected_qps} QPS",
        "replicas": 1,
        "total_monthly_cost": round(base_cost_monthly, 2),
        "cost_per_request": round(
            base_cost_monthly / max(expected_qps * 3600 * 24 * 30, 1), 6
        ),
    })

    # High concurrency (3x QPS)
    high_qps = expected_qps * 3
    high_replicas = min(max(math.ceil(high_qps / max(expected_qps, 0.1)), 2), max_replicas)
    scenarios.append({
        "name": "High Concurrency",
        "description": f"{high_replicas} replicas, ~{high_qps:.1f} QPS",
        "replicas": high_replicas,
        "total_monthly_cost": round(base_cost_monthly * high_replicas, 2),
        "cost_per_request": round(
            (base_cost_monthly * high_replicas) / max(high_qps * 3600 * 24 * 30, 1), 6
        ),
    })

    # Enterprise (10x QPS)
    ent_qps = expected_qps * 10
    ent_replicas = min(max(math.ceil(ent_qps / max(expected_qps, 0.1)), 4), max_replicas * 3)
    scenarios.append({
        "name": "Enterprise",
        "description": f"{ent_replicas} replicas, ~{ent_qps:.1f} QPS with autoscaling",
        "replicas": ent_replicas,
        "total_monthly_cost": round(base_cost_monthly * ent_replicas * 0.85, 2),  # 15% savings from spot/reserved
        "cost_per_request": round(
            (base_cost_monthly * ent_replicas * 0.85) / max(ent_qps * 3600 * 24 * 30, 1), 6
        ),
    })

    return scenarios


def estimate_cost(
    parameters_billion: float,
    precision: str,
    context_length: int,
    cloud_provider: str,
    expected_qps: float = 1.0,
    avg_tokens_per_request: int = 512,
    hours_per_day: int = 24,
    days_per_month: int = 30,
    model_file_size_gb: float = None,
    autoscaling_enabled: bool = False,
    min_replicas: int = 1,
    max_replicas: int = 3,
) -> CostResult | None:
    """
    Main entry point: produce a full cost estimate for deploying a model.

    Cost = hourly_rate × hours_per_day × days_per_month
    So 8 hours/day for 20 days = 160 billable hours.
    """
    # 1. Calculate VRAM requirements
    vram = calculate_vram(parameters_billion, precision, context_length)

    # 2. Select GPU instance
    instance = select_gpu_instance(vram.total_gb, cloud_provider)
    if instance is None:
        return None

    # 3. Calculate costs — only pay for active hours on active days
    billable_hours = hours_per_day * days_per_month
    compute_monthly = instance.cost_per_hour * billable_hours

    storage_gb = model_file_size_gb or (parameters_billion * BYTES_PER_PARAM.get(precision, 2.0) * 1e9 / (1024 ** 3))
    # Storage is always-on (charged per month regardless of hours)
    storage_monthly = calculate_storage_cost(storage_gb, instance.storage_cost_per_gb_month)

    # Bandwidth scales with actual usage hours
    bandwidth_monthly = calculate_bandwidth_cost(
        avg_tokens_per_request, expected_qps, instance.bandwidth_cost_per_gb,
        hours_per_day, days_per_month,
    )

    idle_monthly = calculate_idle_cost(instance.cost_per_hour, hours_per_day, days_per_month)

    # KV cache overhead: if the cache is large relative to VRAM, we may need more GPU memory
    kv_overhead_cost = 0.0
    if vram.kv_cache_gb > vram.model_weights_gb * 0.5:
        kv_overhead_cost = compute_monthly * 0.05  # 5% premium for high KV cache usage

    # idle_monthly is informational (cost if left running 24/7), not added to total.
    # Total reflects the cost assuming the instance is shut down during off-hours.
    total_monthly = (
        compute_monthly + storage_monthly + bandwidth_monthly + kv_overhead_cost
    )

    # 4. Scaling scenarios
    scenarios = generate_scaling_scenarios(
        total_monthly, instance, expected_qps,
        autoscaling_enabled, min_replicas, max_replicas,
    )

    # 5. Recommendation
    utilization = (vram.total_gb / instance.total_vram_gb) * 100
    recommendation = _generate_recommendation(
        instance, vram, utilization, parameters_billion, precision
    )

    # 6. Optimized config
    optimized = _suggest_optimization(
        parameters_billion, precision, vram, instance, cloud_provider
    )

    return CostResult(
        cloud_provider=cloud_provider,
        instance_type=instance.instance_type,
        gpu_type=instance.gpu_type,
        gpu_count=instance.gpu_count,
        total_vram_gb=instance.total_vram_gb,
        vram_required_gb=vram.total_gb,
        vram_breakdown=vram,
        compute_cost_monthly=round(compute_monthly, 2),
        storage_cost_monthly=round(storage_monthly, 2),
        bandwidth_cost_monthly=round(bandwidth_monthly, 2),
        idle_cost_monthly=round(idle_monthly, 2),
        kv_cache_overhead_cost=round(kv_overhead_cost, 2),
        total_cost_monthly=round(total_monthly, 2),
        scaling_scenarios=scenarios,
        recommendation=recommendation,
        optimized_config=optimized,
    )


def _generate_recommendation(
    instance: CloudInstance,
    vram: VRAMEstimate,
    utilization: float,
    params_b: float,
    precision: str,
) -> str:
    lines = []
    lines.append(
        f"Recommended: {instance.instance_type} with {instance.gpu_count}x {instance.gpu_type.replace('_', ' ')} "
        f"({instance.total_vram_gb}GB total VRAM)."
    )
    lines.append(f"VRAM utilization: {utilization:.0f}% ({vram.total_gb:.1f}/{instance.total_vram_gb}GB).")

    if utilization > 90:
        lines.append(
            "Warning: VRAM utilization is very high. Consider quantizing to a lower precision "
            "or choosing a larger instance for production use."
        )
    elif utilization < 40:
        lines.append(
            "VRAM is underutilized. You could increase batch size or context length, "
            "or consider a smaller (cheaper) instance."
        )

    if precision == "fp32":
        lines.append(
            "Tip: Using FP32 doubles memory vs FP16 with minimal quality gain for inference. "
            "Consider FP16 or BF16 to cut costs."
        )

    if params_b > 70:
        lines.append(
            "This is a large model (>70B params). Multi-GPU inference with tensor parallelism is required."
        )

    return " ".join(lines)


def _suggest_optimization(
    params_b: float,
    precision: str,
    vram: VRAMEstimate,
    current_instance: CloudInstance,
    provider: str,
) -> dict:
    suggestions = {}

    # Suggest quantization if using FP16+
    if precision in ("fp32", "fp16", "bf16") and params_b > 7:
        lower_precision = "int8" if precision in ("fp32",) else "int4"
        reduced_vram = calculate_vram(params_b, lower_precision, 4096)
        cheaper = select_gpu_instance(reduced_vram.total_gb, provider)
        if cheaper and cheaper.cost_per_hour < current_instance.cost_per_hour:
            savings_pct = (
                (1 - cheaper.cost_per_hour / current_instance.cost_per_hour) * 100
            )
            suggestions["quantization"] = {
                "target_precision": lower_precision,
                "new_vram_gb": reduced_vram.total_gb,
                "new_instance": cheaper.instance_type,
                "new_cost_per_hour": cheaper.cost_per_hour,
                "savings_pct": round(savings_pct, 1),
            }

    # Suggest spot/preemptible instances
    suggestions["spot_instances"] = {
        "description": "Use spot/preemptible instances for non-critical workloads",
        "estimated_savings_pct": 60,
        "tradeoff": "Instances may be preempted with 30s-2min notice",
    }

    # Suggest reserved instances for steady workloads
    suggestions["reserved_pricing"] = {
        "description": "1-year reserved instance commitment",
        "estimated_savings_pct": 30,
        "tradeoff": "Requires upfront commitment, less flexibility",
    }

    return suggestions
