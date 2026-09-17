"""PositionManager — gestión operativa de posición abierta (AUTO 2.0 · P1).

Cablea los objetos cognitivos ya existentes (``PositionState`` + ``ExitPlan`` +
``PositionDecision``) en un único punto de gestión de posición del hot path AUTO,
sustituyendo el dict de posiciones en RAM + ``ProtectionConfig`` global.

Flujo por barra de mercado::

    mark → ExitPlan → PositionDecision → order intent (hold/reduce/sell + stop)

El manager NO ejecuta órdenes (SIM-only: solo decide la intención); la ejecución y la
reconciliación viven aguas abajo. Añade la salida por régimen (``REGIME_EXIT``) a nivel
de manager — sin tocar el ``ExitPlan`` existente — para no romper el contrato cognitivo:
si el régimen es exit-only (UNKNOWN/RISK_OFF) la intención es venta TOTAL con motivo
``regime_exit``, con **precedencia absoluta** sobre cualquier otra intención de gestión
(V2.40.1: antes solo se forzaba sobre un ``hold``, así que un ``REDUCE``/``TAKE_PROFIT``
podía ganarle a la política exit-only).

Sobre la reconciliación: el invariante de la casa es que la reconciliación veta
APERTURAS, nunca una salida protectora (ver
``test_v2_recon_status_never_blocks_protective_exit``). Un recon crítico se refleja en el
``ExitPlan``/``PositionDecision`` (y el llamante emite la venta con la cantidad CANÓNICA),
pero no se usa aquí como excepción que pudiera dejar una posición abierta contra un
régimen exit-only.

Fail-closed: posición inexistente/cerrada, mark inválido o dirección no soportada ⇒
``None`` (no se inventa una orden). Los stops que empeoran son rechazados por
``PositionState`` (H2), así que el manager hereda esa garantía.

AUTO-1A — ``manage_position_outcome`` distingue el ``None`` BENIGNO (nada que gestionar)
del hueco OPERATIVO (``PositionManagerSkip``: mark rechazado o decisión no construible).
``manage_position`` colapsa ambos a ``None`` (retrocompatible), pero el hot path AUTO usa
el tri-estado para que ningún tick quede sin rastro en el journal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.exit_policy import ExitPolicy
from bolsa_analytics.cognitive.market_regime_gate import regime_is_exit_only
from bolsa_analytics.cognitive.position_decision import (
    PositionDecision,
    build_position_decision,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    apply_position_mark,
)
from bolsa_application.auto_reason_codes import (
    POSITION_DECISION_UNAVAILABLE,
    POSITION_MARK_REJECTED,
)

OrderAction = Literal["hold", "reduce", "sell"]

# Motivo de salida por régimen (AUTO 2.0). No vive en ExitPlan (contrato cognitivo
# intacto); es una capa operativa del manager.
REGIME_EXIT = "regime_exit"


@dataclass(frozen=True, slots=True)
class PositionManagerSkip:
    """Gestión de posición NO realizada, con motivo explícito.

    ``mark_rejected`` = el ``PositionState`` rechazó el mark (precio no finito/<=0 o
    incoherente con el histórico) ⇒ la posición queda SIN gestionar en este tick.
    ``decision_unavailable`` = no se pudo construir la ``PositionDecision`` (p. ej. falta
    un dato obligatorio del contrato cognitivo) ⇒ no hay intención que ejecutar.

    Antes estos dos casos eran ``return None`` mudos: indistinguibles de un tick sin nada
    que hacer (Auditoría 2). Los literales son únicos y viven en ``auto_reason_codes``.
    """

    instrument_id: str
    reason: str
    detail: str = ""

    @property
    def is_protective(self) -> bool:
        """Un skip NUNCA es una salida: la posición sigue viva y sin gestión."""
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "position_skip",
            "instrumentId": self.instrument_id,
            "reason": self.reason,
            "detail": self.detail,
            "attention": "high",
        }


@dataclass(frozen=True, slots=True)
class PositionManagerResult:
    """Intención operativa de gestión de UNA posición abierta."""

    position: PositionState
    decision: PositionDecision
    order_action: OrderAction
    order_qty: float | None
    stop_update: float | None
    exit_reasons: tuple[str, ...]
    attention: str
    as_of: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "positionId": self.position.position_id,
            "instrumentId": self.position.instrument_id,
            "orderAction": self.order_action,
            "orderQty": self.order_qty,
            "stopUpdate": self.stop_update,
            "exitReasons": list(self.exit_reasons),
            "attention": self.attention,
            "positionDecision": self.decision.to_dict(),
            "position": self.position.to_dict(),
            "asOf": self.as_of,
        }


def _order_from_decision(
    decision: PositionDecision,
    position: PositionState,
) -> tuple[OrderAction, float | None, float | None]:
    """Mapea ``PositionDecision.action`` → (order_action, qty, stop_update)."""
    action = decision.action
    remaining = position.remaining_quantity
    if action == "EXIT":
        return "sell", remaining, None
    if action in ("REDUCE", "TAKE_PROFIT"):
        qty = decision.suggested_qty
        if qty is None or qty <= 0:
            return "hold", None, None
        if qty >= remaining - 1e-9:
            return "sell", remaining, None
        return "reduce", qty, None
    if action == "PROTECT":
        return "hold", None, decision.suggested_stop
    return "hold", None, None


def manage_position(
    position: PositionState | None,
    *,
    mark_price: float,
    regime: str | None = None,
    thesis_invalid: bool = False,
    portfolio_recon_status: str | None = None,
    expires_at: str | None = None,
    now: str | None = None,
    exit_policy: ExitPolicy | None = None,
    template_id: str | None = None,
    trail_hint: bool = False,
    trail_stop: float | None = None,
    at: str | None = None,
) -> PositionManagerResult | None:
    """Gestiona una posición abierta: mark + decisión + intención de orden.

    Devuelve ``None`` si no hay posición gestionable (fail-closed) **o si la gestión no
    pudo completarse** (mark rechazado / decisión no construible). El régimen exit-only
    fuerza venta total con motivo ``regime_exit`` con precedencia ABSOLUTA sobre
    cualquier otra intención (hold/reduce/take-profit/trailing).

    Retrocompatible: delega en ``manage_position_outcome`` y colapsa los motivos de
    no-gestión a ``None``. El llamante que necesite DISTINGUIR "no hay nada que hacer"
    de "no pude gestionar" usa ``manage_position_outcome`` (hot path AUTO).
    """
    outcome = manage_position_outcome(
        position,
        mark_price=mark_price,
        regime=regime,
        thesis_invalid=thesis_invalid,
        portfolio_recon_status=portfolio_recon_status,
        expires_at=expires_at,
        now=now,
        exit_policy=exit_policy,
        template_id=template_id,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
        at=at,
    )
    return outcome if isinstance(outcome, PositionManagerResult) else None


def manage_position_outcome(
    position: PositionState | None,
    *,
    mark_price: float,
    regime: str | None = None,
    thesis_invalid: bool = False,
    portfolio_recon_status: str | None = None,
    expires_at: str | None = None,
    now: str | None = None,
    exit_policy: ExitPolicy | None = None,
    template_id: str | None = None,
    trail_hint: bool = False,
    trail_stop: float | None = None,
    at: str | None = None,
) -> PositionManagerResult | PositionManagerSkip | None:
    """Como ``manage_position`` pero DEVOLVIENDO el motivo cuando no pudo gestionar.

    Tri-estado del ciclo de gestión de posición:

    * ``PositionManagerResult`` — gestionada (hold/reduce/sell/protect).
    * ``PositionManagerSkip`` — NO gestionada: mark rechazado o decisión no construible.
      El llamante DEBE journalizarlo con atención alta (la posición sigue viva y sin
      gestión, que es un estado operativo, no un no-op).
    * ``None`` — nada que gestionar (sin posición, cerrada o ya plana): benigno.
    """
    if position is None or position.status == "CLOSED":
        return None
    if position.remaining_quantity <= 0:
        return None

    instrument_id = str(getattr(position, "instrument_id", "") or "")
    marked = apply_position_mark(position, mark_price, at=at)
    if marked is None:
        return PositionManagerSkip(
            instrument_id=instrument_id,
            reason=POSITION_MARK_REJECTED,
            detail=f"mark_price={mark_price!r}",
        )

    decision = build_position_decision(
        marked,
        mark_price=mark_price,
        exit_policy=exit_policy,
        template_id=template_id,
        portfolio_recon_status=portfolio_recon_status,
        thesis_invalid=thesis_invalid,
        at=at,
        now=now,
        expires_at=expires_at,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
    )
    if decision is None:
        return PositionManagerSkip(
            instrument_id=instrument_id,
            reason=POSITION_DECISION_UNAVAILABLE,
            detail=f"mark_price={mark_price!r} recon={portfolio_recon_status!r}",
        )

    order_action, order_qty, stop_update = _order_from_decision(decision, marked)

    exit_reasons: list[str] = []
    if decision.primary_reason:
        exit_reasons.append(decision.primary_reason.lower())

    # Salida por régimen (AUTO 2.0 · V2.40.1): precedencia ABSOLUTA. El régimen exit-only
    # pide deshacer riesgo, así que no compite con la gestión normal: ignora hold, reduce,
    # take-profit, trailing y cualquier actualización de stop, y emite venta TOTAL.
    # Antes solo se forzaba cuando la decisión era ``hold``, de modo que en ``UNKNOWN``/
    # ``RISK_OFF`` un ``REDUCE`` o un ``TAKE_PROFIT`` podían prevalecer y dejar posición
    # abierta contra la política declarada (exit-only ⇒ deshacer, no "gestionar un poco").
    if regime_is_exit_only(regime):
        order_action = "sell"
        order_qty = marked.remaining_quantity
        stop_update = None
        exit_reasons.append(REGIME_EXIT)

    return PositionManagerResult(
        position=marked,
        decision=decision,
        order_action=order_action,
        order_qty=order_qty,
        stop_update=stop_update,
        exit_reasons=tuple(dict.fromkeys(exit_reasons)),
        attention=decision.attention,
        as_of=decision.market_as_of or "",
    )
