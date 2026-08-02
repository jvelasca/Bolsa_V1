"""HTTP smoke: draft authoring + AI status (BOLSA_LLM_PROVIDER=none)."""

from __future__ import annotations

import os

import pytest
from bolsa_ai import reset_default_proxy
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_default_proxy()
    return create_app()


@pytest.mark.asyncio
async def test_ai_status_endpoint(app) -> None:
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ai/status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["preferredProvider"] == "none"
    assert data["mode"] == "none"
    assert "producerVersion" in data


@pytest.mark.asyncio
async def test_strategy_draft_from_prompt_heuristic(app) -> None:
    os.environ["BOLSA_LLM_PROVIDER"] = "none"
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/strategies/draft-from-prompt",
                json={"prompt": "estrategia cruce medias móviles"},
            )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["presetKey"]
    assert data["definition"]
    assert data["engine"]


@pytest.mark.asyncio
async def test_indicator_draft_from_prompt_heuristic(app) -> None:
    os.environ["BOLSA_LLM_PROVIDER"] = "none"
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/indicators/draft-from-prompt",
                json={"prompt": "RSI 14 en panel inferior"},
            )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["definitionId"] == "rsi"
    assert data["validated"] is True
