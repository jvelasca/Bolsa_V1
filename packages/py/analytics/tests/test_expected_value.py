"""AUTO-4 / V2.44 — valor esperado ECONÓMICO (`expected_value.py`).

Los tests certifican la disciplina de medición del repo aplicada a la economía: lo que se
puede medir se mide, y lo que no **degrada** la medición declarándolo; nunca se convierte en
un `0.0` que se colaría como "una oportunidad más" en la cartera.
"""

from bolsa_analytics.cognitive.expected_value import (
    EV_COST_UNMEASURED,
    EV_GEOMETRY_UNMEASURED,
    EV_LOSS_MEAN_MISSING,
    EV_LOSS_MEAN_POSITIVE,
    EV_P_WIN_OUT_OF_RANGE,
    EV_WIN_DERIVED_FROM_TARGET,
    EV_WIN_MEAN_MISSING,
    EV_WIN_MEAN_NEGATIVE,
    build_expected_value,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.portfolio_reservation import TradingCostModel

#: Modelo de coste NULO: aísla el valor esperado bruto del coste (el coste tiene sus
#: propios tests y no debe oscurecer los del EV). Sujeto a la misma casa del coste.
_ZERO_COST = TradingCostModel(
    commission_bps=0.0, spread_bps=0.0, slippage_bps=0.0, gap_bps=0.0
)


def _ev(**kwargs):
    kwargs.setdefault("entry", 100.0)
    kwargs.setdefault("stop", 95.0)
    kwargs.setdefault("quantity", 10.0)
    kwargs.setdefault("cost_model", _ZERO_COST)
    return build_expected_value(**kwargs)


def test_expected_r_and_net_currency_come_from_the_declared_means() -> None:
    """``p·win + (1−p)·loss`` en R y su traducción a dinero con el MISMO 1R del motor."""
    ev = _ev(p_win=0.6, avg_win_r=2.0, avg_loss_r=-1.0)

    # 0.6·2 + 0.4·(−1) = 0.8R ; 1R = |100 − 95| · 10 = 50 ⇒ 40 de valor esperado.
    assert ev.expected_r == 0.8
    assert ev.risk_amount == 50.0
    assert ev.expected_currency == 40.0
    assert ev.cost_currency == 0.0
    assert ev.net_expected_currency == 40.0
    assert ev.measurement == MEASUREMENT_COMPLETE
    assert ev.notes == ()
    assert ev.is_measurable is True


def test_the_cost_is_subtracted_from_the_expected_value() -> None:
    """El neto ES el valor esperado menos el coste de ida y vuelta (no se ignora)."""
    ev = _ev(
        p_win=0.6,
        avg_win_r=2.0,
        avg_loss_r=-1.0,
        cost_model=TradingCostModel(
            commission_bps=10.0, spread_bps=2.0, slippage_bps=5.0, gap_bps=0.0
        ),
    )
    assert ev.expected_currency == 40.0
    assert ev.cost_currency is not None and ev.cost_currency > 0.0
    assert ev.net_expected_currency == round(40.0 - ev.cost_currency, 4)
    assert ev.net_expected_currency < ev.expected_currency
    assert ev.measurement == MEASUREMENT_COMPLETE


def test_the_payload_publishes_the_economics_with_its_measurement() -> None:
    """El contrato del journal: la economía va con su estado de medición y sus notas."""
    payload = _ev(p_win=0.6, avg_win_r=2.0, avg_loss_r=-1.0).to_dict()

    assert payload["expectedR"] == 0.8
    assert payload["netExpectedCurrency"] == 40.0
    assert payload["measurement"] == MEASUREMENT_COMPLETE
    assert payload["notes"] == []

    unknown = _ev(p_win=None, avg_win_r=2.0, avg_loss_r=-1.0).to_dict()
    assert unknown["expectedR"] is None
    assert unknown["netExpectedCurrency"] is None
    assert unknown["measurement"] == MEASUREMENT_UNKNOWN
    assert EV_P_WIN_OUT_OF_RANGE in unknown["notes"]


def test_p_win_out_of_range_is_unknown_and_never_a_fabricated_zero() -> None:
    """Una probabilidad que no es probabilidad no produce un `0.0`: produce UNKNOWN."""
    ev = _ev(p_win=1.5, avg_win_r=2.0, avg_loss_r=-1.0)

    assert ev.expected_r is None
    assert ev.net_expected_currency is None
    assert ev.measurement == MEASUREMENT_UNKNOWN
    assert EV_P_WIN_OUT_OF_RANGE in ev.notes
    assert ev.is_measurable is False


def test_a_missing_win_mean_degrades_to_unknown() -> None:
    """Sin media de ganadoras (y sin target del que derivarla) no hay valor esperado."""
    ev = _ev(p_win=0.6, avg_win_r=None, avg_loss_r=-1.0, target=None)

    assert ev.expected_r is None
    assert ev.measurement == MEASUREMENT_UNKNOWN
    assert EV_WIN_MEAN_MISSING in ev.notes


def test_a_missing_loss_mean_degrades_to_unknown() -> None:
    ev = _ev(p_win=0.6, avg_win_r=2.0, avg_loss_r=None)

    assert ev.expected_r is None
    assert ev.measurement == MEASUREMENT_UNKNOWN
    assert EV_LOSS_MEAN_MISSING in ev.notes


def test_a_win_mean_derived_from_the_target_is_declared_not_silent() -> None:
    """El target puede SUSTITUIR a la media histórica, pero se declara como derivada."""
    ev = _ev(p_win=0.5, avg_win_r=None, avg_loss_r=-1.0, target=110.0)

    # (110 − 100) / (100 − 95) = 2R ⇒ 0.5·2 + 0.5·(−1) = 0.5R.
    assert ev.avg_win_r == 2.0
    assert ev.expected_r == 0.5
    assert EV_WIN_DERIVED_FROM_TARGET in ev.notes


def test_an_inverted_geometry_does_not_turn_risk_into_zero() -> None:
    """Un stop del lado equivocado no es "riesgo 0": deja el neto SIN medir (PARTIAL)."""
    ev = build_expected_value(
        entry=100.0,
        stop=100.0,
        quantity=10.0,
        p_win=0.6,
        avg_win_r=2.0,
        avg_loss_r=-1.0,
        cost_model=_ZERO_COST,
    )

    assert ev.expected_r == 0.8  # el R adimensional SÍ está medido
    assert ev.risk_amount is None
    assert ev.expected_currency is None
    assert ev.net_expected_currency is None
    assert ev.measurement == MEASUREMENT_PARTIAL
    assert EV_GEOMETRY_UNMEASURED in ev.notes


def test_an_unmeasurable_cost_leaves_the_net_unmeasured() -> None:
    """Sin coste medible el neto NO se cierra (el valor esperado bruto sigue medido)."""
    ev = build_expected_value(
        entry=100.0,
        stop=95.0,
        quantity=10.0,
        p_win=0.6,
        avg_win_r=2.0,
        avg_loss_r=-1.0,
        # Sin modelo y sin ``AccountSettings``, el coste no es medible (``total`` None).
        cost_model=None,
    )
    if ev.cost_currency is None:
        assert ev.expected_currency == 40.0
        assert ev.net_expected_currency is None
        assert ev.measurement == MEASUREMENT_PARTIAL
        assert EV_COST_UNMEASURED in ev.notes
    else:
        # Si el modelo por defecto sí declara coste, el neto debe estar cerrado.
        assert ev.net_expected_currency == round(40.0 - ev.cost_currency, 4)
        assert ev.measurement == MEASUREMENT_COMPLETE


def test_a_geometry_without_quantity_leaves_the_net_unmeasured() -> None:
    ev = build_expected_value(
        entry=100.0,
        stop=95.0,
        quantity=None,
        p_win=0.6,
        avg_win_r=2.0,
        avg_loss_r=-1.0,
        cost_model=_ZERO_COST,
    )

    assert ev.expected_r == 0.8
    assert ev.expected_currency is None
    assert ev.net_expected_currency is None
    assert ev.measurement == MEASUREMENT_PARTIAL
    assert EV_GEOMETRY_UNMEASURED in ev.notes


def test_a_negative_win_mean_and_a_positive_loss_mean_are_both_rejected() -> None:
    """Una media con el signo cambiado no es un dato: es una medición imposible."""
    negative_win = _ev(p_win=0.6, avg_win_r=-2.0, avg_loss_r=-1.0)
    assert negative_win.measurement == MEASUREMENT_UNKNOWN
    assert EV_WIN_MEAN_NEGATIVE in negative_win.notes

    positive_loss = _ev(p_win=0.6, avg_win_r=2.0, avg_loss_r=1.0)
    assert positive_loss.measurement == MEASUREMENT_UNKNOWN
    assert EV_LOSS_MEAN_POSITIVE in positive_loss.notes


def test_a_certain_win_does_not_need_a_loss_mean() -> None:
    """Con ``p = 1`` no hay rama perdedora: exigir su media sería inventar un veto."""
    ev = _ev(p_win=1.0, avg_win_r=2.0, avg_loss_r=None)

    assert ev.expected_r == 2.0
    assert ev.measurement == MEASUREMENT_COMPLETE
    assert EV_LOSS_MEAN_MISSING not in ev.notes
    assert EV_COST_UNMEASURED not in ev.notes
