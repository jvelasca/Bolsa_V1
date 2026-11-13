"""POST /instrument-daily-opinions/query — UNA lectura de cartera por petición HTTP.

El dictamen on-demand mide la cartera de la cuenta en el SERVIDOR. Este test fija el
contrato de ``apps/api-python/src/bolsa_api/api/dependencies.py`` (``get_daily_opinion_service``)
en el borde HTTP: una petición con varios instrumentos provoca exactamente UNA lectura de
posiciones (no una por id) y la ruta no reenvía hints del cliente.

Se monta el router aislado (patrón de ``test_instrument_chart_routes.py``): se sustituye la
sesión y la factoría del módulo de ruta, y se ejecuta el ``DailyOpinionService`` REAL con
puertos falsos, igual que los cablea la dependencia de producción.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_api.api.dependencies import get_daily_opinion_service, get_db_session
from bolsa_api.api.v1.routes import instrument_daily_opinions as route
from bolsa_application.daily_opinion_service import DailyOpinionService
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    InstrumentDailyOpinionRecord,
)
from bolsa_infrastructure.database.repositories.position_state_repository import (
    SqlAlchemyPositionStateRepository,
)

AS_OF = date(2026, 11, 10)
NOW = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
ACCOUNT = "acc-1"


# ── puertos falsos (mismo contrato que los adaptadores reales) ───────────────


class _FakeOpinions:
    """Caché vacía: toda fila es un miss y se mide en la petición."""

    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []

    async def list_for_instruments(
        self,
        instrument_ids: list[str],
        as_of: date,
        source: str = "on_demand",
        *,
        account_scope: str = "__global__",
    ) -> list[InstrumentDailyOpinionRecord]:
        return []

    async def upsert(self, payload: dict[str, Any]) -> InstrumentDailyOpinionRecord:
        self.upserts.append(dict(payload))
        return InstrumentDailyOpinionRecord(
            id=f"ido_{len(self.upserts)}",
            instrument_id=str(payload["instrument_id"]),
            account_id=payload.get("account_id"),
            as_of_bar_date=payload["as_of_bar_date"],
            stance=str(payload["stance"]),
            dictamen_stars=int(payload["dictamen_stars"]),
            strategy_stars=payload.get("strategy_stars"),
            io_score=payload.get("io_score"),
            fa_score=payload.get("fa_score"),
            ta_score=payload.get("ta_score"),
            distress=bool(payload.get("distress") or False),
            reasons=list(payload.get("reasons") or []),
            gate_status=payload.get("gate_status"),
            top_id=payload.get("top_id"),
            top_version=payload.get("top_version"),
            source=str(payload.get("source") or "on_demand"),
            engine_version=str(payload.get("engine_version") or "opinion_v1"),
            idempotency_key=str(payload.get("idempotency_key") or ""),
            computed_at=payload.get("computed_at") or NOW,
            created_at=NOW,
            updated_at=NOW,
            position_open=payload.get("position_open"),
        )


class _FakeTops:
    async def get(self, instrument_id: str, timeframe: str) -> Any:
        return SimpleNamespace(
            id=f"top_{instrument_id}",
            version=1,
            updated_at=NOW,
            slots=[{"rank": 1, "stars": 4.0}],
        )


class _FakeOhlcv:
    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: Any,
        limit: int,
        date_to: str,
    ) -> list[Any]:
        return [SimpleNamespace(timestamp=AS_OF.isoformat())]


class _FakeChips:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def execute_chips(self, instrument_ids: list[str], **_: Any) -> list[dict[str, Any]]:
        self.calls.append(list(instrument_ids))
        return [
            {
                "instrumentId": iid,
                "indiceOperativo": 85.0,
                "scoreDisplay100": 70.0,
                "technicalDisplay100": 60.0,
            }
            for iid in instrument_ids
        ]


class _FakePositions:
    """Cuenta las lecturas: es la afirmación que este fichero protege."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def list_open_for_account(self, account_id: str) -> list[Any]:
        self.calls.append(account_id)
        return []


def _service(positions: _FakePositions) -> DailyOpinionService:
    # Mismo cableado que ``get_daily_opinion_service`` (dependencies L2086-2097).
    return DailyOpinionService(
        _FakeOpinions(),  # type: ignore[arg-type]
        _FakeTops(),  # type: ignore[arg-type]
        _FakeOhlcv(),  # type: ignore[arg-type]
        None,
        composite=_FakeChips(),
        fundamentals=_FakeChips(),
        positions=positions,
    )


# ── app aislada ─────────────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(route.router, prefix="/api")

    async def _session() -> Any:
        yield None

    application.dependency_overrides[get_db_session] = _session
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _allow_account(_request: Any, _account_id: str | None) -> None:
    """La visibilidad de la cuenta se prueba en su propia suite; aquí solo estorba la BD."""
    return None


@pytest.mark.asyncio
async def test_query_reads_portfolio_once_per_request(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    positions = _FakePositions()
    service = _service(positions)
    monkeypatch.setattr(route, "get_daily_opinion_service", lambda _session: service)
    monkeypatch.setattr(route, "require_owned_account_if_present", _allow_account)

    response = await client.post(
        "/api/instrument-daily-opinions/query",
        json={
            "instrumentIds": ["inst-1", "inst-2", "inst-3"],
            "asOfBarDate": AS_OF.isoformat(),
            "accountId": ACCOUNT,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [row["instrumentId"] for row in payload["data"]] == [
        "inst-1",
        "inst-2",
        "inst-3",
    ]
    # Una petición con tres ids ⇒ UNA lectura de cartera, no tres.
    assert positions.calls == [ACCOUNT]


@pytest.mark.asyncio
async def test_query_ignores_client_hints_and_measures_position(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    positions = _FakePositions()
    service = _service(positions)
    monkeypatch.setattr(route, "get_daily_opinion_service", lambda _session: service)
    monkeypatch.setattr(route, "require_owned_account_if_present", _allow_account)

    response = await client.post(
        "/api/instrument-daily-opinions/query",
        json={
            "instrumentIds": ["inst-1"],
            "asOfBarDate": AS_OF.isoformat(),
            "accountId": ACCOUNT,
            # Deprecado e IGNORADO: si el servidor confiara en él, no leería la cartera.
            "hints": [{"instrumentId": "inst-1", "positionOpen": True}],
        },
    )

    assert response.status_code == 200
    assert positions.calls == [ACCOUNT]
    row = response.json()["data"][0]
    # El hint True del cliente NO se usa: la cartera medida dice «sin posición» ⇒ buy.
    assert row["stance"] == "buy"
    assert "position_unmeasured" not in row["reasons"]


def test_dependency_wires_the_positions_port() -> None:
    """El wiring de producción inyecta el puerto de posiciones (no ``None``).

    Sin él, el dictamen on-demand no mediría la cartera de la cuenta y todas las filas
    saldrían ``position_unmeasured``. La factoría solo CONSTRUYE adaptadores: no toca la BD.
    """
    service = get_daily_opinion_service(None)  # type: ignore[arg-type]

    assert isinstance(service._positions, SqlAlchemyPositionStateRepository)
    assert service._composite is not None
    assert service._fundamentals is not None
