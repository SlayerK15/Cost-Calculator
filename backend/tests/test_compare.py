"""Tests for model comparison endpoint."""

import pytest


class TestCompareModels:
    @pytest.mark.asyncio
    async def test_compare_two_models(self, client):
        resp = await client.post("/api/compare/models", json={
            "models": [
                {"name": "Llama 8B", "parameters_billion": 8.0},
                {"name": "Mistral 7B", "parameters_billion": 7.3},
            ],
            "cloud_provider": "aws",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["comparisons"]) == 2
        assert data["cloud_provider"] == "aws"

    @pytest.mark.asyncio
    async def test_compare_four_models(self, client):
        resp = await client.post("/api/compare/models", json={
            "models": [
                {"name": "TinyLlama", "parameters_billion": 1.1},
                {"name": "Phi-3", "parameters_billion": 3.8},
                {"name": "Llama 8B", "parameters_billion": 8.0},
                {"name": "Llama 70B", "parameters_billion": 70.0},
            ],
            "cloud_provider": "aws",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["comparisons"]) == 4

    @pytest.mark.asyncio
    async def test_compare_too_few_models(self, client):
        resp = await client.post("/api/compare/models", json={
            "models": [{"name": "Solo", "parameters_billion": 8.0}],
            "cloud_provider": "aws",
        })
        assert resp.status_code == 422  # min_length=2 validation

    @pytest.mark.asyncio
    async def test_compare_too_many_models(self, client):
        resp = await client.post("/api/compare/models", json={
            "models": [
                {"name": f"Model {i}", "parameters_billion": i * 2.0}
                for i in range(1, 6)
            ],
            "cloud_provider": "aws",
        })
        assert resp.status_code == 422  # max_length=4 validation

    @pytest.mark.asyncio
    async def test_compare_response_fields(self, client):
        resp = await client.post("/api/compare/models", json={
            "models": [
                {"name": "A", "parameters_billion": 8.0},
                {"name": "B", "parameters_billion": 13.0},
            ],
            "cloud_provider": "aws",
        })
        data = resp.json()
        for c in data["comparisons"]:
            assert "model_name" in c
            assert "vram_required_gb" in c
            assert "total_cost_monthly" in c
            assert "gpu_type" in c
            assert "recommendation" in c
