"""DEX-5 — Operational invariants / property suite (ADR-035).

Ancla spine: qty ≥ 0 · filled ≤ ordered · terminal no re-ejecuta ·
1 decision → ≤1 live order · drift blocks opening · protect no ↑ exposición.
Sin hypothesis: grafo OR-3 + random.Random seeded + parametrize.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest

from bolsa_analytics.cognitive.operational_invariants import (
    adverse_exposure,
    filled_le_ordered,
    is_hard_terminal_no_fill,
    is_terminal_status,
    protect_stop_worsens_exposure,
    qty_non_negative,
    qty_positive,
)
from bolsa_analytics.cognitive.paper_order import (
    ALLOWED_TRANSITIONS,
    PaperOrderStatus,
    apply_paper_order_fill,
    build_paper_order,
    stable_order_id_from_decision,
    transition_paper_order,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    build_position_state_from_fill,
)
from bolsa_application.confirm_recommendation import (
    ConfirmRecommendationIntent,
    confirm_leg_idempotency_key,
)
from bolsa_application.reconciliation_opening_gate import (
    reconciliation_opening_veto_reason,
)
from bolsa_application.risk_engine import check_opening
from bolsa_domain.entities.portfolio import TradeResult, Transaction

_OPEN_STATUSES: tuple[PaperOrderStatus, ...] = (
    "CREATED",
    "SUBMITTED",
    "ACK",
    "PARTIAL",
    "UNKNOWN",
)
_ALL_STATUSES: tuple[PaperOrderStatus, ...] = tuple(ALLOWED_TRANSITIONS.keys())


# ── helpers Confirm (OR-1 replay, thin) ──────────────────────────────────────


class _IdempotentTrade:
    def __init__(self) -> None:
        self._by_key: dict[str, TradeResult] = {}
        self.execute_calls = 0
        self.unique_fills = 0
        self._lock = asyncio.Lock()

    async def find_existing_by_idempotency(
        self,
        *,
        account_id: str | None = None,
        portfolio_id: str | None = None,
        idempotency_key: str,
    ) -> TradeResult | None:
        _ = account_id, portfolio_id
        return self._by_key.get(idempotency_key)

    async def execute(self, **kwargs: object) -> TradeResult:
        key = str(kwargs.get("idempotency_key") or "")
        async with self._lock:
            self.execute_calls += 1
            existing = self._by_key.get(key)
            if existing is not None:
                return existing
            self.unique_fills += 1
            tx = Transaction(
                id=f"tx-{self.unique_fills}",
                type="buy",  # type: ignore[arg-type]
                instrument_id="inst-1",
                symbol="SYM",
                quantity=5.0,
                price=12.0,
                total=60.0,
                executed_at="2026-08-26T12:00:00Z",
            )
            result = TradeResult(
                transaction=tx,
                summary=type("S", (), {"cash": 0.0})(),
            )
            self._by_key[key] = result
            return result


def _opening_raw(*, decision_id: str) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 5.0,
        "suggestedPrice": 12.0,
        "tradePlan": {
            "decisionId": decision_id,
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 12.0,
            "structuralStop": 10.8,
            "riskAmount": 500.0,
        },
    }


def _walk_to(
    rng: random.Random,
    target: PaperOrderStatus,
    *,
    quantity: float = 10.0,
) -> Any:
    """Camina el grafo desde CREATED hasta ``target`` (o PARTIAL previo)."""
    order = build_paper_order(
        order_id="ORD-DEX5",
        instrument_id="i",
        side="buy",
        quantity=quantity,
    )
    if target == "CREATED":
        return order
    path: list[PaperOrderStatus] = []
    if target == "PARTIAL":
        path = ["ACK", "PARTIAL"]
    elif target == "FILLED":
        # atajo OI-4 o vía ACK
        path = ["FILLED"] if rng.random() < 0.5 else ["ACK", "FILLED"]
    elif target in ALLOWED_TRANSITIONS["CREATED"]:
        path = [target]
    else:
        path = ["ACK", target] if target in ALLOWED_TRANSITIONS["ACK"] else [target]

    for nxt in path:
        if nxt == "PARTIAL":
            fill = rng.uniform(0.1, quantity - 0.1)
            order = transition_paper_order(order, "PARTIAL", filled_quantity=fill)
        elif nxt == "FILLED":
            order = apply_paper_order_fill(order, transaction_id="tx-w")
        else:
            order = transition_paper_order(order, nxt)
    return order


# ── I1 qty ≥ 0 ───────────────────────────────────────────────────────────────


def test_dex5_qty_positive_on_build() -> None:
    with pytest.raises(ValueError, match="qty_not_positive"):
        build_paper_order(instrument_id="i", side="buy", quantity=-1.0)
    with pytest.raises(ValueError, match="qty_not_positive"):
        build_paper_order(instrument_id="i", side="buy", quantity=0.0)
    order = build_paper_order(instrument_id="i", side="buy", quantity=1.0)
    assert qty_positive(order.quantity)
    assert qty_non_negative(order.quantity)


def test_dex5_property_qty_non_negative_after_legal_transitions() -> None:
    rng = random.Random(20260826)
    for _ in range(80):
        qty = rng.uniform(0.5, 100.0)
        status = rng.choice(_OPEN_STATUSES + ("FILLED", "REJECTED", "CANCELLED", "EXPIRED"))
        try:
            order = _walk_to(rng, status, quantity=qty)
        except ValueError:
            continue
        assert qty_non_negative(order.quantity)
        assert filled_le_ordered(order)


# ── I2 filled ≤ ordered ──────────────────────────────────────────────────────


def test_dex5_filled_gt_ordered_rejected() -> None:
    ack = transition_paper_order(
        build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=10.0),
        "ACK",
    )
    with pytest.raises(ValueError, match="filled_gt_ordered"):
        transition_paper_order(ack, "FILLED", filled_quantity=10.1)
    with pytest.raises(ValueError, match="filled_gt_ordered"):
        transition_paper_order(ack, "FILLED", filled_quantity=-0.1)


def test_dex5_property_filled_le_ordered_graph() -> None:
    rng = random.Random(42)
    for from_s, tos in ALLOWED_TRANSITIONS.items():
        for to_s in tos:
            if from_s in {"FILLED", "REJECTED", "CANCELLED", "EXPIRED"}:
                continue
            try:
                order = _walk_to(rng, from_s, quantity=10.0)
            except ValueError:
                continue
            if to_s == "PARTIAL":
                nxt = transition_paper_order(order, "PARTIAL", filled_quantity=3.0)
            elif to_s == "FILLED":
                nxt = apply_paper_order_fill(order, transaction_id="tx")
            else:
                nxt = transition_paper_order(order, to_s)
            assert filled_le_ordered(nxt), f"{from_s}->{to_s}"


# ── I3 terminal no re-ejecuta ────────────────────────────────────────────────


@pytest.mark.parametrize("terminal", ["REJECTED", "CANCELLED", "EXPIRED"])
def test_dex5_hard_terminal_cannot_fill(terminal: PaperOrderStatus) -> None:
    base = build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=2.0)
    done = transition_paper_order(base, terminal)
    assert is_hard_terminal_no_fill(done.status)
    assert is_terminal_status(done.status)
    with pytest.raises(ValueError, match="fill_from_terminal|illegal_transition"):
        apply_paper_order_fill(done, transaction_id="tx-x")


def test_dex5_property_terminal_no_reexec_seeded() -> None:
    rng = random.Random(7)
    for _ in range(40):
        terminal = rng.choice(("REJECTED", "CANCELLED", "EXPIRED", "FILLED"))
        order = _walk_to(rng, terminal, quantity=rng.uniform(1.0, 20.0))
        if terminal == "FILLED":
            again = apply_paper_order_fill(order, transaction_id="tx-other")
            assert again.status == "FILLED"
            assert again.transaction_id == order.transaction_id
            assert filled_le_ordered(again)
        else:
            with pytest.raises(ValueError):
                apply_paper_order_fill(order, transaction_id="tx-bad")


# ── I4 1 decision → ≤1 live order ────────────────────────────────────────────


def test_dex5_property_stable_order_id_deterministic() -> None:
    rng = random.Random(99)
    seen: dict[str, str] = {}
    for i in range(60):
        # mezcla alfanum / ruido
        decision = f"DEC-{rng.randint(1, 10_000)}-{i}"
        if rng.random() < 0.15:
            decision = f"  {decision}!!  "
        oid = stable_order_id_from_decision(decision)
        assert oid == stable_order_id_from_decision(decision)
        assert oid.startswith("ORD-")
        key = decision.strip()
        if key in seen:
            assert seen[key] == oid
        else:
            # colisión rara entre keys distintas: permitir solo si slug colapsa
            for other_key, other_oid in seen.items():
                if other_oid == oid:
                    # mismo slug efectivo
                    assert (
                        "".join(c for c in key if c.isalnum() or c in "-_")[:48]
                        == "".join(c for c in other_key if c.isalnum() or c in "-_")[:48]
                        or (not any(c.isalnum() or c in "-_" for c in key))
                    )
            seen[key] = oid


@pytest.mark.asyncio
async def test_dex5_one_decision_one_live_order_confirm_replay() -> None:
    decision_id = "DEC-DEX5-ONE"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    fake = _IdempotentTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    raw = _opening_raw(decision_id=decision_id)
    first = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    second = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert first["paperOrder"]["orderId"] == stable_order_id_from_decision(leg_key)
    assert second["paperOrder"]["orderId"] == first["paperOrder"]["orderId"]
    assert fake.unique_fills == 1
    assert first["paperOrder"]["status"] == "FILLED"
    assert second["paperOrder"]["status"] == "FILLED"


# ── I5 drift / incident blocks opening ───────────────────────────────────────


@pytest.mark.parametrize(
    ("portfolio", "live", "venue", "expect"),
    [
        ("drift", None, "paper", "reconciliation:portfolio_drift"),
        ("clean", "drift", "live", "reconciliation:live_drift"),
        ("clean", "unavailable", "live", "reconciliation:live_unavailable"),
        ("clean", None, "paper", None),
    ],
)
def test_dex5_drift_veto_reason_matrix(
    portfolio: str | None,
    live: str | None,
    venue: str,
    expect: str | None,
) -> None:
    got = reconciliation_opening_veto_reason(
        portfolio_recon_status=portfolio,  # type: ignore[arg-type]
        live_recon_status=live,  # type: ignore[arg-type]
        broker_venue=venue,
        require=True,
    )
    assert got == expect


def test_dex5_property_drift_and_incident_block_opening() -> None:
    rng = random.Random(13)
    blocking: list[dict[str, Any]] = [
        {"portfolio_recon_status": "drift", "require_recon_veto": True},
        {
            "live_recon_status": "drift",
            "broker_venue": "live",
            "require_recon_veto": True,
        },
        {
            "live_recon_status": "unavailable",
            "broker_venue": "live",
            "require_recon_veto": True,
        },
        {"incident_status": "unresolved", "require_incident_veto": True},
    ]
    for _ in range(30):
        kwargs = dict(rng.choice(blocking))
        d = check_opening(
            profile=None,
            instrument_id="i1",
            symbol="SAN",
            trade_type="buy",
            quantity=1,
            price=10,
            signal_kind="entry_long",
            equity=10_000.0,
            **kwargs,
        )
        assert d.verdict == "DENY"
        assert any(
            r.startswith("reconciliation:") or r == "incident:unresolved"
            for r in d.reasons
        )


# ── I6 protect no aumenta exposición ─────────────────────────────────────────


def _open_pos(*, direction: str, entry: float, stop: float):
    plan = {
        "decisionId": "dec-dex5",
        "instrumentId": "MSFT",
        "direction": direction,
        "status": "TRIGGERED",
        "entry": entry,
        "structuralStop": stop,
        "target1": entry + (5.0 if direction == "long" else -5.0),
    }
    pos = build_position_state_from_fill(
        plan,
        fill_price=entry,
        fill_quantity=10.0,
        filled_at="2026-08-26T12:00:00Z",
        position_id="pos-dex5",
    )
    assert pos is not None
    return pos


def test_dex5_property_protect_no_worse_exposure() -> None:
    rng = random.Random(26)
    for _ in range(80):
        direction = rng.choice(("long", "short"))
        entry = rng.uniform(50.0, 200.0)
        if direction == "long":
            current = entry - rng.uniform(1.0, 10.0)
            better = current + rng.uniform(0.1, 5.0)
            worse = current - rng.uniform(0.1, 5.0)
        else:
            current = entry + rng.uniform(1.0, 10.0)
            better = current - rng.uniform(0.1, 5.0)
            worse = current + rng.uniform(0.1, 5.0)

        pos = _open_pos(direction=direction, entry=entry, stop=current)
        assert protect_stop_worsens_exposure(direction, current, worse) is True
        assert protect_stop_worsens_exposure(direction, current, better) is False

        denied = apply_position_current_stop(pos, worse)
        assert denied is None

        applied = apply_position_current_stop(pos, better)
        assert applied is not None
        assert applied.current_stop is not None
        assert adverse_exposure(direction, entry, applied.current_stop) <= (
            adverse_exposure(direction, entry, current) + 1e-9
        )
