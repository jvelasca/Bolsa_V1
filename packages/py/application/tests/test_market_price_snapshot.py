"""V2.76 · AUTO-MATERIAL-4 — ``MarketPriceSnapshot`` (precio de MERCADO para el PAPER forward).

Contratos que se fijan aquí (todos fail-closed):

* Antes de refrescar NO hay precio: no se inventa un número para poder operar.
* La cotización VIVA gana; el CIERRE durable es el respaldo declarado de los símbolos que la
  primaria no sirvió (y nunca sobrescribe un precio vivo).
* Un valor no finito, no positivo o ausente deja el símbolo SIN precio (``0.0`` en el
  ``price_script``).
* Un proveedor que revienta no produce precio: se declara el fallo y se sigue (el respaldo,
  si existe, puede cubrirlo).
* La procedencia viaja con el dato (``market_live`` / ``market_close``).
"""

from __future__ import annotations

import pytest

from bolsa_application.market_price_snapshot import (
    PRICE_SOURCE_CLOSE,
    PRICE_SOURCE_LIVE,
    MarketPriceSnapshot,
)


def _live(values: dict[str, float]) -> object:
    async def _provider(_symbols: object) -> dict[str, float]:
        return dict(values)

    return _provider


def _closes(values: dict[str, float]) -> object:
    async def _provider(_symbols: object) -> dict[str, float]:
        return dict(values)

    return _provider


def _boom(_symbols: object) -> object:
    async def _provider() -> dict[str, float]:
        raise RuntimeError("sin feed")

    return _provider()


@pytest.mark.asyncio
async def test_before_refresh_there_is_no_price() -> None:
    """Sin refresco no hay dato: el ``price_script`` devuelve ``0.0``, no un precio inventado."""
    snapshot = MarketPriceSnapshot(quotes_provider=_live({"AAA": 12.5}))

    assert snapshot("AAA", 1) == 0.0
    assert snapshot.price_for("AAA") is None
    assert snapshot.source_for("AAA") is None


@pytest.mark.asyncio
async def test_live_quote_is_served_and_declared() -> None:
    """La cotización viva es el precio y su procedencia se declara."""
    snapshot = MarketPriceSnapshot(quotes_provider=_live({"AAA": 12.5}))

    assert await snapshot.refresh(["AAA"]) == 1
    assert snapshot("AAA", 1) == 12.5
    assert snapshot.price_for("AAA") == 12.5
    assert snapshot.source_for("AAA") == PRICE_SOURCE_LIVE
    assert snapshot.sources() == {"AAA": PRICE_SOURCE_LIVE}


@pytest.mark.asyncio
async def test_close_is_the_declared_fallback_for_unsupplied_symbols() -> None:
    """Lo que la primaria no sirve lo cubre el cierre durable, y se declara como tal."""
    snapshot = MarketPriceSnapshot(
        quotes_provider=_live({"AAA": 12.5}),
        closes_provider=_closes({"AAA": 99.0, "BBB": 41.0}),
    )

    assert await snapshot.refresh(["AAA", "BBB"]) == 2
    assert snapshot.price_for("AAA") == 12.5, "el cierre NO sobrescribe un precio vivo"
    assert snapshot.source_for("AAA") == PRICE_SOURCE_LIVE
    assert snapshot.price_for("BBB") == 41.0
    assert snapshot.source_for("BBB") == PRICE_SOURCE_CLOSE


@pytest.mark.asyncio
async def test_symbol_without_any_source_has_no_price() -> None:
    """Sin dato en ninguna fuente el símbolo queda SIN precio (``0.0``), nunca relleno."""
    snapshot = MarketPriceSnapshot(
        quotes_provider=_live({"AAA": 12.5}),
        closes_provider=_closes({"AAA": 99.0}),
    )

    assert await snapshot.refresh(["AAA", "BBB"]) == 1
    assert snapshot.price_for("BBB") is None
    assert snapshot("BBB", 1) == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), None, "basura"])
async def test_non_usable_values_are_rejected(bad: object) -> None:
    """Un valor no finito, no positivo o no numérico NO es un precio: fail-closed."""
    snapshot = MarketPriceSnapshot(quotes_provider=_live({"AAA": bad}))  # type: ignore[dict-item]

    assert await snapshot.refresh(["AAA"]) == 0
    assert snapshot.price_for("AAA") is None
    assert snapshot("AAA", 1) == 0.0


@pytest.mark.asyncio
async def test_a_failing_primary_still_lets_the_fallback_cover() -> None:
    """Un proveedor vivo caído no es un precio: el respaldo cubre y el fallo se declara."""
    snapshot = MarketPriceSnapshot(
        quotes_provider=_boom,  # type: ignore[arg-type]
        closes_provider=_closes({"AAA": 41.0}),
    )

    assert await snapshot.refresh(["AAA"]) == 1
    assert snapshot.price_for("AAA") == 41.0
    assert snapshot.source_for("AAA") == PRICE_SOURCE_CLOSE


@pytest.mark.asyncio
async def test_two_failing_providers_leave_no_price() -> None:
    """Sin ninguna fuente viva el símbolo queda sin precio: no hay número que servir."""
    snapshot = MarketPriceSnapshot(
        quotes_provider=_boom,  # type: ignore[arg-type]
        closes_provider=_boom,  # type: ignore[arg-type]
    )

    assert await snapshot.refresh(["AAA"]) == 0
    assert snapshot.price_for("AAA") is None


@pytest.mark.asyncio
async def test_refresh_rebuilds_the_cache_without_carrying_stale_symbols() -> None:
    """El refresco NO acumula: un símbolo retirado del watch no sigue sirviendo su precio viejo."""
    snapshot = MarketPriceSnapshot(quotes_provider=_live({"AAA": 12.5, "BBB": 41.0}))

    assert await snapshot.refresh(["AAA", "BBB"]) == 2
    assert await snapshot.refresh(["AAA"]) == 1
    assert snapshot.price_for("AAA") == 12.5
    assert snapshot.price_for("BBB") is None


@pytest.mark.asyncio
async def test_empty_watch_clears_the_cache() -> None:
    """Un watch vacío no deja precios colgando del tick anterior."""
    snapshot = MarketPriceSnapshot(quotes_provider=_live({"AAA": 12.5}))

    assert await snapshot.refresh(["AAA"]) == 1
    assert await snapshot.refresh([]) == 0
    assert snapshot.price_for("AAA") is None
    assert snapshot.sources() == {}
