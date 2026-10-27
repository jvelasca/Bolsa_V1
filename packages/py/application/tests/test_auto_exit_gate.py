"""S-6 — F5 (``ExitPermission``) consultado por el AUTO antes de una salida.

Contrato declarado en ``bolsa_application.auto_exit_gate``:

* la consulta se hace sobre el **mismo ``ExitPlan``** que produjo la decisión;
* el veredicto **no** bloquea la salida en AUTO SIM (``blocks_exit is False``), pero un
  ``DENY`` viaja con su exención declarada en vez de desaparecer;
* sin plan (camino legacy) F5 responde ``missing_exit_plan``: se confiesa el hueco, no se
  inventa un plan para poder decir «ALLOW».
"""

from __future__ import annotations

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.auto_exit_gate import (
    AUTO_EXIT_EXEMPTION,
    AUTO_EXIT_PERMISSION_EVENT,
    review_auto_exit,
)
from bolsa_application.position_manager import manage_position_outcome


def _open_long():
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


# ── el contrato que la auditoría pedía escribir ──────────────────────────────────────


def test_target_exit_is_clicked_by_f5_and_still_emitted_by_contract() -> None:
    """Con dato rancio, ``TARGET_1`` recibe DENY y **aun así** la salida se emite.

    Es la decisión de arquitectura de la casa, ahora declarada: bloquear un objetivo por
    un dato rancio no reduce exposición y cambiaría la serie de fills del simulador.
    """
    outcome = manage_position_outcome(
        _open_long(), mark_price=105.0, regime="BULL_TREND", template_id="moderate"
    )
    assert outcome is not None
    assert outcome.order_action == "reduce"
    review = review_auto_exit(outcome.exit_plan, data_stale=True)

    assert review.protective is False, "TARGET_1 no es una salida protectora"
    assert review.denied is True
    assert review.permission.reasons == ("data_stale",)
    assert review.exemption == AUTO_EXIT_EXEMPTION
    assert review.blocks_exit is False, "el AUTO no bloquea la salida: contrato S-6"
    # La consulta NO reescribe la intención: la venta sigue en pie.
    assert outcome.order_action == "reduce"
    assert outcome.order_qty == 3.0


def test_protective_exit_is_allowed_even_with_stale_data() -> None:
    """El stop no espera: F5 lo deja pasar con el mismo dato rancio (control positivo).

    Sin este caso, ``review_auto_exit`` podría estar devolviendo ``DENY`` siempre y el
    primer test seguiría verde.
    """
    outcome = manage_position_outcome(
        _open_long(), mark_price=95.0, regime="BULL_TREND", template_id="moderate"
    )
    assert outcome is not None
    assert outcome.order_action == "sell"
    review = review_auto_exit(outcome.exit_plan, data_stale=True)

    assert review.protective is True
    assert review.permission.allowed is True
    assert review.permission.reasons == ()
    assert review.exemption is None


def test_missing_plan_is_confessed_not_invented() -> None:
    """Sin ``ExitPlan`` F5 dice ``missing_exit_plan`` (no se fabrica un permiso)."""
    review = review_auto_exit(None, data_stale=True)

    assert review.denied is True
    assert review.permission.reasons == ("missing_exit_plan",)
    assert review.exemption == AUTO_EXIT_EXEMPTION
    assert review.blocks_exit is False


def test_drift_denies_only_non_protective_exits() -> None:
    """La asimetría de F5 se mantiene: el drift veta el objetivo, no el stop."""
    target = manage_position_outcome(
        _open_long(), mark_price=105.0, regime="BULL_TREND", template_id="moderate"
    )
    stop = manage_position_outcome(
        _open_long(), mark_price=95.0, regime="BULL_TREND", template_id="moderate"
    )
    assert target is not None and stop is not None

    assert review_auto_exit(target.exit_plan, portfolio_drift=True).permission.reasons == (
        "portfolio_drift",
    )
    assert review_auto_exit(stop.exit_plan, portfolio_drift=True).permission.allowed is True


# ── el plan juzgado es el que decidió ───────────────────────────────────────────────


def test_manager_exposes_the_plan_that_produced_the_decision() -> None:
    """``PositionManagerResult.exit_plan`` = el plan de la decisión (no una copia)."""
    outcome = manage_position_outcome(
        _open_long(), mark_price=105.0, regime="BULL_TREND", template_id="moderate"
    )
    assert outcome is not None
    assert outcome.exit_plan is not None
    assert outcome.exit_plan.primary_reason == outcome.decision.primary_reason
    assert outcome.exit_plan.position_id == outcome.position.position_id

    blob = outcome.to_dict()
    assert blob["exitPlanId"] == outcome.exit_plan.exit_plan_id
    assert blob["exitPlanStatus"] == outcome.exit_plan.status


def test_the_permission_event_name_is_declared_once() -> None:
    """El ``reasonCode`` del journal vive en el módulo, no suelto en el worker."""
    assert AUTO_EXIT_PERMISSION_EVENT == "exit_permission"


def test_the_permission_code_is_a_position_attribution_not_an_entry_veto() -> None:
    """S-6 — el código queda en el dueño único y **no** engorda el censo de vetos.

    ``exit_permission`` acompaña a una salida que **salió**: si el lector de operabilidad lo
    tratara como veto, un DENY exento se leería como «apertura bloqueada» y el censo mentiría.
    """
    from bolsa_application.auto_reason_codes import (
        EXIT_PERMISSION,
        POSITION_ATTRIBUTION_REASONS,
    )
    from bolsa_application.market_operability import VETO_BUCKET_BY_REASON

    assert EXIT_PERMISSION == AUTO_EXIT_PERMISSION_EVENT
    assert EXIT_PERMISSION in POSITION_ATTRIBUTION_REASONS
    assert EXIT_PERMISSION not in VETO_BUCKET_BY_REASON
