"""AUTO-14 — la costura del reparto por CELDA de régimen (paso 5, §20).

Lo que se prueba es la costura del worker, no las piezas puras (esas viven en
``packages/py/analytics/tests/test_auto_adaptive.py``): que el cruce ``strategy × regime`` que el tick
ya mide (``AUTO-9``/``AUTO-10``) se traduzca en el **peso** del reparto cuando la celda del régimen
del tick está medida, que una celda **fina** NO mueva nada y lo declare, que la base de celda viaje
en su campo propio sin tocar los frames sellados (``allocation`` y el journal de ``AUTO-11``) y que
la subida del sello de política declare su consecuencia: un ``policy_version_mismatch`` marca el gate
``STALE`` **sin** resetear el contador de fallos.

El control NO es mudo: los dos caminos (con régimen por ciclo y sin él) corren sobre los MISMOS
fills, así que la única diferencia posible es la celda.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_CELL_NOTE_NOT_DECISIVE,
    ADAPTIVE_CELL_NOTE_NOT_FOUND,
    ALLOCATION_AXIS_NET_R,
)
from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    DATA_GATE_NOTE_POLICY_MISMATCH,
    DATA_GATE_STALE,
)
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_adaptive_recovery import AdaptiveStateReading
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading
from bolsa_application.sim_durable_store import SimFillFinanceContext

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"
_FLOOR = 0.35

#: Ciclos GANADORES en el régimen del tick: ``(110 − 100) · 10 / 5 = 20`` de R bruto, ``19.8`` neto.
_WIN = ("100", "110")
#: Ciclos ganadores SUAVES: ``R`` neto ``9.8``.
_MILD = ("100", "105")
#: Ciclos perdedores suaves (bajan la media global sin hundirla): ``R`` neto ``−2.2``.
_LOSS = ("110", "109")


def _fill(version: str, index: int, *, side: str, price: str) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=f"{version}-{index}-{side}",
        instrument_id="AAA",
        side=side,
        quantity=Decimal("10"),
        price=Decimal(price),
        account_id=_ACCOUNT,
        venue="SIM",
        strategy_version_id=version,
        cycle_id=f"cyc-{version}-{index}",
        created_at=datetime(2026, 9, 1, 9 if side == "buy" else 15, 0, tzinfo=UTC),
    )


def _cycles(
    version: str, start: int, count: int, *, trade: tuple[str, str]
) -> list[SimFillFinanceContext]:
    """``count`` ciclos cerrados y medidos de una versión, desde el índice ``start``."""
    buy, sell = trade
    return [
        fill
        for index in range(start, start + count)
        for fill in (
            _fill(version, index, side="buy", price=buy),
            _fill(version, index, side="sell", price=sell),
        )
    ]


class _FillStore:
    """Store de fills por versión: el único material del tick (no hay una lectura más)."""

    def __init__(self, by_version: dict[str, list[SimFillFinanceContext]]) -> None:
        self._by_version = by_version
        self.calls: list[str] = []

    async def list_for_strategy_version(
        self, version: str, *, account_id: str | None = None, limit: int | None = None
    ) -> list[SimFillFinanceContext]:
        self.calls.append(version)
        return list(self._by_version.get(version, ()))


class _Reservations:
    """Reservas de mentira con riesgo **y coste** medidos: el coste habilita el eje del R neto."""

    async def list_by_cycle_ids(
        self, _account_id: str | None, cycle_ids: Any, *, limit: int = 500
    ) -> list[Any]:
        return [
            SimpleNamespace(
                cycle_id=cycle_id,
                reservation_id=f"RES-{cycle_id}",
                is_buy=True,
                reserved_risk="5",
                cost={"total": 1.0, "measurement": "COMPLETE"},
                created_at="2026-09-01T09:00:00+00:00",
            )
            for cycle_id in cycle_ids
        ]


class _Reader:
    """Lector del régimen por ciclo (la mitad de lectura de ``AUTO-10``), por índice declarado."""

    def __init__(self, by_cycle: dict[str, str], *, default: str) -> None:
        self._by_cycle = by_cycle
        self._default = default
        self.calls: list[int] = []

    async def __call__(self, cycle_ids: Sequence[str]) -> CycleRegimeReading:
        self.calls.append(len(cycle_ids))
        return CycleRegimeReading(
            regime_by_cycle={
                cycle_id: self._by_cycle.get(cycle_id, self._default) for cycle_id in cycle_ids
            }
        )


def _worker(
    *,
    store: Any | None = None,
    regimes: _Reader | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = _Reservations()
    worker._cycle_regime_reader = regimes
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_sink_failures = 0
    worker._v2_adaptive_journal_anchor_age = 0
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = SimpleNamespace(strftime=lambda _fmt: _AS_OF)
    return worker


#: El material del tick: "a" y "b" compiten con el R neto medido, "c" tiene la celda del tick FINA.
#:
#: * ``a`` — 12 ganadores en ``TREND_UP`` y 12 perdedores suaves en ``RANGE`` ⇒ global ``8.8``,
#:   celda ``TREND_UP`` ``19.8``.
#: * ``b`` — 24 ganadores suaves en ``TREND_UP`` ⇒ global y celda ``9.8``.
#: * ``c`` — 2 ganadores en ``TREND_UP`` y 10 ganadores suaves en ``RANGE`` ⇒ global ``11.4667``,
#:   celda ``TREND_UP`` con solo 2 ciclos (``< min_trades``) ⇒ NO decisiva.
#:
#: El global de ``c`` es ALTO a propósito: mantiene la media del reparto por encima de ``a`` y
#: ``b``, de modo que el cambio de peso de la celda se ve en un multiplicador que NO está topado
#: (el mayor siempre satura en ``1.0``, así que una celda solo se mide en los demás).
def _material() -> dict[str, list[SimFillFinanceContext]]:
    return {
        "a": [
            *_cycles("a", 0, 12, trade=_WIN),
            *_cycles("a", 12, 12, trade=_LOSS),
        ],
        "b": _cycles("b", 0, 24, trade=_MILD),
        "c": [
            *_cycles("c", 0, 2, trade=_WIN),
            *_cycles("c", 2, 10, trade=_MILD),
        ],
    }


def _regime_reader(*, c_cell: bool = True) -> _Reader:
    """El régimen REAL de cada ciclo, por índice: el cruce gana sus celdas por versión.

    ``c_cell=False`` quita la celda ``TREND_UP`` de ``c`` moviendo sus dos primeros ciclos a
    ``BEAR_TREND`` (y el resto a ``RANGE``). **AUTO-18**: se mueven a un régimen DISTINTO, no a
    ``RANGE``, para que el número de RACHAS del global no cambie (``TREND_UP``+``RANGE`` → 2
    rachas; ``BEAR_TREND``+``RANGE`` → 2 rachas). La independencia es un eje propio que también
    encoge el global, así que el control de la celda FINA tiene que aislar la celda, no la racha.
    """
    by_cycle: dict[str, str] = {}
    for index in range(0, 12):
        by_cycle[f"cyc-a-{index}"] = "TREND_UP"
    for index in range(12, 24):
        by_cycle[f"cyc-a-{index}"] = "RANGE"
    for index in range(0, 24):
        by_cycle[f"cyc-b-{index}"] = "TREND_UP"
    first_regime = "TREND_UP" if c_cell else "BEAR_TREND"
    for index in range(0, 2):
        by_cycle[f"cyc-c-{index}"] = first_regime
    for index in range(2, 12):
        by_cycle[f"cyc-c-{index}"] = "RANGE"
    return _Reader(by_cycle, default="RANGE")


_ROWS = ("a", "b", "c")


# ── La celda medida mueve el PESO; la fina no lo mueve ──────────────────────────────


@pytest.mark.asyncio
async def test_a_measured_cell_moves_the_weight_and_a_thin_one_never_does() -> None:
    """Mismo material, tres caminos: la celda del tick afina el peso; la fina cae al global.

    Sin régimen por ciclo no hay celda para ``TREND_UP`` y el reparto pesa con la fila GLOBAL, así
    que la diferencia entre los planes solo puede venir del cruce ``strategy × regime``. Y la celda
    FINA no se controla por el valor del multiplicador (que encoge y se acota), sino contra el
    MISMO material con esa celda **ausente**: si la fina moviera el peso, los dos planes no podrían
    diferir solo en la NOTA declarada.
    """
    material = _material()
    without = await _worker(store=_FillStore(material))._v2_build_adaptive_plan(
        set(_ROWS), "BULL_TREND"
    )
    with_cells = await _worker(
        store=_FillStore(material), regimes=_regime_reader()
    )._v2_build_adaptive_plan(set(_ROWS), "BULL_TREND")
    thin_absent = await _worker(
        store=_FillStore(material), regimes=_regime_reader(c_cell=False)
    )._v2_build_adaptive_plan(set(_ROWS), "BULL_TREND")

    assert without is not None and with_cells is not None and thin_absent is not None
    # Sin cruce legible no se elige celda: el reparto es el GLOBAL y lo declara.
    assert without.allocation.cell_used == {}
    assert set(without.allocation.cell_fallback.values()) == {ADAPTIVE_CELL_NOTE_NOT_FOUND}
    assert without.allocation.evidence_axis == ALLOCATION_AXIS_NET_R

    # Con el cruce medido, "a" y "b" pesan con la celda de SU régimen del tick.
    assert with_cells.allocation.evidence_axis == ALLOCATION_AXIS_NET_R
    assert with_cells.allocation.cell_axis == ALLOCATION_AXIS_NET_R
    assert with_cells.allocation.cell_used == {"a": "TREND_UP", "b": "TREND_UP"}

    # La celda de "a" (19.8) sustituye a su global (8.8): "a" gana peso relativo y "b" lo pierde.
    # La celda afina, nunca ENSANCHA: el multiplicador sigue acotado a ``[0, 1]``.
    assert with_cells.allocation.multiplier_for("a") > without.allocation.multiplier_for("a")
    assert with_cells.allocation.multiplier_for("a") <= 1.0
    assert with_cells.allocation.multiplier_for("b") < without.allocation.multiplier_for("b")

    # CONTROL no mudo de la celda FINA: "c" cae a su GLOBAL en los dos cruces. Lo único que cambia
    # es la NOTA (la celda existía y era fina vs. no existía), jamás el peso ni quién compite.
    assert with_cells.allocation.cell_note_for("c") == ADAPTIVE_CELL_NOTE_NOT_DECISIVE
    assert thin_absent.allocation.cell_note_for("c") == ADAPTIVE_CELL_NOTE_NOT_FOUND
    assert with_cells.allocation.cell_for("c") is None
    assert with_cells.allocation.cell_used == thin_absent.allocation.cell_used
    assert with_cells.allocation.multipliers == thin_absent.allocation.multipliers


@pytest.mark.asyncio
async def test_the_cell_never_changes_who_competes_and_the_ramp_stays_the_ceiling() -> None:
    """La composición la decide la fila, y el techo de la rampa se aplica DESPUÉS del reparto."""
    fills = _material()
    without = await _worker(
        store=_FillStore(fills), regimes=_regime_reader()
    )._v2_build_adaptive_plan(set(_ROWS), "BULL_TREND")

    worker = _worker(store=_FillStore(fills), regimes=_regime_reader())
    # "a" vuelve de una pausa CUMPLIDA en este tick: se fecha aquí y su rampa arranca en el suelo.
    worker._v2_adaptive_paused_cycles = {"a": 5}
    with_ramp = await worker._v2_build_adaptive_plan(set(_ROWS), "BULL_TREND")

    assert without is not None and with_ramp is not None
    assert set(with_ramp.allocation.multipliers) == set(_ROWS), "nadie entra ni sale por la celda"
    assert with_ramp.allocation.cell_for("a") == "TREND_UP", (
        "primero se reparte con la celda; la rampa la topa, no la borra"
    )
    assert with_ramp.allocation.multiplier_for("a") == pytest.approx(0.25), "el escalón es TECHO"
    assert with_ramp.allocation.multiplier_for("a") < without.allocation.multiplier_for("a")
    # El techo topa SOLO a la que vuelve: no redistribuye a las demás ni les cambia la base.
    assert with_ramp.allocation.multiplier_for("b") == without.allocation.multiplier_for("b")
    assert with_ramp.allocation.multiplier_for("c") == without.allocation.multiplier_for("c")
    assert worker._v2_adaptive_sink_failures == 0, "la costura no inventa fallos de sink"


# ── La declaración viaja sin tocar los frames sellados ──────────────────────────────


@pytest.mark.asyncio
async def test_the_tick_declares_the_cell_basis_in_its_own_field(caplog: Any) -> None:
    """La base de CELDA se publica con campo propio: ``axis``, ``used`` y ``fallback``."""
    worker = _worker(store=_FillStore(_material()), regimes=_regime_reader())

    with caplog.at_level(logging.INFO):
        plan = await worker._v2_build_adaptive_plan(set(_ROWS), "BULL_TREND")

    assert plan is not None
    payload = plan.as_dict()
    assert set(payload["allocation"]) == {"riskMultipliers", "evidenceAxis"}, (
        "el frame sellado de ``allocation`` no se toca"
    )
    assert payload["allocationCells"] == {
        "axis": ALLOCATION_AXIS_NET_R,
        "used": {"a": "TREND_UP", "b": "TREND_UP"},
        "fallback": {"c": ADAPTIVE_CELL_NOTE_NOT_DECISIVE},
    }
    assert "adaptive allocation cells" in caplog.text
    assert "'TREND_UP'" in caplog.text
    assert ADAPTIVE_CELL_NOTE_NOT_DECISIVE in caplog.text


@pytest.mark.asyncio
async def test_the_journal_projection_is_byte_identical_with_a_cell_present() -> None:
    """``AUTO-11`` sigue proyectando DOS claves: una base de reparto nueva no se cuela al journal."""
    worker = _worker(store=_FillStore(_material()), regimes=_regime_reader())
    plan = await worker._v2_build_adaptive_plan(set(_ROWS), "BULL_TREND")
    assert plan is not None
    assert plan.allocation.cell_used, "el caso de prueba tiene celda: si no, no probaría nada"

    class _Journal:
        def __init__(self) -> None:
            self.entries: list[Any] = []

        async def sink(self, entry: Any) -> None:
            self.entries.append(entry)

    journal = _Journal()
    worker._adaptive_sink = journal.sink
    await worker._v2_journal_adaptive_recommendation(plan)

    assert len(journal.entries) == 1
    assert set(journal.entries[0].payload["allocation"]) == {"riskMultipliers", "evidenceAxis"}


# ── La consecuencia declarada del sello: mismatch de política ⇒ STALE, sin resetear ──


def test_the_seal_bump_declares_a_stale_gate_and_never_resets_the_failure_counter() -> None:
    """Cada subida del sello marca la evidencia histórica como de otra política: se DECLARA.

    Es la consecuencia medida de subir la versión de política (``auto14-v1`` → ``auto16-v1`` en
    ``AUTO-16``), no una relajación del contrato de ``AUTO-11``: el gate la declara ``STALE`` (una
    política distinta rigió esas filas), y por eso **no** se apagan las protecciones ni se resetea el
    contador de fallos del proceso.
    """
    worker = _worker(store=None)
    worker._v2_adaptive_state_reading = AdaptiveStateReading(policy_version_mismatch=True)
    worker._v2_adaptive_sink_failures = 2

    reading = worker._v2_adaptive_data_gate(
        report=SimpleNamespace(by_strategy=()),
        confidence=SimpleNamespace(by_strategy=(), recent_available=True),
        regime="BULL_TREND",
    )

    assert reading.status == DATA_GATE_STALE
    assert DATA_GATE_NOTE_POLICY_MISMATCH in reading.notes
    assert worker._v2_adaptive_sink_failures == 2, "un mismatch de política no es un fallo de sink"


def test_without_a_reading_the_gate_never_invents_a_mismatch() -> None:
    """Control: sin lectura durable registrada no hay mismatch que declarar."""
    worker = _worker(store=None)

    reading = worker._v2_adaptive_data_gate(
        report=SimpleNamespace(by_strategy=()),
        confidence=SimpleNamespace(by_strategy=(), recent_available=True),
        regime="BULL_TREND",
    )

    assert reading.status != DATA_GATE_STALE
    assert DATA_GATE_NOTE_POLICY_MISMATCH not in reading.notes
