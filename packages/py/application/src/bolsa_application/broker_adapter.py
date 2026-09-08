"""IBrokerAdapter — puerto Paper | Live (ADR-034 / XL-1 / XL-2).

PaperBrokerAdapter envuelve PaperBroker. MockBrokerAdapter = LIVE not_wired.
XtbBrokerAdapter = LIVE vía bridge; submitted ≠ fill; filled→ledger (XL-2).
≠ thaw PAPER_D_EXECUTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
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
from bolsa_application.live_order_query import BrokerOrderQueryResult
from bolsa_application.paper_broker import PaperBroker
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
    """LIVE vía bridge XTB. submitted ≠ fill; filled→ledger (XL-2).

    VIRTUAL sandbox: sin ``LIVE_EXECUTION_UNLOCKED`` no hay POST al bridge.
    Kill switch se reconsulta aquí (además del OpeningGate).
    """

    def __init__(
        self,
        *,
        bridge_url: str | None = None,
        client: _XtbOrderClient | None = None,
        execute_trade: Any | None = None,
        kill_switch_check: Any | None = None,
        execution_unlocked_check: Any | None = None,
    ) -> None:
        if client is not None:
            self._client: _XtbOrderClient | None = client
        elif bridge_url and bridge_url.strip():
            self._client = XtbBridgeClient(bridge_url.strip())
        else:
            self._client = None
        self._execute_trade = execute_trade
        self._kill_switch_check = kill_switch_check
        self._execution_unlocked_check = execution_unlocked_check

    async def _kill_on(self) -> bool:
        check = self._kill_switch_check
        if check is None:
            from bolsa_application.risk_runtime import effective_kill_switch

            return bool(await effective_kill_switch())
        result = check()
        if hasattr(result, "__await__"):
            return bool(await result)
        return bool(result)

    def _unlocked(self) -> bool:
        check = self._execution_unlocked_check
        if check is None:
            from bolsa_application.live_execution_runtime import live_execution_unlocked

            return bool(live_execution_unlocked())
        return bool(check())

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
        if await self._kill_on():
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="rejected",
                paper_order=None,
                paper_receipt=None,
                trade=None,
                status="rejected",
                reason="kill_switch_active",
                transaction_id=None,
            )
        if not self._unlocked():
            # VIRTUAL sandbox: Confirm chrome OK, money path NO.
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="not_wired",
                paper_order=None,
                paper_receipt=None,
                trade=None,
                status="not_wired",
                reason="live_virtual_sandbox",
                transaction_id=None,
            )
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
            # V2.13 · Cierra el atajo síncrono old-XL2 (auditoría H4): un ``filled``
            # del bridge ya NO empuja a ledger vía ``execute_trade`` por detrás de
            # la máquina XL-3. Un XTB real es generado A-síncronamente (el bridge
            # ``filled`` síncrono solo se ve en el mock/test); el depósito financiero
            # de un LiveOrder debe pasar por la máquina XL-3 + query + apply
            # financiero (PARKED). Hasta que exista, este *se queda UNKNOWN durable*
            # (falta resolver el fill === función del query real, no del POST).
            # Fail-closed: jamás se fabrica un ledger ni un ``executed`` aquí.
            return BrokerAdapterSubmitResult(
                venue="LIVE",
                adapter=BROKER_ADAPTER_XTB,
                fill_status="unknown",
                paper_order=None,
                paper_receipt=None,
                trade=None,
                status="unknown",
                reason="live_sync_fill_blocked_requires_reconcile",
                transaction_id=None,
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


class XtbLiveOrderQueryAdapter:
    """Implementa ``LiveOrderQueryPort`` con el bridge XTB real (H6).

    Consulta ``GET /orders/{venue_order_id}`` (broker-truth del life-cycle de la
    orden) y mapea a ``BrokerOrderQueryResult``:
    * estados working/partial/filled/rejected/cancelled → outcome equivalente;
    * cantidades ``filled/remaining`` se cuantifican a ``Decimal(6dp)`` (paridad
      con la máquina XL-3, que es Decimal desde H1) ANTES de construir el result;
    * cualquier error/timeout/404 del bridge → resultado ``unavailable`` (fail-
      closed: la máquina permanece UNKNOWN; no se fabrica cierre terminal).

    No deposita ledger ni ejecuta nada: es lectura pura del contexto del venue.
    """

    def __init__(self, client: XtbBridgeClient) -> None:
        self._client = client

    @staticmethod
    def _qty(value: object | None) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            q = Decimal(str(value))
        except (ValueError, TypeError):
            return Decimal("0")
        if q.is_nan() or q < 0:
            return Decimal("0")
        return q

    async def query_broker_order(self, *, venue_order_id: str) -> BrokerOrderQueryResult:
        try:
            st = await self._client.query_order(venue_order_id)
        except Exception:
            return BrokerOrderQueryResult(
                outcome="unavailable",
                venue_order_id=venue_order_id,
                filled_quantity=None,
                remaining_quantity=None,
                reason="xtb_query_unavailable",
            )
        # ``BrokerOrderQueryResult`` mapeará el life-cycle del venue a estado de
        # la máquina vía ``to_live_status`` (working/partial/filled/rejected/
        # cancelled → WORKING/PARTIAL/FILLED/REJECTED/CANCELLED).
        # Decimal(6dp) exacto al construir el result: tapona el hueco H1 del float
        # en la cadena broker→máquina (working/partial/filled con quantities).
        def _dec(value: object | None) -> Decimal:
            return self._qty(value).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )

        return BrokerOrderQueryResult(
            outcome=st.state,
            venue_order_id=st.venue_order_id,
            filled_quantity=_dec(st.filled_quantity),
            remaining_quantity=_dec(st.remaining_quantity),
            reason=st.reason,
        )
