"""HTTP paper trade con permiso pre-fill (Ciclo I1).

``buy`` re-ejecuta ``allow_opening_fill`` (mismo SoT que Confirm/Fill).
``sell`` no abre cesta y no pasa el gate de apertura.
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
    ) -> None:
        self._execute_trade = execute_trade
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates

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
            )
            if not allowed:
                raise OpeningVetoedError("risk_veto")
        return await self._execute_trade.execute(
            instrument_id=instrument_id,
            trade_type=side,
            quantity=quantity,
            price=price,
            account_id=account_id,
            idempotency_key=idempotency_key,
        )

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
