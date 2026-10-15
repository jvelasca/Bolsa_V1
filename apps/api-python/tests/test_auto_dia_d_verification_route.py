"""P2/v111 — contrato HTTP de la verificación DÍA-D ENLAZADA a un ciclo AUTO.

Hermético (sin PostgreSQL): se sustituyen la sesión, el repositorio y el RESOLUTOR de hechos
durables por dobles, y se verifica la resolución de cuenta. Cubre: registro idempotente (doble),
identidad DERIVADA del servidor (no del payload), ``404`` para un ciclo inexistente, ``409`` si
lo declarado contradice el hecho durable, fail-closed sin cuenta (POST 400 / GET vacío) y que un
ciclo sin identidad de estrategia persiste el hueco declarado (nunca cadena vacía).
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_dia_d_verification as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app
from bolsa_application.dia_d_cycle_verification import DiaDCycleFacts
from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification


class _FakeRepo:
    def __init__(self) -> None:
        self.rows: list[DiaDCycleVerification] = []

    async def upsert(self, **kwargs: Any) -> DiaDCycleVerification:
        row = DiaDCycleVerification(
            id=f"v-{len(self.rows) + 1}",
            cycle_id=kwargs["cycle_id"],
            account_id=kwargs.get("account_id"),
            instrument_id=kwargs["instrument_id"],
            symbol=kwargs["symbol"],
            dia_d=kwargs["dia_d"],
            end_date=kwargs["end_date"],
            mode=kwargs["mode"],
            created_at="2026-04-02T00:00:00+00:00",
            strategy_preset_key=kwargs.get("strategy_preset_key"),
            strategy_version=kwargs.get("strategy_version"),
            strategy_definition_id=kwargs.get("strategy_definition_id"),
            band=kwargs.get("band"),
            result=kwargs.get("result"),
            research_evidence_id=kwargs.get("research_evidence_id"),
            facts_hash=kwargs.get("facts_hash"),
            verified_by=kwargs.get("verified_by"),
        )
        self.rows = [r for r in self.rows if r.cycle_id != row.cycle_id] + [row]
        return row

    async def list_verifications(
        self,
        *,
        account_id: str | None = None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]:
        return [
            r
            for r in self.rows
            if (cycle_id is None or r.cycle_id == cycle_id)
            and (account_id is None or r.account_id == account_id)
        ]


class _Session:
    async def commit(self) -> None:  # pragma: no cover
        return None

    async def rollback(self) -> None:  # pragma: no cover
        return None


_FACTS = {
    "cyc-1": DiaDCycleFacts(
        cycle_id="cyc-1",
        instrument_id="inst-durable-1",
        symbol="ACA",
        strategy_preset_key="sma_crossover",
        strategy_version="ver-durable",
    ),
    "cyc-2": DiaDCycleFacts(
        cycle_id="cyc-2",
        instrument_id="inst-durable-2",
        symbol="ITX",
        strategy_preset_key=None,
        strategy_version=None,
    ),
}


def _app(repo: _FakeRepo, scope: str | None):  # noqa: ANN202 — helper de test
    app = create_app()

    async def _session():  # noqa: ANN202
        yield _Session()

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    async def _facts(_session: Any, _account_id: str, *, cycle_id: str):  # noqa: ANN202
        return _FACTS.get(cycle_id)

    app.dependency_overrides[get_db_session] = _session
    route.get_dia_d_cycle_verification_repository = lambda _session: repo  # type: ignore[assignment]
    route.resolve_account_scope_or_default = _scope  # type: ignore[assignment]
    route.resolve_dia_d_cycle_facts = _facts  # type: ignore[assignment]
    return app


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cycleId": "cyc-1",
        "diaD": "2026-04-01",
        "endDate": "2026-04-02",
        "mode": "auto",
    }
    body.update(overrides)
    return body


async def _post(app, body: dict[str, Any]):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/auto/dia-d-verifications", json=body)


async def _get(app, path: str):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_post_persists_server_derived_identity() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    response = await _post(
        app,
        _body(
            band="favorable",
            result={"band": "favorable", "returnPct": 3.2},
            researchEvidenceId="ev-1",
        ),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["cycleId"] == "cyc-1"
    assert data["accountId"] == "acc-1"
    # Derivado del SERVIDOR (aunque el payload no lo declare).
    assert data["instrumentId"] == "inst-durable-1"
    assert data["symbol"] == "ACA"
    assert data["strategyPresetKey"] == "sma_crossover"
    assert data["strategyVersion"] == "ver-durable"
    assert data["factsHash"]
    assert repo.rows[0].account_id == "acc-1"


@pytest.mark.asyncio
async def test_post_accepts_consistent_declared_identity() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    response = await _post(
        app,
        _body(instrumentId="inst-durable-1", symbol="ACA", strategyPresetKey="sma_crossover"),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_rejects_conflicting_declared_identity() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    response = await _post(app, _body(strategyPresetKey="rsi_mean_reversion"))
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "cycle_identity_conflict"
    assert repo.rows == []


@pytest.mark.asyncio
async def test_post_rejects_unknown_cycle() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    response = await _post(app, _body(cycleId="cyc-unknown"))
    assert response.status_code == 404
    assert response.json()["detail"] == "cycle_not_found"
    assert repo.rows == []


@pytest.mark.asyncio
async def test_post_declares_gaps_without_fabricating_identity() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    data = (await _post(app, _body(cycleId="cyc-2"))).json()["data"]
    assert data["strategyPresetKey"] is None
    assert data["strategyVersion"] is None
    assert data["strategyDefinitionId"] is None


@pytest.mark.asyncio
async def test_post_without_scope_is_fail_closed() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope=None)
    response = await _post(app, _body())
    assert response.status_code == 400
    assert repo.rows == []


@pytest.mark.asyncio
async def test_post_without_indispensable_key_is_rejected() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    response = await _post(app, _body(cycleId=""))
    assert response.status_code == 400
    assert repo.rows == []


@pytest.mark.asyncio
async def test_get_lists_verifications_of_the_cycle() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    await _post(app, _body())
    await _post(app, _body(cycleId="cyc-2"))
    body = (await _get(app, "/api/auto/dia-d-verifications?cycleId=cyc-1")).json()
    assert body["total"] == 1
    assert body["data"][0]["cycleId"] == "cyc-1"
    assert body["notes"] == []


@pytest.mark.asyncio
async def test_get_without_cycle_filter_lists_all_of_the_account() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc-1")
    await _post(app, _body())
    await _post(app, _body(cycleId="cyc-2"))
    body = (await _get(app, "/api/auto/dia-d-verifications")).json()
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_get_without_scope_is_fail_closed() -> None:
    repo = _FakeRepo()
    app = _app(repo, scope=None)
    body = (await _get(app, "/api/auto/dia-d-verifications?cycleId=cyc-1")).json()
    assert body["data"] == []
    assert body["notes"] == ["no_account_scope"]
