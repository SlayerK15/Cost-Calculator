"""
Usage Forecaster Service.

Projects future costs using simple linear regression on deployment metrics.
No external dependencies — uses basic least-squares math.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DeploymentMetric


async def forecast_deployment(
    managed_deployment_id: str,
    db: AsyncSession,
    forecast_days: int = 30,
) -> dict:
    """
    Forecast next month's costs based on historical metrics.
    Uses simple linear regression on daily cost aggregates.
    """
    # Fetch last 90 days of metrics
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    result = await db.execute(
        select(DeploymentMetric)
        .where(DeploymentMetric.managed_deployment_id == managed_deployment_id)
        .where(DeploymentMetric.timestamp >= cutoff)
        .order_by(DeploymentMetric.timestamp.asc())
    )
    metrics = result.scalars().all()

    if len(metrics) < 3:
        return {
            "projected_monthly_cost": 0,
            "current_monthly_cost": 0,
            "change_pct": 0,
            "daily_forecast": [],
            "confidence": "low",
        }

    # Aggregate daily costs
    daily_costs: dict[str, float] = {}
    for m in metrics:
        day_key = m.timestamp.strftime("%Y-%m-%d")
        daily_costs[day_key] = daily_costs.get(day_key, 0) + m.cost_usd

    sorted_days = sorted(daily_costs.keys())
    if len(sorted_days) < 3:
        return {
            "projected_monthly_cost": 0,
            "current_monthly_cost": 0,
            "change_pct": 0,
            "daily_forecast": [],
            "confidence": "low",
        }

    # Simple linear regression: y = slope * x + intercept
    n = len(sorted_days)
    xs = list(range(n))
    ys = [daily_costs[d] for d in sorted_days]

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        slope = 0
        intercept = sum_y / n
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

    # R-squared for confidence
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    if r_squared > 0.7:
        confidence = "high"
    elif r_squared > 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    # Current month cost (last 30 days of data)
    last_30_days = sorted_days[-30:] if len(sorted_days) >= 30 else sorted_days
    current_monthly = sum(daily_costs[d] for d in last_30_days)
    if len(last_30_days) < 30:
        current_monthly = current_monthly / len(last_30_days) * 30

    # Project next N days
    daily_forecast = []
    last_date = datetime.strptime(sorted_days[-1], "%Y-%m-%d")
    for i in range(1, forecast_days + 1):
        future_x = n - 1 + i
        projected = max(0, slope * future_x + intercept)
        future_date = last_date + timedelta(days=i)
        daily_forecast.append({
            "date": future_date.strftime("%Y-%m-%d"),
            "projected_cost": round(projected, 2),
        })

    projected_monthly = sum(d["projected_cost"] for d in daily_forecast)
    change_pct = ((projected_monthly - current_monthly) / current_monthly * 100) if current_monthly > 0 else 0

    return {
        "projected_monthly_cost": round(projected_monthly, 2),
        "current_monthly_cost": round(current_monthly, 2),
        "change_pct": round(change_pct, 1),
        "daily_forecast": daily_forecast,
        "confidence": confidence,
    }
