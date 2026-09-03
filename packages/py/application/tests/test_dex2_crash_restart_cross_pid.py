"""DEX-2 — Crash/restart cross-PID: store/cliente fresco leyendo PG → UNKNOWN · 0 re-POST.

OR-2 usaba el mismo InMemory. Aquí proceso A escribe vía PostgresSubmitIntentStore;
proceso B = nueva sesión + nuevo store sobre el mismo backing durable (simula PID nuevo).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision
from bolsa_analytics.cognitive.submit_intent import (
    bind_venue_order,
    mark_send_attempted,
    record_submit_intent,
)
from bolsa_infrastructure.database.models.tables import SubmitIntentRow
from bolsa_market.providers import XtbBridgeOrderResult

from bolsa_application.broker_adapter import XtbBrokerAdapter
from bolsa_application.confirm_recommendation import (
    ConfirmRecommendationIntent,
    confirm_leg_idempotency_key,
)
from bolsa_application.submit_intent_store import PostgresSubmitIntentStore


def _decision_id_from_stmt(stmt: Any) -> str:
    for crit in getattr(stmt, "_where_criteria", ()) or ():
        right = getattr(crit, "right", None)
        value = getattr(right, "value", None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise AssertionError("DEX-2 fake session: no decision_id in select")


class _SharedPgTable:
    """Backing durable compartido entre sesiones (simula filas PG commitadas)."""

    def __init__(self) -> None:
        self.by_decision: dict[str, SubmitIntentRow] = {}


class _FakeResult:
    def __init__(self, row: SubmitIntentRow | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> SubmitIntentRow | None:
        return self._row


class _FakePgSession:
    """Sesión mínima: select/add/commit/delete contra tabla compartida."""

    def __init__(self, table: _SharedPgTable) -> None:
        self._table = table
        self._pending_add: list[SubmitIntentRow] = []
        self._pending_delete: list[str] = []
        self.commit = AsyncMock(side_effect=self._commit)
        self.rollback = AsyncMock(side_effect=self._rollback)

    async def execute(self, stmt: Any) -> _FakeResult:
        key = _decision_id_from_stmt(stmt)
        # Misma identidad que identity-map SQLAlchemy: mutaciones in-place
        # de put() sobre fila existente quedan en el backing al commit.
        return _FakeResult(self._table.by_decision.get(key))

    def add(self, row: SubmitIntentRow) -> None:
        self._pending_add.append(row)

    async def delete(self, row: SubmitIntentRow) -> None:
        self._pending_delete.append(row.decision_id)

    async def _commit(self) -> None:
        for row in self._pending_add:
            self._table.by_decision[row.decision_id] = row
        for key in self._pending_delete:
            self._table.by_decision.pop(key, None)
        self._pending_add.clear()
        self._pending_delete.clear()

    async def _rollback(self) -> None:
        self._pending_add.clear()
        self._pending_delete.clear()


def _fresh_store(table: _SharedPgTable) -> PostgresSubmitIntentStore:
    """Proceso B: nueva sesión + nuevo store (no reutiliza el de A)."""
    return PostgresSubmitIntentStore(_FakePgSession(table))


class _CountingAdapter:
    def __init__(self) -> None:
        self.submit_calls = 0

    async def submit(self, **kwargs: Any) -> Any:
        self.submit_calls += 1
        raise AssertionError("adapter.submit must not run on DEX-2 recovery")


class _FakeXtb:
    def __init__(self, result: XtbBridgeOrderResult) -> None:
        self.result = result
        self.calls = 0

    async def submit_order(self, **kwargs: Any) -> XtbBridgeOrderResult:
        _ = kwargs
        self.calls += 1
        return self.result


def _raw(*, decision_id: str) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 10.0,
        "suggestedPrice": 100.0,
        "tradePlan": {
            "decisionId": decision_id,
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
            "riskAmount": 50.0,
        },
    }


@pytest.mark.asyncio
async def test_dex2_postgres_store_survives_new_session_instance() -> None:
    """Proceso A put → kill sesión → proceso B get (store distinto, mismo PG)."""
    table = _SharedPgTable()
    store_a = _fresh_store(table)
    decision_id = "DEC-DEX2-PG"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    intent = mark_send_attempted(
        record_submit_intent(
            decision_id=leg_key,
            intent_id=stable_intent_id_from_decision(leg_key),
            order_id=stable_order_id_from_decision(leg_key),
            account_id="acc-1",
            venue="live",
        )
    )
    await store_a.put(intent)
    store_a_id = id(store_a)
    del store_a  # kill proceso A

    store_b = _fresh_store(table)
    assert id(store_b) != store_a_id
    got = await store_b.get(leg_key)
    assert got is not None
    assert got.phase == "send_attempted"
    assert got.decision_id == leg_key
    assert got.intent_id == stable_intent_id_from_decision(leg_key)
    assert got.order_id == stable_order_id_from_decision(leg_key)
    assert got.send_attempted_at is not None


@pytest.mark.asyncio
async def test_dex2_fresh_client_reconstructs_unknown_without_submit() -> None:
    """Crash post-recorded en A → Confirm con store B → UNKNOWN · 0 submit."""
    table = _SharedPgTable()
    store_a = _fresh_store(table)
    decision_id = "DEC-DEX2-CRASH"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    recorded = record_submit_intent(
        decision_id=leg_key,
        intent_id=stable_intent_id_from_decision(leg_key),
        order_id=stable_order_id_from_decision(leg_key),
        account_id="acc-1",
    )
    await store_a.put(recorded)
    del store_a

    adapter = _CountingAdapter()
    store_b = _fresh_store(table)
    uc = ConfirmRecommendationIntent(
        broker_adapter=adapter,  # type: ignore[arg-type]
        submit_intent_store=store_b,
    )
    result = await uc.execute(
        recommendation_raw=_raw(decision_id=decision_id),
        account_id="acc-1",
        execute=True,
    )
    assert adapter.submit_calls == 0
    assert result["trade"]["status"] == "unknown"
    assert result["trade"]["crashRecovery"] is True
    assert result["trade"]["reason"] == "crash_before_venue_ack"
    assert result["intent"]["intentId"] == stable_intent_id_from_decision(decision_id)
    assert result["submitIntent"]["orderId"] == stable_order_id_from_decision(leg_key)
    assert result["paperOrder"]["status"] == "UNKNOWN"
    assert result["paperOrder"]["orderId"] == stable_order_id_from_decision(leg_key)


@pytest.mark.asyncio
async def test_dex2_fresh_client_preserves_venue_mapping_without_repost() -> None:
    """Crash post-venue_bound en A → B recupera mapeo · 0 re-POST."""
    table = _SharedPgTable()
    store_a = _fresh_store(table)
    decision_id = "DEC-DEX2-VENUE"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    recorded = record_submit_intent(
        decision_id=leg_key,
        intent_id=stable_intent_id_from_decision(leg_key),
        order_id=stable_order_id_from_decision(leg_key),
        account_id="acc-1",
    )
    await store_a.put(bind_venue_order(recorded, venue_order_id="xtb-dex2-1"))
    del store_a

    adapter = _CountingAdapter()
    store_b = _fresh_store(table)
    uc = ConfirmRecommendationIntent(
        broker_adapter=adapter,  # type: ignore[arg-type]
        submit_intent_store=store_b,
    )
    result = await uc.execute(
        recommendation_raw=_raw(decision_id=decision_id),
        account_id="acc-1",
        execute=True,
    )
    assert adapter.submit_calls == 0
    assert result["trade"]["status"] == "unknown"
    assert result["trade"]["venueOrderId"] == "xtb-dex2-1"
    assert result["trade"]["crashRecovery"] is True
    assert result["submitIntent"]["phase"] == "venue_bound"
    assert result["submitIntent"]["venueOrderId"] == "xtb-dex2-1"


@pytest.mark.asyncio
async def test_dex2_live_submit_then_fresh_client_no_second_post() -> None:
    """Proceso A: 1 submit + bind. Kill. Proceso B: Confirm · 0 re-POST."""
    table = _SharedPgTable()
    store_a = _fresh_store(table)
    xtb = _FakeXtb(XtbBridgeOrderResult(status="submitted", venue_order_id="xtb-dex2-live"))
    adapter = XtbBrokerAdapter(client=xtb)
    uc_a = ConfirmRecommendationIntent(
        broker_adapter=adapter,
        submit_intent_store=store_a,
    )
    decision_id = "DEC-DEX2-LIVE"
    raw = _raw(decision_id=decision_id)
    first = await uc_a.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert xtb.calls == 1
    assert first["trade"]["venueOrderId"] == "xtb-dex2-live"
    del store_a
    del uc_a

    adapter_b = _CountingAdapter()
    store_b = _fresh_store(table)
    uc_b = ConfirmRecommendationIntent(
        broker_adapter=adapter_b,  # type: ignore[arg-type]
        submit_intent_store=store_b,
    )
    second = await uc_b.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert adapter_b.submit_calls == 0
    assert xtb.calls == 1  # no segundo POST al venue
    assert second["trade"]["status"] == "unknown"
    assert second["trade"]["venueOrderId"] == "xtb-dex2-live"
    assert second["trade"]["crashRecovery"] is True
    assert second["submitIntent"]["phase"] == "venue_bound"


@pytest.mark.asyncio
async def test_dex2_put_update_visible_to_fresh_store() -> None:
    """Updates (send_attempted) commitados en A son visibles en B."""
    table = _SharedPgTable()
    store_a = _fresh_store(table)
    decision_id = "DEC-DEX2-PHASE"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    base = record_submit_intent(
        decision_id=leg_key,
        intent_id=stable_intent_id_from_decision(leg_key),
        order_id=stable_order_id_from_decision(leg_key),
        account_id="acc-1",
    )
    await store_a.put(base)
    await store_a.put(mark_send_attempted(base))
    del store_a

    store_b = _fresh_store(table)
    got = await store_b.get(leg_key)
    assert got is not None
    assert got.phase == "send_attempted"
    assert got.send_attempted_at is not None
