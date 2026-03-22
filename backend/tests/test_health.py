"""Tests for health check and basic app functionality."""

import pytest


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
