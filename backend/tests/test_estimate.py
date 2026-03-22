"""Tests for cost estimation endpoints."""

import pytest
from tests.conftest import auth_header, create_user
from app.models.models import LLMModel, ModelSource, Precision, UserTier


class TestPublicEstimate:
    @pytest.mark.asyncio
    async def test_public_estimate_success(self, client):
        resp = await client.post("/api/estimate/public", json={
            "model_name": "Llama 3.1 8B",
            "parameters_billion": 8.0,
            "precision": "fp16",
            "context_length": 4096,
            "cloud_provider": "aws",
            "expected_qps": 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["vram_required_gb"] > 0
        assert data["cost_breakdown"]["total_cost_monthly"] > 0
        assert data["recommended_gpu"]["gpu_type"] != ""
        assert len(data["scaling_scenarios"]) == 3

    @pytest.mark.asyncio
    async def test_public_estimate_all_providers(self, client):
        for prov in ["aws", "gcp", "azure"]:
            resp = await client.post("/api/estimate/public", json={
                "parameters_billion": 8.0,
                "cloud_provider": prov,
            })
            assert resp.status_code == 200, f"Failed for {prov}"

    @pytest.mark.asyncio
    async def test_public_estimate_invalid_provider(self, client):
        resp = await client.post("/api/estimate/public", json={
            "parameters_billion": 8.0,
            "cloud_provider": "oracle",
        })
        # Should fail because no instances found
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_public_estimate_tiny_model(self, client):
        resp = await client.post("/api/estimate/public", json={
            "parameters_billion": 0.5,
            "precision": "fp16",
            "context_length": 2048,
            "cloud_provider": "aws",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_public_estimate_huge_model(self, client):
        resp = await client.post("/api/estimate/public", json={
            "parameters_billion": 405.0,
            "precision": "fp16",
            "context_length": 4096,
            "cloud_provider": "aws",
        })
        # May succeed or fail depending on available instances
        assert resp.status_code in (200, 400)


class TestPublicCompare:
    @pytest.mark.asyncio
    async def test_public_compare_multi_cloud(self, client):
        resp = await client.post(
            "/api/estimate/public/compare",
            params={
                "parameters_billion": 8.0,
                "model_name": "Test Model",
                "precision": "fp16",
                "context_length": 4096,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "estimates" in data
        assert len(data["estimates"]) >= 1  # at least one provider should work


class TestAPIProviderComparison:
    @pytest.mark.asyncio
    async def test_compare_api_providers(self, client):
        resp = await client.post("/api/estimate/public/compare-api-providers", json={
            "parameters_billion": 8.0,
            "precision": "fp16",
            "context_length": 4096,
            "cloud_provider": "aws",
            "expected_qps": 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly_requests"] > 0
        assert len(data["api_providers"]) > 0
        assert data["self_hosted_monthly"] > 0

    @pytest.mark.asyncio
    async def test_api_providers_sorted_by_cost(self, client):
        resp = await client.post("/api/estimate/public/compare-api-providers", json={
            "parameters_billion": 8.0,
            "cloud_provider": "aws",
            "expected_qps": 1.0,
        })
        data = resp.json()
        costs = [p["monthly_cost"] for p in data["api_providers"]]
        assert costs == sorted(costs)


class TestAuthenticatedEstimate:
    @pytest.mark.asyncio
    async def test_create_estimate_success(self, client, free_user, db_session):
        user, token = free_user
        model = LLMModel(
            user_id=user.id,
            name="Test Llama 8B",
            source=ModelSource.HUGGINGFACE,
            huggingface_id="meta-llama/Llama-3.1-8B",
            parameters_billion=8.0,
            precision=Precision.FP16,
            context_length=4096,
        )
        db_session.add(model)
        await db_session.flush()

        resp = await client.post("/api/estimate/", json={
            "model_id": model.id,
            "cloud_provider": "aws",
            "expected_qps": 1.0,
        }, headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "Test Llama 8B"
        assert data["id"] != ""

    @pytest.mark.asyncio
    async def test_create_estimate_model_not_found(self, client, free_user):
        _, token = free_user
        resp = await client.post("/api/estimate/", json={
            "model_id": "nonexistent-id",
            "cloud_provider": "aws",
        }, headers=auth_header(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_estimate_no_auth(self, client):
        resp = await client.post("/api/estimate/", json={
            "model_id": "some-id",
            "cloud_provider": "aws",
        })
        assert resp.status_code in (401, 403)


class TestOptimize:
    @pytest.mark.asyncio
    async def test_optimize_endpoint(self, client):
        resp = await client.post("/api/estimate/optimize", json={
            "parameters_billion": 8.0,
            "precision": "fp16",
            "context_length": 4096,
            "cloud_provider": "aws",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_monthly_cost"] > 0
        assert len(data["optimizations"]) > 0
