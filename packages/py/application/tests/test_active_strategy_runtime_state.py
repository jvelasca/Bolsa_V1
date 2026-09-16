"""ActiveStrategyRuntimeState + seam TradePlan→DecisionPackage (AUTO 2.0 · P0/P2)."""

from bolsa_application.active_strategy_runtime_state import (
    derive_runtime_state,
    runtime_allows_new_entries,
    runtime_allows_position_management,
)
from bolsa_application.auto_investment_system import trade_plan_to_decision_package

# ── ActiveStrategyRuntimeState ────────────────────────────────────────────────


def test_derive_precedence() -> None:
    assert derive_runtime_state() == "ACTIVE"
    assert derive_runtime_state(regime_exit_only=True) == "ACTIVE_EXIT_ONLY"
    assert derive_runtime_state(paused=True, regime_exit_only=True) == "ACTIVE_PAUSED"
    assert derive_runtime_state(degraded=True, paused=True) == "ACTIVE_DEGRADED"
    assert derive_runtime_state(retired=True, degraded=True) == "RETIRED"


def test_runtime_entry_permission_fail_closed() -> None:
    assert runtime_allows_new_entries("ACTIVE") is True
    assert runtime_allows_new_entries("ACTIVE_PAUSED") is False
    assert runtime_allows_new_entries("ACTIVE_EXIT_ONLY") is False
    assert runtime_allows_new_entries("ACTIVE_DEGRADED") is False
    assert runtime_allows_new_entries("RETIRED") is False
    assert runtime_allows_new_entries(None) is False
    assert runtime_allows_new_entries("basura") is False


def test_runtime_position_management_permission() -> None:
    assert runtime_allows_position_management("ACTIVE_PAUSED") is True
    assert runtime_allows_position_management("ACTIVE_EXIT_ONLY") is True
    assert runtime_allows_position_management("RETIRED") is False


# ── TradePlan → DecisionPackage seam ──────────────────────────────────────────


def test_trade_plan_to_decision_package_buy() -> None:
    from bolsa_analytics.cognitive.trade_plan import TradePlan

    # V2.40.4: el plan que llega a este seam ya pasó ``validate_trade_plan``, así que se
    # construye coherente (riesgo = qty × distancia, valor = qty × entry, geometría ±1R/±2R).
    plan = TradePlan(
        decision_id="dec-1",
        instrument_id="AAPL",
        direction="long",
        status="TRIGGERED",
        quantity=75.0,
        risk_pct=0.75,
        why_not=(),
        execution_allowed=True,
        entry=100.0,
        structural_stop=96.0,
        target1=104.0,
        target2=108.0,
        initial_risk_r=4.0,
        risk_amount=300.0,
        position_value=7500.0,
    )
    pkg = trade_plan_to_decision_package(plan, source="auto-2.0")
    assert pkg is not None
    assert pkg.action == "BUY"
    assert pkg.instrument_id == "AAPL"
    assert pkg.quantity == 75.0
    assert pkg.suggested_price == 100.0
    assert pkg.is_execution_intent is False  # sigue siendo propuesta, no bypass.
    assert "stop=96.0" in pkg.memo


def test_trade_plan_to_decision_package_sell() -> None:
    from bolsa_analytics.cognitive.trade_plan import TradePlan

    plan = TradePlan(
        decision_id="dec-2",
        instrument_id="AAPL",
        direction="short",
        status="TRIGGERED",
        quantity=10.0,
        risk_pct=0.5,
        why_not=(),
        execution_allowed=True,
        entry=100.0,
        structural_stop=104.0,
        target1=96.0,
        target2=92.0,
        initial_risk_r=4.0,
        risk_amount=40.0,
        position_value=1000.0,
    )
    pkg = trade_plan_to_decision_package(plan)
    assert pkg is not None
    assert pkg.action == "SELL"


def test_trade_plan_to_decision_package_fail_closed() -> None:
    from bolsa_analytics.cognitive.trade_plan import TradePlan

    assert trade_plan_to_decision_package(None) is None
    blocked = TradePlan(
        decision_id="dec-3",
        instrument_id="AAPL",
        direction="long",
        status="BLOCKED",
        quantity=0.0,
        risk_pct=0.0,
        why_not=("fit",),
        execution_allowed=False,
    )
    assert trade_plan_to_decision_package(blocked) is None
    no_direction = TradePlan(
        decision_id="dec-4",
        instrument_id="AAPL",
        direction="none",
        status="TRIGGERED",
        quantity=10.0,
        risk_pct=0.5,
        why_not=(),
        execution_allowed=True,
    )
    assert trade_plan_to_decision_package(no_direction) is None


def test_trade_plan_to_decision_package_rejects_incoherent_plan() -> None:
    """V2.40.4: defensa en profundidad en el seam que consume el worker.

    Un plan que dice "ejecuta" con cantidad pero sin geometría de riesgo coherente NO
    se convierte en propuesta, aunque ``execution_allowed`` sea True: el motor ya lo
    veta (``plan_invalid``), y este seam lo vuelve a comprobar para que ningún camino
    alternativo pueda emitir una propuesta incoherente.
    """
    from bolsa_analytics.cognitive.trade_plan import TradePlan

    incoherent = TradePlan(
        decision_id="dec-5",
        instrument_id="AAPL",
        direction="long",
        status="TRIGGERED",
        quantity=75.0,
        risk_pct=0.75,
        why_not=(),
        execution_allowed=True,
        entry=100.0,
        structural_stop=96.0,
        # Sin targets / initialRiskR / riskAmount / positionValue: el plan se contradice.
    )
    assert trade_plan_to_decision_package(incoherent) is None
