"""Tests for authentication endpoints."""

import uuid
import pytest
from tests.conftest import auth_header

VALID_PASSWORD = "Secure123"


def _email():
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": _email(),
            "password": VALID_PASSWORD,
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        email = _email()
        payload = {"email": email, "password": VALID_PASSWORD}
        await client.post("/api/auth/register", json=payload)
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": VALID_PASSWORD,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_too_short(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": _email(),
            "password": "Ab1",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_no_digit(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": _email(),
            "password": "abcdefgh",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_no_letter(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": _email(),
            "password": "12345678",
        })
        assert resp.status_code == 422


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        email = _email()
        await client.post("/api/auth/register", json={
            "email": email,
            "password": VALID_PASSWORD,
        })
        resp = await client.post("/api/auth/login", json={
            "email": email,
            "password": VALID_PASSWORD,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        email = _email()
        await client.post("/api/auth/register", json={
            "email": email,
            "password": VALID_PASSWORD,
        })
        resp = await client.post("/api/auth/login", json={
            "email": email,
            "password": "WrongPass1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/auth/login", json={
            "email": _email(),
            "password": VALID_PASSWORD,
        })
        assert resp.status_code == 401


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_success(self, client, free_user):
        user, token = free_user
        resp = await client.get("/api/auth/me", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email
        assert data["id"] == user.id

    @pytest.mark.asyncio
    async def test_get_me_no_auth(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        resp = await client.get("/api/auth/me", headers=auth_header("invalid.token.here"))
        assert resp.status_code == 401
