"""Composicion y runtime del worker AUTO (arranque, loop, fuentes y sinks).

Extraido de ``auto_simulation_worker`` con ``Delta motor = 0``. El unico cambio es el
import local de ``AutoSimulationWorker`` en el punto de construccion, para evitar el
ciclo de import (el facade importa este modulo para re-exportarlo).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from bolsa_analytics.cognitive.auto_adaptive import (
    AdaptivePolicy,
)
from bolsa_api.background.auto_price_provider import (
    OhlcvPriceSource,
)
from bolsa_api.background.auto_worker_shared import (  # noqa: F401
    _ACTIVE_STRATEGY_SOURCE_PREFIX,
    _ADOPTION_MIN_STOP_GAP,
    _APPLIED_OUTCOMES,
    _CANONICAL_LEDGER_LIMIT,
    _DURABLE_FACTS_READ_WINDOW,
    _DURABLE_FACTS_RECOVERY_CYCLES,
    _FILL_CHUNKS,
    _MIRRORS_DECLARED,
    _POSITION_JOURNAL_RETRY_CAP,
    _QTY_EPS,
    _SETTLEMENT_FILL_WINDOW,
    _V2_CYCLE_RISK_READ_LIMIT,
    _V2_ENTRY_SOURCE_PREFIX,
    _V2_OPEN_ORDERS_LIMIT,
    _V2_RESERVATIONS_LIMIT,
    ADOPTION_COST_SOURCE_LEDGER,
    ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS,
    ADOPTION_COST_SOURCE_NONE,
    ADOPTION_COST_SOURCE_PROJECTION,
    ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER,
    AUTO_REAL_PRICE_ENV,
    AUTO_SIM_BACKOFF_MAX_SECONDS,
    AUTO_SIM_TICK_BREAKER_FAILURES,
    AUTO_SIM_WORKER_ENABLED,
    CIRCUIT_BREAKER_PAUSED,
    CONTROL_PLANE_STALE,
    DECIDER_REFRESH_FAILED,
    DURABLE_STORES_MISSING,
    JOURNAL_FILL_UNAPPLIED,
    OPERATIVE_DURABLE_SEAMS,
    OPERATOR_INTENT_OFF,
    OPERATOR_INTENT_UNREADABLE,
    TICK_FAILED,
    V2_RESERVATION_GRACE_STAMP_RESOLUTION,
    V2_RESERVATION_GRACE_TURNS,
    WATCH_REFRESH_FAILED,
    BookEquitySnapshot,
    Clock,
    FillObservation,
    PendingExitIntent,
    PriceScript,
    ProtectionConfig,
    TurnReport,
    _AppliedFill,
    _auto_sim_backoff_cap,
    _blend_entry_price,
    _canonical_applied_facts,
    _canonical_entry_prices,
    _canonical_open_attribution,
    _dec_or_none,
    _declare_effective_mirrors,
    _instant,
    _instant_sort_key,
    _mark_observation_changed,
    _open_order_from_fill,
    _protection_config_from_env,
    _Settlement,
    _sim_interval_seconds,
    _strategy_preset_from_source,
    _strategy_version_from_source,
    auto_sim_backoff_seconds,
    auto_sim_breaker_failures,
    default_clock,
    derive_activity,
    flat_price_script,
    logger,
    read_account_book_equity,
    real_price_enabled,
    reservation_grace_window,
    settlement_snapshot_from_fills,
    sim_worker_enabled,
    step_minute_clock,
    turn_equity_from_book,
)
from bolsa_api.background.estudio_watch import SessionScopedEstudioList
from bolsa_api.background.paper_auto_engine_worker import (
    DecisionProvider,
    _watch_from_estudio_enabled,
    _watch_symbols,
    refresh_watch_from_estudio,
    sync_decider_watch,
)
from bolsa_application.applied_fills import read_applied_fill_facts
from bolsa_application.auto_adaptive_journal import (
    AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
)
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    AdaptiveStateReading,
    adaptive_state_unread,
    read_adaptive_state,
)
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading, read_cycle_regimes
from bolsa_application.auto_engine_state_store import (
    AutoEngineLease,
    AutoEngineLeaseLost,
    AutoEngineLeaseStore,
    AutoEngineStore,
)
from bolsa_application.auto_engine_state_store import (
    lease_ttl_seconds as auto_engine_lease_ttl_seconds,
)
from bolsa_application.auto_operational_audit import (
    operational_audit_enabled,
)
from bolsa_application.auto_reason_codes import (
    ACTIVE_SIGNAL_DISABLED,
    LEASE_NOT_HELD,
)
from bolsa_application.auto_v2_entry import (
    AtrSource,
    CatalogTradeContextSource,
    DiscoveryRegimeSource,
    EdgeReportSource,
    tunables_from_env,
)
from bolsa_application.closed_bars import (
    make_closed_bar_loader,
)
from bolsa_application.execution_event import (
    ExecutionEventStore,
)
from bolsa_application.flags import env_finite_float

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.

if TYPE_CHECKING:  # pragma: no cover - solo tipos
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker


# V2.22-env + V2.23/A9 (Bloque 2): cuenta SIM inequívoca para el motor autónomo.
SIM_ACCOUNT_ID = os.getenv("AUTO_ENGINE_SIM_ACCOUNT_ID") or None


# V2.23/A9 (Bloque 2): composición REAL por sesión (scheduler → Worker).
# Patrón ``execution_event_reaper_worker``: la sesión se abre por tick y aquí se
# construyen los stores + finanzas reales sobre ESA sesión.
def _compose_real_stores(
    session: Any,
    *,
    finance_resolver: Any = None,
) -> tuple[
    ExecutionEventStore,
    AutoEngineStore | None,
    Callable[[Any], Awaitable[bool]] | None,
    Any,
]:
    """Construye la composición durable por sesión (exec, auto, finance, contexto).

    * ``exec_store`` = ``PostgresExecutionEventStore`` (captura idempotente por
      ``execution_id`` sobre la sesión abierta del tick).
    * ``auto_store``  = ``PostgresAutoEngineStore`` (Alembic 027, tick durable).
    * ``finance_applier`` = applier SIM real (V2.23/A9, P1-05): reconstruye por
      ``execution_id`` el contexto financiero durable del fill
      (``sim_fill_finance_context``) sin depender de la memoria del worker.
    * ``context_store`` = ``PostgresSimFillFinanceContextStore`` de la sesión, que
      ``_settle`` usa para persistir el contexto de cada fill ANTES de mover dinero.

    Si el caller inyecta un ``finance_resolver`` propio, se respeta; por defecto se
    usa el resolver durable del contexto.
    """
    from bolsa_application.accounts import ExecuteTrade  # noqa: PLC0415
    from bolsa_application.auto_engine_state_store import PostgresAutoEngineStore  # noqa: PLC0415
    from bolsa_application.execution_event import PostgresExecutionEventStore  # noqa: PLC0415
    from bolsa_application.sim_durable_store import (  # noqa: PLC0415
        PostgresSimFillFinanceContextStore,
    )
    from bolsa_application.sim_finance_context import (  # noqa: PLC0415
        build_durable_finance_resolver,
    )
    from bolsa_application.simulated_finance import (  # noqa: PLC0415
        build_simulated_execute_trade_applier,
        require_sim_only_scope,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (  # noqa: PLC0415
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (  # noqa: PLC0415
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (  # noqa: PLC0415
        SqlAlchemyPortfolioRepository,
    )

    exec_store = PostgresExecutionEventStore(session)
    auto_store = PostgresAutoEngineStore(session)
    context_store = PostgresSimFillFinanceContextStore(session)
    resolver = (
        finance_resolver
        if finance_resolver is not None
        else build_durable_finance_resolver(context_store)
    )
    trade = ExecuteTrade(
        SqlAlchemyAccountRepository(session),
        SqlAlchemyPortfolioRepository(session),
        SqlAlchemyLedgerRepository(session),
    )
    # ``build_..._applier(execute_trade, resolver)`` deduce la vía por duck-typing y
    # acepta resolver síncrono o asíncrono (durable). El worker AUTO acuña explícitamente
    # su permiso positivo SIM-only (A8·M0 §7): sin él, el applier que mueve dinero no se
    # construye. El worker NUNCA posee capacidad LIVE.
    applier = build_simulated_execute_trade_applier(
        trade,
        resolver,
        scope=require_sim_only_scope(source="auto_simulation_worker"),
    )
    return exec_store, auto_store, applier, context_store


def build_cycle_regime_sink(session: Any) -> Callable[[Any], Awaitable[None]]:
    """AUTO-10: sink durable del régimen por ciclo, atado a la sesión del tick.

    El repositorio del spine (``decision_journal_entries``, ADR-029 F1) ya existía y solo lo
    usaba la API; aquí se le da el uso que faltaba (``AUTO-10``). Va por sesión, como el resto
    de espejos del turno: el runner abre una sesión por tick y esto se construye sobre ESA.

    Commitea él mismo, a diferencia de ``JournalRepository.append`` (que solo hace ``flush``):
    la sesión del tick se cierra con ``close()``, así que un ``flush`` sin commit dejaría la
    fila sin escribir —el hueco volvería a mentir por omisión, que es justo lo que ``AUTO-10``
    cierra. El commit cae justo después del commit de la reserva de entrada, cuando no hay
    nada más pendiente de otro store en la misma sesión.
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (  # noqa: PLC0415
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)

    async def sink(entry: Any) -> None:
        try:
            await repository.append(entry)
            await session.commit()
        except Exception:
            # Fail-open DE VERDAD: una escritura fallida deja la sesión envenenada y sin
            # ``rollback`` el siguiente store del MISMO turno fallaría con
            # ``PendingRollbackError`` —la traza rota tumbaría el compromiso de capital—.
            # Se limpia aquí y el error sube para que el worker lo DECLARE en el log.
            await session.rollback()
            raise

    return sink


def build_cycle_regime_reader(
    session: Any,
) -> Callable[[Sequence[str]], Awaitable[CycleRegimeReading]]:
    """AUTO-10: lector del régimen por ciclo desde el journal durable de la sesión del tick.

    Es la mitad de lectura del mismo repositorio que usa ``build_cycle_regime_sink``, sobre la
    MISMA sesión del turno. Cierra el circuito ``escribir → leer`` de ``AUTO-10``: la lectura va
    por ``decision_id`` (campo con índice, sin migración) y **confirma** el ``payload['cycleId']``
    antes de creerse un régimen, así que una derivación equivocada solo deja el hueco declarado.
    El coste de la tanda está medido y declarado en ``auto_cycle_regime_reader``.

    Fail-open DECLARADO: si la lectura revienta, el error sube al worker, que lo registra y deja
    los ciclos con su hueco (``regime_not_found``/``regime_not_durable``). El denominador de R,
    que es otra fuente, no se pierde por esto.
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (  # noqa: PLC0415
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)

    async def reader(cycle_ids: Sequence[str]) -> CycleRegimeReading:
        return await read_cycle_regimes(repository.list_by_decision_ids, cycle_ids)

    return reader


def build_adaptive_recommendation_sink(session: Any) -> Callable[[Any], Awaitable[None]]:
    """AUTO-11: sink durable de la recomendación Adaptive, atado a la sesión del tick.

    Mismo repositorio del spine que AUTO-10 y mismo patrón que ``build_cycle_regime_sink``: va por
    sesión (una por tick) y **commitea él mismo**, porque la sesión del turno se cierra con
    ``close()`` y un ``flush`` sin commit dejaría la recomendación sin escribir —el cooldown
    volvería a depender de la memoria—. El ``rollback`` en el fallo no es cosmético: sin él la
    sesión queda envenenada y el siguiente store del MISMO turno fallaría con
    ``PendingRollbackError``, con lo que un fallo de observabilidad tumbaría el compromiso de
    capital.
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (  # noqa: PLC0415
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)

    async def sink(entry: Any) -> None:
        try:
            await repository.append(entry)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return sink


def build_top3_opportunity_sink(
    session: Any,
) -> Callable[[list[Any], str | None], Awaitable[None]]:
    """V2.88.84 — sink durable del TOP3 cross-asset, atado a la sesión del tick.

    Materializa la tabla ``top3_opportunities`` (migración 052): el productor que faltaba en
    la composición real. Mismo patrón que los demás espejos del turno (una sesión por tick,
    commit propio y ``rollback`` en el fallo para no envenenar la sesión). El ``regime`` del
    run llega en la LLAMADA —es propiedad del cómputo, no del slot— y se persiste tal cual
    (``None`` incluido), sin inventar uno. Una lista vacía es un no-op (no se escribe un run
    sin TOP3).
    """
    from bolsa_application.top3_opportunity_store import (  # noqa: PLC0415
        PostgresTop3OpportunitySink,
    )

    async def sink(records: list[Any], regime: str | None) -> None:
        try:
            await PostgresTop3OpportunitySink(session, regime=regime).save(records)
        except Exception:
            await session.rollback()
            raise

    return sink


def build_operational_audit_sink(session: Any) -> Callable[[Any], Awaitable[None]]:
    """AUTO Operational Monitor (``M2``): sink durable de la auditoría operativa.

    Mismo repositorio del spine (``decision_journal_entries``) y mismo patrón que
    ``build_cycle_regime_sink``/``build_adaptive_recommendation_sink``: atado a la sesión del
    tick (una por turno), **commitea él mismo** —la sesión se cierra con ``close()`` y un
    ``flush`` sin commit dejaría la traza sin escribir— y en el fallo hace ``rollback`` para no
    envenenar la sesión del turno. La construcción es **inerte** por defecto: el llamante sólo
    la inyecta tras ``AUTO_OPERATIONAL_AUDIT`` (OFF), de modo que sin flag el turno es byte
    idéntico (Δ = 0).
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (  # noqa: PLC0415
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)

    async def sink(entry: Any) -> None:
        try:
            await repository.append(entry)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return sink





def build_durable_fact_cycle_reader(
    session: Any,
    *,
    account_id: str | None,
    engine_id: str | None,
) -> Callable[[str], Awaitable[frozenset[str]]]:
    """(v2.88.27) lector de los ``cycleId`` que YA tienen un hecho durable de ese ``event_type``.

    Mitad de lectura del MISMO repositorio del spine que ``build_operational_audit_sink`` y con
    la misma sesión del tick. Se acota por cuenta y por motor (``engineId`` en el ``payload``),
    de modo que dos motores de una cuenta no se pisan la deduplicación. Sólo se leen los hechos
    del ``event_type`` pedido (``auto_cycle_settlement`` en la recuperación) y se devuelve el
    conjunto de ``payload['cycleId']``; una entrada sin ciclo no aporta un ciclo inventado.

    Fail-open DECLARADO: si la lectura revienta, el error sube al worker, que lo registra y NO
    reemite nada —reemitir sin saber qué existe seguiría siendo idempotente por la clave, pero
    afirmar "ya está" sin prueba sería el hueco disfrazado—.
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (  # noqa: PLC0415
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)

    async def reader(event_type: str) -> frozenset[str]:
        rows, _total = await repository.list_entries(
            account_id=str(account_id or ""),
            event_type=event_type,
            engine_id=engine_id,
            limit=_DURABLE_FACTS_READ_WINDOW,
        )
        cycles: set[str] = set()
        for row in rows:
            payload = row.payload or {}
            cycle = str(payload.get("cycleId") or "").strip()
            if cycle:
                cycles.add(cycle)
        return frozenset(cycles)

    return reader


def build_adaptive_state_reader(
    session: Any,
    *,
    policy: AdaptivePolicy,
) -> Callable[[str | None], Awaitable[AdaptiveStateReading]]:
    """AUTO-11: lector del estado Adaptive (cooldown/rotación) desde el journal durable.

    Lee las últimas evaluaciones (``adaptive_recommendation``) de la cuenta por índice de
    ``event_type``, no por el ``payload``, y las reconstruye con ``read_adaptive_state``. La
    política EN CURSO entra por parámetro porque la historia se juzga con los umbrales de hoy —y
    se declara la mezcla de versiones en vez de reescribir el pasado—.

    Fail-open DECLARADO: una cuenta ausente devuelve ``adaptive_state_unread`` (contador vacío +
    ``read_ok = False``) en vez de consultar sin filtro; si la lectura revienta, el error sube al
    worker, que lo registra y arranca con el contador vacío declarado.
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (  # noqa: PLC0415
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)

    async def reader(account_id: str | None) -> AdaptiveStateReading:
        account = str(account_id or "").strip()
        if not account:
            # Sin cuenta no hay ``WHERE`` posible: ``list_entries`` exige una y consultar sin
            # filtro traería la historia de OTRA cuenta. Se declara el hueco en vez de arriesgarlo.
            return adaptive_state_unread("no_account", window=ADAPTIVE_STATE_WINDOW_DEFAULT)
        rows, _total = await repository.list_entries(
            account_id=account,
            event_type=AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
            limit=ADAPTIVE_STATE_WINDOW_DEFAULT,
        )
        return read_adaptive_state(
            rows,
            min_pause_cycles=policy.min_pause_cycles,
            running_policy_version=policy.policy_version,
            window=ADAPTIVE_STATE_WINDOW_DEFAULT,
        )

    return reader


def _compose_canonical_reader(session: Any) -> Any:
    """AUTO-1A: lector del estado financiero CANÓNICO = Σ FILLS APLICADOS.

    Devuelve ``account_id -> {symbol: qty}`` derivado del libro de fills
    MATERIALIZADOS (``execution_events(status=APPLIED)`` + ``sim_fill_finance_context``)
    a través del read-model ``PositionLedger`` (``POSITION = Σ APPLIED``).

    Antes leía ``position_state``: la MISMA proyección que debía auditar, de modo que
    una posición inflada por un llenado parcial (p. ej. 100 pedidos con 73,5 aplicados)
    podía "validarse" a sí misma. Ahora la autoridad es el hecho financiero, y la
    proyección ``sim_auto_positions`` vuelve a ser lo que declara ser: un espejo
    reconstruible.

    Fail-closed: si el libro no se puede leer ENTERO (store ausente, error de lectura,
    tope agotado o alguna fila no interpretable), devuelve ``None`` ⇒ el reconciliador
    marca ``UNKNOWN``, veta aperturas y permite salidas protectoras. Nunca devuelve un
    mapa parcial, que haría parecer más pequeña la posición real.
    """
    from bolsa_application.applied_fills import (
        build_canonical_positions,
    )
    from bolsa_application.execution_event import PostgresExecutionEventStore  # noqa: PLC0415
    from bolsa_application.sim_durable_store import (  # noqa: PLC0415
        PostgresSimFillFinanceContextStore,
    )

    async def _read(account_id: str) -> dict[str, Decimal] | None:
        try:
            read = await read_applied_fill_facts(
                PostgresExecutionEventStore(session),
                # ``autocommit=False``: la lectura del libro es SOLO lectura y no debe
                # cerrar la unidad-de-trabajo del tick.
                PostgresSimFillFinanceContextStore(session, autocommit=False),
                account_id,
                limit=_CANONICAL_LEDGER_LIMIT,
            )
        except Exception:  # noqa: BLE001 — sin canónico no se inventa posición.
            logger.exception("auto_sim canonical applied-ledger read failed")
            return None
        if not read.is_complete:
            logger.warning(
                "auto_sim canonical applied-ledger not measurable: measurement=%s "
                "rejected=%s mismatched=%s truncated=%s error=%s (aperturas vetadas)",
                read.measurement,
                read.rejected,
                read.mismatched,
                read.truncated,
                read.error,
            )
            return None
        # ``CanonicalPositions`` es un ``dict``: el seam sigue siendo
        # ``account_id -> {symbol: qty}``, y además viaja con las trazas aplicadas que
        # sustentan cada cantidad (necesarias para reconciliar tras un crash).
        return build_canonical_positions(read)

    return _read


def _compose_regime_source(
    session: Any, *, watch: Sequence[str], as_of: Any, math_version: str | None = None
) -> Any:
    """V2.40.1: régimen REAL del tick (barras del universo → régimen operativo).

    Sin esto, el AUTO en producción corría con régimen ``UNKNOWN`` ⇒ exit-only ⇒ nunca
    abría nada: el motor parecía "prudente" cuando en realidad estaba ciego. El
    ``bars_provider`` lee las últimas barras por símbolo en la MISMA sesión del tick; un
    fallo deja el régimen en ``NO_REGIME`` (⇒ ``UNKNOWN`` ⇒ exit-only), nunca en
    "mercado operable". El override ``AUTO_ENGINE_SIM_V2_REGIME`` sigue teniendo
    prioridad (lo resuelve ``_v2_regime``).

    V2.43/AUTO-3: ``math_version`` permite pedir ``discovery_market_regime_v1`` (añade
    ``low_vol``). Por defecto ``v0`` ⇒ comportamiento y etiquetas de siempre.

    ``W3`` (v2.88.16): las barras se cargan con la **frontera de barras CERRADAS**
    (``as_of`` = día de la última barra cerrada, parámetro OBLIGATORIO). Antes se leían las
    últimas N barras SIN cota, de modo que el régimen veía el ``high``/``low`` de la barra
    EN CURSO: un juicio sobre datos que la barra todavía no había cerrado. Ahora el régimen
    de la barra ``B`` se decide con las barras ``<= B-1``. Sin ``as_of`` resoluble la
    ventana es vacía ⇒ ``NO_REGIME`` (fail-closed), jamás "mercado operable" por defecto.
    """
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (  # noqa: PLC0415
        SqlAlchemyOhlcvRepository,
    )

    loader = make_closed_bar_loader(
        SqlAlchemyOhlcvRepository(session),
        list(watch),
        as_of,
        # Mismo techo de barras que el cargador histórico: W3 mueve la FRONTERA, no el
        # presupuesto de lectura.
        limit=120,
    )
    if math_version is None:
        return DiscoveryRegimeSource(bars_provider=loader)
    return DiscoveryRegimeSource(bars_provider=loader, math_version=math_version)


def _compose_atr_source(session: Any, *, watch: Sequence[str], as_of: Any) -> Any:
    """V2.42 slice 2b (E2): ATR REAL del tick (barras del universo → ATR por símbolo).

    El motor AUTO abría con una geometría sintética (2% del precio) *fabricada en el
    origen*: la intención "ATR real si existe" ya estaba escrita aguas abajo pero el
    worker la anulaba. Esta fuente lee las mismas barras que el régimen, con el MISMO
    loader por sesión, para que la foto de un tick sea una sola.

    Fail-closed: sin barras suficientes el símbolo queda SIN ATR (``atr_source`` lo
    declara) y con ``AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1`` la candidata no entra.

    ``W3`` (v2.88.16): la ventana es la de barras **CERRADAS** (``as_of`` obligatorio), la
    MISMA que la del régimen: el ATR de la barra ``B`` no puede incluir el
    ``high``/``low`` de la barra en curso.
    """
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (  # noqa: PLC0415
        SqlAlchemyOhlcvRepository,
    )

    loader = make_closed_bar_loader(
        SqlAlchemyOhlcvRepository(session),
        list(watch),
        as_of,
        limit=120,
    )
    return AtrSource(bars_provider=loader)


def _compose_price_source(
    session: Any,
    *,
    watch: Sequence[str],
    as_of: Any,
    timeframe: Any = None,
) -> Any:
    """W4 (v2.88.17): precio REAL del tick desde el repositorio de barras.

    Es la fuente que mata el ``100.0`` del simulado. Usa la MISMA sesión y el MISMO
    repositorio que el régimen y el ATR, pero con una frontera DISTINTA: ``as_of`` es el
    **día de la barra CORRIENTE** (``B``), porque de esa ventana sale el ``open(B)`` de la
    ejecución; la decisión (``close(B-1)``) la toma el propio proveedor rebanando la ventana
    (``OhlcvPriceSource``). Fail-closed: sin barra ``B`` el símbolo no tiene precio ⇒ HOLD
    declarado, nunca un ``close(B-1)`` rancio ni un ``100.0``.
    """
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (  # noqa: PLC0415
        SqlAlchemyOhlcvRepository,
    )

    return OhlcvPriceSource(
        SqlAlchemyOhlcvRepository(session),
        list(watch),
        as_of=as_of,
        timeframe=timeframe,
        limit=120,
    )


def _compose_trade_context_source(session: Any) -> Any:
    """V2.40.1: contexto de cartera REAL (sector + ADV + frescura) del catálogo.

    Una sola query por tick (``list_trade_context_by_ids``) sirve tanto el sector del
    candidato como su ADV notional y el instante de observación de los fundamentales.
    """
    from bolsa_infrastructure.database.repositories.instrument_repository import (  # noqa: PLC0415
        SqlAlchemyInstrumentRepository,
    )

    repository = SqlAlchemyInstrumentRepository(session)

    async def _read(symbols: Sequence[str]) -> Mapping[str, Any]:
        return await repository.list_trade_context_by_ids(list(symbols))

    return CatalogTradeContextSource(reader=_read)


def _compose_edge_source(session: Any) -> Any:
    """V2.40.1: edge REAL por versión de estrategia (``EdgeReportRow.edge_score``).

    Sustituye al antiguo ``default_edge = 0.9``: sin informe de edge persistido para la
    versión, la oportunidad NO tiene edge (queda por debajo de ``min_edge`` y no entra).
    Es la parte "fuente real" del fail-closed, no un valor de relleno.
    """
    from bolsa_infrastructure.database.repositories.cognitive_repository import (  # noqa: PLC0415
        SqlAlchemyCognitiveRepository,
    )

    repository = SqlAlchemyCognitiveRepository(session)

    async def _read(strategy_ref: str, account_id: str | None) -> float | None:
        report = await repository.latest_edge_report(
            strategy_or_signal_ref=strategy_ref, account_id=account_id
        )
        return None if report is None else report.edge_score

    return EdgeReportSource(reader=_read)


def _compose_evidence_source(session: Any) -> Any:
    """V2.88 / TOP3 cross-asset: evidencia LAB del campeón ACTIVE por instrumento.

    Carga, para cada instrumento del tick, la estrategia ACTIVE y su último
    ``StrategyEvaluation`` + ``StrategyHealth``; el adapter los convierte en componentes
    de oportunidad (robustness/regime_fit/…). Sin estrategia activa para un instrumento
    no se devuelve entrada ⇒ su scoring queda histórico (solo edge+liquidity). Un fallo
    deja el mapa vacío (fail-closed: nunca se inventa evidencia).
    """
    from bolsa_application.opportunity_evidence_adapter import (  # noqa: PLC0415
        StrategyEvidenceBundle,
        StrategyEvidenceSource,
    )
    from bolsa_application.strategy_lifecycle_store import (  # noqa: PLC0415
        PostgresStrategyLifecycleStore,
    )

    store = PostgresStrategyLifecycleStore(session)

    async def _read(
        symbols: Sequence[str], _regime: str | None
    ) -> Mapping[str, StrategyEvidenceBundle]:
        bundles: dict[str, StrategyEvidenceBundle] = {}
        for symbol in symbols:
            record = await store.get_active(instrument_id=str(symbol))
            if record is None:
                continue
            evaluations = await store.list_evaluations(record.active.candidate_id)
            healths = await store.list_health(record.active.version_id)
            bundles[str(symbol)] = StrategyEvidenceBundle(
                evaluation=evaluations[-1] if evaluations else None,
                health=healths[-1] if healths else None,
            )
        return bundles

    return StrategyEvidenceSource(reader=_read)


def active_strategy_enabled() -> bool:
    """V2.26/A10: ¿el AUTO debe seguir la estrategia ACTIVE? (env, default OFF)."""
    return (os.getenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def active_strategy_signal_enabled() -> bool:
    """V2.29/A10: ¿la ACTIVE evalúa su PROPIA señal? (env, default OFF).

    OFF: la ACTIVE solo aporta lote/watch sobre el spine (comportamiento V2.26-V2.28).
    ON: la ACTIVE evalúa su definición ejecutable sobre barras reales (SignalEvaluator
    real) y es **fail-closed a NO TRADE** (V2.31/A11): si no puede evaluar su señal,
    devuelve HOLD; nunca opera con la lógica de otra estrategia.
    """
    return (os.getenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _signal_snapshot_limit() -> int:
    """Nº de barras a precargar para la señal (env ``AUTO_ENGINE_SIM_SIGNAL_BARS``)."""
    raw = (os.getenv("AUTO_ENGINE_SIM_SIGNAL_BARS") or "").strip()
    if not raw:
        return 120
    try:
        value = int(raw)
    except ValueError:
        return 120
    return value if value > 0 else 120


#: B-1 — de dónde salió la ventana EFECTIVA de la señal (clave aditiva del journal).
SIGNAL_WINDOW_SOURCE_ENV = "env"
SIGNAL_WINDOW_SOURCE_PRESET = "preset_warmup"


def _signal_window(executable: Any, *, env_limit: int) -> tuple[int, int | None, str]:
    """Ventana EFECTIVA de barras: ``(barras, warmup medido | None, origen)``.

    ``AUTO_ENGINE_SIM_SIGNAL_BARS`` deja de ser un TECHO y pasa a ser un **suelo**: la env
    fija el mínimo que el operador quiere precargar, y el warmup del preset (medido sobre la
    serie, no por aritmética de periodos) puede subirlo. Antes el worker pedía la env y el
    preset de SMA200 devolvía siempre un HOLD por warmup: declarado, pero inevitable.

    ``None`` en el warmup significa que **no se pudo medir**; entonces no se inventa una
    ventana: se devuelve la env y el decisor falla cerrado con ``warmup_unmeasurable``. Un
    preset sin series devuelve ``0`` y no sube nada.
    """
    from bolsa_analytics.signals.preset_evaluability import measured_warmup_bars

    warmup = measured_warmup_bars(executable) if isinstance(executable, dict) else None
    if warmup is None:
        return env_limit, None, SIGNAL_WINDOW_SOURCE_ENV
    if warmup > env_limit:
        return warmup, warmup, SIGNAL_WINDOW_SOURCE_PRESET
    return env_limit, warmup, SIGNAL_WINDOW_SOURCE_ENV


async def load_active_strategy_decider(
    session_factory: Any,
    *,
    instrument_id: str | None = None,
    account_id: str | None = None,
    watch: Sequence[str],
    lot_qty: float = 100.0,
    ohlcv: Any = None,
    signal_enabled: bool = False,
    as_of: Any = None,
    long_by_symbol: Callable[[str], bool] | None = None,
) -> DecisionProvider | None:
    """Carga la estrategia ACTIVE del store y la expone vía ``DecisionProvider``.

    V2.26/A10: éste es el ÚNICO punto por el que la estrategia promovida entra en el
    hot path del AUTO. Si no hay estrategia activa, o falla la lectura, devuelve
    ``None`` y el worker sigue con el spine determinista (comportamiento previo a
    V2.31, válido cuando la señal de la ACTIVE está deshabilitada).

    M16 (auditoría .183): el ámbito se declara con el id que TOCA. La cuenta se pide con
    ``account_id`` (``get_active_for_account``) y el instrumento con ``instrument_id``
    (``get_active``); la cuenta NUNCA viaja como si fuera un instrumento. Si llegan los
    dos, manda la cuenta: es el ámbito que conduce el motor. Sin ninguno de los dos es un
    error del llamante, no un ``None`` silencioso.

    V2.29/A10: con ``signal_enabled=True`` la ACTIVE evalúa su PROPIA señal sobre las
    últimas barras (SignalEvaluator real).

    V2.31/A11 (P1-02): con la señal habilitada, el decisor es **fail-closed a NO TRADE**.
    Sin snapshot, sin definición ejecutable o ante error de evaluación, la ACTIVE
    devuelve HOLD; NUNCA hereda la acción de otra estrategia. ``ohlcv`` permite inyectar
    el repo en tests; si es ``None`` se compone por sesión.

    ``W3`` (v2.88.16): ``as_of`` es la **frontera de barras cerradas** que alimenta la
    señal (día de la última barra cerrada, o provider). Es un parámetro EXPLÍCITO: si no
    se declara, la señal se evalúa como antes (sin cota) y eso es un lookahead declarado
    del llamante, no un default escondido del motor.

    ``B-3``: ``long_by_symbol`` es el **libro real**. Sin él, el estado ``gated`` se
    replaya desde el inicio de la ventana y una posición abierta antes de la ventana no
    puede cerrarse (su entrada no está en la ventana). Con él, el estado arranca abierto.
    """
    if not active_strategy_enabled():
        return None
    if account_id is None and instrument_id is None:
        # Error del llamante, declarado ANTES del try: dentro se convertiría en un
        # ``None`` silencioso y el AUTO seguiría sin estrategia por un bug, no por diseño.
        raise ValueError(
            "load_active_strategy_decider necesita account_id o instrument_id: "
            "el ámbito de la ACTIVE no se adivina"
        )
    try:
        from bolsa_application.auto_orchestrator import active_strategy_decider
        from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

        async with session_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            # M16: la cuenta se resuelve por su propia columna; el instrumento por la suya.
            if account_id is not None:
                record = await store.get_active_for_account(account_id=account_id)
            else:
                if instrument_id is None:  # ya validado arriba; estrecha el tipo
                    return None
                record = await store.get_active(instrument_id=instrument_id)
            if record is None:
                return None
            if signal_enabled:
                repo = ohlcv
                if repo is None:
                    from bolsa_api.api.dependencies import get_ohlcv_repository

                    repo = get_ohlcv_repository(session)
                return await _build_signal_decider(
                    record=record,
                    watch=watch,
                    lot_qty=lot_qty,
                    ohlcv=repo,
                    # B-1: sin watch, el símbolo de reserva es el INSTRUMENTO de la
                    # ACTIVE (no la cuenta: pedir barras de una cuenta era el M16).
                    instrument_id=record.active.instrument_id,
                    as_of=as_of,
                    long_by_symbol=long_by_symbol,
                )

        return active_strategy_decider(
            active=record.active,
            fallback=None,
            watch=watch,
            lot_qty=lot_qty,
            # B-5 — sin el flag de señal propia la ACTIVE **no opera** (fail-closed V2.31);
            # aquí es donde se declara POR QUÉ, en vez de devolver un HOLD mudo.
            hold_reason=ACTIVE_SIGNAL_DISABLED,
        )
    except Exception:  # noqa: BLE001 — sin activa fiable se conserva el spine seguro.
        logger.exception("auto_sim active-strategy load failed (se usa el spine)")
        return None


async def _build_signal_decider(
    *,
    record: Any,
    watch: Sequence[str],
    lot_qty: float,
    ohlcv: Any,
    instrument_id: str,
    as_of: Any = None,
    long_by_symbol: Callable[[str], bool] | None = None,
) -> DecisionProvider:
    """Compone el ``DecisionProvider`` con SignalEvaluator real + snapshot de barras.

    El snapshot se carga con la sesión viva del llamante (async) y se cierra sobre el
    decisor síncrono. Cualquier fallo del snapshot se absorbe: el símbolo sin datos
    hará HOLD (fail-closed), nunca se delega en otra estrategia (V2.31/A11).

    ``W3`` (v2.88.16): el snapshot se carga con la frontera de barras CERRADAS cuando el
    llamante declara ``as_of`` (el motor lo hace con ``_v2_closed_bar_as_of``). Con
    ``as_of`` declarado, una ventana vacía (frontera no expresable, p. ej. granularidad
    sub-diaria) deja el símbolo SIN barras ⇒ HOLD: fail-closed, nunca se decide con la
    barra en curso.
    """
    from bolsa_application.active_strategy_signal_evaluator import (
        make_active_strategy_decider,
        make_bar_snapshot_loader,
    )

    symbols = tuple(str(s) for s in (record.active.definition.get("watch") or watch)) or (
        instrument_id,
    )
    # B-1 — la ventana se DIMENSIONA antes de pedir barras: la env es el suelo y el warmup
    # medido del preset puede subirla. Si no se puede medir, el decisor hará HOLD declarado
    # (``warmup_unmeasurable``) en vez de inventar una ventana.
    executable = (getattr(record.active, "definition", None) or {}).get("executable")
    env_limit = _signal_snapshot_limit()
    limit, measured_warmup, window_source = _signal_window(executable, env_limit=env_limit)
    if measured_warmup is None:
        logger.warning(
            "auto_sim signal warmup no medible (preset=%s): la ACTIVE fallará cerrado "
            "con %s y la ventana se queda en %s",
            getattr(record.active, "preset_key", None),
            "warmup_unmeasurable",
            limit,
        )
    elif window_source == SIGNAL_WINDOW_SOURCE_PRESET:
        logger.info(
            "auto_sim signal window raised for preset=%s: env=%s required=%s effective=%s",
            getattr(record.active, "preset_key", None),
            env_limit,
            measured_warmup,
            limit,
        )
    refresh = (
        make_closed_bar_loader(ohlcv, symbols, as_of, limit=limit)
        if as_of is not None
        else make_bar_snapshot_loader(ohlcv, symbols, limit=limit)
    )
    loaded = await refresh()

    def _bars_for(symbol: str) -> list[Any]:
        # Fail-closed: sin snapshot legible no hay barras ⇒ el decisor hace HOLD.
        if not isinstance(loaded, dict):
            return []
        entry = loaded.get(symbol)
        return list(entry) if entry else []

    return make_active_strategy_decider(
        active=record.active,
        watch=watch,
        bars_by_symbol=_bars_for,
        lot_qty=lot_qty,
        long_by_symbol=long_by_symbol,
        signal_window_source=window_source,
    )


async def _runtime_hook(runtime: Any, name: str, *args: Any) -> Any:
    """M7 — invoca un hook de salud del runtime SI existe; un hook roto no tumba el loop.

    Los dobles de test del loop (p. ej. el ``_Runtime`` de la suite del watch) sólo
    implementan ``run_tick``. Exigirles el contrato de salud convertiría una mejora de
    observabilidad en un fallo de arranque, así que el hook es opcional y su excepción
    se declara y se descarta (la salud del motor ya está degradada por definición).
    """
    hook = getattr(runtime, name, None)
    if hook is None:
        return None
    try:
        return await hook(*args)
    except Exception:  # noqa: BLE001 — la salud del motor no puede romper su loop.
        logger.exception("auto_sim runtime hook %s failed", name)
        return None


async def auto_sim_loop(
    runtime: AutoSimRuntime,
    *,
    interval_seconds: float = 60.0,
    decider_refresher: Any = None,
    watch_refresher: Any = None,
) -> None:
    """Task periódica (SIM-ONLY) del scheduler; no avanza si el gate está OFF.

    V2.23/A9 (Bloque 2): cada tick corre ``runtime.run_tick()``, que abre UNA sesión
    de PostgreSQL y compone los stores + finanzas SIM reales sobre ella. El runtime
    conserva el ``AutoSimulationWorker`` entre turnos (estado ``_open`` del día en
    RAM; la materia durable de crash/restart es del Bloque 5). NUNCA arranca un
    ``AutoSimulationWorker()`` desnudo.

    V2.26/A10: ``decider_refresher`` (opcional) es una corrutina que devuelve el
    ``DecisionProvider`` vigente (p. ej. el que sigue la estrategia ACTIVE) y se
    re-evalúa antes de cada tick; ``None`` ⇒ se mantiene el decider actual.

    V2.88.123/S2: ``watch_refresher`` (opcional) refresca el watch diario desde el
    universo ESTUDIO **antes** de resolver el decider y de operar, de modo que todo
    el turno (y los sources que se componen por tick) vean el universo vigente.

    M7 (auditoría .183): un refresco o un turno fallido NO se traga en silencio. El
    fallo se declara al runtime (``note_control_failure`` / ``note_tick_failure``), que
    marca el control plane como NO fresco —vetando APERTURAS mientras dure el fallo— y,
    si el turno falla de forma consecutiva, abre el breaker a ``PAUSED``. El loop deja de
    martillear: el intervalo se duplica por fallo consecutivo (``auto_sim_backoff_seconds``)
    hasta el tope. Los hooks son OPCIONALES (``getattr``) para no romper dobles de test.
    """
    logger.info("AutoSimulationWorker (SIM-ONLY) loop iniciado (tick=%ss)", interval_seconds)
    base = max(0.0, float(interval_seconds))
    failures = 0
    try:
        while True:
            await asyncio.sleep(auto_sim_backoff_seconds(base, failures))
            if not sim_worker_enabled():
                continue
            # V2.88.123/S2: watch (universo ESTUDIO) ANTES del decider, para que el
            # refresco de la estrategia ACTIVE ya vea el universo del turno.
            if watch_refresher is not None:
                try:
                    await watch_refresher()
                except Exception:  # noqa: BLE001 — un refresh fallido no tumba el loop.
                    logger.exception("auto_sim watch refresh failed")
                    await _runtime_hook(runtime, "note_control_failure", WATCH_REFRESH_FAILED)
                else:
                    await _runtime_hook(runtime, "note_control_success", WATCH_REFRESH_FAILED)
            if decider_refresher is not None:
                try:
                    refreshed = await decider_refresher()
                    if refreshed is not None:
                        runtime.set_decider(refreshed)
                except Exception:  # noqa: BLE001 — un refresh fallido no tumba el loop.
                    logger.exception("auto_sim decider refresh failed")
                    await _runtime_hook(runtime, "note_control_failure", DECIDER_REFRESH_FAILED)
                else:
                    await _runtime_hook(runtime, "note_control_success", DECIDER_REFRESH_FAILED)
            try:
                await runtime.run_tick()
            except Exception:  # noqa: BLE001 — un turno no debe tumbar el loop.
                failures += 1
                logger.exception("auto_sim tick failed (fallos consecutivos=%d)", failures)
                paused = await _runtime_hook(runtime, "note_tick_failure", failures)
                if paused is not None:
                    logger.error(
                        "auto_sim circuit breaker: motor PAUSADO tras %d turnos fallidos",
                        failures,
                    )
            else:
                if failures:
                    logger.warning("auto_sim tick recuperado tras %d fallos consecutivos", failures)
                failures = 0
                await _runtime_hook(runtime, "note_tick_success")
    finally:
        # P7 (auditoría .183): el scheduler cancela este task en SIGTERM/SIGINT. Soltar el
        # lease aquí es lo que hace que un reinicio ORDENADO conduzca de inmediato en vez
        # de esperar el TTL (180 s) con el motor parado. El fence no se debilita: sólo se
        # suelta si dueño y generación siguen siendo los de este runtime. Los dobles de
        # test que sólo implementan ``run_tick`` no tienen lease que soltar.
        closer = getattr(runtime, "close", None)
        if closer is not None:
            await closer()


class AutoSimRuntime:
    """Composición real (Bloque 2): scheduler → session_factory → Worker/AUTO.

    Conduce el ``AutoSimulationWorker`` del día abriendo una sesión por tick y
    entregando a ``worker.real_turn`` los stores/account de ESA sesión. El worker
    conserva ``_open``/``_journal`` del día entre turnos en el proceso.
    """

    def __init__(
        self,
        session_factory: Any,
        *,
        worker: AutoSimulationWorker | None = None,
        decider: DecisionProvider | None = None,
        engine_id: str = "auto-sim",
        account_id: str | None = None,
        finance_resolver: Any = None,
        canonical_positions_reader: Any = None,
        regime_source: Any = None,
        trade_context_source: Any = None,
        edge_source: Any = None,
        atr_source: Any = None,
        liquidity_source: Callable[[str], float | None] | None = None,
        # V2.88 / TOP3 cross-asset: evidencia LAB del campeón ACTIVE (inyectable en tests).
        # Con ``None`` (producción) se compone la fuente real por sesión/tick.
        evidence_source: Any = None,
        # W4: fuente de precio inyectable (tests). Con ``None`` (producción) se compone el
        # ``OhlcvPriceSource`` real por sesión/tick, que es lo que mata el ``100.0``.
        price_source: Any = None,
        # P7 (auditoría .183): TTL del lease entre procesos. ``None`` ⇒ se lee del entorno
        # (``AUTO_ENGINE_LEASE_TTL_SECONDS``, default 180 s).
        lease_ttl_seconds: float | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._engine_id = engine_id
        self._account_id = account_id
        self._finance_resolver = finance_resolver
        # V2.40.1: fuentes de dato inyectables. Con ``None`` (producción) se componen por
        # sesión en cada tick (barras, catálogo y EdgeReport); inyectarlas permite que un
        # test controle el dato sin PG.
        self._regime_source = regime_source
        self._trade_context_source = trade_context_source
        self._edge_source = edge_source
        self._atr_source = atr_source
        self._liquidity_source = liquidity_source
        self._evidence_source = evidence_source
        self._price_source = price_source
        # V2.24/A9.1 (P1-01): lector canónico inyectable (por defecto se compone por
        # sesión desde ``position_state``). Sin él, la reconciliación es UNKNOWN.
        self._canonical_reader = canonical_positions_reader
        if worker is None:
            from bolsa_api.background.auto_simulation_worker import (  # noqa: PLC0415
                AutoSimulationWorker,
            )

            worker = AutoSimulationWorker(
                decider=decider,
                engine_id=engine_id,
                account_id=account_id,
                require_account_id=True,
                # M8 (auditoría .183): este runtime conduce la operativa REAL. Sin sus
                # espejos durables el turno se rechaza (``durable_stores_missing``) en vez
                # de operar con la mitad del estado en RAM.
                require_durable_stores=True,
                regime_source=regime_source,
                liquidity_source=liquidity_source,
                trade_context_source=trade_context_source,
                edge_source=edge_source,
                evidence_source=evidence_source,
                atr_source=atr_source,
                price_source=price_source,
            )
        self._worker = worker
        # P7: un único turno a la vez por runtime; ``run_tick`` muta ``_open`` y sustituye
        # stores del worker, así que dos turnos solapados corromperían el estado.
        self._tick_lock = asyncio.Lock()
        # P7 (auditoría .183) — el lock de arriba es INTRA-proceso. Entre procesos arbitra
        # el lease durable de ``auto_engine_runs`` (migración 063): identidad de ESTE
        # proceso, lease vigente y la generación con la que se conduce el motor.
        self._lease_ttl_seconds = (
            lease_ttl_seconds if lease_ttl_seconds is not None else auto_engine_lease_ttl_seconds()
        )
        self._lease_owner = f"auto-sim-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._lease: AutoEngineLease | None = None
        self._lease_generation_seen: int | None = None
        # M7 (auditoría .183) — fallos CONSECUTIVOS del turno y motivo de la pausa. El
        # breaker NO se levanta solo: un motor que revienta tres turnos seguidos necesita
        # que alguien mire. ``resume()`` es la salida explícita del operador.
        self._tick_failure_streak = 0
        self._paused_reason: str | None = None

    @property
    def worker(self) -> AutoSimulationWorker:
        return self._worker

    def set_decider(self, decider: DecisionProvider | None) -> None:
        """V2.26/A10: permite refrescar el ``DecisionProvider`` (estrategia ACTIVE).

        El worker mantiene su estado ``_open``; solo cambia la fuente de propuestas.
        ``None`` es no-op para no dejar el worker sin decider por un refresh vacío.
        """
        if decider is None:
            return
        self._worker._decider = decider  # noqa: SLF001 — seam interno documentado.

    # ---- M7 (auditoría .183): salud del control plane y breaker del turno ----------

    @property
    def paused_reason(self) -> str | None:
        """Motivo del breaker abierto (``None`` = el motor puede conducir turnos)."""
        return self._paused_reason

    @property
    def tick_failure_streak(self) -> int:
        """Fallos consecutivos vistos por este proceso (se reinicia con un turno bueno)."""
        return self._tick_failure_streak

    async def note_control_failure(self, reason: str) -> None:
        """M7 — watch o estrategia dejaron de refrescarse: el turno sigue, las APERTURAS no.

        Cerrar reduce riesgo y debe seguir siendo posible con el último dato bueno; abrir
        con un universo o una estrategia caducados elige un instrumento que este proceso ya
        no está mirando. El token se levanta sólo cuando ese refresco vuelve a funcionar.
        """
        self._worker.mark_control_stale(reason)

    async def note_control_success(self, reason: str) -> None:
        """M7 — ese refresco volvió a funcionar: se retira su token (los demás siguen)."""
        self._worker.clear_control_stale(reason)

    async def note_tick_success(self) -> None:
        """M7 — turno bueno: cierra la racha de fallos y retira el token del turno."""
        if self._tick_failure_streak:
            logger.info(
                "auto_sim turno recuperado tras %d fallos consecutivos engine=%s",
                self._tick_failure_streak,
                self._engine_id,
            )
        self._tick_failure_streak = 0
        self._worker.clear_control_stale(TICK_FAILED)

    async def note_tick_failure(self, streak: int) -> bool:
        """M7 — un turno reventó: se declara, se veta abrir y, por racha, se PAUSA.

        Devuelve ``True`` si ESTE fallo abrió el breaker. El fallo queda en el ledger
        durable (``DEGRADED`` y, al abrir el breaker, ``PAUSED``) para que el monitor y un
        reinicio no lean un motor «sano» que en realidad sólo estaba fallando en silencio.
        """
        self._tick_failure_streak = max(0, int(streak))
        self._worker.mark_control_stale(TICK_FAILED)
        threshold = auto_sim_breaker_failures()
        if threshold <= 0 or self._tick_failure_streak < threshold:
            await self.record_failure_tick("DEGRADED", f"{TICK_FAILED}:{self._tick_failure_streak}")
            return False
        self.pause(f"{CIRCUIT_BREAKER_PAUSED}:{self._tick_failure_streak}")
        await self.record_failure_tick("PAUSED", self._paused_reason or CIRCUIT_BREAKER_PAUSED)
        return True

    def pause(self, reason: str) -> None:
        """M7 — abre el breaker: no se ejecutan turnos hasta ``resume()`` explícito."""
        self._paused_reason = str(reason or CIRCUIT_BREAKER_PAUSED)
        self._worker.mark_control_stale(CIRCUIT_BREAKER_PAUSED)
        self._worker.declare_skip(self._paused_reason)
        logger.error(
            "auto_sim PAUSED por circuit breaker (%s) engine=%s",
            self._paused_reason,
            self._engine_id,
        )

    def resume(self) -> None:
        """M7 — rearma el breaker (decisión del operador, no un reintento automático)."""
        self._paused_reason = None
        self._tick_failure_streak = 0
        self._worker.clear_control_stale(CIRCUIT_BREAKER_PAUSED)
        self._worker.clear_control_stale(TICK_FAILED)

    async def record_failure_tick(self, state: str, reason: str) -> None:
        """M7 — matricula el turno FALLIDO en el ledger durable del motor.

        Antes, una excepción del tick no dejaba rastro durable: el ledger seguía diciendo
        ``RUNNING`` con el último tick bueno y nadie podía distinguir «motor sano» de
        «motor que reventó y el loop lo reintentó». La fila se escribe con el siguiente
        ``seq`` (un turno fallido ES un turno) y ``activity=BLOCKED``.

        Un fallo al persistir no puede tumbar el loop (ya está degradado): se declara.
        """
        try:
            from bolsa_application.auto_engine_state_store import (  # noqa: PLC0415
                AutoEngineTickInput,
                PostgresAutoEngineStore,
            )

            async with self._session_factory() as session:
                store = PostgresAutoEngineStore(session)
                snap = await store.read(self._engine_id)
                seq = (snap.ticks if snap is not None else 0) + 1
                await store.record_tick(
                    AutoEngineTickInput(
                        engine_id=self._engine_id,
                        venue=(snap.venue if snap is not None else "sim"),
                        state=cast(Any, state),
                        seq=seq,
                        proposals=(snap.proposals if snap is not None else 0),
                        vetoes=(snap.vetoes if snap is not None else 0),
                        pending_plans=(snap.pending_plans if snap is not None else 0),
                        last_reason=(reason,),
                        activity="BLOCKED",
                    )
                )
        except Exception:  # noqa: BLE001 — persistir el fallo no puede romper el loop.
            logger.exception(
                "auto_sim no se pudo persistir el turno fallido (%s) engine=%s",
                reason,
                self._engine_id,
            )

    async def run_tick(self) -> TurnReport | None:
        """Un turno real serializado: si ya hay uno en curso, este se omite (no se encola).

        Omitir en vez de esperar evita una cola de turnos sobre barras ya viejas; el
        siguiente tick del loop lo retoma.

        M7: con el breaker abierto (``PAUSED``) el turno NI se intenta. Reintentarlo a
        ciegas es lo que convertía un fallo repetido en un martilleo silencioso.
        """
        if self._paused_reason is not None:
            logger.warning(
                "auto_sim tick bloqueado por circuit breaker (%s) engine=%s",
                self._paused_reason,
                self._engine_id,
            )
            self._worker.declare_skip(self._paused_reason)
            return None
        if self._tick_lock.locked():
            logger.warning(
                "auto_sim tick omitido: turno anterior aún en curso engine=%s", self._engine_id
            )
            return None
        async with self._tick_lock:
            try:
                return await self._run_tick_unlocked()
            except AutoEngineLeaseLost:
                # P7 — el fence rechazó la escritura porque otro proceso pasó a conducir el
                # motor. El turno se DESCARTA (no se reintenta a ciegas): el siguiente tick
                # re-adquiere lease, y si la generación cambió, readopta la posición.
                logger.warning(
                    "auto_sim tick descartado: el lease cambió de dueño engine=%s",
                    self._engine_id,
                )
                self._lease = None
                return None

    async def _hold_lease(self, store: AutoEngineLeaseStore) -> AutoEngineLease | None:
        """Renueva el lease de ESTE proceso para el motor, o lo adquiere si lo perdió.

        El lease es lo que arbitra entre procesos: renovarlo antes de cada ciclo mantiene
        la exclusividad mientras el proceso conduce, y ``None`` significa que otro proceso
        pasó a ser el dueño (lease vencido y reclamado, o soltado). En ese caso NO se
        ejecuta el ciclo: es exactamente la carrera que P7 cierra.

        Deja anotada la generación vigente: si cambió respecto de la última vista, exige
        readoptar la posición (la RAM de este proceso dejó de ser la verdad).
        """
        if self._lease is not None:
            renewed = await store.renew_lease(self._lease, ttl_seconds=self._lease_ttl_seconds)
            if renewed is not None:
                self._lease = renewed
                self._note_lease_generation(renewed)
                return renewed
            logger.warning(
                "auto_sim lease perdido: otro proceso conduce el motor engine=%s", self._engine_id
            )
            self._lease = None
        lease = await store.acquire_lease(
            self._engine_id, owner=self._lease_owner, ttl_seconds=self._lease_ttl_seconds
        )
        self._lease = lease
        if lease is not None:
            self._note_lease_generation(lease)
        return lease

    def _note_lease_generation(self, lease: AutoEngineLease) -> None:
        """P7 — si la generación del lease cambió, la RAM dejó de ser la verdad.

        El dueño anterior pudo abrir/cerrar posiciones antes de morir. Este proceso
        reconstruye ``_open`` desde ``sim_auto_positions`` (``readopt_positions``) en vez
        de heredar una memoria que ya no le corresponde.
        """
        previous = self._lease_generation_seen
        self._lease_generation_seen = lease.generation
        if previous is not None and previous != lease.generation:
            logger.warning(
                "auto_sim lease generation cambió (%s → %s): se readopta posición engine=%s",
                previous,
                lease.generation,
                self._engine_id,
            )
            self._worker.require_position_readopt()

    async def close(self) -> None:
        """Suelta el lease al apagar ORDENADAMENTE (no en un crash).

        Sin esto, un reinicio espera el TTL completo (180 s por defecto) aunque el dueño
        anterior se apagó limpiamente: el lease arbitra entre procesos VIVOS, no castiga
        un apagado ordenado. La valla no se debilita: ``release_lease`` sólo suelta si
        dueño Y generación siguen siendo los de este runtime, así que un ``close()`` de
        un proceso que ya perdió el lease es un no-op (y la generación no retrocede).
        """
        lease, self._lease = self._lease, None
        if lease is None:
            return
        from bolsa_application.auto_engine_state_store import (  # noqa: PLC0415
            PostgresAutoEngineStore,
        )

        try:
            async with self._session_factory() as session:
                await PostgresAutoEngineStore(session).release_lease(lease)
        except Exception:  # noqa: BLE001 — apagar nunca debe romperse por el lease.
            logger.exception(
                "auto_sim lease release falló al apagar (se deja vencer) engine=%s",
                self._engine_id,
            )

    async def _operator_intent_blocks_turn(self, session: Any) -> bool:
        """M10 (auditoría .183) — ¿una intención durable ``OFF`` impide este turno?

        Se lee ANTES de componer stores o tocar la cartera. Un ``OFF`` explícito gana al
        env: sin esta lectura, un reinicio con ``AUTO_SIMULATION_WORKER_ENABLED=1`` volvía
        a arrancar un motor que el operador había apagado.

        La AUSENCIA de fila NO es ``OFF``: el operador no declaró intención y el env
        decide. Devolver ``True`` ahí apagaría motores que hoy funcionan, que es inventar
        una decisión que nadie tomó.

        La lectura es fail-closed ante excepción: si el store no puede responder no se
        conduce el turno (mismo criterio que el resto de espejos durables).
        """
        from bolsa_application.auto_engine_intent_store import (  # noqa: PLC0415
            PostgresAutoEngineIntentStore,
        )

        try:
            intent = await PostgresAutoEngineIntentStore(session).load(
                self._account_id or "", self._engine_id
            )
        except Exception:  # noqa: BLE001 — sin lectura no hay permiso para operar.
            logger.exception(
                "auto_sim: intención durable ilegible; turno omitido engine=%s",
                self._engine_id,
            )
            self._worker.declare_skip(OPERATOR_INTENT_UNREADABLE)
            return True
        if intent is None or not intent.is_off:
            return False
        logger.warning(
            "auto_sim tick omitido: intención durable OFF cuenta=%s engine=%s actor=%s motivo=%s",
            self._account_id or "-",
            self._engine_id,
            intent.actor or "-",
            intent.reason or "-",
        )
        self._worker.declare_skip(OPERATOR_INTENT_OFF)
        return True

    async def _run_tick_unlocked(self) -> TurnReport | None:
        """Un turno real: abre sesión, compone stores PG + finanzas, y lo conduce.

        Cada tick compone también el espejo durable de posición (``sim_auto_positions``,
        Bloque 5/P1-06) sobre la MISMA sesión. En el primer tick del proceso,
        ``real_turn`` readopta la posición durable (G7: no segundo BUY tras crash);
        los ticks siguientes ya operan con ``_open`` en memoria + espejo por cambio.
        """
        from bolsa_application.reservation_store import (  # noqa: PLC0415
            PostgresReservationStore,
        )
        from bolsa_application.sim_durable_store import (  # noqa: PLC0415
            PostgresSimAutoPositionStore,
            PostgresSimConsumedSignalStore,
        )

        async with self._session_factory() as session:
            # M10 (auditoría .183) — la INTENCIÓN durable del operador se lee ANTES de
            # componer stores o tocar la cartera (ver ``_operator_intent_blocks_turn``).
            if await self._operator_intent_blocks_turn(session):
                return None
            exec_store, auto_store, applier, context_store = _compose_real_stores(
                session,
                finance_resolver=self._finance_resolver,
            )
            position_store = PostgresSimAutoPositionStore(session)
            # AUTO 2.0 · P4: las señales consumidas también sobreviven al reinicio
            # (misma sesión, commit propio): un crash no reabre la MISMA oportunidad
            # sobre la MISMA barra.
            consumed_signal_store = PostgresSimConsumedSignalStore(session)
            # AUTO-1b: el libro durable de RESERVAS, sobre la misma sesión del tick. Es
            # la autoridad de ``reserved_cash``/``pending_risk`` entre ticks; con
            # ``autocommit=True`` (default) cada alta queda durable ANTES de emitir la
            # orden, de modo que un crash inmediato no pierde el compromiso.
            reservation_store = PostgresReservationStore(session)
            # V2.43.3 (P0-1/P0-2): los dos espejos durables nuevos, sobre la misma sesión.
            # ``kill_switch_store`` hace que la parada dura sobreviva al reinicio;
            # ``exit_order_store`` da identidad duradera a cada salida.
            from bolsa_application.exit_order_store import (  # noqa: PLC0415
                PostgresExitOrderStore,
            )
            from bolsa_application.kill_switch_store import (  # noqa: PLC0415
                PostgresKillSwitchStore,
            )

            kill_switch_store = PostgresKillSwitchStore(session)
            exit_order_store = PostgresExitOrderStore(session)
            # AUTO-10: la traza DURABLE del régimen por ciclo, sobre la misma sesión del tick.
            cycle_regime_sink = build_cycle_regime_sink(session)
            cycle_regime_reader = build_cycle_regime_reader(session)
            # AUTO-11: la recomendación Adaptive durable y su lector, también sobre la MISMA
            # sesión. Con el flag Adaptive OFF el worker no los usa: cero I/O nuevo.
            adaptive_sink = build_adaptive_recommendation_sink(session)
            # AUTO Operational Monitor (``M2``): el sink de auditoría operativa se construye
            # SÓLO tras el flag ``AUTO_OPERATIONAL_AUDIT`` (OFF por defecto). Con él apagado la
            # costura es inerte (Δ = 0) y el monitor declara sus huecos ``NO MEDIDO``.
            operational_audit_sink = (
                build_operational_audit_sink(session) if operational_audit_enabled() else None
            )
            # v2.88.27 — el LECTOR de deduplicación, también tras el flag: sin auditoría no hay
            # hechos que recuperar (y sin él el arranque no toca el spine: Δ = 0).
            durable_fact_cycle_reader = (
                build_durable_fact_cycle_reader(
                    session,
                    account_id=self._account_id,
                    engine_id=self._worker._engine_id,  # noqa: SLF001 — seam interno.
                )
                if operational_audit_enabled()
                else None
            )
            adaptive_reader = build_adaptive_state_reader(
                session,
                policy=self._worker._v2_adaptive_policy(),  # noqa: SLF001 — seam interno.
            )
            # AUTO-15: la racha de fallos del sink como estado DURABLE, sobre la MISMA sesión.
            # Con el flag Adaptive OFF nadie la escribe ni la lee: cero I/O nuevo.
            from bolsa_application.adaptive_gate_store import (  # noqa: PLC0415
                PostgresAdaptiveGateStore,
            )

            adaptive_gate_store = PostgresAdaptiveGateStore(session)
            # V2.88.84 — el TOP3 cross-asset (``top3_opportunities``, migración 052): la foto
            # durable de «qué 3 oportunidades ha rankeado AUTO y por qué», sobre la MISMA sesión del tick.
            # Cierra el hueco de ``v2.88.82`` (cadena probada pero sin productor cableado).
            top3_opportunity_sink = build_top3_opportunity_sink(session)
            # Handoff durable ESTUDIO → AUTO (migración 058): el lector de propuestas
            # pendientes y el sumidero de desenlaces, sobre la MISMA sesión del tick. El
            # productor adopta la identidad del parte y la sella en el ciclo; sin esto la
            # cadena solo podría "cuadrar" por símbolo (una inferencia, no una prueba).
            from bolsa_application.estudio_daily_proposals import (  # noqa: PLC0415
                LoadAdoptableDailyProposals,
                RecordDailyProposalOutcomes,
                record_outcomes_in_savepoint,
            )
            from bolsa_infrastructure.database.repositories.estudio_daily_proposal_repository import (  # noqa: PLC0415, E501
                SqlAlchemyEstudioDailyProposalRepository,
            )

            # Lectura: un fallo no debe escribir nada, así que el repo del loader conserva el
            # autocommit histórico. Sumidero (O-2): ``autocommit=False`` porque el desenlace va
            # en un SAVEPOINT y lo commitea el helper; un ``commit`` dentro del savepoint lo
            # cerraría en falso.
            proposal_repository = SqlAlchemyEstudioDailyProposalRepository(session)
            proposal_loader = LoadAdoptableDailyProposals(proposal_repository)
            proposal_outcomes = RecordDailyProposalOutcomes(
                SqlAlchemyEstudioDailyProposalRepository(session, autocommit=False)
            )

            async def _daily_proposal_sink(
                outcomes: list[dict[str, Any]],
            ) -> Any:
                """Sella el desenlace aislado en un SAVEPOINT (no aborta la sesión del tick)."""
                return await record_outcomes_in_savepoint(
                    session, proposal_outcomes.execute, outcomes
                )

            async def _daily_proposal_source(
                account_id: str,
                decision_bar_day: str,
                instruments: Sequence[str],
            ) -> Any:
                """Propuestas adoptables para la frontera de decisión del tick."""
                return await proposal_loader.execute(
                    account_id=account_id,
                    instruments=instruments,
                    decision_bar_day=decision_bar_day,
                )

            # v2.88.70: la equity del turno es la del libro. Si falla, las aperturas
            # quedan vetadas dentro de ``auto_turn``. No se sustituye por 100_000.
            await self._worker.load_book_equity(session)
            # P7/P8 (auditoría .183) — exclusividad entre PROCESOS y claim por barra lógica,
            # ANTES de tocar la cartera. Sin lease vigente o con la barra ya reclamada, este
            # proceso no ejecuta el ciclo (no se inventa un turno que otro ya conduce).
            if auto_store is None:  # pragma: no cover — el runtime real siempre lo compone.
                logger.error("auto_sim tick sin store durable engine=%s", self._engine_id)
                return None
            lease_store = cast(AutoEngineLeaseStore, auto_store)
            lease = await self._hold_lease(lease_store)
            if lease is None:
                logger.warning(
                    "auto_sim tick omitido: otro proceso posee el lease engine=%s",
                    self._engine_id,
                )
                self._worker.declare_skip(LEASE_NOT_HELD)
                return None
            self._note_lease_generation(lease)
            logical_bar = self._worker._v2_current_bar_start()  # noqa: SLF001 — seam interno.
            claim = await lease_store.claim_cycle(
                self._engine_id, logical_bar=logical_bar, lease=lease
            )
            if claim is None:
                logger.info(
                    "auto_sim ciclo ya reclamado para la barra %s engine=%s",
                    logical_bar or "(sin barra)",
                    self._engine_id,
                )
                return None
            # AUTO 2.0 · V2.40.1: fuentes de DATO reales del tick sobre la misma sesión.
            # Antes no se cableaba ninguna ⇒ régimen UNKNOWN (exit-only) y sector/edge
            # inexistentes; el AUTO "parecía prudente" estando a ciegas. Ahora el motor
            # decide con barras, catálogo y EdgeReport; si el dato falta, veta (no asume).
            return await self._worker.real_turn(
                exec_store=exec_store,
                auto_store=auto_store,
                finance_applier=applier,
                account_id=self._account_id,
                context_store=context_store,
                position_store=position_store,
                consumed_signal_store=consumed_signal_store,
                reservation_store=reservation_store,
                kill_switch_store=kill_switch_store,
                exit_order_store=exit_order_store,
                cycle_regime_sink=cycle_regime_sink,
                cycle_regime_reader=cycle_regime_reader,
                operational_audit_sink=operational_audit_sink,
                durable_fact_cycle_reader=durable_fact_cycle_reader,
                adaptive_sink=adaptive_sink,
                adaptive_reader=adaptive_reader,
                adaptive_gate_store=adaptive_gate_store,
                canonical_positions_reader=self._canonical_reader
                or _compose_canonical_reader(session),
                regime_source=self._regime_source
                or _compose_regime_source(
                    session,
                    watch=tuple(_watch_symbols()),
                    # W3: frontera de barras CERRADAS (B-1). El provider lee el reloj del
                    # worker en cada refresco, así que el turno siguiente mueve la frontera
                    # sin recomponer nada (una sola composición por sesión/tick).
                    as_of=self._worker._v2_closed_bar_as_of,  # noqa: SLF001 — seam interno.
                    math_version=tunables_from_env().regime_math_version,
                ),
                trade_context_source=self._trade_context_source
                or _compose_trade_context_source(session),
                edge_source=self._edge_source or _compose_edge_source(session),
                # V2.88 / TOP3 cross-asset: evidencia del campeón ACTIVE por instrumento.
                # Sin fuente inyectada se compone la real por sesión (fail-closed: un
                # fallo de lectura deja el scoring histórico, no una evidencia inventada).
                evidence_source=self._evidence_source or _compose_evidence_source(session),
                # V2.88.84 — productor durable del TOP3 cross-asset (tabla 052), misma sesión.
                top3_opportunity_sink=top3_opportunity_sink,
                # Handoff durable ESTUDIO → AUTO (058): la propuesta del parte manda en la
                # identidad del plan/ciclo; el desenlace se sella con el ``cycle_id``.
                daily_proposal_source=_daily_proposal_source,
                daily_proposal_sink=_daily_proposal_sink,
                atr_source=self._atr_source
                or _compose_atr_source(
                    session,
                    watch=tuple(_watch_symbols()),
                    as_of=self._worker._v2_closed_bar_as_of,  # noqa: SLF001 — seam interno.
                ),
                # W4: precio REAL del tick, **tras el interruptor declarado**
                # (``AUTO_ENGINE_SIM_REAL_PRICE``, default OFF ⇒ costura inerte, Δ = 0). Con
                # el flag ON, la frontera es la de EJECUCIÓN (día de la barra corriente
                # ``B``), distinta de la de régimen/ATR (``B-1``): de aquí sale el ``open(B)``
                # del fill; el proveedor rebanar la ventana para el ``close(B-1)`` de la
                # decisión. Es lo que mata el ``100.0`` plano.
                price_source=self._price_source
                or (
                    _compose_price_source(
                        session,
                        watch=tuple(_watch_symbols()),
                        as_of=self._worker._v2_current_bar_day,  # noqa: SLF001 — seam interno.
                        timeframe=self._worker._v2_granularity.decision.timeframe,  # noqa: SLF001
                    )
                    if real_price_enabled()
                    else None
                ),
                # P7/P8: el turno liquida el ciclo RECLAMADO y escribe bajo la valla del
                # lease con el que se conduce el motor.
                cycle_claim=claim,
                lease=lease,
            )


class _HermeticRuntime:
    """Adapter para un ``worker`` inyectado sin PG (uso en tests/hermético)."""

    def __init__(self, worker: AutoSimulationWorker) -> None:
        self._worker = worker

    async def run_tick(self) -> None:
        await self._worker.auto_turn()

    async def close(self) -> None:
        """Sin lease durable no hay nada que soltar (contrato paralelo a ``AutoSimRuntime``)."""


def _default_spine_decider() -> DecisionProvider:
    """Spine determinista (Bloque 4) cuando ``AUTO_ENGINE_SIM_SPINE_AUTO=1``.

    Default fail-closed: spins OFF ⇒ el spine devuelve HOLD para todo (no propone
    nunca una ejecución SIM por defecto). Activarlo es una decisión explícita del
    operador (solo SIM, SIM-ONLY); el RiskGate sigue teniendo la última autoridad.
    """
    from bolsa_application.auto_decision_engine import deterministic_auto_decider

    watch = tuple(_watch_symbols())
    enabled = (os.getenv("AUTO_ENGINE_SIM_SPINE_AUTO") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    lot = env_finite_float("AUTO_ENGINE_SIM_LOT_QTY", default=100.0, minimum=0.0)
    if lot is None or lot <= 0:
        lot = 100.0
    # V2.24.2 (P2-D): retén configurable para poder certificar un restart con la
    # posición ABIERTA (default 3 = comportamiento histórico).
    try:
        exit_after_ticks = int(os.getenv("AUTO_ENGINE_SIM_EXIT_AFTER_TICKS") or "3")
    except ValueError:
        exit_after_ticks = 3
    if exit_after_ticks <= 0:
        exit_after_ticks = 3
    return deterministic_auto_decider(
        watch,
        lot_qty=lot,
        exit_after_ticks=exit_after_ticks,
        enabled=enabled,
    )


def _sim_engine_id(default: str = "auto-sim") -> str:
    """V2.24/A9.1 (P2-04): engine_id configurable por env (aislamiento/telemetría).

    Permite que un despliegue y una prueba Reina aíslen su ledger de ticks
    (``auto_engine_ticks``) sin compartir el engine por defecto.
    """
    raw = (os.getenv("AUTO_ENGINE_SIM_ENGINE_ID") or "").strip()
    return raw or default


class EngineIdentityMissingError(RuntimeError):
    """R-4 — el arranque durable no puede identificar al motor (variable ausente).

    Es un ``RuntimeError`` a propósito (un despliegue roto debe verse), pero el scheduler
    la captura para acotar el daño: AUTO queda apagado y el resto de workers arranca.
    """


def _durable_sim_engine_id() -> str:
    """R-4 (verificación 2026-10-26 §8) — identidad de motor OBLIGATORIA en durable.

    Con composición PG, dos procesos que caigan al default ``auto-sim`` comparten las
    mismas filas de proyección/latch y la reconciliación deja de identificar al motor.
    El arranque durable exige la variable explícita y falla con un mensaje accionable; el
    constructor hermético conserva su default (Δ = 0 fuera de la ventana durable).

    El fallo es ``EngineIdentityMissingError`` (subclase de ``RuntimeError``) para que el
    scheduler pueda ACOTARLO: este proceso no arranca el motor AUTO, pero no se lleva por
    delante los demás workers (ver ``scheduler_worker._start_workers``).
    """
    raw = _sim_engine_id(default="")
    if not raw:
        raise EngineIdentityMissingError(
            "AUTO_ENGINE_SIM_ENGINE_ID es obligatorio para arrancar el motor AUTO "
            "durable (composición PG): sin identidad explícita de motor la proyección y "
            "el latch de la parada no identifican a este proceso. Defina la variable "
            "(p. ej. AUTO_ENGINE_SIM_ENGINE_ID=auto-sim-prod-1) o arranque el camino "
            "hermético con un worker inyectado."
        )
    return raw


def start_auto_sim_worker(
    session_factory: Any = None,
    *,
    worker: AutoSimulationWorker | None = None,
    decider: DecisionProvider | None = None,
    interval_seconds: float = 60.0,
    engine_id: str | None = None,
    account_id: str | None = None,
    finance_resolver: Any = None,
    regime_source: Any = None,
    trade_context_source: Any = None,
    edge_source: Any = None,
    liquidity_source: Callable[[str], float | None] | None = None,
    evidence_source: Any = None,
    # V2.88.123/S2: puerto ESTUDIO inyectable (tests). Con ``None`` y el flag ON se
    # compone el puerto session-scoped real desde ``session_factory``.
    estudio_list: Any = None,
) -> asyncio.Task[None] | None:
    """start hook para ``_event_loop_starters()`` (env-gated; default OFF, SIM).

    V2.22 bug (P1-01): arrancaba ``AutoSimulationWorker()`` desnudo (sin exec_store/
    auto_store/decider/finance) y el camino autónomo real nunca liquidaba. V2.23
    (Bloque 2): con ``session_factory`` compone un ``AutoSimRuntime`` real con
    ``PostgresExecutionEventStore``/``AutoEngineStore``/finanzas SIM por sesión.
    El decider por defecto es el Spine determinista (Bloque 4), seguro (HOLD a menos
    que ``AUTO_ENGINE_SIM_SPINE_AUTO=1``). Sin ``session_factory`` (uso unit/hermético)
    permite seguir con un ``worker`` inyectado (p.ej. con ``InMemoryExecutionEventStore``).

    R-4 (verificación 2026-10-26 §8): con composición durable, la ausencia de
    ``AUTO_ENGINE_SIM_ENGINE_ID`` (y sin ``engine_id`` explícito) RAISE
    ``EngineIdentityMissingError``. El scheduler acota el fallo a este worker
    (``_start_workers``): AUTO queda apagado y el resto de crons arranca. Un arranque
    directo (script/prueba) sigue viendo el fallo explícito.
    """
    if not sim_worker_enabled():
        logger.info(
            "AutoSimulationWorker (%s) desactivado — SIM-ONLY por defecto.", AUTO_SIM_WORKER_ENABLED
        )
        return None
    # La configuración efectiva se DECLARA al arrancar: qué interruptores están on/off y con
    # qué números. Antes, el gobernador/ATR/precio-real nacían apagados sin decirlo.
    from bolsa_api.auto_runtime import auto_runtime_snapshot

    runtime_flags = auto_runtime_snapshot()
    logger.info(
        "AUTO runtime: worker=%s v2=%s realPrice=%s governor=%s atrRequired=%s "
        "accountMaxDD=%s engineId=%s",
        runtime_flags["workerEnabled"],
        runtime_flags["v2Enabled"],
        runtime_flags["realPrice"],
        runtime_flags["governorEnabled"],
        runtime_flags["atrRequired"],
        runtime_flags["accountMaxDrawdownPct"],
        runtime_flags["engineId"],
    )
    for runtime_warning in runtime_flags["warnings"]:
        if not str(runtime_warning).startswith("AUTO apagado"):
            logger.warning("AUTO runtime: %s", runtime_warning)
    runtime: Any
    # V2.26/A10: refresco opcional del decider desde la estrategia ACTIVE (env-gated).
    decider_refresher: Any = None
    # V2.88.123/S2: refresco opcional del watch desde ESTUDIO (env-gated, default OFF).
    watch_refresher: Any = None
    if session_factory is None:
        # Sin composición PG no creamos un runtime "real"; degradamos al worker
        # inyectado (tests/hermético) o construimos uno SOLO si viene cableado.
        if worker is None:
            logger.warning(
                "auto_sim_worker sin session_factory y sin worker: no se arranca "
                "ningún runtime (evita un AutoSimulationWorker() desnudo)."
            )
            return None
        runtime = _HermeticRuntime(worker)  # helper local definido abajo
    else:
        effective_account = account_id or SIM_ACCOUNT_ID
        # V2.24/A9.1 (P1-04): AUTO SIM exige cuenta inequívoca. Sin cuenta NO se
        # arranca el motor durable (fail-closed): jamás una traza con account_id=None.
        if not effective_account:
            logger.error(
                "auto_sim_worker habilitado pero SIN cuenta SIM inequívoca "
                "(%s / AUTO_ENGINE_SIM_ACCOUNT_ID): NO se arranca el motor AUTO "
                "(fail-closed).",
                "account_id",
            )
            return None
        # El spine determinista fija su ``watch`` al componerse; lo capturamos para
        # poder alinearlo por tick cuando el flag ESTUDIO esté ON (V2.88.123/S2).
        spine_decider = decider if decider is not None else _default_spine_decider()
        # R-4 (verificación 2026-10-26 §8) — con composición PG la identidad del motor es
        # obligatoria: un default silencioso ``auto-sim`` comparte filas entre procesos.
        durable_engine_id = engine_id or _durable_sim_engine_id()
        runtime = AutoSimRuntime(
            session_factory,
            worker=worker,
            decider=spine_decider,
            engine_id=durable_engine_id,
            account_id=effective_account,
            finance_resolver=finance_resolver,
            regime_source=regime_source,
            trade_context_source=trade_context_source,
            edge_source=edge_source,
            liquidity_source=liquidity_source,
            evidence_source=evidence_source,
        )
        # V2.88.123/S2: refresco del watch (universo ESTUDIO) por tick, solo con el
        # flag ON. Con OFF es ``None`` ⇒ byte-idéntico (no toca la BD).
        watch_refresher = _compose_watch_refresher(
            estudio_list if estudio_list is not None else SessionScopedEstudioList(session_factory),
            spine_decider,
        )
        # V2.26/A10: solo con runtime PG real y sin decider inyectado; el seam es el
        # ``DecisionProvider`` (no se toca RiskGate/SimulationGate ni se abre LIVE).
        if decider is None and active_strategy_enabled():

            async def _refresh_active_decider() -> DecisionProvider | None:
                return await load_active_strategy_decider(
                    session_factory,
                    # M16 (auditoría .183): el runtime conduce una CUENTA; se pide como
                    # cuenta (``get_active_for_account``), nunca pasándola por instrumento.
                    account_id=effective_account,
                    # V2.88.123/S2: con el flag ON el universo ACTIVE sigue a ESTUDIO
                    # (cache vigente); con OFF, el CSV histórico ``AUTO_ENGINE_SIM_WATCH``.
                    watch=_active_decider_watch(),
                    signal_enabled=active_strategy_signal_enabled(),
                    # W3: la señal se evalúa con las barras CERRADAS hasta la barra anterior
                    # (provider sobre el reloj del worker: el refresco es previo al turno,
                    # así que la frontera va como mínimo un tick por detrás del reloj vivo
                    # — estrictamente conservador, jamás por delante).
                    as_of=runtime.worker._v2_closed_bar_as_of,  # noqa: SLF001 — seam interno.
                    # B-3: el estado `gated` viene del LIBRO REAL, no de un replay de la
                    # ventana. Se pasa como callable para que lea la posición en el
                    # instante de decidir —el libro cambia dentro del turno—.
                    long_by_symbol=runtime.worker.holds_long,
                )

            decider_refresher = _refresh_active_decider
    return asyncio.create_task(
        auto_sim_loop(
            runtime,
            interval_seconds=_sim_interval_seconds(interval_seconds),
            decider_refresher=decider_refresher,
            watch_refresher=watch_refresher,
        )
    )


def _active_decider_watch() -> tuple[str, ...]:
    """Watch del decider de la estrategia ACTIVE (V2.88.123/S2).

    Con el flag ``..._WATCH_FROM_ESTUDIO`` ON, el universo ESTUDIO vigente (cache
    refrescada por tick); con OFF, el CSV histórico ``AUTO_ENGINE_SIM_WATCH``
    exactamente como antes (byte-idéntico).
    """
    if _watch_from_estudio_enabled():
        return tuple(_watch_symbols())
    return tuple(
        s.strip() for s in (os.getenv("AUTO_ENGINE_SIM_WATCH") or "").split(",") if s.strip()
    )


def _compose_watch_refresher(estudio_list: Any, spine_decider: Any) -> Any:
    """Compone el refresco del watch desde ESTUDIO (V2.88.123/S2) o ``None``.

    Con el flag OFF es ``None`` ⇒ ``auto_sim_loop`` no toca la BD (byte-idéntico).
    Con ON resuelve el universo por tick y alinea el ``watch`` del spine determinista
    (que fija su membresía al componerse) SIN recrear el motor.
    """
    if not _watch_from_estudio_enabled():
        return None

    async def _refresh() -> None:
        await refresh_watch_from_estudio(estudio_list)
        sync_decider_watch(spine_decider, _watch_symbols())

    return _refresh




__all__ = [
    'AutoSimRuntime',
    'EngineIdentityMissingError',
    'SIGNAL_WINDOW_SOURCE_ENV',
    'SIGNAL_WINDOW_SOURCE_PRESET',
    'SIM_ACCOUNT_ID',
    '_HermeticRuntime',
    '_active_decider_watch',
    '_build_signal_decider',
    '_compose_atr_source',
    '_compose_canonical_reader',
    '_compose_edge_source',
    '_compose_evidence_source',
    '_compose_price_source',
    '_compose_real_stores',
    '_compose_regime_source',
    '_compose_trade_context_source',
    '_compose_watch_refresher',
    '_default_spine_decider',
    '_durable_sim_engine_id',
    '_runtime_hook',
    '_signal_snapshot_limit',
    '_signal_window',
    '_sim_engine_id',
    'active_strategy_enabled',
    'active_strategy_signal_enabled',
    'auto_sim_loop',
    'build_adaptive_recommendation_sink',
    'build_adaptive_state_reader',
    'build_cycle_regime_reader',
    'build_cycle_regime_sink',
    'build_durable_fact_cycle_reader',
    'build_operational_audit_sink',
    'build_top3_opportunity_sink',
    'load_active_strategy_decider',
    'start_auto_sim_worker',
]
