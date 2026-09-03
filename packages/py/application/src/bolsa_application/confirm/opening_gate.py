"""DEX-4 — OpeningGate coordinator (cesta check_opening → risk_veto)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_application.opening_permission import allow_opening_fill


class OpeningGateCoordinator:
    """Escalón 3/D1 + DS-03/05 + OR-4 + DEX-3 via ``allow_opening_fill``."""

    def __init__(
        self,
        *,
        portfolio_summary: Any | None = None,
        instruments: Any | None = None,
        profile_store: Any | None = None,
        accounts: Any | None = None,
        ohlcv: Any | None = None,
        mandates: Any | None = None,
        portfolio_recon: Any | None = None,
        live_recon: Any | None = None,
        lifecycle_recon: Any | None = None,
        incident_store: Any | None = None,
        instrument_data_status: Any | None = None,
        resolve_broker_venue: Any | None = None,
    ) -> None:
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates
        self._portfolio_recon = portfolio_recon
        self._live_recon = live_recon
        self._lifecycle_recon = lifecycle_recon
        self._incident_store = incident_store
        self._instrument_data_status = instrument_data_status
        self._resolve_broker_venue = resolve_broker_venue

    async def allows_opening(
        self,
        *,
        rec: Recommendation,
        intent: Any,
        price: float,
        account_id: str,
    ) -> bool:
        venue = "paper"
        if self._resolve_broker_venue is not None:
            venue = await self._resolve_broker_venue(account_id)
        return await allow_opening_fill(
            portfolio_summary=self._portfolio_summary,
            instruments=self._instruments,
            profile_store=self._profile_store,
            accounts=self._accounts,
            ohlcv=self._ohlcv,
            mandates=self._mandates,
            portfolio_recon=self._portfolio_recon,
            live_recon=self._live_recon,
            lifecycle_recon=self._lifecycle_recon,
            incident_store=self._incident_store,
            instrument_data_status=self._instrument_data_status,
            broker_venue=venue,
            account_id=account_id,
            instrument_id=intent.instrument_id,
            symbol=str(rec.symbol or intent.instrument_id),
            trade_type=str(intent.side),
            quantity=float(intent.quantity),
            price=float(price),
            signal_kind=str(rec.action),
        )
