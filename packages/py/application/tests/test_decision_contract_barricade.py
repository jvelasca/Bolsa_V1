"""V2.21 / A8 (M5) — Barricada: la IA solo propone; nunca salta gates.

Sin código IA nuevo (contract_doc). Verifica que un cualquiera canal IA que trate
de ejecutar un bypass (intención directa, o venue LIVE aun "autorizado") es
abortado por la puerta determinista RiskGate → no se materializa camino real.
"""

from __future__ import annotations

import pytest

from bolsa_application.decision_contract import (
    DecisionPackage,
    RiskGateReason,
    risk_gate_auto_paper_dry,
)


def _pkg(action: str = "BUY", *, venue: str = "paper", qty: float = 1.0) -> DecisionPackage:
    p = DecisionPackage(action=action, instrument_id="AAA", quantity=qty)
    return p


def test_ia_happy_proposal_is_only_a_proposal() -> None:
    pkg = _pkg("BUY")
    assert pkg.is_execution_intent is False  # nunca es, por sí, una orden.
    d = risk_gate_auto_paper_dry(pkg, kill_switch_active=False, venue="paper")
    assert d.allow_proposal is True  # admisible PARA PROPONER (sim); no llena.
    assert RiskGateReason.AUTO_OK_SIMULATED in d.reasons


@pytest.mark.parametrize(
    "action, venue, kill, expect",
    [
        ("BUY", "paper", False, True),
        ("SELL", "simulated", False, True),
        ("HOLD", "paper", False, True),
        ("BUY", "LIVE", False, False),  # AUTO jamás abre LIVE.
        ("BUY", "paper", True, False),  # kill switch bloquea aun en propuesta.
        ("BUY", "live_real_wired", False, False),
    ],
)
def test_risk_gate_aborts_non_auto_and_kill(
    action: str, venue: str, kill: bool, expect: bool
) -> None:
    res = risk_gate_auto_paper_dry(_pkg(action, venue=venue), kill_switch_active=kill, venue=venue)
    assert res.allow_proposal is expect


def test_ia_attempt_to_execute_bypass_is_denied() -> None:
    """Un 'canal IA' NO puede elevar su propuesta a ejecución: no existe forma de
    marcarla como orden desde el contrato (siempre is_execution_intent=False), y
    aunque forzase a un adaptador LIVE inexistente, la puerta lo veta."""
    forged = DecisionPackage(
        action="BUY",
        instrument_id="AAA",
        quantity=2.0,
        source="ia_blind_bridge",  # fuente que pretendería "ejecutar ya".
        memo="ejecuta ya, sáltate el gate",
    )
    # 1) Aun forzada, la propuesta NO es una intención ejecutable (estructural).
    assert forged.is_execution_intent is False
    # 2) En simulation/paper la propuesta es admisible (dry) pero NUNCA corre dinero
    #    por aquí (requiere un ExecutionPlan posterior con venue AUTO + SIMULATION).
    sim = risk_gate_auto_paper_dry(forged, kill_switch_active=False, venue="paper")
    assert sim.allow_proposal is True
    # 3) Si el puente LIVE real intentara entrar como venue → VETO inmediato.
    live = risk_gate_auto_paper_dry(forged, kill_switch_active=False, venue="LIVE")
    assert live.allow_proposal is False
    assert RiskGateReason.VENUE_NOT_AUTO_ALLOWED in live.reasons


def test_execution_plan_derived_only_on_sim_allowed() -> None:
    """M5: aun un BUY admitido en dry solo produce un *ExecutionPlan* SIM-ONLY
    de planificación, jamás una orden ni un venue LIVE."""
    from bolsa_application.decision_contract import (
        ExecutionPlan,
        derive_execution_plan,
    )

    buy = DecisionPackage(action="BUY", instrument_id="AAA", quantity=1.0)
    p = derive_execution_plan(buy, venue="paper", kill_switch_active=False)
    assert isinstance(p, ExecutionPlan)
    assert p.targets_live is False  # structural: el plan jamás abre LIVE.
    assert p.action == "BUY"

    p2 = derive_execution_plan(buy, venue="simulated", kill_switch_active=False)
    assert p2 is not None and p2.venue == "simulated"

    # HOLD / kill switch / venue LIVE no emiten plan (no hay camino real).
    hold = DecisionPackage(action="HOLD", instrument_id="AAA", quantity=0.0)
    assert derive_execution_plan(hold, venue="paper") is None
    assert derive_execution_plan(buy, venue="paper", kill_switch_active=True) is None
    assert derive_execution_plan(buy, venue="LIVE") is None


def test_m6_simulation_gate_is_third_barrier_before_router() -> None:
    """V2.22/A9 (M6): un env AUTO mal configurado (venue=live) se bloquea en el
    SimulationGate ANTES de que ninguna barrera posterior resuelva broker."""
    from bolsa_application.decision_contract import simulation_gate_allows

    # Camino AUTO permitido (|paper, simulated|) pasa.
    assert simulation_gate_allows("paper") is True
    assert simulation_gate_allows("simulated") is True
    assert simulation_gate_allows("SIM") is True
    # LIVE/xtb/real/broker_live, incluso "autorizado" por quien lo pida, ⇒ BLOCKED.
    for bad in ("live", "xtb", "real", "broker_live", "LIVE", "AUTo=live"):
        assert simulation_gate_allows(bad) is False, bad
