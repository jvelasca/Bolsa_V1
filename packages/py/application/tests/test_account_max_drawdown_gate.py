"""Corte opt-in de drawdown PICO-VALLE de la cuenta (auditoría externa 2026-11-08).

La auditoría encontró que ``EquityMarkBook`` ya medía ``max_pct`` pero el worker devolvía
solo ``daily_pct``: no existía ningún corte por caída acumulada desde el máximo. Aquí se
fija el contrato de la puerta: con límite, una caída por encima veta APERTURAS; una
medición ausente NO se autoriza en silencio; sin límite no cambia nada.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    build_auto_portfolio_snapshot,
)
from bolsa_analytics.cognitive.opportunity_ranker import score_opportunity
from bolsa_application.auto_v2_entry import V2Tunables, tunables_from_env
from bolsa_application.portfolio_decision_engine import (
    PortfolioDecisionConfig,
    decide_portfolio,
)


def _snapshot(*, max_drawdown_pct: float | None) -> object:
    return build_auto_portfolio_snapshot(
        account_id="acct-dd",
        capital=100_000.0,
        cash=80_000.0,
        equity=100_000.0,
        buying_power=80_000.0,
        risk_used=500.0,
        risk_budget=2_000.0,
        data_freshness=DATA_FRESH,
        max_drawdown_pct=max_drawdown_pct,
    )


def _score(value: float = 0.8) -> object:
    return score_opportunity(
        "AAPL",
        edge=value,
        robustness=value,
        regime_fit=value,
        momentum=value,
        liquidity=value,
        risk_reward=value,
        execution_quality=value,
    )


def _decide(
    *,
    account_max_drawdown_pct: float | None,
    max_drawdown_pct: float | None,
) -> object:
    return decide_portfolio(
        instrument_id="AAPL",
        direction="long",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(),
        snapshot=_snapshot(max_drawdown_pct=max_drawdown_pct),
        regime="BULL_TREND",
        sector="Technology",
        liquidity_notional=1_000_000.0,
        decision_id="dec-dd",
        config=PortfolioDecisionConfig(
            account_max_drawdown_pct=account_max_drawdown_pct,
        ),
    )


def test_a_drawdown_over_the_cap_vetoes_the_opening() -> None:
    decision = _decide(account_max_drawdown_pct=15.0, max_drawdown_pct=20.0)

    assert decision.approved is False
    assert decision.action == "HOLD"
    assert decision.reason_codes == ("account_max_drawdown_exceeded",)
    assert decision.is_no_trade is True


def test_a_drawdown_below_the_cap_still_allows_the_opening() -> None:
    decision = _decide(account_max_drawdown_pct=15.0, max_drawdown_pct=10.0)

    assert decision.approved is True
    assert decision.reason_codes == ("approved",)


def test_the_cap_is_a_ceiling_not_a_floor() -> None:
    assert _decide(account_max_drawdown_pct=15.0, max_drawdown_pct=15.0).approved is True
    assert _decide(account_max_drawdown_pct=15.0, max_drawdown_pct=15.1).approved is False


def test_an_unmeasured_drawdown_never_becomes_an_approval() -> None:
    decision = _decide(account_max_drawdown_pct=15.0, max_drawdown_pct=None)

    assert decision.approved is False
    assert decision.reason_codes == ("account_max_drawdown_unmeasured",)


def test_without_a_cap_the_gate_is_byte_identical() -> None:
    # Sin límite, ni siquiera una medición ausente cambia la decisión histórica.
    assert _decide(account_max_drawdown_pct=None, max_drawdown_pct=None).approved is True
    assert _decide(account_max_drawdown_pct=None, max_drawdown_pct=90.0).approved is True


def test_the_cap_reads_from_env_and_is_off_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT", raising=False)
    assert V2Tunables().account_max_drawdown_pct is None
    assert tunables_from_env().decision_config().account_max_drawdown_pct is None

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT", "15")
    tunables = tunables_from_env()
    assert tunables.account_max_drawdown_pct == pytest.approx(15.0)
    assert tunables.decision_config().account_max_drawdown_pct == pytest.approx(15.0)


@pytest.mark.parametrize("raw", ["", "0", "-5", "quince", "nan", "inf"])
def test_an_invalid_or_zero_cap_is_declared_off(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT", raw)

    assert tunables_from_env().account_max_drawdown_pct is None
