"""ExecutionRouter persiste Decision Memory tras Gate (D7+)."""

from __future__ import annotations

from bolsa_analytics.cognitive import build_memory_entry
from bolsa_domain.entities.cognitive_artifacts import DecisionMemoryRecord

from bolsa_application.cognitive_persistence import memory_entry_to_record
from bolsa_application.trading_policy_guard import CognitiveGuardResult


class _FakeStore:
    def __init__(self) -> None:
        self.rows: list[DecisionMemoryRecord] = []

    async def append_decision_memory(self, record: DecisionMemoryRecord) -> DecisionMemoryRecord:
        self.rows.append(record)
        return record


async def _persist_via_router_helper():
    """Copia la lógica de _persist_gate_memory sin construir router completo."""
    from bolsa_application.execution_router import ExecutionRouter

    store = _FakeStore()
    # Minimal stub: solo necesitamos el método de instancia
    router = object.__new__(ExecutionRouter)
    router._cognitive_store = store  # type: ignore[attr-defined]

    mem = build_memory_entry(
        decision_id="DEC-x",
        instrument_id="inst-1",
        outcome="rejected",
        reasons=["PreEarningsBlackout"],
        policy_rule_ids=["PreEarningsBlackout"],
        reevaluate_when=["after_earnings_blackout_clears"],
    )
    guard = CognitiveGuardResult(
        allowed=False,
        reasons=mem.reasons,
        policy_id="pol",
        policy_version="1",
        memory_id=mem.memory_id,
        decision_id=mem.decision_id,
        gate=None,
        memory=mem,
    )
    await router._persist_gate_memory(guard, account_id="acc-1")  # type: ignore[attr-defined]
    assert len(store.rows) == 1
    assert store.rows[0].account_id == "acc-1"
    assert store.rows[0].outcome == "rejected"
    assert store.rows[0].id == mem.memory_id


def test_persist_gate_memory_writes_store():
    import asyncio

    asyncio.run(_persist_via_router_helper())


def test_memory_entry_to_record_keeps_reevaluate():
    mem = build_memory_entry(
        decision_id="DEC-y",
        instrument_id="MSFT",
        outcome="rejected",
        reasons=["x"],
        reevaluate_when=["after_macro_event_window"],
    )
    rec = memory_entry_to_record(mem, account_id="a1")
    assert rec.reevaluate_when == ("after_macro_event_window",)
