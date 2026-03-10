"""Service for generating simulated metrics for managed deployments."""

import random
import math
from datetime import datetime, timezone, timedelta


def generate_metrics_snapshot(
    gpu_count: int = 1,
    status: str = "running",
    autoscaling_enabled: bool = False,
    min_replicas: int = 1,
    max_replicas: int = 3,
    cost_per_hour: float = 3.0,
) -> dict:
    """Generate a single realistic metrics snapshot for a managed deployment."""
    if status != "running":
        return {
            "requests_count": 0,
            "avg_latency_ms": 0,
            "p99_latency_ms": 0,
            "tokens_generated": 0,
            "gpu_utilization": 0,
            "vram_used_gb": 0,
            "cpu_utilization": 0,
            "active_replicas": 0,
            "cost_usd": 0,
        }

    # Simulate realistic load patterns
    base_gpu_util = random.uniform(0.3, 0.85)
    base_requests = int(random.gauss(150, 50))
    base_requests = max(10, base_requests)

    active_replicas = min_replicas
    if autoscaling_enabled and base_gpu_util > 0.7:
        scale_factor = (base_gpu_util - 0.7) / 0.3
        active_replicas = min(max_replicas, min_replicas + int(scale_factor * (max_replicas - min_replicas)))

    avg_latency = random.gauss(120, 30)
    avg_latency = max(40, avg_latency)
    p99_latency = avg_latency * random.uniform(2.5, 4.0)

    tokens = base_requests * int(random.gauss(256, 80))
    vram_per_gpu = random.uniform(15, 40)

    interval_hours = 1 / 60  # 1-minute interval
    cost = cost_per_hour * active_replicas * interval_hours

    return {
        "requests_count": base_requests,
        "avg_latency_ms": round(avg_latency, 1),
        "p99_latency_ms": round(p99_latency, 1),
        "tokens_generated": max(0, tokens),
        "gpu_utilization": round(base_gpu_util, 3),
        "vram_used_gb": round(vram_per_gpu * gpu_count, 1),
        "cpu_utilization": round(random.uniform(0.1, 0.5), 3),
        "active_replicas": active_replicas,
        "cost_usd": round(cost, 4),
    }


def generate_time_series(
    hours: int = 24,
    interval_minutes: int = 15,
    gpu_count: int = 1,
    cost_per_hour: float = 3.0,
) -> list[dict]:
    """Generate a time series of metrics for charting."""
    now = datetime.now(timezone.utc)
    points = []
    total_intervals = (hours * 60) // interval_minutes

    for i in range(total_intervals):
        ts = now - timedelta(minutes=(total_intervals - i) * interval_minutes)
        # Simulate daily traffic pattern (sine wave peaking at 2pm UTC)
        hour_of_day = ts.hour + ts.minute / 60
        traffic_multiplier = 0.4 + 0.6 * max(0, math.sin((hour_of_day - 6) * math.pi / 12))

        base_requests = int(random.gauss(150, 40) * traffic_multiplier)
        base_requests = max(5, base_requests)
        gpu_util = min(0.95, random.gauss(0.5, 0.15) * traffic_multiplier + 0.1)
        gpu_util = max(0.05, gpu_util)

        avg_latency = random.gauss(100, 20) + (1 - traffic_multiplier) * 20
        avg_latency = max(30, avg_latency)

        tokens = base_requests * int(random.gauss(256, 60))
        cost = cost_per_hour * (interval_minutes / 60)

        points.append({
            "timestamp": ts.isoformat(),
            "requests_count": base_requests,
            "avg_latency_ms": round(avg_latency, 1),
            "p99_latency_ms": round(avg_latency * random.uniform(2.5, 4.0), 1),
            "tokens_generated": max(0, tokens),
            "gpu_utilization": round(gpu_util, 3),
            "vram_used_gb": round(random.uniform(15, 40) * gpu_count, 1),
            "cpu_utilization": round(random.uniform(0.1, 0.5), 3),
            "active_replicas": 1,
            "cost_usd": round(cost, 4),
        })

    return points


def generate_scaling_events(hours: int = 24) -> list[dict]:
    """Generate simulated auto-scaling events."""
    now = datetime.now(timezone.utc)
    events = []
    num_events = random.randint(2, max(3, hours // 4))

    for i in range(num_events):
        offset = random.randint(10, hours * 60)
        ts = now - timedelta(minutes=offset)
        gpu_util = random.uniform(0.4, 0.95)
        direction = "scale_up" if gpu_util > 0.7 else "scale_down"
        from_replicas = random.randint(1, 3)
        to_replicas = from_replicas + (1 if direction == "scale_up" else -1)
        to_replicas = max(1, to_replicas)

        events.append({
            "timestamp": ts.isoformat(),
            "event": direction,
            "reason": f"GPU utilization {'above' if direction == 'scale_up' else 'below'} threshold ({gpu_util:.0%})",
            "from_replicas": from_replicas,
            "to_replicas": to_replicas,
            "gpu_utilization": round(gpu_util, 3),
        })

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events
