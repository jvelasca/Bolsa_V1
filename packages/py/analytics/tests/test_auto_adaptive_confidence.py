"""AUTO-12 — tests del motor de CONFIANZA estadística puro (``auto_adaptive_confidence``).

Lo que se prueba es la disciplina de medición, que es el punto entero del módulo:

* que la muestra que **sostiene** un número sea la de R medido (``effective_n``), no la bruta;
* que la completitud de medición sea **compuesta** (R + R neto + PnL) y que un cubo no
  medido baje la banda en vez de pasar por medida;
* que ``recent``/``long`` se ordenen por **instante real** y que sin fechas legibles se
  **declare** el hueco (``recent_unavailable``, ``decay = UNKNOWN``) en vez de inventar
  cronología — la lección que ``cycle_risk`` cerró en ``V2.52``;
* que las bandas de ``decay`` sean las declaradas (``NONE``/``MILD``/``SEVERE``/``UNKNOWN``)
  y que ``UNKNOWN`` ponga TECHO de confianza (no se premia lo que no se pudo leer);
* que la lectura sea orden-invariante y que una ausencia de ciclos devuelva una lectura
  vacía **declarada**, nunca un cero mudo.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_BASIS_MIXED,
    ADAPTIVE_BASIS_STABLE_APPLIED,
    ADAPTIVE_BASIS_STABLE_ESTIMATED,
    ADAPTIVE_BASIS_TRANSITION,
    ADAPTIVE_BASIS_UNKNOWN,
    ADAPTIVE_CONFIDENCE_HIGH,
    ADAPTIVE_CONFIDENCE_LOW,
    ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE,
    ADAPTIVE_CONFIDENCE_MEDIUM,
    ADAPTIVE_CONFIDENCE_NO_CYCLES,
    ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT,
    ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE,
    ADAPTIVE_CONFIDENCE_RECENT_UNDATED,
    ADAPTIVE_CONFIDENCE_THIN_SAMPLE,
    ADAPTIVE_DECAY_MILD,
    ADAPTIVE_DECAY_NONE,
    ADAPTIVE_DECAY_SEVERE,
    ADAPTIVE_DECAY_UNKNOWN,
    _basis_transition,
    build_adaptive_confidence,
)
from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_COST_BASIS_APPLIED,
    SELF_EVAL_COST_BASIS_ESTIMATED,
    SELF_EVAL_COST_BASIS_MIXED,
)


def _cycle(
    version: str = "orb-1",
    *,
    index: int = 0,
    pnl: str = "10",
    regime: str = "TREND_UP",
    closed_at: str | None = None,
    risk: str | None = "5",
    cost: bool = True,
    cost_measurement: str = "COMPLETE",
) -> dict[str, object]:
    """Fila de ciclo mínima: lo que el cruce y la confianza leen, y nada inventado."""
    row: dict[str, object] = {
        "cycleId": f"{version}-{index}",
        "strategyVersion": version,
        "pnl": pnl,
        "marketRegime": regime,
    }
    if closed_at is not None:
        row["closedAt"] = closed_at
    if risk is not None:
        row["riskAmount"] = risk
    if cost:
        row["cost"] = {"total": 1.0, "measurement": cost_measurement}
    return row


def _dated(
    version: str = "orb-1",
    *,
    count: int,
    first_day: int = 1,
    month: int = 9,
    index_offset: int = 0,
    pnl: str = "10",
    regime: str = "TREND_UP",
    with_risk: bool = True,
    with_cost: bool = True,
    cost_measurement: str = "COMPLETE",
) -> list[dict[str, object]]:
    """``count`` ciclos con instante real (un día distinto cada uno => orden inequívoco)."""
    return [
        _cycle(
            version,
            index=index_offset + index,
            pnl=pnl,
            regime=regime,
            closed_at=f"2026-{month:02d}-{first_day + index:02d}T10:00:00+00:00",
            risk="5" if with_risk else None,
            cost=with_cost,
            cost_measurement=cost_measurement,
        )
        for index in range(count)
    ]


# ── Muestra: bruta vs la que sostiene el número ─────────────────────────────────────


def test_the_sample_that_sustains_the_number_is_the_measured_one() -> None:
    """40 ciclos, 4 con riesgo medido: la confianza habla de 4, no de 40."""
    cycles = _dated(count=4) + [
        _cycle(index=index, closed_at=f"2026-09-{index:02d}T10:00:00+00:00", risk=None)
        for index in range(5, 41)
    ]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=10)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.sample_size == 40
    assert row.effective_n == 4, "el denominador real de la expectancy son los R medidos"
    assert row.effective_n <= row.sample_size
    assert row.risk_coverage == pytest.approx(0.1)
    assert row.confidence == ADAPTIVE_CONFIDENCE_LOW
    assert ADAPTIVE_CONFIDENCE_THIN_SAMPLE in row.notes


def test_the_coverage_counts_what_was_actually_measured() -> None:
    cycles = _dated(count=8) + _dated(count=2, first_day=20, index_offset=100, with_cost=False)
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.risk_coverage == pytest.approx(1.0)
    assert row.cost_coverage == pytest.approx(0.8), "2 de 10 ciclos no declaran coste"
    assert row.measurement_completeness != "COMPLETE"
    assert ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE in row.notes


def test_regime_coverage_declares_the_cycles_without_a_regime() -> None:
    """Un ciclo sin régimen declarado NO prueba el cruce ``strategy × regime``."""
    cycles = _dated(count=6) + [
        _cycle(
            index=index,
            closed_at=f"2026-09-{index:02d}T10:00:00+00:00",
            regime="UNKNOWN",
        )
        for index in range(7, 11)
    ]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.regime_coverage == pytest.approx(0.6), "6 de 10 declaran régimen"
    assert len(row.by_regime) == 2, "el cubo UNKNOWN es una celda declarada, no un cero"


# ── Completitud compuesta y bandas de confianza ─────────────────────────────────────


def test_measurement_completeness_is_composed_from_r_net_r_and_pnl() -> None:
    """Sin coste medido, el R neto es ``UNKNOWN``; un solo eje ausente baja la banda."""
    no_cost = _dated(count=40, with_cost=False) + _dated(count=40, first_day=1, month=10)
    reading = build_adaptive_confidence(no_cost, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.measurement_completeness != "COMPLETE"
    assert row.confidence != ADAPTIVE_CONFIDENCE_HIGH, "medición incompleta no es HIGH"


def test_a_wide_and_fully_measured_sample_is_high_confidence() -> None:
    cycles = _dated(count=60) + _dated(count=60, first_day=1, month=10)
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.confidence == ADAPTIVE_CONFIDENCE_HIGH
    assert row.measurement_completeness == "COMPLETE"


def test_a_thin_sample_is_declared_low_instead_of_being_punished() -> None:
    """Ausencia de base ≠ dato malo: se declara ``LOW``; el castigo del reparto no vive aquí."""
    cycles = _dated(count=3)
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=10)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.confidence == ADAPTIVE_CONFIDENCE_LOW
    assert ADAPTIVE_CONFIDENCE_THIN_SAMPLE in row.notes


# ── Decay: bandas declaradas ────────────────────────────────────────────────────────


def test_a_recent_window_that_turned_negative_is_declared_severe() -> None:
    """El caso del audit: ``LONG +`` con ``RECENT −`` era invisible sin eje de recencia."""
    cycles = _dated(count=30, pnl="10") + _dated(count=10, first_day=1, month=10, pnl="-10")
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.long_expectancy_r is not None and row.long_expectancy_r > 0
    assert row.recent_expectancy_r is not None and row.recent_expectancy_r < 0
    assert row.decay == ADAPTIVE_DECAY_SEVERE
    assert row.confidence == ADAPTIVE_CONFIDENCE_LOW, "el deterioro severo baja un nivel"


def test_a_recent_window_that_only_faded_is_declared_mild() -> None:
    """``recent`` por debajo de ``long * 0.75`` sin llegar a negativo: MILD, no SEVERE."""
    cycles = _dated(count=30, pnl="10") + _dated(count=10, first_day=1, month=10, pnl="4")
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.decay == ADAPTIVE_DECAY_MILD


def test_a_recent_window_that_holds_up_is_declared_none() -> None:
    cycles = _dated(count=30, pnl="10") + _dated(count=10, first_day=1, month=10, pnl="12")
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.decay == ADAPTIVE_DECAY_NONE


def test_a_recent_window_below_the_minimum_sample_cannot_declare_decay() -> None:
    """Una ventana de 2 ciclos no autoriza a concluir deterioro: se declara ``UNKNOWN``."""
    cycles = _dated(count=30, pnl="10") + _dated(count=2, first_day=1, month=10, pnl="-10")
    reading = build_adaptive_confidence(cycles, recent_window=2, long_window=200, min_trades=10)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.decay == ADAPTIVE_DECAY_UNKNOWN
    assert ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT in row.notes


# ── Eje de recencia honesto ─────────────────────────────────────────────────────────


def test_without_readable_instants_the_recent_window_is_declared_not_invented() -> None:
    """Sin ``closedAt`` no se ordena por posición de lista fingiendo cronología."""
    cycles = [_cycle(index=index) for index in range(30)]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)

    row = reading.confidence_for("orb-1")
    assert row is not None
    assert reading.recent_available is False
    assert ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE in reading.notes
    assert ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE in row.notes
    assert row.recent_expectancy_r is None
    assert row.decay == ADAPTIVE_DECAY_UNKNOWN
    assert row.long_expectancy_r is not None, "la ventana larga SÍ se puede medir sin fechas"


def test_an_unreadable_instant_is_declared_but_a_readable_one_wins() -> None:
    cycles = _dated(count=12) + [
        _cycle(index=99, closed_at="no-es-una-fecha"),
        _cycle(index=100, closed_at="2026-09-31T10:00:00+00:00"),
    ]
    reading = build_adaptive_confidence(cycles, recent_window=5, long_window=200, min_trades=5)

    assert reading.recent_available is True
    assert ADAPTIVE_CONFIDENCE_RECENT_UNDATED in reading.notes


def test_an_unknown_decay_caps_the_confidence_instead_of_premising_it() -> None:
    """Sin ``decay`` legible no se premia: una muestra excelente se queda como máximo MEDIUM."""
    cycles = _dated(count=60) + _dated(count=60, first_day=1, month=10, index_offset=500)
    for cycle in cycles:
        del cycle["closedAt"]

    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.effective_n == 120, "la muestra es amplia y está medida"
    assert row.decay == ADAPTIVE_DECAY_UNKNOWN
    assert row.confidence == ADAPTIVE_CONFIDENCE_MEDIUM, "el techo no premia lo que no se pudo leer"


def test_the_recent_window_is_selected_by_instant_not_by_list_position() -> None:
    """Se reordena la ENTRADA: la ventana reciente debe salir del instante, no del orden."""
    cycles = _dated(count=30, pnl="10")
    recent_negative = _dated(count=10, first_day=1, month=10, pnl="-10")
    shuffled = list(reversed(recent_negative)) + list(reversed(cycles))

    reading = build_adaptive_confidence(shuffled, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.decay == ADAPTIVE_DECAY_SEVERE, "el orden de entrada no puede cambiar la lectura"


def test_the_reading_is_order_invariant() -> None:
    rows = (
        _dated(count=20, pnl="10")
        + _dated(count=5, first_day=21, pnl="10", regime="RANGE")
        + _dated(count=5, first_day=1, month=10, pnl="-10")
    )
    first = build_adaptive_confidence(rows, recent_window=5, long_window=200, min_trades=5)
    second = build_adaptive_confidence(list(reversed(rows)), recent_window=5, long_window=200, min_trades=5)

    assert first.as_dict() == second.as_dict()


def test_a_cycle_without_identity_is_still_measured_and_declared() -> None:
    """Sin ``cycleId`` el informe lo declara; la confianza no puede perder la fila."""
    rows = _dated(count=10)
    for _index, row in enumerate(rows):
        del row["cycleId"]
    reading = build_adaptive_confidence(rows, recent_window=5, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.sample_size == 10


# ── Lectura vacía declarada ─────────────────────────────────────────────────────────


def test_no_cycles_is_a_declared_empty_reading_not_a_mute_zero() -> None:
    reading = build_adaptive_confidence([])

    assert reading.by_strategy == ()
    assert reading.recent_available is False
    assert reading.notes == (ADAPTIVE_CONFIDENCE_NO_CYCLES,)
    assert reading.confidence_for("orb-1") is None
    assert reading.as_dict()["byStrategy"] == {}


def test_the_windows_are_declared_and_resolved_to_at_least_one() -> None:
    reading = build_adaptive_confidence(_dated(count=5), recent_window=0, long_window=0)

    assert reading.recent_window == 1 and reading.long_window == 1


# ── Desglose por régimen ────────────────────────────────────────────────────────────


def test_each_regime_cell_carries_its_own_sample_and_confidence() -> None:
    rows = _dated(count=60, regime="TREND_UP") + _dated(
        count=3, first_day=1, month=10, index_offset=200, regime="RANGE"
    )
    reading = build_adaptive_confidence(rows, recent_window=5, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    cells = {cell.regime: cell for cell in row.by_regime}
    assert cells["TREND_UP"].confidence == ADAPTIVE_CONFIDENCE_HIGH
    assert cells["RANGE"].confidence == ADAPTIVE_CONFIDENCE_LOW
    assert cells["RANGE"].effective_n == 3


def test_the_payload_is_json_shaped_and_carries_the_gaps() -> None:
    reading = build_adaptive_confidence(_dated(count=12), recent_window=5, long_window=200, min_trades=5)
    payload = reading.as_dict()
    row = payload["byStrategy"]["orb-1"]

    assert payload["recentWindow"] == 5 and payload["longWindow"] == 200
    assert row["sampleSize"] == 12
    assert row["measurementCompleteness"] == "COMPLETE"
    assert row["decay"] in {ADAPTIVE_DECAY_NONE, ADAPTIVE_DECAY_MILD, ADAPTIVE_DECAY_SEVERE}
    assert row["confidence"] in {
        ADAPTIVE_CONFIDENCE_LOW,
        ADAPTIVE_CONFIDENCE_MEDIUM,
        ADAPTIVE_CONFIDENCE_HIGH,
    }
    assert isinstance(row["notes"], list)
    assert isinstance(row["byRegime"], list)


def test_a_whole_window_of_unmeasured_risk_is_declared_unknown_not_zero() -> None:
    """Nadie midió el riesgo: la expectancy R queda declarada, no convertida en 0."""
    rows = _dated(count=20, with_risk=False)
    reading = build_adaptive_confidence(rows, recent_window=5, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.effective_n == 0
    assert row.long_expectancy_r is None, "sin riesgo no hay R; jamás un cero"
    assert row.risk_coverage == 0.0
    assert row.decay == ADAPTIVE_DECAY_UNKNOWN


# ── AUTO-17 — la base del R neto como dimensión estadística ─────────────────────────


def _cycle_with_basis(
    version: str,
    *,
    index: int,
    basis: str,
    closed_at: str,
    pnl: str = "10",
    regime: str = "TREND_UP",
) -> dict[str, object]:
    """Ciclo del que sale un R neto con la base pedida (``estimated`` o ``applied``).

    La base ``applied`` exige que la comisión del MODELO sea cuantificable: sin ella el neto
    aplicado no se compone y vuelve al estimado (la regla de ``AUTO-16``).
    """
    row = _cycle(version, index=index, pnl=pnl, regime=regime, closed_at=closed_at)
    if basis == "applied":
        row["cost"] = {"total": 1.0, "commission": 0.5, "measurement": "COMPLETE"}
        row["costApplied"] = {"friction": "0.5", "measurement": "COMPLETE"}
    return row


def test_the_basis_transition_states_are_declared() -> None:
    """El detector es puro y declara sus cinco estados, incluida la transición real."""
    assert (
        _basis_transition(SELF_EVAL_COST_BASIS_ESTIMATED, SELF_EVAL_COST_BASIS_ESTIMATED)
        == ADAPTIVE_BASIS_STABLE_ESTIMATED
    )
    assert (
        _basis_transition(SELF_EVAL_COST_BASIS_APPLIED, SELF_EVAL_COST_BASIS_APPLIED)
        == ADAPTIVE_BASIS_STABLE_APPLIED
    )
    assert (
        _basis_transition(SELF_EVAL_COST_BASIS_ESTIMATED, SELF_EVAL_COST_BASIS_APPLIED)
        == ADAPTIVE_BASIS_TRANSITION
    )
    assert _basis_transition("mixed", SELF_EVAL_COST_BASIS_APPLIED) == ADAPTIVE_BASIS_MIXED
    assert _basis_transition(None, SELF_EVAL_COST_BASIS_APPLIED) == ADAPTIVE_BASIS_UNKNOWN
    assert _basis_transition("undeclared", SELF_EVAL_COST_BASIS_ESTIMATED) == ADAPTIVE_BASIS_UNKNOWN


def test_a_homogeneous_window_is_stable_and_keeps_the_historic_decay() -> None:
    """CONTROL de compatibilidad: una sola base ⇒ ``STABLE_ESTIMATED`` y el decay de siempre."""
    cycles = _dated(count=30, pnl="10") + _dated(count=10, first_day=1, month=10, pnl="-10")
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_ESTIMATED
    assert row.basis_transition == ADAPTIVE_BASIS_STABLE_ESTIMATED
    assert row.decay == ADAPTIVE_DECAY_SEVERE


def test_a_window_that_spans_two_bases_declares_mixed_and_refuses_to_decay() -> None:
    """AUTO-17: una ventana que mezcla ``estimated`` (viejo) con ``applied`` (nuevo) ⇒ ``MIXED``.

    Es el escenario de la transición real: el neto reciente sale más alto porque cambió el metro,
    no porque la estrategia mejore. La lectura lo declara (``mixed``), no publica pooled y NO
    interpreta el salto como deterioro ni mejora (``decay = UNKNOWN``).
    """
    old = [
        _cycle_with_basis(
            "orb-1", index=i, basis="estimated", closed_at=f"2026-09-{i:02d}T10:00:00+00:00"
        )
        for i in range(1, 31)
    ]
    new = [
        _cycle_with_basis(
            "orb-1",
            index=100 + i,
            basis="applied",
            closed_at=f"2026-10-{i:02d}T10:00:00+00:00",
            pnl="14",
        )
        for i in range(1, 11)
    ]
    reading = build_adaptive_confidence(old + new, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_MIXED
    assert row.basis_transition == ADAPTIVE_BASIS_MIXED
    assert row.decay == ADAPTIVE_DECAY_UNKNOWN, "un cambio de base no es deterioro"
    assert len(row.net_r_series) == 2, "el desglose conserva las dos series"
    assert {series.basis for series in row.net_r_series} == {
        SELF_EVAL_COST_BASIS_ESTIMATED,
        SELF_EVAL_COST_BASIS_APPLIED,
    }


def test_a_stable_applied_window_is_declared_and_keeps_the_historic_decay() -> None:
    """CONTROL del otro extremo: todo medido contra el aplicado ⇒ ``STABLE_APPLIED``."""
    cycles = [
        _cycle_with_basis(
            "orb-1", index=i, basis="applied", closed_at=f"2026-09-{i:02d}T10:00:00+00:00"
        )
        for i in range(1, 31)
    ] + [
        _cycle_with_basis(
            "orb-1",
            index=100 + i,
            basis="applied",
            closed_at=f"2026-10-{i:02d}T10:00:00+00:00",
            pnl="-10",
        )
        for i in range(1, 11)
    ]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_APPLIED
    assert row.basis_transition == ADAPTIVE_BASIS_STABLE_APPLIED
    assert row.decay == ADAPTIVE_DECAY_SEVERE
