"""AUTO-2 (V2.42) — stop real, FSM y motor único de protección (hermético).

Cubre tres contratos que antes no existían:

1. ``position_manager_stop_update`` **no descarta** el stop que propone un ``PROTECT``
   (antes ``position_manager_package`` sólo leía ``order_action``/``order_qty`` y
   ``current_stop`` quedaba congelado en el valor de nacimiento: ni break-even ni
   trailing existían en AUTO).
2. ``ProtectionConfig`` deja de ser un motor: el shim ``protection_compat`` reproduce
   los umbrales legacy ``v2.39.x`` (flag-off congelado) y traduce sus motivos al
   vocabulario del FSM.
3. Invariante de oro (roadmap): **ninguna salida protectora se veta** por reconciliación
   degradada — el stop sigue subiendo y el SELL protector se emite.

Hermético: sin PG, sin red, sin reloj real.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from bolsa_analytics.cognitive.exit_policy import (
    MODERATE_EXIT_POLICY,
    resolve_exit_policy,
)
from bolsa_analytics.cognitive.position_decision import build_position_decision
from bolsa_analytics.cognitive.position_lifecycle import (
    advance_lifecycle,
    compute_trail_stop,
    is_trail_armed,
    trailing_state_dict,
    trailing_status,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    apply_position_reduce,
    build_position_state_from_fill,
    derive_position_status,
)
from bolsa_application.auto_v2_entry import (
    plan_v2_position_outcome,
    position_manager_package,
    position_manager_stop_update,
)
from bolsa_application.position_manager import manage_position_outcome
from bolsa_application.protection_compat import (
    PROTECTIVE_STOP,
    SESSION_CLOSE,
    T1_EXIT,
    TRAILING_STOP,
    ProtectionPolicy,
    lifecycle_event_for_protection_reason,
    protection_exit_fraction,
    protection_exit_reason,
)

_AT = "2026-09-17T10:00:00Z"


def _open_long(*, stop: float = 95.0, qty: float = 10.0) -> PositionState:
    plan = {
        "decisionId": "dec-auto2",
        "instrumentId": "AAPL",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": stop,
        "target1": 105.0,
        "target2": 110.0,
    }
    return build_position_state_from_fill(
        plan, fill_price=100.0, fill_quantity=qty, position_id="pos-auto2"
    )


# --------------------------------------------------------------------------- #
# 1. El stop propuesto deja de descartarse
# --------------------------------------------------------------------------- #


def test_position_manager_stop_update_surfaces_protect() -> None:
    """Un ``PROTECT`` no emite orden (spine intacto) pero SÍ surface su stop."""
    outcome = plan_v2_position_outcome(
        _open_long(),
        mark_price=101.0,
        regime="BULL_TREND",
        trail_hint=True,
        trail_stop=98.0,
        at=_AT,
    )
    assert outcome is not None
    assert outcome.decision.action == "PROTECT"  # type: ignore[union-attr]
    # El spine no cambia: PROTECT no inventa una orden.
    assert position_manager_package(outcome) is None  # type: ignore[arg-type]
    # Pero el stop YA no se pierde.
    assert position_manager_stop_update(outcome) == 98.0  # type: ignore[arg-type]


def test_position_manager_stop_update_none_on_full_exit() -> None:
    """Una venta total no propone stop (el cierre no necesita ratchet)."""
    outcome = plan_v2_position_outcome(
        _open_long(), mark_price=95.0, regime="BULL_TREND", at=_AT
    )
    assert outcome is not None
    assert outcome.order_action == "sell"  # type: ignore[union-attr]
    assert position_manager_stop_update(outcome) is None  # type: ignore[arg-type]


def test_position_manager_stop_update_rejects_garbage() -> None:
    """Fail-closed: ``None``, NaN, 0 y negativos no son stops utilizables."""
    assert position_manager_stop_update(None) is None

    outcome = plan_v2_position_outcome(
        _open_long(), mark_price=101.0, regime="BULL_TREND", at=_AT
    )
    assert outcome is not None
    for garbage in (None, float("nan"), 0.0, -3.0):
        assert position_manager_stop_update(replace(outcome, stop_update=garbage)) is None  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 2. Política de salida: una sola fuente (MODERATE 0.3/0.3)
# --------------------------------------------------------------------------- #


def test_exit_policy_has_single_source_moderate() -> None:
    """``resolve_exit_policy(None)`` es MODERATE: no hay camino AUTO a 0.5/1.0."""
    assert resolve_exit_policy(None) == MODERATE_EXIT_POLICY
    assert (MODERATE_EXIT_POLICY.t1_reduce_fraction, MODERATE_EXIT_POLICY.t2_reduce_fraction) == (
        0.3,
        0.3,
    )
    assert resolve_exit_policy("moderate") == resolve_exit_policy(None)


def test_t1_reduce_is_moderate_without_template() -> None:
    """Sin ``template_id`` (el camino que antes caía a 0.5) T1 reduce 30%."""
    without = build_position_decision(_open_long(), mark_price=105.0, at=_AT)
    with_moderate = build_position_decision(
        _open_long(), mark_price=105.0, template_id="moderate", at=_AT
    )
    assert without is not None and with_moderate is not None
    assert without.action == "TAKE_PROFIT"
    assert without.suggested_qty == 3.0  # 0.3 de 10, NO 0.5
    assert without.suggested_qty == with_moderate.suggested_qty


# --------------------------------------------------------------------------- #
# 3. protection_compat: shim, no motor
# --------------------------------------------------------------------------- #


def _policy(**kwargs: object) -> ProtectionPolicy:
    base: dict[str, object] = {"enabled": True}
    base.update(kwargs)
    return ProtectionPolicy(**base)  # type: ignore[arg-type]


def test_legacy_policy_reproduces_v239_thresholds() -> None:
    """Los cuatro motivos legacy con sus umbrales porcentuales exactos."""
    policy = _policy()
    entry = Decimal("100")
    cases = [
        # (precio, máximo, minuto, motivo esperado)
        (Decimal("97.5"), Decimal("100"), 0, PROTECTIVE_STOP),
        (Decimal("103"), Decimal("100"), 0, T1_EXIT),
        # Máximo por encima de T1 + retroceso >= 1.5% ⇒ trailing, NO t1_exit (orden manda).
        (Decimal("101.5"), Decimal("103.5"), 0, TRAILING_STOP),
        # ... aunque el precio SIGA por encima de T1 (+5%): retroceso real desde el máximo.
        (Decimal("105"), Decimal("110"), 0, TRAILING_STOP),
        # Retroceso sin haber rebasado T1 ⇒ trailing simple.
        (Decimal("98.6"), Decimal("100.5"), 0, TRAILING_STOP),
        (Decimal("101"), Decimal("101"), 0, None),
    ]
    for price, high, minute, expected in cases:
        got = protection_exit_reason(
            policy, held=True, entry=entry, high=high, price=price, minute=minute
        )
        assert got == expected, f"price={price} high={high} minute={minute}: {got} != {expected}"
    # Fin de sesión: sólo con ``session_end_minute`` configurado (>0) y manda sobre todo.
    session = _policy(session_end_minute=600)
    assert (
        protection_exit_reason(
            session,
            held=True,
            entry=entry,
            high=Decimal("100"),
            price=Decimal("100"),
            minute=600,
        )
        == SESSION_CLOSE
    )
    assert (
        protection_exit_reason(
            session,
            held=True,
            entry=entry,
            high=Decimal("100"),
            price=Decimal("97"),
            minute=599,
        )
        == PROTECTIVE_STOP
    )


def test_legacy_policy_fail_closed() -> None:
    """Sin activar, sin posición o sin precios válidos no hay salida automática."""
    entry = Decimal("100")
    assert (
        protection_exit_reason(
            _policy(enabled=False),
            held=True,
            entry=entry,
            high=entry,
            price=Decimal("50"),
            minute=0,
        )
        is None
    )
    assert (
        protection_exit_reason(
            _policy(), held=False, entry=entry, high=entry, price=Decimal("50"), minute=0
        )
        is None
    )
    assert (
        protection_exit_reason(
            _policy(), held=True, entry=Decimal("0"), high=entry, price=Decimal("50"), minute=0
        )
        is None
    )


def test_legacy_policy_methods_delegate_to_module() -> None:
    """La dataclass es value object: su lógica vive en el módulo (dueño único)."""
    policy = _policy(t1_fraction=0.5)
    for price, high in ((Decimal("97.5"), Decimal("100")), (Decimal("103"), Decimal("100"))):
        delegated = policy.exit_reason(
            held=True, entry=Decimal("100"), high=high, price=price, minute=0
        )
        assert delegated == protection_exit_reason(
            policy, held=True, entry=Decimal("100"), high=high, price=price, minute=0
        )
    assert policy.exit_fraction(T1_EXIT) == 0.5 == protection_exit_fraction(policy, T1_EXIT)
    assert policy.exit_fraction(PROTECTIVE_STOP) == 1.0
    assert policy.exit_fraction(None) == 1.0


def test_legacy_reason_translates_to_fsm_event() -> None:
    """Un vocabulario, dos superficies: la traducción no vuelve a decidir."""
    assert lifecycle_event_for_protection_reason(PROTECTIVE_STOP) == "EXIT_REQUESTED"
    assert lifecycle_event_for_protection_reason(SESSION_CLOSE) == "EXIT_REQUESTED"
    assert lifecycle_event_for_protection_reason(T1_EXIT) == "T1_HIT"
    assert lifecycle_event_for_protection_reason(TRAILING_STOP) == "PROTECT_APPLIED"
    assert lifecycle_event_for_protection_reason(None) is None
    assert lifecycle_event_for_protection_reason("invented") is None


# --------------------------------------------------------------------------- #
# 4. Invariante de oro: la protección no se veta por reconciliación
# --------------------------------------------------------------------------- #


def test_stop_hit_still_sells_with_recon_drift() -> None:
    """DIVERGENT ⇒ CRITICAL ⇒ REVIEW, salvo salida protectora: el stop rebasado VENDE."""
    outcome = plan_v2_position_outcome(
        _open_long(),
        mark_price=95.0,
        regime="BULL_TREND",
        portfolio_recon_status="drift",
        at=_AT,
    )
    assert outcome is not None
    assert outcome.order_action == "sell"  # type: ignore[union-attr]
    assert outcome.order_qty == 10.0  # type: ignore[union-attr]
    assert "structural_stop" in outcome.exit_reasons  # type: ignore[union-attr]
    assert outcome.attention == "BLOCKED"  # type: ignore[union-attr]
    assert outcome.decision.recon_health == "CRITICAL"  # type: ignore[union-attr]


def test_ratchet_still_applies_with_recon_drift() -> None:
    """El trailing sigue proponiendo stop (y subiéndolo) aunque el libro no cuadre."""
    outcome = plan_v2_position_outcome(
        _open_long(),
        mark_price=101.0,
        regime="BULL_TREND",
        portfolio_recon_status="drift",
        trail_hint=True,
        trail_stop=98.0,
        at=_AT,
    )
    assert outcome is not None
    assert position_manager_stop_update(outcome) == 98.0  # type: ignore[arg-type]


def test_take_profit_still_waits_for_recon() -> None:
    """El límite del invariante: tomar beneficio SÍ puede esperar al veredicto."""
    outcome = plan_v2_position_outcome(
        _open_long(),
        mark_price=105.0,
        regime="BULL_TREND",
        portfolio_recon_status="drift",
        at=_AT,
    )
    assert outcome is not None
    assert outcome.order_action == "hold"  # type: ignore[union-attr]
    assert outcome.decision.action == "REVIEW"  # type: ignore[union-attr]


def test_degraded_lifecycle_keeps_protection_and_reverifies() -> None:
    """``RECONCILIATION_REQUIRED`` no deja la posición sin salida ni sin ratchet."""
    degraded = replace(_open_long(), lifecycle_state="RECONCILIATION_REQUIRED")
    outcome = manage_position_outcome(
        degraded, mark_price=95.0, regime="BULL_TREND", at=_AT
    )
    assert outcome is not None
    assert outcome.order_action == "sell"

    ratchet = manage_position_outcome(
        degraded,
        mark_price=101.0,
        regime="BULL_TREND",
        trail_hint=True,
        trail_stop=98.0,
        at=_AT,
    )
    assert ratchet is not None
    assert position_manager_stop_update(ratchet) == 98.0

    # Un hecho observable (ratchet aplicado) RE-VERIFICA el estado: la degradación se
    # declara, no se esconde, y no es un pozo sin salida.
    reverified, transition = advance_lifecycle(
        degraded, "PROTECT_APPLIED", at=_AT
    )
    assert transition.accepted is True
    assert reverified.lifecycle_state == "PROTECTED"


# --------------------------------------------------------------------------- #
# 5. Portes V2=1 de la cobertura legacy (§6.3 del plan)
#
# Los 5 tests de ``test_a9_1_durability_integrity.py`` siguen cubriendo el shim
# flag-off; su semántica se porta aquí a la V2 real (trailing en R, high-watermark
# persistido y objetivo T1 que deja de competir tras alcanzarse). El porte del
# reinicio con watermark vive en
# ``apps/api-python/tests/test_auto_v2_worker_integration.py``
# (``test_v2_restart_rehydrates_trailing_and_keeps_ratcheting``).
# --------------------------------------------------------------------------- #


def test_v2_trail_in_r_replaces_legacy_pct_and_wins_over_t1() -> None:
    """Porte de ``test_exit_reason_trailing_wins_over_t1`` a la distancia en R.

    Legacy: un retroceso ≥ ``trailing_pct`` (1,5 % desde 110 ⇒ 108,35) se etiquetaba
    ``trailing_stop`` aunque el precio siguiera por encima de T1. V2: el trailing es un
    stop REAL (riesgo 5, anchura ``medium`` 1.0R ⇒ 110 − 5 = **105**, no 108,35) y, con T1
    ya alcanzado, el objetivo deja de competir: el precio que lo toca sale por stop y el
    que queda por encima sólo declara trail con su ratchet.
    """
    t1_done = replace(
        _open_long(),
        current_stop=105.0,
        target1_achieved_at=_AT,
        lifecycle_state="T1_REACHED",
        trailing=trailing_state_dict(status="armed", high_watermark=110.0, at=_AT),
    )
    trail_stop = compute_trail_stop(t1_done, trail_width="medium", high_watermark=110.0)
    assert trail_stop == 105.0, "R: 110 − 1.0 × 5; NO el 1,5 % legacy (108,35)"

    # Tocado: la posición sale protegida por stop, no "por objetivo".
    touched = plan_v2_position_outcome(
        t1_done, mark_price=104.9, regime="BULL_TREND", trail_hint=True, trail_stop=trail_stop
    )
    assert touched is not None
    assert touched.order_action == "sell"
    assert "structural_stop" in touched.exit_reasons
    assert "target_1" not in touched.exit_reasons

    # Por encima del stop: no vende, pero el trail SÍ propone el stop nuevo.
    above = plan_v2_position_outcome(
        t1_done, mark_price=105.5, regime="BULL_TREND", trail_hint=True, trail_stop=trail_stop
    )
    assert above is not None
    assert "trail" in above.exit_reasons
    assert "target_1" not in above.exit_reasons
    # PROTECT no emite orden (spine intacto) pero surface su stop: el ratchet sigue.
    assert above.decision.action == "PROTECT"
    assert position_manager_stop_update(above) == 105.0


def test_v2_t1_reduces_when_no_retracement() -> None:
    """Porte de ``test_exit_reason_t1_when_no_retracement``: sin retroceso manda T1.

    El precio rebasa T1 y el trailing NO está armado (no hay hecho T1 ni pico): la
    gestión correcta es la reducción MODERATE, no una salida total ni un trail inventado.
    """
    outcome = plan_v2_position_outcome(
        _open_long(), mark_price=105.5, regime="BULL_TREND", at=_AT
    )
    assert outcome is not None
    assert outcome.order_action == "reduce"
    assert outcome.order_qty == 3.0, "0.3 de 10 (MODERATE), no el 0.5 del fallback"
    assert "target_1" in outcome.exit_reasons
    assert "trail" not in outcome.exit_reasons


def test_v2_t1_partial_fraction_matches_legacy_shim() -> None:
    """Porte de ``test_t1_partial_fraction``: una sola fracción de T1 (0.3) y stop 1.0."""
    assert MODERATE_EXIT_POLICY.t1_reduce_fraction == 0.3
    legacy = _policy(t1_pct=0.02, t1_fraction=0.3)
    assert protection_exit_fraction(legacy, T1_EXIT) == 0.3
    assert protection_exit_fraction(legacy, PROTECTIVE_STOP) == 1.0
    # La reducción REAL del camino V2 coincide con la fracción declarada del shim.
    outcome = plan_v2_position_outcome(
        _open_long(), mark_price=105.0, regime="BULL_TREND", at=_AT
    )
    assert outcome is not None and outcome.order_qty == 3.0


def test_v2_t1_partial_leaves_residual_lifecycle() -> None:
    """Porte de ``test_t1_partial_leaves_residual_position`` al FSM explícito.

    El T1 parcial deja cola viva: el hecho de cantidad manda en ``status`` (``PARTIAL``)
    y el FSM registra ``T1_HIT → PARTIAL_FILL``, con el trailing ARMADO por haber
    alcanzado T1 (de donde cuelga el ratchet real).
    """
    hit, t1 = advance_lifecycle(_open_long(), "T1_HIT", at=_AT, mark_trailing=True)
    assert t1.accepted is True and hit.lifecycle_state == "T1_REACHED"
    assert trailing_status(hit) == "armed" and is_trail_armed(hit) is True

    reduced = apply_position_reduce(
        hit, 3.0, exit_price=105.0, at=_AT, mark_target1_achieved=True
    )
    assert reduced is not None
    assert reduced.remaining_quantity == 7.0, "deja cola, no cierra"

    partial, t2 = advance_lifecycle(reduced, "PARTIAL_FILL", at=_AT, mark_trailing=True)
    assert t2.accepted is True and partial.lifecycle_state == "PARTIAL_EXIT"
    assert partial.status == "PARTIAL" == derive_position_status(partial)
    assert trailing_status(partial) == "armed", "el parcial no desarma el trailing"
