"""AUTO-7 — tests de la autoevaluación pura por ``strategyVersion`` (read-only).

Se verifica lo que hace útil al módulo: que agregue de verdad por versión y que **declare
sus huecos** en vez de rellenarlos. Los casos límite son el punto: embudo abierto sin
medición, motivo ausente, precio ausente, ciclo repetido, ciclo sin identidad y ciclo sin
versión. Ninguno de ellos puede convertirse en un ``0`` silencioso.

Además (``AUTO-9``, paso 3 del plan ``v2.50``) cubre el R **por ciclo** — ``pnl /
reserved_risk`` y el neto descontando el coste estimado — con el mismo criterio: sin riesgo
no hay R (ni ``0`` ni ``inf``), sin coste no hay neto (un coste ausente **no** es coste
cero) y un resultado plano medido (``pnl = 0``) **sí** es una medida.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.auto_self_evaluation import (
    AUTO_SELF_EVALUATION_KEY,
    SELF_EVAL_COST_UNMEASURED,
    SELF_EVAL_CYCLE_WITHOUT_IDENTITY,
    SELF_EVAL_DRAWDOWN_SHARE_PROXY,
    SELF_EVAL_DUPLICATE_CYCLE,
    SELF_EVAL_FUNNEL_DURABLE_MISMATCH,
    SELF_EVAL_FUNNEL_NOT_DIMENSIONED,
    SELF_EVAL_FUNNEL_SEEN_MISMATCH,
    SELF_EVAL_FUNNEL_UNBALANCED,
    SELF_EVAL_FUNNEL_UNKNOWN,
    SELF_EVAL_MISSING_INPUTS,
    SELF_EVAL_OPPORTUNITY_STATUS_UNKNOWN,
    SELF_EVAL_PNL_UNMEASURED,
    SELF_EVAL_REGIME_UNDETERMINED,
    SELF_EVAL_REGIME_UNKNOWN,
    SELF_EVAL_REJECTION_COST_UNMEASURED,
    SELF_EVAL_REJECTION_WITHOUT_REASON,
    SELF_EVAL_RISK_UNMEASURED,
    SELF_EVAL_SLIPPAGE_UNMEASURED,
    SELF_EVAL_THIN_SAMPLE,
    SELF_EVAL_UNVERSIONED_CYCLE,
    aggregate_by_regime,
    cycle_r,
    declared_regime,
    evaluate_auto_self_evaluation,
    single_decisive_regime,
)


def _cycle(
    version: str = "orb-1",
    *,
    pnl: str | None = "100",
    cycle_id: str | None = None,
    closed_at: str | None = None,
    r: float | None = None,
    mfe: float | None = None,
    mae: float | None = None,
    slippage: str | None = None,
    regime: str | None = None,
    risk: str | None = None,
    cost: object | None = None,
) -> dict[str, object]:
    """Ciclo mínimo con SOLO lo que el test declara (el resto queda ausente)."""
    row: dict[str, object] = {"strategyVersion": version}
    if pnl is not None:
        row["pnl"] = pnl
    if cycle_id is not None:
        row["cycleId"] = cycle_id
    if closed_at is not None:
        row["closedAt"] = closed_at
    if r is not None:
        row["rMultiple"] = r
    if mfe is not None or mae is not None:
        row["mfeMae"] = {"mfeR": mfe, "maeR": mae}
    if slippage is not None:
        row["slippageCurrency"] = slippage
    if regime is not None:
        row["marketRegime"] = regime
    if risk is not None:
        row["reservedRisk"] = risk
    if cost is not None:
        row["cost"] = cost
    return row


@dataclass(frozen=True, slots=True)
class _CycleObject:
    """Variante objeto del mismo contrato (dominio, no payload): el módulo la acepta."""

    strategy_version_id: str
    realized_pnl: str
    cycle_id: str | None = None
    r_multiple: float | None = None


# ── Agregación por estrategia ───────────────────────────────────────────────────────


def test_aggregates_results_and_cost_metrics_per_strategy_version() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="120", cycle_id="c1", r=1.2, mfe=1.5, mae=0.4, slippage="3"),
            _cycle(pnl="-80", cycle_id="c2", r=-0.8, mfe=0.3, mae=1.0, slippage="2"),
            _cycle("meanrev-2", pnl="-30", cycle_id="c3", r=-0.3),
        ]
    )

    assert [row.strategy_version for row in report.by_strategy] == ["meanrev-2", "orb-1"]
    orb = next(row for row in report.by_strategy if row.strategy_version == "orb-1")

    assert orb.trades == 2
    assert orb.wins == 1 and orb.losses == 1
    assert orb.realized_pnl == 40
    assert orb.expectancy_currency == 20
    assert orb.expectancy_r == pytest.approx(0.2)
    assert orb.win_rate == pytest.approx(0.5)
    assert orb.profit_factor == pytest.approx(1.5)
    assert orb.avg_win_currency == 120
    assert orb.avg_loss_currency == 80
    assert orb.mfe_r == pytest.approx(0.9)
    assert orb.mae_r == pytest.approx(0.7)
    assert orb.slippage_currency == 5
    assert orb.drawdown_currency == 80
    assert orb.results_measurement == "COMPLETE"
    assert report.trades == 3
    assert report.realized_pnl == 10
    assert report.read_only is True


def test_profit_factor_is_undefined_without_losses_and_breakeven_is_not_a_win() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="50", cycle_id="c1"), _cycle(pnl="0", cycle_id="c2")]
    )

    row = report.by_strategy[0]
    assert row.profit_factor is None, "sin pérdidas el ratio es indefinido, no infinito"
    assert (row.wins, row.losses, row.trades) == (1, 0, 2)
    assert row.win_rate == pytest.approx(0.5), "el breakeven no es una ganadora"


def test_drawdown_share_is_declared_as_an_additive_proxy() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1", closed_at="2026-09-15T10:00:00Z"),
            _cycle(pnl="-80", cycle_id="c2", closed_at="2026-09-15T11:00:00Z"),
            _cycle("meanrev-2", pnl="-30", cycle_id="c3", closed_at="2026-09-15T12:00:00Z"),
        ]
    )

    shares = {row.strategy_version: row.drawdown_share for row in report.by_strategy}
    assert shares == {"orb-1": 0.7273, "meanrev-2": 0.2727}
    assert SELF_EVAL_DRAWDOWN_SHARE_PROXY in report.notes
    assert report.drawdown_currency == 110, (
        "curva del informe en orden de cierre: 100 → 20 → -10 ⇒ caída de 110"
    )


def test_accepts_domain_objects_with_snake_case_fields() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _CycleObject("orb-1", "120", cycle_id="c1", r_multiple=1.2),
            _CycleObject("orb-1", "-80", cycle_id="c2", r_multiple=-0.8),
        ]
    )

    row = report.by_strategy[0]
    assert row.realized_pnl == 40
    assert row.expectancy_r == pytest.approx(0.2)


# ── Embudo: cierra solo cuando está medido ──────────────────────────────────────────


def test_funnel_closes_only_when_every_state_is_catalogued_and_counted() -> None:
    report = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "traded", "strategy_version": "orb-1"},
            {"status": "rejected", "reason": "top_n_excluded", "strategyVersion": "orb-1"},
            {"status": "expired", "reason": "no_fill"},
        ],
        seen=3,
        durable_seen=3,
    )

    assert report.funnel_closed is True
    assert (report.seen, report.traded, report.rejected, report.expired, report.missed) == (
        3,
        1,
        1,
        1,
        0,
    )
    assert report.rejection_reasons == (("top_n_excluded", 1),)
    assert report.errors == ()


def test_funnel_stays_open_without_opportunities_instead_of_an_invented_zero() -> None:
    report = evaluate_auto_self_evaluation(cycles=[_cycle(cycle_id="c1")])

    assert report.funnel_closed is False
    assert report.seen is None, "no medir no es un 0"
    assert (report.traded, report.rejected, report.expired, report.missed) == (
        None,
        None,
        None,
        None,
    )
    assert SELF_EVAL_FUNNEL_UNKNOWN in report.notes
    assert report.funnel_measurement == "UNKNOWN"
    assert report.measurement != "COMPLETE"


def test_funnel_declares_declared_seen_and_durable_seen_mismatches() -> None:
    mismatched = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "traded", "strategy_version": "orb-1"},
            {"status": "rejected", "reason": "top_n_excluded"},
        ],
        seen=5,
        durable_seen=7,
    )

    assert SELF_EVAL_FUNNEL_SEEN_MISMATCH in mismatched.errors
    assert SELF_EVAL_FUNNEL_DURABLE_MISMATCH in mismatched.errors
    assert SELF_EVAL_FUNNEL_UNBALANCED in mismatched.errors
    assert mismatched.funnel_closed is False


def test_unknown_status_and_rejection_without_reason_leave_the_funnel_open() -> None:
    report = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "traded", "strategy_version": "orb-1"},
            {"status": "wishful", "reason": "?"},
            {"status": "rejected"},
        ]
    )

    assert SELF_EVAL_OPPORTUNITY_STATUS_UNKNOWN in report.errors
    assert SELF_EVAL_REJECTION_WITHOUT_REASON in report.errors
    assert report.funnel_closed is False
    assert report.seen == 3, "la fila no catalogada no desaparece: deja el embudo abierto"


def test_rejection_cost_is_measured_only_with_both_prices() -> None:
    measured = evaluate_auto_self_evaluation(
        opportunities=[
            {
                "status": "rejected",
                "reason": "top_n_excluded",
                "strategy_version": "orb-1",
                "reference_price": 100,
                "subsequent_price": 103,
            }
        ],
        seen=1,
    )
    assert measured.opportunity_cost_return == pytest.approx(0.03)
    assert measured.opportunity_cost_measurement == "COMPLETE"
    assert measured.by_strategy[0].rejection_cost_return == pytest.approx(0.03)
    assert SELF_EVAL_REJECTION_COST_UNMEASURED not in measured.notes

    unmeasured = evaluate_auto_self_evaluation(
        opportunities=[{"status": "rejected", "reason": "top_n_excluded", "reference_price": 100}],
        seen=1,
    )
    assert unmeasured.opportunity_cost_return is None, "sin precio posterior no hay coste"
    assert unmeasured.opportunity_cost_measurement == "UNKNOWN"
    assert SELF_EVAL_REJECTION_COST_UNMEASURED in unmeasured.notes


# ── Identidad, unicidad y atribución ────────────────────────────────────────────────


def test_a_repeated_cycle_is_counted_once_and_declared() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1"),
            _cycle(pnl="100", cycle_id="c1"),
        ]
    )

    assert report.cycles == 1
    assert report.duplicate_cycles == 1
    assert report.realized_pnl == 100, "un doble conteo mentiría igual que un doble fill"
    assert SELF_EVAL_DUPLICATE_CYCLE in report.errors
    assert report.decisive is False


def test_cycles_without_identity_are_counted_and_declared_not_collapsed() -> None:
    report = evaluate_auto_self_evaluation(cycles=[_cycle(pnl="10"), _cycle(pnl="20")])

    assert report.cycles == 2, "sin identidad no se puede deduplicar: son dos"
    assert report.cycles_without_identity == 2
    assert report.duplicate_cycles == 0
    assert SELF_EVAL_CYCLE_WITHOUT_IDENTITY in report.notes


def test_unversioned_cycles_are_not_spread_across_strategies() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1"),
            _cycle("", pnl="50", cycle_id="c2"),
        ]
    )

    assert report.trades == 1, "solo el ciclo atribuible entra en el roll-up"
    assert report.unattributed_cycles == 1
    assert report.unattributed_pnl == 50
    assert report.realized_pnl == 100
    assert [row.strategy_version for row in report.by_strategy] == ["orb-1"]
    assert SELF_EVAL_UNVERSIONED_CYCLE in report.notes


# ── Muestras, huecos declarados y contrato de lectura ──────────────────────────────


def test_thin_sample_is_declared_and_blocks_the_decisive_flag() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id=f"c{i}") for i in range(9)],
        min_trades=10,
    )

    assert SELF_EVAL_THIN_SAMPLE in report.notes
    assert report.by_strategy[0].sample_quality == "insufficient"
    assert report.decisive is False

    enough = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id=f"c{i}") for i in range(10)],
        min_trades=10,
    )
    assert enough.decisive is True
    assert enough.by_strategy[0].sample_quality == "insufficient", (
        "10 ciclos siguen siendo muestra escasa para concluir (bandas de honestidad)"
    )
    useful = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id=f"c{i}") for i in range(20)],
        min_trades=10,
    )
    assert useful.by_strategy[0].sample_quality == "preliminary"


def test_missing_risk_and_slippage_are_declared_with_their_own_measurement() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id="c1"), _cycle(pnl="-5", cycle_id="c2")]
    )

    row = report.by_strategy[0]
    assert row.expectancy_r is None
    assert row.risk_measurement == "UNKNOWN"
    assert row.slippage_measurement == "UNKNOWN"
    assert SELF_EVAL_RISK_UNMEASURED in report.notes
    assert SELF_EVAL_SLIPPAGE_UNMEASURED in report.notes
    assert report.results_measurement == "COMPLETE", "el resultado SÍ se midió"
    assert report.measurement == "UNKNOWN", (
        "el agregado es tan fiable como su bloque menos fiable: aquí faltan R, "
        "excursiones, slippage y el embudo"
    )


def test_an_empty_report_is_unknown_not_complete() -> None:
    report = evaluate_auto_self_evaluation()

    assert report.cycles == 0
    assert report.results_measurement == "UNKNOWN"
    assert report.measurement == "UNKNOWN"
    assert report.decisive is False
    assert report.funnel_closed is False
    assert SELF_EVAL_MISSING_INPUTS in report.notes


def test_as_dict_is_serializable_and_declares_read_only() -> None:
    import json

    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id="c1", r=1.0)],
        opportunities=[{"status": "traded", "strategy_version": "orb-1"}],
        seen=1,
    )
    payload = report.as_dict()

    assert payload["key"] == AUTO_SELF_EVALUATION_KEY
    assert payload["readOnly"] is True
    assert payload["byStrategy"][0]["strategyVersion"] == "orb-1"
    assert payload["byStrategy"][0]["decisive"] is False
    assert json.loads(json.dumps(payload))["funnel"]["closed"] is True


# ── AUTO-9 — el R de un ciclo (paso 3 del plan `v2.50`) ─────────────────────────────


def _cost(total: float | None = 12.5) -> dict[str, object]:
    """Un ``TradingCost.to_dict()`` mínimo: solo lo que el cálculo del R necesita."""
    return {"total": total, "measurement": "COMPLETE" if total is not None else "PARTIAL"}


def test_cycle_r_is_the_pnl_over_the_committed_risk_and_net_discounts_the_cost() -> None:
    measured = cycle_r(pnl="200", risk_amount="100", cost=_cost(12.5))

    assert measured.r_multiple == pytest.approx(2.0)
    assert measured.net_r_multiple == pytest.approx((200.0 - 12.5) / 100.0)
    assert measured.risk_amount == 100
    assert measured.cost_estimate == pytest.approx(12.5)
    assert measured.measurement == "COMPLETE"
    assert measured.notes == ()


def test_cycle_r_never_invents_a_zero_or_an_infinity_without_risk() -> None:
    """Sin denominador no hay R: ni ``0`` (afirmaría "no pasó nada") ni ``inf`` (gratis)."""
    for missing in (None, "0", "0.0", "-100"):
        row = cycle_r(pnl="200", risk_amount=missing, cost=_cost(12.5))
        assert row.r_multiple is None, missing
        assert row.net_r_multiple is None, missing
        assert row.measurement == "UNKNOWN", missing
        assert SELF_EVAL_RISK_UNMEASURED in row.notes, missing


def test_cycle_r_declares_the_missing_cost_instead_of_gifting_r() -> None:
    """Coste ausente o **incompleto** ⇒ el neto no se mide; el bruto sí."""
    for absent in (None, {}, {"total": None, "measurement": "PARTIAL"}, "no-soy-un-coste"):
        row = cycle_r(pnl="200", risk_amount="100", cost=absent)
        assert row.r_multiple == pytest.approx(2.0), absent
        assert row.net_r_multiple is None, absent
        assert row.cost_estimate is None, absent
        assert row.measurement == "PARTIAL", absent
        assert SELF_EVAL_COST_UNMEASURED in row.notes, absent


def test_cycle_r_without_pnl_does_not_even_ask_for_the_cost() -> None:
    row = cycle_r(pnl=None, risk_amount="100", cost=_cost(1.0))

    assert row.r_multiple is None
    assert row.net_r_multiple is None
    assert row.measurement == "UNKNOWN"
    assert SELF_EVAL_PNL_UNMEASURED in row.notes
    assert SELF_EVAL_COST_UNMEASURED not in row.notes, (
        "sin PnL la pregunta del coste no se plantea: declararla sería ruido"
    )


def test_a_measured_flat_result_is_zero_point_zero_and_not_a_gap() -> None:
    """``pnl = 0`` medido es ``0.0`` (``COMPLETE``); un hueco no se disfraza de cero."""
    row = cycle_r(pnl="0", risk_amount="100", cost=_cost(0.0))

    assert row.r_multiple == 0.0
    assert row.net_r_multiple == 0.0
    assert row.measurement == "COMPLETE"
    assert row.notes == ()


def test_cycle_r_rounds_to_four_decimals_like_the_rest_of_the_module() -> None:
    row = cycle_r(pnl="100", risk_amount="3", cost=_cost(0.0))

    assert row.r_multiple == pytest.approx(33.3333)
    assert row.net_r_multiple == pytest.approx(33.3333)


def test_cycle_r_accepts_a_rebuilt_cost_and_its_serialized_form_alike() -> None:
    """El round-trip del coste no cambia el R: la forma serializada es la misma medida."""
    from bolsa_analytics.cognitive.portfolio_reservation import TradingCost, coerce_trading_cost

    serialized = _cost(12.5)
    rebuilt = coerce_trading_cost(serialized)
    assert rebuilt is not None

    expected = cycle_r(pnl="200", risk_amount="100", cost=TradingCost(total=12.5))
    assert cycle_r(pnl="200", risk_amount="100", cost=serialized) == expected
    assert cycle_r(pnl="200", risk_amount="100", cost=rebuilt) == expected


def test_cycle_r_as_dict_publishes_the_trace_of_the_division() -> None:
    import json

    payload = cycle_r(pnl="200", risk_amount="100").as_dict()

    assert payload["rMultiple"] == pytest.approx(2.0)
    assert payload["netRMultiple"] is None
    assert payload["riskAmount"] == "100"
    assert payload["costEstimate"] is None
    assert payload["measurement"] == "PARTIAL"
    assert payload["notes"] == [SELF_EVAL_COST_UNMEASURED]
    assert json.loads(json.dumps(payload))["riskAmount"] == "100"


# ── AUTO-9 — el cruce strategy × regime (paso 4 del plan `v2.50`) ────────────────────


def _regime_cycles(regime: str | None, count: int, *, tag: str) -> list[dict[str, object]]:
    """``count`` ciclos medidos (con R) de un mismo régimen, con identidades distintas."""
    return [_cycle(pnl="10", cycle_id=f"{tag}{i}", regime=regime, r=1.0) for i in range(count)]


def test_one_strategy_is_split_into_its_regimes_and_the_totals_stay_exact() -> None:
    """El cruce **no reparte**: cada celda es un subconjunto y la suma vuelve a la fila."""
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1", regime="trend_up", r=1.0),
            _cycle(pnl="-40", cycle_id="c2", regime="trend_up", r=-0.4),
            _cycle(pnl="70", cycle_id="c3", regime="range", r=0.7),
            _cycle(pnl="-10", cycle_id="c4", regime="range", r=-0.1),
            _cycle(pnl="5", cycle_id="c5", regime="high_vol", r=0.05),
        ],
        min_trades=1,
    )

    cells = {cell.regime: cell for cell in report.by_regime}
    assert set(cells) == {"trend_up", "range", "high_vol"}
    assert cells["trend_up"].cycles == 2
    assert cells["trend_up"].realized_pnl == Decimal("60")
    assert cells["trend_up"].expectancy_r == pytest.approx(0.3)
    assert cells["range"].cycles == 2
    assert cells["high_vol"].cycles == 1

    row = report.by_strategy[0]
    assert sum(cell.cycles for cell in report.by_regime) == row.trades
    assert sum(cell.realized_pnl for cell in report.by_regime) == row.realized_pnl
    assert sum(cell.wins for cell in report.by_regime) == row.wins
    assert sum(cell.losses for cell in report.by_regime) == row.losses


def test_a_cycle_without_regime_goes_to_its_own_bucket_and_is_never_reassigned() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1", regime="trend_up", r=1.0),
            _cycle(pnl="50", cycle_id="c2", r=0.5),
        ],
        min_trades=1,
    )

    cells = {cell.regime: cell for cell in report.by_regime}
    assert set(cells) == {"trend_up", SELF_EVAL_REGIME_UNKNOWN}
    assert cells["trend_up"].cycles == 1, "el ciclo sin régimen NO engorda el declarado"
    assert cells[SELF_EVAL_REGIME_UNKNOWN].cycles == 1
    assert cells[SELF_EVAL_REGIME_UNKNOWN].realized_pnl == Decimal("50")
    assert report.cycles_without_regime == 1


def test_the_absent_regime_is_one_bucket_whatever_its_spelling() -> None:
    """``None``, ausente y ``unknown`` en cualquier caja: el MISMO cubo, no cuatro."""
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="10", cycle_id="c1"),
            _cycle(pnl="10", cycle_id="c2", regime="unknown"),
            _cycle(pnl="10", cycle_id="c3", regime="UNKNOWN"),
            _cycle(pnl="10", cycle_id="c4", regime="Unknown"),
        ],
        min_trades=1,
    )

    assert len(report.by_regime) == 1
    assert report.by_regime[0].regime == SELF_EVAL_REGIME_UNKNOWN
    assert report.by_regime[0].cycles == 4
    assert report.cycles_without_regime == 4


def test_the_cross_computes_the_r_from_the_raw_cycle_material_when_it_is_not_declared() -> None:
    """El cruce sirve al productor del ``v2.50``, que solo tiene el material en crudo."""
    cell = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="200", cycle_id="c1", regime="trend_up", risk="100", cost=_cost(12.5))],
        min_trades=1,
    ).by_regime[0]

    assert cell.expectancy_r == pytest.approx(2.0)
    assert cell.net_expectancy_r == pytest.approx(1.875)
    assert cell.decisive is True


def test_a_declared_r_wins_over_the_computed_one() -> None:
    """Si el productor ya midió el R, el cruce no lo recalcula por su cuenta."""
    cell = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="200", cycle_id="c1", regime="trend_up", r=9.99, risk="100")],
        min_trades=1,
    ).by_regime[0]

    assert cell.expectancy_r == pytest.approx(9.99)


def test_a_regime_cell_below_min_trades_is_not_decisive_even_if_the_strategy_is() -> None:
    """``min_trades`` es POR CELDA: 30 ciclos no hacen decisoria una celda de 5."""
    report = evaluate_auto_self_evaluation(
        cycles=[*_regime_cycles("trend_up", 25, tag="t"), *_regime_cycles("range", 5, tag="r")],
        min_trades=10,
    )

    cells = {cell.regime: cell for cell in report.by_regime}
    assert report.by_strategy[0].decisive is True, "el agregado sí alcanza la muestra"
    assert cells["trend_up"].decisive is True
    assert cells["range"].cycles == 5
    assert cells["range"].decisive is False


def test_a_regime_cell_with_any_cycle_without_r_is_not_decisive() -> None:
    """Una celda decisoria exige el R medido en TODOS sus ciclos, no en la mayoría."""
    complete = _regime_cycles("trend_up", 10, tag="c")
    assert evaluate_auto_self_evaluation(cycles=complete, min_trades=10).by_regime[0].decisive

    with_gap = [
        *complete[:-1],
        _cycle(pnl="10", cycle_id="c9", regime="trend_up"),
    ]
    cell = evaluate_auto_self_evaluation(cycles=with_gap, min_trades=10).by_regime[0]

    assert cell.cycles == 10, "el ciclo sin R cuenta como ciclo, no como hueco de muestra"
    assert cell.cycles_without_risk == 1
    assert cell.r_measurement == "PARTIAL"
    assert cell.decisive is False


def test_a_regime_cell_declares_the_net_expectancy_unmeasured_when_the_cost_is_missing() -> None:
    """Sin coste en un ciclo, el neto NO se rellena: promedia lo medido y declara el hueco.

    El bruto cubre 2 ciclos y el neto solo 1, así que los dos números **no son comparables**.
    Por eso la celda publica ``netRMeasurement == PARTIAL`` y ``cyclesWithoutCost``: quien
    lea ``net_expectancy_r`` **tiene** que pasar por esa medida (``decisive`` no la cubre).
    """
    cell = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="200", cycle_id="c1", regime="trend_up", risk="100", cost=_cost(12.5)),
            _cycle(pnl="100", cycle_id="c2", regime="trend_up", risk="100"),
        ],
        min_trades=1,
    ).by_regime[0]

    assert cell.expectancy_r == pytest.approx(1.5), "el bruto sí cubre los dos ciclos"
    assert cell.net_expectancy_r == pytest.approx(1.875), "el neto solo cubre uno"
    assert cell.net_r_measurement == "PARTIAL"
    assert cell.cycles_without_cost == 1
    assert SELF_EVAL_COST_UNMEASURED in cell.notes
    assert cell.decisive is True, "el R BRUTO sí está medido en los dos ciclos"


def test_the_cross_declares_that_the_funnel_is_not_dimensioned_by_regime() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id="c1", regime="trend_up", r=1.0)],
        opportunities=[{"status": "traded", "strategy_version": "orb-1"}],
        seen=1,
        min_trades=1,
    )

    assert SELF_EVAL_FUNNEL_NOT_DIMENSIONED in report.notes
    assert "funnel" not in report.by_regime[0].as_dict()
    assert report.by_strategy[0].as_dict()["funnel"]["traded"] == 1, (
        "el embudo sigue donde SÍ está medido; el cruce no se lo apropia"
    )
    assert report.funnel_closed is True


def test_the_cross_is_order_independent_and_never_counts_a_duplicate_twice() -> None:
    cycles = [
        _cycle(pnl="10", cycle_id="a", regime="trend_up", r=1.0),
        _cycle(pnl="20", cycle_id="b", regime="range", r=2.0),
        _cycle(pnl="-5", cycle_id="c", regime="trend_up", r=-0.5),
        _cycle(pnl="7", cycle_id="d", r=0.7),
    ]

    forward = evaluate_auto_self_evaluation(cycles=cycles, min_trades=1).as_dict()
    backward = evaluate_auto_self_evaluation(cycles=list(reversed(cycles)), min_trades=1).as_dict()
    assert forward["byRegime"] == backward["byRegime"]

    repeated = evaluate_auto_self_evaluation(
        cycles=[*cycles, _cycle(pnl="999", cycle_id="a", regime="trend_up", r=9.0)],
        min_trades=1,
    )
    cell = {row.regime: row for row in repeated.by_regime}["trend_up"]
    assert cell.cycles == 2
    assert cell.realized_pnl == Decimal("5"), "el duplicado se declara, no se suma"


def test_the_cross_is_empty_when_no_cycle_is_attributable() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(version="", pnl="10", cycle_id="c1", regime="trend_up")],
        min_trades=1,
    )

    assert report.by_regime == ()
    assert report.cycles_without_regime == 0
    assert SELF_EVAL_FUNNEL_NOT_DIMENSIONED not in report.notes
    assert report.unattributed_cycles == 1


def test_a_regime_is_only_published_when_it_is_unique_and_decisive() -> None:
    """El régimen se publica con su hueco al lado: o uno, o el motivo de no tenerlo."""
    cells = aggregate_by_regime(
        [*_regime_cycles("trend_up", 10, tag="a"), *_regime_cycles("range", 4, tag="b")],
        min_trades=10,
    )

    assert single_decisive_regime(cells, "orb-1") == "trend_up"
    assert declared_regime(cells, "orb-1") == ("trend_up", None)
    assert declared_regime(cells, "otra-version") == (None, SELF_EVAL_REGIME_UNDETERMINED)

    two_decisive = aggregate_by_regime(
        [*_regime_cycles("trend_up", 10, tag="a"), *_regime_cycles("range", 10, tag="b")],
        min_trades=10,
    )
    assert declared_regime(two_decisive, "orb-1") == (None, SELF_EVAL_REGIME_UNDETERMINED), (
        "con dos regímenes decisivos el régimen NO está determinado: no se elige uno"
    )

    only_unknown = aggregate_by_regime(_regime_cycles(None, 10, tag="u"), min_trades=10)
    assert only_unknown[0].decisive is True
    assert declared_regime(only_unknown, "orb-1") == (None, SELF_EVAL_REGIME_UNDETERMINED), (
        "UNKNOWN decisiva NO asciende a régimen: sigue significando 'no se midió'"
    )


def test_the_regime_cross_is_serializable_and_read_only() -> None:
    import json

    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id="c1", regime="trend_up", r=1.0)], min_trades=1
    )
    payload = report.as_dict()

    assert payload["readOnly"] is True
    assert payload["cyclesWithoutRegime"] == 0
    cell = payload["byRegime"][0]
    assert cell["regime"] == "trend_up"
    assert cell["netExpectancyR"] is None
    assert json.loads(json.dumps(payload))["byRegime"] == payload["byRegime"]


def test_the_strategy_row_publishes_the_net_expectancy_with_its_own_measurement() -> None:
    """El R neto agregado por estrategia, con la cobertura que lo respalda (paso 5)."""
    row = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="200", cycle_id="c1", risk="100", cost=_cost(12.5)),
            _cycle(pnl="100", cycle_id="c2", risk="100"),
        ],
        min_trades=1,
    ).by_strategy[0]

    assert row.expectancy_r == pytest.approx(1.5), "el bruto cubre los dos ciclos"
    assert row.net_expectancy_r == pytest.approx(1.875), "el neto solo cubre uno"
    assert row.net_r_measurement == "PARTIAL"
    assert row.cycles_without_cost == 1
    assert SELF_EVAL_COST_UNMEASURED in row.notes

    payload = row.as_dict()
    assert payload["netExpectancyR"] == pytest.approx(1.875)
    assert payload["netRMeasurement"] == "PARTIAL"
    assert payload["cyclesWithoutCost"] == 1
