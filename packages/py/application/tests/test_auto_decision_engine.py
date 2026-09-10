"""V2.23 / A9 (Bloque 4) — hermético del Decision Spine determinista.

Verifica que ``AutoDecisionEngine`` (proveedor por defecto del scheduler SIM) es
HOLD-dominante y fail-closed, que con ``enabled`` NO propone una ejecución hasta que
abre BUY, retiene HOLD y cierra SELL una vez, y que tras el cierre NO re-abre
(no-doble BUY). Todo "en papel": el espinazo solo produce ``DecisionPackage``; el
RiskGate sigue siendo quien otorga/veta (fuera del alcance de este test).
"""

from __future__ import annotations

from bolsa_application.auto_decision_engine import (
    AutoDecisionEngine,
    deterministic_auto_decider,
)

_SYMBOL = "AAA"


def _new(exit_ticks: int, *, enabled: bool = True) -> AutoDecisionEngine:
    return deterministic_auto_decider(
        (_SYMBOL,),
        lot_qty=100.0,
        exit_after_ticks=exit_ticks,
        max_qty=100.0,
        enabled=enabled,
    )


def test_disabled_is_hold_only() -> None:
    spine = _new(3, enabled=False)
    for _ in range(20):
        pkg = spine(_SYMBOL)
        assert pkg.action == "HOLD"
        assert pkg.quantity == 0


def test_out_of_watch_is_hold() -> None:
    spine = _new(3, enabled=True)
    pkg = spine("ZZZ")
    assert pkg.action == "HOLD"


def test_buy_hold_then_sell_once_no_reopen() -> None:
    exit_ticks = 2
    spine = _new(exit_ticks)
    actions: list[str] = []

    def call() -> str:
        a = spine(_SYMBOL).action
        actions.append(a)
        return a

    # Primer tick: apertura.
    assert call() == "BUY"
    # Retención: no re-compra mientras abierto; cede HOLD hasta cumplir el retén.
    assert call() == "HOLD"  # age_enter=1 → edad 1 < exit(2)
    # Cumplido el retén ⇒ cierre.
    assert call() == "SELL"
    # Tras el cierre: cooldown (nunca re-abre en el mismo proceso).
    for _ in range(10):
        assert call() == "HOLD"

    assert actions.count("BUY") == 1
    assert actions.count("SELL") == 1


def test_quantities_are_bounded() -> None:
    spine = AutoDecisionEngine(
        watch=(_SYMBOL,),
        lot_qty=500.0,
        exit_after_ticks=1,
        max_qty=100.0,
        enabled=True,
    )
    pkg = spine(_SYMBOL)
    assert pkg.action == "BUY"
    assert pkg.quantity <= 100.0
