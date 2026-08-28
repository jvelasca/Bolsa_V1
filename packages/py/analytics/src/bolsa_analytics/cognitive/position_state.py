"""PositionState — autoridad post-entrada (ADR-032 F2 + F2.1).

Tesis ≠ plan ≠ permiso ≠ posición. Thin 5.x/8.x siguen advisory aparte;
este módulo **no** importa ni copia esos mappers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from bolsa_analytics.cognitive.position_revision import (
    PositionRevision,
    PositionRevisionOrigin,
    build_position_revision,
    revisions_from_raw,
    stop_or_status_changed,
)

PositionStatus = Literal["OPEN", "PARTIAL", "PROTECTED", "CLOSED"]
PositionExitStatus = Literal["none", "hint", "armed", "done"]
TradePlanDirection = Literal["long", "short", "none"]

POSITION_STATE_KEY = "positionState"


def _finite_positive(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


def _is_audited_override(override: object | None) -> bool:
    """H2: reason no vacío. No persiste."""
    if not isinstance(override, dict):
        return False
    reason = override.get("reason")
    return isinstance(reason, str) and bool(reason.strip())


def _stop_worsens(
    direction: TradePlanDirection, current: float | None, nxt: float
) -> bool:
    if current is None or current <= 0:
        return False
    if direction == "long":
        return nxt < current - 1e-9
    if direction == "short":
        return nxt > current + 1e-9
    return False


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def signed_r_from_price(
    direction: TradePlanDirection,
    entry: float | None,
    risk: float | None,
    price: float,
) -> float | None:
    """R firmado vs entry/risk. Sin inputs válidos → None."""
    if direction not in ("long", "short"):
        return None
    if entry is None or risk is None or risk <= 0:
        return None
    if price <= 0:
        return None
    raw = (price - entry) / risk if direction == "long" else (entry - price) / risk
    return _round4(raw)


def _is_break_even_stop(position: PositionState) -> bool:
    entry = position.actual_entry
    stop = position.current_stop
    if entry is None or stop is None:
        return False
    if position.direction == "long":
        return stop >= entry
    if position.direction == "short":
        return stop <= entry
    return False


def derive_position_status(position: PositionState) -> PositionStatus:
    """Precedencia F2.1: CLOSED > BE→PROTECTED > PARTIAL > OPEN."""
    if position.status == "CLOSED" or position.remaining_quantity <= 0:
        return "CLOSED"
    if _is_break_even_stop(position):
        return "PROTECTED"
    if position.remaining_quantity < position.quantity:
        return "PARTIAL"
    return "OPEN"


@dataclass(frozen=True, slots=True)
class PositionState:
    """Ciclo de vida de posición abierta (F2 + F2.1)."""

    position_id: str
    trade_plan_id: str
    instrument_id: str
    direction: TradePlanDirection
    status: PositionStatus
    planned_entry: float | None
    actual_entry: float | None
    initial_stop: float | None
    current_stop: float | None
    target1: float | None
    target2: float | None
    quantity: float
    remaining_quantity: float
    initial_risk: float | None
    realized_r: float
    unrealized_r: float | None
    mfe_mae: dict[str, object]
    thesis_health: dict[str, object] | None
    protection_state: dict[str, object] | None
    trailing: dict[str, object] | None
    exit_status: PositionExitStatus
    created_at: str
    updated_at: str
    target1_achieved_at: str | None = None
    target2_achieved_at: str | None = None
    revisions: tuple[PositionRevision, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "status": self.status,
            "plannedEntry": self.planned_entry,
            "actualEntry": self.actual_entry,
            "initialStop": self.initial_stop,
            "currentStop": self.current_stop,
            "target1": self.target1,
            "target2": self.target2,
            "target1AchievedAt": self.target1_achieved_at,
            "target2AchievedAt": self.target2_achieved_at,
            "quantity": self.quantity,
            "remainingQuantity": self.remaining_quantity,
            "initialRisk": self.initial_risk,
            "realizedR": self.realized_r,
            "unrealizedR": self.unrealized_r,
            "mfeMae": dict(self.mfe_mae),
            "thesisHealth": self.thesis_health,
            "protectionState": self.protection_state,
            "trailing": self.trailing,
            "exitStatus": self.exit_status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "revisions": [r.to_dict() for r in self.revisions],
        }


def position_state_from_dict(raw: dict[str, object] | None) -> PositionState | None:
    """P3 — rehidrata JSONB persistido. Inverso de ``to_dict``. Sin campos nuevos.

    Claves de bookkeeping (``_…``) se ignoran. Dict inválido → None.
    """
    if not isinstance(raw, dict):
        return None
    direction = raw.get("direction")
    if direction not in ("long", "short"):
        return None
    status = raw.get("status")
    if status not in ("OPEN", "PARTIAL", "PROTECTED", "CLOSED"):
        return None
    position_id = raw.get("positionId")
    trade_plan_id = raw.get("tradePlanId")
    instrument_id = raw.get("instrumentId")
    if not isinstance(position_id, str) or not position_id.strip():
        return None
    if not isinstance(trade_plan_id, str) or not trade_plan_id.strip():
        return None
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None
    qty = _finite_positive(raw.get("quantity"))
    remaining = _finite(raw.get("remainingQuantity"))
    if qty is None or remaining is None or remaining < 0:
        return None
    exit_status = raw.get("exitStatus")
    if exit_status not in ("none", "hint", "armed", "done"):
        exit_status = "none"
    created = raw.get("createdAt")
    updated = raw.get("updatedAt")
    if not isinstance(created, str) or not created.strip():
        return None
    if not isinstance(updated, str) or not updated.strip():
        updated = created
    mfe_raw = raw.get("mfeMae")
    mfe_mae: dict[str, object]
    if isinstance(mfe_raw, dict):
        mfe_mae = dict(mfe_raw)
    else:
        mfe_mae = {"mfeR": None, "maeR": None, "source": "none"}
    realized = _finite(raw.get("realizedR"))
    if realized is None:
        realized = 0.0
    stub_health = raw.get("thesisHealth")
    stub_protect = raw.get("protectionState")
    stub_trail = raw.get("trailing")
    return PositionState(
        position_id=position_id.strip(),
        trade_plan_id=trade_plan_id.strip(),
        instrument_id=instrument_id.strip(),
        direction=direction,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        planned_entry=_finite(raw.get("plannedEntry")),
        actual_entry=_finite(raw.get("actualEntry")),
        initial_stop=_finite(raw.get("initialStop")),
        current_stop=_finite(raw.get("currentStop")),
        target1=_finite(raw.get("target1")),
        target2=_finite(raw.get("target2")),
        quantity=_round4(qty),
        remaining_quantity=_round4(remaining),
        initial_risk=_finite(raw.get("initialRisk")),
        realized_r=_round4(realized),
        unrealized_r=_finite(raw.get("unrealizedR")),
        mfe_mae=mfe_mae,
        thesis_health=dict(stub_health) if isinstance(stub_health, dict) else {"status": "none"},
        protection_state=dict(stub_protect) if isinstance(stub_protect, dict) else {"status": "none"},
        trailing=dict(stub_trail) if isinstance(stub_trail, dict) else {"status": "none"},
        exit_status=exit_status,  # type: ignore[arg-type]
        created_at=created.strip(),
        updated_at=updated.strip() if isinstance(updated, str) else created.strip(),
        target1_achieved_at=(
            raw.get("target1AchievedAt").strip()
            if isinstance(raw.get("target1AchievedAt"), str)
            and str(raw.get("target1AchievedAt")).strip()
            else None
        ),
        target2_achieved_at=(
            raw.get("target2AchievedAt").strip()
            if isinstance(raw.get("target2AchievedAt"), str)
            and str(raw.get("target2AchievedAt")).strip()
            else None
        ),
        revisions=revisions_from_raw(raw.get("revisions")),
    )


def build_position_state_from_fill(
    trade_plan: dict[str, object] | None,
    *,
    fill_price: float | None,
    fill_quantity: float | None,
    filled_at: str | None = None,
    position_id: str | None = None,
    override: dict[str, object] | None = None,
) -> PositionState | None:
    """Factory F2: TradePlan dict + fill → OPEN.

    H2: exige status TRIGGERED, o override auditado. WATCH/ARMED no nacen.
    Sin plan/fill válido → None.
    """
    if not isinstance(trade_plan, dict):
        return None
    direction = trade_plan.get("direction")
    if direction not in ("long", "short"):
        return None
    status = trade_plan.get("status")
    if status != "TRIGGERED" and not _is_audited_override(override):
        return None
    price = _finite_positive(fill_price)
    qty = _finite_positive(fill_quantity)
    if price is None or qty is None:
        return None

    decision_id = trade_plan.get("decisionId")
    if not isinstance(decision_id, str) or not decision_id.strip():
        return None
    instrument_id = trade_plan.get("instrumentId")
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None

    planned_entry = _finite(trade_plan.get("entry"))
    planned_stop = _finite(trade_plan.get("structuralStop"))
    actual_entry = _round4(price)
    initial_stop = planned_stop
    if initial_stop is not None:
        initial_risk = _round4(abs(actual_entry - initial_stop))
    elif planned_entry is not None and planned_stop is not None:
        initial_risk = _round4(abs(planned_entry - planned_stop))
    else:
        initial_risk = None
    if initial_risk is not None and initial_risk <= 0:
        initial_risk = None

    now = filled_at if isinstance(filled_at, str) and filled_at else ""
    if not now:
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    stub = {"status": "none"}
    qty_r = _round4(qty)
    pid = position_id.strip() if isinstance(position_id, str) and position_id.strip() else str(uuid4())

    return PositionState(
        position_id=pid,
        trade_plan_id=decision_id,
        instrument_id=instrument_id,
        direction=direction,  # type: ignore[arg-type]
        status="OPEN",
        planned_entry=planned_entry,
        actual_entry=actual_entry,
        initial_stop=initial_stop,
        current_stop=initial_stop,
        target1=_finite(trade_plan.get("target1")),
        target2=_finite(trade_plan.get("target2")),
        quantity=qty_r,
        remaining_quantity=qty_r,
        initial_risk=initial_risk,
        realized_r=0.0,
        unrealized_r=None,
        mfe_mae={"mfeR": None, "maeR": None, "source": "none"},
        thesis_health=dict(stub),
        protection_state=dict(stub),
        trailing=dict(stub),
        exit_status="none",
        created_at=now,
        updated_at=now,
        revisions=(),
    )


def _with_revision_if_changed(
    previous: PositionState,
    next_pos: PositionState,
    *,
    origin: PositionRevisionOrigin,
    reason: str | None,
    at: str,
) -> PositionState:
    if not stop_or_status_changed(
        previous_stop=previous.current_stop,
        next_stop=next_pos.current_stop,
        previous_status=previous.status,
        next_status=next_pos.status,
    ):
        return next_pos
    rev = build_position_revision(
        at=at,
        previous_stop=previous.current_stop,
        next_stop=next_pos.current_stop,
        previous_status=previous.status,
        next_status=next_pos.status,
        origin=origin,
        reason=reason,
    )
    return replace(next_pos, revisions=previous.revisions + (rev,))


def apply_position_mark(
    position: PositionState | None,
    mark_price: float,
    *,
    at: str | None = None,
) -> PositionState | None:
    """F2.1 mark → unrealized_r + picos MFE/MAE. No cambia status."""
    if position is None or position.status == "CLOSED":
        return None
    price = _finite_positive(mark_price)
    if price is None:
        return None

    unrealized = signed_r_from_price(
        position.direction,
        position.actual_entry,
        position.initial_risk,
        price,
    )

    mfe_mae = dict(position.mfe_mae)
    if unrealized is not None:
        prev_mfe = _finite(mfe_mae.get("mfeR"))
        prev_mae = _finite(mfe_mae.get("maeR"))
        base_mfe = prev_mfe if prev_mfe is not None else unrealized
        base_mae = prev_mae if prev_mae is not None else unrealized
        source = mfe_mae.get("source")
        if source == "none":
            source = "close_proxy"
        elif source not in ("bars", "close_proxy"):
            source = "close_proxy"
        mfe_mae = {
            "mfeR": _round4(max(base_mfe, unrealized)),
            "maeR": _round4(min(base_mae, unrealized)),
            "source": source,
        }

    return replace(
        position,
        unrealized_r=unrealized,
        mfe_mae=mfe_mae,
        updated_at=_now_iso(at),
    )


def apply_position_reduce(
    position: PositionState | None,
    qty: float,
    *,
    exit_price: float | None = None,
    at: str | None = None,
    origin: PositionRevisionOrigin = "reduce",
    reason: str | None = None,
    mark_target1_achieved: bool = False,
    mark_target2_achieved: bool = False,
) -> PositionState | None:
    """F2.1 reduce → remaining / realized_r / PARTIAL|CLOSED.

    OI-5: append revisión si status cambia.
    V1.21: ``mark_target1_achieved`` fija ``target1_achieved_at``.
    V1.27: ``mark_target2_achieved`` fija ``target2_achieved_at``.
    """
    if position is None or position.status == "CLOSED":
        return None
    cut_in = _finite_positive(qty)
    if cut_in is None:
        return None
    if cut_in > position.remaining_quantity + 1e-12:
        return None

    cut = _round4(min(cut_in, position.remaining_quantity))
    remaining = _round4(position.remaining_quantity - cut)
    realized = position.realized_r
    exit_p = _finite_positive(exit_price) if exit_price is not None else None
    if exit_p is not None and position.quantity > 0:
        slice_r = signed_r_from_price(
            position.direction,
            position.actual_entry,
            position.initial_risk,
            exit_p,
        )
        if slice_r is not None:
            realized = _round4(realized + slice_r * (cut / position.quantity))

    updated = _now_iso(at)
    t1_at = (
        position.target1_achieved_at or updated
        if mark_target1_achieved
        else position.target1_achieved_at
    )
    t2_at = (
        position.target2_achieved_at or updated
        if mark_target2_achieved
        else position.target2_achieved_at
    )
    if remaining <= 0:
        next_pos = replace(
            position,
            remaining_quantity=0.0,
            realized_r=realized,
            status="CLOSED",
            exit_status="done",
            target1_achieved_at=t1_at,
            target2_achieved_at=t2_at,
            updated_at=updated,
        )
        return _with_revision_if_changed(
            position,
            next_pos,
            origin=origin,
            reason=reason,
            at=updated,
        )

    mid = replace(
        position,
        remaining_quantity=remaining,
        realized_r=realized,
        target1_achieved_at=t1_at,
        target2_achieved_at=t2_at,
        updated_at=updated,
    )
    next_pos = replace(mid, status=derive_position_status(mid))
    return _with_revision_if_changed(
        position,
        next_pos,
        origin=origin,
        reason=reason,
        at=updated,
    )


def apply_position_current_stop(
    position: PositionState | None,
    stop: float,
    *,
    at: str | None = None,
    override: dict[str, object] | None = None,
    origin: PositionRevisionOrigin | None = None,
    reason: str | None = None,
) -> PositionState | None:
    """F2.1 current_stop geométrico → posible PROTECTED (BE).

    H2: no empeora el stop sin override auditado.
    OI-5: append revisión si stop o status cambian de verdad.
    """
    if position is None or position.status == "CLOSED":
        return None
    stop_p = _finite_positive(stop)
    if stop_p is None:
        return None
    worsens = _stop_worsens(position.direction, position.current_stop, stop_p)
    if worsens and not _is_audited_override(override):
        return None

    updated = _now_iso(at)
    mid = replace(
        position,
        current_stop=_round4(stop_p),
        updated_at=updated,
    )
    next_pos = replace(mid, status=derive_position_status(mid))

    resolved_origin: PositionRevisionOrigin
    if origin is not None:
        resolved_origin = origin
    elif worsens:
        resolved_origin = "override"
    else:
        resolved_origin = "stop"

    override_reason = None
    if isinstance(override, dict):
        raw_reason = override.get("reason")
        if isinstance(raw_reason, str) and raw_reason.strip():
            override_reason = raw_reason.strip()
    resolved_reason = reason if reason is not None else override_reason

    return _with_revision_if_changed(
        position,
        next_pos,
        origin=resolved_origin,
        reason=resolved_reason,
        at=updated,
    )
