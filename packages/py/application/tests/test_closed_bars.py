"""``W3`` · v2.88.16 — frontera de barras CERRADAS (NO lookahead + ancla temporal por barra).

Invariantes que se fijan aquí:

* ``last_closed_bar_day`` es la **última barra cerrada**: la barra que contiene el instante
  NUNCA es visible (ni justo a su apertura, ni un segundo antes de su cierre).
* La frontera se puede mover **sin recomponer** el cargador (``as_of`` provider) y jamás
  admite una barra del futuro, ni una barra sin fecha legible.
* Con barra **sub-diaria** (frontera no expresable a día) la ventana es **vacía**: el motor
  no decide; no se degrada a «las barras de hoy», que es el lookahead que esto cierra.
* ``bar_tick`` es **constante dentro de la barra** y distinto entre barras: es la unidad con
  la que la identidad de la orden y el ``seed`` del fill dejan de depender del minuto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from bolsa_analytics.cognitive.signal_identity import bar_window
from bolsa_application.closed_bars import (
    bar_day,
    bar_tick,
    clamp_bars_as_of,
    last_closed_bar_day,
    make_closed_bar_loader,
)
from bolsa_domain.ohlcv_time import parse_bar_timestamp


@dataclass(frozen=True, slots=True)
class _Bar:
    timestamp: str
    open: float = 100.0
    high: float = 101.0
    low: float = 99.0
    close: float = 100.0
    volume: int = 1_000


def _bar(day: str, close: float = 100.0) -> _Bar:
    return _Bar(timestamp=f"{day}T00:00:00Z", close=close)


def _moment(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


# ── ``last_closed_bar_day``: la barra EN CURSO nunca es visible ────────────────────


def test_last_closed_bar_day_d1_is_the_day_before_the_current_bar() -> None:
    """La barra del día ``D`` no está cerrada hasta el fin de ``D``: ``as_of`` es ``D-1``."""
    for text in ("2026-09-30T00:00:00", "2026-09-30T14:00:00", "2026-09-30T23:59:59"):
        assert last_closed_bar_day(_moment(text), "1d") == "2026-09-29"
    # Al abrir la barra siguiente, la anterior ya cerró ⇒ la frontera avanza un día.
    assert last_closed_bar_day(_moment("2026-10-01T00:00:00"), "1d") == "2026-09-30"


def test_last_closed_bar_day_is_always_before_the_current_bar_start() -> None:
    """Propiedad general: la frontera es ANTERIOR al inicio de la barra corriente."""
    for text in ("2026-09-30T14:00:00", "2026-03-01T00:00:00", "2026-01-01T00:00:01"):
        moment = _moment(text)
        window = bar_window(moment, "1d")
        assert window is not None
        start_day = parse_bar_timestamp(window[0]).strftime("%Y-%m-%d")
        assert last_closed_bar_day(moment, "1d") < start_day


def test_last_closed_bar_day_multi_day_bar_is_the_previous_bar_not_the_live_one() -> None:
    """Vale para cualquier timeframe ≥ día, sea cual sea el día en que ancle la barra."""
    moment = _moment("2026-09-30T14:00:00")
    window = bar_window(moment, "2d")
    assert window is not None
    expected = (parse_bar_timestamp(window[0]) - timedelta(seconds=1)).strftime("%Y-%m-%d")
    assert last_closed_bar_day(moment, "2d") == expected
    assert last_closed_bar_day(moment, "2d") < parse_bar_timestamp(window[0]).strftime("%Y-%m-%d")


def test_last_closed_bar_day_fail_closed_for_weekly_which_the_kernel_cannot_read() -> None:
    """``1wk`` no es legible por el kernel de barras (unidades ``m``/``h``/``d``).

    ``1wk`` está **declarada y NO habilitada** (``W1``: ``GranularityRejection.
    DECISION_NOT_ENABLED``, el gap del lunes no tiene pruebas temporales), así que no
    puede llegar al motor; si llegara, la frontera NO se inventa: ventana vacía ⇒ HOLD.
    """
    assert bar_window(_moment("2026-09-30T14:00:00"), "1wk") is None
    assert last_closed_bar_day(_moment("2026-09-30T14:00:00"), "1wk") == ""


@pytest.mark.parametrize("timeframe", ["1m", "5m", "1h", "4h"])
def test_last_closed_bar_day_fail_closed_for_subdaily(timeframe: str) -> None:
    """Barra sub-diaria: la frontera NO es expresable a día ⇒ ``""`` (ventana vacía)."""
    assert last_closed_bar_day(_moment("2026-09-30T14:00:00"), timeframe) == ""


def test_last_closed_bar_day_fail_closed_without_readable_bar() -> None:
    """Sin barra legible (timeframe ajeno o instante sin zona) no se inventa frontera."""
    assert last_closed_bar_day(_moment("2026-09-30T14:00:00"), "") == ""
    assert last_closed_bar_day(_moment("2026-09-30T14:00:00"), "zzz") == ""
    assert last_closed_bar_day(datetime(2026, 9, 30, 14, 0), "1d") == ""


# ── ``bar_tick``: identidad temporal estable DENTRO de la barra ────────────────────


def test_bar_tick_is_constant_within_the_bar_and_moves_between_bars() -> None:
    """El tick no depende del minuto: dos instantes de la misma barra son el MISMO tick."""
    a = bar_tick(_moment("2026-09-30T00:00:00"), "1d")
    b = bar_tick(_moment("2026-09-30T09:31:00"), "1d")
    c = bar_tick(_moment("2026-09-30T23:59:59"), "1d")
    assert a == b == c
    assert bar_tick(_moment("2026-10-01T00:00:00"), "1d") == a + 1


def test_bar_tick_distinguishes_hours_within_a_day() -> None:
    """Con timeframe horario el tick sigue siendo estable dentro de la hora."""
    h10 = bar_tick(_moment("2026-09-30T10:00:00"), "1h")
    assert bar_tick(_moment("2026-09-30T10:59:59"), "1h") == h10
    assert bar_tick(_moment("2026-09-30T11:00:00"), "1h") == h10 + 1


def test_bar_tick_fail_closed_is_a_constant_anchor() -> None:
    """Sin barra legible el ancla es una CONSTANTE determinista (nunca el minuto)."""
    assert bar_tick(_moment("2026-09-30T14:00:00"), "") == 0
    assert bar_tick(_moment("2026-09-30T14:00:00"), "zzz") == 0
    assert bar_tick(datetime(2026, 9, 30, 14, 0), "1d") == 0


# ── Cargador acotado: la barra viva no llega a la decisión ─────────────────────────


class _Repo:
    """Port de barras que **anota** los argumentos y devuelve SIEMPRE la serie completa."""

    def __init__(self, bars: list[Any], *, accepts_date_to: bool = True) -> None:
        self._bars = bars
        self._accepts_date_to = accepts_date_to
        self.calls: list[dict[str, Any]] = []

    async def get_bars(self, symbol: str, **kwargs: Any) -> list[Any]:
        self.calls.append({"symbol": symbol, **kwargs})
        if not self._accepts_date_to and "date_to" in kwargs:
            raise TypeError("get_bars() got an unexpected keyword argument 'date_to'")
        return list(self._bars)


@pytest.mark.asyncio
async def test_loader_never_admits_the_live_bar_and_pushes_the_boundary_to_the_port() -> None:
    """La barra EN CURSO (día 2) no entra aunque el port la devuelva; ``date_to`` la excluye."""
    repo = _Repo([_bar("2026-09-28"), _bar("2026-09-29"), _bar("2026-09-30")])
    as_of = lambda: last_closed_bar_day(_moment("2026-09-30T14:00:00"), "1d")  # noqa: E731
    refresh = make_closed_bar_loader(repo, ["AAA"], as_of, limit=120)

    snapshot = await refresh()

    assert [bar_day(bar) for bar in snapshot["AAA"]] == ["2026-09-28", "2026-09-29"]
    assert repo.calls[0]["date_to"] == "2026-09-29"
    assert repo.calls[0]["limit"] == 120


@pytest.mark.asyncio
async def test_loader_clamps_in_client_when_the_port_cannot_filter() -> None:
    """Un port sin ``date_to`` no puede filtrar el futuro: la guardia en cliente sí."""
    repo = _Repo([_bar("2026-09-28"), _bar("2026-09-30")], accepts_date_to=False)
    refresh = make_closed_bar_loader(repo, ["AAA"], "2026-09-29")

    snapshot = await refresh()

    assert [bar_day(bar) for bar in snapshot["AAA"]] == ["2026-09-28"]


@pytest.mark.asyncio
async def test_loader_drops_undated_bars_and_empty_symbols() -> None:
    """Una barra sin fecha legible se DESCARTA: nunca se asume que es del pasado."""
    repo = _Repo([_bar("2026-09-28"), _Bar(timestamp=""), _Bar(timestamp="sin-fecha")])
    refresh = make_closed_bar_loader(repo, ["AAA"], "2026-09-29")

    snapshot = await refresh()

    assert [bar_day(bar) for bar in snapshot["AAA"]] == ["2026-09-28"]


@pytest.mark.asyncio
async def test_loader_follows_the_clock_without_being_recomposed() -> None:
    """El provider mueve la frontera entre ticks: mismo cargador, ventana distinta."""
    now = {"at": _moment("2026-09-30T14:00:00")}
    repo = _Repo([_bar("2026-09-28"), _bar("2026-09-29"), _bar("2026-09-30")])
    refresh = make_closed_bar_loader(
        repo, ["AAA"], lambda: last_closed_bar_day(now["at"], "1d"), limit=120
    )

    first = await refresh()
    now["at"] = _moment("2026-10-01T14:00:00")
    second = await refresh()

    assert [bar_day(bar) for bar in first["AAA"]] == ["2026-09-28", "2026-09-29"]
    assert [bar_day(bar) for bar in second["AAA"]] == ["2026-09-28", "2026-09-29", "2026-09-30"]


@pytest.mark.asyncio
async def test_loader_fail_closed_without_boundary_reads_nothing() -> None:
    """Sin frontera resoluble NO se lee: cero barras (el motor queda en HOLD)."""
    repo = _Repo([_bar("2026-09-28")])
    # Sub-diaria: la frontera no es expresable a día ⇒ ventana vacía.
    refresh = make_closed_bar_loader(
        repo, ["AAA"], lambda: last_closed_bar_day(_moment("2026-09-30T14:00:00"), "1h")
    )

    assert await refresh() == {}
    assert repo.calls == []


@pytest.mark.asyncio
async def test_loader_ignores_a_failing_symbol_and_serves_the_rest() -> None:
    """Un símbolo sin barras no aborta el refresco: se queda sin ventana (HOLD)."""

    class _Exploding:
        async def get_bars(self, symbol: str, **kwargs: Any) -> list[Any]:
            if symbol == "BOOM":
                raise RuntimeError("sin barras")
            return [_bar("2026-09-28")]

    refresh = make_closed_bar_loader(_Exploding(), ["BOOM", "AAA"], "2026-09-29")
    snapshot = await refresh()

    assert list(snapshot) == ["AAA"]


def test_clamp_is_fail_closed_without_boundary() -> None:
    """Sin ``as_of`` resoluble la guardia devuelve vacío (nunca «todo el histórico»)."""
    bars = [_bar("2026-09-28")]
    assert clamp_bars_as_of(bars, "") == []
    assert clamp_bars_as_of(bars, None) == []
