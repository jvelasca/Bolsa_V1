"""P2 (auditoría TRADING/AUTO .183) — el Policy Gate no salta reglas sin dato.

Antes de esta corrección, ``MinMarketCap``, ``MinADV``, ``MaxSpreadBps``,
``MaxSectorExposure`` y los tres circuit breakers de drawdown quedaban ``SKIPPED``
cuando el dato no venía, y ``SKIPPED`` no veta. El resultado es que una política podía
exigir un mínimo de liquidez que NUNCA se comprobaba.

El contrato nuevo tiene dos piezas:

* regla activa + dato ausente ⇒ ``FAILED`` con motivo ``<Regla>_unmeasured``;
* solo las reglas que la política declara en ``optional_measurements`` quedan
  ``SKIPPED``, y con motivo ``<Regla>_unmeasured_declared`` (``SKIPPED`` con causa no es
  lo mismo que ``SKIPPED`` a secas).

Cada test nombra la regla que protege.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from bolsa_analytics.cognitive import (
    MODERATE_POLICY,
    ProposedTradeContext,
    evaluate_policy_gate,
    gate_decision_package,
)
from bolsa_analytics.cognitive.policy_gate import PolicyGateResult


def _measured_kwargs(**overrides: object) -> dict[str, object]:
    """Trade COMPLETAMENTE medido: es el mínimo para que el gate pueda aprobar."""
    kwargs: dict[str, object] = dict(
        symbol="AAPL",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        sector="technology",
        spread_bps=5.0,
        risk_pct_of_account=0.4,
        reward_to_risk_ratio=2.5,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=2,
        portfolio_concentration_pct=5.0,
        hours_to_earnings=72,
        account_daily_drawdown_pct=0.0,
        account_weekly_drawdown_pct=0.0,
        account_max_drawdown_pct=0.0,
        basket_max_sector_weight_pct=5.0,
    )
    kwargs.update(overrides)
    return kwargs


def _rule(gate: PolicyGateResult, name: str):
    matches = [r for r in gate.evaluated_rules if r.rule == name]
    assert len(matches) == 1, f"{name} debe aparecer exactamente una vez"
    return matches[0]


@pytest.mark.parametrize(
    ("field", "rule"),
    [
        ("market_cap_usd", "MinMarketCap"),
        ("average_daily_volume_usd", "MinADV"),
        ("spread_bps", "MaxSpreadBps"),
        ("basket_max_sector_weight_pct", "MaxSectorExposure"),
        ("account_daily_drawdown_pct", "HardDailyDrawdown"),
        ("account_weekly_drawdown_pct", "HardWeeklyDrawdown"),
        ("account_max_drawdown_pct", "HardMaxDrawdown"),
    ],
)
def test_a_missing_measurement_is_not_verified(field: str, rule: str) -> None:
    """Un trade medido pasa; quitar UNA medición veta con su nombre."""
    clean = evaluate_policy_gate(
        MODERATE_POLICY,
        **{
            **_measured_kwargs(),
            # La plantilla declara opcionales spread y max drawdown: aquí se exige todo
            # para probar el modo estricto sin depender de la plantilla.
            "optional_measurements": (),
        },  # type: ignore[arg-type]
    )
    assert clean.passed is True

    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **{**_measured_kwargs(), field: None, "optional_measurements": ()},  # type: ignore[arg-type]
    )
    assert gate.passed is False
    failed = _rule(gate, rule)
    assert failed.status == "FAILED"
    assert failed.message == f"{rule}_unmeasured"
    assert failed.actual == "n/a"
    assert f"{rule}_unmeasured" in gate.veto_reasons


def test_a_declared_optional_rule_is_skipped_with_its_reason() -> None:
    """Declarar la excepción es explícito; el SKIPPED viaja con causa."""
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **{
            **_measured_kwargs(),
            "spread_bps": None,
            "optional_measurements": ("MaxSpreadBps",),
        },  # type: ignore[arg-type]
    )
    assert gate.passed is True
    skipped = _rule(gate, "MaxSpreadBps")
    assert skipped.status == "SKIPPED"
    assert skipped.message == "MaxSpreadBps_unmeasured_declared"
    assert gate.veto_reasons == ()


def test_the_policy_carries_its_own_declarations() -> None:
    """``optional_measurements=None`` lee la política: la decisión viaja con ella."""
    declared = replace(
        MODERATE_POLICY,
        optional_measurements=("MaxSpreadBps", "HardMaxDrawdown"),
    )
    gate = evaluate_policy_gate(
        declared,
        **{**_measured_kwargs(), "spread_bps": None, "account_max_drawdown_pct": None},  # type: ignore[arg-type]
    )
    assert _rule(gate, "MaxSpreadBps").status == "SKIPPED"
    assert _rule(gate, "HardMaxDrawdown").status == "SKIPPED"
    assert gate.passed is True


def test_a_policy_that_declares_nothing_is_strict() -> None:
    """El default de la política es estricto: () no es una excepción implícita."""
    strict = replace(MODERATE_POLICY, optional_measurements=())
    gate = evaluate_policy_gate(
        strict,
        **{**_measured_kwargs(), "spread_bps": None},  # type: ignore[arg-type]
    )
    assert gate.passed is False
    assert _rule(gate, "MaxSpreadBps").status == "FAILED"


def test_an_inactive_rule_is_not_emitted() -> None:
    """Un mínimo que la política no declara no es una regla pendiente de dato."""
    policy_without_adv = replace(
        MODERATE_POLICY,
        universe=replace(
            MODERATE_POLICY.universe,
            min_average_daily_volume_usd=None,
            min_market_cap_usd=None,
            max_spread_bps=None,
        ),
        optional_measurements=(),
    )
    gate = evaluate_policy_gate(
        policy_without_adv,
        **{
            **_measured_kwargs(),
            "average_daily_volume_usd": None,
            "market_cap_usd": None,
            "spread_bps": None,
        },  # type: ignore[arg-type]
    )
    names = {r.rule for r in gate.evaluated_rules}
    assert "MinADV" not in names
    assert "MinMarketCap" not in names
    assert "MaxSpreadBps" not in names
    assert gate.passed is True


def test_a_measured_value_below_the_limit_still_vetoes() -> None:
    """Cerrar el fail-open no cambia la comparación: manda el límite de la política."""
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **{**_measured_kwargs(), "average_daily_volume_usd": 1.0},  # type: ignore[arg-type]
    )
    assert gate.passed is False
    assert _rule(gate, "MinADV").status == "FAILED"
    assert _rule(gate, "MinADV").message is None


def test_the_decision_package_path_carries_the_same_verdict() -> None:
    """El veto llega al DecisionPackage: no se ejecuta y el motivo se conserva."""
    from bolsa_analytics.knowledge import TechnicalInputs, build_decision_package_ta

    package, _, _ = build_decision_package_ta(
        "inst-aapl",
        TechnicalInputs(
            rsi=68,
            adx=32,
            plus_di=28,
            minus_di=15,
            obv_slope=1.0,
            price_slope=1.0,
            atr_percentile=50,
            close=150,
            sma_20=145,
            sma_50=140,
        ),
    )
    assert package.action == "recommend_long"
    gated = gate_decision_package(
        package,
        MODERATE_POLICY,
        ProposedTradeContext(
            symbol="AAPL",
            market_cap_usd=3e12,
            # ADV AUSENTE: el catálogo no lo midió y la plantilla exige 5M USD.
            average_daily_volume_usd=None,
            risk_pct_of_account=0.4,
            reward_to_risk_ratio=2.5,
            has_stop_loss=True,
            hours_to_earnings=72,
            account_daily_drawdown_pct=0.0,
            account_weekly_drawdown_pct=0.0,
            basket_max_sector_weight_pct=5.0,
        ),
    )
    assert gated.execution_allowed is False
    assert gated.gate is not None
    assert "MinADV_unmeasured" in gated.gate.veto_reasons
    assert gated.package.action == "recommend_long"  # la oportunidad no se reescribe
