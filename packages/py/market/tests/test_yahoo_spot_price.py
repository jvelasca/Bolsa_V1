"""``fetch_spot_price`` — N-2: un precio basura no es un precio.

Antes, ``float(regular_price)`` se devolvía sin comprobar nada: 0, -1, ``nan`` e ``inf``
llegaban intactos a la sonda del proveedor (que los daba por buenos y pintaba verde) y a FX
(que solo filtraba ``== 0`` en la cotización inversa).
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from bolsa_market.yahoo_client import YahooFinanceClient


def _client(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> YahooFinanceClient:
    client = YahooFinanceClient(min_interval_sec=0.0)

    async def _fetch_chart_payload(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(client, "fetch_chart_payload", _fetch_chart_payload)
    return client


def _meta_payload(price: Any) -> dict[str, Any]:
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price, "regularMarketTime": 1}}]}}


@pytest.mark.asyncio
async def test_a_valid_price_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, _meta_payload(11.2345))

    price, timestamp = await client.fetch_spot_price("^IBEX")

    assert price == pytest.approx(11.2345)
    assert timestamp == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_price",
    [0, 0.0, -1.0, float("nan"), float("inf"), "-inf"],
    ids=["int-zero", "zero", "negative", "nan", "inf", "-inf"],
)
async def test_a_worthless_price_is_rejected(
    monkeypatch: pytest.MonkeyPatch, bad_price: Any
) -> None:
    client = _client(monkeypatch, _meta_payload(bad_price))

    with pytest.raises(RuntimeError) as excinfo:
        await client.fetch_spot_price("^IBEX")

    assert "no válido" in str(excinfo.value)
    assert not math.isfinite(float(bad_price)) or float(bad_price) <= 0


@pytest.mark.asyncio
async def test_a_non_numeric_price_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, _meta_payload("no-es-un-precio"))

    with pytest.raises(RuntimeError) as excinfo:
        await client.fetch_spot_price("^IBEX")

    assert "no numérico" in str(excinfo.value)


@pytest.mark.asyncio
async def test_the_close_fallback_is_validated_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin ``regularMarketPrice`` se usa el último cierre: tampoco puede ser basura."""
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {},
                    "timestamp": [1, 2],
                    "indicators": {"quote": [{"close": [10.0, None]}]},
                }
            ]
        }
    }
    client = _client(monkeypatch, payload)

    price, timestamp = await client.fetch_spot_price("^IBEX")

    assert price == pytest.approx(10.0)
    assert timestamp == "1"


@pytest.mark.asyncio
async def test_a_bad_close_fallback_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {},
                    "timestamp": [1],
                    "indicators": {"quote": [{"close": [0.0]}]},
                }
            ]
        }
    }
    client = _client(monkeypatch, payload)

    with pytest.raises(RuntimeError) as excinfo:
        await client.fetch_spot_price("^IBEX")

    assert "no válido" in str(excinfo.value)
