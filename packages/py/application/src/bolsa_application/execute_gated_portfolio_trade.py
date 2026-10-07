"""HTTP paper trade con permiso pre-fill (Ciclo I1) + sync PositionState (OI-1).

``buy`` re-ejecuta ``allow_opening_fill`` (mismo SoT que Confirm/Fill).
``sell`` no abre cesta; V1.32 — si hay PositionState abierta, exige Confirm
(ExitPermission) y no deja bypass HTTP. V2.88.85 (H1): excepción para posiciones
nacidas por el canal manual (``HUMAN_MANUAL``), que sí cierran por HTTP.
Tras fill: ``post_fill_position_sync`` alinea ledger y Position persistida.
"""

from __future__ import annotations

from typing import Any

from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import ExecuteTrade, GetPortfolioSummary
from bolsa_application.accounts.idempotency import _trade_payload_matches
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.opening_permission import (
    AccountScopeLookup,
    InstrumentSectorLookup,
    LatestBarLookup,
    allow_opening_fill,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    open_transaction_id_from_trade,
)
from bolsa_application.post_fill_position_sync import (
    HUMAN_MANUAL_OVERRIDE,
    sync_position_after_ledger_fill,
)
from bolsa_application.reconciliation_opening_gate import (
    LiveReconLookup,
    PortfolioReconLookup,
)
from bolsa_domain.errors import IdempotencyKeyReused

#: V2.88.85 (H1) — origen del snapshot de una posición nacida por el canal HTTP manual.
HUMAN_MANUAL_ORIGIN = "HUMAN_MANUAL"

#: V2.88.85 (H1) — prefijo del ``trade_plan_id`` sintetizado para esas posiciones.
HUMAN_MANUAL_TRADE_PLAN_PREFIX = "manual-"


def _row_field(row: Any, name: str) -> Any:
    """Lee un campo de una fila de posición (``dict`` o ``PositionStateRecord``)."""
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def row_is_human_manual(row: Any) -> bool:
    """V2.88.85 (H1) — ¿la posición nació por el canal HTTP manual (``HUMAN_MANUAL``)?

    Una posición que el propio usuario abrió en modo MANUAL debe poder cerrarse por HTTP
    con la misma identidad. El fence de venta sigue intacto para posiciones SEMI/AUTO:
    aquí solo se autoriza la salida directa cuando la fila declara origen manual
    (``birth_override_reason``/``trade_plan_snapshot.origin``/``trade_plan_id`` ``manual-``).
    """
    if row is None:
        return False
    override = _row_field(row, "birth_override_reason")
    if isinstance(override, str) and override.strip() == HUMAN_MANUAL_OVERRIDE:
        return True
    snapshot = _row_field(row, "trade_plan_snapshot")
    if isinstance(snapshot, dict):
        origin = snapshot.get("origin")
        if isinstance(origin, str) and origin.strip() == HUMAN_MANUAL_ORIGIN:
            return True
    trade_plan_id = _row_field(row, "trade_plan_id")
    if isinstance(trade_plan_id, str) and trade_plan_id.strip().startswith(
        HUMAN_MANUAL_TRADE_PLAN_PREFIX
    ):
        return True
    return False


class OpeningVetoedError(Exception):
    """Apertura HTTP bloqueada por ``check_opening`` (fail-closed)."""


class ExitVetoedError(Exception):
    """V1.32 — venta HTTP bloqueada si hay PositionState (usar Confirm SEMI).

    V2.88.85 (H1): no se lanza para posiciones ``HUMAN_MANUAL`` (ver :func:`row_is_human_manual`).
    """


class ExecuteGatedPortfolioTrade:
    """Use-case del ``POST /portfolio/trade``: gate en buy, fence en sell+Position."""

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
        lifecycle_recon: Any | None = None,
        incident_store: Any | None = None,
        instrument_data_status: Any | None = None,
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
        self._lifecycle_recon = lifecycle_recon
        self._incident_store = incident_store
        self._instrument_data_status = instrument_data_status
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

        # Replay idempotente ANTES del gate (P2): si ya existe un trade con esta
        # ``idempotency_key``, la petición NO es una nueva apertura y no debe reevaluarse
        # ``allow_opening_fill``. Sin esto, un reintento legítimo (mismo payload tras un
        # timeout) veía la posición ya abierta por el primer intento y el gate la vetaba
        # → 403 en vez de rejugar el 200.
        #
        # Y si la key existe pero el payload CAMBIÓ, el conflicto (409) también tiene
        # prioridad sobre el 403 del gate: la reutilización de la key es un error
        # determinista del cliente que debe reportarse como tal, no enmascararse como un
        # veto de apertura. Si se dejara pasar al gate, la posición ya abierta lo vetaría
        # y devolveríamos 403 en lugar del 409 esperado.
        existing = await self._execute_trade.find_existing_by_idempotency(
            account_id=account_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if not _trade_payload_matches(
                existing.transaction,
                instrument_id=instrument_id,
                trade_type=side,
                quantity=float(quantity),
                price=float(price),
            ):
                raise IdempotencyKeyReused(idempotency_key)
            return existing

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
                lifecycle_recon=self._lifecycle_recon,
                incident_store=self._incident_store,
                instrument_data_status=self._instrument_data_status,
                broker_venue=venue,
            )
            if not allowed:
                raise OpeningVetoedError("risk_veto")
        elif side == "sell" and self._position_from_exit is not None:
            # V1.32 — Position abierta ⇒ Confirm SEMI (ExitPermission), no HTTP.
            # V2.88.85 (H1) — salvo una posición nacida por el canal manual
            # (``HUMAN_MANUAL``): quien abrió en MANUAL debe poder cerrar por HTTP. El
            # fence sigue intacto para posiciones SEMI/AUTO (origen != manual).
            row = await self._position_from_exit.get_open(
                account_id or "", instrument_id
            )
            if row is not None and not row_is_human_manual(row):
                raise ExitVetoedError(
                    "position_exit_requires_confirm: esta posición no es manual; "
                    "usa Confirm (SEMI) para cerrarla o reducirla."
                )
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
        # HUMAN_MANUAL: este HTTP no es Confirm SEMI. Sin TradePlan TRIGGERED
        # el sync sintetiza snapshot ``manual-{tx}`` — no inventar un plan IA.
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
