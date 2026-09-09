"""V2.12 — LiveOrderRecoveryWorker (XL-3 UNKNOWN → query_broker, NO re-POST).

On-by-default (env ``LIVE_RECOVERY_WORKER_ENABLED``) en ``scheduler_worker``, no
en la lifespan de FastAPI (evita duplicación bajo ``uvicorn --workers N``). Cada
tick lee filas duraderas ``live_orders`` en estado ``UNKNOWN`` y las resuelve con
el puerto ``LiveOrderQueryPort`` (``query_broker``). Resolver **nunca** re-POSTea:
UNKNOWN solo sale vía query del broker o queda UNKNOWN si el venue no contesta.

Fail-closed:
* Sin cliente de query cableado para la cuenta/venue → tratar como
  ``unavailable``: la fila queda UNKNOWN y se refresca ``updated_at`` (para no
  hilar fino) + se anota el intento. Nada se cierra en falso.
* Un outcome ``unavailable`` del cliente real → igualmente UNKNOWN (sin estado
  terminal fabricado).
* Los outcomes ``partial``/``filled``/``working``/``rejected``/``cancelled`` que
  iluminan una transición legal desde UNKNOWN se persisten como estado de la
  máquina. **NO** se sintetiza ``execute_trade``/ledger aquí (veto XL-3; el
  slice XL-2 síncrono sigue vivo y el apply financiero sigue PARKED).

≠ thaw · ≠ PAPER_D_EXECUTE · ≠ autoriza re-POST.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.live_order_query import LiveOrderQueryPort
from bolsa_application.live_order_store import PostgresLiveOrderStore

logger = logging.getLogger(__name__)

TICK_SECONDS = 5
_ENV_ENABLED = "LIVE_RECOVERY_WORKER_ENABLED"
_DEFAULT_BATCH = 50


# Ventana de lease del claimed UNKNOWN antes de que otro worker pueda reapropiarlo.
# Configurable por entorno (no solo parámetro interno): cada deployment puede
# sintonizar sin editar fuente. Se lee en import para una semántica global estable.
def _claim_stale_seconds_default() -> int:
    raw = (os.getenv("LIVE_RECOVERY_CLAIM_STALE_SECONDS") or "120").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 120
    return value if value > 0 else 120


DEFAULT_CLAIM_STALE_SECONDS = _claim_stale_seconds_default()

# Provider shape: (venue, account_id, venue_order_id) → query port | None.
QueryProvider = Callable[
    [str, str, str],
    Awaitable[LiveOrderQueryPort | None],
]


def _worker_identity() -> str:
    """Id estable por worker/proceso para el lease cross-PID."""
    try:
        pid = str(os.getpid())
    except Exception:  # noqa: BLE001 — portabilidad
        pid = "?"
    return f"live-recovery-{pid}"


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


# V2.19 (P2-01/C3) — go fail-closed del apply financiero en el recovery.
# Según plan: lectura en import (estilo ``live_drift_durable_writer_enabled``),
# default OFF. Sin go el recovery queda fsm_only exacto de V2.18 (nada de dinero
# materializado en Position/Ledger desde un fill recuperado).
_GO_ENV = "LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED"


def financial_apply_enabled() -> bool:
    """¿Está encendido el puente financiero del recovery? (default OFF = off).

    Fail-closed: solo ``1|true|yes|on`` lo habilita. Sobre /a7-gate (BD dedicada
    real-PG) el CI inyecta ``=1`` para que la batería financiera no se auto-salte.
    """
    raw = (os.getenv(_GO_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def _no_query_provider(
    venue: str,
    account_id: str,
    venue_order_id: str,
) -> LiveOrderQueryPort | None:
    """Sin cliente real de query cableado → unavailable (fail-closed).

    Util de fallback: devuelve None (la fila permanece UNKNOWN, solo bump). No es
    el provider que el scheduler cablea por defecto cuando hay ``XTB_BRIDGE_URL``.
    """
    _ = venue, account_id, venue_order_id
    return None


def build_live_query_provider(
    *,
    bridge_url: str | None,
) -> QueryProvider:
    """Provider real de query por venue LIVE (H6), con bridge XTB.

    Devuelve una función dado (venue, account_id, venue_order_id) que entrega un
    adaptador que consulta ``GET /orders/{id}``:

    * venue ``LIVE`` y bridge URL disponible → ``XtbLiveOrderQueryAdapter``
      (fail-closed: ante error/timeout/404 del bridge el worker la trata como
      ``unavailable`` y la fila queda UNKNOWN — no se fabrica cierre);
    * cualquier otro caso (venue no-LIVE o sin URL) → ``None`` (semántica de
      ``_no_query_provider``).

    El bridge XTB es una configuración global del repo (``xtb_bridge_url``), no per
    account, así que el provider no distingue de account (solo filtra venue LIVE).
    """
    url = (bridge_url or "").strip()
    if not url:
        return _no_query_provider

    from bolsa_application.broker_adapter import XtbLiveOrderQueryAdapter
    from bolsa_market.providers import XtbBridgeClient

    client = XtbBridgeClient(url)

    async def _provider(
        venue: str,
        account_id: str,
        venue_order_id: str,
    ) -> LiveOrderQueryPort | None:
        if (venue or "").strip().upper() != "LIVE":
            return None
        # account_id / venue_order_id no afectan la construcción (cliente global);
        # se referencian solo para reconocer el contrato del provider.
        _ = account_id, venue_order_id
        return XtbLiveOrderQueryAdapter(client)

    return _provider


async def resolve_one_unknown(
    order: Any,
    query: LiveOrderQueryPort | None,
    *,
    store: Any,
    account_id: str,
    out_result: list[Any] | None = None,
) -> str:
    """Resuelve una fila UNKNOWN → devuelve 'resolved'|'unavailable'|'error'.

    Fail-closed:
    * sin cliente de query o sin venue_order_id → sigue UNKNOWN (updated_at bump).
    * outcome no mapeable / intraducible desde UNKNOWN → sigue UNKNOWN.
    * outcome legal → persiste la transición. NUNCA sintetiza execute_trade.
    * ``out_result`` (opcional): bucket mutable al que, si se resuelve a un fill
      real (FILLED/PARTIAL) y se consultó al broker, se le deja el ``result`` de
      la query para que el caller decida después el paso financiero bajo go. Con
      ``None`` (default) ni se crea ni se rellena: comporta exacto V2.18.
    """
    from bolsa_analytics.cognitive.live_order import (
        can_transition_live_order,
        transition_live_order,
    )

    if query is None or not order.venue_order_id:
        return await _refresh_unknown(store, order, account_id=account_id)
    result = await query.query_broker_order(venue_order_id=order.venue_order_id)
    target = result.to_live_status()
    if target is None or not can_transition_live_order(order.status, target):
        return await _refresh_unknown(store, order, account_id=account_id)
    filled_qty = order.filled_quantity
    if target in {"PARTIAL", "FILLED"} and result.filled_quantity is not None:
        filled_qty = float(result.filled_quantity)
    advanced = transition_live_order(
        order,
        target,
        filled_quantity=filled_qty,
    )
    await store.put(advanced, account_id=account_id)
    logger.info(
        "live_order %s UNKNOWN→%s (resolved vía query, no re-POST)",
        order.order_id,
        target,
    )
    if out_result is not None and target in {"FILLED", "PARTIAL"}:
        out_result[:] = [result]
    return "resolved"


async def _refresh_unknown(store: Any, order: Any, *, account_id: str) -> str:
    """Queda UNKNOWN; refresca updated_at para no hilar el ciclo de poll."""
    await store.put(order, account_id=account_id)
    return "unavailable"


async def _drain_unknowns(
    store: Any,
    *,
    query_provider: QueryProvider | None,
    limit: int,
    worker_id: str = "live-recovery-inprocess",
    stale_after_seconds: int = DEFAULT_CLAIM_STALE_SECONDS,
    _fill_results: list[tuple[Any, Any]] | None = None,
) -> dict[str, Any]:
    """Drena filas UNKNOWN del store (testable sin PG).

    Multi-worker: si el store expone claim/lease de fila (PG), cada tick
    *reclama* UNKNOWN con ``claim_unknown_batch`` (SKIP LOCKED + lease) en vez de
    listar a ciegas; dos workers no procesan la misma orden en paralelo. Si no
    hay mecanismo de claim (store genérico) se cae a ``list_unknown``.

    ``_fill_results`` (opcional, test-internal): si el caller quiere saber qué
    filas se resolvieron a un fill real (para el puente financiero bajo go), este
    bucket mutable recoge ``(order, query_result)`` por cada UNKNOWN→FILLED/
    PARTIAL resuelto en este tick. Default ``None`` → mismo comportamiento que
    siempre; no se crea ni se rellena nada (los tests unit no cambian).
    """
    provider = query_provider or _no_query_provider
    claim = getattr(store, "claim_unknown_batch", None)
    if claim is not None:
        rows = await claim(
            limit=limit,
            worker_id=worker_id,
            stale_after_seconds=stale_after_seconds,
        )
    else:
        rows = await store.list_unknown(limit=limit)
    resolved: int = 0
    unavailable: int = 0
    errors: int = 0
    for order in rows:
        try:
            query = await provider(order.venue, order.account_id, order.venue_order_id)
            bucket: list[Any] = []
            status = await resolve_one_unknown(
                order,
                query,
                store=store,
                account_id=order.account_id or "",
                out_result=bucket,
            )
            if status == "resolved":
                resolved += 1
                if _fill_results is not None and bucket:
                    _fill_results.append((order, bucket[0]))
            else:
                # UNKNOWN irresoluto / sin cliente: la fila sigue UNKNOWN y su
                # lease envejece; NO se llama a release_claim aquí para evitar
                # hilar fino (el claim fresco excluye hasta la ventana stale).
                unavailable += 1
        except Exception:  # noqa: BLE001 — una fila no tumba el tick
            errors += 1
            logger.exception("live_order recovery failed order_id=%s", order.order_id)

    return {
        "drained": len(rows),
        "resolved": resolved,
        "unavailable": unavailable,
        "errors": errors,
    }


async def _apply_recovery_fills_financially(
    session: AsyncSession,
    fills: list[tuple[Any, Any]],
) -> None:
    """Materializa (bajo go) los fills que este tick resolvió el recovery.

    Reiteración del puente por fases elegido (V2.19 · P2-01/C3):
      1. Se descartan los fills SIN precio/secuencia constatable
         (``build_recovery_execution_candidate`` → None) → fsm_only intacto.
      2. Para cada candidato se captura la traza ``execution_events`` y se aplica
         por ``apply_execution_financial_once`` (CAPTURED→APPLYING→APPLIED/
         FAILED/RETRY) reusando la idempotencia por ``execution_id`` + la
         ``idempotency_key`` financiera (ExecuteTrade M4). No-doble even con
         retry multi-worker / crash.

    ``fills`` = [(LiveOrder origen, BrokerOrderQueryResult)] del tick. Este paso
    construye sus propios repos sobre la MESMA sesión del recovery; las llamadas
    son idempotentes así que un crash intermedio reaprovecha los ticks siguientes
    sin doble materialización.
    """
    from bolsa_application.accounts import ExecuteTrade
    from bolsa_application.execution_event import (
        PostgresExecutionEventStore,
        apply_execution_financial_once,
    )
    from bolsa_application.recovery_apply import (
        build_recovery_execution_candidate,
        recovery_idempotency_key,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    account_repo = SqlAlchemyAccountRepository(session)
    portfolio_repo = SqlAlchemyPortfolioRepository(session)
    ledger_repo = SqlAlchemyLedgerRepository(session)
    exec_store = PostgresExecutionEventStore(session)
    trade = ExecuteTrade(account_repo, portfolio_repo, ledger_repo)

    for order, result in fills:
        candidate = build_recovery_execution_candidate(order, result)
        if candidate is None:
            continue  # sin precio/secuencia → no se toca dinero.
        # Capturamos por-valor (default-args) para evitar late-binding del loop.
        _instrument = order.instrument_id
        _side = order.side
        _fill_price = float(result.fill_price)

        async def _apply_one(
            _execution: Any,
            *,
            _instrument: str = _instrument,
            _side: str = _side,
            _price: float = _fill_price,
        ) -> bool:
            try:
                await trade.execute(
                    instrument_id=_instrument,
                    trade_type=_side,
                    quantity=float(_execution.qty),
                    price=_price,
                    account_id=_execution.account_id,
                    idempotency_key=recovery_idempotency_key(_execution.execution_id),
                )
                return True
            except Exception:  # noqa: BLE001 — NOT applied; no marcar APPLIED.
                logger.exception(
                    "recovery financial ExecuteTrade failed execution_id=%s",
                    _execution.execution_id,
                )
                return False

        try:
            outcome = await apply_execution_financial_once(
                exec_store,
                execution=candidate,
                apply_finance=_apply_one,
                retryable_on_ineffective=True,
            )
            logger.info(
                "recovery financial fill order=%s execution_id=%s outcome=%s",
                order.order_id,
                candidate.execution_id,
                outcome,
            )
        except Exception:  # noqa: BLE001 — un fill no tumba el resto del tick.
            logger.exception(
                "recovery financial durable failed execution_id=%s",
                candidate.execution_id,
            )


async def _drain_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    query_provider: QueryProvider | None = None,
    limit: int = _DEFAULT_BATCH,
    worker_id: str | None = None,
    stale_after_seconds: int = DEFAULT_CLAIM_STALE_SECONDS,
) -> dict[str, Any]:
    async with session_factory() as session:
        store = PostgresLiveOrderStore(session)
        fills: list[tuple[Any, Any]] = []  # (orden_origen, BrokerOrderQueryResult)
        result = await _drain_unknowns(
            store,
            query_provider=query_provider,
            limit=limit,
            worker_id=worker_id or _worker_identity(),
            stale_after_seconds=stale_after_seconds,
            _fill_results=fills,
        )
        # V2.19 (P2-01/C3) — puente financiero del recovery bajo go fail-closed.
        # Tras resolver a FILL/PARTIAL este tick, si el go financiero está ON y el
        # broker acreditó precio+secuencia, materializa por fases idempotentes en
        # la MISMA sesión. Sin go (default) o sin precio → cero dinero (fsm_only).
        # Un fallo financiero NO tumba el tick: fail-closed (siguiente tick
        # reintenta desde la fila / execution_events ya marcada APPLYING/RETRY).
        if fills and financial_apply_enabled():
            try:
                await _apply_recovery_fills_financially(session, fills)
            except Exception:  # noqa: BLE001 — nunca aborta el ciclo de recovery
                logger.exception("recovery financial apply (go) failed")
        # H7 — drift reconcile de la máquina (working/partial/cancel-requested):
        # mismo query_provider y misma sesión. Por defecto read-only (reporta a
        # log; el operador/otra capa decide la acción). Bajo go explícito
        # (LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED) además persiste incidentes
        # durables live_drift por cuenta (P2-01/E2) reusando la misma sesión.
        holder = await _drift_incident_holder(session)
        await _reconcile_open_orders(
            store,
            query_provider=query_provider,
            limit=limit,
            incident_holder=holder,
        )
        # P1-02/E2 — reconcile de POSICIÓN continuo (LR-1) bajo el MISMO go.
        # Fallos aquí no tumban el tick (fail-closed: siguiente tick reintenta).
        try:
            await _reconcile_live_positions_once(session)
        except Exception:  # noqa: BLE001 — defensivo, nunca aborta el ciclo
            logger.exception("live_position reconcile tick failed")
    return result


async def _live_position_reconcile_active() -> bool:
    """Gate P1-02: go del writer durable Y venue efectivo live.

    Sin go o venue no-live → False (sin cambio de runtime por defecto). Venue
    efectivo via ``effective_broker_venue_async`` (runtime ?? redis ?? env).
    """
    from bolsa_application.broker_venue_runtime import effective_broker_venue_async
    from bolsa_application.order_live_drift_incident import (
        live_drift_durable_writer_enabled,
    )

    if not live_drift_durable_writer_enabled():
        return False
    return await effective_broker_venue_async() == "live"


async def _reconcile_live_positions_once(session: AsyncSession) -> None:
    """Una pasada de reconcile de posición: LR-1 vs broker-truth (venue live).

    Solo se ejecuta bajo el go del writer durable (default OFF) y venue efectivo
    live. Compara posiciones/cash locales (``GetPortfolioSummary``) con las del
    bridge live y abre incidentes durables ``live_drift``/``live_unavailable`` por
    cuenta vía ``sync_opening_incidents`` (no auto-heal). Fallos → no rompen tick.
    """
    if not await _live_position_reconcile_active():
        return
    from bolsa_application.accounts.portfolio import GetPortfolioSummary
    from bolsa_application.operational_incident_store import (
        PostgresOperationalIncidentStore,
    )
    from bolsa_application.reconcile_live_ledger import ReconcileLiveLedger
    from bolsa_application.reconcile_live_positions import (
        SyncOpeningIncidentsOpener,
        reconcile_and_open_position_incidents,
    )
    from bolsa_application.reconciliation_opening_gate import (
        HoldingsFromSummary,
        PortfolioCashFromSummary,
        ReconcileLiveLedgerLookup,
        XtbBridgeLiveVenueAdapter,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    # Cuentas activas y repos del resumen local (misma sesión del tick).
    account_repo = SqlAlchemyAccountRepository(session)
    accounts = await account_repo.list_active_accounts()
    ids = [account.id for account in accounts]

    summary = GetPortfolioSummary(
        account_repo,
        SqlAlchemyPortfolioRepository(session),
    )

    from bolsa_infrastructure.config import get_settings

    live = None
    url = (get_settings().xtb_bridge_url or "").strip()
    if url:
        from bolsa_market.providers import XtbBridgeClient

        live = XtbBridgeLiveVenueAdapter(XtbBridgeClient(url))
    uc = ReconcileLiveLedger(
        cash=PortfolioCashFromSummary(summary),
        holdings=HoldingsFromSummary(summary),
        live=live,
    )
    lookup = ReconcileLiveLedgerLookup(uc)

    incident_store = PostgresOperationalIncidentStore(session)
    opener = SyncOpeningIncidentsOpener(incident_store)
    result = await reconcile_and_open_position_incidents(
        ids,
        live_recon=lookup,
        opener=opener,
    )
    logger.info("live_position reconcile (LR-1) %s", result.summary())


async def _drift_incident_holder(
    session: AsyncSession,
) -> Any:
    """Incident store PG para el drift durable, solo si el writer está habilitado.

    Gate ``bajo go`` fail-closed: sin env → None (sin cambio de runtime V2.13).
    """
    from bolsa_application.operational_incident_store import (
        PostgresOperationalIncidentStore,
    )
    from bolsa_application.order_live_drift_incident import (
        live_drift_durable_writer_enabled,
    )

    if not live_drift_durable_writer_enabled():
        return None
    return PostgresOperationalIncidentStore(session)


async def _reconcile_open_orders(
    store: PostgresLiveOrderStore,
    *,
    query_provider: QueryProvider | None,
    limit: int,
    incident_holder: Any | None = None,
) -> None:
    """H7 — consulta open orders vs broker-truth, log-drift (nunca auto-heal).

    Con ``incident_holder`` presente (writer durable habilitado bajo go) convierte
    el drift accionable en incidente durable ``live_drift`` por cuenta.
    """
    from bolsa_application.live_order_machine_reconcile import (
        reconcile_live_order_machine,
    )
    from bolsa_application.order_live_drift_incident import (
        publish_order_live_drifts,
    )

    if query_provider is None:
        # Sin provider real (fail-closed) no hay destino que consultar.
        return
    try:
        report = await reconcile_live_order_machine(
            store,
            query_provider=query_provider,
            limit=limit,
        )
        if report.drifts:
            logger.warning(
                "live_order machine reconcile (H7) drift=%s summary=%s",
                len(report.drifts),
                report.summary(),
            )
        if incident_holder is not None and report.drifts:
            published = await publish_order_live_drifts(
                report,
                holder=incident_holder,
            )
            logger.warning(
                "live_order durable drift (P2-01) publish=%s",
                published.summary(),
            )
    except Exception:  # noqa: BLE001 — una sesión que falle no tumba el tick
        logger.exception("live_order machine reconcile failed")


async def live_order_recovery_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    query_provider: QueryProvider | None = None,
    limit: int = _DEFAULT_BATCH,
    worker_id: str | None = None,
    stale_after_seconds: int = DEFAULT_CLAIM_STALE_SECONDS,
) -> None:
    wid = worker_id or _worker_identity()
    logger.info("LiveOrderRecoveryWorker iniciado (tick=%ss worker=%s)", tick_seconds, wid)
    while True:
        await asyncio.sleep(tick_seconds)
        if not _worker_enabled():
            continue
        try:
            drain = await _drain_once(
                session_factory,
                query_provider=query_provider,
                limit=limit,
                worker_id=wid,
                stale_after_seconds=stale_after_seconds,
            )
            if drain["drained"]:
                logger.info("live_order recovery drain: %s", drain)
        except Exception:  # noqa: BLE001
            logger.exception("live_order recovery tick failed")


def start_live_order_recovery_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    query_provider: QueryProvider | None = None,
    limit: int = _DEFAULT_BATCH,
    worker_id: str | None = None,
) -> asyncio.Task[None] | None:
    if not _worker_enabled():
        logger.info(
            "LiveOrderRecoveryWorker desactivado (%s=false)",
            _ENV_ENABLED,
        )
        return None
    # H6: por defecto el recovery se arranca con el query_provider REAL cuando hay
    # ``XTB_BRIDGE_URL`` configurada (fail-closed sin URL ⇒ ``_no_query_provider``:
    # las filas permanecen UNKNOWN). Callers que necesiten un prov. específico en
    # tests pueden inyectarlo explícitamente.
    effective_query_provider = query_provider
    if effective_query_provider is None:
        from bolsa_infrastructure.config import get_settings

        effective_query_provider = build_live_query_provider(
            bridge_url=get_settings().xtb_bridge_url,
        )
    return asyncio.create_task(
        live_order_recovery_worker_loop(
            session_factory,
            tick_seconds=tick_seconds,
            query_provider=effective_query_provider,
            limit=limit,
            worker_id=worker_id,
        )
    )
