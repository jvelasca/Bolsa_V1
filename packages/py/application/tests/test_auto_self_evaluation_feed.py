"""AUTO-7 — tests del alimentador read-only del informe de autoevaluación.

Se prueba lo que el adaptador NO puede permitirse: contar como cerrado un ciclo que sigue
abierto, inventar PnL sin contrapartida, repartir entre dos estrategias un ciclo que declara
dos versiones, o rellenar con ceros los huecos (R, MAE/MFE, slippage, embudo) que los
productores actuales no aportan.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import recovery_reading
from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE,
    ADAPTIVE_DECAY_SEVERE,
    build_adaptive_confidence,
)
from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_CYCLE_WITHOUT_IDENTITY,
    SELF_EVAL_UNVERSIONED_CYCLE,
    evaluate_auto_self_evaluation,
)
from bolsa_application.auto_self_evaluation_feed import (
    build_adaptive_confidence_from_fills,
    build_auto_self_evaluation,
    cycles_from_fills,
    make_auto_self_evaluation_provider,
    recovery_evidence_from_fills,
)
from bolsa_application.cycle_risk import cycle_risk_from_reservations
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)


def _fill(
    side: str,
    qty: str,
    price: str,
    *,
    execution_id: str,
    version: str = "orb-1",
    cycle_id: str | None = None,
    created_at: datetime | None = None,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        strategy_version_id=version,
        cycle_id=cycle_id,
        created_at=created_at,
    )


# ── Reconstrucción del ciclo ────────────────────────────────────────────────────────


def test_a_closed_cycle_is_reconstructed_from_its_two_fills() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )

    assert cycles == (
        {"cycleId": "cyc-1", "strategyVersion": "orb-1", "pnl": Decimal("50")},
    )


def test_an_open_cycle_is_not_counted_as_a_result() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "4", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )

    assert cycles == (), "una posición abierta todavía no tiene resultado que medir"


def test_a_sell_without_counterpart_does_not_fabricate_pnl() -> None:
    cycles = cycles_from_fills(
        [_fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1")]
    )

    assert cycles == (), "sin compra que casar no hay PnL (no se fabrica un corto)"


def test_partial_exits_of_a_closed_cycle_realize_fifo_once() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "4", "105", execution_id="e2", cycle_id="cyc-1"),
            _fill("sell", "6", "110", execution_id="e3", cycle_id="cyc-1"),
        ]
    )

    assert len(cycles) == 1
    assert cycles[0]["pnl"] == Decimal("80"), "4×5 + 6×10, una sola vez"


def test_legacy_fills_without_cycle_id_yield_one_anonymous_cycle_per_match() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1"),
            _fill("buy", "10", "102", execution_id="e2"),
            _fill("sell", "10", "105", execution_id="e3"),
            _fill("sell", "10", "110", execution_id="e4"),
        ]
    )

    assert [cycle["pnl"] for cycle in cycles] == [Decimal("50"), Decimal("80")]
    assert all("cycleId" not in cycle for cycle in cycles), "sin identidad: se declara"


def test_a_cycle_declaring_two_strategies_is_not_split_between_them() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", version="orb-1", cycle_id="cyc-1"),
            _fill(
                "sell", "10", "105", execution_id="e2", version="meanrev-2", cycle_id="cyc-1"
            ),
        ]
    )

    assert cycles == ({"cycleId": "cyc-1", "strategyVersion": "", "pnl": Decimal("50")},)

    report = build_auto_self_evaluation(fills=[
        _fill("buy", "10", "100", execution_id="e1", version="orb-1", cycle_id="cyc-1"),
        _fill("sell", "10", "105", execution_id="e2", version="meanrev-2", cycle_id="cyc-1"),
    ])
    assert report.by_strategy == ()
    assert report.unattributed_cycles == 1
    assert SELF_EVAL_UNVERSIONED_CYCLE in report.notes


def test_anonymous_legacy_cycles_are_declared_by_the_report() -> None:
    report = build_auto_self_evaluation(
        fills=[
            _fill("buy", "10", "100", execution_id="e1"),
            _fill("sell", "10", "105", execution_id="e2"),
        ]
    )

    assert report.cycles == 1
    assert report.cycles_without_identity == 1
    assert SELF_EVAL_CYCLE_WITHOUT_IDENTITY in report.notes
    assert report.by_strategy[0].realized_pnl == 50


# ── Huecos declarados, nunca rellenados ─────────────────────────────────────────────


def test_the_report_declares_what_fills_alone_cannot_measure() -> None:
    report = build_auto_self_evaluation(
        fills=[
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )
    row = report.by_strategy[0]

    assert row.expectancy_currency == 50
    assert row.win_rate == 1.0
    assert row.profit_factor is None, "sin perdedoras el ratio es indefinido"
    assert row.expectancy_r is None and row.risk_measurement == "UNKNOWN"
    assert row.mfe_r is None and row.excursions_measurement == "UNKNOWN"
    assert row.slippage_currency is None
    assert report.funnel_closed is False and report.seen is None
    assert report.read_only is True
    assert report.decisive is False, "una sola operación no autoriza a concluir"


def test_no_fills_is_an_unknown_report_not_a_report_of_zeros() -> None:
    report = build_auto_self_evaluation(fills=[])

    assert report.cycles == 0
    assert report.realized_pnl == 0
    assert report.expectancy_currency is None
    assert report.measurement == "UNKNOWN"
    assert report.by_strategy == ()


# ── AUTO-12 — instante de cierre (``closedAt``) sin cambiar la forma de AUTO-7 ───────


def test_without_instants_the_cycle_shape_is_the_historical_one() -> None:
    """Byte-identidad de AUTO-7: sin ``created_at`` no aparece ``closedAt``."""
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )

    assert cycles == (
        {"cycleId": "cyc-1", "strategyVersion": "orb-1", "pnl": Decimal("50")},
    )
    assert all("closedAt" not in cycle for cycle in cycles)


def test_the_close_instant_is_the_last_fill_of_the_cycle() -> None:
    """El cierre de un ciclo es su ÚLTIMO fill: no se toma el primero ni el de entrada."""
    cycles = cycles_from_fills(
        [
            _fill(
                "buy",
                "10",
                "100",
                execution_id="e1",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
            ),
            _fill(
                "sell",
                "10",
                "105",
                execution_id="e2",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 14, 30, tzinfo=UTC),
            ),
        ]
    )

    assert len(cycles) == 1
    assert cycles[0]["closedAt"] == "2026-09-20T14:30:00+00:00"


def test_partial_exits_take_the_latest_instant_as_the_close() -> None:
    cycles = cycles_from_fills(
        [
            _fill(
                "buy",
                "10",
                "100",
                execution_id="e1",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
            ),
            _fill(
                "sell",
                "4",
                "105",
                execution_id="e2",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 11, 0, tzinfo=UTC),
            ),
            _fill(
                "sell",
                "6",
                "110",
                execution_id="e3",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 16, 45, tzinfo=UTC),
            ),
        ]
    )

    assert cycles[0]["closedAt"] == "2026-09-20T16:45:00+00:00"


def test_a_legacy_anonymous_cycle_claims_no_close_instant() -> None:
    """Sin identidad de ciclo no hay frontera de cierre que afirmar: se declara el hueco."""
    cycles = cycles_from_fills(
        [
            _fill(
                "buy",
                "10",
                "100",
                execution_id="e1",
                created_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
            ),
            _fill(
                "sell",
                "10",
                "105",
                execution_id="e2",
                created_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
            ),
        ]
    )

    assert len(cycles) == 1
    assert "closedAt" not in cycles[0], "el ciclo anónimo no reclama un instante"


def test_a_fill_without_a_readable_instant_does_not_hide_the_other_ones() -> None:
    """Un fill sin fecha no borra el cierre medible del grupo (y no se inventa el suyo)."""
    cycles = cycles_from_fills(
        [
            _fill(
                "buy",
                "10",
                "100",
                execution_id="e1",
                cycle_id="cyc-1",
            ),
            _fill(
                "sell",
                "10",
                "105",
                execution_id="e2",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
            ),
        ]
    )

    assert cycles[0]["closedAt"] == "2026-09-20T12:00:00+00:00"


def test_the_report_ignores_the_close_instant_it_does_not_declare() -> None:
    """``closedAt`` es eje de la CONFIANZA, no magnitud del informe: AUTO-7 no cambia."""
    with_instants = build_auto_self_evaluation(
        fills=[
            _fill(
                "buy",
                "10",
                "100",
                execution_id="e1",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
            ),
            _fill(
                "sell",
                "10",
                "105",
                execution_id="e2",
                cycle_id="cyc-1",
                created_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
            ),
        ]
    )
    without_instants = build_auto_self_evaluation(
        fills=[
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )

    assert with_instants.as_dict() == without_instants.as_dict()


def test_the_confidence_reading_uses_the_same_material_as_the_report() -> None:
    """La confianza y el informe se construyen de los MISMOS fills: no hay segundo productor."""
    fills = [
        _fill(
            "buy",
            "10",
            "100",
            execution_id=f"b{index}",
            cycle_id=f"cyc-{index}",
            created_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        )
        for index in range(12)
    ] + [
        _fill(
            "sell",
            "10",
            "105",
            execution_id=f"s{index}",
            cycle_id=f"cyc-{index}",
            created_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
        )
        for index in range(12)
    ]

    reading = build_adaptive_confidence_from_fills(fills=fills, min_trades=5)
    report = build_auto_self_evaluation(fills=fills)

    row = reading.confidence_for("orb-1")
    assert row is not None
    assert row.sample_size == report.by_strategy[0].trades == 12
    assert reading.as_dict() == build_adaptive_confidence(
        cycles_from_fills(fills), min_trades=5
    ).as_dict()


def test_without_instants_the_confidence_declares_the_gap_instead_of_ordering() -> None:
    reading = build_adaptive_confidence_from_fills(
        fills=[
            _fill("buy", "10", "100", execution_id=f"b{index}", cycle_id=f"cyc-{index}")
            for index in range(6)
        ]
        + [
            _fill("sell", "10", "105", execution_id=f"s{index}", cycle_id=f"cyc-{index}")
            for index in range(6)
        ],
        min_trades=5,
    )

    row = reading.confidence_for("orb-1")
    assert row is not None
    assert reading.recent_available is False
    assert ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE in reading.notes
    assert row.recent_expectancy_r is None


def _cycle_risk(cycle_ids: list[str]) -> dict[str, Any]:
    """Evidencia de riesgo REAL del módulo de ``AUTO-9``: mismo productor que el informe."""
    reservations = [
        SimpleNamespace(
            cycle_id=cycle_id,
            reservation_id=f"RES-{cycle_id}",
            is_buy=True,
            reserved_risk="5",
            cost=None,
            created_at="2026-09-01T09:00:00+00:00",
        )
        for cycle_id in cycle_ids
    ]
    return cycle_risk_from_reservations(cycle_ids, reservations)


def test_the_confidence_reading_is_ordered_by_instant_and_measures_decay() -> None:
    """Un ciclo reciente perdedor sobre un histórico ganador: SEVERE, no NONE."""
    early = [
        _fill(
            "buy",
            "10",
            "100",
            execution_id=f"eb{index}",
            cycle_id=f"old-{index}",
            created_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        )
        for index in range(10)
    ] + [
        _fill(
            "sell",
            "10",
            "110",
            execution_id=f"es{index}",
            cycle_id=f"old-{index}",
            created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        )
        for index in range(10)
    ]
    late = [
        _fill(
            "buy",
            "10",
            "110",
            execution_id=f"lb{index}",
            cycle_id=f"new-{index}",
            created_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        )
        for index in range(6)
    ] + [
        _fill(
            "sell",
            "10",
            "100",
            execution_id=f"ls{index}",
            cycle_id=f"new-{index}",
            created_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
        )
        for index in range(6)
    ]
    cycle_ids = [f"old-{index}" for index in range(10)] + [f"new-{index}" for index in range(6)]

    reading = build_adaptive_confidence_from_fills(
        fills=[*early, *late],
        cycle_risk=_cycle_risk(cycle_ids),
        recent_window=6,
        long_window=200,
        min_trades=5,
    )
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.long_expectancy_r is not None and row.long_expectancy_r > 0
    assert row.recent_expectancy_r is not None and row.recent_expectancy_r < 0
    assert row.decay == ADAPTIVE_DECAY_SEVERE
    assert row.confidence == "LOW", "el deterioro severo baja un nivel la banda"


# ── Provider (composición) ─────────────────────────────────────────────────────────


class _Session:
    """Sesión mínima: el provider la abre y la cierra, nada más."""

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


@pytest.mark.asyncio
async def test_provider_returns_the_report_of_the_version() -> None:
    store = InMemorySimFillFinanceContextStore()
    await store.save(_fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"))
    await store.save(_fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"))
    provider = make_auto_self_evaluation_provider(
        lambda: _Session(), store_factory=lambda _session: store
    )

    payload = await provider("orb-1")

    assert payload["readOnly"] is True
    assert payload["byStrategy"][0]["strategyVersion"] == "orb-1"
    assert payload["byStrategy"][0]["realizedPnl"] == "50.000000"


@pytest.mark.asyncio
async def test_provider_without_version_declares_the_reason() -> None:
    provider = make_auto_self_evaluation_provider(lambda: _Session())

    payload = await provider("   ")

    assert payload["errors"] == ["strategy_version_required"]
    assert payload["decisive"] is False


@pytest.mark.asyncio
async def test_provider_read_failure_is_declared_and_never_fabricates_metrics() -> None:
    class _Broken:
        async def list_for_strategy_version(self, *_a: object, **_k: object) -> None:
            raise RuntimeError("db down")

    provider = make_auto_self_evaluation_provider(
        lambda: _Session(), store_factory=lambda _session: _Broken()
    )

    payload = await provider("orb-1")

    assert payload["errors"] == ["read_failed"]
    assert payload["byStrategy"] == []
    assert payload["decisive"] is False


def test_the_pure_feeds_module_does_not_touch_the_analytics_input_contract() -> None:
    """El informe de los fills y el informe puro comparten contrato (mismo ``as_dict``)."""
    report = build_auto_self_evaluation()
    assert report.as_dict() == evaluate_auto_self_evaluation().as_dict()


# ── Evidencia de la rampa de reincorporación (AUTO-13, §24) ─────────────────────────


def _closed_cycle(
    cycle_id: str,
    *,
    version: str = "orb-1",
    at: datetime,
    profitable: bool = True,
) -> list[SimFillFinanceContext]:
    """Un ciclo cerrado medido: ``pnl`` de ±5 sobre un riesgo reservado de 5 ⇒ ``R`` de ±1."""
    return [
        _fill(
            "buy",
            "10",
            "100",
            execution_id=f"{cycle_id}-b",
            version=version,
            cycle_id=cycle_id,
            created_at=at,
        ),
        _fill(
            "sell",
            "10",
            "100.5" if profitable else "99.5",
            execution_id=f"{cycle_id}-s",
            version=version,
            cycle_id=cycle_id,
            created_at=at,
        ),
    ]


def _evidence_for(fills: list[Any], **overrides: Any):
    cycle_ids = sorted({fill.cycle_id for fill in fills if fill.cycle_id})
    base: dict[str, Any] = {
        "fills": fills,
        "cycle_risk": _cycle_risk(cycle_ids),
        "reactivated_at": {"orb-1": "2026-09-10T00:00:00+00:00"},
    }
    base.update(overrides)
    return recovery_evidence_from_fills(**base).get("orb-1")


def test_the_recovery_evidence_counts_only_the_cycles_after_the_cut() -> None:
    """La rampa cuenta la evidencia POSTERIOR al corte: la anterior a la reactivación no suma."""
    before = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
    after = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    fills = [
        *_closed_cycle("old-1", at=before),
        *_closed_cycle("old-2", at=before),
        *_closed_cycle("new-1", at=after),
        *_closed_cycle("new-2", at=after),
    ]
    evidence = _evidence_for(fills)

    assert evidence is not None
    assert evidence.measured_cycles == 2
    assert evidence.window_available is True
    assert evidence.measured_positive is True
    assert evidence.note is None


def test_a_patiently_recovered_version_climbs_one_step_per_three_positive_cycles() -> None:
    """Con la evidencia real de los fills, la rampa sube 0.25 → 0.50 a los tres ciclos."""
    at = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    fills = [fill for index in range(3) for fill in _closed_cycle(f"new-{index}", at=at)]
    evidence = _evidence_for(fills)

    assert evidence is not None and evidence.measured_cycles == 3
    assert recovery_reading(evidence).step == pytest.approx(0.50)


def test_without_a_fechado_cut_there_is_no_ramp() -> None:
    """Sin corte durable no se emite evidencia: no se inventa una reincorporación."""
    at = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    fills = _closed_cycle("new-1", at=at)

    assert recovery_evidence_from_fills(fills=fills, reactivated_at={}) == {}
    assert recovery_evidence_from_fills(fills=fills, reactivated_at={"orb-1": "   "}) == {}
    assert recovery_evidence_from_fills(fills=fills, reactivated_at={"orb-1": "ayer"}) == {}


def test_a_version_without_legible_dates_declares_the_window_unavailable() -> None:
    """Sin ``closedAt`` legible la rampa no puede subir; el hueco se DECLARA, no se rellena."""
    undated = [
        _fill("buy", "10", "100", execution_id="ub", cycle_id="new-1"),
        _fill("sell", "10", "100.5", execution_id="us", cycle_id="new-1"),
    ]
    evidence = _evidence_for(undated)

    assert evidence is not None
    assert evidence.window_available is False
    assert evidence.note == "recovery_unmeasured"


def test_a_negative_recent_window_resets_the_ramp() -> None:
    """El deterioro medido manda: la rampa se reinicia en vez de seguir subiendo."""
    at = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    fills = _closed_cycle("new-1", at=at, profitable=False)
    cycle_ids = ["new-1"]
    reading = build_adaptive_confidence_from_fills(
        fills=fills, cycle_risk=_cycle_risk(cycle_ids), recent_window=1, long_window=1, min_trades=1
    )
    evidence = _evidence_for(fills, confidence=reading)

    assert evidence is not None
    assert evidence.measured_positive is False
    assert recovery_reading(evidence).step == pytest.approx(0.25)
    assert recovery_reading(evidence).note == "recovery_not_positive"


def test_a_severe_decay_is_declared_in_the_recovery_evidence() -> None:
    """``decay == SEVERE`` viaja a la evidencia para que la rampa se reinicie por el motivo real."""
    early = [
        fill
        for index in range(12)
        for fill in _closed_cycle(f"old-{index}", at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    ]
    late = [
        fill
        for index in range(6)
        for fill in _closed_cycle(
            f"new-{index}", at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC), profitable=False
        )
    ]
    cycle_ids = [f"old-{index}" for index in range(12)] + [f"new-{index}" for index in range(6)]
    reading = build_adaptive_confidence_from_fills(
        fills=[*early, *late],
        cycle_risk=_cycle_risk(cycle_ids),
        recent_window=6,
        long_window=200,
        min_trades=1,
    )
    evidence = _evidence_for([*early, *late], confidence=reading)

    assert evidence is not None
    assert evidence.severe_decay is True
    assert recovery_reading(evidence).note == "recovery_severe_decay"


def test_a_version_that_was_never_paused_gets_no_evidence_row() -> None:
    at = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    fills = _closed_cycle("new-1", at=at)

    assert _evidence_for(fills, reactivated_at={"otra": "2026-09-10T00:00:00+00:00"}) is None
