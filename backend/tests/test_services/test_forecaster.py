"""Tests for the cost forecaster service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.services.forecaster import forecast_deployment


class TestForecaster:
    @pytest.mark.asyncio
    async def test_forecast_with_no_metrics(self):
        """No metrics → graceful fallback."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await forecast_deployment("fake-deployment-id", db=mock_session)

        assert result is not None
        assert result["confidence"] == "low"
        assert result["daily_forecast"] == []

    @pytest.mark.asyncio
    async def test_forecast_with_mock_metrics(self):
        """Mock 30 days of metrics → should produce a forecast."""
        now = datetime.now(timezone.utc)
        mock_metrics = []
        for i in range(30):
            m = MagicMock()
            m.timestamp = now - timedelta(days=30 - i)
            m.cost_usd = 10.0 + i * 0.5  # linearly increasing cost
            m.requests_count = 100 + i * 10
            m.tokens_generated = 50000 + i * 1000
            mock_metrics.append(m)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_metrics
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await forecast_deployment("fake-deployment-id", db=mock_session)

        assert result is not None
        assert result["projected_monthly_cost"] > 0
        assert len(result["daily_forecast"]) == 30
        assert result["confidence"] in ("low", "medium", "high")
