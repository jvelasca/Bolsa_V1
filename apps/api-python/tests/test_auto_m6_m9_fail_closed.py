"""M6/M9 — el journal de posición reencola si el sink falla; price_script que lanza = sin precio."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker


def _worker(**kw) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=lambda: datetime(2026, 9, 15, 9, 0, tzinfo=UTC), account_id="acc-m", **kw
    )


def test_price_script_exception_is_no_price() -> None:
    def boom(_symbol, _tick):
        raise RuntimeError("feed down")

    w = _worker(price_script=boom)
    assert w._v2_price_exec("AAA", 0) is None
    assert w._v2_price_mid("AAA", 0) is None


@pytest.mark.asyncio
async def test_failed_position_journal_is_requeued_then_published() -> None:
    calls: list[object] = []
    state = {"fail": True}

    async def sink(entry):
        if state["fail"]:
            raise RuntimeError("sink down")
        calls.append(entry)

    w = _worker(operational_audit_sink=sink)
    w._v2_seal_audit_identity = lambda e: e  # type: ignore[method-assign]
    w._v2_position_journal_pending = ["e1", "e2"]
    await w._v2_flush_position_journal()
    assert w._v2_position_journal_pending == ["e1", "e2"]
    state["fail"] = False
    await w._v2_flush_position_journal()
    assert calls == ["e1", "e2"]
    assert w._v2_position_journal_pending == []
