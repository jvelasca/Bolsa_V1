"""W4 (``v2.88.17-beta``) — seam de precio: estado «no hay precio» y proveedor REAL (puro, sin PG).

``W4`` mata el ``100.0`` **silencioso** del simulado. El obstáculo de fondo es que
``PriceScript = Callable[[str, int], float]`` **no puede expresar ausencia**: su único
recurso era mentir con ``100.0`` (``base_mid``) o ``0`` (geometría y el *mark* de equity).
Este módulo prueba el seam y su proveedor real en el plano puro:

1. **``Δ = 0``**: ``ConstantPriceSource`` devuelve EXACTAMENTE lo que devolvía el script y
   **nunca** ``None``. Envolver ``flat_price_script`` reproduce ``100.0``.
2. **Ausencia ≠ valor**: ``None`` es «no hay precio»; nada lo degrada a un default.
3. **Sin default silencioso**: ``as_price_source`` no elige precio por nadie.
4. **``OhlcvPriceSource`` (frontera MIXTA)**: ``mid`` = ``close`` de la última barra con día
   ``< B``; ``execution`` = ``open`` de la barra con día ``== B``. Sin barra ``B`` ⇒
   ``execution`` es ``None`` (fail-closed), y **jamás** se lee el ``close``/``high``/``low``
   de ``B`` para la decisión (eso sería lookahead).

La política de turno (``HOLD`` por símbolo, ``BLOCKED`` si no hay ningún precio) NO vive
aquí: vive en el worker (``test_auto_v2_real_price_fail_closed.py``).
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_api.background.auto_price_provider import (
    ConstantPriceSource,
    MappingPriceSource,
    OhlcvPriceSource,
    PriceSource,
    as_price_source,
)
from bolsa_api.background.auto_simulation_worker import flat_price_script

# ── 1. Δ = 0: el adaptador no mueve un precio del camino hermético ──────────────


@pytest.mark.asyncio
async def test_constant_source_reproduces_the_script_exactly() -> None:
    """``mid`` y ``execution`` devuelven EXACTAMENTE ``script(símbolo, tick)``."""
    seen: list[tuple[str, int]] = []

    def script(symbol: str, tick: int) -> float:
        seen.append((symbol, tick))
        return 10.0 + tick + len(symbol)

    source = ConstantPriceSource(script)
    for tick in (0, 1, 42, 2099):
        await source.refresh(tick=tick)
        for symbol in ("AAA", "BBBB"):
            expected = 10.0 + tick + len(symbol)
            assert source.mid(symbol) == expected
            assert source.execution(symbol) == expected
    # El contrato temporal se conserva: el script recibe el tick de BARRA que le pasa el motor.
    assert (("AAA", 2099) in seen) and (("BBBB", 0) in seen)


@pytest.mark.asyncio
async def test_constant_source_over_flat_script_is_the_old_100_0_path() -> None:
    """``flat_price_script`` (100.0) sigue dando ``100.0`` en las DOS fronteras.

    Es el invariante de ``Δ = 0``: adoptar el seam NO cambia el replay ni los tests, sólo
    hace *explícito* el default que antes era invisible en el worker.
    """
    source = ConstantPriceSource(flat_price_script)
    await source.refresh(tick=1234)
    assert source.mid("AAPL") == 100.0
    assert source.execution("AAPL") == 100.0
    assert source.missing(("AAPL",)) == ()


@pytest.mark.asyncio
async def test_constant_source_is_deterministic_and_never_none() -> None:
    """Mismo tick ⇒ mismo precio; y ``ConstantPriceSource`` nunca inventa ``None``."""
    source = ConstantPriceSource(flat_price_script)
    await source.refresh(tick=7)
    assert source.mid("X") == source.mid("X") == 100.0
    # Un símbolo DESCONOCIDO tampoco es ``None``: el camino inyectable es total por contrato.
    assert source.mid("DESCONOCIDO") == 100.0
    assert source.missing(("X", "DESCONOCIDO")) == ()


# ── 2. Ausencia ≠ valor ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mapping_source_reports_absence_as_none_not_a_default() -> None:
    """Un símbolo AUSENTE ⇒ ``None``. Nunca ``0``, nunca ``100.0``, nunca el vecino."""
    source = MappingPriceSource({"CON_PRECIO": 57.25})
    await source.refresh()
    assert source.mid("CON_PRECIO") == 57.25
    assert source.mid("SIN_PRECIO") is None
    assert source.execution("SIN_PRECIO") is None
    assert source.missing(("CON_PRECIO", "SIN_PRECIO")) == ("SIN_PRECIO",)


@pytest.mark.asyncio
async def test_mapping_source_explicit_none_is_absence() -> None:
    """``{símbolo: None}`` es ausencia explícita, no el precio ``0``."""
    source = MappingPriceSource({"A": None, "B": 0.0})
    await source.refresh()
    assert source.mid("A") is None
    assert source.execution("A") is None
    # ``0.0`` SÍ es un valor presente (un precio real no se confunde con ausencia).
    assert source.mid("B") == 0.0
    assert source.execution("B") == 0.0
    assert source.missing(("A", "B")) == ("A",)


@pytest.mark.asyncio
async def test_mapping_source_empty_means_everything_missing() -> None:
    """Sin mapa ⇒ ningún símbolo tiene precio (la puerta al ``BLOCKED`` del turno)."""
    source = MappingPriceSource()
    await source.refresh()
    assert source.missing(("A", "B")) == ("A", "B")


@pytest.mark.asyncio
async def test_refresh_is_one_photo_per_tick() -> None:
    """``refresh`` se invoca una vez por tick (observable; el worker lo hace una vez/turno)."""
    source = MappingPriceSource({"A": 5.0})
    await source.refresh(tick=1)
    await source.refresh(tick=2)
    assert source.refreshes == 2


# ── 3. Sin default silencioso en el adaptador ──────────────────────────────────


def test_as_price_source_passes_a_source_through_unchanged() -> None:
    """Un ``PriceSource`` ya construido no se re-envuelve (identidad)."""
    source = MappingPriceSource({"A": 1.0})
    assert as_price_source(source) is source


@pytest.mark.asyncio
async def test_as_price_source_wraps_a_plain_script() -> None:
    """Un ``PriceScript`` suelto se adapta conservando su valor exacto."""
    adapted = as_price_source(flat_price_script)
    assert isinstance(adapted, ConstantPriceSource)
    await adapted.refresh(tick=9)
    assert adapted.mid("A") == 100.0 and adapted.execution("A") == 100.0


def test_as_price_source_refuses_a_non_callable_instead_of_defaulting() -> None:
    """Sin fuente, REVIENTA: no hay ``100.0`` de consolación."""
    with pytest.raises(TypeError):
        as_price_source(100.0)  # type: ignore[arg-type]


def test_constant_source_rejects_a_non_callable_script() -> None:
    """El adaptador no acepta basura como si fuera una fuente de precio."""
    with pytest.raises(TypeError):
        ConstantPriceSource(42.0)  # type: ignore[arg-type]


# ── 4. El Protocol distingue «puede expresar ausencia» ────────────────────────


def test_protocol_is_satisfied_by_real_sources_but_not_by_a_bare_script() -> None:
    """Los tres proveedores son ``PriceSource``; un lambda NO.

    La distinción es el punto de ``W4``: un ``PriceScript`` no puede decir «no hay precio».
    """
    assert isinstance(ConstantPriceSource(flat_price_script), PriceSource)
    assert isinstance(MappingPriceSource({"A": 1.0}), PriceSource)
    assert isinstance(OhlcvPriceSource(_FakeBars({}), ("A",), as_of="2026-09-29"), PriceSource)
    assert not isinstance(lambda _s, _t: 100.0, PriceSource)


# ── 5. OhlcvPriceSource: frontera MIXTA (decisión <= B-1, ejecución == B) ──────


class _FakeBars:
    """Lector de barras fake (misma forma que ``SqlAlchemyOhlcvRepository.get_bars``)."""

    def __init__(
        self, bars: dict[str, list[dict[str, Any]]], *, support_date_to: bool = True
    ) -> None:
        self._bars = bars
        self._support = support_date_to
        self.calls: list[tuple[str, Any]] = []

    async def get_bars(
        self, symbol: str, *, timeframe: Any = None, limit: Any = None, date_to: Any = None
    ) -> list[dict[str, Any]]:
        self.calls.append((symbol, date_to))
        if not self._support and date_to is not None:
            raise TypeError("port sin date_to")
        return list(self._bars.get(symbol, []))


def _bar(day: str, open_: float, close: float) -> dict[str, Any]:
    return {
        "timestamp": f"{day}T00:00:00.000000+00:00",
        "open": open_,
        "high": max(open_, close) * 1.01,
        "low": min(open_, close) * 0.99,
        "close": close,
    }


@pytest.mark.asyncio
async def test_ohlcv_source_splits_the_two_boundaries() -> None:
    """``mid`` = ``close`` de ``B-1``; ``execution`` = ``open`` de ``B`` — la MISMA lectura."""
    reader = _FakeBars(
        {
            "AAA": [
                _bar("2026-09-27", 8.0, 9.0),
                _bar("2026-09-28", 10.0, 11.0),
                _bar("2026-09-29", 12.0, 13.0),
            ]
        }
    )
    source = OhlcvPriceSource(reader, ("AAA",), as_of="2026-09-29")
    await source.refresh()

    assert source.mid("AAA") == 11.0, "la decisión lee el close de la última barra CERRADA (< B)"
    assert source.execution("AAA") == 12.0, "la ejecución lee el open de la barra CORRIENTE (== B)"
    # Una sola lectura por símbolo con la frontera de EJECUCIÓN (incluye B).
    assert reader.calls == [("AAA", "2026-09-29")]


@pytest.mark.asyncio
async def test_ohlcv_source_never_reads_the_current_bar_close_for_decision() -> None:
    """Guardia de lookahead: con SOLO la barra ``B``, el ``mid`` queda vacío (no su close)."""
    reader = _FakeBars({"AAA": [_bar("2026-09-29", 12.0, 99.0)]})
    source = OhlcvPriceSource(reader, ("AAA",), as_of="2026-09-29")
    await source.refresh()

    assert source.mid("AAA") is None, "no hay barra < B ⇒ no hay precio de decisión"
    assert source.execution("AAA") == 12.0
    # El ``close`` de B (99.0) no se filtra por ningún lado.
    assert 99.0 not in {source.mid("AAA"), source.execution("AAA")}


@pytest.mark.asyncio
async def test_ohlcv_source_without_current_bar_has_no_execution_price() -> None:
    """Sin barra ``B`` (vivo/PAPER antes de persistir) ⇒ ``execution`` None ⇒ fail-closed.

    Opción (a) del propietario: **jamás** se cae a la barra ``B-1`` (precio rancio).
    """
    reader = _FakeBars({"AAA": [_bar("2026-09-28", 10.0, 11.0)]})
    source = OhlcvPriceSource(reader, ("AAA",), as_of="2026-09-29")
    await source.refresh()

    assert source.execution("AAA") is None, "sin barra B no hay precio de ejecución"
    assert source.mid("AAA") == 11.0, "la decisión sí tiene su close(B-1)"
    assert source.missing(("AAA",)) == ("AAA",), "el símbolo es no ejecutable (HOLD)"


@pytest.mark.asyncio
async def test_ohlcv_source_falls_back_to_client_clamp_without_date_to() -> None:
    """Port sin ``date_to``: se pide sin filtro y la guardia en cliente acota (misma verdad)."""
    reader = _FakeBars(
        {"AAA": [_bar("2026-09-28", 10.0, 11.0), _bar("2026-09-30", 20.0, 21.0)]},
        support_date_to=False,
    )
    source = OhlcvPriceSource(reader, ("AAA",), as_of="2026-09-29")
    await source.refresh()

    assert source.mid("AAA") == 11.0
    assert source.execution("AAA") is None, "la barra de B no está ⇒ sin precio de ejecución"


@pytest.mark.asyncio
async def test_ohlcv_source_fails_closed_without_as_of() -> None:
    """Sin frontera resoluble (``""``) no hay ventana segura ⇒ ningún precio (fail-closed)."""
    reader = _FakeBars({"AAA": [_bar("2026-09-29", 12.0, 13.0)]})
    source = OhlcvPriceSource(reader, ("AAA",), as_of="")
    await source.refresh()

    assert source.mid("AAA") is None
    assert source.execution("AAA") is None
    assert reader.calls == [], "sin as_of no se lee nada"
