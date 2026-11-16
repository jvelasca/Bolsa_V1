"""R2 — contrato HTTP del disparador gobernado del embudo (``POST /api/auto/orchestrator/run``).

Hermético: sin PostgreSQL, sin orquestador real. Se sustituyen sesión, ledger, cuenta y
composición del orquestador por dobles. Cubre:

* ``dryRun`` por defecto: un cuerpo que lo omite no escribe el lifecycle (recibo con
  ``writes`` declaradas y ``promoted=false``), sin fila de ACTIVE.
* Idempotencia: repetir el mismo POST devuelve el mismo ``runId`` con ``replayed=true``.
* ``409`` para un instrumento fuera de ESTUDIO y para cuenta cerrada.
* ``400`` si se pide ``toPhase='active'``; ``422`` si el cliente mete evidencia extra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from bolsa_application.auto_orchestrator import OrchestratorResult
from bolsa_application.orchestrator_trigger import InMemoryTriggerLedger
from bolsa_application.strategy_lifecycle_store import InMemoryStrategyLifecycleStore
from bolsa_domain.entities.strategy_lifecycle import GateResult, GateStatus
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_orchestrator as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:  # pragma: no cover
        return None


@dataclass
class _Resolution:
    status: str = "ok"
    instrument_ids: list[str] = field(default_factory=lambda: ["AAA"])


class _FakeOrchestrator:
    """Orquestador mínimo: resuelve universo y devuelve un ciclo ya en FINALISTA."""

    def __init__(self, *, instruments: tuple[str, ...] = ("AAA",)) -> None:
        self.deps = type("_Deps", (), {"store": InMemoryStrategyLifecycleStore()})()
        self._instruments = list(instruments)
        self.calls = 0

    async def resolve_universe(self) -> Any:
        return _Resolution(instrument_ids=self._instruments)

    async def run_cycle(self, *, instrument_id: str, run_id: str, max_phase: str) -> Any:
        self.calls += 1
        # El ciclo REAL escribe candidata/evaluación/finalista; el doble reproduce la
        # escritura observable para que el ``dryRun`` se demuestre suprimiéndola.
        await self.deps.store.save_finalist(object())
        return OrchestratorResult(
            instrument_id=instrument_id,
            status="finalista",
            candidates=1,
            evaluated=1,
            phase="finalista",
            gates=(
                GateResult(gate="p1", status=GateStatus.PASS, detail="neto"),
                GateResult(gate="dsr", status=GateStatus.NOT_EVALUATED),
            ),
        )

    async def watch_active(self, **kwargs: Any) -> Any:  # pragma: no cover
        raise AssertionError("la vigilancia queda fuera del techo FINALISTA")


@dataclass
class _Account:
    id: str
    status: str = "active"


class _AccountRepo:
    def __init__(self, account: _Account | None) -> None:
        self._account = account

    async def get_account(self, account_id: str, owner_user_id: str | None = None) -> _Account:
        if self._account is None or self._account.id != account_id:
            raise ValueError("Cuenta no encontrada")
        return self._account


_DEFAULT_ACCOUNT = _Account(id="acc-1")


def _app(
    *,
    instruments: tuple[str, ...] = ("AAA",),
    account: _Account | None = _DEFAULT_ACCOUNT,
    scope: str | None = "acc-1",
    orch: _FakeOrchestrator | None = None,
    ledger: InMemoryTriggerLedger | None = None,
):  # noqa: ANN202 — helper de test
    app = create_app()
    session = _Session()
    orchestrator = orch or _FakeOrchestrator(instruments=instruments)
    trigger_ledger = ledger or InMemoryTriggerLedger()

    async def _session():  # noqa: ANN202
        yield session

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    app.dependency_overrides[get_db_session] = _session
    route.resolve_account_scope_or_default = _scope  # type: ignore[assignment]
    route.get_account_repository = lambda _session: _AccountRepo(account)  # type: ignore[assignment]
    route.build_orchestrator = lambda _factory: orchestrator  # type: ignore[assignment]
    route.get_trigger_ledger = lambda _session: trigger_ledger  # type: ignore[assignment]
    app.state.session = session
    app.state.orchestrator = orchestrator
    app.state.trigger_ledger = trigger_ledger
    # ``get_session_factory`` solo se usa para componer el orquestador, que el test dobla.
    app.state.session_factory = lambda: None
    return app


async def _post(app, body: dict[str, Any] | None):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if body is None:
            return await client.post("/api/auto/orchestrator/run")
        return await client.post("/api/auto/orchestrator/run", json=body)


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"instrumentId": "AAA"}
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_body_without_dry_run_defaults_to_dry_and_writes_nothing() -> None:
    app = _app()
    response = await _post(app, _body())

    assert response.status_code == 200
    data = response.json()
    assert data["dryRun"] is True
    assert data["phaseReached"] == "finalista"
    assert data["promoted"] is False
    assert data["activeVersionId"] is None
    assert "save_finalist" in data["writes"]
    assert [gate["gate"] for gate in data["gates"]] == ["p1", "dsr"]
    # La única escritura es el recibo de auditoría (lo confirma su id).
    assert data["auditEventId"]
    assert app.state.session.commits == 1


@pytest.mark.asyncio
async def test_repeated_post_is_idempotent() -> None:
    app = _app()
    first = await _post(app, _body(dryRun=False))
    second = await _post(app, _body(dryRun=False))

    assert first.status_code == second.status_code == 200
    assert first.json()["runId"] == second.json()["runId"]
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert app.state.orchestrator.calls == 1
    assert len(app.state.trigger_ledger.entries) == 1


@pytest.mark.asyncio
async def test_instrument_outside_estudio_is_409() -> None:
    app = _app(instruments=("BBB",))
    response = await _post(app, _body())

    assert response.status_code == 409
    assert "instrument_out_of_estudio_scope" in response.json()["detail"]
    assert app.state.session.commits == 0


@pytest.mark.asyncio
async def test_closed_account_is_409() -> None:
    app = _app(account=_Account(id="acc-1", status="closed"))
    response = await _post(app, _body(accountId="acc-1"))

    assert response.status_code == 409
    assert "account_closed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_to_phase_active_is_400() -> None:
    app = _app()
    response = await _post(app, _body(toPhase="active"))

    assert response.status_code == 400
    assert "phase_not_allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_client_evidence_is_rejected() -> None:
    app = _app()
    response = await _post(app, _body(gates={"p1": "pass"}, evidence={"netReturnPct": 99}))

    # ``extra='forbid'``: el cliente no puede aportar evidencia al embudo.
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_instrument_is_400_and_writes_nothing() -> None:
    app = _app()
    response = await _post(app, {"dryRun": False})

    assert response.status_code == 400
    assert "instrument_required" in response.json()["detail"]

    empty = await _post(app, None)
    assert empty.status_code == 400
    assert app.state.orchestrator.calls == 0
