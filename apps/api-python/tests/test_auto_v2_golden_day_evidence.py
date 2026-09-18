"""V2.42 slice 2c — evidencia de un DÍA completo (cierre del criterio de salida de AUTO-2).

El roadmap §4 cierra ``AUTO-2`` cuando se cumplen DOS cosas, y este fichero es su gate:

1. ``ProtectionConfig`` **sin ninguna lectura** en el camino ``AUTO_ENGINE_SIM_V2=1``: con el
   motor V2 ON la política legacy no se evalúa (se sustituye por un sensor que explota si
   alguien la llama) ⇒ la condición es **estructural**, no un valor afortunado.
2. ``TIME_EXIT``/``THESIS_EXIT`` **con evidencia en el journal de un día completo**: se corre
   un día hermético (sin PG) con tres posiciones que mueren por motivos DISTINTOS y se agrega
   el día con ``build_auto_daily_report`` (motivos de cierre + procedencia del ATR):

   * ``AAA`` vence por TIEMPO (techo congelado al nacer) ⇒ ``time_exit``;
   * ``BBB`` invalida su TESIS atravesando el nivel congelado ⇒ ``thesis_exit``;
   * ``CCC`` rompe el STOP estructural ⇒ ``structural_stop`` (no se disfraza de tesis);

   El día debe quedar ``healthy`` y la suma de motivos debe ser EXACTAMENTE el número de
   salidas: ningún cierre se queda sin explicar.

Además mide la **procedencia del ATR** de las candidatas del día (``real`` frente a
``fallback``), que es la medición con la que D3 decide (o no) flipar el veto.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.auto_daily_journal import build_auto_daily_report
from bolsa_application.auto_reason_codes import (
    ATR_GEOMETRY,
    ATR_SOURCE_FALLBACK,
    ATR_SOURCE_REAL,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

#: Tres símbolos, tres sectores: el gate de concentración sectorial no veta el día.
_SYMBOLS = ["AAA", "BBB", "CCC"]
_SECTORS = {"AAA": "tech", "BBB": "health", "CCC": "energy"}
#: ATR real inyectado (2 % de 100): el stop estructural queda en 100 − 1.5×2 = 97.
_ATR = {"v": 2.0}
#: Nivel de invalidación de tesis de ``BBB``: por debajo del precio y por encima del stop.
_THESIS_LEVEL = 99.5
#: Precio que rompe el stop estructural (97) de ``CCC``.
_STRUCTURAL_BREAK = 96.0


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    # El ``.env`` de la raíz se carga en el conftest: el veto de ATR debe partir SIEMPRE
    # del default (D3: medir ANTES de vetar).
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", raising=False)


def _edge_source(value: float = 0.9):
    """``EdgeReportSource`` fake: edge persistido por versión (sin PG)."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _worker(*, clock=None, prices: dict[str, float], atr: bool = True, **kwargs: object):
    """Worker del día: precio y ATR inyectados (deterministas), sin PG."""
    defaults: dict[str, object] = {
        "sector_source": lambda symbol: _SECTORS.get(symbol),
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": _edge_source(),
        "price_script": lambda symbol, _minute: prices[symbol],
    }
    if atr:
        defaults["atr_source"] = lambda _symbol: _ATR["v"]
    defaults.update(kwargs)
    defaults.setdefault("exec_store", InMemoryExecutionEventStore())
    if clock is None:
        _start, clock = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    return AutoSimulationWorker(clock=clock, **defaults)  # type: ignore[arg-type]


def _clock_holder(now: datetime):
    """Reloj mutable: el test decide cuándo avanza el tiempo (días, no minutos)."""
    holder = {"now": now}
    return holder, lambda: holder["now"]


def _decider_for(worker: AutoSimulationWorker, want: set[str]) -> _Prov:
    """BUY sólo para los símbolos planos que el día quiere abrir; HOLD en el resto."""

    def _d(symbol: str) -> DecisionPackage:
        if symbol in want and worker._open.get(symbol, Decimal("0")) <= 0:
            return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _journal_codes(worker: AutoSimulationWorker) -> list[str]:
    """Motivos de gestión de posición journalizados (payload ``reasonCodes``)."""
    return [
        code
        for entry in worker._v2_journal
        if entry.payload is not None and entry.event_type == "auto_position_management"
        for code in entry.payload["reasonCodes"]
    ]


async def _open_all_three(worker: AutoSimulationWorker) -> None:
    """Abre las tres posiciones del día (falla si el pipeline no las aprueba)."""
    want = set(_SYMBOLS)
    for _ in range(6):
        worker._decider = _decider_for(worker, want)
        await worker.auto_turn()
        if want.issubset(set(worker.open_symbols)):
            return
    raise AssertionError(
        f"el día no abrió las tres posiciones (abiertas: {worker.open_symbols})"
    )


async def _run_until_closed(worker: AutoSimulationWorker, symbol: str) -> None:
    """Corre ticks (HOLD) hasta que la posición muere; falla si no muere."""
    for _ in range(6):
        worker._decider = _decider_for(worker, set())
        await worker.auto_turn()
        if worker._open.get(symbol, Decimal("0")) <= 0:
            return
    raise AssertionError(f"la posición {symbol} no cerró (motivo no disparado)")


async def _run_golden_day(
    worker: AutoSimulationWorker, holder: dict[str, datetime], prices: dict[str, float]
) -> None:
    """Un día con tres desenlaces distintos (9:00 entrada → cierres → techo)."""
    await _open_all_three(worker)

    # BBB — la tesis se invalida: se declara el nivel congelado (seam: hoy ningún productor
    # lo manda al TradePlan) y el precio lo atraviesa SIN tocar el stop estructural (97).
    born = worker._v2_positions["BBB"]
    assert born.invalidation_price == born.initial_stop, "sin nivel, el stop es el nivel"
    worker._v2_positions["BBB"] = replace(born, invalidation_price=_THESIS_LEVEL)
    prices["BBB"] = 99.0
    await _run_until_closed(worker, "BBB")
    prices["BBB"] = 100.0

    # CCC — rompe el stop estructural: la venta NO puede atribuirse a la tesis.
    prices["CCC"] = _STRUCTURAL_BREAK
    await _run_until_closed(worker, "CCC")
    prices["CCC"] = 100.0

    # AAA — vence el techo de mantenimiento CONGELADO al nacer: se salta el tiempo (días).
    deadline = worker._v2_positions["AAA"].holding_deadline_at
    assert deadline is not None, "el techo debe nacer congelado (E1)"
    holder["now"] = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    await _run_until_closed(worker, "AAA")


# ── Evidencia del día: motivos de cierre + día sano ───────────────────────────────────


@pytest.mark.asyncio
async def test_v2_golden_day_journal_evidences_time_exit_and_thesis_exit(
    v2_env: None,
) -> None:
    """Un día completo declara ``time_exit`` y ``thesis_exit`` (criterio de salida)."""
    prices = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0}
    holder, clock = _clock_holder(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    worker = _worker(clock=clock, prices=prices)

    await _run_golden_day(worker, holder, prices)

    assert not worker.open_symbols, "el día debe cerrar el libro (tres salidas)"

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        atr_sources=worker.atr_source_counts(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    day = report.as_dict()

    # 1) El journal del día declara los tres motivos, cada uno UNA vez: la atribución es
    #    exclusiva (el stop-out no se cuenta como salida por tesis ni al revés).
    assert dict(report.exit_reasons) == {
        "time_exit": 1,
        "thesis_exit": 1,
        "structural_stop": 1,
    }, day
    assert report.exits == 3 and report.positions_created == 3, day
    assert sum(dict(report.exit_reasons).values()) == report.exits, "todo cierre explicado"

    # 2) Día AUTO sano (mismos invariantes que certifica el día SIM-ONLY).
    assert report.healthy, report.errors
    assert report.ledger_balance_status == "BALANCED"

    # 3) El journal RICO declara los motivos de la salida de gestión. Un cierre puede
    #    materializarse en DOS ventas parciales (la segunda cierra), así que el motivo
    #    aparece una vez por tick que pide salir: aquí se exige PRESENCIA y ausencia de
    #    motivos cruzados (el stop-out no entra por esta vía); el conteo exacto por cierre
    #    es el del día (arriba), que es la evidencia del criterio.
    codes = _journal_codes(worker)
    assert "time_exit" in codes, codes
    assert "thesis_exit" in codes, codes
    assert "structural_stop" not in codes, f"el stop-out no se declara como gestión: {codes}"

    # 4) La medición del ATR del día viaja en el reporte (procedencia, no impresión).
    assert dict(report.atr_sources).get(ATR_SOURCE_REAL, 0) > 0, day
    assert dict(report.atr_sources).get(ATR_SOURCE_FALLBACK, 0) == 0, day


@pytest.mark.asyncio
async def test_v2_golden_day_never_reads_the_legacy_protection_policy(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con ``AUTO_ENGINE_SIM_V2=1`` la política legacy NO se evalúa (sensor que explota).

    ``ProtectionConfig``/``ProtectionPolicy`` es el motor de protección ANTIGUO. El criterio
    de salida de ``AUTO-2`` exige que el camino V2 no la lea: aquí se sustituyen las dos
    funciones que la consultan por sensores que fallan, y el día completo debe terminar igual.
    """
    import bolsa_api.background.auto_simulation_worker as worker_mod

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("el camino V2 leyó la política de protección legacy")

    monkeypatch.setattr(worker_mod, "protection_exit_reason", _boom)
    monkeypatch.setattr(worker_mod, "protection_exit_fraction", _boom)

    prices = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0}
    holder, clock = _clock_holder(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    worker = _worker(clock=clock, prices=prices)

    await _run_golden_day(worker, holder, prices)

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        atr_sources=worker.atr_source_counts(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert report.exits == 3, "el día V2 completo corre sin tocar la política legacy"


@pytest.mark.asyncio
async def test_v2_golden_day_measures_atr_provenance_when_real_is_missing(
    v2_env: None,
) -> None:
    """Sin ATR real el día lo DECLARA (``atr_geometry``) y lo cuenta como ``fallback``.

    Es la medición que D3 pedía antes de flipar el veto: con ATR real disponible la
    procedencia es ``real``; sin él, el sintético se declara en el journal y se cuenta.
    """
    prices = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0}
    worker = _worker(prices=prices, atr=False)
    worker._decider = _decider_for(worker, {"AAA"})
    await worker.auto_turn()

    counts = dict(worker.atr_source_counts())
    assert counts.get(ATR_SOURCE_FALLBACK, 0) > 0, counts
    assert counts.get(ATR_SOURCE_REAL, 0) == 0, counts

    declared = [
        entry
        for entry in worker._v2_journal
        if entry.payload is not None and ATR_GEOMETRY in entry.payload["reasonCodes"]
    ]
    assert declared, "el ATR sintético debe declararse en el journal (nunca disfrazarse)"
    assert declared[0].payload["atrSource"] == ATR_SOURCE_FALLBACK
