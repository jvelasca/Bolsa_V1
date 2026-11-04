"""Contrato HTTP de los endpoints que alimentan el gráfico MERCADO.

Se monta el router aislado y se sustituyen los casos de uso: aquí se fija el
contrato (códigos, ``data``/``meta`` y errores), no la persistencia.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_analytics.indicators import build_indicator_series, latest_indicator_signals
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.api.v1.routes import instruments as instruments_route
from bolsa_application.get_instrument_data_status import InstrumentDataStatus
from bolsa_application.get_instrument_indicators import IndicatorSeriesResult
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.value_objects.timeframe import TimeFrame

pytestmark = pytest.mark.asyncio


def _bars(count: int = 5) -> list[OhlcvBar]:
    return [
        OhlcvBar(
            timestamp=f"2026-10-{index + 1:02d}",
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
            volume=10_000 + index,
        )
        for index in range(count)
    ]


def _status() -> InstrumentDataStatus:
    return InstrumentDataStatus(
        timeframe="1d",
        last_bar_date="2026-10-31",
        expected_last_bar_date="2026-10-31",
        freshness_status="current",
        bar_count=5,
        last_sync_status="success",
        last_sync_at="2026-10-31T18:00:00+00:00",
        last_sync_error=None,
        sanity_warnings=(),
        gap_count=0,
        xtb_vs_close_deviation_pct=None,
        last_xtb_quote_at=None,
    )


class _StubUseCase:
    def __init__(self, result: Any, *, capture: dict[str, Any] | None = None) -> None:
        self._result = result
        self._capture = capture

    async def execute(self, instrument_id: str, **kwargs: Any) -> Any:
        if self._capture is not None:
            self._capture.update({"instrument_id": instrument_id, **kwargs})
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(instruments_route.router, prefix="/api")

    async def _session() -> Any:
        yield None

    application.dependency_overrides[get_db_session] = _session
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _stub(monkeypatch: pytest.MonkeyPatch, name: str, use_case: Any) -> None:
    monkeypatch.setattr(instruments_route, name, lambda _session: use_case)


async def test_ohlcv_contract_returns_data_and_meta(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    captured: dict[str, Any] = {}
    _stub(monkeypatch, "get_ohlcv_bars_use_case", _StubUseCase(_bars(), capture=captured))

    response = await client.get("/api/instruments/i1/ohlcv?limit=500&timeframe=1d")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"] == {"timeframe": "1d", "count": 5}
    assert len(payload["data"]) == 5
    assert payload["data"][0]["timestamp"] == "2026-10-01"
    assert payload["data"][-1]["close"] == 105
    assert captured["limit"] == 500
    assert captured["timeframe"] == TimeFrame.D1


async def test_ohlcv_empty_data_is_200_not_404(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _stub(monkeypatch, "get_ohlcv_bars_use_case", _StubUseCase([]))

    response = await client.get("/api/instruments/i1/ohlcv?timeframe=1h")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == []
    assert payload["meta"]["count"] == 0
    assert payload["meta"]["timeframe"] == "1h"


async def test_ohlcv_unknown_instrument_is_404(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _stub(monkeypatch, "get_ohlcv_bars_use_case", _StubUseCase(None))

    response = await client.get("/api/instruments/missing/ohlcv")

    assert response.status_code == 404


async def test_ohlcv_invalid_timeframe_is_400(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _stub(monkeypatch, "get_ohlcv_bars_use_case", _StubUseCase(_bars()))

    response = await client.get("/api/instruments/i1/ohlcv?timeframe=7x")

    assert response.status_code == 400


@pytest.mark.parametrize("limit", [0, 10_001])
async def test_ohlcv_limit_is_bounded(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient, limit: int
) -> None:
    _stub(monkeypatch, "get_ohlcv_bars_use_case", _StubUseCase(_bars()))

    response = await client.get(f"/api/instruments/i1/ohlcv?limit={limit}")

    assert response.status_code == 422


async def test_indicators_are_dense_and_aligned_with_bars(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    bars = _bars(30)
    points = build_indicator_series(
        [bar.timestamp for bar in bars],
        [bar.close for bar in bars],
    )
    _stub(
        monkeypatch,
        "get_instrument_indicators_use_case",
        _StubUseCase(IndicatorSeriesResult(data=points, signals=latest_indicator_signals(points))),
    )

    response = await client.get("/api/instruments/i1/indicators?limit=500&timeframe=1d")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == len(bars)
    assert [point["timestamp"] for point in payload["data"]] == [
        bar.timestamp for bar in bars
    ]
    assert payload["meta"]["signals"]["rsiZone"] in {"overbought", "oversold", "neutral"}


async def test_indicators_unknown_instrument_is_404(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _stub(monkeypatch, "get_instrument_indicators_use_case", _StubUseCase(None))

    response = await client.get("/api/instruments/missing/indicators")

    assert response.status_code == 404


async def test_data_status_contract(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _stub(monkeypatch, "get_instrument_data_status_use_case", _StubUseCase(_status()))

    response = await client.get("/api/instruments/i1/data-status?timeframe=1d")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["freshnessStatus"] == "current"
    assert payload["barCount"] == 5
    assert payload["expectedLastBarDate"] == "2026-10-31"
    assert payload["gapCount"] == 0


async def test_data_status_unknown_instrument_is_404(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _stub(monkeypatch, "get_instrument_data_status_use_case", _StubUseCase(None))

    response = await client.get("/api/instruments/missing/data-status")

    assert response.status_code == 404
