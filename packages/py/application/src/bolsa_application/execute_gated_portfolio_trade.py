"""HTTP paper trade con permiso pre-fill (Ciclo I1) + sync PositionState (OI-1).

``buy`` re-ejecuta ``allow_opening_fill`` (mismo SoT que Confirm/Fill).
``sell`` no abre cesta y no pasa el gate de apertura.
Tras fill: ``post_fill_position_sync`` alinea ledger y Position persistida.
"""

from __future__ import annotations

from typing import Any

from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import ExecuteTrade, GetPortfolioSummary
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.opening_permission import (
    AccountScopeLookup,
    InstrumentSectorLookup,
    LatestBarLookup,
    allow_opening_fill,
)
from bolsa_application.reconciliation_opening_gate import (
    LiveReconLookup,
    PortfolioReconLookup,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    open_transaction_id_from_trade,
)
from bolsa_application.post_fill_position_sync import sync_position_after_ledger_fill


class OpeningVetoedError(Exception):
    """Apertura HTTP bloqueada por ``check_opening`` (fail-closed)."""


class ExecuteGatedPortfolioTrade:
    """Use-case del ``POST /portfolio/trade``: gate en buy, ledger en ambos."""

    def __init__(
        self,
        execute_trade: ExecuteTrade,
        *,
        portfolio_summary: GetPortfolioSummary,
        instruments: InstrumentSectorLookup | None = None,
        profile_store: InvestorProfileStore | None = None,
        accounts: AccountScopeLookup | None = None,
        ohlcv: LatestBarLookup | None = None,
        mandates: AccountMandateLookup | None = None,
        portfolio_recon: PortfolioReconLookup | None = None,
        live_recon: LiveReconLookup | None = None,
        position_from_fill: PersistPositionFromFill | None = None,
        position_from_exit: PersistPositionFromExit | None = None,
    ) -> None:
        self._execute_trade = execute_trade
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates
        self._portfolio_recon = portfolio_recon
        self._live_recon = live_recon
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit

    async def execute(
        self,
        *,
        instrument_id: str,
        trade_type: str,
        quantity: float,
        price: float,
        account_id: str | None,
        idempotency_key: str,
    ) -> Any:
        side = str(trade_type).lower()
        if side == "buy":
            symbol = await self._resolve_symbol(instrument_id)
            venue = await self._resolve_broker_venue(account_id or "")
            allowed = await allow_opening_fill(
                portfolio_summary=self._portfolio_summary,
                account_id=account_id or "",
                instrument_id=instrument_id,
                symbol=symbol,
                trade_type="buy",
                quantity=float(quantity),
                price=float(price),
                signal_kind="recommend_long",
                instruments=self._instruments,
                profile_store=self._profile_store,
                accounts=self._accounts,
                ohlcv=self._ohlcv,
                mandates=self._mandates,
                portfolio_recon=self._portfolio_recon,
                live_recon=self._live_recon,
                broker_venue=venue,
            )
            if not allowed:
                raise OpeningVetoedError("risk_veto")
        trade = await self._execute_trade.execute(
            instrument_id=instrument_id,
            trade_type=side,
            quantity=quantity,
            price=price,
            account_id=account_id,
            idempotency_key=idempotency_key,
        )
        tx_id = open_transaction_id_from_trade(trade)
        filled_at = getattr(getattr(trade, "transaction", None), "executed_at", None)
        await sync_position_after_ledger_fill(
            account_id=account_id or "",
            instrument_id=instrument_id,
            side=side,
            fill_price=float(price),
            fill_quantity=float(quantity),
            trade=trade,
            open_transaction_id=tx_id,
            filled_at=str(filled_at) if filled_at else None,
            position_from_fill=self._position_from_fill,
            position_from_exit=self._position_from_exit,
            trade_plan_snapshot=None,
        )
        return trade

    async def _resolve_broker_venue(self, account_id: str) -> str:
        from bolsa_application.broker_venue_runtime import (
            account_broker_venue_from_settings,
            effective_broker_venue_async,
        )

        account_venue: str | None = None
        getter = getattr(self._accounts, "get_settings_json", None) if self._accounts else None
        if getter is not None and account_id:
            try:
                settings = await getter(account_id)
                account_venue = account_broker_venue_from_settings(settings)
            except Exception:  # noqa: BLE001
                account_venue = None
        return await effective_broker_venue_async(account_venue=account_venue)

    async def _resolve_symbol(self, instrument_id: str) -> str:
        if self._instruments is None or not instrument_id:
            return instrument_id
        try:
            inst = await self._instruments.get_by_id(instrument_id)
        except Exception:  # noqa: BLE001
            return instrument_id
        if inst is None:
            return instrument_id
        symbol = getattr(inst, "symbol", None)
        if isinstance(symbol, str) and symbol.strip():
            return symbol.strip()
        return instrument_id
