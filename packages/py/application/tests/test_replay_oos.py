"""V2.86 · AUTO-MATERIAL-14 — contratos del replay OOS (censo + no-lookahead + puntuación).

Invariantes que se fijan aquí:

* Las barras **posteriores** al día simulado NO existen para el clasificador (no lookahead).
  Dos universos que solo difieren en el FUTURO clasifican IGUAL el día de corte.
* El censo reutiliza el mismo veredicto conservador del motor y declara cada día.
* El reloj avanza un DÍA por tick y el precio del tick ``n`` es el del día ``days[n-1]``.
* La puntuación OOS empareja ida y vuelta y declara los huecos (no los rellena con ``0``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from bolsa_application.replay_oos import (
    ReplayCursor,
    ReplayFill,
    ReplayTick,
    bar_day,
    census_operable_days,
    clamp_bars_as_of,
    make_as_of_bar_loader,
    make_day_price_script,
    score_replay,
    step_day_clock,
)

# ── utilidades de construcción de barras deterministas ────────────────────────────

_ORIGIN = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 1_000


def _day(index: int) -> str:
    return (_ORIGIN + timedelta(days=index)).strftime("%Y-%m-%d")


def _bar_at(index: int, close: float, *, band: float) -> _Bar:
    return _Bar(
        timestamp=f"{_day(index)}T00:00:00Z",
        open=close,
        high=close + band,
        low=close - band,
        close=close,
    )


def _flat_series(count: int, base: float = 100.0, *, band: float = 1.0) -> list[_Bar]:
    """Serie plana: ``range`` (vol relativa ``2·band/base`` por debajo de ``high_vol``)."""
    return [_bar_at(i, base, band=band) for i in range(count)]


def _declining_series(count: int, *, step: float = 0.2, band: float = 1.0) -> list[_Bar]:
    """Serie en descenso suave: ``trend_down`` (pendiente normalizada < −0.5)."""
    return [_bar_at(i, 100.0 - step * i, band=band) for i in range(count)]


def _crash_series(start: int, count: int, *, band: float = 8.0) -> list[_Bar]:
    """Serie revuelta: ``high_vol`` (vol relativa muy por encima del umbral)."""
    return [_bar_at(start + i, 90.0 - 4.0 * i, band=band) for i in range(count)]


def _volatile_series(count: int, *, band: float = 6.0) -> list[_Bar]:
    """Serie plana pero REVUELTA: cierres constantes (sin tendencia) y banda ancha."""
    return [_bar_at(i, 100.0, band=band) for i in range(count)]


# ── Paso 1 · barras acotadas a ``as_of`` (no lookahead) ───────────────────────────


def test_clamp_bars_as_of_drops_future_and_undated_bars() -> None:
    """La guardia deja SOLO ``timestamp <= as_of``; una barra sin fecha se descarta."""
    bars = [_bar_at(0, 100.0, band=1.0), _bar_at(1, 101.0, band=1.0), _bar_at(5, 90.0, band=1.0)]
    kept = clamp_bars_as_of(bars, _day(1))
    assert [bar_day(bar) for bar in kept] == [_day(0), _day(1)]
    assert clamp_bars_as_of([_Bar("", 1.0, 1.0, 1.0, 1.0)], _day(1)) == []
    # Sin ``as_of`` resoluble no hay ventana segura: se devuelve vacío (fail-closed).
    assert clamp_bars_as_of(bars, "") == []


@pytest.mark.asyncio
async def test_loader_without_date_to_still_clamps_in_client() -> None:
    """Un port que ignora ``date_to`` no puede filtrar el futuro: la guardia en cliente sí."""

    class _Repo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def get_bars(self, instrument_id: str, *, timeframe=None, limit=None):
            self.calls.append({"instrument_id": instrument_id, "limit": limit})
            return [
                _bar_at(0, 100.0, band=1.0),
                _bar_at(1, 101.0, band=1.0),
                _bar_at(9, 60.0, band=1.0),
            ]

    repo = _Repo()
    loader = make_as_of_bar_loader(repo, ["AAA"], _day(1))
    snapshot = await loader()

    assert [bar_day(bar) for bar in snapshot["AAA"]] == [_day(0), _day(1)]
    assert repo.calls and repo.calls[0]["limit"] is not None


@pytest.mark.asyncio
async def test_loader_uses_repository_date_to_when_available() -> None:
    """Si el repositorio soporta ``date_to``, se usa (menos filas en vuelo)."""

    class _Repo:
        def __init__(self) -> None:
            self.date_to: list[object] = []

        async def get_bars(
            self, instrument_id: str, *, timeframe=None, limit=None, date_to=None
        ):
            self.date_to.append(date_to)
            return [_bar_at(0, 100.0, band=1.0)]

    repo = _Repo()
    loader = make_as_of_bar_loader(repo, ["AAA"], _day(4))
    await loader()

    assert repo.date_to == [_day(4)]


def test_regime_at_cutoff_does_not_change_when_future_bars_are_added() -> None:
    """El día de corte clasifica IGUAL con o sin barras posteriores (mata el lookahead).

    Este es el test que mata la mutación de ``clamp_bars_as_of``: si la guardia dejara de
    filtrar, el universo con la caída FUTURA clasificaría distinto en el día de corte.
    """
    past = _flat_series(80)
    future = _crash_series(80, 6)
    cutoff = [bar_day(past[-1])]

    without_future = census_operable_days({"AAA": past}, cutoff)
    with_future = census_operable_days({"AAA": [*past, *future]}, cutoff)

    assert without_future.days[0].regimes == with_future.days[0].regimes == {"AAA": "range"}
    assert without_future.days[0].aggregate == with_future.days[0].aggregate == "range"
    # El futuro SÍ cambia el día posterior: prueba que las barras no son inertes.
    later = census_operable_days({"AAA": [*past, *future]}, [bar_day(future[-1])])
    assert later.days[0].regimes == {"AAA": "high_vol"}


# ── Paso 0 · censo de días operables ──────────────────────────────────────────────


def test_census_blocks_the_day_when_one_symbol_trends_down() -> None:
    """Un solo ``trend_down`` de N deja el agregado en ``trend_down`` ⇒ long vetado."""
    flat = _flat_series(80)
    falling = _declining_series(80)
    days = [bar_day(flat[-1])]

    report = census_operable_days({"AAA": flat, "BBB": falling}, days)

    row = report.days[0]
    assert row.regimes == {"AAA": "range", "BBB": "trend_down"}
    assert row.aggregate == "trend_down"
    assert row.operational == "BEAR_TREND"
    assert row.entries_allowed_long is False
    assert row.operable_symbols == 1
    assert row.measured_symbols == 2
    assert report.operable_days == 0


def test_census_allows_the_day_when_no_symbol_trends_down() -> None:
    """Sin ``trend_down`` el agregado es operable y el censo lo declara con su racha."""
    flat = _flat_series(80)
    rising = [_bar_at(i, 100.0 + 0.2 * i, band=1.0) for i in range(80)]
    days = [bar_day(flat[-1]), _day(81), _day(82)]

    report = census_operable_days({"AAA": flat, "BBB": rising}, days)

    assert report.operable_days == 3
    assert report.max_operable_streak == 3
    assert report.days[0].regimes == {"AAA": "range", "BBB": "trend_up"}
    assert report.days[0].entries_allowed_long is True
    assert report.aggregate_counts == {"range": 3}
    # El desglose por eje operativo declara que son SIDEWAYS (range), no BULL_TREND.
    assert report.operable_by_operational() == {"SIDEWAYS": 3}


def test_census_counts_high_vol_as_operable_and_declares_it() -> None:
    """``high_vol`` NO lo veta este gate, así que cuenta como operable... y se DECLARA.

    Es el matiz que impide leer «318 días operables» como «318 días de tendencia alcista»:
    el desglose por eje operativo lo publica como ``HIGH_VOLATILITY``.
    """
    flat = _flat_series(80)
    crash = _volatile_series(80)
    days = [bar_day(crash[-1])]

    report = census_operable_days({"AAA": flat, "BBB": crash}, days)

    assert report.days[0].aggregate == "high_vol"
    assert report.days[0].operational == "HIGH_VOLATILITY"
    assert report.days[0].entries_allowed_long is True
    assert report.operable_by_operational() == {"HIGH_VOLATILITY": 1}


def test_census_declares_a_gap_when_no_symbol_is_classifiable() -> None:
    """Sin barras suficientes no hay régimen: ``NO_REGIME`` ⇒ operabilidad vetada (fail-closed)."""
    short = _flat_series(10)
    report = census_operable_days({"AAA": short}, [bar_day(short[-1])])

    assert report.days[0].regimes == {}
    assert report.days[0].measured_symbols == 0
    assert report.days[0].aggregate == ""
    assert report.days[0].operational == "UNKNOWN"
    assert report.days[0].entries_allowed_long is False


# ── Paso 2a · reloj de un día por tick y precio histórico ─────────────────────────


def test_step_day_clock_advances_exactly_one_day_per_tick() -> None:
    start = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    _, clock = step_day_clock(start)

    assert clock() - start == timedelta(days=1)
    assert clock() - start == timedelta(days=2)


def test_day_price_script_maps_tick_to_its_own_day_and_fails_closed_off_range() -> None:
    days = [_day(0), _day(1), _day(2)]
    prices = make_day_price_script({"AAA": {_day(1): 105.0}}, days)

    assert prices("AAA", 1) == 105.0  # el tick t opera al open de days[t]
    assert prices("AAA", 0) == 0.0  # fuera de rango ⇒ sin precio (fail-closed)
    assert prices("BBB", 1) == 0.0  # símbolo sin dato ⇒ sin precio
    assert prices("AAA", 99) == 0.0


def test_replay_cursor_keeps_as_of_clock_and_price_aligned() -> None:
    """El cursor es la única autoridad: as_of = día previo, precio = open del día simulado."""
    days = [_day(0), _day(1), _day(4), _day(5)]
    cursor = ReplayCursor(
        days,
        {"AAA": {_day(1): 101.0, _day(4): 104.0}},
        start_index=1,
    )

    assert cursor.current_day() == _day(1)
    assert cursor.as_of() == _day(0)
    assert cursor.clock().strftime("%Y-%m-%d") == _day(1)
    assert cursor.price_script("AAA", 7) == 101.0  # el tick del worker se ignora

    cursor.set_index(2)
    assert cursor.as_of() == _day(1)
    assert cursor.price_script("AAA", 7) == 104.0
    # En el primer índice no hay día previo: sin ``as_of`` la ventana es fail-closed.
    cursor.set_index(0)
    assert cursor.as_of() == ""


def test_day_price_script_rejects_non_positive_and_non_finite_values() -> None:
    days = [_day(0), _day(1)]
    prices = make_day_price_script(
        {"AAA": {_day(1): float("nan"), _day(2): float("inf")}, "BBB": {_day(2): -5.0}},
        days,
    )

    assert prices("AAA", 2) == 0.0
    assert prices("BBB", 2) == 0.0


# ── Paso 3 · puntuación OOS contra barras futuras conocidas ───────────────────────


def _tick(
    day: str,
    *,
    fills: tuple[ReplayFill, ...] = (),
    prices: dict[str, float] | None = None,
    open_positions: dict[str, float] | None = None,
    entry_prices: dict[str, float] | None = None,
    stops: dict[str, float] | None = None,
) -> ReplayTick:
    return ReplayTick(
        day=day,
        regime="SIDEWAYS",
        prices=prices or {},
        open_positions=open_positions or {},
        entry_prices=entry_prices or {},
        stops=stops or {},
        fill_rows=fills,
    )


def test_score_replay_measures_realized_r_and_sign() -> None:
    """Entrada 100, stop 95 (riesgo 5), salida 110 ⇒ R = +2.0."""
    ticks = [
        _tick(
            _day(0),
            fills=(ReplayFill(_day(0), "AAA", "buy", 100.0, 100.0, strategy_version="vA"),),
            stops={"AAA": 95.0},
        ),
        _tick(_day(1), fills=(ReplayFill(_day(1), "AAA", "sell", 100.0, 110.0, strategy_version="vA"),)),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 1
    trip = report.round_trips[0]
    assert trip.realized_r == pytest.approx(2.0)
    assert trip.entry_day == _day(0)
    assert trip.exit_day == _day(1)
    assert report.positive_share == 1.0
    assert report.mean_r == pytest.approx(2.0)
    assert report.by_version()["vA"]["count"] == 1
    assert report.open_positions == ()


def test_score_replay_declares_gaps_instead_of_inventing_zero() -> None:
    """Una salida sin entrada previa y un riesgo no medible se DECLARAN, no se cuentan."""
    ticks = [
        _tick(_day(0), fills=(ReplayFill(_day(0), "AAA", "sell", 100.0, 110.0),)),
        _tick(
            _day(1),
            fills=(ReplayFill(_day(1), "BBB", "buy", 100.0, 100.0),),
            stops={"BBB": 100.0},  # stop == entry ⇒ riesgo 0 ⇒ no medible
        ),
        _tick(_day(2), fills=(ReplayFill(_day(2), "BBB", "sell", 100.0, 120.0),)),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 0
    assert report.mean_r is None
    assert report.positive_share is None
    assert any("salida_sin_entrada" in gap for gap in report.unmeasured)
    assert any("riesgo_no_medible" in gap for gap in report.unmeasured)


def test_score_replay_reports_open_positions_as_unrealized_not_realized() -> None:
    """Lo que queda vivo al final se marca a mercado como NO realizado (nunca realizado)."""
    ticks = [
        _tick(
            _day(0),
            fills=(ReplayFill(_day(0), "AAA", "buy", 100.0, 100.0),),
            stops={"AAA": 95.0},
        ),
        _tick(_day(1), prices={"AAA": 105.0}),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 0
    assert len(report.open_positions) == 1
    assert report.open_positions[0].unrealized_r == pytest.approx(1.0)
    assert report.open_positions[0].last_price == 105.0


def test_score_replay_aggregates_partial_fills_into_one_round_trip_per_cycle() -> None:
    """Fills PARCIALES del mismo ciclo ⇒ UNA sola ida y vuelta (no ``k`` repetidas).

    El motor liquida en trozos: contar una R por cada fila multiplicaría el censo por el
    número de trozos y repetiría la misma R. La unidad honesta es el ciclo.
    """
    ticks = [
        _tick(
            _day(0),
            fills=(
                ReplayFill(_day(0), "AAA", "buy", 30.0, 100.0),
                ReplayFill(_day(0), "AAA", "buy", 70.0, 100.0),
            ),
            stops={"AAA": 95.0},
        ),
        _tick(
            _day(1),
            fills=(
                ReplayFill(_day(1), "AAA", "sell", 40.0, 110.0),
                ReplayFill(_day(1), "AAA", "sell", 60.0, 110.0),
            ),
        ),
        _tick(_day(2), prices={"AAA": 100.0}),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 1
    assert report.round_trips[0].realized_r == pytest.approx(2.0)
    assert report.open_positions == ()


def test_score_replay_keeps_a_partial_exit_open_until_the_cycle_closes() -> None:
    """Una salida parcial NO cierra el ciclo: sigue abierto hasta que la cantidad llega a 0."""
    ticks = [
        _tick(
            _day(0),
            fills=(ReplayFill(_day(0), "AAA", "buy", 100.0, 100.0),),
            stops={"AAA": 95.0},
        ),
        _tick(_day(1), fills=(ReplayFill(_day(1), "AAA", "sell", 40.0, 110.0),)),
        _tick(_day(2), prices={"AAA": 100.0}),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 0
    assert len(report.open_positions) == 1
    assert report.open_positions[0].quantity == pytest.approx(60.0)
    assert report.open_positions[0].unrealized_r == pytest.approx(0.0)


def test_score_replay_measures_vwap_entry_and_exit_prices() -> None:
    """Con fills a precios distintos, la entrada y la salida se leen a precio MEDIO ponderado."""
    ticks = [
        _tick(
            _day(0),
            fills=(
                ReplayFill(_day(0), "AAA", "buy", 50.0, 100.0),
                ReplayFill(_day(0), "AAA", "buy", 50.0, 110.0),
            ),
            stops={"AAA": 90.0},
        ),
        _tick(
            _day(1),
            fills=(ReplayFill(_day(1), "AAA", "sell", 100.0, 250.0),),
        ),
        _tick(_day(2), prices={"AAA": 250.0}),
    ]

    report = score_replay(ticks)

    trip = report.round_trips[0]
    assert trip.entry_price == pytest.approx(105.0)  # VWAP de las compras
    assert trip.realized_r == pytest.approx((250.0 - 105.0) / (105.0 - 90.0))


def test_score_replay_measures_a_short_round_trip_with_short_geometry() -> None:
    """Corta: se ABRE con ``sell`` (stop ARRIBA) y se cierra con ``buy`` más abajo ⇒ R positivo.

    Es el contrato que el scorer OOS no sabía leer: con geometría larga, ``stop > entry`` haría
    que el riesgo saliera negativo y el ciclo entero se descartaría como ``riesgo_no_medible``
    en vez de medirse.
    """
    ticks = [
        _tick(
            _day(0),
            fills=(ReplayFill(_day(0), "AAA", "sell", 100.0, 100.0, direction="short"),),
            stops={"AAA": 105.0},
        ),
        _tick(
            _day(1),
            fills=(ReplayFill(_day(1), "AAA", "buy", 100.0, 90.0, direction="short"),),
        ),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 1
    trip = report.round_trips[0]
    assert trip.direction == "short"
    assert trip.realized_r == pytest.approx(2.0)  # (100 − 90) / (105 − 100)
    assert report.positive_share == 1.0
    assert report.unmeasured == ()


def test_score_replay_reports_a_short_open_position_with_unrealized_r() -> None:
    """Una corta viva se marca a mercado con geometría corta (no se descarta)."""
    ticks = [
        _tick(
            _day(0),
            fills=(ReplayFill(_day(0), "AAA", "sell", 100.0, 100.0, direction="short"),),
            stops={"AAA": 105.0},
        ),
        _tick(_day(1), prices={"AAA": 95.0}),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 0
    assert len(report.open_positions) == 1
    assert report.open_positions[0].direction == "short"
    assert report.open_positions[0].unrealized_r == pytest.approx(1.0)  # (100 − 95) / 5


def test_score_replay_declares_an_unsupported_direction_instead_of_assuming_long() -> None:
    """Una dirección no reconocible se DECLARA (fail-closed); nunca se asume larga."""
    ticks = [
        _tick(
            _day(0),
            fills=(ReplayFill(_day(0), "AAA", "buy", 100.0, 100.0, direction="flat"),),
            stops={"AAA": 95.0},
        ),
        _tick(
            _day(1),
            fills=(ReplayFill(_day(1), "AAA", "sell", 100.0, 110.0, direction="flat"),),
        ),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 0
    assert any("direccion_no_soportada" in gap for gap in report.unmeasured)
