"""PositionManager — PositionState + ExitPlan + PositionDecision (AUTO 2.0 · P1)."""

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.position_manager import REGIME_EXIT, manage_position


def _open_long(mark: float = 100.0):
    plan = {
        "decisionId": "dec-1",
        "instrumentId": "AAPL",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    return build_position_state_from_fill(
        plan, fill_price=100.0, fill_quantity=10.0, position_id="pos-1"
    )


def test_hold_when_no_exit_signal() -> None:
    result = manage_position(_open_long(), mark_price=101.0, regime="BULL_TREND")
    assert result is not None
    assert result.order_action == "hold"
    assert result.order_qty is None
    assert result.exit_reasons == ()
    assert result.decision.action == "HOLD"


def test_structural_stop_sells_all() -> None:
    result = manage_position(_open_long(), mark_price=95.0, regime="BULL_TREND")
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == 10.0
    assert "structural_stop" in result.exit_reasons


def test_target1_reduces_partial() -> None:
    # mark >= T1 (105) ⇒ TARGET_1 ⇒ reduce 30% (moderate) de 10 ⇒ 3.
    result = manage_position(
        _open_long(), mark_price=105.0, regime="BULL_TREND", template_id="moderate"
    )
    assert result is not None
    assert result.order_action == "reduce"
    assert result.order_qty == 3.0
    assert "target_1" in result.exit_reasons


def test_thesis_invalidation_sells_full_position() -> None:
    # V2.42 slice 2b (decisión D2 firmada): la invalidación CONFIRMADA de la tesis es una
    # salida REAL (proteger capital), no un ``REVIEW``. Este es el A/B del camino MESA: la
    # misma función compartida que usa el AUTO ahora emite VENTA total, y el motivo sigue
    # auditado en ``exit_reasons``.
    position = _open_long()
    result = manage_position(
        position, mark_price=101.0, thesis_invalid=True, regime="BULL_TREND"
    )
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == position.remaining_quantity
    assert result.decision.action == "EXIT"
    assert result.attention == "URGENT"
    assert "thesis_invalidation" in result.exit_reasons


def test_thesis_invalidation_under_recon_drift_reviews_not_sells() -> None:
    # El veto de reconciliación sigue declarado: ``THESIS_INVALIDATION`` NO es una salida
    # protectora (D2), así que con el libro en drift la venta no se autoriza a ciegas.
    result = manage_position(
        _open_long(),
        mark_price=101.0,
        thesis_invalid=True,
        regime="BULL_TREND",
        portfolio_recon_status="drift",
    )
    assert result is not None
    assert result.order_action == "hold"
    assert result.decision.action == "REVIEW"


def test_regime_exit_only_forces_full_sell() -> None:
    result = manage_position(_open_long(), mark_price=101.0, regime="UNKNOWN")
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == 10.0
    assert REGIME_EXIT in result.exit_reasons


def test_regime_exit_only_overrides_take_profit() -> None:
    """V2.40.1: EXIT_ONLY tiene precedencia ABSOLUTA sobre el take-profit.

    Antes solo se forzaba la venta total cuando la decisión era ``hold``, así que un
    ``TAKE_PROFIT`` (mark ≥ T1) prevalecía y dejaba el 70% de la posición abierta contra
    la política declarada (solo SIM/cuenta simulada, pero riesgo real de diseño).
    """
    result = manage_position(
        _open_long(), mark_price=105.0, regime="UNKNOWN", template_id="moderate"
    )
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == 10.0
    assert REGIME_EXIT in result.exit_reasons


def test_time_stop_exits() -> None:
    result = manage_position(
        _open_long(),
        mark_price=101.0,
        regime="BULL_TREND",
        now="2026-09-15T10:00:00Z",
        expires_at="2026-09-15T09:00:00Z",
    )
    assert result is not None
    assert result.order_action == "sell"
    assert "time_stop" in result.exit_reasons


def test_closed_or_none_position_returns_none() -> None:
    assert manage_position(None, mark_price=100.0) is None
    closed = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAPL",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    from bolsa_analytics.cognitive.position_state import apply_position_reduce

    closed_pos = apply_position_reduce(closed, 10.0, exit_price=100.0)
    assert closed_pos is not None
    assert manage_position(closed_pos, mark_price=100.0) is None


def test_result_to_dict_shape() -> None:
    result = manage_position(_open_long(), mark_price=95.0, regime="BULL_TREND")
    assert result is not None
    d = result.to_dict()
    assert d["positionId"] == "pos-1"
    assert d["orderAction"] == "sell"
    assert d["positionDecision"]["action"] == "EXIT"
    assert "position" in d


# ── AUTO-1A: los skips de gestión dejan de ser ``None`` mudo ───────────────────


def test_manage_position_outcome_declares_rejected_mark() -> None:
    """Un mark que el ``PositionState`` rechaza es un SKIP con motivo, no un ``None``.

    Antes, ``manage_position`` devolvía ``None`` y el llamante no podía distinguir
    "esta posición no se pudo gestionar" de "no había nada que hacer" (Auditoría 2):
    la posición quedaba viva y sin gestión, sin rastro en el journal.
    """
    from bolsa_application.auto_reason_codes import POSITION_MARK_REJECTED
    from bolsa_application.position_manager import PositionManagerSkip, manage_position_outcome

    outcome = manage_position_outcome(_open_long(), mark_price=0.0, regime="BULL_TREND")
    assert isinstance(outcome, PositionManagerSkip)
    assert outcome.reason == POSITION_MARK_REJECTED
    assert outcome.instrument_id == "AAPL"
    assert outcome.is_protective is False
    d = outcome.to_dict()
    assert d["kind"] == "position_skip"
    assert d["attention"] == "high"
    assert d["reason"] == POSITION_MARK_REJECTED
    assert d["instrumentId"] == "AAPL"
    # Retrocompatibilidad: el wrapper clásico sigue colapsando a ``None``.
    assert manage_position(_open_long(), mark_price=0.0, regime="BULL_TREND") is None


def test_manage_position_outcome_declares_decision_unavailable() -> None:
    """Sin decisión construible (p. ej. dirección inválida) ⇒ SKIP con motivo."""
    from dataclasses import replace as _replace

    from bolsa_application.auto_reason_codes import POSITION_DECISION_UNAVAILABLE
    from bolsa_application.position_manager import PositionManagerSkip, manage_position_outcome

    broken = _replace(_open_long(), direction="")
    outcome = manage_position_outcome(broken, mark_price=101.0, regime="BULL_TREND")
    assert isinstance(outcome, PositionManagerSkip)
    assert outcome.reason == POSITION_DECISION_UNAVAILABLE
    assert outcome.detail


def test_manage_position_outcome_matches_result_for_managed_position() -> None:
    from bolsa_application.position_manager import PositionManagerResult, manage_position_outcome

    outcome = manage_position_outcome(_open_long(), mark_price=95.0, regime="BULL_TREND")
    assert isinstance(outcome, PositionManagerResult)
    assert outcome.order_action == "sell"


def test_manage_position_outcome_benign_cases_stay_none() -> None:
    """Sin posición / cerrada / plana NO son skips: no hay nada que journalizar."""
    from bolsa_application.position_manager import manage_position_outcome

    assert manage_position_outcome(None, mark_price=100.0) is None


# ── V2.44 (AUTO-3 slice 2): el gobernador gobierna también la SALIDA ──────────
#
# Antes el ``RiskRegime``/``OperationalState`` solo vetaban APERTURAS: una posición
# abierta seguía gestionándose por objetivo/trailing aunque la cuenta estuviera en
# ``RISK_OFF``. Estos tests muerden esa frontera: el gobernador entra en el ciclo de vida
# con un motivo DECISORIO único (``primary_exit_reason``) y los secundarios declarados.


def test_risk_off_forces_full_risk_exit() -> None:
    from bolsa_application.position_manager import (
        RISK_EXIT,
        PositionManagerResult,
        manage_position_outcome,
    )

    position = _open_long()
    outcome = manage_position_outcome(
        position, mark_price=101.0, regime="BULL_TREND", risk_regime="RISK_OFF"
    )
    assert isinstance(outcome, PositionManagerResult)
    assert outcome.order_action == "sell"
    assert outcome.order_qty == position.remaining_quantity
    # ``RISK_EXIT`` va por delante de ``PORTFOLIO_RISK`` en la precedencia: el motivo
    # decisorio es la liquidación de riesgo, no la etiqueta genérica de cartera.
    assert outcome.primary_exit_reason == RISK_EXIT
    assert "portfolio_risk" in outcome.secondary_reasons


def test_risk_off_beats_take_profit() -> None:
    """Un T1 tocado NO puede dejar la posición abierta contra un ``RISK_OFF``."""
    position = _open_long()
    result = manage_position(
        position, mark_price=105.0, regime="BULL_TREND", risk_regime="RISK_OFF",
        template_id="moderate",
    )
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == position.remaining_quantity
    assert result.primary_exit_reason == "risk_exit"


def test_exit_only_drawdown_band_is_a_risk_exit() -> None:
    """La banda ``EXIT_ONLY`` es el mismo hecho de riesgo que ``RISK_OFF``."""
    position = _open_long()
    result = manage_position(
        position, mark_price=101.0, regime="BULL_TREND", drawdown_band="EXIT_ONLY"
    )
    assert result is not None
    assert result.order_action == "sell"
    assert result.primary_exit_reason == "risk_exit"


def test_halted_forces_kill_switch_total_sell() -> None:
    from bolsa_application.position_manager import KILL_SWITCH

    position = _open_long()
    result = manage_position(
        position, mark_price=101.0, regime="BULL_TREND", operational_state="HALTED"
    )
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == position.remaining_quantity
    assert result.primary_exit_reason == KILL_SWITCH


def test_regime_exit_outranks_risk_exit_in_attribution() -> None:
    """Un régimen exit-only + ``RISK_OFF`` emite UN motivo decisorio y el otro secundario."""
    result = manage_position(
        _open_long(), mark_price=101.0, regime="UNKNOWN", risk_regime="RISK_OFF"
    )
    assert result is not None
    assert result.primary_exit_reason == "regime_exit"
    assert "risk_exit" in result.secondary_reasons


def test_exit_only_operational_state_does_not_liquidate() -> None:
    """``EXIT_ONLY`` veta APERTURAS, no liquida por sí solo: la posición sigue viva."""
    result = manage_position(
        _open_long(),
        mark_price=101.0,
        regime="BULL_TREND",
        risk_regime="RISK_ON",
        operational_state="EXIT_ONLY",
    )
    assert result is not None
    assert result.order_action == "hold"
    assert result.exit_reasons == ()


def test_unknown_risk_regime_is_not_permissive() -> None:
    """Un valor de riesgo no reconocido ⇒ ``UNKNOWN`` ⇒ no se interpreta como RISK_ON."""
    result = manage_position(
        _open_long(), mark_price=101.0, regime="BULL_TREND", risk_regime="garbage"
    )
    assert result is not None
    assert result.order_action == "hold"


def test_portfolio_risk_and_manual_propagate() -> None:
    """``PORTFOLIO_RISK``/``MANUAL`` dejan de ser inalcanzables desde AUTO."""
    risk = manage_position(_open_long(), mark_price=105.0, regime="BULL_TREND",
                           portfolio_risk=True, template_id="moderate")
    assert risk is not None
    assert risk.order_action == "sell"
    assert risk.primary_exit_reason == "portfolio_risk"

    manual = manage_position(_open_long(), mark_price=105.0, regime="BULL_TREND",
                             manual=True, template_id="moderate")
    assert manual is not None
    assert manual.order_action == "sell"
    assert manual.primary_exit_reason == "manual"
