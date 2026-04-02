import pytest
import httpx
import os

@pytest.mark.anyio
async def test_root_live():
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "CryptoVault API is live" in response.json()["message"]

@pytest.mark.anyio
async def test_health_live():
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        # Database should be connected in production
        assert response.json()["database"] == "connected"

@pytest.mark.anyio
async def test_ping_live():
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        response = await client.get("/api/ping")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["message"] == "pong"

@pytest.mark.anyio
async def test_csrf_token_generation():
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        response = await client.get("/api/csrf")
        assert response.status_code == 200
        assert "csrf_token" in response.json()
        assert "csrf_token" in response.cookies
