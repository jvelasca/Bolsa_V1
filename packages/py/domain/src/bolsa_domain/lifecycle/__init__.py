"""V1.87 — Lifecycle event domain kernel (pure: no infra / FastAPI).

FSM + identity envelope + strict idempotency + ENTRY accounting + Decimal money.
Sequence numbers are assigned by the store under an aggregate lock, not here.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

LifecycleEventKind = Literal[
    "POSITION_OPENED",
    "T1_TRIGGERED",
    "T1_EXECUTED",
    "T2_TRIGGERED",
    "T2_EXECUTED",
    "TRAIL_APPLIED",
    "EXIT_REQUIRED",
    "POSITION_CLOSED",
]

LifecycleStage = Literal[
    "clean",
    "candidate",
    "open",
    "t1_ready",
    "t1_executed",
    "trailing",
    "exit_required",
    "t2_ready",
    "t2_executed",
    "closed",
]

LineagePath = Literal["trail", "t2"]

LifecycleAppendErrorCode = Literal[
    "illegal_transition",
    "time_regression",
    "duplicate_fill_id",
    "position_mismatch",
    "identity_mismatch",
    "invalid_kind",
    "invalid_payload",
    "event_id_conflict",
    "trail_relaxation",
    "invalid_timestamp",
]

FILL_KINDS: frozenset[str] = frozenset(
    {"POSITION_OPENED", "T1_EXECUTED", "T2_EXECUTED", "POSITION_CLOSED"}
)
EXIT_FILL_KINDS: frozenset[str] = frozenset(
    {"T1_EXECUTED", "T2_EXECUTED", "POSITION_CLOSED"}
)
WIRE_EVENT_KINDS: frozenset[str] = frozenset(
    {"T1_EXECUTED", "T2_TRIGGERED", "T2_EXECUTED", "POSITION_CLOSED"}
)

LIFECYCLE_BIRTH_QTY = Decimal("10")
LIFECYCLE_AVG_COST = Decimal("100")
LIFECYCLE_CASH = Decimal("100000")
LIFECYCLE_INITIAL_STOP = Decimal("95")
LIFECYCLE_INITIAL_RISK = (LIFECYCLE_AVG_COST - LIFECYCLE_INITIAL_STOP) * LIFECYCLE_BIRTH_QTY
LIFECYCLE_REMAINING_AFTER_T1 = Decimal("5")
LIFECYCLE_REMAINING_AFTER_T2 = Decimal("2")
_MONEY_EPS = Decimal("0.000000001")

DEFAULT_AT: dict[str, str] = {
    "POSITION_OPENED": "2026-09-02T10:00:00.000Z",
    "T1_TRIGGERED": "2026-09-02T11:00:00.000Z",
    "T1_EXECUTED": "2026-09-02T11:30:00.000Z",
    "TRAIL_APPLIED": "2026-09-02T12:00:00.000Z",
    "T2_TRIGGERED": "2026-09-02T12:15:00.000Z",
    "T2_EXECUTED": "2026-09-02T12:45:00.000Z",
    "EXIT_REQUIRED": "2026-09-02T14:00:00.000Z",
    "POSITION_CLOSED": "2026-09-02T15:00:00.000Z",
}

MOCK_OPEN_FILL_ID = "fill-mock-entry"
MOCK_T1_FILL_ID = "fill-mock-t1"
MOCK_T2_FILL_ID = "fill-mock-t2"
MOCK_CLOSE_FILL_ID = "fill-mock-exit"

TRANSITIONS: dict[str, dict[str, str]] = {
    "clean": {},
    "candidate": {"POSITION_OPENED": "open"},
    # V1.89: SEMI full exit may close from open/t1 without trail theater.
    "open": {
        "T1_TRIGGERED": "t1_ready",
        "T1_EXECUTED": "t1_executed",
        "POSITION_CLOSED": "closed",
    },
    "t1_ready": {"T1_EXECUTED": "t1_executed", "POSITION_CLOSED": "closed"},
    "t1_executed": {
        "TRAIL_APPLIED": "trailing",
        "T2_TRIGGERED": "t2_ready",
        "POSITION_CLOSED": "closed",
    },
    "trailing": {"EXIT_REQUIRED": "exit_required", "POSITION_CLOSED": "closed"},
    "exit_required": {"POSITION_CLOSED": "closed"},
    "t2_ready": {"T2_EXECUTED": "t2_executed"},
    "t2_executed": {"POSITION_CLOSED": "closed"},
    "closed": {},
}

HASH_FIELDS = (
    "kind",
    "at",
    "positionId",
    "accountId",
    "instrumentId",
    "decisionId",
    "tradePlanId",
    "symbol",
    "side",
    "currency",
    "fillId",
    "quantity",
    "price",
    "fees",
    "venue",
    "venueOrderId",
    "previousStop",
    "newStop",
    "reason",
    "revisionId",
)


@dataclass(frozen=True, slots=True)
class LifecycleAppendError:
    code: LifecycleAppendErrorCode
    message: str


@dataclass(frozen=True, slots=True)
class LifecycleIdentity:
    account_id: str
    position_id: str
    instrument_id: str
    symbol: str
    decision_id: str
    trade_plan_id: str
    side: str = "LONG"
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class LifecycleStoreEvent:
    event_id: str
    position_id: str
    kind: LifecycleEventKind
    at: str
    account_id: str | None = None
    instrument_id: str | None = None
    decision_id: str | None = None
    trade_plan_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    currency: str | None = None
    fill_id: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    fees: Decimal | None = None
    venue: str | None = None
    venue_order_id: str | None = None
    previous_stop: Decimal | None = None
    new_stop: Decimal | None = None
    reason: str | None = None
    revision_id: str | None = None
    payload_hash: str | None = None
    schema_version: int = 1
    causation_id: str | None = None
    correlation_id: str | None = None
    sequence_no: int | None = None

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "positionId": self.position_id,
            "kind": self.kind,
            "at": self.at,
            "accountId": self.account_id,
            "instrumentId": self.instrument_id,
            "decisionId": self.decision_id,
            "tradePlanId": self.trade_plan_id,
            "symbol": self.symbol,
            "side": self.side,
            "currency": self.currency,
            "fillId": self.fill_id,
            "quantity": _json_money(self.quantity),
            "price": _json_money(self.price),
            "fees": _json_money(self.fees),
            "venue": self.venue,
            "venueOrderId": self.venue_order_id,
            "previousStop": _json_money(self.previous_stop),
            "newStop": _json_money(self.new_stop),
            "reason": self.reason,
            "revisionId": self.revision_id,
            "payloadHash": self.payload_hash,
            "schemaVersion": self.schema_version,
            "causationId": self.causation_id,
            "correlationId": self.correlation_id,
            "sequenceNo": self.sequence_no,
        }


@dataclass(frozen=True, slots=True)
class LifecycleEventInput:
    kind: LifecycleEventKind
    at: str | None = None
    event_id: str | None = None
    position_id: str | None = None
    account_id: str | None = None
    instrument_id: str | None = None
    decision_id: str | None = None
    trade_plan_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    currency: str | None = None
    fill_id: str | None = None
    quantity: Decimal | float | int | str | None = None
    price: Decimal | float | int | str | None = None
    fees: Decimal | float | int | str | None = None
    venue: str | None = None
    venue_order_id: str | None = None
    previous_stop: Decimal | float | int | str | None = None
    new_stop: Decimal | float | int | str | None = None
    reason: str | None = None
    revision_id: str | None = None
    causation_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleAccounting:
    cash: Decimal
    remaining: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    last_price: Decimal
    market_value: Decimal
    total_equity: Decimal
    avg_cost: Decimal
    initial_equity: Decimal = LIFECYCLE_CASH


@dataclass(frozen=True, slots=True)
class AppendOk:
    log: tuple[LifecycleStoreEvent, ...]
    event: LifecycleStoreEvent
    idempotent: bool
    stage: LifecycleStage
    lineage_path: LineagePath


@dataclass(frozen=True, slots=True)
class AppendFail:
    error: LifecycleAppendError


def _as_money(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(str(int(value)))
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise TypeError(f"unsupported money type {type(value)!r}")


def _json_money(value: Decimal | None) -> int | float | None:
    """JSON-stable number: ints stay ints so hashes do not depend on Decimal."""
    if value is None:
        return None
    integral = value.to_integral_value()
    if value == integral:
        return int(integral)
    return float(value)


def _finite_positive(value: Decimal | None, *, allow_zero: bool = False) -> bool:
    if value is None:
        return False
    if not value.is_finite():
        return False
    if allow_zero:
        return value >= 0
    return value > 0


def _ms(iso: str) -> float | LifecycleAppendError:
    try:
        # Accept trailing Z
        normalized = iso.replace("Z", "+00:00") if iso.endswith("Z") else iso
        dt = datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return LifecycleAppendError(
            code="invalid_timestamp",
            message=f"invalid ISO timestamp: {iso!r}",
        )
    return dt.timestamp() * 1000.0


def last_price_for_stage(stage: LifecycleStage, lineage_path: LineagePath) -> Decimal:
    if stage in ("t2_ready", "t2_executed"):
        return Decimal("110")
    if stage == "closed":
        return Decimal("110") if lineage_path == "t2" else Decimal("106")
    return Decimal("106")


def validate_transition_result(
    current_state: LifecycleStage,
    kind: LifecycleEventKind,
) -> tuple[Literal[True], LifecycleStage] | tuple[Literal[False], LifecycleAppendError]:
    next_state = TRANSITIONS.get(current_state, {}).get(kind)
    if next_state is None:
        return (
            False,
            LifecycleAppendError(
                code="illegal_transition",
                message=f"illegal transition {current_state} + {kind}",
            ),
        )
    return (True, next_state)  # type: ignore[return-value]


def canonical_payload_for_hash(event: LifecycleStoreEvent) -> dict[str, Any]:
    raw = event.to_canonical_dict()
    out: dict[str, Any] = {}
    for key in HASH_FIELDS:
        camel = key
        # HASH_FIELDS already camelCase-ish mixed — map from canonical
        mapping = {
            "kind": "kind",
            "at": "at",
            "positionId": "positionId",
            "accountId": "accountId",
            "instrumentId": "instrumentId",
            "decisionId": "decisionId",
            "tradePlanId": "tradePlanId",
            "symbol": "symbol",
            "side": "side",
            "currency": "currency",
            "fillId": "fillId",
            "quantity": "quantity",
            "price": "price",
            "fees": "fees",
            "venue": "venue",
            "venueOrderId": "venueOrderId",
            "previousStop": "previousStop",
            "newStop": "newStop",
            "reason": "reason",
            "revisionId": "revisionId",
        }
        src = mapping[camel]
        val = raw.get(src)
        if val is not None:
            out[src] = val
    return out


def compute_payload_hash(event: LifecycleStoreEvent) -> str:
    payload = canonical_payload_for_hash(event)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _scoped_mock_fill_id(base: str, position_id: str) -> str:
    """Namespace mock fill IDs by position so global UNIQUE(fill_id) stays safe."""
    return f"{base}:{position_id}"


def _default_fill(
    kind: LifecycleEventKind,
    remaining_before: Decimal,
    lineage_path: LineagePath,
    *,
    position_id: str,
) -> dict[str, Any] | None:
    if kind == "POSITION_OPENED":
        return {
            "quantity": LIFECYCLE_BIRTH_QTY,
            "price": LIFECYCLE_AVG_COST,
            "fill_id": _scoped_mock_fill_id(MOCK_OPEN_FILL_ID, position_id),
        }
    if kind == "T1_EXECUTED":
        return {
            "quantity": LIFECYCLE_BIRTH_QTY - LIFECYCLE_REMAINING_AFTER_T1,
            "price": Decimal("105"),
            "fill_id": _scoped_mock_fill_id(MOCK_T1_FILL_ID, position_id),
        }
    if kind == "T2_EXECUTED":
        return {
            "quantity": LIFECYCLE_REMAINING_AFTER_T1 - LIFECYCLE_REMAINING_AFTER_T2,
            "price": Decimal("110"),
            "fill_id": _scoped_mock_fill_id(MOCK_T2_FILL_ID, position_id),
        }
    if kind == "POSITION_CLOSED":
        return {
            "quantity": remaining_before,
            "price": last_price_for_stage("closed", lineage_path),
            "fill_id": _scoped_mock_fill_id(MOCK_CLOSE_FILL_ID, position_id),
        }
    return None


def normalize_lifecycle_event(
    input_event: LifecycleEventInput,
    *,
    remaining_before: Decimal = Decimal("0"),
    lineage_path: LineagePath = "trail",
    defaults: LifecycleIdentity | None = None,
) -> LifecycleStoreEvent | LifecycleAppendError:
    kind = input_event.kind
    if kind not in TRANSITIONS["candidate"] and kind not in {
        k for edges in TRANSITIONS.values() for k in edges
    }:
        # still allow known kinds from FILL etc.
        pass
    at = input_event.at or DEFAULT_AT.get(kind)
    if not at:
        return LifecycleAppendError(code="invalid_kind", message=f"unknown kind {kind}")
    parsed = _ms(at)
    if isinstance(parsed, LifecycleAppendError):
        return parsed

    identity = defaults or LifecycleIdentity(
        account_id=input_event.account_id or "default-account-seed",
        position_id=input_event.position_id or "pos-e2e-lifecycle-1",
        instrument_id=input_event.instrument_id or "inst-aapl",
        symbol=input_event.symbol or "AAPL",
        decision_id=input_event.decision_id or "dec-e2e-lifecycle-1",
        trade_plan_id=input_event.trade_plan_id or "tp-e2e-lifecycle-1",
        side=input_event.side or "LONG",
        currency=input_event.currency or "USD",
    )

    event_id = input_event.event_id or str(uuid.uuid4())
    position_id = input_event.position_id or identity.position_id

    base = LifecycleStoreEvent(
        event_id=event_id,
        position_id=position_id,
        kind=kind,
        at=at,
        account_id=input_event.account_id or identity.account_id,
        instrument_id=input_event.instrument_id or identity.instrument_id,
        decision_id=input_event.decision_id or identity.decision_id,
        trade_plan_id=input_event.trade_plan_id or identity.trade_plan_id,
        symbol=input_event.symbol or identity.symbol,
        side=input_event.side or identity.side,
        currency=input_event.currency or identity.currency,
        causation_id=input_event.causation_id,
        correlation_id=input_event.correlation_id,
    )

    if kind == "TRAIL_APPLIED":
        previous_stop = (
            _as_money(input_event.previous_stop)
            if input_event.previous_stop is not None
            else LIFECYCLE_INITIAL_STOP
        )
        assert previous_stop is not None
        new_stop = (
            _as_money(input_event.new_stop)
            if input_event.new_stop is not None
            else previous_stop + Decimal("3")
        )
        event = replace(
            base,
            previous_stop=previous_stop,
            new_stop=new_stop,
            reason=input_event.reason or "trail",
            revision_id=input_event.revision_id or f"rev-trail-{position_id}",
            fill_id=input_event.fill_id,
        )
        return replace(event, payload_hash=compute_payload_hash(event))

    if kind in FILL_KINDS:
        defaults_fill = _default_fill(
            kind, remaining_before, lineage_path, position_id=position_id
        )
        qty = (
            input_event.quantity
            if input_event.quantity is not None
            else (defaults_fill or {}).get("quantity")
        )
        price = (
            input_event.price
            if input_event.price is not None
            else (defaults_fill or {}).get("price")
        )
        fill_id = input_event.fill_id or (defaults_fill or {}).get("fill_id")
        fees = Decimal("0") if input_event.fees is None else input_event.fees
        event = replace(
            base,
            fill_id=str(fill_id) if fill_id is not None else None,
            quantity=_as_money(qty),
            price=_as_money(price),
            fees=_as_money(fees),
            venue=input_event.venue or "MOCK",
            venue_order_id=input_event.venue_order_id,  # never invent
            currency=input_event.currency or identity.currency,
        )
        return replace(event, payload_hash=compute_payload_hash(event))

    event = replace(base, fill_id=input_event.fill_id)
    return replace(event, payload_hash=compute_payload_hash(event))


def remaining_after_log(
    events: list[LifecycleStoreEvent] | tuple[LifecycleStoreEvent, ...],
) -> Decimal:
    remaining = Decimal("0")
    for ev in events:
        qty = ev.quantity or Decimal("0")
        if ev.kind == "POSITION_OPENED":
            remaining += qty
        elif ev.kind in EXIT_FILL_KINDS:
            remaining -= qty
    return remaining


def reduce_lifecycle_events(
    events: list[LifecycleStoreEvent] | tuple[LifecycleStoreEvent, ...],
) -> tuple[LifecycleStage, LineagePath]:
    stage: LifecycleStage = "candidate"
    lineage_path: LineagePath = "trail"
    for ev in events:
        ok, result = validate_transition_result(stage, ev.kind)
        if not ok:
            assert isinstance(result, LifecycleAppendError)
            raise ValueError(
                f"reduce_lifecycle_events: {result.message} at {ev.event_id}"
            )
        stage = result  # type: ignore[assignment]
        if ev.kind in ("T2_TRIGGERED", "T2_EXECUTED"):
            lineage_path = "t2"
        elif ev.kind in ("TRAIL_APPLIED", "EXIT_REQUIRED"):
            lineage_path = "trail"
    return stage, lineage_path


def identity_from_event(event: LifecycleStoreEvent) -> LifecycleIdentity:
    return LifecycleIdentity(
        account_id=event.account_id or "",
        position_id=event.position_id,
        instrument_id=event.instrument_id or "",
        symbol=event.symbol or "",
        decision_id=event.decision_id or "",
        trade_plan_id=event.trade_plan_id or "",
        side=event.side or "LONG",
        currency=event.currency or "USD",
    )


def _validate_identity(
    log: list[LifecycleStoreEvent] | tuple[LifecycleStoreEvent, ...],
    event: LifecycleStoreEvent,
) -> LifecycleAppendError | None:
    if not log:
        return None
    anchor = identity_from_event(log[0])
    if event.position_id != anchor.position_id:
        return LifecycleAppendError(
            code="position_mismatch",
            message=f"positionId {event.position_id} ≠ log {anchor.position_id}",
        )
    checks = (
        ("instrumentId", event.instrument_id, anchor.instrument_id),
        ("decisionId", event.decision_id, anchor.decision_id),
        ("tradePlanId", event.trade_plan_id, anchor.trade_plan_id),
        ("accountId", event.account_id, anchor.account_id),
        ("symbol", event.symbol, anchor.symbol),
        ("side", event.side, anchor.side),
        ("currency", event.currency, anchor.currency),
    )
    for label, got, expected in checks:
        if got is not None and expected and got != expected:
            return LifecycleAppendError(
                code="identity_mismatch",
                message=f"{label} {got} ≠ envelope {expected}",
            )
    return None


def _validate_time(
    log: list[LifecycleStoreEvent] | tuple[LifecycleStoreEvent, ...],
    event: LifecycleStoreEvent,
) -> LifecycleAppendError | None:
    previous = log[-1] if log else None
    next_ms = _ms(event.at)
    if isinstance(next_ms, LifecycleAppendError):
        return next_ms
    if previous:
        prev_ms = _ms(previous.at)
        if isinstance(prev_ms, LifecycleAppendError):
            return prev_ms
        if event.kind == "POSITION_CLOSED":
            if next_ms <= prev_ms:
                return LifecycleAppendError(
                    code="time_regression",
                    message=(
                        f"POSITION_CLOSED at {event.at} must be > previous {previous.at}"
                    ),
                )
        elif next_ms < prev_ms:
            return LifecycleAppendError(
                code="time_regression",
                message=f"at {event.at} < previous {previous.at}",
            )

    t1_trig = next((e for e in log if e.kind == "T1_TRIGGERED"), None)
    if event.kind == "T1_EXECUTED" and t1_trig:
        t1_ms = _ms(t1_trig.at)
        if isinstance(t1_ms, LifecycleAppendError):
            return t1_ms
        if next_ms <= t1_ms:
            return LifecycleAppendError(
                code="time_regression",
                message="T1_EXECUTED must be after T1_TRIGGERED",
            )

    t1_exec = next((e for e in (*log, event) if e.kind == "T1_EXECUTED"), None)
    if event.kind == "TRAIL_APPLIED" and t1_exec:
        t1e = _ms(t1_exec.at)
        if isinstance(t1e, LifecycleAppendError):
            return t1e
        if next_ms < t1e:
            return LifecycleAppendError(
                code="time_regression",
                message="TRAIL_APPLIED must be >= T1_EXECUTED",
            )

    t2_trig = next((e for e in log if e.kind == "T2_TRIGGERED"), None)
    if event.kind == "T2_EXECUTED" and t2_trig:
        t2_ms = _ms(t2_trig.at)
        if isinstance(t2_ms, LifecycleAppendError):
            return t2_ms
        if next_ms <= t2_ms:
            return LifecycleAppendError(
                code="time_regression",
                message="T2_EXECUTED must be after T2_TRIGGERED",
            )
    return None


def _validate_payload(
    event: LifecycleStoreEvent,
    *,
    remaining_before: Decimal,
    stage: LifecycleStage,
    lineage_path: LineagePath,
) -> LifecycleAppendError | None:
    if event.kind in FILL_KINDS:
        qty = event.quantity
        price = event.price
        fees = event.fees if event.fees is not None else Decimal("0")
        if not _finite_positive(qty):
            return LifecycleAppendError(
                code="invalid_payload",
                message=f"quantity must be > 0, got {qty}",
            )
        if not _finite_positive(price):
            return LifecycleAppendError(
                code="invalid_payload",
                message=f"price must be > 0, got {price}",
            )
        if fees is None or not fees.is_finite() or fees < 0:
            return LifecycleAppendError(
                code="invalid_payload",
                message=f"fees must be >= 0 finite, got {fees}",
            )
        assert qty is not None
        if event.kind == "POSITION_OPENED":
            pass
        elif event.kind == "POSITION_CLOSED":
            if abs(qty - remaining_before) > _MONEY_EPS:
                return LifecycleAppendError(
                    code="invalid_payload",
                    message=(
                        f"POSITION_CLOSED.quantity {qty} != remaining {remaining_before}"
                    ),
                )
        elif qty > remaining_before + _MONEY_EPS:
            return LifecycleAppendError(
                code="invalid_payload",
                message=f"quantity {qty} > remaining {remaining_before}",
            )

    if event.kind == "TRAIL_APPLIED":
        prev = event.previous_stop
        new = event.new_stop
        if prev is None or new is None:
            return LifecycleAppendError(
                code="invalid_payload",
                message="TRAIL_APPLIED requires previousStop and newStop",
            )
        if not prev.is_finite() or not new.is_finite():
            return LifecycleAppendError(
                code="invalid_payload",
                message="trail stops must be finite",
            )
        side = (event.side or "LONG").upper()
        if side == "LONG" and new < prev:
            return LifecycleAppendError(
                code="trail_relaxation",
                message=f"LONG trail newStop {new} < previousStop {prev}",
            )
        if side == "SHORT" and new > prev:
            return LifecycleAppendError(
                code="trail_relaxation",
                message=f"SHORT trail newStop {new} > previousStop {prev}",
            )
        last_price = last_price_for_stage(stage, lineage_path)
        if side == "LONG" and new >= last_price:
            return LifecycleAppendError(
                code="invalid_payload",
                message=f"LONG trail newStop {new} must be < lastPrice {last_price}",
            )
        if side == "SHORT" and new <= last_price:
            return LifecycleAppendError(
                code="invalid_payload",
                message=f"SHORT trail newStop {new} must be > lastPrice {last_price}",
            )
    return None


def append_validated_lifecycle_event(
    log: list[LifecycleStoreEvent] | tuple[LifecycleStoreEvent, ...],
    input_event: LifecycleEventInput,
    *,
    defaults: LifecycleIdentity | None = None,
) -> AppendOk | AppendFail:
    log_list = list(log)
    try:
        stage, lineage_path = (
            reduce_lifecycle_events(log_list) if log_list else ("candidate", "trail")
        )
    except ValueError as exc:
        return AppendFail(
            error=LifecycleAppendError(code="illegal_transition", message=str(exc))
        )

    # Idempotent replay: normalize against prefix before existing event so
    # remaining-dependent defaults (CLOSE qty) stay stable after append.
    if input_event.event_id:
        existing_idx = next(
            (
                i
                for i, row in enumerate(log_list)
                if row.event_id == input_event.event_id
            ),
            None,
        )
        if existing_idx is not None:
            existing = log_list[existing_idx]
            prefix = log_list[:existing_idx]
            try:
                prefix_stage, prefix_path = (
                    reduce_lifecycle_events(prefix)
                    if prefix
                    else ("candidate", "trail")
                )
            except ValueError as exc:
                return AppendFail(
                    error=LifecycleAppendError(
                        code="illegal_transition", message=str(exc)
                    )
                )
            remaining_at = remaining_after_log(prefix)
            candidate = normalize_lifecycle_event(
                input_event,
                remaining_before=remaining_at,
                lineage_path=prefix_path,
                defaults=defaults,
            )
            if isinstance(candidate, LifecycleAppendError):
                return AppendFail(error=candidate)
            existing_hash = existing.payload_hash or compute_payload_hash(existing)
            new_hash = candidate.payload_hash or compute_payload_hash(candidate)
            if existing_hash == new_hash:
                return AppendOk(
                    log=tuple(log_list),
                    event=existing,
                    idempotent=True,
                    stage=stage,
                    lineage_path=lineage_path,
                )
            # V1.90 — same eventId+fillId + same economic fields ⇒ idempotent
            # even if `at` drifted on replay (never use wall-clock in payload).
            if (
                existing.fill_id
                and candidate.fill_id
                and existing.fill_id == candidate.fill_id
                and existing.kind == candidate.kind
                and existing.quantity == candidate.quantity
                and existing.price == candidate.price
                and existing.position_id == candidate.position_id
            ):
                return AppendOk(
                    log=tuple(log_list),
                    event=existing,
                    idempotent=True,
                    stage=stage,
                    lineage_path=lineage_path,
                )
            return AppendFail(
                error=LifecycleAppendError(
                    code="event_id_conflict",
                    message=(
                        f"eventId {input_event.event_id} already exists "
                        "with different payload"
                    ),
                )
            )

    remaining_before = remaining_after_log(log_list)
    normalized = normalize_lifecycle_event(
        input_event,
        remaining_before=remaining_before,
        lineage_path=lineage_path,
        defaults=defaults,
    )
    if isinstance(normalized, LifecycleAppendError):
        return AppendFail(error=normalized)
    event = normalized

    identity_err = _validate_identity(log_list, event)
    if identity_err:
        return AppendFail(error=identity_err)

    if event.fill_id:
        dup = next(
            (
                row
                for row in log_list
                if row.fill_id == event.fill_id and row.event_id != event.event_id
            ),
            None,
        )
        if dup:
            return AppendFail(
                error=LifecycleAppendError(
                    code="duplicate_fill_id",
                    message=f"fillId {event.fill_id} already on {dup.event_id}",
                )
            )

    time_err = _validate_time(log_list, event)
    if time_err:
        return AppendFail(error=time_err)

    ok, result = validate_transition_result(stage, event.kind)
    if not ok:
        assert isinstance(result, LifecycleAppendError)
        return AppendFail(error=result)

    payload_err = _validate_payload(
        event,
        remaining_before=remaining_before,
        stage=stage,
        lineage_path=lineage_path,
    )
    if payload_err:
        return AppendFail(error=payload_err)

    next_log = (*log_list, event)
    next_stage, next_path = reduce_lifecycle_events(next_log)
    return AppendOk(
        log=next_log,
        event=event,
        idempotent=False,
        stage=next_stage,
        lineage_path=next_path,
    )


def account_lifecycle_fills(
    events: list[LifecycleStoreEvent] | tuple[LifecycleStoreEvent, ...],
) -> LifecycleAccounting:
    stage, lineage_path = reduce_lifecycle_events(events)
    cash = LIFECYCLE_CASH
    remaining = Decimal("0")
    realized_pnl = Decimal("0")
    avg_cost = LIFECYCLE_AVG_COST

    for ev in events:
        if ev.kind not in FILL_KINDS:
            continue
        qty = ev.quantity or Decimal("0")
        price = ev.price or Decimal("0")
        fees = ev.fees or Decimal("0")
        if ev.kind == "POSITION_OPENED":
            cash -= qty * price + fees
            remaining += qty
            avg_cost = price
        else:
            cash += qty * price - fees
            remaining -= qty
            realized_pnl += (price - avg_cost) * qty - fees

    if remaining < -_MONEY_EPS:
        raise ValueError(f"account_lifecycle_fills: remaining {remaining} < 0")

    last_price = last_price_for_stage(stage, lineage_path)
    market_value = last_price * remaining
    unrealized_pnl = (last_price - avg_cost) * remaining
    total_pnl = realized_pnl + unrealized_pnl
    total_equity = cash + market_value
    return LifecycleAccounting(
        cash=cash,
        remaining=remaining,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        last_price=last_price,
        market_value=market_value,
        total_equity=total_equity,
        avg_cost=avg_cost,
        initial_equity=LIFECYCLE_CASH,
    )


def assert_equity_invariant(
    acct: LifecycleAccounting, *, tol: Decimal = Decimal("0.000001")
) -> None:
    expected = acct.initial_equity + acct.realized_pnl + acct.unrealized_pnl
    if abs(acct.total_equity - expected) > tol:
        raise AssertionError(
            f"equity {acct.total_equity} != initial+realized+unrealized {expected}"
        )


__all__ = [
    "AppendFail",
    "AppendOk",
    "FILL_KINDS",
    "LIFECYCLE_AVG_COST",
    "LIFECYCLE_BIRTH_QTY",
    "LIFECYCLE_CASH",
    "LIFECYCLE_INITIAL_RISK",
    "LIFECYCLE_INITIAL_STOP",
    "LifecycleAccounting",
    "LifecycleAppendError",
    "LifecycleAppendErrorCode",
    "LifecycleEventInput",
    "LifecycleEventKind",
    "LifecycleIdentity",
    "LifecycleStage",
    "LifecycleStoreEvent",
    "LineagePath",
    "account_lifecycle_fills",
    "append_validated_lifecycle_event",
    "assert_equity_invariant",
    "compute_payload_hash",
    "last_price_for_stage",
    "normalize_lifecycle_event",
    "reduce_lifecycle_events",
    "remaining_after_log",
    "validate_transition_result",
]
