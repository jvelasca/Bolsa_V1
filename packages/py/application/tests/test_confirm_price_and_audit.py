"""Confirm: revalidación de precio fail-closed (apertura Y cierre) y auditoría visible.

Hallazgos del bloque crítico de /mercado/operativa:
- El cierre (`reduce`/`exit_hint`) no revalidaba precio: se podía firmar una salida a un
  precio que ya no existía.
- Si no hay último cierre conocido, el precio NO está medido → `price_unmeasured`
  (fail-closed), nunca «sin desviación».
- El fallo al persistir la sesión de auditoría se reintenta una vez con el MISMO id y, si
  vuelve a fallar, se declara en `result["auditPersist"]` en vez de silenciarse.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from bolsa_application.confirm.identity import build_recommendation_from_raw
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent


class _NoCloseOhlcv:
    async def get_latest_close(self, instrument_id: str) -> float | None:
        return None


class _CloseOhlcv:
    def __init__(self, close: float) -> None:
        self._close = close

    async def get_latest_close(self, instrument_id: str) -> float | None:
        return self._close


def _rec(
    *,
    action: str,
    price: float,
) -> Any:
    return build_recommendation_from_raw(
        {
            "recommendationId": "rec-price",
            "decisionId": "dec-price",
            "instrumentId": "inst-1",
            "symbol": "AAPL",
            "action": action,
            "suggestedPrice": price,
            "suggestedQuantity": 10,
        },
        account_id="acc-1",
    )


def _intent(side: str) -> Any:
    return SimpleNamespace(
        side=side,
        instrument_id="inst-1",
        to_dict=lambda: {"side": side, "instrumentId": "inst-1"},
    )


async def _run_trade_path(
    *,
    action: str,
    price: float,
    side: str,
    side_package: dict[str, Any] | None,
    ohlcv: Any,
) -> dict[str, Any]:
    coordinator = ConfirmRecommendationIntent(ohlcv=ohlcv)
    result: dict[str, Any] = {"intent": {}, "trade": None}
    await coordinator._run_trade_path(  # noqa: SLF001 — contrato interno bajo test
        result=result,
        rec=_rec(action=action, price=price),
        intent=_intent(side),
        account_id="acc-1",
        session_id=None,
        contract_status="absent",
        package=None,
        side_package=side_package,
        trade_plan_dict=None,
        session_payload=None,
        risk_override_reason=None,
    )
    return result


@pytest.mark.asyncio
async def test_close_without_known_close_is_rejected_price_unmeasured() -> None:
    result = await _run_trade_path(
        action="reduce",
        price=101.0,
        side="sell",
        side_package={"action": "recommend_long", "instrumentId": "inst-1"},
        ohlcv=_NoCloseOhlcv(),
    )

    assert result["trade"] == {
        "status": "rejected_by_gate",
        "reason": "price_unmeasured",
    }


@pytest.mark.asyncio
async def test_open_without_known_close_is_rejected_price_unmeasured() -> None:
    result = await _run_trade_path(
        action="recommend_long",
        price=101.0,
        side="buy",
        side_package=None,
        ohlcv=_NoCloseOhlcv(),
    )

    assert result["trade"] == {
        "status": "rejected_by_gate",
        "reason": "price_unmeasured",
    }


@pytest.mark.asyncio
async def test_close_with_stale_price_is_rejected_too() -> None:
    result = await _run_trade_path(
        action="reduce",
        price=110.0,
        side="sell",
        side_package={"action": "recommend_long", "instrumentId": "inst-1"},
        ohlcv=_CloseOhlcv(100.0),
    )

    assert result["trade"] == {
        "status": "rejected_by_gate",
        "reason": "stale_price",
    }


class _AlwaysFailStore:
    def __init__(self) -> None:
        self.appends: list[Any] = []
        self.updates: list[Any] = []

    async def get_decision_session(self, session_id: str) -> None:
        return None

    async def append_decision_session(self, record: Any) -> None:
        self.appends.append(record)
        raise RuntimeError("db down")

    async def update_decision_session(self, record: Any) -> None:
        self.updates.append(record)
        raise RuntimeError("db down")


class _FlakyStore(_AlwaysFailStore):
    def __init__(self, failures: int = 1) -> None:
        super().__init__()
        self._failures = failures

    async def append_decision_session(self, record: Any) -> None:
        self.appends.append(record)
        if len(self.appends) <= self._failures:
            raise RuntimeError("network blip")


@pytest.mark.asyncio
async def test_session_write_retries_once_with_the_same_id() -> None:
    store = _FlakyStore(failures=1)
    coordinator = ConfirmRecommendationIntent(cognitive_store=store)
    rec = _rec(action="recommend_long", price=100.0)

    payload = await coordinator._audit.persist(  # noqa: SLF001
        session_id=None,
        rec=rec,
        account_id="acc-1",
        execution={"trade": {"status": "skipped"}},
    )

    assert len(store.appends) == 2
    first_id, second_id = (record.id for record in store.appends)
    assert first_id == second_id
    assert payload["kind"] == "confirm"


@pytest.mark.asyncio
async def test_persist_failure_is_declared_in_audit_persist() -> None:
    store = _AlwaysFailStore()
    coordinator = ConfirmRecommendationIntent(cognitive_store=store)
    raw = {
        "recommendationId": "rec-audit",
        "decisionId": f"dec-{uuid4().hex[:8]}",
        "instrumentId": "inst-1",
        "symbol": "AAPL",
        "action": "wait",
        "suggestedPrice": 100.0,
        "suggestedQuantity": 10,
    }

    result = await coordinator.execute(
        recommendation_raw=raw,
        account_id="acc-1",
        execute=False,
    )

    assert len(store.appends) == 2  # un reintento, mismo id
    assert result["decisionSession"] is None
    assert result["auditPersist"]["status"] == "error"
    assert "db down" in result["auditPersist"]["reason"]


@pytest.mark.asyncio
async def test_successful_persist_reports_audit_ok() -> None:
    class _OkStore(_AlwaysFailStore):
        async def append_decision_session(self, record: Any) -> None:
            self.appends.append(record)

    store = _OkStore()
    coordinator = ConfirmRecommendationIntent(cognitive_store=store)
    raw = {
        "recommendationId": "rec-audit-ok",
        "decisionId": f"dec-{uuid4().hex[:8]}",
        "instrumentId": "inst-1",
        "symbol": "AAPL",
        "action": "wait",
        "suggestedPrice": 100.0,
        "suggestedQuantity": 10,
    }

    result = await coordinator.execute(
        recommendation_raw=raw,
        account_id="acc-1",
        execute=False,
    )

    assert len(store.appends) == 1
    assert result["auditPersist"] == {"status": "ok"}
    assert result["decisionSession"] is not None
