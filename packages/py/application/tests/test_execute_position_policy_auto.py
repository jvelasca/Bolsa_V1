"""V1.45 — ExecutePositionPolicyAuto + GP-AUTO-01 E2E PAPER (pytest)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.operating_policy import resolve_operating_policy
from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    ExecutePositionPolicyAutoInput,
    PaperPositionSellResult,
)
from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect


def _plan() -> dict[str, object]:
    return {
        "decisionId": "dec-v145",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open_row(*, qty: float = 10.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-08-31T15:00:00Z",
        position_id="pos-v145",
    )
    assert pos is not None
    return {
        "id": "pos-v145",
        "account_id": "acc-1",
        "instrument_id": "MSFT",
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _Store:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.updates: list[dict[str, Any]] = []

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        _ = account_id, instrument_id
        if self.row is None:
            return None
        if self.row.get("status") == "CLOSED":
            return None
        return self.row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        self.updates.append({"status": status, "position_state": position_state})
        self.row = {
            **(self.row or {}),
            "id": position_id,
            "status": status,
            "position_state": position_state,
        }
        return self.row

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        blob = (self.row or {}).get("position_state") if self.row else None
        current = None
        if isinstance(blob, dict):
            try:
                current = float(blob.get("currentStop"))
            except (TypeError, ValueError):
                current = None
        if current is None or abs(current - float(expected_stop)) > 1e-9:
            return None
        return await self.update_state(
            position_id=position_id, status=status, position_state=position_state
        )


class _FakeSell:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def sell(
        self,
        *,
        account_id: str,
        instrument_id: str,
        quantity: float,
        price: float,
        full_exit: bool,
        **kwargs: Any,
    ) -> PaperPositionSellResult:
        self.calls.append(
            {
                "account_id": account_id,
                "instrument_id": instrument_id,
                "quantity": quantity,
                "price": price,
                "full_exit": full_exit,
                "idempotency_key": kwargs.get("idempotency_key"),
            }
        )
        return PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=quantity,
            fill_price=price,
            transaction_id=f"tx-{uuid4().hex[:8]}",
        )


def _uc(store: _Store, sell: _FakeSell | None = None) -> ExecutePositionPolicyAuto:
    return ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell or _FakeSell(),
    )


@pytest.mark.asyncio
async def test_env_off_denies_paper_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    assert paper_d_execute_allowed() is False
    store = _Store(_open_row())
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    result = await _uc(store).execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=False,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
        )
    )
    assert result.status == "denied"
    assert result.permission is not None
    assert "paper_auto_env_blocked" in result.permission.reasons
    assert len(store.updates) == 0


@pytest.mark.asyncio
async def test_market_closed_t1_held() -> None:
    store = _Store(_open_row())
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    result = await _uc(store).execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=True,
            portfolio_drift=False,
            session="closed",
        )
    )
    assert result.status == "held"
    assert result.decision is not None
    assert result.decision.defer_reason == "queue_next_session"


@pytest.mark.asyncio
async def test_protective_stop_allows_despite_stale() -> None:
    store = _Store(_open_row())
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    # Mark through stop
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=94.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    assert exit_plan.primary_reason == "STRUCTURAL_STOP"
    sell = _FakeSell()
    result = await _uc(store, sell).execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=94.0,
            paper_d_execute=True,
            data_stale=True,
            market_closed=False,
            portfolio_drift=False,
            immediate_risk=True,
            stop_touched=True,
            stale=True,
            session="open",
        )
    )
    assert result.status in ("exited", "reduced", "sell_skipped")
    assert result.decision is not None
    assert result.decision.verdict == "EXIT"


@pytest.mark.asyncio
async def test_stale_t1_held_or_denied() -> None:
    store = _Store(_open_row())
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    result = await _uc(store).execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=True,
            data_stale=True,
            market_closed=False,
            portfolio_drift=False,
            stale=True,
            session="open",
        )
    )
    # Policy HOLD data_stale before permission when stale + not immediate.
    assert result.status == "held"
    assert result.decision is not None
    assert result.decision.defer_reason == "data_stale"


@pytest.mark.asyncio
async def test_gp_auto_01_e2e_paper_moderate() -> None:
    """GP-AUTO-01: T1 reduce → TRAIL protect → T2 reduce → close remainder → CLOSED."""
    store = _Store(_open_row(qty=10.0))
    sell = _FakeSell()
    uc = _uc(store, sell)
    policy = resolve_operating_policy("moderate")

    # --- T1 @ 110 ---
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    t1_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit, at="2026-08-31T16:00:00Z"
    )
    assert t1_plan is not None
    t1 = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=t1_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T16:00:00Z",
        )
    )
    assert t1.status == "reduced"
    assert t1.decision is not None and t1.decision.verdict == "REDUCE"
    assert sell.calls[0]["quantity"] == pytest.approx(3.0)
    assert sell.calls[0]["full_exit"] is False
    after_t1 = position_state_from_dict(store.row["position_state"])
    assert after_t1 is not None
    assert after_t1.remaining_quantity == pytest.approx(7.0)

    # --- TRAIL ---
    trail_plan = build_exit_plan_from_position(
        after_t1, trail_hint=True, trail_stop=102.0, at="2026-08-31T16:05:00Z"
    )
    assert trail_plan is not None
    trail = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=after_t1,
            exit_plan=trail_plan,
            operating_policy=policy,
            mark_price=112.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T16:05:00Z",
        )
    )
    assert trail.status == "protected"
    assert trail.decision is not None and trail.decision.verdict == "TRAIL"
    after_trail = position_state_from_dict(store.row["position_state"])
    assert after_trail is not None
    assert after_trail.current_stop == pytest.approx(102.0)
    revs = revisions_from_raw(after_trail.to_dict().get("revisions"))
    assert any(r.origin == "trail" for r in revs)

    # --- T2 reduce 30% of remaining ---
    t2_plan = build_exit_plan_from_position(
        after_trail, mark_price=120.0, exit_policy=policy.exit, at="2026-08-31T16:10:00Z"
    )
    assert t2_plan is not None
    t2 = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=after_trail,
            exit_plan=t2_plan,
            operating_policy=policy,
            mark_price=120.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T16:10:00Z",
        )
    )
    assert t2.status == "reduced"
    assert t2.decision is not None and t2.decision.verdict == "REDUCE"
    assert sell.calls[-1]["quantity"] == pytest.approx(2.1)
    after_t2 = position_state_from_dict(store.row["position_state"])
    assert after_t2 is not None
    rem = float(after_t2.remaining_quantity)
    assert rem == pytest.approx(4.9)

    # --- close remainder (spec: close remainder → CLOSED) ---
    sold = await sell.sell(
        account_id="acc-1",
        instrument_id="MSFT",
        quantity=rem,
        price=120.0,
        full_exit=True,
    )
    assert sold.status == "trade_executed"
    from bolsa_application.persist_position_from_exit import PersistPositionFromExitInput

    await PersistPositionFromExit(store).persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="MSFT",
            fill_quantity=rem,
            fill_price=120.0,
            exit_transaction_id=sold.transaction_id or "tx-close",
            filled_at="2026-08-31T16:15:00Z",
            mark_target2_achieved=True,
        )
    )

    assert store.row is not None
    assert store.row["status"] == "CLOSED"
    assert len(sell.calls) >= 3


@pytest.mark.asyncio
async def test_reduce_without_qty_errors_not_full_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REDUCE sin cantidad no vende remaining (no escala a EXIT)."""
    from bolsa_analytics.cognitive.position_event import build_position_event
    from bolsa_analytics.cognitive.position_policy_decision import PositionPolicyDecision

    store = _Store(_open_row(qty=10.0))
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    fake = PositionPolicyDecision(
        verdict="REDUCE",
        reason_code="TARGET_1",
        event=build_position_event("TARGET_1", "2026-08-31T16:00:00Z"),
        quantity=None,
        new_stop=None,
        target=110.0,
        risk_impact="reduce",
        policy_id="moderate",
        as_of="2026-08-31T16:00:00Z",
        authorization="policy",
        defer_reason=None,
    )
    monkeypatch.setattr(
        "bolsa_application.execute_position_policy_auto.decide_position_policy",
        lambda *_a, **_k: fake,
    )
    sell = _FakeSell()
    result = await _uc(store, sell).execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T16:00:00Z",
        )
    )
    assert result.status == "error"
    assert result.reason == "missing_reduce_quantity"
    assert sell.calls == []
    after = position_state_from_dict(store.row["position_state"])
    assert after is not None
    assert after.remaining_quantity == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_exit_without_qty_uses_remaining(monkeypatch: pytest.MonkeyPatch) -> None:
    """EXIT sin qty explícita sí puede vender remaining."""
    from bolsa_analytics.cognitive.position_event import build_position_event
    from bolsa_analytics.cognitive.position_policy_decision import PositionPolicyDecision

    store = _Store(_open_row(qty=10.0))
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=94.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    fake = PositionPolicyDecision(
        verdict="EXIT",
        reason_code="STRUCTURAL_STOP",
        event=build_position_event("STRUCTURAL_STOP", "2026-08-31T16:20:00Z"),
        quantity=None,
        new_stop=None,
        target=None,
        risk_impact="exit",
        policy_id="moderate",
        as_of="2026-08-31T16:20:00Z",
        authorization="policy",
        defer_reason=None,
    )
    monkeypatch.setattr(
        "bolsa_application.execute_position_policy_auto.decide_position_policy",
        lambda *_a, **_k: fake,
    )
    sell = _FakeSell()
    result = await _uc(store, sell).execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=94.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            immediate_risk=True,
            stop_touched=True,
            session="open",
            as_of="2026-08-31T16:20:00Z",
        )
    )
    assert result.status in ("exited", "reduced")
    assert sell.calls[0]["quantity"] == pytest.approx(10.0)
    assert sell.calls[0]["full_exit"] is True


@pytest.mark.asyncio
async def test_event_claim_failed_does_not_fallback_to_position_id() -> None:
    """Claim None → error; nunca vender con idempotency_key = position_id."""

    class _NoClaim(PersistPositionFromProtect):
        async def claim_sell_event(
            self,
            *,
            account_id: str,
            instrument_id: str,
            event_type: str,
            action: str,
            as_of: str | None,
            quantity: float | None = None,
        ) -> None:
            _ = account_id, instrument_id, event_type, action, as_of, quantity
            return None

    store = _Store(_open_row(qty=10.0))
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    sell = _FakeSell()
    uc = ExecutePositionPolicyAuto(
        protect=_NoClaim(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell,
    )
    result = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T16:00:00Z",
        )
    )
    assert result.status == "error"
    assert result.reason == "event_claim_failed"
    assert sell.calls == []
    after = position_state_from_dict(store.row["position_state"])
    assert after is not None
    assert after.remaining_quantity == pytest.approx(10.0)
