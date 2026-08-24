"""Fill de pending_orders a través del Decision Spine (ADR-031).

El monitor FE ya no llama ``ExecuteTrade`` directo. Las aperturas (side=buy)
re-ejecutan ``check_opening`` (mismo SoT SEMI/AUTO). Los sells no abren cesta
y no pasan el gate de apertura.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_domain.entities.investor_profile import InvestorProfileRecord
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    PendingOrderRecord,
    SqlAlchemyPendingOrderRepository,
)

from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.confirm_recommendation import (
    AccountScopeLookup,
    InstrumentSectorLookup,
    LatestBarLookup,
)
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.risk_engine import check_opening
from bolsa_application.risk_runtime import effective_kill_switch


def _basket_positions_from_summary(summary: Any) -> list[BasketPosition] | None:
    positions = getattr(summary, "positions", None)
    if positions is None:
        return None
    return [
        BasketPosition(
            instrument_id=getattr(p, "instrument_id", ""),
            market_value=getattr(p, "market_value", None),
            sector=getattr(p, "sector", None),
        )
        for p in positions
    ]


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
    ) -> None:
        self._repo = repo
        self._account_repo = account_repo
        self._execute_trade = execute_trade
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates

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
        trade = await self._execute_trade.execute(
            instrument_id=order.instrument_id,
            trade_type=side,
            quantity=float(order.quantity),
            price=float(order.limit_price),
            account_id=scope.account.id,
            idempotency_key=idempotency_key,
        )
        await self._repo.delete(order.id, account_id=scope.account.id)
        tx_id = getattr(trade, "transaction_id", None) or getattr(
            getattr(trade, "transaction", None), "id", None
        )
        return {"status": "executed", "reason": None, "transactionId": tx_id}

    async def _risk_allows_opening(
        self, *, order: PendingOrderRecord, account_id: str
    ) -> bool:
        try:
            summary = await self._portfolio_summary.execute(account_id=account_id)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return False
        equity = float(getattr(summary, "total_equity", 0) or 0)
        positions = getattr(summary, "positions", None)
        open_positions_count = len(positions) if positions is not None else 0
        last_bar_timestamp: str | None = None
        require_fresh_data = False
        if self._ohlcv is not None:
            require_fresh_data = True
            try:
                last_bar_timestamp = await self._ohlcv.get_latest_bar_date(
                    order.instrument_id
                )
            except Exception:  # noqa: BLE001
                return False
        has_open_mandate = False
        mandate_strategy_id: str | None = None
        require_account_mandate = False
        if self._mandates is not None:
            require_account_mandate = True
            try:
                has_open_mandate, mandate_strategy_id = (
                    await self._mandates.get_open_mandate_for_instrument(
                        account_id, order.instrument_id
                    )
                )
            except Exception:  # noqa: BLE001
                return False
        decision = check_opening(
            profile=await self._resolve_opening_profile(account_id),
            instrument_id=order.instrument_id,
            symbol=str(order.symbol or order.instrument_id),
            trade_type="buy",
            quantity=float(order.quantity),
            price=float(order.limit_price),
            signal_kind="recommend_long",
            equity=equity,
            open_positions_count=open_positions_count,
            auto_live=False,
            kill_switch=await effective_kill_switch(),
            portfolio_positions=_basket_positions_from_summary(summary),
            proposal_sector=await self._resolve_proposal_sector(order.instrument_id),
            last_bar_timestamp=last_bar_timestamp,
            require_fresh_data=require_fresh_data,
            has_open_mandate=has_open_mandate,
            mandate_strategy_id=mandate_strategy_id,
            require_account_mandate=require_account_mandate,
        )
        return bool(decision.allowed)

    async def _resolve_opening_profile(
        self, account_id: str
    ) -> InvestorProfileRecord | None:
        if self._profile_store is None or self._accounts is None or not account_id:
            return None
        try:
            scope = await self._accounts.resolve_scope(account_id)
            active_profile_id = getattr(
                getattr(scope, "account", None), "active_profile_id", None
            )
            if not active_profile_id:
                return None
            return await self._profile_store.get(active_profile_id)
        except Exception:  # noqa: BLE001
            return None

    async def _resolve_proposal_sector(self, instrument_id: str) -> str | None:
        if self._instruments is None or not instrument_id:
            return None
        try:
            inst = await self._instruments.get_by_id(instrument_id)
        except Exception:  # noqa: BLE001
            return None
        if inst is None:
            return None
        sector = getattr(inst, "sector", None)
        if isinstance(sector, str) and sector.strip():
            return sector.strip()
        return None
