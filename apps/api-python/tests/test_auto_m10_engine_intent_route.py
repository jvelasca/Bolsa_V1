"""M10 — el contrato HTTP de la intención durable del operador.

Hermético: no toca PostgreSQL. Sustituye el store PG por su gemelo in-memory y la resolución
de cuenta por un doble, así que certifica lo que es del **borde** y no del store:

1. ``GET`` declara los tres hechos por separado (``envEnabled``, ``operatorState``,
   ``effectiveEnabled``) en vez de un booleano que oculte quién decidió.
2. ``POST enabled=false`` deja el apagado y ``GET`` lo lee: con el env en ``ON`` el motor
   queda **efectivamente apagado** (el ``OFF`` gana al env).
3. ``POST enabled=true`` vuelve a autorizar (con el env en ``ON``) y no enciende nada si el
   env está en ``OFF``.
4. Sin ámbito de cuenta el borde responde sin inventar una cuenta ni una intención.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_engine_intent as route
from bolsa_api.main import create_app
from bolsa_application.auto_engine_intent_store import InMemoryAutoEngineIntentStore

_PATH = "/api/auto/engine-intent"


def _app(
    *,
    scope: str | None,
    store: InMemoryAutoEngineIntentStore,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    app = create_app()

    async def _scope(_request: Any, _account_id: Any) -> str | None:
        return scope

    async def _session() -> Any:
        yield object()

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    monkeypatch.setattr(
        route, "PostgresAutoEngineIntentStore", lambda _session: store
    )
    app.dependency_overrides[route.get_db_session] = _session
    return app


async def _request(app: Any, method: str, **kwargs: Any) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, _PATH, **kwargs)


@pytest.mark.asyncio
async def test_get_without_declared_intent_lets_the_env_decide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    app = _app(scope="acc-1", store=InMemoryAutoEngineIntentStore(), monkeypatch=monkeypatch)

    response = await _request(app, "GET")

    assert response.status_code == 200
    body = response.json()
    assert body["accountId"] == "acc-1"
    assert body["operatorState"] is None, "sin fila no hay decisión del operador"
    assert body["envEnabled"] is True
    assert body["effectiveEnabled"] is True, "la ausencia no puede inventar un apagado"


@pytest.mark.asyncio
async def test_post_off_wins_over_the_enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    store = InMemoryAutoEngineIntentStore()
    app = _app(scope="acc-1", store=store, monkeypatch=monkeypatch)

    post = await _request(
        app, "POST", json={"enabled": False, "reason": "maintenance", "actor": "ops"}
    )

    assert post.status_code == 200
    posted = post.json()
    assert posted["operatorState"] == "OFF"
    assert posted["envEnabled"] is True
    assert posted["effectiveEnabled"] is False, "el OFF durable gana al env"
    assert posted["reason"] == "maintenance"
    assert posted["actor"] == "ops"

    read = (await _request(app, "GET")).json()
    assert read["operatorState"] == "OFF"
    assert read["effectiveEnabled"] is False


@pytest.mark.asyncio
async def test_post_on_authorizes_only_while_the_env_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    app = _app(scope="acc-1", store=InMemoryAutoEngineIntentStore(), monkeypatch=monkeypatch)

    body = (await _request(app, "POST", json={"enabled": True})).json()

    assert body["operatorState"] == "ON"
    assert body["effectiveEnabled"] is True

    # El env manda por debajo: un ON del operador no puede encender el motor por sí solo.
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    body = (await _request(app, "GET")).json()
    assert body["operatorState"] == "ON"
    assert body["envEnabled"] is False
    assert body["effectiveEnabled"] is False


@pytest.mark.asyncio
async def test_without_account_scope_nothing_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    store = InMemoryAutoEngineIntentStore()
    app = _app(scope=None, store=store, monkeypatch=monkeypatch)

    post = (await _request(app, "POST", json={"enabled": False})).json()

    assert post["accountId"] is None
    assert post["operatorState"] is None
    assert post["notes"] == ["no_account_scope", "intent_not_recorded"]
    assert len(store) == 0, "sin cuenta no se escribe una intención huérfana"
