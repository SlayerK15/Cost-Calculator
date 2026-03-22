"""Tests for AI agent chatbot endpoints."""

import pytest


class TestAgentChatSync:
    @pytest.mark.asyncio
    async def test_sync_chat(self, client):
        resp = await client.post("/api/agent/chat/sync", json={
            "message": "How much does it cost to deploy Llama 8B on AWS?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert len(data["message"]) > 0

    @pytest.mark.asyncio
    async def test_sync_chat_with_context(self, client):
        resp = await client.post("/api/agent/chat/sync", json={
            "message": "Recommend a model for coding",
            "context": {"page": "estimate"},
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sync_chat_with_history(self, client):
        resp = await client.post("/api/agent/chat/sync", json={
            "message": "What about on GCP?",
            "history": [
                {"role": "user", "content": "How much to deploy Llama 8B?"},
                {"role": "assistant", "content": "About $740/month on AWS."},
            ],
        })
        assert resp.status_code == 200


class TestAgentChatSSE:
    @pytest.mark.asyncio
    async def test_sse_chat(self, client):
        resp = await client.post("/api/agent/chat", json={
            "message": "What GPU do I need for a 7B model?",
        })
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

    @pytest.mark.asyncio
    async def test_sse_chat_produces_data(self, client):
        resp = await client.post("/api/agent/chat", json={
            "message": "Compare AWS and GCP for LLM hosting",
        })
        body = resp.text
        assert "data:" in body
        assert "[DONE]" in body
