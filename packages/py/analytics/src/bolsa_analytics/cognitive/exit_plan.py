"""ExitPlan — plan condicional de salida (ADR-032 F3).

Simétrico a TradePlan, post-entrada. ≠ execution ≠ ExitPermission.
Thin exitRadar / trail / protect siguen advisory aparte; este módulo
**no** importa ni copia esos mappers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from bolsa_analytics.cognitive.exit_policy import ExitPolicy, suggestion_from_exit_policy
from bolsa_analytics.cognitive.position_state import PositionState

ExitReason = Literal[
    "KILL_SWITCH",
    "REGIME_EXIT",
    "RISK_EXIT",
    "STRUCTURAL_STOP",
    "THESIS_INVALIDATION",
    "TARGET_1",
    "TARGET_2",
    "TRAIL",
    "TIME_STOP",
    "PORTFOLIO_RISK",
    "MANUAL",
]
ExitPlanStatus = Literal["IDLE", "HINT", "ARMED", "TRIGGERED", "DONE"]
ExitSuggestedAction = Literal["hold", "protect", "reduce", "full_exit"]
TradePlanDirection = Literal["long", "short", "none"]

EXIT_PLAN_KEY = "exitPlan"

# Precedencia ÚNICA de motivos (V2.44 · AUTO-3 slice 2: se reutiliza y se EXTIENDE, no se
# crea un segundo sistema). El primero que dispara es el ``primary_reason``; el resto
# viajan como ``secondary_reasons`` (el journal deja de perder la atribución múltiple).
# Orden por autoridad de deshacer riesgo:
#   KILL_SWITCH (halt) > REGIME_EXIT (permiso exit-only) > RISK_EXIT (RiskRegime RISK_OFF)
#   > MANUAL > STOP estructural > tesis > riesgo de cartera > objetivos > trail > tiempo.
EXIT_REASON_PRECEDENCE: tuple[ExitReason, ...] = (
    "KILL_SWITCH",
    "REGIME_EXIT",
    "RISK_EXIT",
    "MANUAL",
    "STRUCTURAL_STOP",
    "THESIS_INVALIDATION",
    "PORTFOLIO_RISK",
    "TARGET_1",
    "TARGET_2",
    "TRAIL",
    "TIME_STOP",
)

_HARD_TRIGGER: frozenset[ExitReason] = frozenset(
    {
        "KILL_SWITCH",
        "REGIME_EXIT",
        "RISK_EXIT",
        "MANUAL",
        "STRUCTURAL_STOP",
        "THESIS_INVALIDATION",
        "PORTFOLIO_RISK",
        "TARGET_1",
        "TARGET_2",
    }
)

#: Salidas PROTECTORAS: deshacer riesgo **no** espera a que el libro esté verificado.
#:
#: Fuente ÚNICA (S-2). Antes había dos conjuntos distintos —`exit_permission._is_protective`
#: y `position_decision._PROTECTIVE_EXIT_REASONS`— y habían divergido: F5 trataba la
#: invalidación de tesis como protectora y la decisión de posición la degradaba a `REVIEW`
#: bajo reconciliación `CRITICAL`. Con dos copias, ese drift es cuestión de tiempo: cualquier
#: motivo nuevo se añade a una y no a la otra.
#:
#: Qué entra y por qué: el stop (`STRUCTURAL_STOP`), el trail y el riesgo de cartera son
#: cobertura directa; las tres salidas del gobernador (`KILL_SWITCH`, `REGIME_EXIT`,
#: `RISK_EXIT`) son permisos de deshacer riesgo; y `THESIS_INVALIDATION` es una salida REAL
#: de capital —la razón para mantener la posición ha dejado de existir, así que seguir dentro
#: es exposición sin tesis, no una espera—.
#:
#: Qué NO entra, declarado para que no se reabra por accidente:
#:   * ``TIME_STOP`` no es cubrirse: el plan vence, no hay pérdida en curso (su
#:     accionabilidad en F5 es S-1; su protección es otra pregunta).
#:   * ``MANUAL`` es una orden humana, no una cobertura automática.
#:   * ``TARGET_1``/``TARGET_2`` toman beneficio: puede esperar a que el libro cuadre.
PROTECTIVE_EXIT_REASONS: frozenset[ExitReason] = frozenset(
    {
        "STRUCTURAL_STOP",
        "TRAIL",
        "PORTFOLIO_RISK",
        "RISK_EXIT",
        "REGIME_EXIT",
        "KILL_SWITCH",
        "THESIS_INVALIDATION",
    }
)


def _finite(value: object) -> float | None:
    """Número finito (admite signo). ``nan``/``inf`` no son hechos utilizables."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _finite_positive(value: object) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stop_touched(direction: TradePlanDirection, mark: float, stop: float) -> bool:
    if direction == "long":
        return mark <= stop
    if direction == "short":
        return mark >= stop
    return False


def _target_touched(
    direction: TradePlanDirection, mark: float, target: float
) -> bool:
    if direction == "long":
        return mark >= target
    if direction == "short":
        return mark <= target
    return False


@dataclass(frozen=True, slots=True)
class ExitPlan:
    """Plan condicional de salida (F3)."""

    exit_plan_id: str
    position_id: str
    trade_plan_id: str
    instrument_id: str
    direction: TradePlanDirection
    status: ExitPlanStatus
    reasons: tuple[ExitReason, ...]
    primary_reason: ExitReason | None
    suggested_action: ExitSuggestedAction
    suggested_qty: float | None
    suggested_stop: float | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "exitPlanId": self.exit_plan_id,
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "status": self.status,
            "reasons": list(self.reasons),
            "primaryReason": self.primary_reason,
            "suggestedAction": self.suggested_action,
            "suggestedQty": self.suggested_qty,
            "suggestedStop": self.suggested_stop,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def _collect_reasons(
    position: PositionState,
    *,
    mark_price: float | None,
    now: str | None,
    expires_at: str | None,
    thesis_invalid: bool,
    portfolio_risk: bool,
    manual: bool,
    trail_hint: bool,
    risk_exit: bool = False,
    regime_exit: bool = False,
    kill_switch: bool = False,
    bar_low: float | None = None,
    bar_high: float | None = None,
) -> list[ExitReason]:
    fired: set[ExitReason] = set()
    # V2.44: los tres motivos del gobernador entran en la MISMA taxonomía (no hay override
    # post-hoc fuera del ``Literal``). Precedencia en ``EXIT_REASON_PRECEDENCE``.
    if kill_switch:
        fired.add("KILL_SWITCH")
    if regime_exit:
        fired.add("REGIME_EXIT")
    if risk_exit:
        fired.add("RISK_EXIT")
    if manual:
        fired.add("MANUAL")
    if thesis_invalid:
        fired.add("THESIS_INVALIDATION")
    if portfolio_risk:
        fired.add("PORTFOLIO_RISK")
    if trail_hint:
        fired.add("TRAIL")

    if mark_price is not None:
        # P-2 (verificación 2026-10-26 §8) — el mark es ``open(B)``; con el rango de la
        # barra (``low``/``high``) la gestión ve el recorrido INTRADÍA. Antes un ``Low``
        # por debajo del stop no disparaba nada y el breach desaparecía sin rastro. Si
        # stop y objetivo caen en la MISMA barra gana el stop (no hay orden intrabar
        # conocida): eso lo garantiza ``EXIT_REASON_PRECEDENCE``.
        stop_probe = mark_price
        target_probe = mark_price
        low = _finite_positive(bar_low)
        high = _finite_positive(bar_high)
        if position.direction == "long":
            if low is not None:
                stop_probe = min(stop_probe, low)
            if high is not None:
                target_probe = max(target_probe, high)
        elif position.direction == "short":
            if high is not None:
                stop_probe = max(stop_probe, high)
            if low is not None:
                target_probe = min(target_probe, low)
        if position.current_stop is not None and position.current_stop > 0:
            if _stop_touched(position.direction, stop_probe, position.current_stop):
                fired.add("STRUCTURAL_STOP")
        if (
            position.target1 is not None
            and not position.target1_achieved_at
            and _target_touched(position.direction, target_probe, position.target1)
        ):
            fired.add("TARGET_1")
        if (
            position.target2 is not None
            and not position.target2_achieved_at
            and _target_touched(position.direction, target_probe, position.target2)
        ):
            fired.add("TARGET_2")
        # H2: T2 no interpreta T1 a ciegas (no reduce mitad por atajo T1).
        if "TARGET_2" in fired:
            fired.discard("TARGET_1")

    now_s = now.strip() if isinstance(now, str) else ""
    exp_s = expires_at.strip() if isinstance(expires_at, str) else ""
    if now_s and exp_s and now_s >= exp_s:
        fired.add("TIME_STOP")

    return [r for r in EXIT_REASON_PRECEDENCE if r in fired]


def _derive_status(
    position: PositionState,
    primary: ExitReason | None,
    trail_stop: float | None,
) -> ExitPlanStatus:
    if position.status == "CLOSED" or position.remaining_quantity <= 0:
        return "DONE"
    if primary is None:
        return "IDLE"
    if primary in _HARD_TRIGGER:
        return "TRIGGERED"
    if primary == "TRAIL" and trail_stop is not None:
        return "ARMED"
    return "HINT"


def _derive_suggestion(
    status: ExitPlanStatus,
    primary: ExitReason | None,
    remaining: float,
    trail_stop: float | None,
    exit_policy: object | None = None,
) -> tuple[ExitSuggestedAction, float | None, float | None]:
    if status in ("DONE", "IDLE") or primary is None:
        return "hold", None, None
    policy = exit_policy if isinstance(exit_policy, ExitPolicy) else None
    return suggestion_from_exit_policy(primary, remaining, policy, trail_stop)


def worst_adverse_price(position: PositionState) -> float | None:
    """Peor precio ADVERSO implícito en el MAE persistido (en R). Durable al reinicio.

    ``mfeMae['maeR']`` es el mínimo R observado por ``apply_position_mark``; convertirlo a
    precio da un hecho que SOBREVIVE al reinicio aunque el mark actual se haya recuperado.
    Sin MAE (blob antiguo) devuelve ``None``; nunca inventa una excursión.
    """
    if position.direction not in ("long", "short"):
        return None
    entry = position.actual_entry
    risk = position.initial_risk
    if entry is None or entry <= 0 or risk is None or risk <= 0:
        return None
    mae = _finite(position.mfe_mae.get("maeR"))
    if mae is None:
        return None
    # long:  r = (price − entry)/risk  ⇒ price = entry + r·risk
    # short: r = (entry − price)/risk  ⇒ price = entry − r·risk
    return entry + mae * risk if position.direction == "long" else entry - mae * risk


def protective_fill_price(
    position: PositionState | None,
    *,
    open_price: float | None,
    primary_reason: str | None,
) -> float | None:
    """P-2 — precio de EJECUCIÓN declarado de una salida disparada por extremos.

    El mark es el ``open(B)``; cuando quien decide es el stop, el precio realista es el
    nivel del stop salvo que el hueco ya sea peor:

    * ``STRUCTURAL_STOP`` long ⇒ ``min(open, stop)``; short ⇒ ``max(open, stop)``.
    * ``TARGET_1``/``TARGET_2`` long ⇒ ``max(open, target)``; short ⇒ ``min(open, target)``.

    Cualquier otro motivo (o falta de nivel/precio) ⇒ ``None``: el llamante conserva su
    precio por defecto (Δ = 0 en el camino sin OHLC).

    Naturaleza del número (importante para no sobreinterpretarlo): es un precio
    **DECLARADO de contabilidad** para un replay con barras D1 — el nivel del stop (o del
    objetivo), o el ``open`` si el hueco ya era peor. NO es una cotización ejecutable ni
    una reconstrucción del orden intrabar: en una barra diaria el stop, el objetivo y el
    cierre pueden haber ocurrido en cualquier orden. Sirve para que settlement, fill,
    P&L y estado final usen UN MISMO precio; no convierte el relleno en realista.
    """
    if position is None or position.direction not in ("long", "short"):
        return None
    open_ = _finite_positive(open_price)
    if open_ is None or not primary_reason:
        return None
    reason = str(primary_reason).strip().upper()
    level: float | None = None
    if reason == "STRUCTURAL_STOP":
        level = _finite_positive(position.current_stop)
    elif reason in ("TARGET_1", "TARGET_2"):
        target = position.target2 if reason == "TARGET_2" else position.target1
        level = _finite_positive(target)
    if level is None:
        return None
    if position.direction == "long":
        return min(open_, level) if reason == "STRUCTURAL_STOP" else max(open_, level)
    return max(open_, level) if reason == "STRUCTURAL_STOP" else min(open_, level)


def is_thesis_invalidated(
    position: PositionState | None,
    *,
    mark_price: float | None = None,
) -> bool:
    """V2.42 slice 2b (E3) — ¿la tesis está CONFIRMADA como invalidada?

    Determinista y sin LLM: el nivel se congeló en el nacimiento (``invalidation_price``,
    decisión D2) y la confirmación es que el precio lo haya **atravesado en algún momento**,
    no sólo ahora. Por eso se combina el mark actual con el peor adverso persistido (MAE):
    un stop que no llegó a materializarse NO se "des-hace" porque el precio se recupere.

    ``None``/dirección inválida/sin nivel ⇒ ``False``: la invalidación no se inventa.
    """
    if position is None or position.remaining_quantity <= 0:
        return False
    if position.direction not in ("long", "short"):
        return False
    level = _finite_positive(position.invalidation_price)
    if level is None:
        return False
    seen = [p for p in (_finite_positive(worst_adverse_price(position)), _finite_positive(mark_price)) if p is not None]
    if not seen:
        return False
    if position.direction == "long":
        return min(seen) <= level
    return max(seen) >= level


def build_exit_plan_from_position(
    position: PositionState | None,
    *,
    mark_price: float | None = None,
    now: str | None = None,
    expires_at: str | None = None,
    thesis_invalid: bool = False,
    portfolio_risk: bool = False,
    manual: bool = False,
    trail_hint: bool = False,
    trail_stop: float | None = None,
    risk_exit: bool = False,
    regime_exit: bool = False,
    kill_switch: bool = False,
    exit_plan_id: str | None = None,
    at: str | None = None,
    exit_policy: ExitPolicy | None = None,
    bar_low: float | None = None,
    bar_high: float | None = None,
) -> ExitPlan | None:
    """Factory F3: PositionState + señales → ExitPlan. No muta PositionState.

    ``bar_low``/``bar_high`` son los extremos de la barra corriente (P-2). ``None``
    reproduce byte a byte el comportamiento anterior (sólo ``mark_price``).
    """
    if position is None:
        return None
    if position.direction not in ("long", "short"):
        return None

    mark = _finite_positive(mark_price) if mark_price is not None else None
    trail_s = _finite_positive(trail_stop) if trail_stop is not None else None

    reasons = _collect_reasons(
        position,
        mark_price=mark,
        now=now,
        expires_at=expires_at,
        thesis_invalid=thesis_invalid,
        portfolio_risk=portfolio_risk,
        manual=manual,
        trail_hint=trail_hint,
        risk_exit=risk_exit,
        regime_exit=regime_exit,
        kill_switch=kill_switch,
        bar_low=bar_low,
        bar_high=bar_high,
    )
    primary: ExitReason | None = reasons[0] if reasons else None
    status = _derive_status(position, primary, trail_s)
    action, qty, stop = _derive_suggestion(
        status, primary, position.remaining_quantity, trail_s, exit_policy
    )
    stamp = _now_iso(at)
    epid = (
        exit_plan_id.strip()
        if isinstance(exit_plan_id, str) and exit_plan_id.strip()
        else str(uuid4())
    )

    return ExitPlan(
        exit_plan_id=epid,
        position_id=position.position_id,
        trade_plan_id=position.trade_plan_id,
        instrument_id=position.instrument_id,
        direction=position.direction,
        status=status,
        reasons=tuple(reasons),
        primary_reason=primary,
        suggested_action=action,
        suggested_qty=qty,
        suggested_stop=stop,
        created_at=stamp,
        updated_at=stamp,
    )
