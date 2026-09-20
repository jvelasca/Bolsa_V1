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
from bolsa_analytics.cognitive.operational_governor import (
    coerce_drawdown_band,
    coerce_operational_state,
    coerce_risk_regime,
)
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

# V2.44: el gobernador entra en la gestión de posición. Los motivos canónicos (mayúsculas)
# viven en ``exit_plan.ExitReason``; aquí se declaran los literales que el manager emite
# para que el journal y los tests no dependan de strings sueltos.
KILL_SWITCH = "kill_switch"
RISK_EXIT = "risk_exit"


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

    @property
    def primary_exit_reason(self) -> str:
        """Motivo DECISORIO único (canónico, minúsculas) o ``"managed"`` si no hay."""
        return self.exit_reasons[0] if self.exit_reasons else "managed"

    @property
    def secondary_reasons(self) -> tuple[str, ...]:
        """Motivos que también dispararon, por precedencia (V2.44).

        ``exit_reasons`` conserva el orden de ``EXIT_REASON_PRECEDENCE``, así que el
        primero es el decisorio y el resto son secundarios: el journal deja de perder la
        atribución múltiple sin inventar un segundo eje.
        """
        return self.exit_reasons[1:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "positionId": self.position.position_id,
            "instrumentId": self.position.instrument_id,
            "orderAction": self.order_action,
            "orderQty": self.order_qty,
            "stopUpdate": self.stop_update,
            "exitReasons": list(self.exit_reasons),
            "primaryExitReason": self.primary_exit_reason,
            "secondaryReasons": list(self.secondary_reasons),
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
    manual: bool = False,
    portfolio_risk: bool = False,
    risk_regime: str | None = None,
    drawdown_band: str | None = None,
    operational_state: str | None = None,
) -> PositionManagerResult | None:
    """Gestiona una posición abierta: mark + decisión + intención de orden.

    Devuelve ``None`` si no hay posición gestionable (fail-closed) **o si la gestión no
    pudo completarse** (mark rechazado / decisión no construible).

    V2.44 — el GOBERNADOR gobierna también el ciclo de vida, no solo la entrada:

    * ``regime`` exit-only (``UNKNOWN``/``RISK_OFF``) ⇒ ``REGIME_EXIT`` (venta total).
    * ``risk_regime == RISK_OFF`` (o banda de drawdown ``EXIT_ONLY``) ⇒ ``RISK_EXIT``.
    * ``operational_state == HALTED`` ⇒ ``KILL_SWITCH`` (venta total forzada).
    * ``manual``/``portfolio_risk`` se propagan tal cual (antes eran inalcanzables).

    Los tres motivos del gobernador tienen **precedencia absoluta** sobre hold/reduce/
    take-profit/trailing (una salida de reducción de riesgo no compite con la gestión).

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
        manual=manual,
        portfolio_risk=portfolio_risk,
        risk_regime=risk_regime,
        drawdown_band=drawdown_band,
        operational_state=operational_state,
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
    manual: bool = False,
    portfolio_risk: bool = False,
    risk_regime: str | None = None,
    drawdown_band: str | None = None,
    operational_state: str | None = None,
) -> PositionManagerResult | PositionManagerSkip | None:
    """Como ``manage_position`` pero DEVOLVIENDO el motivo cuando no pudo gestionar.

    Tri-estado del ciclo de gestión de posición:

    * ``PositionManagerResult`` — gestionada (hold/reduce/sell/protect).
    * ``PositionManagerSkip`` — NO gestionada: mark rechazado o decisión no construible.
      El llamante DEBE journalizarlo con atención alta (la posición sigue viva y sin
      gestión, que es un estado operativo, no un no-op).
    * ``None`` — nada que gestionar (sin posición, cerrada o ya plana): benigno.

    V2.44: ``risk_regime``/``drawdown_band``/``operational_state`` son la lectura del
    gobernador para ESTA posición (no el régimen de mercado). Se normalizan con los
    coercers canónicos: un valor no reconocido ⇒ ``UNKNOWN`` (nunca permisivo).
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

    # Lectura del gobernador (fail-closed: lo no reconocido no es permisivo).
    halted = coerce_operational_state(operational_state) == "HALTED"
    band = coerce_drawdown_band(drawdown_band)
    risk_off = coerce_risk_regime(risk_regime) == "RISK_OFF" or band == "EXIT_ONLY"
    regime_exit = regime_is_exit_only(regime)

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
        # ``RiskRegime == RISK_OFF`` ⇒ ``portfolio_risk`` (contrato del roadmap AUTO-3),
        # y además ``risk_exit`` para que el motivo DECISORIO sea ``RISK_EXIT`` (más alto
        # en ``EXIT_REASON_PRECEDENCE``) con ``PORTFOLIO_RISK`` como secundario.
        portfolio_risk=portfolio_risk or risk_off,
        risk_exit=risk_off,
        regime_exit=regime_exit,
        kill_switch=halted,
        manual=manual,
    )
    if decision is None:
        return PositionManagerSkip(
            instrument_id=instrument_id,
            reason=POSITION_DECISION_UNAVAILABLE,
            detail=f"mark_price={mark_price!r} recon={portfolio_recon_status!r}",
        )

    order_action, order_qty, stop_update = _order_from_decision(decision, marked)

    # Orden por PRECEDENCIA: el motivo decisorio primero y los secundarios detrás. El
    # manager ya no "añade" un motivo post-hoc: ``REGIME_EXIT``/``RISK_EXIT``/
    # ``KILL_SWITCH`` nacen en el ``ExitPlan`` (misma taxonomía, un solo ``Literal``).
    exit_reasons: list[str] = []
    if decision.primary_reason:
        exit_reasons.append(decision.primary_reason.lower())
    exit_reasons.extend(reason.lower() for reason in decision.secondary_reasons)

    # Reafirmación defensiva: un halt, un permiso exit-only o un ``RISK_OFF`` son SIEMPRE
    # venta TOTAL. La decisión ya pide ``full_exit``, pero así ningún camino (recon,
    # fracción de T2, ratchet de stop) puede dejar posición abierta contra el gobernador.
    if halted or regime_exit or risk_off:
        order_action = "sell"
        order_qty = marked.remaining_quantity
        stop_update = None

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
