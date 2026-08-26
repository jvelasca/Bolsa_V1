"""Fill de pending_orders a través del Decision Spine (ADR-031) + OI-1 sync.

El monitor FE ya no llama ``ExecuteTrade`` directo. Las aperturas (side=buy)
re-ejecutan ``check_opening`` (mismo SoT SEMI/AUTO). Los sells no abren cesta
y no pasan el gate de apertura. Tras fill: sync PositionState (apertura/cierre).
OI-4 / BrokerAdapter / XL-1: submit vía puerto (default paper); fill OK adjunta
``paperOrder`` FILLED + ``paperBroker`` + ``brokerAdapter``. Mock LIVE →
``not_wired``. XTB rejected/submitted → no borra la pending. Gate/expire → no
receipts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.broker_adapter import IBrokerAdapter, resolve_broker_adapter
from bolsa_application.broker_venue_runtime import (
    account_broker_venue_from_settings,
    effective_broker_venue_async,
)
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.opening_permission import (
    AccountScopeLookup,
    InstrumentSectorLookup,
    LatestBarLookup,
    allow_opening_fill,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.post_fill_position_sync import sync_position_after_ledger_fill
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    PendingOrderRecord,
    SqlAlchemyPendingOrderRepository,
)


def _order_expired(order: PendingOrderRecord, *, now: datetime | None = None) -> bool:
    if not order.expiry_at:
        return False
    try:
        parsed = datetime.fromisoformat(order.expiry_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    moment = now if now is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    return parsed < moment


class FillPendingOrder:
    """Llena una pending order tras ``check_opening`` (aperturas) y borra la fila."""

    def __init__(
        self,
        repo: SqlAlchemyPendingOrderRepository,
        account_repo: SqlAlchemyAccountRepository,
        *,
        execute_trade: Any,
        portfolio_summary: GetPortfolioSummary | None = None,
        instruments: InstrumentSectorLookup | None = None,
        profile_store: InvestorProfileStore | None = None,
        accounts: AccountScopeLookup | None = None,
        ohlcv: LatestBarLookup | None = None,
        mandates: AccountMandateLookup | None = None,
        position_from_fill: PersistPositionFromFill | None = None,
        position_from_exit: PersistPositionFromExit | None = None,
        broker_adapter: IBrokerAdapter | None = None,
    ) -> None:
        self._repo = repo
        self._account_repo = account_repo
        self._execute_trade = execute_trade
        self._broker_adapter = broker_adapter
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit

    async def _resolve_broker_adapter_for_account(self, account_id: str) -> IBrokerAdapter:
        """PA-1: adapter inyectado (tests) o lazy resolve tras account_id."""
        if self._broker_adapter is not None:
            return self._broker_adapter
        account_venue: str | None = None
        getter = getattr(self._account_repo, "get_settings_json", None)
        if getter is not None:
            try:
                settings = await getter(account_id)
                account_venue = account_broker_venue_from_settings(settings)
            except Exception:  # noqa: BLE001 — preferencia opcional; fallback coalesce
                account_venue = None
        venue = await effective_broker_venue_async(account_venue=account_venue)
        return resolve_broker_adapter(self._execute_trade, venue=venue)

    async def execute(
        self,
        order_id: str,
        *,
        account_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        scope = await self._account_repo.resolve_scope(account_id)
        order = await self._repo.get_by_id(order_id, account_id=scope.account.id)
        if order is None:
            raise ValueError("Order not found")
        if _order_expired(order):
            await self._repo.delete(order.id, account_id=scope.account.id)
            return {"status": "expired", "reason": "expired", "transactionId": None}
        side = str(order.side).lower()
        if side == "buy" and self._portfolio_summary is not None:
            allowed = await self._risk_allows_opening(
                order=order,
                account_id=scope.account.id,
            )
            if not allowed:
                return {
                    "status": "rejected_by_gate",
                    "reason": "risk_veto",
                    "transactionId": None,
                }
        order_side: Literal["buy", "sell"] = "sell" if side == "sell" else "buy"
        adapter = await self._resolve_broker_adapter_for_account(scope.account.id)
        pb = await adapter.submit(
            instrument_id=order.instrument_id,
            side=order_side,
            quantity=float(order.quantity),
            price=float(order.limit_price),
            account_id=scope.account.id,
            idempotency_key=idempotency_key,
            order_id=order.id,
        )
        if pb.status == "not_wired":
            return {
                "status": "skipped",
                "reason": pb.reason or "live_not_wired",
                "transactionId": None,
                "brokerAdapter": pb.receipt().to_dict(),
            }
        if pb.status == "rejected":
            return {
                "status": "skipped",
                "reason": pb.reason or "live_rejected",
                "transactionId": None,
                "brokerAdapter": pb.receipt().to_dict(),
            }
        if pb.status == "submitted":
            submitted: dict[str, Any] = {
                "status": "unknown",
                "reason": pb.reason or "live_submitted_no_fill",
                "transactionId": None,
                "brokerAdapter": pb.receipt().to_dict(),
            }
            if pb.venue_order_id:
                submitted["venueOrderId"] = pb.venue_order_id
            return submitted
        if pb.status == "unknown":
            out: dict[str, Any] = {
                "status": "unknown",
                "reason": pb.reason,
                "transactionId": None,
                "brokerAdapter": pb.receipt().to_dict(),
            }
            if pb.paper_order is not None:
                out["paperOrder"] = pb.paper_order.to_dict()
            if pb.paper_receipt is not None:
                out["paperBroker"] = pb.paper_receipt.to_dict()
            return out
        trade = pb.trade
        tx_id = pb.transaction_id
        await self._repo.delete(order.id, account_id=scope.account.id)
        filled_at = getattr(getattr(trade, "transaction", None), "executed_at", None)
        snapshot = (
            order.trade_plan_snapshot
            if isinstance(order.trade_plan_snapshot, dict)
            else None
        )
        if isinstance(tx_id, str) and tx_id.strip():
            await sync_position_after_ledger_fill(
                account_id=scope.account.id,
                instrument_id=order.instrument_id,
                side=side,
                fill_price=float(order.limit_price),
                fill_quantity=float(order.quantity),
                trade=trade,
                open_transaction_id=tx_id,
                filled_at=str(filled_at) if filled_at else None,
                position_from_fill=self._position_from_fill,
                position_from_exit=self._position_from_exit,
                trade_plan_snapshot=snapshot,
            )
        executed: dict[str, Any] = {
            "status": "executed",
            "reason": None,
            "transactionId": tx_id,
            "brokerAdapter": pb.receipt().to_dict(),
        }
        if pb.paper_order is not None:
            executed["paperOrder"] = pb.paper_order.to_dict()
        if pb.paper_receipt is not None:
            executed["paperBroker"] = pb.paper_receipt.to_dict()
        return executed

    async def _risk_allows_opening(
        self, *, order: PendingOrderRecord, account_id: str
    ) -> bool:
        return await allow_opening_fill(
            portfolio_summary=self._portfolio_summary,
            instruments=self._instruments,
            profile_store=self._profile_store,
            accounts=self._accounts,
            ohlcv=self._ohlcv,
            mandates=self._mandates,
            account_id=account_id,
            instrument_id=order.instrument_id,
            symbol=str(order.symbol or order.instrument_id),
            trade_type="buy",
            quantity=float(order.quantity),
            price=float(order.limit_price),
            signal_kind="recommend_long",
        )
