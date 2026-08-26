"""OR-4 — Reconciliation → opening veto (ADR-035).

OI-6 / LR-1 detect/report. Este módulo convierte drift / live unavailable
en VETO de apertura. Exits protectivos bypassean (signal_kind exit*).
Nunca auto-heal.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from bolsa_application.reconcile_live_ledger import (
    ReconcileLiveLedger,
    ReconcileLiveLedgerInput,
)
from bolsa_application.reconcile_portfolio_integrity import (
    ReconcilePortfolioIntegrity,
    ReconcilePortfolioIntegrityInput,
)

PortfolioReconStatus = Literal["clean", "drift"]
LiveReconStatus = Literal["clean", "drift", "unavailable"]
BrokerVenue = Literal["paper", "live"]


def reconciliation_opening_veto_reason(
    *,
    portfolio_recon_status: PortfolioReconStatus | None = None,
    live_recon_status: LiveReconStatus | None = None,
    broker_venue: BrokerVenue | str | None = None,
    require: bool = False,
) -> str | None:
    """Devuelve reason de VETO OR-4, o None si la apertura puede seguir.

    - ``require=False`` y sin statuses → gate off (compat tests / wiring legado).
    - ``portfolio_recon_status=drift`` → ``reconciliation:portfolio_drift`` (cualquier venue).
    - Venue ``live``: ``live_drift`` / ``live_unavailable`` vetan; status ausente con
      ``require`` → ``live_unavailable`` fail-closed.
    - Venue paper (default): ignora live status (bridge ausente no tumba paper).
    """
    if (
        not require
        and portfolio_recon_status is None
        and live_recon_status is None
    ):
        return None

    if portfolio_recon_status == "drift":
        return "reconciliation:portfolio_drift"

    venue = (broker_venue or "paper").strip().lower()
    if venue == "live":
        if live_recon_status == "drift":
            return "reconciliation:live_drift"
        if live_recon_status == "unavailable" or live_recon_status is None:
            # require + live sin status = fail-closed unavailable
            if live_recon_status == "unavailable" or require:
                return "reconciliation:live_unavailable"
    return None


class PortfolioReconLookup(Protocol):
    """Puerto OR-4 — status OI-6 por cuenta."""

    async def portfolio_recon_status(self, account_id: str) -> PortfolioReconStatus:
        """``clean`` | ``drift``. Lanza si infra falla."""
        ...


class LiveReconLookup(Protocol):
    """Puerto OR-4 — status LR-1 por cuenta."""

    async def live_recon_status(self, account_id: str) -> LiveReconStatus:
        """``clean`` | ``drift`` | ``unavailable``. Lanza si infra falla."""
        ...


class ReconcilePortfolioIntegrityLookup:
    """Adapter OI-6 → status para el opening veto."""

    def __init__(self, uc: ReconcilePortfolioIntegrity) -> None:
        self._uc = uc

    async def portfolio_recon_status(self, account_id: str) -> PortfolioReconStatus:
        report = await self._uc.reconcile(
            ReconcilePortfolioIntegrityInput(
                account_id=account_id,
                include_tx_links=False,
            )
        )
        if report is None:
            raise RuntimeError("portfolio recon unavailable")
        return report.status


class ReconcileLiveLedgerLookup:
    """Adapter LR-1 → status para el opening veto."""

    def __init__(self, uc: ReconcileLiveLedger) -> None:
        self._uc = uc

    async def live_recon_status(self, account_id: str) -> LiveReconStatus:
        report = await self._uc.reconcile(
            ReconcileLiveLedgerInput(account_id=account_id)
        )
        if report is None:
            raise RuntimeError("live recon unavailable")
        return report.status


class PortfolioCashFromSummary:
    """Cash paper desde ``GetPortfolioSummary``."""

    def __init__(self, portfolio_summary: Any) -> None:
        self._summary = portfolio_summary

    async def get_cash(self, account_id: str) -> float:
        summary = await self._summary.execute(account_id=account_id)
        return float(getattr(getattr(summary, "portfolio", None), "cash", 0) or 0)


class HoldingsFromSummary:
    """Holdings desde ``GetPortfolioSummary.positions``."""

    def __init__(self, portfolio_summary: Any) -> None:
        self._summary = portfolio_summary

    async def list_holdings(self, account_id: str) -> list[dict[str, Any]]:
        summary = await self._summary.execute(account_id=account_id)
        positions = getattr(summary, "positions", None) or []
        out: list[dict[str, Any]] = []
        for p in positions:
            iid = getattr(p, "instrument_id", None)
            if isinstance(iid, str) and iid.strip():
                out.append(
                    {
                        "instrument_id": iid.strip(),
                        "quantity": float(getattr(p, "quantity", 0) or 0),
                    }
                )
        return out


class OpenPositionsFromRepo:
    """OPEN PositionState rows → snaps OI-6."""

    def __init__(self, position_repo: Any) -> None:
        self._repo = position_repo

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        rows = await self._repo.list_open_for_account(account_id)
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "instrument_id": getattr(row, "instrument_id", ""),
                    "status": getattr(row, "status", "OPEN"),
                    "open_transaction_id": getattr(row, "open_transaction_id", None),
                    "position_state": getattr(row, "position_state", None),
                }
            )
        return out


class LedgerCashPort:
    """Σ ledger cash."""

    def __init__(self, ledger_repo: Any) -> None:
        self._ledger = ledger_repo

    async def sum_cash_amounts(self, account_id: str) -> float:
        return float(await self._ledger.sum_cash_amounts(account_id))


class XtbBridgeLiveVenueAdapter:
    """LiveVenuePort sobre ``XtbBridgeClient`` (LR-1)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def fetch_cash(self) -> float:
        cash = await self._client.fetch_cash()
        return float(getattr(cash, "cash", cash) or 0)

    async def fetch_positions(self) -> list[dict[str, Any]]:
        rows = await self._client.fetch_positions()
        out: list[dict[str, Any]] = []
        for row in rows:
            iid = getattr(row, "instrument_id", None)
            if isinstance(iid, str) and iid.strip():
                out.append(
                    {
                        "instrument_id": iid.strip(),
                        "quantity": float(getattr(row, "quantity", 0) or 0),
                    }
                )
        return out
