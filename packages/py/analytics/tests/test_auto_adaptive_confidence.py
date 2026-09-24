"""AUTO-12 — tests del motor de CONFIANZA estadística puro (``auto_adaptive_confidence``).

Lo que se prueba es la disciplina de medición, que es el punto entero del módulo:

* que la muestra que **sostiene** un número sea la de R medido (``measured_n``), no la bruta;
* que ``AUTO-18`` mida además la **independencia**: ``episodes`` (rachas de régimen) y
  ``effective_n = min(measured_n, episodes)``, con la cobertura por celda como eje propio y la
  expectancy encogida (``shrunk_expectancy_r``) y la calibración descriptiva publicadas;
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

from datetime import UTC, datetime, timedelta

import pytest

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_BASIS_COST_MODEL_TRANSITION,
    ADAPTIVE_BASIS_DATA_DEGRADED,
    ADAPTIVE_BASIS_MIXED,
    ADAPTIVE_BASIS_STABLE_APPLIED,
    ADAPTIVE_BASIS_STABLE_ESTIMATED,
    ADAPTIVE_BASIS_TRANSITION,
    ADAPTIVE_BASIS_UNKNOWN,
    ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED,
    ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT,
    ADAPTIVE_CONFIDENCE_HIGH,
    ADAPTIVE_CONFIDENCE_LOW,
    ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE,
    ADAPTIVE_CONFIDENCE_MEDIUM,
    ADAPTIVE_CONFIDENCE_NO_CYCLES,
    ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT,
    ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE,
    ADAPTIVE_CONFIDENCE_RECENT_UNDATED,
    ADAPTIVE_CONFIDENCE_THIN_SAMPLE,
    ADAPTIVE_COVERAGE_HIGH,
    ADAPTIVE_COVERAGE_LOW,
    ADAPTIVE_COVERAGE_MEDIUM,
    ADAPTIVE_COVERAGE_UNCOVERED,
    ADAPTIVE_DECAY_MILD,
    ADAPTIVE_DECAY_NONE,
    ADAPTIVE_DECAY_SEVERE,
    ADAPTIVE_DECAY_UNKNOWN,
    ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT,
    BasisTransition,
    _band,
    _basis_transition,
    _decay,
    _episodes,
    _shrunk,
    build_adaptive_confidence,
)
from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_COST_BASIS_APPLIED,
    SELF_EVAL_COST_BASIS_ESTIMATED,
    SELF_EVAL_COST_BASIS_MIXED,
    SELF_EVAL_COST_BASIS_UNDECLARED,
)
from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE


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
    cost_model: str | None = None,
) -> dict[str, object]:
    """Fila de ciclo mínima: lo que el cruce y la confianza leen, y nada inventado.

    ``cost_model`` (``AUTO-18``) declara la VERSIÓN del modelo de coste (``costModelVersion`);
    sin ella la fila queda ``undeclared``, como todo histórico anterior a la fase.
    """
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
        cost_row: dict[str, object] = {"total": 1.0, "measurement": cost_measurement}
        if cost_model is not None:
            cost_row["costModelVersion"] = cost_model
        row["cost"] = cost_row
    return row


def _undeclared_cycle(
    version: str = "orb-1",
    *,
    index: int = 0,
    closed_at: str,
    pnl: str = "10",
    net_r: float = 0.1,
) -> dict[str, object]:
    """Ciclo con el neto DECLARADO de fuera y SIN base (``AUTO-18``): hay número, no hay metro."""
    return {
        "cycleId": f"{version}-{index}",
        "strategyVersion": version,
        "pnl": pnl,
        "marketRegime": "TREND_UP",
        "closedAt": closed_at,
        "riskAmount": "5",
        "netRMultiple": net_r,
    }


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
    """40 ciclos, 4 con riesgo medido: la confianza habla de 4, no de 40.

    ``AUTO-18`` añade un segundo descuento: esos 4 ciclos medidos forman UNA sola racha de
    régimen, así que la muestra EFECTIVA es 1 y el descuento se declara.
    """
    cycles = _dated(count=4) + [
        _cycle(index=index, closed_at=f"2026-09-{index:02d}T10:00:00+00:00", risk=None)
        for index in range(5, 41)
    ]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=10)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.sample_size == 40
    assert row.measured_n == 4, "el denominador real de la expectancy son los R medidos"
    assert row.episodes == 1, "los 4 medidos caen en la misma racha de régimen"
    assert row.effective_n == 1, "una sola fase de mercado no son 4 observaciones"
    assert row.effective_n <= row.measured_n <= row.sample_size
    assert row.risk_coverage == pytest.approx(0.1)
    assert row.confidence == ADAPTIVE_CONFIDENCE_LOW
    assert ADAPTIVE_CONFIDENCE_THIN_SAMPLE in row.notes
    assert ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT in row.notes


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
    assert row.measured_n == 120, "la muestra medida es amplia"
    assert row.episodes == 1, "sin fechas, los ciclos forman una sola racha de régimen"
    assert row.effective_n == 1, "la muestra EFECTIVA no hereda el bruto"
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
    assert cells["RANGE"].measured_n == 3
    assert cells["RANGE"].episodes == 1
    assert cells["RANGE"].effective_n == 1, "la celda RANGE mide una sola racha de régimen"


def test_the_payload_is_json_shaped_and_carries_the_gaps() -> None:
    reading = build_adaptive_confidence(_dated(count=12), recent_window=5, long_window=200, min_trades=5)
    payload = reading.as_dict()
    row = payload["byStrategy"]["orb-1"]

    assert payload["recentWindow"] == 5 and payload["longWindow"] == 200
    assert row["sampleSize"] == 12
    assert row["measuredN"] == 12
    assert row["episodes"] == 1
    assert row["effectiveN"] == 1
    assert row["coverage"] == ADAPTIVE_COVERAGE_LOW
    assert row["shrunkExpectancyR"] is not None
    assert row["measurementCompleteness"] == "COMPLETE"
    assert row["decay"] in {ADAPTIVE_DECAY_NONE, ADAPTIVE_DECAY_MILD, ADAPTIVE_DECAY_SEVERE}
    assert row["confidence"] in {
        ADAPTIVE_CONFIDENCE_LOW,
        ADAPTIVE_CONFIDENCE_MEDIUM,
        ADAPTIVE_CONFIDENCE_HIGH,
    }
    assert isinstance(row["notes"], list)
    assert isinstance(row["byRegime"], list)
    assert isinstance(payload["calibration"], list)


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
    cost_model: str | None = None,
) -> dict[str, object]:
    """Ciclo del que sale un R neto con la base pedida (``estimated`` o ``applied``).

    La base ``applied`` exige que la comisión del MODELO sea cuantificable: sin ella el neto
    aplicado no se compone y vuelve al estimado (la regla de ``AUTO-16``).

    ``cost_model`` (``AUTO-18``) declara la versión del modelo de coste; sin él la fila queda
    ``undeclared``, que es la misma ausencia que AUTO-17 no leía.
    """
    row = _cycle(
        version,
        index=index,
        pnl=pnl,
        regime=regime,
        closed_at=closed_at,
        cost_model=cost_model,
    )
    if basis == "applied":
        row["cost"] = {
            "total": 1.0,
            "commission": 0.5,
            "measurement": "COMPLETE",
            **({"costModelVersion": cost_model} if cost_model is not None else {}),
        }
        row["costApplied"] = {"friction": "0.5", "measurement": "COMPLETE"}
    return row


def test_the_basis_transition_states_are_declared() -> None:
    """El detector es puro y declara sus estados: los estables, la transición y los dos huecos.

    ``TRANSITION`` (cambió la BASE) y ``MIXED`` (la ventana mezcla) son ejes distintos, y
    ``DATA_DEGRADED`` (hay neto sin base declarada) es un TERCER estado, distinto del ``UNKNOWN``
    inocuo (no hay neto con el que decidir).
    """
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
    # ``None`` = NO HAY NETO: el desconocido inocuo, que no bloquea.
    assert _basis_transition(None, SELF_EVAL_COST_BASIS_APPLIED) == ADAPTIVE_BASIS_UNKNOWN
    # ``undeclared`` = HAY neto sin base firmada: baja confianza declarada, no un ``UNKNOWN``.
    assert (
        _basis_transition("undeclared", SELF_EVAL_COST_BASIS_ESTIMATED)
        == ADAPTIVE_BASIS_DATA_DEGRADED
    )
    assert (
        _basis_transition("undeclared", "undeclared")
        == ADAPTIVE_BASIS_DATA_DEGRADED
    )


def test_mixed_and_transition_are_two_axes_of_the_same_population() -> None:
    """``MIXED`` es heterogeneidad INTERNA; ``TRANSITION`` es cambio TEMPORAL: ejes distintos.

    Una ventana puede mezclar bases (``MIXED``) o dos ventanas puras pueden diferir
    (``TRANSITION``). Son hechos distintos y ``BasisTransition`` los mantiene separados: colapsarlos
    esconderia si la poblacion no es homogenea o si cambio con el tiempo.
    """
    assert ADAPTIVE_BASIS_MIXED == BasisTransition.MIXED.value
    assert ADAPTIVE_BASIS_TRANSITION == BasisTransition.TRANSITION.value
    assert ADAPTIVE_BASIS_MIXED != ADAPTIVE_BASIS_TRANSITION
    # Interna: la MISMA ventana mezcla bases (una pura y un ``mixed``).
    assert _basis_transition("mixed", SELF_EVAL_COST_BASIS_ESTIMATED) == ADAPTIVE_BASIS_MIXED
    # Temporal: las dos ventanas son puras pero distintas.
    assert (
        _basis_transition(SELF_EVAL_COST_BASIS_ESTIMATED, SELF_EVAL_COST_BASIS_APPLIED)
        == ADAPTIVE_BASIS_TRANSITION
    )


def test_a_net_without_a_base_is_data_degraded_and_lowers_the_band() -> None:
    """AUTO-18 (§19): neto PRESENTE sin base ⇒ ``DATA_DEGRADED`` (baja confianza), no ``UNKNOWN``.

    No es el ``UNKNOWN`` inocuo (no hay neto): aquí el número existe pero nadie firmó el metro, así
    que la lectura se publica con la banda REBAJADA (30 ciclos darían ``MEDIUM``) y una nota propia,
    en vez de pasar por estable.
    """
    cycles = [
        _undeclared_cycle(index=index, closed_at=f"2026-09-{index:02d}T10:00:00+00:00")
        for index in range(1, 31)
    ]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_UNDECLARED, "hay neto: la base no es None"
    assert row.basis_transition == ADAPTIVE_BASIS_DATA_DEGRADED
    assert ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED in row.notes, "el hueco se nombra"
    assert row.confidence == ADAPTIVE_CONFIDENCE_LOW, "el neto sin metro se lee con baja confianza"


def test_no_net_at_all_is_the_benign_unknown_and_does_not_lower_the_band() -> None:
    """CONTROL: sin neto el estado es ``UNKNOWN`` (inocuo): no hay metro que firmar ni rebaja."""
    cycles = _dated(count=30, with_cost=False)
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.net_r_basis is None
    assert row.basis_transition == ADAPTIVE_BASIS_UNKNOWN
    assert ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED not in row.notes


def test_only_data_degraded_lowers_the_band_on_the_basis_axis() -> None:
    """PURA: de TODOS los estados de base, solo ``DATA_DEGRADED`` rebaja la banda.

    ``UNKNOWN`` (no hay neto) y ``MIXED``/``TRANSITION`` (población no homogénea) no son "baja
    confianza por falta de metro": tienen sus propios consumidores (el decay, el eje del reparto).
    El neto PRESENTE sin base sí se lee con menos confianza, y solo él.
    """
    common = {
        "measured_n": 60,
        "completeness": MEASUREMENT_COMPLETE,
        "decay": ADAPTIVE_DECAY_NONE,
    }
    assert _band(**common) == ADAPTIVE_CONFIDENCE_HIGH
    assert _band(**common, basis_transition=ADAPTIVE_BASIS_UNKNOWN) == ADAPTIVE_CONFIDENCE_HIGH
    assert _band(**common, basis_transition=ADAPTIVE_BASIS_MIXED) == ADAPTIVE_CONFIDENCE_HIGH
    assert (
        _band(**common, basis_transition=ADAPTIVE_BASIS_DATA_DEGRADED)
        == ADAPTIVE_CONFIDENCE_MEDIUM
    )


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


# ── AUTO-18 — el METRO del neto como segundo eje de la población ────────────────────


def test_the_cost_model_transition_is_its_own_state() -> None:
    """El detector declara el cambio de METRO, y no lo confunde con los otros dos ejes.

    Tres estados distintos, dos ejes: ``COST_MODEL_TRANSITION`` es el cambio TEMPORAL del metro
    con la base intacta; ``MIXED`` la heterogeneidad INTERNA de una ventana; ``UNKNOWN`` la
    ausencia que no se puede comparar. Y la MISMA ausencia de metro en las dos ventanas no es un
    cambio: sigue devolviendo los ``STABLE_*`` de ``AUTO-17`` (compatibilidad byte a byte).
    """
    estimated = SELF_EVAL_COST_BASIS_ESTIMATED
    assert (
        _basis_transition(
            estimated,
            estimated,
            long_cost_model="cm:bps:10/2/5/0",
            recent_cost_model="cm:bps:10/2/5/0",
        )
        == ADAPTIVE_BASIS_STABLE_ESTIMATED
    )
    assert (
        _basis_transition(
            estimated,
            estimated,
            long_cost_model="cm:bps:10/2/5/0",
            recent_cost_model="cm:preset:10/2/5/0",
        )
        == ADAPTIVE_BASIS_COST_MODEL_TRANSITION
    )
    # Una sola ventana declara el metro: no hay comparación y NO se afirma estabilidad.
    assert (
        _basis_transition(
            estimated, estimated, long_cost_model=None, recent_cost_model="cm:bps:10/2/5/0"
        )
        == ADAPTIVE_BASIS_UNKNOWN
    )
    # La MISMA ausencia en las dos ventanas (histórico pre-fase): ``AUTO-17`` intacto.
    assert (
        _basis_transition(
            estimated,
            estimated,
            long_cost_model="undeclared",
            recent_cost_model="undeclared",
        )
        == ADAPTIVE_BASIS_STABLE_ESTIMATED
    )
    # Heterogeneidad INTERNA del metro ⇒ ``MIXED`` (eje propio), no ``COST_MODEL_TRANSITION``.
    assert (
        _basis_transition(
            estimated,
            estimated,
            long_cost_model="mixed",
            recent_cost_model="cm:bps:10/2/5/0",
        )
        == ADAPTIVE_BASIS_MIXED
    )


def test_the_cost_model_transition_alone_blocks_the_decay() -> None:
    """PURA: con la MISMA base pero distinto metro, el deterioro no se mide.

    ``COST_MODEL_TRANSITION`` se declara en su propio eje y ``_decay`` lo bloquea igual que
    ``TRANSITION``/``MIXED``: un cambio de instrumento no puede leerse como caída del edge. Sin
    este bloqueo, un salto de ``+1 R`` a ``-1 R`` causado solo por otro modelo de coste encogería
    el peso como si el edge se hubiera roto.
    """
    assert (
        _decay(
            1.0,
            -1.0,
            recent_measured_n=30,
            min_trades=5,
            basis_transition=ADAPTIVE_BASIS_COST_MODEL_TRANSITION,
        )
        == ADAPTIVE_DECAY_UNKNOWN
    )
    # CONTROL: sin transición, la misma muestra y el mismo salto SÍ son deterioro severo.
    assert (
        _decay(
            1.0,
            -1.0,
            recent_measured_n=30,
            min_trades=5,
            basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        )
        == ADAPTIVE_DECAY_SEVERE
    )


def test_a_cost_model_change_separates_series_and_blocks_the_decay() -> None:
    """``AUTO-18``: el neto reciente sale distinto porque cambió el METRO, no el rendimiento.

    Misma base y misma dirección de la muestra: lo único que cambia entre la población vieja y la
    nueva es la versión del modelo de coste. La lectura declara la población heterogénea
    (``MIXED``: la ventana larga abarca las dos, y ``COST_MODEL_TRANSITION`` sería el caso puro de
    ventanas disjuntas), **separa** las series en vez de promediarlas, no publica pooled y NO
    interpreta el salto como deterioro (``decay = UNKNOWN``).
    """
    old = [
        _cycle_with_basis(
            "orb-1",
            index=i,
            basis="estimated",
            cost_model="cm:bps:10/2/5/0",
            closed_at=f"2026-09-{i:02d}T10:00:00+00:00",
            pnl="10",
        )
        for i in range(1, 31)
    ]
    new = [
        _cycle_with_basis(
            "orb-1",
            index=100 + i,
            basis="estimated",
            cost_model="cm:preset:10/2/5/0",
            closed_at=f"2026-10-{i:02d}T10:00:00+00:00",
            pnl="-10",
        )
        for i in range(1, 11)
    ]
    reading = build_adaptive_confidence(old + new, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_ESTIMATED, "la base NO cambió: el metro sí"
    assert row.basis_transition == ADAPTIVE_BASIS_MIXED
    assert row.decay == ADAPTIVE_DECAY_UNKNOWN, "un cambio de metro no es deterioro"
    assert len(row.net_r_series) == 2, "el cambio de metro SEPARA series, no las funde"
    assert {series.cost_model_version for series in row.net_r_series} == {
        "cm:bps:10/2/5/0",
        "cm:preset:10/2/5/0",
    }


def test_a_single_cost_model_keeps_the_historic_stability_and_decay() -> None:
    """CONTROL: un solo metro (y la misma base) ⇒ ``STABLE_*`` y el decay de siempre."""
    cycles = [
        _cycle_with_basis(
            "orb-1",
            index=i,
            basis="estimated",
            cost_model="cm:bps:10/2/5/0",
            closed_at=f"2026-09-{i:02d}T10:00:00+00:00",
            pnl="10",
        )
        for i in range(1, 31)
    ] + [
        _cycle_with_basis(
            "orb-1",
            index=100 + i,
            basis="estimated",
            cost_model="cm:bps:10/2/5/0",
            closed_at=f"2026-10-{i:02d}T10:00:00+00:00",
            pnl="-10",
        )
        for i in range(1, 11)
    ]
    reading = build_adaptive_confidence(cycles, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.basis_transition == ADAPTIVE_BASIS_STABLE_ESTIMATED
    assert row.decay == ADAPTIVE_DECAY_SEVERE
    assert len(row.net_r_series) == 1
    assert row.net_r_series[0].cost_model_version == "cm:bps:10/2/5/0"


# ── AUTO-18 — independencia: episodios, cobertura, calibración y encogimiento ──────


def _episode_series(count: int, *, version: str = "orb-1") -> list[dict[str, object]]:
    """``count`` ciclos MEDIDOS, uno por racha de régimen (alterno), en días distintos."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        _cycle(
            version,
            index=index,
            regime="TREND_UP" if index % 2 == 0 else "RANGE",
            closed_at=(base + timedelta(days=index)).isoformat(),
        )
        for index in range(count)
    ]


def _one_regime_series(count: int, *, regime: str = "TREND_UP") -> list[dict[str, object]]:
    """``count`` ciclos MEDIDOS del MISMO régimen, en días distintos (una sola racha)."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        _cycle(
            "orb-1",
            index=index,
            regime=regime,
            closed_at=(base + timedelta(days=index)).isoformat(),
        )
        for index in range(count)
    ]


def test_the_episodes_helper_counts_regime_runs_over_measured_cycles() -> None:
    """(PURA) una racha se corta al cambiar el régimen; ``UNKNOWN`` es su propio valor."""
    rows = (
        _dated(count=2, regime="TREND_UP")
        + _dated(count=2, regime="UNKNOWN", first_day=4, index_offset=100)
        + _dated(count=2, regime="TREND_UP", first_day=7, index_offset=200)
    )
    assert _episodes(rows)["orb-1"] == {"TREND_UP": 2, "UNKNOWN": 1}


def test_effective_n_counts_regime_episodes_not_cycles() -> None:
    rows = (
        _dated(count=3, regime="TREND_UP")
        + _dated(count=3, regime="RANGE", first_day=4, index_offset=100)
        + _dated(count=3, regime="TREND_UP", first_day=7, index_offset=200)
    )
    reading = build_adaptive_confidence(rows, recent_window=3, long_window=200, min_trades=3)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.measured_n == 9
    assert row.episodes == 3, "UP -> RANGE -> UP son tres fases de mercado"
    assert row.effective_n == 3
    assert row.coverage == ADAPTIVE_COVERAGE_LOW


def test_consecutive_cycles_of_one_regime_are_a_single_episode() -> None:
    rows = _dated(count=6, regime="TREND_UP")
    reading = build_adaptive_confidence(rows, recent_window=3, long_window=200, min_trades=3)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.measured_n == 6
    assert row.episodes == 1, "seis ciclos de la misma fase son UNA observacion independiente"
    assert row.effective_n == 1
    assert ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT in row.notes


def test_the_episode_count_is_order_invariant() -> None:
    rows = (
        _dated(count=3, regime="TREND_UP")
        + _dated(count=3, regime="RANGE", first_day=4, index_offset=100)
        + _dated(count=3, regime="TREND_UP", first_day=7, index_offset=200)
    )
    first = build_adaptive_confidence(rows, recent_window=3, long_window=200, min_trades=3)
    second = build_adaptive_confidence(
        list(reversed(rows)), recent_window=3, long_window=200, min_trades=3
    )
    assert first.as_dict() == second.as_dict()


def test_the_coverage_is_its_own_axis_and_does_not_move_the_band() -> None:
    """Un solo régimen: medida impecable (``HIGH``) pero una sola fase (``LOW``)."""
    rows = _one_regime_series(60)
    reading = build_adaptive_confidence(rows, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.confidence == ADAPTIVE_CONFIDENCE_HIGH, "la banda mide la CALIDAD de la medicion"
    assert row.measured_n == 60
    assert row.episodes == 1
    assert row.coverage == ADAPTIVE_COVERAGE_LOW, "la cobertura mide la INDEPENDENCIA"
    assert row.by_regime[0].confidence == ADAPTIVE_CONFIDENCE_HIGH
    assert row.by_regime[0].coverage == ADAPTIVE_COVERAGE_LOW


def test_a_cell_without_measured_risk_is_declared_uncovered() -> None:
    rows = _dated(count=10, with_risk=False)
    reading = build_adaptive_confidence(rows, recent_window=5, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.measured_n == 0
    assert row.episodes == 0
    assert row.effective_n == 0
    assert row.coverage == ADAPTIVE_COVERAGE_UNCOVERED


def test_the_coverage_bands_follow_the_effective_sample() -> None:
    medium = build_adaptive_confidence(
        _episode_series(25), recent_window=10, long_window=200, min_trades=5
    ).confidence_for("orb-1")
    high = build_adaptive_confidence(
        _episode_series(50), recent_window=10, long_window=200, min_trades=5
    ).confidence_for("orb-1")

    assert medium is not None and medium.coverage == ADAPTIVE_COVERAGE_MEDIUM
    assert high is not None and high.coverage == ADAPTIVE_COVERAGE_HIGH


def test_the_shrunk_expectancy_is_published_and_only_shrinks() -> None:
    rows = _episode_series(25)
    reading = build_adaptive_confidence(rows, recent_window=10, long_window=200, min_trades=5)
    row = reading.confidence_for("orb-1")

    assert row is not None
    assert row.long_expectancy_r is not None and row.long_expectancy_r > 0
    assert row.effective_n == 25
    expected = round(row.long_expectancy_r * 25 / (25 + ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT), 4)
    assert row.shrunk_expectancy_r == pytest.approx(expected)
    assert row.shrunk_expectancy_r < row.long_expectancy_r
    assert row.by_regime[0].shrunk_expectancy_r is not None
    assert row.by_regime[0].shrunk_expectancy_r < row.by_regime[0].long_expectancy_r  # type: ignore[operator]


def test_the_shrunk_helper_declares_absence_instead_of_zero() -> None:
    assert _shrunk(None, 10, 20.0) is None
    assert _shrunk(0.5, 0, 20.0) is None, "sin muestra efectiva no hay numero que encoger"
    assert _shrunk(0.5, 20, 20.0) == pytest.approx(0.25)


def test_the_calibration_table_describes_the_bands_without_moving_them() -> None:
    rows = _episode_series(50)
    reading = build_adaptive_confidence(rows, recent_window=10, long_window=200, min_trades=5)
    payload = reading.as_dict()

    assert payload["calibration"], "la tabla descriptiva se publica por banda presente"
    entry = next(
        item
        for item in payload["calibration"]
        if item["level"] == ADAPTIVE_CONFIDENCE_MEDIUM
    )
    assert entry["cells"] == 2, "dos celdas (TREND_UP y RANGE)"
    assert entry["promisedMinN"] == 20
    assert entry["observedMinN"] >= entry["promisedMinN"]
    assert entry["reliable"] is True
    assert entry["observedExpectancyR"] is not None
    assert entry["measuredN"] == 50 and entry["effectiveN"] == 50
    # Read-only: la banda publicada no se mueve por publicar su calibracion.
    row = reading.confidence_for("orb-1")
    assert row is not None
    assert all(cell.confidence == ADAPTIVE_CONFIDENCE_MEDIUM for cell in row.by_regime)


def test_the_calibration_omits_bands_without_cells() -> None:
    reading = build_adaptive_confidence(
        _dated(count=3), recent_window=2, long_window=200, min_trades=3
    )
    assert [row.level for row in reading.calibration] == [ADAPTIVE_CONFIDENCE_LOW]
    assert reading.calibration[0].promised_min_n == 0
    assert reading.calibration[0].reliable is True


def test_no_cycles_publishes_an_empty_calibration_with_the_empty_reading() -> None:
    reading = build_adaptive_confidence([])

    assert reading.calibration == ()
    assert reading.as_dict()["calibration"] == []
