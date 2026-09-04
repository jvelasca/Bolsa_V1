"""V1.65 — PositionOperationalView: proyección canónica post-entrada (espejo TS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.position_revision import PositionRevisionOrigin
from bolsa_analytics.cognitive.position_state import PositionState

PositionOperatingState = Literal[
    "OPEN_UNPROTECTED",
    "PROTECTED",
    "TRAILING",
    "PARTIALLY_REDUCED",
    "EXIT_PENDING",
    "CLOSED",
    "RECONCILIATION_ERROR",
    "RECONCILIATION_DRIFT",
]

PositionOperationalState = (
    PositionOperatingState
    | Literal[
        "PROTECT_REQUIRED",
        "T1_READY",
        "T1_EXECUTED",
        "T2_READY",
        "T2_EXECUTED",
        "EXIT_REQUIRED",
    ]
)

PaperDeskNextAction = Literal[
    "MANTENER",
    "MONITOR",
    "SUBIR_STOP",
    "REDUCIR",
    "SALIR",
    "ESPERAR_APERTURA",
    "REVISAR_DATOS_NO_FRESCOS",
    "BLOQUEADO",
]

PovReconStatus = Literal["clean", "drift", "unavailable"] | None


def map_portfolio_recon_to_pov_recon(status: str | None) -> PovReconStatus:
    if status is None:
        return None
    s = str(status).strip().lower()
    if s == "":
        return None
    if s in ("clean", "ok"):
        return "clean"
    if s == "drift":
        return "drift"
    if s in ("unavailable", "not_wired", "error"):
        return "unavailable"
    return "unavailable"


def _trim_id(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    t = value.strip()
    return t if t else None


def resolve_position_operating_state(
    *,
    position_status: str | None,
    remaining_quantity: float | None,
    quantity: float | None,
    has_trail_revision: bool,
    has_protect_revision: bool,
    recon_status: str = "clean",
    has_unresolved_exit: bool = False,
    current_stop: float | None = None,
    initial_stop: float | None = None,
) -> PositionOperatingState:
    if recon_status == "unavailable":
        return "RECONCILIATION_ERROR"
    if recon_status == "drift":
        return "RECONCILIATION_DRIFT"
    if (position_status or "").upper() == "CLOSED":
        return "CLOSED"
    if has_unresolved_exit:
        return "EXIT_PENDING"
    qty = float(quantity or 0)
    rem = float(remaining_quantity if remaining_quantity is not None else qty)
    if qty > 0 and rem + 1e-9 < qty:
        return "PARTIALLY_REDUCED"
    if has_trail_revision:
        return "TRAILING"
    if has_protect_revision or (position_status or "").upper() == "PROTECTED":
        return "PROTECTED"
    # V2.33 — birth fill with signed structural stop is not OPEN_UNPROTECTED.
    def _finite_positive(n: float | None) -> bool:
        return n is not None and isinstance(n, (int, float)) and float(n) > 0

    if _finite_positive(current_stop) or _finite_positive(initial_stop):
        return "PROTECTED"
    return "OPEN_UNPROTECTED"


def resolve_paper_desk_next_action(
    *,
    status: str,
    decision_verdict: str | None = None,
) -> PaperDeskNextAction:
    """Espejo TS ``resolvePaperDeskNextAction`` en el subconjunto que usa POV.

    protected/reduced/exited sin dry_run → APPLIED → MONITOR (no SUBIR_STOP/REDUCIR).
    """
    if status == "denied":
        return "BLOQUEADO"
    if status in ("protected", "reduced", "exited"):
        return "MONITOR"
    if status == "held":
        return "MANTENER"
    if status in ("error", "no_plan", "skipped", "sell_skipped"):
        return "BLOQUEADO"
    _ = decision_verdict
    return "MANTENER"


def map_operating_state_to_desk_status(state: PositionOperationalState) -> str:
    if state in ("PROTECT_REQUIRED", "OPEN_UNPROTECTED"):
        return "held"
    if state in ("T1_READY", "T1_EXECUTED", "T2_READY", "T2_EXECUTED", "PARTIALLY_REDUCED"):
        return "reduced"
    if state in ("EXIT_REQUIRED", "EXIT_PENDING", "CLOSED"):
        return "exited"
    if state in ("TRAILING", "PROTECTED"):
        return "protected"
    if state in ("RECONCILIATION_ERROR", "RECONCILIATION_DRIFT"):
        return "denied"
    raise ValueError(f"unexpected operating state: {state!r}")


def _stop_history_label(origin: PositionRevisionOrigin, trail_idx: list[int]) -> str:
    if origin == "protect":
        return "Protect"
    if origin == "trail":
        trail_idx[0] += 1
        return f"Trail #{trail_idx[0]}"
    if origin == "reduce":
        return "Reduce"
    if origin == "override":
        return "Ajuste manual"
    if origin == "stop":
        return "Stop"
    raise ValueError(f"unexpected revision origin: {origin!r}")


def build_stop_history(position: PositionState) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    initial = position.initial_stop
    if initial is not None:
        entries.append({"label": "Initial", "stop": initial, "origin": "birth"})
    trail_idx = [0]
    prev = initial
    for rev in position.revisions:
        stop = rev.next_stop
        if stop is None:
            continue
        label = _stop_history_label(rev.origin, trail_idx)
        delta = stop - prev if prev is not None else None
        entries.append(
            {
                "label": label,
                "stop": stop,
                "delta": delta,
                "at": rev.at,
                "origin": rev.origin,
            }
        )
        prev = stop
    if position.current_stop is not None and (
        not entries or entries[-1].get("stop") != position.current_stop
    ):
        last = entries[-1]["stop"] if entries else None
        delta = (
            position.current_stop - last
            if isinstance(last, (int, float))
            else None
        )
        entries.append(
            {
                "label": "Current",
                "stop": position.current_stop,
                "delta": delta,
                "origin": "current",
            }
        )
    return entries


def build_position_operational_events(
    position: PositionState,
    *,
    stop_touched: bool = False,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    if stop_touched:
        events.append({"kind": "STOP_LEVEL_REACHED"})
    if position.status == "CLOSED":
        events.append({"kind": "POSITION_CLOSED"})
    t1 = position.target1_leg
    if t1 is not None and t1.status == "triggered":
        events.append({"kind": "T1_TRIGGERED", "at": t1.at})
    if t1 is not None and t1.status == "executed":
        events.append(
            {"kind": "T1_EXECUTED", "at": t1.at, "fillId": t1.fill_id}
        )
        if t1.fill_id:
            events.append({"kind": "T1_FILL", "fillId": t1.fill_id})
    t2 = position.target2_leg
    if t2 is not None and t2.status == "triggered":
        events.append({"kind": "T2_TRIGGERED", "at": t2.at})
    if t2 is not None and t2.status == "executed":
        events.append(
            {"kind": "T2_EXECUTED", "at": t2.at, "fillId": t2.fill_id}
        )
        if t2.fill_id:
            events.append({"kind": "T2_FILL", "fillId": t2.fill_id})
    return events


def _resolve_extended_operating_state(
    position: PositionState,
    *,
    recon_status: PovReconStatus = None,
    stop_touched: bool = False,
    exit_pending: bool = False,
) -> PositionOperationalState:
    recon = "clean" if recon_status is None else recon_status
    base = resolve_position_operating_state(
        position_status=position.status,
        remaining_quantity=position.remaining_quantity,
        quantity=position.quantity,
        has_trail_revision=any(r.origin == "trail" for r in position.revisions),
        has_protect_revision=any(r.origin == "protect" for r in position.revisions),
        recon_status=recon,
        has_unresolved_exit=exit_pending,
        current_stop=position.current_stop,
        initial_stop=position.initial_stop,
    )
    if base in ("RECONCILIATION_ERROR", "RECONCILIATION_DRIFT", "CLOSED"):
        return base
    if stop_touched and position.status != "CLOSED":
        return "EXIT_REQUIRED"
    t2 = position.target2_leg
    if t2 is not None and t2.status == "executed":
        return "T2_EXECUTED"
    if t2 is not None and t2.status == "triggered":
        return "T2_READY"
    t1 = position.target1_leg
    if t1 is not None and t1.status == "executed":
        return "T1_EXECUTED"
    if t1 is not None and t1.status == "triggered":
        return "T1_READY"
    # V2.33 — birth with structural stop is PROTECTED (phase Planificado in cabin).
    return base


@dataclass(frozen=True, slots=True)
class BuildPositionOperationalViewInput:
    position: PositionState
    recon_status: PovReconStatus = None
    stop_touched: bool = False
    exit_pending: bool = False
    template_id: str | None = None
    analysis_as_of: str | None = None
    desk_status: str | None = None
    decision_verdict: str | None = None


def build_position_operational_view(
    input: BuildPositionOperationalViewInput | PositionState,
    *,
    recon_status: PovReconStatus = None,
    desk_status: str | None = None,
    decision_verdict: str | None = None,
    stop_touched: bool = False,
    exit_pending: bool = False,
    template_id: str | None = None,
    analysis_as_of: str | None = None,
) -> dict[str, Any]:
    """Build POV dict (camelCase wire, espejo TS ``buildPositionOperationalView``)."""
    if isinstance(input, PositionState):
        pos = input
        recon = recon_status
        desk = desk_status
        verdict = decision_verdict
        stop_touch = stop_touched
        exit_pend = exit_pending
        tmpl = template_id
        as_of = analysis_as_of
    else:
        pos = input.position
        recon = input.recon_status
        desk = input.desk_status
        verdict = input.decision_verdict
        stop_touch = input.stop_touched
        exit_pend = input.exit_pending
        tmpl = input.template_id
        as_of = input.analysis_as_of

    operating_state = _resolve_extended_operating_state(
        pos,
        recon_status=recon,
        stop_touched=stop_touch,
        exit_pending=exit_pend,
    )
    primary_action = resolve_paper_desk_next_action(
        status=desk or map_operating_state_to_desk_status(operating_state),
        decision_verdict=verdict,
    )
    decision_id = _trim_id(pos.decision_id)
    t1_leg = pos.target1_leg.to_dict() if pos.target1_leg else None
    t2_leg = pos.target2_leg.to_dict() if pos.target2_leg else None
    return {
        "positionId": pos.position_id,
        "instrumentId": pos.instrument_id,
        "tradePlanId": pos.trade_plan_id,
        "decisionId": decision_id,
        "lineageCollapsed": decision_id is None,
        "operatingState": operating_state,
        "primaryAction": primary_action,
        "levels": {
            "entry": pos.actual_entry if pos.actual_entry is not None else pos.planned_entry,
            "currentStop": pos.current_stop,
            "target1": pos.target1,
            "target2": pos.target2,
            "unrealizedR": pos.unrealized_r,
        },
        "t1": t1_leg,
        "t2": t2_leg,
        "stopHistory": build_stop_history(pos),
        "events": build_position_operational_events(pos, stop_touched=stop_touch),
        "quantity": pos.quantity,
        "remainingQuantity": pos.remaining_quantity,
        "templateId": tmpl,
        "analysisAsOf": as_of,
    }
