"""V1.27 — paridad PositionDecision / ExitPolicy."""

from bolsa_analytics.cognitive.exit_policy import (
    AGGRESSIVE_SWING_EXIT_POLICY,
    MODERATE_EXIT_POLICY,
    suggestion_from_exit_policy,
)
from bolsa_analytics.cognitive.position_decision import build_position_decision
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill


def _pos():
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAPL",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 105.0,
            "target2": 110.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-28T10:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


def test_legacy_t1_halves_without_policy() -> None:
    action, qty, _stop = suggestion_from_exit_policy("TARGET_1", 10.0, None)
    assert action == "reduce"
    assert qty == 5.0


def test_moderate_t1_reduces_30() -> None:
    action, qty, _stop = suggestion_from_exit_policy("TARGET_1", 10.0, MODERATE_EXIT_POLICY)
    assert action == "reduce"
    assert qty == 3.0


def test_aggressive_t1_holds() -> None:
    action, qty, _stop = suggestion_from_exit_policy(
        "TARGET_1", 10.0, AGGRESSIVE_SWING_EXIT_POLICY
    )
    assert action == "hold"
    assert qty is None


def test_decision_hold_next_t1() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        template_id="moderate",
        portfolio_recon_status="clean",
    )
    assert d is not None
    assert d.action == "HOLD"
    assert d.attention == "NORMAL"
    assert d.next_event == "T1"
    assert d.protection == "ACTIVE"
    assert d.urgency == "LOW"
    assert 0 <= d.confidence <= 1
    assert 0 <= d.evidence_strength <= 1
    assert d.recon_health == "CLEAN"


def test_decision_t1_moderate_take_profit() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=105.0,
        exit_policy=MODERATE_EXIT_POLICY,
        portfolio_recon_status="ok",
    )
    assert d is not None
    assert d.action == "TAKE_PROFIT"
    assert d.suggested_qty == 3.0
    assert d.attention == "ATTENTION"


def test_decision_thesis_invalidated_exits() -> None:
    """D2 (2b): la invalidación CONFIRMADA vende; ya no se queda en ``REVIEW``."""
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        thesis_invalid=True,
        portfolio_recon_status="clean",
    )
    assert d is not None
    assert d.action == "EXIT"
    assert d.attention == "URGENT"
    assert d.primary_reason == "THESIS_INVALIDATION"


def test_decision_thesis_invalidated_under_critical_exits() -> None:
    """S-2: la invalidación CONFIRMADA es una salida PROTECTORA, también bajo ``CRITICAL``.

    Antes esta rama devolvía ``REVIEW`` mientras F5 ya la trataba como protectora: la misma
    condición era «cubre riesgo» para una capa y «espera» para la otra, y la posición
    sobrevivía a su propia invalidación cuando el libro estaba en drift. La tesis rota
    significa que la razón para mantener la posición ya no existe: seguir dentro es
    exposición sin tesis, no una espera.
    """
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        thesis_invalid=True,
        portfolio_recon_status="drift",
    )
    assert d is not None
    assert d.action == "EXIT"
    assert d.primary_reason == "THESIS_INVALIDATION"


def test_decision_time_stop_under_critical_still_reviews() -> None:
    """Control negativo: «deshacer riesgo no espera» no es «toda salida espera menos».

    Una salida por TIEMPO no es cubrirse —el plan vence, no hay pérdida en curso—, así que
    bajo ``CRITICAL`` sigue degradando a ``REVIEW``. Si esta prueba cambia, se ha metido
    ``TIME_STOP`` en el conjunto protector por accidente.
    """
    d = build_position_decision(
        _pos(),
        mark_price=101.0,
        now="2026-09-30T10:00:00Z",
        expires_at="2026-09-29T10:00:00Z",
        portfolio_recon_status="drift",
    )
    assert d is not None
    assert d.action == "REVIEW"


def test_decision_take_profit_under_critical_still_reviews() -> None:
    """Control negativo: tomar beneficio puede esperar a que el libro cuadre."""
    d = build_position_decision(
        _pos(),
        mark_price=105.0,
        portfolio_recon_status="drift",
    )
    assert d is not None
    assert d.action == "REVIEW"


def test_both_layers_share_one_protective_set() -> None:
    """S-2 estructural: una sola tabla, no dos copias que puedan divergir.

    La prueba no compara contenido (para eso basta leer la constante): afirma **identidad**
    de origen. Si alguien reintroduce una lista local en cualquiera de las dos capas, esto
    se rompe antes de que las capas vuelvan a discrepar.
    """
    from bolsa_analytics.cognitive import exit_permission, position_decision
    from bolsa_analytics.cognitive.exit_plan import PROTECTIVE_EXIT_REASONS

    assert position_decision._PROTECTIVE_EXIT_REASONS == PROTECTIVE_EXIT_REASONS
    assert exit_permission.PROTECTIVE_EXIT_REASONS is PROTECTIVE_EXIT_REASONS
    # Y lo que de verdad importa: los motivos que NO entran, declarados.
    for reason in ("TIME_STOP", "MANUAL", "TARGET_1", "TARGET_2"):
        assert reason not in PROTECTIVE_EXIT_REASONS


def test_decision_time_stop_exits_with_time_next_event() -> None:
    """E1 (2b): el techo de mantenimiento genera una salida REAL con motivo propio."""
    d = build_position_decision(
        _pos(),
        mark_price=101.0,
        now="2026-09-30T10:00:00Z",
        expires_at="2026-09-29T10:00:00Z",
        portfolio_recon_status="clean",
    )
    assert d is not None
    assert d.action == "EXIT"
    assert d.primary_reason == "TIME_STOP"
    assert d.next_event == "TIME"
    assert d.suggested_qty == 10.0


def test_decision_recon_drift_blocks() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        portfolio_recon_status="drift",
    )
    assert d is not None
    assert d.recon_health == "CRITICAL"
    assert d.attention == "BLOCKED"
    assert d.action == "REVIEW"
    assert d.next_event == "RECONCILIATION"
    assert d.reason == "reconciliation:portfolio_drift"
