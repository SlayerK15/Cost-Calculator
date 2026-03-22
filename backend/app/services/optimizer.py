"""
Cost Optimizer Service.

Analyzes a cost estimate and suggests optimizations
(precision reduction, spot instances, provider switch, etc.).
"""

from app.services.cost_engine.calculator import estimate_cost


def optimize_estimate(
    parameters_billion: float,
    precision: str,
    context_length: int,
    cloud_provider: str,
    expected_qps: float = 1.0,
    hours_per_day: int = 24,
    days_per_month: int = 30,
) -> dict:
    """
    Analyze current estimate and return optimization suggestions.
    """
    # Get current estimate
    current = estimate_cost(
        parameters_billion=parameters_billion,
        precision=precision,
        context_length=context_length,
        cloud_provider=cloud_provider,
        expected_qps=expected_qps,
        hours_per_day=hours_per_day,
        days_per_month=days_per_month,
    )
    if current is None:
        return {
            "current_monthly_cost": 0,
            "optimizations": [],
            "total_potential_savings": 0,
            "best_optimized_cost": 0,
        }

    current_cost = current.total_cost_monthly
    suggestions = []

    # 1. Precision reduction
    precision_options = {
        "fp32": ["fp16", "bf16", "int8", "int4"],
        "fp16": ["int8", "int4"],
        "bf16": ["int8", "int4"],
        "int8": ["int4"],
    }
    for target_prec in precision_options.get(precision, []):
        est = estimate_cost(
            parameters_billion=parameters_billion,
            precision=target_prec,
            context_length=context_length,
            cloud_provider=cloud_provider,
            expected_qps=expected_qps,
            hours_per_day=hours_per_day,
            days_per_month=days_per_month,
        )
        if est and est.total_cost_monthly < current_cost:
            savings = current_cost - est.total_cost_monthly
            suggestions.append({
                "type": "precision",
                "title": f"Switch to {target_prec.upper()} quantization",
                "description": f"Reduce from {precision.upper()} to {target_prec.upper()} to use less VRAM and a smaller GPU instance.",
                "current_cost": current_cost,
                "optimized_cost": est.total_cost_monthly,
                "savings_monthly": savings,
                "savings_pct": round(savings / current_cost * 100, 1),
                "tradeoff": "Minor quality degradation, ~1-3% accuracy loss for INT8, ~3-5% for INT4.",
            })
            break  # Only suggest the best precision reduction

    # 2. Spot instances (estimated 60-70% savings on compute)
    spot_discount = 0.65
    spot_cost = current.compute_cost_monthly * (1 - spot_discount) + (
        current.total_cost_monthly - current.compute_cost_monthly
    )
    if spot_cost < current_cost:
        savings = current_cost - spot_cost
        suggestions.append({
            "type": "spot",
            "title": "Use spot/preemptible instances",
            "description": f"Spot instances on {cloud_provider.upper()} save ~{int(spot_discount*100)}% on compute. Good for fault-tolerant workloads.",
            "current_cost": current_cost,
            "optimized_cost": round(spot_cost, 2),
            "savings_monthly": round(savings, 2),
            "savings_pct": round(savings / current_cost * 100, 1),
            "tradeoff": "Instances can be interrupted with 2-min warning. Need checkpointing and retry logic.",
        })

    # 3. Provider switch
    for alt_provider in ["aws", "gcp", "azure"]:
        if alt_provider == cloud_provider:
            continue
        est = estimate_cost(
            parameters_billion=parameters_billion,
            precision=precision,
            context_length=context_length,
            cloud_provider=alt_provider,
            expected_qps=expected_qps,
            hours_per_day=hours_per_day,
            days_per_month=days_per_month,
        )
        if est and est.total_cost_monthly < current_cost * 0.9:  # >10% savings
            savings = current_cost - est.total_cost_monthly
            suggestions.append({
                "type": "provider_switch",
                "title": f"Switch to {alt_provider.upper()}",
                "description": f"Deploy on {alt_provider.upper()} ({est.instance_type}) for lower cost.",
                "current_cost": current_cost,
                "optimized_cost": est.total_cost_monthly,
                "savings_monthly": round(savings, 2),
                "savings_pct": round(savings / current_cost * 100, 1),
                "tradeoff": "Requires migrating deployment to a different cloud provider.",
            })
            break  # Only suggest the cheapest alternative

    # 4. Autoscaling / reduce hours
    if hours_per_day == 24 and days_per_month >= 28:
        # Suggest business-hours only
        est = estimate_cost(
            parameters_billion=parameters_billion,
            precision=precision,
            context_length=context_length,
            cloud_provider=cloud_provider,
            expected_qps=expected_qps,
            hours_per_day=12,
            days_per_month=22,
        )
        if est:
            savings = current_cost - est.total_cost_monthly
            if savings > 0:
                suggestions.append({
                    "type": "autoscaling",
                    "title": "Run business hours only (12h/day, 22 days/mo)",
                    "description": "If your workload is business-hours only, scale to zero outside peak times.",
                    "current_cost": current_cost,
                    "optimized_cost": est.total_cost_monthly,
                    "savings_monthly": round(savings, 2),
                    "savings_pct": round(savings / current_cost * 100, 1),
                    "tradeoff": "No availability outside business hours. Cold start latency on scale-up.",
                })

    # 5. Reserved instances (1-year commitment ~30% savings)
    reserved_cost = current_cost * 0.70
    savings = current_cost - reserved_cost
    suggestions.append({
        "type": "reserved",
        "title": "1-year reserved instance commitment",
        "description": "Commit to a 1-year term for ~30% savings on compute costs.",
        "current_cost": current_cost,
        "optimized_cost": round(reserved_cost, 2),
        "savings_monthly": round(savings, 2),
        "savings_pct": 30.0,
        "tradeoff": "Locked into 1-year commitment. No flexibility to change instance type.",
    })

    # Sort by savings descending
    suggestions.sort(key=lambda s: -s["savings_monthly"])

    total_potential = max(s["savings_monthly"] for s in suggestions) if suggestions else 0
    best_cost = min(s["optimized_cost"] for s in suggestions) if suggestions else current_cost

    return {
        "current_monthly_cost": current_cost,
        "optimizations": suggestions,
        "total_potential_savings": round(total_potential, 2),
        "best_optimized_cost": round(best_cost, 2),
    }
