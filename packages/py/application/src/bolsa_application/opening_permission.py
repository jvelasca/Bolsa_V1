"""Permiso pre-fill de aperturas (ADR-031 / Ciclo I1).

Confirm SEMI, FillPendingOrder y ``POST /portfolio/trade`` reutilizan
``allow_opening_fill`` → ``check_opening``. ExecutionRouter AUTO no se
fusiona aquí (drawdown, book max, strategy mismatch).

``portfolio_summary=None`` conserva el wiring de test legado (no aplica cesta).
OHLCV / mandates ausentes = gate DS-05 / DS-03 off (mismo patrón Confirm/Fill).
OR-4: portfolio_recon / live_recon ausentes = gate recon off; inyectados →
fail-closed + veto drift / live unavailable (venue live).
DEX-3: incident_store ausente = gate incident off; inyectado → abre INC
en drift y veta ``incident:unresolved`` mientras haya incidente activo.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.operational_incident_store import (
    OperationalIncidentStore,
    sync_opening_incidents,
)
from bolsa_application.reconciliation_opening_gate import (
    LifecycleReconGateStatus,
    LifecycleReconLookup,
    LiveReconLookup,
    LiveReconStatus,
    PortfolioReconLookup,
    PortfolioReconStatus,
)
from bolsa_application.risk_engine import check_opening
from bolsa_application.risk_runtime import effective_kill_switch
from bolsa_domain.entities.investor_profile import InvestorProfileRecord


class InstrumentSectorLookup(Protocol):
    """Puerto mínimo para resolver ``instruments.sector`` (H1)."""

    async def get_by_id(self, instrument_id: str) -> Any | None: ...


class AccountScopeLookup(Protocol):
    """Puerto mínimo para ``scope.account.active_profile_id`` (H5)."""

    async def resolve_scope(
        self, account_id: str, portfolio_id: str | None = None
    ) -> Any: ...


class LatestBarLookup(Protocol):
    """Puerto mínimo DS-05 — última barra OHLCV del instrumento."""

    async def get_latest_bar_date(
        self,
        instrument_id: str,
        *,
        timeframe: Any = ...,
    ) -> str | None: ...

    async def get_latest_close(
        self,
        instrument_id: str,
        *,
        timeframe: Any = ...,
    ) -> float | None: ...


def basket_positions_from_summary(summary: Any) -> list[BasketPosition] | None:
    """Cesta de posiciones para Fit (sector desde infra si está poblado)."""
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


async def resolve_opening_profile(
    *,
    profile_store: InvestorProfileStore | None,
    accounts: AccountScopeLookup | None,
    account_id: str,
) -> InvestorProfileRecord | None:
    """H5 — perfil activo. Fail-open solo en perfil (defaults moderate)."""
    if profile_store is None or accounts is None or not account_id:
        return None
    try:
        scope = await accounts.resolve_scope(account_id)
        active_profile_id = getattr(
            getattr(scope, "account", None), "active_profile_id", None
        )
        if not active_profile_id:
            return None
        return await profile_store.get(active_profile_id)
    except Exception:  # noqa: BLE001 — perfil opcional; no tumba cesta/kill-switch
        return None


async def resolve_proposal_sector(
    *,
    instruments: InstrumentSectorLookup | None,
    instrument_id: str,
) -> str | None:
    """H1 — sector de la puesta nueva. Excepción o sin sector → None."""
    if instruments is None or not instrument_id:
        return None
    try:
        inst = await instruments.get_by_id(instrument_id)
    except Exception:  # noqa: BLE001 — sin sector no bloquea el gate de cesta
        return None
    if inst is None:
        return None
    sector = getattr(inst, "sector", None)
    if isinstance(sector, str) and sector.strip():
        return sector.strip()
    return None


async def allow_opening_fill(
    *,
    portfolio_summary: GetPortfolioSummary | None,
    account_id: str,
    instrument_id: str,
    symbol: str,
    trade_type: str,
    quantity: float,
    price: float,
    signal_kind: str,
    instruments: InstrumentSectorLookup | None = None,
    profile_store: InvestorProfileStore | None = None,
    accounts: AccountScopeLookup | None = None,
    ohlcv: LatestBarLookup | None = None,
    mandates: AccountMandateLookup | None = None,
    portfolio_recon: PortfolioReconLookup | None = None,
    live_recon: LiveReconLookup | None = None,
    lifecycle_recon: LifecycleReconLookup | None = None,
    broker_venue: Literal["paper", "live"] | str | None = None,
    incident_store: OperationalIncidentStore | None = None,
    instrument_data_status: Any | None = None,
) -> bool:
    """True si ``check_opening`` permite el fill de una apertura.

    ``portfolio_summary=None`` → True (legado tests / sin cesta).
    Summary o lookups OHLCV/mandate/recon que lanzan → False (fail-closed).
    """
    if portfolio_summary is None:
        return True
    try:
        summary = await portfolio_summary.execute(account_id=account_id)
    except Exception:  # noqa: BLE001 — H2: indisponibilidad = veto
        return False
    equity = float(getattr(summary, "total_equity", 0) or 0)
    positions = getattr(summary, "positions", None)
    open_positions_count = len(positions) if positions is not None else 0
    last_bar_timestamp: str | None = None
    require_fresh_data = False
    if ohlcv is not None:
        require_fresh_data = True
        try:
            last_bar_timestamp = await ohlcv.get_latest_bar_date(instrument_id)
        except Exception:  # noqa: BLE001 — DS-05: indisponibilidad = veto
            return False
    has_open_mandate = False
    mandate_strategy_id: str | None = None
    require_account_mandate = False
    if mandates is not None:
        require_account_mandate = True
        try:
            has_open_mandate, mandate_strategy_id = (
                await mandates.get_open_mandate_for_instrument(
                    account_id, instrument_id
                )
            )
        except Exception:  # noqa: BLE001 — DS-03: indisponibilidad = veto
            return False
    portfolio_recon_status: PortfolioReconStatus | None = None
    live_recon_status: LiveReconStatus | None = None
    lifecycle_recon_status: LifecycleReconGateStatus | None = None
    require_recon_veto = False
    if portfolio_recon is not None:
        require_recon_veto = True
        try:
            portfolio_recon_status = await portfolio_recon.portfolio_recon_status(
                account_id
            )
        except Exception:  # noqa: BLE001 — OR-4: indisponibilidad = veto
            return False
    if lifecycle_recon is not None:
        require_recon_veto = True
        try:
            lifecycle_recon_status = await lifecycle_recon.lifecycle_recon_status(
                account_id
            )
        except Exception:  # noqa: BLE001 — OR-4 lifecycle: indisponibilidad = veto
            return False
    venue = (broker_venue or "paper").strip().lower()
    if live_recon is not None and venue == "live":
        require_recon_veto = True
        try:
            live_recon_status = await live_recon.live_recon_status(account_id)
        except Exception:  # noqa: BLE001 — OR-4 live: indisponibilidad = veto
            return False
    incident_status: Literal["clear", "unresolved"] | None = None
    require_incident_veto = False
    if incident_store is not None:
        require_incident_veto = True
        try:
            incident_status = await sync_opening_incidents(
                incident_store,
                account_id=account_id,
                portfolio_recon_status=portfolio_recon_status,
                live_recon_status=live_recon_status,
                broker_venue=venue,
            )
        except Exception:  # noqa: BLE001 — DEX-3: indisponibilidad = veto
            return False
    sanity_warnings: tuple[str, ...] = ()
    if instrument_data_status is not None and require_fresh_data:
        try:
            status = await instrument_data_status.execute(instrument_id)
            if status is not None:
                sanity_warnings = tuple(getattr(status, "sanity_warnings", ()) or ())
        except Exception:  # noqa: BLE001 — sanity E2E: indisponibilidad = veto
            return False
    decision = check_opening(
        profile=await resolve_opening_profile(
            profile_store=profile_store,
            accounts=accounts,
            account_id=account_id,
        ),
        instrument_id=instrument_id,
        symbol=symbol,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
        signal_kind=signal_kind,
        equity=equity,
        open_positions_count=open_positions_count,
        auto_live=False,
        kill_switch=await effective_kill_switch(),
        portfolio_positions=basket_positions_from_summary(summary),
        proposal_sector=await resolve_proposal_sector(
            instruments=instruments,
            instrument_id=instrument_id,
        ),
        last_bar_timestamp=last_bar_timestamp,
        require_fresh_data=require_fresh_data,
        has_open_mandate=has_open_mandate,
        mandate_strategy_id=mandate_strategy_id,
        require_account_mandate=require_account_mandate,
        portfolio_recon_status=portfolio_recon_status,
        live_recon_status=live_recon_status,
        lifecycle_recon_status=lifecycle_recon_status,
        broker_venue=venue,
        require_recon_veto=require_recon_veto,
        incident_status=incident_status,
        require_incident_veto=require_incident_veto,
        sanity_warnings=sanity_warnings,
    )
    return bool(decision.allowed)
