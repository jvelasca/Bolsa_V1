"""Política de evidencia por cuenta: defaults estrictos, validación y contrato HTTP hermético."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.account_evidence_policy as route
from bolsa_api.main import create_app
from bolsa_application.account_evidence_policy import (
    InMemoryAccountEvidencePolicyStore,
    default_evidence_policy,
    policy_from_dict,
    validate_policy,
)

_PATH = "/api/account-evidence-policy"


def test_defaults_are_strict_and_valid() -> None:
    policy = default_evidence_policy("acc-1")
    assert policy.is_default is True
    assert validate_policy(policy) == []
    assert policy.min_round_trip_cost_bps == 2 * (5 + 5) + 2


@pytest.mark.parametrize(
    "field",
    ["minCommissionBps", "minSlippageBps"],
)
def test_zero_costs_are_rejected(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        policy_from_dict("acc-1", {field: 0})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minWindows", 2),
        ("minPositiveWindowPct", 10),
        ("holdoutPct", 0),
        ("maxDrawdownPct", float("nan")),
        ("minNetReturnPct", float("inf")),
        ("minWindows", 30.5),
        ("minWindows", True),
    ],
)
def test_out_of_range_or_non_finite_values_are_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValueError, match=field):
        policy_from_dict("acc-1", {field: value})


@pytest.mark.asyncio
async def test_store_returns_defaults_then_versions_writes() -> None:
    store = InMemoryAccountEvidencePolicyStore()
    assert (await store.load("acc-1")).is_default is True
    policy = policy_from_dict("acc-1", {"minWindows": 60})
    assert await store.save(policy) is True
    assert await store.save(replace(policy, min_windows=80)) is False
    saved = await store.load("acc-1")
    assert (saved.min_windows, saved.version, saved.is_default) == (80, 2, False)
    assert (await store.load("acc-2")).is_default is True


def _app(store: InMemoryAccountEvidencePolicyStore, monkeypatch: pytest.MonkeyPatch) -> Any:
    app = create_app()

    async def _scope(_request: Any, _account_id: Any) -> str | None:
        return "acc-1"

    async def _session() -> Any:
        yield object()

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    monkeypatch.setattr(route, "PostgresAccountEvidencePolicyStore", lambda _s: store)
    app.dependency_overrides[route.get_db_session] = _session
    return app


async def _call(app: Any, method: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, _PATH, **kwargs)


@pytest.mark.asyncio
async def test_http_put_persists_partial_update_and_get_reads_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(InMemoryAccountEvidencePolicyStore(), monkeypatch)
    assert (await _call(app, "GET")).json()["isDefault"] is True

    response = await _call(app, "PUT", json={"minWindows": 60, "actor": "ana"})
    assert response.status_code == 200
    body = response.json()
    assert body["minWindows"] == 60
    assert body["minTradesTotal"] == 100, "lo no enviado conserva el valor previo"
    assert body["isDefault"] is False
    assert body["actor"] == "ana"
    assert (await _call(app, "GET")).json()["minWindows"] == 60


@pytest.mark.asyncio
async def test_http_put_rejects_invalid_values_with_422(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryAccountEvidencePolicyStore()
    app = _app(store, monkeypatch)
    response = await _call(app, "PUT", json={"minSlippageBps": 0})
    assert response.status_code == 422
    assert "minSlippageBps" in response.json()["detail"]
    assert (await store.load("acc-1")).is_default is True, "un 422 no escribe nada"
    assert (await _call(app, "PUT", json={"desconocido": 1})).status_code == 422
