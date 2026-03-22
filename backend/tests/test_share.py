"""Tests for sharing and saved estimates endpoints."""

import pytest
from tests.conftest import auth_header


class TestShareCreate:
    @pytest.mark.asyncio
    async def test_create_share(self, client):
        resp = await client.post("/api/share/create", json={
            "estimate": {"total": 740},
            "model_name": "Llama 8B",
            "cloud_provider": "aws",
            "total_cost_monthly": 740.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "share_token" in data
        assert data["share_url"].startswith("/share/")

    @pytest.mark.asyncio
    async def test_create_share_with_api_comparison(self, client):
        resp = await client.post("/api/share/create", json={
            "estimate": {"total": 740},
            "api_comparison": {"providers": []},
            "model_name": "Llama 8B",
            "cloud_provider": "aws",
            "total_cost_monthly": 740.0,
        })
        assert resp.status_code == 200


class TestShareGet:
    @pytest.mark.asyncio
    async def test_get_shared_estimate(self, client):
        create_resp = await client.post("/api/share/create", json={
            "estimate": {"gpu": "A10G"},
            "model_name": "Test Model",
            "cloud_provider": "gcp",
            "total_cost_monthly": 500.0,
        })
        token = create_resp.json()["share_token"]

        resp = await client.get(f"/api/share/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "Test Model"
        assert data["total_cost_monthly"] == 500.0
        assert data["views_count"] == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_share(self, client):
        resp = await client.get("/api/share/nonexistent-token")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_view_count_increments(self, client):
        create_resp = await client.post("/api/share/create", json={
            "estimate": {},
            "model_name": "M",
            "cloud_provider": "aws",
            "total_cost_monthly": 100.0,
        })
        token = create_resp.json()["share_token"]

        await client.get(f"/api/share/{token}")
        await client.get(f"/api/share/{token}")
        resp = await client.get(f"/api/share/{token}")
        assert resp.json()["views_count"] == 3


class TestSavedEstimates:
    @pytest.mark.asyncio
    async def test_save_estimate(self, client, free_user):
        _, token = free_user
        resp = await client.post("/api/saved/estimates", json={
            "label": "My Llama Setup",
            "estimate": {"total": 740},
            "model_name": "Llama 8B",
            "cloud_provider": "aws",
            "total_cost_monthly": 740.0,
            "parameters_billion": 8.0,
        }, headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] == "My Llama Setup"
        assert data["id"] != ""

    @pytest.mark.asyncio
    async def test_list_saved_estimates(self, client, free_user):
        _, token = free_user
        # Save two
        for i in range(2):
            await client.post("/api/saved/estimates", json={
                "label": f"Estimate {i}",
                "estimate": {},
                "model_name": "M",
                "cloud_provider": "aws",
                "total_cost_monthly": 100.0 * (i + 1),
            }, headers=auth_header(token))

        resp = await client.get("/api/saved/estimates", headers=auth_header(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_delete_saved_estimate(self, client, free_user):
        _, token = free_user
        save_resp = await client.post("/api/saved/estimates", json={
            "label": "To Delete",
            "estimate": {},
            "model_name": "M",
            "cloud_provider": "aws",
            "total_cost_monthly": 100.0,
        }, headers=auth_header(token))
        est_id = save_resp.json()["id"]

        resp = await client.delete(f"/api/saved/estimates/{est_id}", headers=auth_header(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_nonexistent_saved(self, client, free_user):
        _, token = free_user
        resp = await client.delete("/api/saved/estimates/fake-id", headers=auth_header(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_save_requires_auth(self, client):
        resp = await client.post("/api/saved/estimates", json={
            "label": "No Auth",
            "estimate": {},
            "model_name": "M",
            "cloud_provider": "aws",
            "total_cost_monthly": 100.0,
        })
        assert resp.status_code in (401, 403)
