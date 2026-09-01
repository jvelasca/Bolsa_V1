"""OI-1 — persistir stop operativo tras Confirm protect (ADR-034).

No muta el ledger. Factory H2 intacta (no empeora stop sin override).
Stop operativo persistido ≠ orden stop de broker.
V1.48: CAS por current_stop + PositionEvent durable (eventId = identidad).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    apply_target_leg,
    position_state_from_dict,
)
from bolsa_application.origin_decision_package import preserve_origin_decision_package
from bolsa_application.persist_position_from_exit import (
    row_position_id,
    row_position_state,
)
from bolsa_application.position_event_log import (
    claim_durable_event,
    preserve_position_events,
)


class PositionStateProtectStore(Protocol):
    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> Any | None: ...

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> Any | None: ...

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> Any | None:
        """V1.48 — UPDATE iff current_stop == expected. None = lost CAS."""
        ...


@dataclass(frozen=True, slots=True)
class PersistPositionFromProtectInput:
    account_id: str
    instrument_id: str
    suggested_stop: float
    override_reason: str | None = None
    applied_at: str | None = None
    # OI-5 / V1.43 — ``protect`` (default) o ``trail`` cuando Confirm firma un TRAIL.
    origin: str = "protect"
    reason: str | None = None
    decision_id: str | None = None
    policy_id: str | None = None


def _resolve_protect_origin(raw: str | None) -> str:
    oid = (raw or "").strip().lower()
    if oid == "trail":
        return "trail"
    return "protect"


def _blob_current_stop(blob: dict[str, Any] | None) -> float | None:
    if not isinstance(blob, dict):
        return None
    raw = blob.get("currentStop")
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if value != value or value <= 0:
        return None
    return value


def _last_revision_id(blob: dict[str, Any]) -> str | None:
    revs = revisions_from_raw(blob.get("revisions"))
    if not revs:
        return None
    rid = (revs[-1].revision_id or "").strip()
    return rid or None


async def _cas_or_update(
    store: PositionStateProtectStore,
    *,
    position_id: str,
    expected_stop: float | None,
    status: str,
    position_state: dict[str, Any],
) -> Any | None:
    cas = getattr(store, "compare_and_swap_stop", None)
    if cas is not None and expected_stop is not None:
        return await cas(
            position_id=position_id,
            expected_stop=float(expected_stop),
            status=status,
            position_state=position_state,
        )
    return await store.update_state(
        position_id=position_id,
        status=status,
        position_state=position_state,
    )


class PersistPositionFromProtect:
    """Aplica ``apply_position_current_stop`` a la fila OPEN; idempotente por stop.

    OI-5: origin=protect|trail deja huella en ``revisions``.
    V1.48: CAS + ``events[]`` (eventId durable).
    """

    def __init__(self, store: PositionStateProtectStore) -> None:
        self._store = store

    async def get_open(self, account_id: str, instrument_id: str) -> Any | None:
        acc = account_id.strip() if account_id else ""
        inst = instrument_id.strip() if instrument_id else ""
        if not acc or not inst:
            return None
        return await self._store.get_open_for_instrument(acc, inst)

    async def persist(self, inp: PersistPositionFromProtectInput) -> Any | None:
        account_id = inp.account_id.strip() if inp.account_id else ""
        instrument_id = inp.instrument_id.strip() if inp.instrument_id else ""
        if not account_id or not instrument_id:
            return None

        existing = await self._store.get_open_for_instrument(account_id, instrument_id)
        if existing is None:
            return None

        pid = row_position_id(existing)
        blob = row_position_state(existing)
        if pid is None or blob is None:
            return None

        pos = position_state_from_dict(blob)
        expected_stop = _blob_current_stop(blob)
        override_reason = (inp.override_reason or "").strip()
        override: dict[str, object] | None = (
            {"reason": override_reason} if override_reason else None
        )
        origin = _resolve_protect_origin(inp.origin)
        reason = (inp.reason or "").strip() or override_reason or (
            "trail_confirm" if origin == "trail" else None
        )
        event_type = "TRAIL" if origin == "trail" else "PROTECT"
        suggested = float(inp.suggested_stop)

        same_stop = (
            expected_stop is not None
            and abs(expected_stop - suggested) <= 1e-9
        )
        if same_stop:
            next_blob, _event, _created = claim_durable_event(
                dict(blob),
                position_id=pid,
                event_type=event_type,
                action="protect",
                as_of=inp.applied_at,
                next_stop=suggested,
                detected_at=inp.applied_at,
            )
            next_blob = preserve_origin_decision_package(blob, next_blob)
            next_blob = preserve_position_events(blob, next_blob)
            status = str(blob.get("status") or pos.status if pos else "OPEN")
            return await _cas_or_update(
                self._store,
                position_id=pid,
                expected_stop=expected_stop,
                status=status,
                position_state=next_blob,
            )

        updated = apply_position_current_stop(
            pos,
            suggested,
            at=inp.applied_at,
            override=override,
            origin=origin,  # type: ignore[arg-type]
            reason=reason,
            decision_id=inp.decision_id or (pos.trade_plan_id if pos else None),
            policy_id=inp.policy_id,
        )
        if updated is None:
            return None

        next_blob = preserve_origin_decision_package(blob, dict(updated.to_dict()))
        next_blob = preserve_position_events(blob, next_blob)
        next_blob, _event, _created = claim_durable_event(
            next_blob,
            position_id=pid,
            event_type=event_type,
            action="protect",
            as_of=inp.applied_at,
            next_stop=suggested,
            revision_id=_last_revision_id(next_blob),
            detected_at=inp.applied_at,
        )
        row = await _cas_or_update(
            self._store,
            position_id=pid,
            expected_stop=expected_stop,
            status=updated.status,
            position_state=next_blob,
        )
        if row is not None:
            return row
        # CAS lost: replay if the winner already applied this stop.
        latest = await self._store.get_open_for_instrument(account_id, instrument_id)
        latest_blob = row_position_state(latest) if latest is not None else None
        latest_stop = _blob_current_stop(latest_blob)
        if latest is not None and latest_stop is not None and abs(latest_stop - suggested) <= 1e-9:
            return latest
        return None

    async def claim_sell_event(
        self,
        *,
        account_id: str,
        instrument_id: str,
        event_type: str,
        action: str,
        as_of: str | None,
        quantity: float | None = None,
    ) -> Any:
        """V1.48 — reclama evento REDUCE/EXIT en JSON antes del sell."""
        acc = account_id.strip() if account_id else ""
        inst = instrument_id.strip() if instrument_id else ""
        if not acc or not inst:
            return None
        existing = await self._store.get_open_for_instrument(acc, inst)
        if existing is None:
            return None
        pid = row_position_id(existing)
        blob = row_position_state(existing)
        if pid is None or blob is None:
            return None
        act = "exit" if action == "exit" else "reduce"
        next_blob, event, _created = claim_durable_event(
            dict(blob),
            position_id=pid,
            event_type=event_type,
            action=act,  # type: ignore[arg-type]
            as_of=as_of,
            quantity=quantity,
            detected_at=as_of,
        )
        next_blob = preserve_origin_decision_package(blob, next_blob)
        kind = (event_type or "").upper()
        which = (
            "t1"
            if kind in ("T1", "TARGET_1")
            else "t2"
            if kind in ("T2", "TARGET_2")
            else None
        )
        if which is not None:
            pos = position_state_from_dict(next_blob)
            if pos is not None:
                advanced = apply_target_leg(
                    pos,
                    which=which,
                    status="triggered",
                    at=as_of,
                    event_id=getattr(event, "event_id", None),
                )
                if which == "t1" and advanced.target1_leg is not None:
                    next_blob["target1Leg"] = advanced.target1_leg.to_dict()
                if which == "t2" and advanced.target2_leg is not None:
                    next_blob["target2Leg"] = advanced.target2_leg.to_dict()
        expected_stop = _blob_current_stop(blob)
        status = str(blob.get("status") or "OPEN")
        row = await _cas_or_update(
            self._store,
            position_id=pid,
            expected_stop=expected_stop,
            status=status,
            position_state=next_blob,
        )
        if row is not None:
            return event
        latest = await self._store.get_open_for_instrument(acc, inst)
        latest_blob = row_position_state(latest) if latest is not None else None
        if latest_blob is None:
            return None
        from bolsa_application.position_event_log import events_from_blob, find_matching_event

        found = find_matching_event(
            events_from_blob(latest_blob),
            position_id=pid,
            event_type=event_type,
            action=act,
            as_of_day=(as_of or "")[:10],
            next_stop=None,
        )
        return found

    async def patch_target_leg(
        self,
        *,
        account_id: str,
        instrument_id: str,
        which: str,
        status: str,
        at: str | None,
        event_id: str | None = None,
        fill_id: str | None = None,
    ) -> Any | None:
        """V1.52 — persiste triggered/failed sin mutar stop."""
        acc = account_id.strip() if account_id else ""
        inst = instrument_id.strip() if instrument_id else ""
        if not acc or not inst or which not in ("t1", "t2"):
            return None
        if status not in ("pending", "triggered", "executed", "failed"):
            return None
        existing = await self._store.get_open_for_instrument(acc, inst)
        if existing is None:
            return None
        pid = row_position_id(existing)
        blob = row_position_state(existing)
        if pid is None or blob is None:
            return None
        pos = position_state_from_dict(blob)
        if pos is None:
            return None
        advanced = apply_target_leg(
            pos,
            which=which,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            at=at,
            event_id=event_id,
            fill_id=fill_id,
        )
        next_blob = dict(blob)
        next_blob = preserve_origin_decision_package(blob, next_blob)
        from bolsa_application.position_event_log import preserve_position_events

        next_blob = preserve_position_events(blob, next_blob)
        if which == "t1" and advanced.target1_leg is not None:
            next_blob["target1Leg"] = advanced.target1_leg.to_dict()
        if which == "t2" and advanced.target2_leg is not None:
            next_blob["target2Leg"] = advanced.target2_leg.to_dict()
        expected_stop = _blob_current_stop(blob)
        row_status = str(blob.get("status") or pos.status)
        return await _cas_or_update(
            self._store,
            position_id=pid,
            expected_stop=expected_stop,
            status=row_status,
            position_state=next_blob,
        )
