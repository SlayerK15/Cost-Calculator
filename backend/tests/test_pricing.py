"""Tests for pricing status and webhook endpoints."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def _mock_async_session(mock_session):
    """Create a context manager mock for async_session()."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestPricingStatus:
    @pytest.mark.asyncio
    async def test_pricing_status(self, client):
        """Status endpoint returns valid response (empty DB = zero counts)."""
        mock_session = AsyncMock()
        # The endpoint makes 4 queries: gpu latest, api latest, gpu count, api count
        gpu_latest_result = MagicMock()
        gpu_latest_result.scalar_one_or_none.return_value = None
        api_latest_result = MagicMock()
        api_latest_result.scalar_one_or_none.return_value = None
        gpu_count_result = MagicMock()
        gpu_count_result.scalars.return_value.all.return_value = []
        api_count_result = MagicMock()
        api_count_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[gpu_latest_result, api_latest_result, gpu_count_result, api_count_result]
        )

        with patch("app.api.pricing.async_session", return_value=_mock_async_session(mock_session)):
            resp = await client.get("/api/pricing/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["gpu_prices_count"] == 0
        assert data["api_prices_count"] == 0
        assert data["using_live_prices"] is False


class TestPricingWebhook:
    @pytest.mark.asyncio
    async def test_webhook_without_secret(self, client):
        resp = await client.post("/api/pricing/webhook/gpu-prices", json={
            "prices": [],
        })
        # Should reject without proper webhook secret (None != SECRET_KEY)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_with_valid_secret(self, client):
        from app.core.config import get_settings
        secret = get_settings().SECRET_KEY
        resp = await client.post(
            "/api/pricing/webhook/gpu-prices",
            json={"prices": []},
            headers={"X-Webhook-Secret": secret},
        )
        # Empty prices list → 400
        assert resp.status_code == 400
