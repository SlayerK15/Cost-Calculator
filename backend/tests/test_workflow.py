"""Tests for n8n workflow API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock
from tests.conftest import auth_header


class TestWorkflowTrigger:
    @pytest.mark.asyncio
    async def test_trigger_requires_auth(self, client):
        resp = await client.post("/api/workflow/trigger", json={
            "domain": "medical",
            "use_case": "diagnose symptoms",
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_trigger_success_no_webhook(self, client, free_user):
        """Empty webhook URL → run stays pending."""
        _, token = free_user
        with patch("app.api.workflow.settings") as mock_settings:
            mock_settings.N8N_WEBHOOK_URL = ""
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = await client.post("/api/workflow/trigger",
                json={
                    "domain": "medical",
                    "use_case": "diagnose symptoms from text",
                },
                headers=auth_header(token),
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["domain"] == "medical"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_trigger_n8n_unreachable(self, client, free_user):
        """When n8n is down, run is created with FAILED status."""
        _, token = free_user
        resp = await client.post("/api/workflow/trigger",
            json={
                "domain": "legal",
                "use_case": "contract analysis",
            },
            headers=auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "failed"
        assert "Failed to reach n8n" in data["error_message"]

    @pytest.mark.asyncio
    async def test_trigger_n8n_success(self, client, free_user):
        """Mock n8n 200 → run transitions to searching."""
        import httpx
        _, token = free_user

        mock_n8n_response = httpx.Response(
            200,
            json={"executionId": "exec-123"},
        )

        async def mock_transport(request):
            # Only intercept calls to the n8n webhook URL
            if "webhook" in str(request.url):
                return mock_n8n_response
            # Should not happen in this test
            raise RuntimeError(f"Unexpected request to {request.url}")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))

        with patch("app.api.workflow.httpx.AsyncClient", return_value=mock_client):
            resp = await client.post("/api/workflow/trigger",
                json={
                    "domain": "finance",
                    "use_case": "Risk analysis",
                    "base_model": "llama3.1:8b-instruct-q4_K_M",
                },
                headers=auth_header(token),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "searching"
        assert data["n8n_execution_id"] == "exec-123"
        assert data["base_model"] == "llama3.1:8b-instruct-q4_K_M"

    @pytest.mark.asyncio
    async def test_trigger_missing_fields(self, client, free_user):
        _, token = free_user
        resp = await client.post("/api/workflow/trigger",
            json={"domain": "healthcare"},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_trigger_config_snapshot(self, client, free_user):
        """Config snapshot stores the input parameters."""
        _, token = free_user
        with patch("app.api.workflow.settings") as mock_settings:
            mock_settings.N8N_WEBHOOK_URL = ""
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = await client.post("/api/workflow/trigger",
                json={"domain": "robotics", "use_case": "arm control"},
                headers=auth_header(token),
            )
        data = resp.json()
        assert data["config_snapshot"]["domain"] == "robotics"
        assert data["config_snapshot"]["use_case"] == "arm control"


class TestWorkflowRuns:
    @pytest.mark.asyncio
    async def test_list_runs_requires_auth(self, client):
        resp = await client.get("/api/workflow/runs")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client, free_user):
        _, token = free_user
        resp = await client.get("/api/workflow/runs", headers=auth_header(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, client, free_user):
        _, token = free_user
        resp = await client.get("/api/workflow/runs/nonexistent", headers=auth_header(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_run_after_trigger(self, client, free_user):
        _, token = free_user
        with patch("app.api.workflow.settings") as mock_settings:
            mock_settings.N8N_WEBHOOK_URL = ""
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            trigger_resp = await client.post("/api/workflow/trigger",
                json={"domain": "education", "use_case": "tutor bot"},
                headers=auth_header(token),
            )
        run_id = trigger_resp.json()["id"]

        resp = await client.get(f"/api/workflow/runs/{run_id}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["domain"] == "education"


class TestWorkflowCallback:
    @pytest.mark.asyncio
    async def test_callback_without_secret(self, client):
        resp = await client.post("/api/workflow/runs/fake-id/callback", json={
            "status": "completed",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_callback_not_found(self, client):
        from app.core.config import get_settings
        secret = get_settings().N8N_CALLBACK_SECRET
        resp = await client.post(
            "/api/workflow/runs/nonexistent/callback",
            json={"status": "completed"},
            headers={"X-Callback-Secret": secret},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_callback_updates_status(self, client, free_user):
        from app.core.config import get_settings
        secret = get_settings().N8N_CALLBACK_SECRET

        _, token = free_user
        with patch("app.api.workflow.settings") as mock_settings:
            mock_settings.N8N_WEBHOOK_URL = ""
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            trigger_resp = await client.post("/api/workflow/trigger",
                json={"domain": "callback-test", "use_case": "testing"},
                headers=auth_header(token),
            )
        run_id = trigger_resp.json()["id"]

        resp = await client.post(
            f"/api/workflow/runs/{run_id}/callback",
            json={
                "status": "completed",
                "n8n_execution_id": "exec-456",
                "result": {"model_name": "test-model", "ollama_tag": "test:latest"},
            },
            headers={"X-Callback-Secret": secret},
        )
        assert resp.status_code == 200

        get_resp = await client.get(f"/api/workflow/runs/{run_id}", headers=auth_header(token))
        data = get_resp.json()
        assert data["status"] == "completed"
        assert data["result_snapshot"]["model_name"] == "test-model"

    @pytest.mark.asyncio
    async def test_callback_with_error(self, client, free_user):
        from app.core.config import get_settings
        secret = get_settings().N8N_CALLBACK_SECRET

        _, token = free_user
        with patch("app.api.workflow.settings") as mock_settings:
            mock_settings.N8N_WEBHOOK_URL = ""
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            trigger_resp = await client.post("/api/workflow/trigger",
                json={"domain": "error-test", "use_case": "fail test"},
                headers=auth_header(token),
            )
        run_id = trigger_resp.json()["id"]

        resp = await client.post(
            f"/api/workflow/runs/{run_id}/callback",
            json={"status": "failed", "error": "Training diverged at step 500"},
            headers={"X-Callback-Secret": secret},
        )
        assert resp.status_code == 200

        get_resp = await client.get(f"/api/workflow/runs/{run_id}", headers=auth_header(token))
        data = get_resp.json()
        assert data["status"] == "failed"
        assert "diverged" in data["error_message"]

    @pytest.mark.asyncio
    async def test_callback_status_transitions(self, client, free_user):
        from app.core.config import get_settings
        secret = get_settings().N8N_CALLBACK_SECRET

        _, token = free_user
        with patch("app.api.workflow.settings") as mock_settings:
            mock_settings.N8N_WEBHOOK_URL = ""
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            trigger_resp = await client.post("/api/workflow/trigger",
                json={"domain": "transitions", "use_case": "status flow"},
                headers=auth_header(token),
            )
        run_id = trigger_resp.json()["id"]

        for status in ["searching", "training", "deploying", "completed"]:
            resp = await client.post(
                f"/api/workflow/runs/{run_id}/callback",
                json={"status": status},
                headers={"X-Callback-Secret": secret},
            )
            assert resp.status_code == 200

        get_resp = await client.get(f"/api/workflow/runs/{run_id}", headers=auth_header(token))
        assert get_resp.json()["status"] == "completed"
