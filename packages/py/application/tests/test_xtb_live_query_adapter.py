"""XtbLiveOrderQueryAdapter — implementación real de ``LiveOrderQueryPort`` (H6).

Verifica el mapeo XtbBridgeOrderState → BrokerOrderQueryResult (life-cycle del
venu) y el fail-closed a ``unavailable`` ante error/timeout/404 del cliente, sin
fabricar cierre terminal.
"""

from __future__ import annotations

import pytest

from bolsa_application.broker_adapter import XtbLiveOrderQueryAdapter
from bolsa_application.live_order_query import BrokerOrderQueryResult
from bolsa_market.providers import XtbBridgeOrderState


class _FakeOrderClient:
    """Duck-type del cliente XTB: dado state controlable lanza bajo demanda."""

    def __init__(self, state: XtbBridgeOrderState | None = None) -> None:
        self.state = state
        self.calls = 0
        self.last_vid: str | None = None

    async def query_order(self, venue_order_id: str) -> XtbBridgeOrderState:
        self.calls += 1
        self.last_vid = venue_order_id
        if self.state is None:
            raise RuntimeError("xtb bridge timeout hit")  # simulando error de red
        return self.state


def _state(
    *,
    state: str,
    vid: str = "xtb-1",
    filled: float = 0.0,
    remaining: float = 100.0,
    reason: str | None = None,
) -> XtbBridgeOrderState:
    return XtbBridgeOrderState(
        venue_order_id=vid,
        state=state,  # type: ignore[arg-type]  # value del mock/bridge real
        filled_quantity=filled,
        remaining_quantity=remaining,
        reason=reason,
    )


@pytest.mark.asyncio
async def test_filled_maps_to_broker_filled() -> None:
    client = _FakeOrderClient(_state(state="filled", vid="xtb-f", filled=100.0, remaining=0.0))
    adapter = XtbLiveOrderQueryAdapter(client)  # type: ignore[arg-type]
    result = await adapter.query_broker_order(venue_order_id="xtb-f")
    assert isinstance(result, BrokerOrderQueryResult)
    assert result.outcome == "filled"
    assert result.venue_order_id == "xtb-f"
    assert result.filled_quantity == 100.0
    assert result.remaining_quantity == 0.0
    assert result.to_live_status() == "FILLED"


@pytest.mark.asyncio
async def test_partial_maps_and_quantities_precise_6dp() -> None:
    client = _FakeOrderClient(
        _state(state="partial", vid="xtb-p", filled=50.25, remaining=49.75)
    )
    adapter = XtbLiveOrderQueryAdapter(client)  # type: ignore[arg-type]
    result = await adapter.query_broker_order(venue_order_id="xtb-p")
    assert result.outcome == "partial"
    # cuantizacion 6dp exacta (taponamos H1), sin residuo float
    assert result.filled_quantity == 50.25
    assert result.remaining_quantity == 49.75
    assert result.to_live_status() == "PARTIAL"


@pytest.mark.asyncio
async def test_working_and_cancelled_and_rejected_map_1to1() -> None:
    adapter_wo = XtbLiveOrderQueryAdapter(  # type: ignore[arg-type]
        _FakeOrderClient(_state(state="working", vid="xtb-w"))
    )
    assert (await adapter_wo.query_broker_order(venue_order_id="xtb-w")).outcome == "working"
    assert (
        await adapter_wo.query_broker_order(venue_order_id="xtb-w")
    ).to_live_status() == "WORKING"

    adapter_cx = XtbLiveOrderQueryAdapter(  # type: ignore[arg-type]
        _FakeOrderClient(_state(state="cancelled", vid="xtb-c"))
    )
    assert (await adapter_cx.query_broker_order(venue_order_id="xtb-c")).outcome == "cancelled"
    assert (
        await adapter_cx.query_broker_order(venue_order_id="xtb-c")
    ).to_live_status() == "CANCELLED"

    adapter_rj = XtbLiveOrderQueryAdapter(  # type: ignore[arg-type]
        _FakeOrderClient(_state(state="rejected", vid="xtb-r"))
    )
    assert (await adapter_rj.query_broker_order(venue_order_id="xtb-r")).outcome == "rejected"
    assert (
        await adapter_rj.query_broker_order(venue_order_id="xtb-r")
    ).to_live_status() == "REJECTED"


@pytest.mark.asyncio
async def test_client_error_maps_unavailable_not_terminal() -> None:
    adapter = XtbLiveOrderQueryAdapter(_FakeOrderClient(state=None))  # type: ignore[arg-type]
    result = await adapter.query_broker_order(venue_order_id="xtb-err")
    assert result.outcome == "unavailable"
    assert result.filled_quantity is None
    # ``to_live_status`` de unavailable → None → la máquina se queda UNKNOWN (no
    # se fabrica un estado terminal inventado).
    assert result.to_live_status() is None


@pytest.mark.asyncio
async def test_zero_and_negative_quantities_are_clamped() -> None:
    client = _FakeOrderClient(_state(state="partial", vid="xtb-z", filled=-5.0, remaining=-1.0))
    adapter = XtbLiveOrderQueryAdapter(client)  # type: ignore[arg-type]
    result = await adapter.query_broker_order(venue_order_id="xtb-z")
    assert result.filled_quantity == 0.0
    assert result.remaining_quantity == 0.0


@pytest.mark.asyncio
async def test_reason_forwarded_when_present() -> None:
    client = _FakeOrderClient(
        _state(state="rejected", vid="xtb-rr", reason="position_too_large")
    )
    adapter = XtbLiveOrderQueryAdapter(client)  # type: ignore[arg-type]
    result = await adapter.query_broker_order(venue_order_id="xtb-rr")
    assert result.reason == "position_too_large"
