"""AUTO-4 / V2.44 — optimizador de cartera (`portfolio_optimizer.py`).

El invariante que estos tests defienden: **el ranking no es la decisión**. La cartera elige
la COMBINACIÓN que maximiza valor esperado sujeto a restricciones duras, y la opción de no
operar compite en igualdad de condiciones.
"""

from bolsa_analytics.cognitive.expected_value import ExpectedValue
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.portfolio_optimizer import (
    OPTIMIZER_CAPITAL_EXCEEDED,
    OPTIMIZER_CORRELATION_UNKNOWN,
    OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK,
    OPTIMIZER_ENUMERATION_CAP_EXCEEDED,
    OPTIMIZER_EXPECTED_VALUE_UNMEASURED,
    OPTIMIZER_NOT_SELECTED,
    OPTIMIZER_RISK_UNMEASURED,
    OPTIMIZER_SECTOR_EXCEEDED,
    OptimizerCandidate,
    OptimizerConstraints,
    optimize_portfolio,
)


def _candidate(
    symbol: str,
    *,
    net: float | None = 10.0,
    risk: float | None = 50.0,
    notional: float | None = 1_000.0,
    sector: str | None = "tech",
    liquidity: float | None = 1_000_000.0,
    correlation: float | None = None,
) -> OptimizerCandidate:
    """Candidata con una economía ya medida (el EV tiene su propio fichero de tests)."""
    if net is None:
        expected = ExpectedValue()
    else:
        expected = ExpectedValue(
            expected_r=0.5,
            risk_amount=risk,
            expected_currency=net,
            net_expected_currency=net,
            measurement=MEASUREMENT_COMPLETE,
        )
    return OptimizerCandidate(
        instrument_id=symbol,
        expected_value=expected,
        notional=notional,
        risk_amount=risk,
        sector=sector,
        liquidity_notional=liquidity,
        correlation_with_portfolio=correlation,
    )


def test_capital_picks_the_affordable_subset_instead_of_the_top_of_the_ranking() -> None:
    """El caso central: el mejor suelto NO es la mejor cartera."""
    candidates = [
        _candidate("AAA", net=30.0, notional=6_000.0),
        _candidate("BBB", net=25.0, notional=5_000.0),
        _candidate("CCC", net=20.0, notional=4_500.0),
    ]
    decision = optimize_portfolio(
        candidates, OptimizerConstraints(max_positions=3, available_cash=10_000.0)
    )

    # Un greedy por ranking habría tomado AAA (30) y se habría quedado ahí: 30 < 45.
    assert decision.selected == ("BBB", "CCC")
    assert decision.expected_value_total == 45.0
    assert decision.reasons_by_instrument()["AAA"] == OPTIMIZER_CAPITAL_EXCEEDED
    assert decision.measurement == MEASUREMENT_COMPLETE


def test_the_empty_set_wins_when_no_combination_has_a_positive_expectation() -> None:
    """Un optimizador que siempre encuentra algo que comprar no es un optimizador."""
    candidates = [
        _candidate("AAA", net=-5.0),
        _candidate("BBB", net=-1.0),
    ]
    decision = optimize_portfolio(candidates, OptimizerConstraints(max_positions=2))

    assert decision.selected == ()
    assert decision.expected_value_total == 0.0
    assert decision.notes == ("empty_set_wins",)
    assert decision.measurement == MEASUREMENT_COMPLETE
    assert decision.decided is True


def test_a_known_correlation_limit_makes_an_unknown_correlation_infeasible() -> None:
    """Fail-closed: con el límite activo, "no sé la correlación" NO es "no correlaciona"."""
    candidates = [
        _candidate("AAA", net=10.0, correlation=0.5),
        _candidate("BBB", net=100.0, correlation=None),
    ]
    decision = optimize_portfolio(
        candidates, OptimizerConstraints(max_positions=1, max_correlation=0.8)
    )

    # BBB vale diez veces más y aun así queda fuera: su dato no es verificable.
    assert decision.selected == ("AAA",)
    assert decision.reasons_by_instrument()["BBB"] == OPTIMIZER_CORRELATION_UNKNOWN
    assert decision.measurement == MEASUREMENT_COMPLETE


def test_the_enumeration_cap_aborts_without_a_silent_greedy() -> None:
    """Sobrepasado el tope NO se optimiza a medias: se declara y se cae al ranking."""
    candidates = [_candidate(f"S{i}") for i in range(4)]
    decision = optimize_portfolio(
        candidates, OptimizerConstraints(max_positions=4, max_combinations=5)
    )

    assert decision.selected == ()
    assert decision.combinations_evaluated == 0
    assert decision.measurement == MEASUREMENT_UNKNOWN
    assert decision.decided is False
    assert OPTIMIZER_ENUMERATION_CAP_EXCEEDED in decision.notes
    assert set(decision.reasons_by_instrument().values()) == {
        OPTIMIZER_ENUMERATION_CAP_EXCEEDED
    }


def test_an_unmeasured_expectation_is_never_scored_as_zero() -> None:
    """Un EV no medido NO se cuela como "el peor de los medidos": se declara inmedible."""
    candidates = [
        _candidate("AAA", net=None),
        _candidate("BBB", net=5.0),
    ]
    decision = optimize_portfolio(candidates, OptimizerConstraints(max_positions=1))

    assert decision.selected == ("BBB",)
    assert decision.reasons_by_instrument()["AAA"] == OPTIMIZER_EXPECTED_VALUE_UNMEASURED


def test_a_candidate_without_measured_risk_cannot_enter() -> None:
    """Sin ``risk_amount`` no hay comparación de riesgo posible ⇒ infeasible declarada."""
    candidates = [
        _candidate("AAA", net=100.0, risk=None),
        _candidate("BBB", net=5.0, risk=10.0),
    ]
    decision = optimize_portfolio(candidates, OptimizerConstraints(max_positions=1))

    assert decision.selected == ("BBB",)
    assert decision.reasons_by_instrument()["AAA"] == OPTIMIZER_RISK_UNMEASURED


def test_a_tie_on_value_prefers_the_lower_risk() -> None:
    """Desempate declarado: a igual valor esperado, gana la cartera de menor riesgo."""
    candidates = [
        _candidate("AAA", net=10.0, risk=100.0),
        _candidate("BBB", net=10.0, risk=50.0),
    ]
    decision = optimize_portfolio(candidates, OptimizerConstraints(max_positions=1))

    assert decision.selected == ("BBB",)
    assert decision.risk_total == 50.0


def test_a_full_tie_is_broken_lexicographically_for_reproducibility() -> None:
    candidates = [
        _candidate("BBB", net=10.0, risk=50.0),
        _candidate("AAA", net=10.0, risk=50.0),
    ]
    decision = optimize_portfolio(candidates, OptimizerConstraints(max_positions=1))

    assert decision.selected == ("AAA",)


def test_joint_sector_concentration_rejects_a_combination_of_acceptable_singles() -> None:
    """La concentración se mide sobre la COMBINACIÓN, no candidata a candidata."""
    candidates = [
        _candidate("AAA", net=10.0, notional=25_000.0, sector="tech"),
        _candidate("BBB", net=10.0, notional=25_000.0, sector="tech"),
    ]
    decision = optimize_portfolio(
        candidates,
        OptimizerConstraints(max_positions=2, equity=100_000.0, max_sector_pct=40.0),
    )

    # Cada una sola es 25% (cabe); juntas son 50% ⇒ ninguna combinación de dos es viable.
    assert decision.selected == ("AAA",)
    assert decision.reasons_by_instrument()["BBB"] == OPTIMIZER_SECTOR_EXCEEDED


def test_no_new_risk_is_a_complete_decision_to_not_trade() -> None:
    """Vetar el riesgo nuevo no es UNKNOWN: es una decisión de cero operaciones, medida."""
    candidates = [_candidate("AAA", net=100.0)]
    decision = optimize_portfolio(candidates, OptimizerConstraints(new_risk_allowed=False))

    assert decision.selected == ()
    assert decision.measurement == MEASUREMENT_COMPLETE
    assert decision.decided is True
    assert decision.notes == ("new_risk_not_allowed",)
    assert (
        decision.reasons_by_instrument()["AAA"] == OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK
    )


def test_the_result_is_independent_of_the_input_order() -> None:
    """Determinismo: la misma cartera da la misma combinación con cualquier orden."""
    candidates = [
        _candidate("AAA", net=30.0, notional=6_000.0),
        _candidate("BBB", net=25.0, notional=5_000.0),
        _candidate("CCC", net=20.0, notional=4_500.0),
    ]
    constraints = OptimizerConstraints(max_positions=3, available_cash=10_000.0)

    assert optimize_portfolio(candidates, constraints) == optimize_portfolio(
        list(reversed(candidates)), constraints
    )


def test_unselected_candidates_are_declared_and_never_silent() -> None:
    """El que no entra siempre tiene motivo: ``optimizer_not_selected`` o su causa real."""
    candidates = [_candidate("AAA", net=30.0), _candidate("BBB", net=-1.0)]
    decision = optimize_portfolio(candidates, OptimizerConstraints(max_positions=1))

    assert decision.selected == ("AAA",)
    assert decision.reasons_by_instrument()["BBB"] == OPTIMIZER_NOT_SELECTED
    assert decision.to_dict()["rejections"] == [
        {"instrumentId": "BBB", "reason": OPTIMIZER_NOT_SELECTED}
    ]
