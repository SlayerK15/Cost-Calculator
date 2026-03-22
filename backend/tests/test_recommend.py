"""Tests for model recommendation endpoint."""

import pytest


class TestRecommendModels:
    @pytest.mark.asyncio
    async def test_recommend_chat(self, client):
        resp = await client.post("/api/recommend/models", json={
            "use_case": "chat",
            "max_budget_monthly": 5000.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["use_case"] == "chat"
        assert data["budget"] == 5000.0
        assert len(data["results"]) > 0

    @pytest.mark.asyncio
    async def test_recommend_coding(self, client):
        resp = await client.post("/api/recommend/models", json={
            "use_case": "coding",
            "max_budget_monthly": 10000.0,
        })
        assert resp.status_code == 200
        assert len(resp.json()["results"]) > 0

    @pytest.mark.asyncio
    async def test_recommend_with_provider(self, client):
        resp = await client.post("/api/recommend/models", json={
            "use_case": "general",
            "max_budget_monthly": 50000.0,
            "cloud_provider": "gcp",
        })
        data = resp.json()
        for r in data["results"]:
            assert r["cloud_provider"] == "gcp"

    @pytest.mark.asyncio
    async def test_recommend_low_budget(self, client):
        resp = await client.post("/api/recommend/models", json={
            "use_case": "chat",
            "max_budget_monthly": 10.0,
        })
        assert resp.status_code == 200
        # Very low budget — may return empty results
        data = resp.json()
        for r in data["results"]:
            assert r["monthly_cost"] <= 10.0

    @pytest.mark.asyncio
    async def test_recommend_result_fields(self, client):
        resp = await client.post("/api/recommend/models", json={
            "use_case": "chat",
            "max_budget_monthly": 50000.0,
        })
        data = resp.json()
        if data["results"]:
            r = data["results"][0]
            assert "model_name" in r
            assert "parameters_billion" in r
            assert "quality_tier" in r
            assert "tags" in r
            assert "monthly_cost" in r
            assert "instance_type" in r

    @pytest.mark.asyncio
    async def test_recommend_max_five(self, client):
        resp = await client.post("/api/recommend/models", json={
            "use_case": "general",
            "max_budget_monthly": 999999.0,
        })
        assert len(resp.json()["results"]) <= 5
