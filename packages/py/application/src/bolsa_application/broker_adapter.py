"""IBrokerAdapter — puerto Paper | Live (ADR-034 / XL-1 / XL-2).

PaperBrokerAdapter envuelve PaperBroker. MockBrokerAdapter = LIVE not_wired.
XtbBrokerAdapter = LIVE vía bridge; submitted ≠ fill; filled→ledger (XL-2).
≠ thaw PAPER_D_EXECUTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from bolsa_analytics.cognitive.broker_adapter import (
    BROKER_ADAPTER_MOCK,
    BROKER_ADAPTER_PAPER,
    BROKER_ADAPTER_XTB,
    BrokerAdapterFillStatus,
    BrokerAdapterName,
    BrokerAdapterReceipt,
    BrokerAdapterVenue,
    build_broker_adapter_receipt,
)
from bolsa_analytics.cognitive.paper_broker import PaperBrokerReceipt
from bolsa_analytics.cognitive.paper_order import PaperOrder, PaperOrderSide
from bolsa_application.paper_broker import PaperBroker
from bolsa_application.persist_position_from_fill import open_transaction_id_from_trade
from bolsa_market.providers import XtbBridgeClient, XtbBridgeOrderResult

BrokerAdapterSubmitStatus = Literal[
    "executed",
    "unknown",
    "not_wired",
    "rejected",
    "submitted",
]


@dataclass(frozen=True, slots=True)
class BrokerAdapterSubmitResult:
    """Resultado del puerto: paper fill, mock, o XTB (submitted ≠ fill; filled→ledger)."""

    venue: BrokerAdapterVenue
    adapter: BrokerAdapterName
    fill_status: BrokerAdapterFillStatus
    paper_order: PaperOrder | None
    paper_receipt: PaperBrokerReceipt | None
    trade: Any | None
    status: BrokerAdapterSubmitStatus
    reason: str | None
    transaction_id: str | None
    venue_order_id: str | None = None

    def receipt(self) -> BrokerAdapterReceipt:
        return build_broker_adapter_receipt(
            venue=self.venue,
            adapter=self.adapter,
            fill_status=self.fill_status,
        )


class IBrokerAdapter(Protocol):
    """Puerto EXECUTION: Paper | Live (mock o XTB bridge)."""

    async def submit(
        self,
        *,
        instrument_id: str,
        side: PaperOrderSide,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> BrokerAdapterSubmitResult: ...


class PaperBrokerAdapter:
    """Implementación PAPER del puerto. Delega en PaperBroker."""

    def __init__(self, execute_trade: Any) -> None:
        self._paper = PaperBroker(execute_trade)

    async def submit(
        self,
        *,
        instrument_id: str,
        side: PaperOrderSide,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> BrokerAdapterSubmitResult:
        pb = await self._paper.submit(
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=price,
            account_id=account_id,
            idempotency_key=idempotency_key,
            order_id=order_id,
            intent_id=intent_id,
        )
        return BrokerAdapterSubmitResult(
            venue="PAPER",
            adapter=BROKER_ADAPTER_PAPER,
            fill_status=pb.status,
            paper_order=pb.paper_order,
            paper_receipt=pb.receipt(),
            trade=pb.trade,
            status=pb.status,
            reason=pb.reason,
            transaction_id=pb.transaction_id,
        )


class MockBrokerAdapter:
    """LIVE-shaped mock. Nunca envía. fillStatus=not_wired."""

    async def submit(
        self,
        *,
        instrument_id: str,
        side: PaperOrderSide,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> BrokerAdapterSubmitResult:
        _ = (
            instrument_id,
            side,
            quantity,
            price,
            account_id,
            idempotency_key,
            order_id,
            intent_id,
        )
        return BrokerAdapterSubmitResult(
            venue="LIVE",
            adapter=BROKER_ADAPTER_MOCK,
            fill_status="not_wired",
            paper_order=None,
            paper_receipt=None,
            trade=None,
            status="not_wired",
            reason="live_not_wired",
            transaction_id=None,
        )


class _XtbOrderClient(Protocol):
    async def submit_order(
        self,
        *,
        instrument_id: str,
        side: str,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> XtbBridgeOrderResult: ...


class XtbBrokerAdapter:
    """LIVE vía bridge XTB. submitted ≠ fill; filled→ledger (XL-2)."""

    def __init__(
        self,
        *,
        bridge_url: str | None = None,
        client: _XtbOrderClient | None = None,
        execute_trade: Any | None = None,
    ) -> None:
        if client is not None:
            self._client: _XtbOrderClient | None = client
        elif bridge_url and bridge_url.strip():
            self._client = XtbBridgeClient(bridge_url.strip())
        else:
            self._client = None
        self._execute_trade = execute_trade

    async def submit(
        self,
        *,
        instrument_id: str,
        side: PaperOrderSide,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> BrokerAdapterSubmitResult:
        if self._client is None:
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="not_wired",
                paper_order=None,
                paper_receipt=None,
                trade=None,
                status="not_wired",
                reason="xtb_bridge_not_configured",
                transaction_id=None,
            )
        try:
            order = await self._client.submit_order(
                instrument_id=instrument_id,
                side=side,
                quantity=quantity,
                price=price,
                account_id=account_id,
                idempotency_key=idempotency_key,
                order_id=order_id,
                intent_id=intent_id,
            )
        except Exception as exc:  # noqa: BLE001 — honesty: unknown, no ledger
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="unknown",
                paper_order=None,
                paper_receipt=None,
                trade=None,
                status="unknown",
                reason=str(exc) or "xtb_bridge_error",
                transaction_id=None,
            )
        if order.status == "submitted":
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="submitted",
                paper_order=None,
                paper_receipt=None,
                trade=None,
                status="submitted",
                reason="live_submitted_no_fill",
                transaction_id=None,
                venue_order_id=order.venue_order_id,
            )
        if order.status == "filled":
            if self._execute_trade is None:
                return BrokerAdapterSubmitResult(
                    venue="LIVE",
                    adapter=BROKER_ADAPTER_XTB,
                    fill_status="unknown",
                    paper_order=None,
                    paper_receipt=None,
                    trade=None,
                    status="unknown",
                    reason="xtb_execute_not_wired",
                    transaction_id=None,
                    venue_order_id=order.venue_order_id,
                )
            try:
                trade = await self._execute_trade.execute(
                    instrument_id=instrument_id,
                    trade_type=side,
                    quantity=quantity,
                    price=price,
                    account_id=account_id,
                    idempotency_key=idempotency_key,
                )
            except Exception as exc:  # noqa: BLE001 — OI-3: UNKNOWN ≠ ERROR
                return BrokerAdapterSubmitResult(
                    venue="LIVE",
                    adapter=BROKER_ADAPTER_XTB,
                    fill_status="unknown",
                    paper_order=None,
                    paper_receipt=None,
                    trade=None,
                    status="unknown",
                    reason=str(exc),
                    transaction_id=None,
                    venue_order_id=order.venue_order_id,
                )
            tx_id = open_transaction_id_from_trade(trade)
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="executed",
                paper_order=None,
                paper_receipt=None,
                trade=trade,
                status="executed",
                reason=None,
                transaction_id=tx_id,
                venue_order_id=order.venue_order_id,
            )
        return BrokerAdapterSubmitResult(
            venue="LIVE",
            adapter=BROKER_ADAPTER_XTB,
            fill_status="rejected",
            paper_order=None,
            paper_receipt=None,
            trade=None,
            status="rejected",
            reason=order.reason or "live_rejected",
            transaction_id=None,
            venue_order_id=order.venue_order_id,
        )


def resolve_broker_adapter(
    execute_trade: Any,
    *,
    venue: Literal["paper", "live"] | None = None,
    bridge_url: str | None = None,
) -> IBrokerAdapter:
    """VS-1 — elige PaperBrokerAdapter | XtbBrokerAdapter según venue efectivo.

    ``venue=None`` → ``effective_broker_venue()``. Live sin URL → XTB ``not_wired``.
    """
    from bolsa_application.broker_venue_runtime import (
        effective_broker_venue,
        normalize_broker_venue,
    )

    chosen = normalize_broker_venue(venue) if venue is not None else effective_broker_venue()
    if chosen == "live":
        url = bridge_url
        if url is None:
            from bolsa_infrastructure.config import get_settings

            url = get_settings().xtb_bridge_url
        return XtbBrokerAdapter(bridge_url=url, execute_trade=execute_trade)
    return PaperBrokerAdapter(execute_trade)
