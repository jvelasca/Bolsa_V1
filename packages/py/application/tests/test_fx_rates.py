"""``GetFxRate`` — N-2: solo un tipo de cambio finito y positivo es un tipo de cambio.

Antes, la cotización directa no se validaba y la inversa solo rechazaba ``price == 0``: un
negativo invertía el signo del tipo de cambio (o producía un ``ZeroDivisionError``) y un
``nan`` se propagaba como cotización válida.
"""

from __future__ import annotations

from typing import Any

import pytest

import bolsa_application.fx as fx_module
from bolsa_application.fx import GetFxRate


class _Client:
    def __init__(self, prices: dict[str, Any]) -> None:
        self._prices = prices
        self.calls: list[str] = []

    async def fetch_spot_price(self, symbol: str) -> tuple[Any, str]:
        self.calls.append(symbol)
        value = self._prices.get(symbol)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise RuntimeError(f"sin precio para {symbol}")
        return value, "2026-11-01T09:00:00Z"


def _install(monkeypatch: pytest.MonkeyPatch, prices: dict[str, Any]) -> _Client:
    client = _Client(prices)
    monkeypatch.setattr(fx_module, "get_yahoo_finance_client", lambda: client)
    return client


@pytest.mark.asyncio
async def test_a_valid_direct_rate_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install(monkeypatch, {"EURUSD=X": 1.08})

    rate = await GetFxRate().execute("EUR", "USD")

    assert rate.rate == pytest.approx(1.08)
    assert rate.yahoo_symbol == "EURUSD=X"
    assert client.calls == ["EURUSD=X"]


@pytest.mark.asyncio
async def test_the_same_currency_is_one_without_traffic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _install(monkeypatch, {})

    rate = await GetFxRate().execute("EUR", "EUR")

    assert rate.rate == 1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_rate", [0.0, -1.2, float("nan"), float("inf")])
async def test_a_worthless_direct_rate_falls_back_to_the_inverse(
    monkeypatch: pytest.MonkeyPatch, bad_rate: float
) -> None:
    """La basura en la directa NO se devuelve: se intenta la inversa."""
    client = _install(monkeypatch, {"EURUSD=X": bad_rate, "USDEUR=X": 0.9})

    rate = await GetFxRate().execute("EUR", "USD")

    assert rate.yahoo_symbol == "USDEUR=X"
    assert rate.rate == pytest.approx(1.0 / 0.9)
    assert client.calls == ["EURUSD=X", "USDEUR=X"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_rate", [0.0, -1.0, float("nan"), float("inf")])
async def test_a_worthless_inverse_rate_is_a_declared_failure(
    monkeypatch: pytest.MonkeyPatch, bad_rate: float
) -> None:
    _install(monkeypatch, {"EURUSD=X": RuntimeError("sin directa"), "USDEUR=X": bad_rate})

    with pytest.raises(RuntimeError):
        await GetFxRate().execute("EUR", "USD")
