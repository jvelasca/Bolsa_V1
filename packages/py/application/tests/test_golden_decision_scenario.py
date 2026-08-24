"""Golden Scenario — replay de la columna de decisión (sin Yahoo / red).

Assessments TA congelados + cesta congelada → ``run_decision_runtime`` →
``check_opening`` produce el mismo par (action, verdict). No es replay de mercado
DÍA D; es la columna Runtime → Package → Fit.
"""

from __future__ import annotations

from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_analytics.knowledge import build_technical_assessment, run_decision_runtime
from bolsa_analytics.knowledge.models import TechnicalInputs

from bolsa_application.risk_engine import RiskDecision, check_opening

# Inputs TA congelados (mismo vector que ``test_technical_assessment_runtime``).
_FROZEN_TA = TechnicalInputs(
    rsi=62,
    adx=28,
    plus_di=28,
    minus_di=12,
    obv_slope=1.0,
    price_slope=0.5,
    bb_width_pct=4.0,
    atr=1.2,
    atr_percentile=40,
    close=150,
    sma_20=148,
    sma_50=145,
)

# Cesta tech 29%: el fill 2% tech cruza MaxSectorExposure 30% (moderate).
_FROZEN_BASKET_DENY: list[BasketPosition] = [
    BasketPosition("t1", 22.0, "tech"),
    BasketPosition("t2", 22.0, "tech"),
    BasketPosition("t3", 14.0, "tech"),
    BasketPosition("h1", 20.0, "health"),
    BasketPosition("e1", 20.0, "energy"),
    BasketPosition("c1", 10.0, "cons"),
]

# Cesta diversificada: el mismo fill no viola concentración ni sector.
_FROZEN_BASKET_ALLOW: list[BasketPosition] = [
    BasketPosition("a", 4.0, "tech"),
    BasketPosition("b", 4.0, "health"),
    BasketPosition("c", 4.0, "energy"),
    BasketPosition("d", 4.0, "cons"),
]


def _opening(*, existing: list[BasketPosition], sector: str) -> RiskDecision:
    return check_opening(
        profile=None,
        instrument_id="inst-golden",
        symbol="INST-GOLDEN",
        trade_type="buy",
        quantity=4.0,
        price=1.0,
        signal_kind="entry_long",
        equity=200.0,
        portfolio_positions=existing,
        proposal_sector=sector,
    )


def test_golden_decision_scenario_frozen_ta_and_basket() -> None:
    """TA bullish → recommend_long; cesta tech 29%+fill → DENY Fit; diversificada → ALLOW."""
    ta, _, _ = build_technical_assessment("inst-golden", _FROZEN_TA)
    runtime = run_decision_runtime(instrument_id="inst-golden", assessments=[ta])
    assert runtime.package.action == "recommend_long"

    denied = _opening(existing=_FROZEN_BASKET_DENY, sector="tech")
    assert denied.verdict == "DENY"
    assert any("Exposición sector superada" in r for r in denied.reasons)

    allowed = _opening(existing=_FROZEN_BASKET_ALLOW, sector="materials")
    assert allowed.verdict == "ALLOW"
    assert all(
        "Concentración cesta superada" not in r and "Exposición sector superada" not in r
        for r in allowed.reasons
    )
