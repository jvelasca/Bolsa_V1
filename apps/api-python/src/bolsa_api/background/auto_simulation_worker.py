"""V2.22 / A9 (M5) — AutoSimulationWorker: bucle autónomo SIM-ONLY + liquidación.

Bucle continuo determinista por tick (S) SIM-ONLY, por símbolo en watch:
  (1) decisión inyectable (DecisionProvider) — default HOLD-safe,
  (2) gate AUTO de venue/simulación: sólo {paper, simulated}, kill OFF (jamás LIVE),
  (3) BUY sin posición abierta → liquida ``submit_simulated_order`` (settlement
      ExecutionEvent idempotente de M1/M2) y abre la posición SIM; SELL sobre una
      posición abierta → cierra/reconcilia por la misma vía SIM (reduce/exits),
  (4) rastrea posiciones abiertas a través de los turnos y emite el journal AUTO
      del día (M7); con ``auto_store`` persiste telemetría durable (M4).

REGLAS FIJAS (A9):
  * AUTO jamás toca LIVE: venues ∈ {paper, simulated}; no hay bridge LIVE; los
    ``LIVE_EXECUTION_*`` quedan intactos y en false.
  * Habilitación por ``AUTO_SIMULATION_WORKER_ENABLED`` (default OFF): sin env el
    ``start_auto_sim_worker`` no arranca task ni avanza nada que llene.
  * Reloj y price_script inyectados y deterministas: recorren minutos "simulados"
    sin ``sleep`` real — así la prueba reina mueve un día completo (hermética).

Alcance honesto (ver relevo): la liquidación reutiliza el camino de dominio M1/M2
(``submit_simulated_order``/``apply_simulated_order_once`` → traces ``ExecutionEvent``
idempotentes por ``execution_id``) contra un ``ExecutionEventStore`` inyectado. El
worker es el conductor (decisión → settlement SIM → posición → journal); los
invariantes de no-duplicación / no-LIVE / veneno live se verifican en el journal y
el store de eventos SIM, y con un ``finance_applier`` inyectado (seam
``bolsa_application.simulated_finance``, ExecuteTrade idempotente por
``simulated_idempotency_key``) los fills SIM pueden materializar dinero real
SIM-ONLY. Sin ``finance_applier`` (None, default hermético) las trazas quedan
``CAPTURED`` sin dinero; el cierre de libro contable PG real por tick es el gate PG
en vivo (``test_simulated_finance_pg``) que en este entorno sin credenciales dev
hace skip. Nunca LIVE.
"""

# ruff: noqa: F401  (facade de re-export: conserva la superficie publica del modulo original)
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, cast

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_REGIME_UNKNOWN,
    AdaptivePlan,
    AdaptivePolicy,
    RecoveryEvidence,
    build_adaptive_plan,
)
from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    DATA_GATE_FREEZES,
    DataGatePolicy,
    DataGateReading,
    assess_data_gate,
    journal_age_cycles,
)
from bolsa_analytics.cognitive.auto_portfolio_snapshot import UNKNOWN_SECTOR
from bolsa_analytics.cognitive.data_freshness import (
    FreshnessPolicy,
    assess_data_freshness,
)
from bolsa_analytics.cognitive.exit_order import (
    ExitOrder,
    build_exit_order,
    new_exit_order_id,
)
from bolsa_analytics.cognitive.exit_plan import (
    ExitPlan,
    is_thesis_invalidated,
    protective_fill_price,
)
from bolsa_analytics.cognitive.exit_policy import (
    resolve_exit_policy,
    resolve_holding_horizon,
)
from bolsa_analytics.cognitive.hard_kill_switch import (
    KILL_STATE_UNREADABLE,
    HardKillSwitch,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    combine_measurements,
    measurement_from_counts,
)
from bolsa_analytics.cognitive.open_order import (
    OpenOrder,
    build_open_order,
    summarize_open_orders,
)
from bolsa_analytics.cognitive.operational_governor import (
    assess_from_measurements,
    coerce_market_regime,
    to_market_regime,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    RELEASE_REASON_CANCEL,
    RELEASE_REASON_DEAD_TAIL,
    RELEASE_REASON_FILL,
    RELEASE_REASON_RESTART,
    RESERVATION_RELEASED_BY_CANCEL,
    RESERVATION_RELEASED_BY_FILL,
    RESERVATION_RELEASED_BY_RESTART,
    SIDE_BUY,
    SIDE_SELL,
    PortfolioReservation,
    build_reservation,
)
from bolsa_analytics.cognitive.position_ledger import (
    build_position_ledger,
    coerce_applied_fill_fact,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    advance_lifecycle,
    compute_trail_stop,
    derive_lifecycle_state,
    high_watermark_from_position,
    is_trail_armed,
    protection_state_dict,
    trailing_status,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    apply_position_current_stop,
    apply_position_reduce,
    build_position_state_from_fill,
    position_state_from_dict,
    seal_protection_transition,
)
from bolsa_analytics.cognitive.signal_identity import bar_window
from bolsa_analytics.cognitive.trade_context import TradeContext
from bolsa_api.background.auto_price_provider import (
    OhlcvPriceSource,
    PriceSource,
    price_source_kind,
)
from bolsa_api.background.auto_worker_execution import _ExecutionMixin
from bolsa_api.background.auto_worker_price import _PriceMixin
from bolsa_api.background.auto_worker_runtime import (  # noqa: F401
    SIGNAL_WINDOW_SOURCE_ENV,
    SIGNAL_WINDOW_SOURCE_PRESET,
    SIM_ACCOUNT_ID,
    AutoSimRuntime,
    EngineIdentityMissingError,
    _active_decider_watch,
    _build_signal_decider,
    _compose_atr_source,
    _compose_canonical_reader,
    _compose_edge_source,
    _compose_evidence_source,
    _compose_price_source,
    _compose_real_stores,
    _compose_regime_source,
    _compose_trade_context_source,
    _compose_watch_refresher,
    _default_spine_decider,
    _durable_sim_engine_id,
    _HermeticRuntime,
    _runtime_hook,
    _signal_snapshot_limit,
    _signal_window,
    _sim_engine_id,
    active_strategy_enabled,
    active_strategy_signal_enabled,
    auto_sim_loop,
    build_adaptive_recommendation_sink,
    build_adaptive_state_reader,
    build_cycle_regime_reader,
    build_cycle_regime_sink,
    build_durable_fact_cycle_reader,
    build_operational_audit_sink,
    build_top3_opportunity_sink,
    load_active_strategy_decider,
    start_auto_sim_worker,
)
from bolsa_api.background.auto_worker_safety import _SafetyMixin
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
from bolsa_api.background.auto_worker_state import _StateMixin
from bolsa_api.background.estudio_watch import SessionScopedEstudioList
from bolsa_api.background.paper_auto_engine_worker import (
    DecisionProvider,
    _effective_venue,
    _kill_switch_env_on,
    _watch_from_estudio_enabled,
    _watch_symbols,
    refresh_watch_from_estudio,
    sync_decider_watch,
)
from bolsa_application.account_drawdown import EquityMarkBook
from bolsa_application.adaptive_gate_store import AdaptiveGateStore, sink_failures_from_state
from bolsa_application.applied_fills import read_applied_fill_facts
from bolsa_application.auto_adaptive_journal import (
    AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
    build_adaptive_recommendation_entry,
)
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    AdaptiveStateReading,
    adaptive_state_unread,
    read_adaptive_state,
)
from bolsa_application.auto_cycle_journal import build_auto_cycle_regime_entry
from bolsa_application.auto_cycle_reconciliation import (
    cycle_ids_with_reservations,
    reconcile_cycle_trace,
)
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading, read_cycle_regimes
from bolsa_application.auto_daily_journal import OperationMeasurement, OpportunityRow, SimJournalRow
from bolsa_application.auto_engine_state_store import (
    AutoActivity,
    AutoEngineCycleClaim,
    AutoEngineLease,
    AutoEngineLeaseLost,
    AutoEngineLeaseStore,
    AutoEngineSnapshot,
    AutoEngineStore,
    AutoEngineTickInput,
)
from bolsa_application.auto_engine_state_store import (
    lease_ttl_seconds as auto_engine_lease_ttl_seconds,
)
from bolsa_application.auto_exit_gate import (
    AUTO_EXIT_PERMISSION_EVENT,
    AutoExitReview,
    review_auto_exit,
)
from bolsa_application.auto_operational_audit import (
    REASON_GRACE_WINDOW_KEEP,
    REASON_SESSION_OWNED,
    RECONCILIATION_KEEP,
    RECONCILIATION_RELEASE,
    build_cycle_settlement_entry,
    build_entry_order_entry,
    build_position_materialized_entry,
    build_protection_entry,
    build_reservation_claim_entry,
    build_reservation_reconciliation_entry,
    durable_fact_dedupe_key,
    operational_audit_enabled,
)
from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
from bolsa_application.auto_reason_codes import (
    ACTIVE_SIGNAL_DISABLED,
    ATR_GEOMETRY,
    ATR_SOURCE_FALLBACK,
    ATR_SOURCE_MISSING,
    ATR_SOURCE_REAL,
    EXIT_NOT_EMITTED,
    EXIT_QTY_OVER_POSITION,
    FILL_NOT_MATERIALIZED,
    FILL_PARTIALLY_MATERIALIZED,
    LEASE_NOT_HELD,
    LIFECYCLE_TRANSITION_REJECTED,
    OPPORTUNITY_TRADED,
    POSITION_ROW_UNRECONCILED,
    POSITION_UNMANAGED,
    PROTECT_REQUESTED,
    PROTECTION_MISSING,
    RECONCILIATION_REQUIRED,
    RESERVATION_ALREADY_LIVE,
    RESERVATION_UNMEASURABLE,
    SETTLEMENT_FAILED,
    STOP_RATCHET_APPLIED,
    STOP_RATCHET_REJECTED,
    THESIS_EXIT,
    TIME_EXIT,
    day_exit_reason,
)
from bolsa_application.auto_self_evaluation_feed import (
    build_adaptive_confidence_from_fills,
    build_adaptive_uncertainty_from_fills,
    build_auto_self_evaluation,
    cycles_from_fills,
    recovery_evidence_from_fills,
)
from bolsa_application.auto_v2_entry import (
    AtrSource,
    CatalogTradeContextSource,
    DiscoveryRegimeSource,
    EdgeReportSource,
    V2Signal,
    V2Tunables,
    build_active_strategy_hold_journal_entry,
    build_position_management_journal_entry,
    build_worker_snapshot,
    plan_v2_position_outcome,
    plan_v2_tick,
    position_manager_package,
    position_manager_stop_update,
    sector_from_package,
    signal_identity_for_bar,
    tunables_from_env,
    v2_engine_enabled,
)
from bolsa_application.auto_v2_entry import (
    edge_from_package as _edge_from_package,
)
from bolsa_application.closed_bars import (
    bar_tick,
    last_closed_bar_day,
    make_closed_bar_loader,
)
from bolsa_application.cycle_risk import CycleRisk, cycle_risk_from_reservations
from bolsa_application.decision_contract import (
    DecisionPackage,
    derive_execution_plan,
    risk_gate_auto_paper_dry,
    simulation_gate_allows,
)
from bolsa_application.execution_event import (
    UNAPPLIED_EXECUTION_EVENT_STATUSES,
    ExecutionEventStore,
)
from bolsa_application.exit_order_store import ExitOrderStore
from bolsa_application.flags import env_finite_float, env_flag
from bolsa_application.kill_switch_store import KillState, KillSwitchStore
from bolsa_application.operative_granularity_policy import resolve_operative_granularity
from bolsa_application.position_manager import (
    KILL_SWITCH,
    RISK_EXIT,
    PositionManagerResult,
    PositionManagerSkip,
)
from bolsa_application.price_source_kind import (
    PRICE_SOURCE_SCRIPT,
    PRICE_SOURCE_SYNTHETIC,
)
from bolsa_application.protection_compat import (
    ProtectionPolicy,
    protection_exit_fraction,
    protection_exit_reason,
)
from bolsa_application.reservation_store import ReservationStore
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    POSITION_PROJECTION_OK,
    POSITION_PROJECTION_REBUILT,
    POSITION_PROJECTION_UNKNOWN,
    reconcile_sim_account,
)
from bolsa_application.simulated_broker import fill_seed
from bolsa_application.simulated_settlement import (
    normalized_auto_venue,
    submit_simulated_order,
)
from bolsa_application.top3_opportunities import (
    HISTORICAL_SCORING_NO_CHAMPION,
    select_top3_records,
)

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.
from bolsa_domain.numeric import finite_float, finite_positive, finite_range, positive_quantity


class AutoSimulationWorker(
    _PriceMixin,
    _StateMixin,
    _SafetyMixin,
    _ExecutionMixin,
):
    """Driver determinista del día autónomo (por tick; hard SIM-ONLY).

    Mantiene el libro de posiciones abiertas entre turnos (``self._open`` por
    símbolo) y el journal completo del día. El settlement de cada intención
    aprobada va por ``submit_simulated_order`` (M1/M2). Sin ``exec_store`` la
    liquidación falla-cerrado (no abre ni llena; sin dinero). Sin LIVE nunca.
    """

    # AUTO Operational Monitor (M2): la costura inerte se declara a nivel de CLASE para que
    # cualquier instancia la vea —incluidas las que los tests construyen con ``object.__new__``
    # sin pasar por ``__init__`` (patrón común para probar un solo método)—. Sin el default,
    # leerla revienta con ``AttributeError`` en medio de un turno; con él, la ausencia de sink
    # es exactamente el ``Δ = 0`` que promete el flag OFF.
    _operational_audit_sink: Callable[[Any], Awaitable[None]] | None = None
    _audit_session_id: str | None = None
    # v2.88.27 — mismos defaults de CLASE para el lector de deduplicación y el flag de
    # recuperación: una instancia creada sin pasar por ``__init__`` ve "sin lector" (no recupera)
    # en vez de reventar con ``AttributeError`` a mitad de arranque.
    _durable_fact_cycle_reader: Callable[[str], Awaitable[frozenset[str]]] | None = None
    _v2_durable_facts_recovered: bool = False

    def __init__(
        self,
        *,
        decider: DecisionProvider | None = None,
        exec_store: ExecutionEventStore | None = None,
        auto_store: AutoEngineStore | None = None,
        price_script: PriceScript = flat_price_script,
        # W4 (v2.88.17): seam de precio que PUEDE decir «no hay precio». ``None`` (default)
        # conserva el camino hermético EXACTO: se lee ``price_script`` en vivo —así los
        # tests pueden seguir mutando ``worker._price_script``— de modo que adoptar el seam
        # NO mueve un precio. Con una fuente real, ``execution()``/``mid()`` pueden devolver
        # ``None`` y el motor cae fail-closed (HOLD por símbolo, declarado), nunca a 100.0/0.
        price_source: PriceSource | None = None,
        clock: Clock | None = None,
        finance_applier: Callable[[Any], Awaitable[bool]] | None = None,
        context_store: Any = None,
        position_store: Any = None,
        engine_id: str = "auto-sim",
        account_id: str | None = None,
        kill_switch_source: Callable[[], bool] | None = None,
        canonical_positions_reader: Any = None,
        require_account_id: bool = False,
        # M8 (auditoría .183): el runtime que conduce la operativa REAL exige sus espejos
        # durables. Un turno al que le falte uno se rechaza (``durable_stores_missing``)
        # en vez de operar con la mitad del estado en RAM. Default ``False`` conserva el
        # camino hermético (tests/replay), que nunca hizo esa promesa.
        require_durable_stores: bool = False,
        regime_source: Callable[[], str | None] | None = None,
        sector_source: Callable[[str], str | None] | None = None,
        liquidity_source: Callable[[str], float | None] | None = None,
        # V2.42 slice 2b (E2): ATR real por símbolo (barras as-of). ``None`` (hermético)
        # ⇒ la geometría usa el fallback declarado, marcado como tal en el journal.
        atr_source: Callable[[str], float | None] | None = None,
        # Objetos con ``refresh()`` async + lectura sync (``CatalogTradeContextSource``,
        # ``EdgeReportSource``). Se anotan como ``Any`` en la firma (seam inyectable para
        # tests) y se estrechan en el ``__init__`` a la interfaz que consume el hot path.
        edge_source: Any = None,
        trade_context_source: Any = None,
        # V2.88 / TOP3 cross-asset: evidencia LAB del campeón ACTIVE por instrumento
        # (``StrategyEvidenceSource``). Con ``None`` el scoring es byte-idéntico al
        # histórico (solo edge+liquidity). Se refresca por tick como el resto de fuentes.
        evidence_source: Any = None,
        # V2.88.84 — sink DURABLE del TOP3 cross-asset (``top3_opportunities``, migración 052):
        # el productor que faltaba. Recibe ``(records, regime)`` y persiste la foto de la barra
        # (una por barra, con la procedencia del score declarada por slot). Sin él (hermético o
        # test) no se escribe nada ⇒ Δ = 0 y el hueco sigue declarado, nunca inventado.
        top3_opportunity_sink: Callable[[list[Any], str | None], Awaitable[None]] | None = None,
        consumed_signal_store: Any = None,
        # Handoff durable ESTUDIO → AUTO (migración 058). El LECTOR recibe
        # ``(cuenta, día de barra de decisión, instrumentos)`` y devuelve la selección
        # (``AdoptionResult``); el SUMIDERO recibe los desenlaces (consumida/rechazada) y
        # los sella. Sin ellos el motor no adopta nada y la cadena publica
        # ``not_attributed``: nunca se infiere por símbolo.
        daily_proposal_source: (Callable[[str, str, Sequence[str]], Awaitable[Any]] | None) = None,
        daily_proposal_sink: Callable[[list[dict[str, Any]]], Awaitable[Any]] | None = None,
        # AUTO-1b: espejo durable de las RESERVAS de cartera (``portfolio_reservations``).
        # Con él, las reservas vivas son la autoridad de ``reserved_cash``/``pending_risk``
        # y ``execution_events`` queda como reconciliación de arranque. Sin él (camino
        # hermético) el libro de órdenes pendientes sigue derivándose como en V2.40.4.
        reservation_store: ReservationStore | None = None,
        # OBS-14.b — ventana de gracia por EDAD del barrido de reservas: una candidata AJENA
        # que todavía no envejeció se CONSERVA (fail-closed). ``None`` ⇒ la derivada de la
        # cadencia real del loop (``reservation_grace_window()``). ``timedelta(0)`` restaura
        # el comportamiento previo (retirar toda candidata); se usa para contraste.
        reservation_grace: timedelta | None = None,
        # AUTO-10: sink DURABLE del régimen por ciclo (``decision_journal_entries``). Con él,
        # el ``marketRegime`` de un ciclo deja de vivir solo en la lista del proceso y el eje
        # ``strategy × regime`` gana su insumo. Sin él (camino hermético o test) no se escribe
        # nada: el hueco sigue declarado, nunca inventado.
        cycle_regime_sink: Callable[[Any], Awaitable[None]] | None = None,
        # AUTO-10: LECTOR de ese mismo journal (la otra mitad). Recibe los ``cycle_id`` del tick
        # y devuelve la lectura con sus huecos declarados. Sin él, el productor de R conserva el
        # comportamiento de AUTO-9 (``regime_not_durable``): no se finge que se leyó.
        cycle_regime_reader: Callable[[Sequence[str]], Awaitable[CycleRegimeReading]] | None = None,
        # AUTO Operational Monitor (``M2``): sink DURABLE de la auditoría operativa
        # (``auto_entry_decision``/``auto_reservation_claim``/``auto_reservation_reconciliation``)
        # sobre el mismo spine (``decision_journal_entries``). Sin él (hermético/test) no se
        # escribe nada y el monitor declara los huecos; con él, ownership y concurrencia pasan
        # de ``NO MEDIDO`` a hechos. Interruptor ``AUTO_OPERATIONAL_AUDIT`` default OFF (Δ = 0).
        operational_audit_sink: Callable[[Any], Awaitable[None]] | None = None,
        # v2.88.27 — LECTOR de deduplicación del MISMO spine: dado un ``event_type``, devuelve
        # los ``cycleId`` que YA tienen ese hecho durable (acotado por cuenta y motor). Es lo que
        # permite al arranque reemitir sólo el ``SETTLEMENT`` que un crash dejó sin publicar. Sin
        # él no se recupera nada (el hueco sigue declarado) aunque la inserción ya sea idempotente
        # por ``dedupe_key``.
        durable_fact_cycle_reader: Callable[[str], Awaitable[frozenset[str]]] | None = None,
        # AUTO-11: la recomendación Adaptive DURABLE (``decision_journal_entries``). Con él, la
        # memoria de la rotación (cooldown/hysteresis) deja de vivir solo en la lista del proceso
        # y una pausa SOBREVIVE al reinicio. Sin él (hermético/test) no se escribe nada: no se
        # finge una evidencia que no se puede leer.
        adaptive_sink: Callable[[Any], Awaitable[None]] | None = None,
        # AUTO-11: LECTOR de ese mismo journal (la otra mitad). Recibe la cuenta del tick y
        # devuelve el estado reconstruido con TODOS sus límites declarados. Sin él, el arranque no
        # recupera nada y el contador arranca como en ``V2.51`` (se declara en el log).
        adaptive_reader: Callable[[str | None], Awaitable[AdaptiveStateReading]] | None = None,
        # AUTO-15: la racha de fallos CONSECUTIVOS del sink como estado DURABLE
        # (``adaptive_gate_state``). Sin él la racha sigue siendo solo del proceso y un reinicio la
        # olvida (el límite que AUTO-13 declaró); con él, el arranque la LEE antes del primer plan.
        adaptive_gate_store: AdaptiveGateStore | None = None,
        # V2.43.3 (P0-1): espejo durable del latch de la parada dura (``auto_kill_state``).
        # Sin él la parada es solo del proceso y un reinicio la olvida. Con él, el arranque
        # la LEE antes de readoptar posición y el motor no puede reabrirse solo.
        kill_switch_store: KillSwitchStore | None = None,
        # V2.43.3 (P0-2): espejo durable de la identidad de las SALIDAS (``auto_exit_orders``).
        # Da a cada cierre una identidad (``exit_order_id``) que sobrevive al reinicio, en
        # vez de depender del contador de proceso ``_v2_exit_seq``.
        exit_order_store: ExitOrderStore | None = None,
        # V2.43/AUTO-3: libro de marcas de equity (drawdown medido para el gobernador).
        # Inyectable para que un test/evidencia fije la marca del día de forma determinista;
        # en producción cada worker lleva el suyo (una serie por proceso de la misma cuenta).
        equity_marks: EquityMarkBook | None = None,
    ) -> None:
        self._decider = decider
        self._exec_store = exec_store
        self._auto_store = auto_store
        self._price_script = price_script
        # W4: la fuente real (``None`` ⇒ camino hermético por ``price_script``).
        self._price_source = price_source
        # W4: precio AUSENTE declarado y contado por símbolo (nunca un fallback mudo).
        self._v2_price_missing: dict[str, int] = {}
        self._clock = clock if clock is not None else default_clock
        self._engine_id = engine_id
        self._account_id = account_id
        # V2.23/A9 (Bloque 3, kill fail-closed): fuente del kill switch inyectable.
        # Por defecto comparte el gate fail-closed de ``paper_auto_engine_worker``
        # (si NO se puede leer desde ningún origen, bloquea el AUTO). Un test puede
        # inyectar una fuente determinista.
        self._kill_switch_source = kill_switch_source or _kill_switch_env_on
        # V2.22/a9 finance seam: un ``ApplyFinanceCallable`` opcional. Con None (default
        # hermético) los fills SIM quedan como hoy (``CAPTURED``, sin dinero). Con un
        # applier real, ``_settle`` lo reenvía como ``apply_finance`` de la liquidación.
        self._finance_applier = finance_applier
        # V2.23/A9 (Bloque 5): durabilidad SIM.
        #   ``context_store``  = contexto financiero por fill (P1-05).
        #   ``position_store`` = espejo durable de posición abierta (P1-06 / G7).
        self._context_store = context_store
        self._position_store = position_store
        # V2.24/A9.1 (P1-01): proyección reconstruible. ``canonical_positions_reader``
        # lee el estado financiero CANÓNICO (posiciones abiertas del ledger) para
        # reconstruir/comprobar la proyección. Sin él, la proyección no puede autorizar
        # aperturas por sí sola (fail-closed ante divergencia).
        self._canonical_positions_reader = canonical_positions_reader
        # V2.24/A9.1 (P1-04): en el camino durable REAL la cuenta es obligatoria
        # (fail-closed). Los tests herméticos que ejercitan la mecánica SIM sin PG
        # pueden relajarlo explícitamente con ``require_account_id=False``.
        self._require_account_id = require_account_id
        # M8: el turno operativo exige sus espejos durables (ver ``OPERATIVE_DURABLE_SEAMS``).
        self._require_durable_stores = require_durable_stores
        self._reconciliation: dict[str, str] = {}
        # R-2 (cierre 2026-10-26): símbolos con MÁS de un motor vivo en la cuenta. El
        # total de la cuenta no identifica a esta fila, así que su cantidad no está
        # reconciliada aunque se conserve la propia (una fila ya inflada por el defecto
        # anterior no se repara sola). Se usa para DECLARAR el cierre, nunca para vetarlo.
        self._multi_engine_symbols: set[str] = set()
        self._readopted = False
        # V2.23/A9 (Bloque 6): protección autónoma (SL/T1/trailing/cierre de sesión).
        # Configurable por env, OFF por defecto. El precio de entrada/máximo se toma
        # del ``price_script`` determinista al abrir (misma fuente que la liquidación).
        self._protection = _protection_config_from_env()
        self._entry_price: dict[str, Decimal] = {}
        self._high_price: dict[str, Decimal] = {}
        # W-159-2 (Hueco B) — base de coste CANÓNICA por símbolo, reconstruida del libro de
        # fills aplicados (``_canonical_entry_prices``). El espejo ``_entry_price`` puede
        # venir de una fila obsoleta de otro motor; el libro, no. La adopción usa el libro
        # cuando existe y el espejo solo como respaldo declarado.
        self._canonical_entry_by_symbol: dict[str, Decimal] = {}
        # W-159-3 (Hueco D) — atribución (versión y ciclo) de la posición viva, derivada del
        # libro canónico. Un motor nuevo no tiene proyección previa, pero el hecho de qué
        # estrategia abrió la posición y a qué ciclo pertenece SÍ está en los fills.
        self._canonical_attribution: dict[str, dict[str, Any]] = {}
        # V2.28/A10 (P1-02 real): versión de estrategia que abrió la posición de cada
        # símbolo. Permite atribuir también los fills de CIERRE (protección/venta) a la
        # misma versión: sin esto la serie de la versión tendría compras sin ventas y
        # el PnL observado no cuadraría.
        self._position_version: dict[str, str] = {}
        # V2.24/A9.1 (P2-06): T1 parcial ya ejecutado por símbolo (no re-dispara T1).
        self._t1_done: set[str] = set()
        # AUTO 2.0 (V2) — pipeline de decisión (env-gated, default OFF). Con ON, las
        # entradas pasan por OpportunityRanker + PortfolioDecisionEngine + TradePlan y
        # la gestión de posición por PositionState + ExitPlan + PositionDecision, en
        # lugar del decider directo y de la política global ``ProtectionConfig``.
        # El settlement/ledger/reconciliación NO cambian: esto solo decide QUÉ emitir.
        self._v2_enabled = v2_engine_enabled()
        self._v2_tunables: V2Tunables = tunables_from_env()
        # Granularidad operativa (diseño v2): relojes separados, gate fail-closed. En
        # este incremento es un SEAM INERTE: la configuración por defecto (``1d``)
        # reproduce el comportamiento previo byte a byte. ``signal_timeframe`` deja de
        # leerse suelto y se DERIVA del ``DecisionClock`` (ver ``operative_granularity_policy``).
        self._v2_granularity = resolve_operative_granularity(self._v2_tunables.signal_timeframe)
        # W2 · Fase A — short-circuit por barra. Con el reloj de DECISIÓN en D1, todo el
        # I/O de DATO del tick (régimen, espejo de señales consumidas, contexto de cartera,
        # órdenes pendientes, Adaptive, poda) relee dentro de la MISMA barra un dato que ya
        # está cargado en RAM y no puede cambiar lo que la barra ya decidió. El turno
        # DURABLE reutiliza ese dato de barra; la DECISIÓN no se omite (la función pura
        # ``plan_v2_tick`` se recalcula con el estado corriente), de modo que la
        # contabilidad del tick —embudo, journal, procedencia del ATR— sale idéntica.
        # ``False`` por defecto: el camino hermético (tests y replay, que llaman
        # ``auto_turn`` suelto) reproduce el comportamiento previo byte a byte. Lo enciende
        # ``real_turn`` para el alcance de SU turno (misma disciplina que los stores).
        self._v2_bar_short_circuit = False
        #: Barra cuyo dato de decisión ya se cargó en ESTE proceso (``""`` = ninguna aún).
        self._v2_bar_plan_bar: str = ""
        #: Plan Adaptive del dato de barra (se reutiliza junto con el resto del I/O).
        self._v2_bar_adaptive: AdaptivePlan | None = None
        #: ``True`` si el plan de la barra dejó entradas aprobadas SIN consumir: mientras
        #: quede algo pendiente NO se salta nada (el reintento dentro de la barra es
        #: observable y hay que preservarlo). Fail-closed: sin poder afirmar que está
        #: liquidada, la barra se planifica como siempre.
        self._v2_bar_pending = False
        #: Turnos que reutilizaron el dato de barra (instrumentación; 0 en hermético).
        self._v2_bar_short_circuit_ticks = 0
        #: S-5 — símbolos ya declarados ``position_unmanaged`` en la barra corriente. La
        #: posición sigue sin gestión mientras exista, así que la declaración se repite una
        #: vez por barra (no una vez por tick de 60 s): es un hecho del día, no un latido.
        self._v2_unmanaged_bar: str = ""
        self._v2_unmanaged_symbols: set[str] = set()
        self._v2_positions: dict[str, Any] = {}
        # V2.40.4 — libro de órdenes PENDIENTES (fills no materializados) del último
        # refresco, con su estado de medición. Por defecto vacío y COMPLETO (sin espejo
        # durable no puede haber dinero en vuelo); el refresco por tick lo actualiza.
        self._v2_open_orders: tuple[OpenOrder, ...] = ()
        self._v2_order_book_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
        # AUTO-1b — libro durable de RESERVAS. ``_v2_reservations`` son las vivas (la
        # autoridad de capital/riesgo comprometido), ``_v2_reservations_measurement`` su
        # estado de medición y ``_v2_reservation_blocked`` los instrumentos cuya reserva
        # NO llegó a persistirse en el tick (su aprobación no se emite: no existe
        # aprobación sin reserva durable). ``_v2_reservation_carryover`` son los
        # instrumentos con reserva viva de ticks ANTERIORES: no se apila otra igual.
        self._reservation_store = reservation_store
        # OBS-14.b — ventana de gracia por EDAD del barrido de reservas (``None`` ⇒ la
        # derivada de la cadencia real del loop: ``V2_RESERVATION_GRACE_TURNS`` turnos).
        self._v2_reservation_grace: timedelta = (
            reservation_grace if reservation_grace is not None else reservation_grace_window()
        )
        self._v2_reservations: tuple[PortfolioReservation, ...] = ()
        self._v2_reservations_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
        self._v2_reservation_blocked: frozenset[str] = frozenset()
        self._v2_reservation_carryover: frozenset[str] = frozenset()
        # OBS-14.b — PROPIEDAD de las reservas dadas de alta por ESTA sesión
        # (``save_claim`` ganado en el tick o reserva de salida persistida). El cierre de
        # turno NO puede retirar reservas ajenas: en una carrera entre sesiones la
        # evidencia durable («sin APPLIED y sin traza en vuelo») es INDISTINGUIBLE de una
        # orden que otra sesión aún no ha emitido en su propio turno, y liberarla sería
        # fail-OPEN (devolver al mercado un capital que sí se materializó después). La
        # reconciliación de ARRANQUE sí barre el libro completo: ahí el proceso nace sin
        # memoria y la reserva ajena huérfana es exactamente lo que hay que retirar.
        self._v2_owned_reservations: set[str] = set()
        self._v2_open_orders_read_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
        self._v2_reservations_reconciled = False
        # V2.43.3 (P0-1) — espejo durable del latch de la parada dura. Sin store la parada
        # queda SOLO en memoria (camino hermético): se declara y el arranque no puede
        # restaurarla. Con store, el load se repite en cada turno real (P-1: es la única
        # forma de adoptar un HALT durable aparecido después y de recuperar la lectura
        # tras un fallo transitorio).
        self._kill_switch_store = kill_switch_store
        # R-1 (verificación 2026-10-26 §8) — latch de LECTURA de la proyección: si el
        # espejo (o el canónico) no se pudo leer, NINGÚN símbolo autoriza aperturas en
        # este tick, aunque ``_watch_symbols()`` venga vacío o el símbolo no esté en el
        # diccionario de reconciliación. Se libera sólo tras una lectura válida.
        self._projection_read_failed = False
        # V2.43.3 (P0-2) — identidad durable de las salidas. ``_v2_exit_orders`` son los
        # INTENT vivos conocidos en memoria (espejo del libro durable); el store es la
        # autoridad tras un reinicio.
        self._exit_order_store = exit_order_store
        self._v2_exit_orders: dict[str, ExitOrder] = {}
        # V2.44 — parada DURA latcheada, por encima del gobernador. Nace desactivada; el
        # worker la activa con motivos tipificados (reconciliación rota, ejecución
        # duplicada, datos corruptos) y solo una reconciliación explícita la libera.
        self._v2_kill_switch = HardKillSwitch()
        # Relojes por DIMENSIÓN para la frescura (V2.44). Se pueblan al leer precios/ATR
        # del tick; una prueba (o un feed real parado) puede dejar ``market_data`` viejo
        # para forzar el veto de aperturas sin congelar las salidas protectoras.
        self._v2_data_timestamps: dict[str, float] = {}
        self._v2_freshness_policy = FreshnessPolicy()
        self._v2_plan: Any = None
        self._v2_journal: list[Any] = []
        # V2.49/AUTO-8.1 — ciclos consecutivos que cada versión lleva PAUSADA por la
        # rotación Adaptive. Es el DATO de estado que habilita hysteresis y cooldown. Desde
        # AUTO-11 se **reconstruye del journal durable** en el arranque (una vez por proceso):
        # sin lector sigue arrancando vacío —el límite que declaraba ``V2.51``—, pero con lector
        # una pausa ya no se levanta antes de su ventana mínima por un reinicio.
        self._v2_adaptive_paused_cycles: dict[str, int] = {}
        # AUTO-11: copia del contador que ENTRÓ a decidir en el turno. ``build_adaptive_plan`` lo
        # pisa con el de SALIDA justo después, y la evidencia durable debe publicar el de entrada:
        # registrar el de salida afirmaría que Adaptive decidió con un estado que aún no existía.
        self._v2_adaptive_paused_cycles_entered: dict[str, int] = {}
        # AUTO-13: salud de la EVIDENCIA Adaptive. Dos hechos con límites distintos y declarados:
        # (a) un contador EN MEMORIA de fallos CONSECUTIVOS del sink (detecta el fallo al instante,
        # pero se pierde al reiniciar) y (b) el ancla DURABLE de antigüedad del journal, medida del
        # ``asOf`` de la última recomendación publicada (sobrevive al reinicio). El estado del gate
        # los combina; ninguno se disfraza del otro.
        self._v2_adaptive_sink_failures: int = 0
        #: AUTO-15: ¿la racha que entró al gate viene del estado DURABLE? Empieza en ``False`` (no
        #: se ha consultado nada) y lo pone quien puede afirmarlo: la siembra de arranque, el
        #: incremento o el reset. Un ``True`` sin store detrás sería una mentira sobre la prueba.
        self._v2_adaptive_sink_failures_durable: bool = False
        self._v2_adaptive_sink_last_success_at: str | None = None
        #: Antigüedad durable (ciclos) de la última publicación, o ``None`` si no se pudo medir.
        self._v2_adaptive_journal_anchor_age: int | None = None
        #: La lectura durable del arranque, guardada para poder declarar sus límites al medir el ancla.
        self._v2_adaptive_state_reading: AdaptiveStateReading | None = None
        #: AUTO-13 (§24) — memoria DERIVADA de la rampa: por versión, el instante en que dejó de
        #: estar pausada. Se **siembra** del lector durable (``reactivated_at``) y el propio
        #: proceso la mantiene al día con las transiciones que ve (pausada → activa). Sin ella,
        #: una versión que cumple su cooldown a mitad de proceso no entraría en la rampa hasta el
        #: siguiente reinicio: la mitad viva de una memoria que no se persiste.
        self._v2_adaptive_reactivated_at: dict[str, str] = {}
        # AUTO-11: recuperación del estado Adaptive y reconciliación del rastro de ciclo, una vez
        # por proceso cada una.
        self._v2_adaptive_state_recovered = False
        self._v2_cycle_trace_reconciled = False
        # v2.88.27 — recuperación de hechos durables del spine, una vez por proceso. Reemite el
        # ``SETTLEMENT`` de un ciclo cerrado que un crash dejó sin publicar; la identidad
        # determinista (``dedupe_key``) hace el reenvío idempotente.
        self._v2_durable_facts_recovered = False
        # V2.45/AUTO-5 — embudo del día (Golden Day 2.0): filas de oportunidad con su
        # estado FINAL y su motivo, más el contador INDEPENDIENTE de candidatas vistas
        # (así "faltó una oportunidad por explicar" es detectable, no silencioso).
        self._v2_opportunities: list[OpportunityRow] = []
        self._v2_seen_signals: int = 0
        # V2.45/AUTO-5 — MAE/MFE por operación, leído del ``mfe_mae`` del PositionState al
        # cerrar (se RECOGE, no se calibra: la calibración stop/T1/trailing es AUTO-7).
        self._v2_operation_measurements: list[OperationMeasurement] = []
        self._v2_last_exit_reasons: dict[str, tuple[str, ...]] = {}
        # S-6 — el ``ExitPlan`` que produjo la gestión del símbolo en ESTE turno. Es el
        # objeto sobre el que se consulta F5 al emitir la salida: se guarda aquí para no
        # reconstruirlo aguas abajo (misma condición ⇒ mismo plan en las dos capas).
        self._v2_last_exit_plans: dict[str, ExitPlan | None] = {}
        # S-6 — veredicto F5 de cada salida emitida (para el informe del turno y las
        # pruebas; el journal es la fuente durable).
        self._v2_last_exit_reviews: dict[str, AutoExitReview] = {}
        # V2.42 slice 2c: etiqueta del DÍA del motivo de cierre (``time_exit``/...), la que
        # viaja en la fila ``position_close``. Se deriva del motivo DECISORIO del plan, así
        # que un stop-out no se cuenta como salida por tesis.
        self._v2_last_exit_label: dict[str, str] = {}
        # S-3: salidas DECIDIDAS que aún no han emitido orden (``EXIT_PENDING`` no se
        # escribe hasta que la venta existe; ver ``_v2_note_exit_intent``).
        self._v2_pending_exit: dict[str, PendingExitIntent] = {}
        # O-1: settlements que lanzaron (contador del proceso; el día lo deriva del journal).
        self._settlement_failures: int = 0
        # H-2 (§9 del pack): un ``PROTECT`` que NO mueve el stop y NO cambia el estado
        # quedaba mudo para siempre. Se journaliza UNA vez por (símbolo, stop) para no
        # inundar el journal en cada tick de un trailing ya en régimen permanente.
        self._v2_protect_noop_stop: dict[str, float] = {}
        # V2.42 slice 2b (E2): medición de la procedencia del ATR del tick. El journal
        # sólo declara las señales que CAEN al sintético (el caso interesante); estos
        # contadores dan la fracción completa para el audit-pack.
        self._v2_atr_source_counts: dict[str, int] = {
            ATR_SOURCE_REAL: 0,
            ATR_SOURCE_FALLBACK: 0,
            ATR_SOURCE_MISSING: 0,
        }
        # H-2-style: la declaración de geometría sintética se journaliza UNA vez por
        # (símbolo, origen) — es una propiedad de la geometría, no un hecho del tick. Sin
        # el memo, un universo sin barras escribiría una entrada por candidata y por
        # turno, y el journal del día (que es evidencia de decisiones) se ahogaría.
        self._v2_atr_journaled: dict[str, str] = {}
        # B-5 — el HOLD de la ACTIVE con motivo se declara UNA vez por (símbolo, motivo,
        # barra): es un hecho de la barra, no del tick. Sin esta memo el mismo «la señal está
        # apagada» se escribiría cada 60 s y ahogaría el journal de decisiones.
        self._v2_active_hold_journaled: set[tuple[str, str, str]] = set()
        self._v2_atr_source = atr_source
        # V2.43/AUTO-3 — drawdown MEDIDO para el gobernador de riesgo y mercado. La serie
        # de equity del proceso es la MISMA cuenta (marca día/semana desde el primer
        # equity del día). ``_sim_realized_pnl`` acumula el P&L de las ventas aplicadas
        # (el worker SIM no lleva caja; sin este término, una pérdida ya cerrada
        # desaparecería de la equity de marca en el tick siguiente). Solo se LEE con el
        # governor ON, así que con el flag OFF no cambia ningún comportamiento.
        self._v2_equity_marks = equity_marks if equity_marks is not None else EquityMarkBook()
        self._sim_realized_pnl: Decimal = Decimal("0")
        # v2.88.70: el turno real fija la equity del libro (cash + valor de mercado).
        # Sin esa lectura las aperturas quedan vetadas. El fallback de env/100k solo
        # vive en el camino hermético, que nunca llama a ``load_book_equity``.
        # M14: UNA foto inmutable por lectura (no tres atributos) con su ``as_of``.
        self._book_equity_snapshot = BookEquitySnapshot()
        self._book_equity_required = False
        # AUTO 2.0 (V2): fuente del régimen operativo (inyectable). Sin fuente y sin
        # override de env, el régimen es UNKNOWN ⇒ exit-only (fail-closed: sin régimen
        # no se abren entradas nuevas).
        self._v2_regime_source = regime_source
        # AUTO-11: lo que se publica DURABLEMENTE con cada evaluación Adaptive. Sin sink no hay
        # escritura (ni se finge): el cooldown sigue siendo solo del proceso, como en ``V2.51``.
        self._adaptive_sink = adaptive_sink
        # AUTO-11: lo que se LEE de vuelta en el arranque para reconstruir el cooldown. Sin lector
        # no se recupera nada (se declara en el log) y el contador arranca a 0.
        self._adaptive_reader = adaptive_reader
        # AUTO-15: el espejo DURABLE de la racha de fallos del sink del gate. Sin él la racha
        # vive solo en el proceso (``_v2_adaptive_sink_failures``) y un reinicio la devuelve a 0:
        # el gate volvería a creerse sano con un journal que lleva fallando. Con él, el arranque
        # la siembra de ``adaptive_gate_state`` y la racha no se olvida.
        self._adaptive_gate_store = adaptive_gate_store
        # AUTO-10: lo que se publica DURABLEMENTE cuando un ciclo abre. Sin sink no hay
        # escritura (ni se finge): el hueco de régimen por ciclo sigue declarado.
        self._cycle_regime_sink = cycle_regime_sink
        # AUTO-10: lo que se LEE de vuelta. Sin lector, el R por ciclo sigue midiéndose pero el
        # régimen queda declarado como no durable (comportamiento de AUTO-9).
        self._cycle_regime_reader = cycle_regime_reader
        # AUTO Operational Monitor (``M2``): lo que se publica DURABLEMENTE en el spine con la
        # auditoría operativa (decisión/claim/reconciliación). Sin sink no se escribe (ni se
        # finge): los paneles de ownership/concurrencia siguen declarados ``NO MEDIDO``.
        self._operational_audit_sink = operational_audit_sink
        # v2.88.27 — lo que se LEE de vuelta para deduplicar/recuperar hechos M2 en el arranque.
        # Sin lector no se recupera nada (el hueco sigue declarado), pero la inserción ya es
        # idempotente por ``dedupe_key``.
        self._durable_fact_cycle_reader = durable_fact_cycle_reader
        # Identidad de sesión para la auditoría (dueño del claim y ``caller`` del barrido). Se
        # acuña perezosamente SÓLO cuando hay sink: sin auditoría no consume nada (Δ = 0).
        self._audit_session_id: str | None = None
        # AUTO 2.0 (V2): fuente del sector por símbolo (inyectable). Sin ella, el sector
        # solo existe si la propuesta lo declara en su ``memo``; si no, es desconocido y
        # el gate de concentración sectorial veta (V2.40.1: nunca se asume exento).
        self._v2_sector_source = sector_source
        # AUTO 2.0 · V2.40.1: liquidez real (ADV notional) por símbolo. Sin ella, la
        # liquidez es desconocida ⇒ ``liquidity_unknown`` ⇒ no hay entrada (antes un
        # ``None`` se puntuaba como "liquidez perfecta", que es fail-OPEN).
        self._v2_liquidity_source = liquidity_source
        # AUTO 2.0 · V2.40.1: contexto de cartera (sector+ADV+frescura) y edge real por
        # versión de estrategia. Son objetos con ``refresh()`` async (I/O una vez por
        # tick) y lectura SÍNCRONA en el hot path, igual que el régimen.
        self._v2_trade_context_source: CatalogTradeContextSource | None = trade_context_source
        self._v2_edge_source: EdgeReportSource | None = edge_source
        self._v2_evidence_source: Any = evidence_source
        # Handoff ESTUDIO → AUTO (migración 058): el LECTOR de propuestas pendientes y el
        # SUMIDERO de desenlaces. Se inyectan por sesión/tick como los demás espejos; sin
        # ellos el camino es el histórico (Δ = 0) y la cadena declara ``not_attributed``.
        self._daily_proposal_source: Callable[[str, str, Sequence[str]], Awaitable[Any]] | None = (
            daily_proposal_source
        )
        self._daily_proposal_sink: Callable[[list[dict[str, Any]]], Awaitable[Any]] | None = (
            daily_proposal_sink
        )
        # Foto de propuestas adoptables de la BARRA corriente (se relee al cambiar de barra).
        self._v2_bar_proposals: dict[str, dict[str, Any]] = {}
        self._v2_bar_proposals_bar: str = ""
        # Propuestas de ESTA pasada del plan (``instrumento → payload``) y caducadas.
        self._v2_tick_proposals: dict[str, dict[str, Any]] = {}
        self._v2_tick_expired: tuple[tuple[str, str], ...] = ()
        # V2.88.84 — espejo durable del TOP3 cross-asset (``top3_opportunities``, migración 052).
        # Inyectable por sesión/tick como los demás; sin él no se escribe (Δ = 0).
        self._top3_opportunity_sink: Callable[[list[Any], str | None], Awaitable[None]] | None = (
            top3_opportunity_sink
        )
        # Barra (inicio ISO) de la última foto del TOP3: acota la escritura a UNA por barra.
        self._v2_top3_bar: str = ""
        # AUTO 2.0 · P4: espejo durable de las señales consumidas (inyectable). Con él,
        # un reinicio NO autoriza a re-emitir la misma señal sobre la misma barra; sin
        # él (hermético) el dedupe vive solo en RAM, como hasta ahora.
        self._consumed_signal_store = consumed_signal_store
        # AUTO 2.0 (V2): identidades de señal YA consumidas (oportunidades emitidas
        # sobre su barra). Evita que el mismo BUY sobre la misma barra vuelva a
        # re-emitirse en el turno siguiente (worker 60s sobre señal D1) — el ``churn``
        # clásico: stop-out y re-entrada inmediata con la señal que ya se usó.
        self._v2_consumed_signals: set[str] = set()
        # Barra (inicio ISO) a la que pertenece ``_v2_consumed_signals``: al cambiar de
        # barra la memoria se reinicia (solo la barra corriente deduplica).
        self._v2_consumed_bar: str = ""
        # P5: marcas cuyo ``mark`` durable falló (signal_id → (símbolo, barra)); se reintentan.
        self._v2_consumed_unpersisted: dict[str, tuple[str, str]] = {}
        # P6: transiciones del INTENT de salida cuyo guardado falló (exit_order_id → orden).
        self._v2_exit_unpersisted: dict[str, ExitOrder] = {}
        # AUTO 2.0 · P4: planes V2 rehidratados del espejo durable al readoptar
        # (``symbol → PositionState.to_dict()``), pendientes de primer uso. Se usa una
        # sola vez: una vez rehidratado, el ``PositionState`` vivo manda.
        self._v2_durable_plans: dict[str, dict[str, Any]] = {}
        # Identidad de la señal de cada símbolo en el tick corriente (para marcarla como
        # consumida SOLO cuando la entrada se ejecuta de verdad).
        self._v2_tick_signals: dict[str, str] = {}
        self._minute = 0
        self._time = self._clock()
        self._open: dict[str, Decimal] = {}
        # V2.24/A9.1 (P1-03): identidades de orden lógicas únicas por intención, para
        # namespacear el ``execution_id`` (no colisión entre cuentas/engines).
        # W3 (v2.88.16): ``_order_seq`` deja de formar parte de la IDENTIDAD (que se ancla a
        # la barra) pero se CONSERVA como contador monotónico de INTENT de entrada del
        # worker: es la telemetría declarada de AUTO-6 (invariante ``Σ _order_seq == 1`` de
        # las suites hermética y PG concurrentes) y la traza histórica del día.
        self._order_seq: int = 0
        # W3 (v2.88.16): ordinal de INTENCIÓN **dentro de la barra corriente**. La identidad
        # lógica de la orden se ancla al tick de barra (estable dentro de la barra) + este
        # ordinal, de modo que un reintento intra-barra reproduce la MISMA identidad y la
        # liquidación la resuelve ``already_applied`` (no abre dos veces). Se reinicia al
        # cambiar de barra: una intención nueva de otra barra no colisiona con la anterior.
        self._v2_intent_bar = ""
        self._v2_intent_seq: dict[tuple[str, str], int] = {}
        self._active_orders: dict[str, str] = {}
        self._journal: list[SimJournalRow] = []
        # W-159-1 (Hueco C): los eventos de gestión de posición se acumulan aquí y se
        # publican UNA vez por turno en el spine durable (``decision_journal_entries``).
        # Antes vivían solo en ``_v2_journal`` (RAM del proceso) y en la fila agregada del
        # día: una adopción degradada no dejaba rastro con su ``entry``/``stop``/``atr`` y
        # el Hueco B quedó sin poder depurarse a posteriori.
        self._v2_position_journal_pending: list[Any] = []
        # V2.23/A9: última razón del gate determinista (para telemetría/durable).
        self._last_gate_reason: tuple[str, ...] = ("idle",)
        # M7 (auditoría .183) — tokens de control plane CADUCADO (watch/estrategia/turno).
        # No es un kill switch: el motor sigue gestionando lo abierto (cerrar reduce
        # riesgo) pero no puede ABRIR con un universo o una estrategia que ya no refresca.
        self._control_plane_stale: set[str] = set()

    async def readopt_positions(self) -> Mapping[str, Decimal]:
        """Readopta del espejo durable la posición abierta (Bloque 5 · P1-06 / G7).

        Invariante: BUY 100 → crash → restart → readopt deja ``_open`` con 100 para
        ese símbolo, de modo que un nuevo ``auto_turn`` con un BUY no apila un segundo
        BUY (misma guarda ``action == "BUY" and held > 0``). Sin ``position_store``
        (hermético) es un no-op. Idempotente: readoptar dos veces no altera el estado.

        V2.24/A9.1:
        * P1-02 — la lectura va scoped por ``(account_id, engine_id)``.
        * P2-01 — restaura también ``entry_price``/``high_watermark`` (el trailing no
          puede olvidar el máximo tras un reinicio).
        * P1-01/P2-02 — si hay lector canónico, RECONCILIA la proyección contra el
          estado financiero real antes de fiarse de ella.
        """
        if self._position_store is None:
            self._readopted = True
            return dict(self._open)
        account_id = self._account_id
        if not account_id:
            # P1-04: sin cuenta inequívoca no se readopta nada (fail-closed).
            self._readopted = True
            return dict(self._open)
        try:
            projection = await self._read_projection(account_id)
        except Exception:  # noqa: BLE001 — un fallo de lectura no debe inventar posición.
            logger.exception("auto_sim readopt_positions failed")
            # R-1 (verificación 2026-10-26 §8) — un fallo de lectura NO autoriza abrir.
            # Antes se marcaba ``_readopted = True`` con ``_open`` vacío y
            # ``_reconciliation`` sin entrada para esos símbolos: ``_openings_vetoed``
            # devolvía ``False`` y el tick siguiente ejecutaba un BUY (fail-open). El
            # símbolo se declara ``UNKNOWN`` (veta aperturas) y la readopción NO se
            # consume: un fallo transitorio se reintenta en el tick siguiente y sólo se
            # levanta el veto con una lectura correcta.
            self._reconciliation = {
                symbol: POSITION_PROJECTION_UNKNOWN for symbol in _watch_symbols()
            }
            self._projection_read_failed = True
            return dict(self._open)
        # La lectura de la proyección fue válida: el latch de lectura se libera AQUÍ (y
        # sólo aquí). La reconciliación puede volver a engancharlo si el canónico tampoco
        # se puede leer; un fallo posterior no deja el veto «a medias».
        self._projection_read_failed = False
        # V2.32/A12: la proyección durable YA guarda la versión de estrategia que abrió
        # la posición (migración 033). Al readoptarla se restaura ``_position_version``,
        # de modo que los fills de cierre posteriores al crash vuelven a atribuirse a la
        # misma versión (antes quedaban en NULL y truncaban la serie observada).
        authoritative = await self._reconcile_before_trusting(account_id, projection)
        # R-1 (cierre 2026-10-26) — si la reconciliación enganchó el latch porque el
        # CANÓNICO no se pudo leer, la readopción NO se consume: se adopta el espejo de la
        # propia fila (para poder cerrar lo materializado) y se reintenta en el tick
        # siguiente. Antes se marcaba ``_readopted = True`` y el veto de aperturas quedaba
        # enganchado para siempre: un fallo transitorio del lector canónico exigía
        # reiniciar el proceso.
        canonical_read_failed = self._projection_read_failed
        # La posición abierta se adopta desde la proyección Y, si la reconciliación
        # determinó un canónico fiable, también desde él (un espejo vacío no debe
        # hacer perder una posición real: P1-01).
        for symbol, qty in (authoritative or {}).items():
            if not qty or qty <= 0:
                continue
            # R-2 (verificación 2026-10-26 §8) — el canónico es de CUENTA; ``_open`` es de
            # MOTOR. Con más de una fila viva, adoptar el total dejaría a este motor
            # gestionando (y pudiendo vender) títulos de otro: medido con dos filas de 100
            # y canónico 200, ``held`` pasaba a 200 y un SELL de 200 no se clampaba. Se
            # conserva la cantidad de la PROPIA fila y se declara UNKNOWN (aperturas
            # vetadas); el cierre queda acotado a lo materializado por este motor.
            if await self._multiple_live_rows(account_id, symbol):
                self._multi_engine_symbols.add(symbol)
                own = projection.get(symbol)
                own_qty = getattr(own, "quantity", None)
                if own_qty is not None and own_qty > 0:
                    self._open[symbol] = own_qty
                self._reconciliation[symbol] = POSITION_PROJECTION_UNKNOWN
                logger.warning(
                    "auto_sim readopt keeps the engine row symbol=%s own=%s canonical=%s "
                    "(varias filas vivas: el total de la cuenta no es de este motor)",
                    symbol,
                    own_qty,
                    qty,
                )
                continue
            self._multi_engine_symbols.discard(symbol)
            self._open[symbol] = qty
        for symbol, row in projection.items():
            qty = row.quantity
            if qty and qty > 0:
                self._open.setdefault(symbol, qty)
                if row.entry_price is not None:
                    self._entry_price[symbol] = Decimal(str(row.entry_price))
                if row.high_watermark is not None:
                    self._high_price[symbol] = Decimal(str(row.high_watermark))
                if row.strategy_version_id:
                    self._position_version[symbol] = str(row.strategy_version_id)
                # AUTO 2.0 · P4: el plan operativo durable se guarda para rehidratarlo
                # EXACTO en el primer uso (``_v2_adopt_position``). Reconstruirlo por
                # ATR sería inventar un stop/objetivos distintos de los que el motor
                # estaba siguiendo antes del crash.
                if row.position_state:
                    self._v2_durable_plans[symbol] = dict(row.position_state)
        # W-159-3 (Hueco D): el LIBRO manda sobre el espejo. El espejo es una proyección y
        # puede arrastrar la versión de un round-trip anterior del mismo símbolo; el libro
        # declara quién abrió EL INVENTARIO VIVO. Se aplica después del bucle para que la
        # procedencia del hecho (no la copia) sea la que atribuya el cierre.
        for symbol, data in self._canonical_attribution.items():
            version = data.get("strategyVersion")
            if version and symbol in self._open:
                self._position_version[symbol] = str(version)
        if self._multi_engine_symbols:
            # R-2: el cierre queda acotado a la propia fila, pero el invariante agregado
            # (Σ filas vivas == canónico) NO se comprueba implícitamente. Se declara aquí,
            # en el único momento en que ya se detectó la ambigüedad (sin I/O por tick).
            try:
                await self.live_row_invariant_report(
                    account_id=account_id,
                    symbols=tuple(sorted(self._multi_engine_symbols)),
                )
            except Exception:  # noqa: BLE001 — un informe no puede tumbar la readopción.
                logger.exception("auto_sim live row invariant report failed")
        if canonical_read_failed:
            logger.warning(
                "auto_sim readopt incomplete: canonical positions unreadable "
                "(aperturas vetadas; se reintenta en el tick siguiente)"
            )
            return dict(self._open)
        self._readopted = True
        return dict(self._open)

    async def _settle(
        self,
        side: str,
        symbol: str,
        qty: Decimal,
        strategy_version_id: str | None = None,
        exit_order_id: str | None = None,
        cycle_id: str | None = None,
        exec_price: Decimal | None = None,
    ) -> _Settlement:
        """Liquida la orden SIM y separa lo MATERIALIZADO de lo que quedó PENDIENTE.

        AUTO-1A (P0): antes se devolvían TODOS los fills del schedule y el llamante los
        contaba con la cantidad PEDIDA, de modo que un llenado parcial (p. ej. 50 + 23,5
        de 100) producía una posición de 100 y un exit de 100 sobre 73,5 reales. Ahora se
        cruza el resultado del settlement con el outcome durable del apply: solo
        ``applied``/``already_applied`` movió dinero.
        """
        if self._require_durable_stores and self._finance_applier is None:
            # M8: en modo operativo NO existe el modo estructural. Confirmar el schedule sin
            # libro financiero marcaría fills como ``applied`` sin que nadie mueva dinero: el
            # hueco se declara como settlement FALLIDO, no como fill.
            logger.error(
                "auto_sim settlement rechazado: modo operativo sin finance_applier symbol=%s",
                symbol,
            )
            self._settlement_failures += 1
            return _Settlement(requested_qty=qty, failed=True)
        if self._exec_store is None:
            return _Settlement(requested_qty=qty)
        # Modo ESTRUCTURAL (smoke sin dinero, documentado en el módulo): sin
        # ``finance_applier`` no hay caja que mover y la traza queda no-``APPLIED`` por
        # construcción; el único hecho observable es la confirmación del schedule. Se
        # declara para no confundirlo con un apply fallido en modo dinero.
        structural = self._finance_applier is None
        venue = self._venue()
        logical_order_id = self._next_logical_order_id(symbol, side, exit_order_id)
        # W3 (v2.88.16): la EJECUCIÓN se ancla a la barra (tick de barra, estable dentro de
        # ella), no al minuto: el ``seed`` del book y la referencia de precio dejan de
        # cambiar entre reintentos del mismo intento, así que un reintento intra-barra
        # reproduce el MISMO ``execution_id`` y no mueve dinero dos veces. Lo que NO se toca
        # aquí es el marco de la PROtección (reloj independiente, diseño v2): su lectura
        # sigue siendo del tick corriente.
        bar_tick_now = self._v2_bar_tick()
        # W4: sin precio de ejecución NO se liquida (fail-closed). Antes decía
        # ``... or 100.0``: un precio FABRICADO, invisible sólo porque el script por defecto
        # ya valía 100.0. Ahora un precio ausente es un estado declarado, no un número.
        exec_mid = self._v2_price_exec(symbol, bar_tick_now)
        if exec_mid is None:
            self._v2_note_price_missing(symbol)
            return _Settlement(requested_qty=qty)
        # P-2: una salida disparada por el EXTREMO de la barra declara su precio de
        # ejecución (``min(open, stop)`` en long, ``max(open, stop)`` en short). Se
        # declara aquí y NO se recalcula: el nivel que disparó la orden es el que se
        # liquida, salvo que el hueco ya ofreciera un precio mejor.
        if exec_price is not None and exec_price > 0:
            exec_mid = float(exec_price)
        try:
            result, outcomes = await submit_simulated_order(
                self._exec_store,
                instrument_id=symbol,
                side=side,
                quantity=qty,
                # V2.23/A9 (P2-12): cuenta SIM inequívoca (nunca ``None`` en motor real).
                account_id=self._account_id,
                venue=venue,
                seed=fill_seed(bar_tick_now, symbol),
                base_mid=exec_mid,
                fill_chunks=_FILL_CHUNKS,
                order_id=(
                    f"auto-{side}-{symbol}-{exit_order_id}"
                    if exit_order_id
                    else f"auto-{side}-{symbol}-{bar_tick_now}"
                ),
                # V2.24/A9.1 (P1-03): namespace de identidad (no colisión entre cuentas).
                engine_id=self._engine_id,
                logical_order_id=logical_order_id,
                owner="auto-sim-worker",
                apply_finance=self._finance_applier,
                context_store=self._context_store,
                # V2.28/A10 (P1-02 real): atribuye el fill a la versión ACTIVE que lo
                # originó (``None`` si la propuesta no viene de una estrategia).
                strategy_version_id=strategy_version_id,
                # V2.47: el fill hereda el ciclo financiero para que el trazado inverso
                # posición→fill→reserva→decisión sea posible.
                cycle_id=cycle_id,
                # v2.88.25: la FUENTE real que construyó este precio viaja al contexto durable
                # del fill (migración 047). Ya NO hay que leer ``realPriceEnabled``
                # (configuración) como si fuera el precio de ESTA operación.
                price_source=self._v2_price_source_kind(),
                # v2.101: el instante del tick se sella en el fill. Sin él, el fill no tiene
                # día en la evidencia de equity y quedaba fuera de la curva (1.045 casos).
                created_at=self._time,
            )
        except Exception as exc:  # noqa: BLE001 — un fallo de settlement no tumba el motor.
            # Fail-closed: un problema al persistir contexto/aplicar dinero NO debe
            # romper el turno AUTOnomo (se degrada a "sin fill este tick"). El motor
            # reintentará; jamás se fabrica una posición sin settlement confirmado.
            #
            # O-1 (cierre 2026-10-27): el fallo deja de vivir SOLO en el log. Se cuenta en el
            # día (``settlementFailures``) y se journaliza con su motivo, para que «no hubo
            # fill» y «el fill falló» no sean la misma fila.
            logger.exception("auto_sim settle failed symbol=%s side=%s", symbol, side)
            self._settlement_failures += 1
            self._journal_position_event(
                symbol,
                SETTLEMENT_FAILED,
                at=self._v2_instant(),
                detail={
                    "side": side,
                    "requestedQty": str(qty),
                    "venue": venue,
                    "structural": structural,
                    "error": type(exc).__name__,
                },
            )
            return _Settlement(requested_qty=qty, structural=structural, failed=True)
        if not result.fills:
            return _Settlement(
                requested_qty=qty, outcomes=dict(outcomes or {}), structural=structural
            )
        vid = str(result.venue_order_id or "").strip() or f"sim-{side}-{symbol}"
        resolved_outcomes = dict(outcomes or {})
        applied: list[FillObservation] = []
        unapplied: list[FillObservation] = []
        for f in result.fills:
            if abs(f.qty_delta) <= 0:
                continue
            observation = FillObservation(
                side=side,
                venue=venue,
                execution_id=f.execution_id or f"{vid}#{f.fill_seq}",
                order_id=vid,
                qty=abs(f.qty_delta),
            )
            outcome = resolved_outcomes.get(observation.execution_id)
            if structural or outcome in _APPLIED_OUTCOMES:
                # Modo estructural: lo confirmado por el schedule ES el hecho.
                # Modo dinero: solo ``applied``/``already_applied`` movieron caja.
                applied.append(observation)
            else:
                # Un outcome no aplicado significa que NO materializó dinero: se
                # declara como pendiente, nunca como posición.
                unapplied.append(observation)
        if unapplied:
            logger.warning(
                "auto_sim settlement partial symbol=%s side=%s requested=%s applied=%s "
                "unapplied=%s outcomes=%s",
                symbol,
                side,
                qty,
                sum((o.qty for o in applied), Decimal("0")),
                sum((o.qty for o in unapplied), Decimal("0")),
                resolved_outcomes,
            )
        return _Settlement(
            requested_qty=qty,
            applied=tuple(applied),
            unapplied=tuple(unapplied),
            outcomes=resolved_outcomes,
            structural=structural,
        )

    async def load_book_equity(self, session: Any) -> None:
        """Lee ``PortfolioSummary.total_equity`` y lo deja como autoridad del turno.

        M14: la foto se **invalida ANTES** del ``await``. Si la lectura falla —o si el
        turno se cancela a mitad (``CancelledError`` no es ``Exception`` y no pasa por
        el ``except``)—, el turno siguiente no puede heredar la equity del anterior: la
        foto vigente es «no medido» y las aperturas quedan vetadas. La publicación es
        además una sola asignación: nadie observa una mezcla de equity nueva con estado
        viejo.
        """
        self._book_equity_required = True
        self._book_equity_snapshot = BookEquitySnapshot(unreadable=True)
        try:
            equity = await read_account_book_equity(session, self._account_id)
        except Exception:
            logger.exception(
                "auto_sim book equity unreadable account=%s",
                self._account_id,
            )
            return
        if equity <= 0:
            return
        self._book_equity_snapshot = BookEquitySnapshot(
            equity=float(equity),
            as_of=self._v2_instant(),
            unreadable=False,
        )

    def _v2_collect_packages(self) -> dict[str, Any]:
        """Consulta el decider una vez por símbolo en watch (propuestas del tick)."""
        packages: dict[str, Any] = {}
        for symbol in _watch_symbols():
            key = symbol.strip()
            if not key or key in packages:
                continue
            pkg = self._decider(key) if self._decider else None
            if pkg is not None:
                packages[key] = pkg
        return packages

    def _v2_bar_tick(self) -> int:
        """``W3`` — índice ENTERO de la barra de decisión corriente (estable dentro de ella).

        Es la unidad de identidad temporal del motor: con ella se anclan el ``seed`` del
        fill y la identidad lógica de la orden, de modo que un reintento dentro de la misma
        barra reproduce el MISMO ``execution_id`` (idempotente) en vez de una segunda
        ejecución. Es también el ``tick`` que recibe ``PriceScript`` para la referencia de
        EJECUCIÓN (un solo ancla temporal por barra).
        """
        return bar_tick(self._time, self._v2_granularity.decision.timeframe)

    def _v2_closed_bar_as_of(self) -> str:
        """``W3`` — ``as_of`` de la decisión: día de la última barra **CERRADA** (``B-1``).

        Es la frontera de NO lookahead que se pasa a los cargadores de barras (señal,
        régimen, ATR): la barra que contiene ``self._time`` NO está cerrada y no puede
        alimentar la decisión. Fail-closed: si el timeframe no permite expresar la frontera
        (barra sub-diaria o ilegible) devuelve ``""`` ⇒ ventana VACÍA ⇒ el motor no decide.
        """
        return last_closed_bar_day(self._time, self._v2_granularity.decision.timeframe)

    async def _v2_plan_tick(self, *, reuse_bar_datum: bool = False) -> Any:
        """Planifica el tick completo (entradas) por el pipeline AUTO 2.0.

        ``reuse_bar_datum`` (``W2`` · Fase A) es el short-circuit por barra: el reloj de
        DECISIÓN es D1, así que dentro de la MISMA barra el I/O de DATO del tick no puede
        aportar nada que la barra no haya decidido ya. Se omite —régimen, espejo durable de
        señales consumidas, contexto de cartera, órdenes pendientes, Adaptive y poda— y se
        trabaja con el dato de barra ya cargado en RAM.

        Lo que NO se omite es la DECISIÓN: ``plan_v2_tick`` es una función PURA y se
        recalcula con el estado corriente (posiciones, reservas vivas, señales consumidas,
        precio del tick). Eso es lo que mantiene el turno **semánticamente idéntico**: el
        embudo, el journal de decisión y la procedencia del ATR se publican igual, con el
        estado de la barra en el momento del turno (una señal nueva que aparezca a mitad de
        barra sigue decidiéndose), y solo desaparece el I/O redundante.
        """
        if not reuse_bar_datum or not self._v2_bar_datum_loaded():
            await self._v2_refresh_regime()
        # W4: el PRECIO se relee SIEMPRE, también con el dato de barra reutilizado. La
        # fuente se recompone por sesión/tick y el short-circuit por barra no la refresca:
        # sin esta relectura un turno dentro de la MISMA barra se quedaría sin ``execution``
        # y no podría marcar ni cerrar (fail-closed involuntario en el camino de precio real).
        await self._v2_refresh_price()
        self._v2_roll_consumed_bar()
        if not reuse_bar_datum:
            await self._v2_load_consumed_signals()
        regime = self._v2_regime()
        packages = self._v2_collect_packages()
        # Contexto de cartera (sector/ADV) y edge son datos EXTERNOS: se precargan una vez
        # por tick con las versiones realmente OBSERVADAS (no con una lista adivinada),
        # antes de construir las señales, para que la decisión lea estado coherente y no
        # haga I/O. También se refrescan las versiones de las posiciones abiertas (los
        # cierres se atribuyen a su versión y necesitan el mismo edge).
        versions = {
            _strategy_version_from_source(getattr(pkg, "source", None)) or "unversioned"
            for pkg in packages.values()
        }
        versions.update(self._position_version.values())
        if not reuse_bar_datum:
            await self._v2_refresh_trade_context(tuple(packages), tuple(sorted(versions)))
            # V2.88 / TOP3 cross-asset: evidencia LAB del campeón ACTIVE por instrumento.
            # Precarga UNA vez por tick (misma política que contexto/edge); el hot path lee
            # síncrono. Sin fuente inyectada es un no-op (Δ = 0, scoring histórico).
            await self._v2_refresh_evidence(packages, regime)
            # Órdenes pendientes (capital ya comprometido): se leen ANTES de construir la
            # foto para que la decisión del tick no pueda gastar dos veces el mismo cash.
            # AUTO-1b: con libro durable de reservas, la autoridad del compromiso son las
            # reservas vivas y estas trazas quedan como reconciliación (solo suma lo que
            # ninguna reserva cubre).
            await self._v2_refresh_open_orders()
        # V2.48/AUTO-8 — Adaptive: con el flag ON se construye la recomendación desde los
        # fills durables de las versiones observadas; con OFF (o sin store) es ``None`` y
        # el tick no paga ningún I/O nuevo (byte-idéntico). El dato de barra ya lo trae
        # construido, así que el turno reutilizado no lo relee.
        if reuse_bar_datum:
            adaptive = self._v2_bar_adaptive
        else:
            adaptive = (
                await self._v2_build_adaptive_plan(versions, regime)
                if self._v2_tunables.adaptive_enabled
                else None
            )
            self._v2_bar_adaptive = adaptive
        snapshot = self._v2_snapshot(regime)
        # V2.88.84 — la evidencia se lee UNA vez y se reusa para el plan y para la foto del
        # TOP3, de modo que la procedencia declarada por slot es la MISMA que la del scoring.
        evidence_lookup = self._v2_evidence_lookup(packages)
        # Handoff ESTUDIO → AUTO: las propuestas pendientes de la barra de decisión. Se
        # leen ANTES de construir las señales (la identidad adoptada viaja en la señal).
        await self._v2_load_daily_proposals()
        plan = plan_v2_tick(
            snapshot=snapshot,
            signals=self._v2_signals(packages),
            regime=regime,
            # ADR-047: el veto de entrada es POR SÍMBOLO; ``regime`` queda como
            # declaración del tick (``marketRegime``) y dial del gobernador.
            regime_by_symbol=self._v2_regime_by_symbol(),
            tunables=self._v2_tunables,
            as_of=self._time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            consumed_signal_ids=self._v2_consumed_signals,
            halted=self._v2_kill_switch_halted(),
            adaptive=adaptive,
            evidence=evidence_lookup,
            # Handoff: ``instrumento → propuesta validada``. Sin propuestas es ``None`` y
            # el tick es byte-idéntico al histórico.
            daily_proposals=self._v2_tick_proposals or None,
        )
        # AUTO-1b: el compromiso se hace DURABLE antes de emitir la orden. Sin persistir
        # no hay aprobación que emitir (fail-closed, ver ``_v2_persist_tick_reservations``).
        # Con el dato de barra reutilizado la llamada se conserva: si la barra aún aprobara
        # algo nuevo (señal distinta aparecida a mitad de barra) su reserva DEBE persistirse.
        await self._v2_persist_tick_reservations(plan)
        # Handoff ESTUDIO → AUTO: el desenlace de las propuestas que el motor evaluó. Se
        # sella DESPUÉS de persistir la reserva (la reserva es el compromiso; la traza va
        # después) y ANTES de emitir la orden, para que ``consumed_cycle_id`` sea el ciclo
        # que de verdad viaja a la orden.
        await self._v2_settle_daily_proposals(plan)
        # AUTO-11: la recomendación Adaptive se publica DESPUÉS de que el motor determinista la
        # consumió (mismo orden que AUTO-10: primero el dinero, después la traza). Así el journal
        # nunca registra una recomendación que no llegó a aplicarse.
        await self._v2_journal_adaptive_recommendation(adaptive)
        self._v2_journal.extend(plan.journal_entries)
        # AUTO Operational Monitor (``M2``): el journal de decisión del turno deja de vivir
        # sólo en RAM. Con el flag ON se persiste en el spine y ``SIGNAL``/``TOP_N``/``RISK``
        # pasan a ser enlazables por ``decision_id``/``cycleId``. Sin sink es un no-op.
        await self._v2_journal_entry_decisions(plan.journal_entries)
        # B-5 — el HOLD de la ACTIVE con motivo se declara con su PROPIO evento (no es una
        # oportunidad vetada: nadie la evaluó). Una sola vez por (símbolo, motivo, barra); el
        # mismo hecho no se reescribe en cada turno de 60 s de la misma barra diaria.
        hold_entries = self._v2_declare_active_strategy_holds(plan)
        if hold_entries:
            self._v2_journal.extend(hold_entries)
            await self._v2_journal_entry_decisions(hold_entries)
        # V2.45/AUTO-5 — embudo del día. El precio posterior de las rechazadas de ticks
        # ANTERIORES se mide con el tick corriente (es su primer precio DESPUÉS del
        # descarte); las filas de ESTE tick se incorporan después, porque una oportunidad no
        # puede ser su propio "precio posterior". Con el dato de barra reutilizado esto se
        # sigue midiendo con el precio VIVO del turno (es RAM, no I/O).
        self._v2_measure_opportunity_costs()
        self._v2_opportunities.extend(plan.opportunities)
        self._v2_seen_signals += int(getattr(plan, "seen_signals", 0) or 0)
        if not reuse_bar_datum:
            # La poda del espejo durable cubre la ventana ANTERIOR a la barra corriente, que
            # ya está podada cuando el dato de barra se cargó: dentro de la misma barra no
            # hay nada nuevo que podar.
            await self._v2_prune_consumed_signals()
        # V2.88.84 — TOP3 cross-asset: la foto durable de «qué 3 oportunidades ha rankeado
        # AUTO y por qué». Una por barra; declara por slot si el score usó evidencia LAB o histórico.
        await self._v2_persist_top3(
            plan, regime=regime, evidenced_symbols=frozenset(evidence_lookup or {})
        )
        return plan

    async def _v2_load_daily_proposals(self) -> None:
        """Carga las propuestas del parte adoptables para la barra de decisión.

        Se leen UNA vez por barra (``_v2_bar_proposals``), de modo que dos turnos dentro
        de la misma barra —el segundo ya sin la propuesta pendiente— conservan la MISMA
        identidad de señal: si no, el dedupe de señal se rompería a mitad de barra.

        Fail-closed: sin fuente inyectada, sin cuenta o sin frontera de barras no se
        adopta nada (Δ = 0) y la cadena declarará ``not_attributed``. Un fallo de lectura
        se registra y deja el tick sin propuestas: la traza no tumba el turno.
        """
        self._v2_tick_proposals = {}
        self._v2_tick_expired = ()
        source = self._daily_proposal_source
        if source is None or not self._account_id:
            return
        bar = self._v2_current_bar_start()
        if bar and bar == self._v2_bar_proposals_bar:
            self._v2_tick_proposals = self._v2_tick_proposal_map_from_bar()
            return
        decision_day = self._v2_closed_bar_as_of()
        if not decision_day:
            return
        instruments = [s.strip() for s in _watch_symbols() if s.strip()]
        try:
            adoption = await source(self._account_id, decision_day, instruments)
        except Exception:  # noqa: BLE001 — el handoff no puede tumbar el turno.
            logger.exception("auto_sim v2 daily proposal handoff failed (declared gap)")
            return
        try:
            by_key = adoption.by_instrument()
        except Exception:  # noqa: BLE001 — un contrato roto se declara, no se inventa.
            logger.exception("auto_sim v2 daily proposal handoff contract invalid")
            return
        self._v2_bar_proposals = dict(by_key)
        self._v2_bar_proposals_bar = bar
        self._v2_tick_proposals = self._v2_tick_proposal_map_from_bar()
        self._v2_tick_expired = tuple(getattr(adoption, "expired", ()) or ())
        if self._v2_tick_proposals:
            logger.info(
                "auto_sim v2 handoff ESTUDIO: %d propuesta(s) adoptable(s) day=%s bar=%s",
                len(self._v2_tick_proposals),
                decision_day,
                bar,
            )

    async def _v2_cycle_risk(self, fills: Sequence[Any]) -> dict[str, CycleRisk] | None:
        """AUTO-9/AUTO-10 — denominador de R, coste y RÉGIMEN por CICLO.

        READ-ONLY y aditivo: lee las reservas de los ciclos que aparecen en los fills del
        tick (``list_by_cycle_ids``, vivas y liberadas — un ciclo cerrado ya no tiene
        reserva viva) y las agrega con el módulo puro. El informe pasa de declarar "R no
        medible" a declararlo **medido o ausente ciclo a ciclo**, sin inventar ninguno.

        **Régimen durable (AUTO-10).** Con lector inyectado, el ``marketRegime`` de cada ciclo
        se lee del journal durable por ``decision_id`` derivado y CONFIRMANDO el
        ``payload['cycleId']`` (una fila que no confirma no se cree: la forma no prueba
        origen), y el productor pasa a declarar ``regime_not_found`` en vez de
        ``regime_not_durable``. Sin lector se conserva el comportamiento de ``AUTO-9``: el
        régimen sigue entrando a la rotación del tick como siempre, pero no se atribuye hacia
        atrás a un ciclo histórico.

        Un fallo de lectura devuelve ``None`` (degradación DECLARADA): el informe vuelve a
        su forma AUTO-7 en vez de estrechar o rotar con un R que no se pudo medir. El fallo
        del lector de régimen NO tumba el turno ni anula el R: los ciclos afectados quedan
        con su hueco declarado (``regime_not_found``).
        """
        store = self._reservation_store
        cycle_ids = sorted(
            {str(fill.cycle_id).strip() for fill in fills if str(fill.cycle_id or "").strip()}
        )
        if not cycle_ids or store is None:
            return None
        try:
            reservations = await store.list_by_cycle_ids(
                self._account_id, cycle_ids, limit=_V2_CYCLE_RISK_READ_LIMIT
            )
        except Exception:  # noqa: BLE001 — sin lectura no hay R; no se inventa.
            logger.exception("auto_sim v2 adaptive cycle risk read failed")
            return None
        if len(reservations) >= _V2_CYCLE_RISK_READ_LIMIT:
            # Lectura saturada: los ciclos que no cupieron quedan declarados sin reserva
            # (hueco honesto) en vez de recibir el denominador de otro ciclo.
            logger.warning(
                "auto_sim v2 adaptive cycle risk read saturated limit=%s cycles=%s",
                _V2_CYCLE_RISK_READ_LIMIT,
                len(cycle_ids),
            )
        regimes, durable = await self._v2_read_cycle_regimes(cycle_ids)
        return cycle_risk_from_reservations(
            cycle_ids,
            reservations,
            regime_by_cycle=regimes,
            regime_source_durable=durable,
        )

    async def _v2_build_adaptive_plan(
        self,
        versions: set[str],
        regime: str | None,
        *,
        gate: DataGateReading | None = None,
    ) -> AdaptivePlan | None:
        """V2.48/AUTO-8 — recomendación Adaptive desde los fills durables observados.

        Lee SOLO los fills de las versiones REALES del tick (una fila sin versión no se
        rota ni se asigna: el módulo puro la declara ``unknown``). Ante un fallo de
        lectura devuelve ``None`` (fail-closed): sin salud medible no se rota ni se
        estrecha nada — nunca se pausa a ciegas.

        **AUTO-12.** Con el mismo material se construye la lectura de CONFIANZA estadística
        (``build_adaptive_confidence_from_fills``) y se pasa al plan: el reparto encoge el peso
        de un edge medido sobre pocos ciclos en vez de tratarlo como una base de 180. Es pura
        (sin I/O nuevo); sin material la confianza queda vacía y el plan es el histórico.

        **AUTO-13.** Antes de repartir, el plan pasa por el gate de EVIDENCIA (§21/§22): la
        confianza se mide igual, pero solo se **usa para repartir** si la evidencia está sana.
        ``gate=None`` (el caso normal) lo compone el tick de sus hechos ya medidos; un llamante
        puede aportar una lectura ya graduada. Con el gate ``OK`` los argumentos y el plan son
        **byte-idénticos** al histórico de ``v2.53``.
        """
        adaptive_versions = {v for v in versions if v and v != "unversioned"}
        if not adaptive_versions or self._context_store is None:
            return None
        fills: list[Any] = []
        for version in adaptive_versions:
            try:
                fills.extend(
                    await self._context_store.list_for_strategy_version(
                        version, account_id=self._account_id
                    )
                )
            except Exception:  # noqa: BLE001 — sin lectura no hay salud; no se inventa.
                logger.exception("auto_sim v2 adaptive fill read failed version=%s", version)
                return None
        # El riesgo por ciclo se mide UNA vez y alimenta las dos lecturas (informe y confianza):
        # dos llamadas podrían divergir en silencio si la fuente se moviera entre ambas.
        cycle_risk = await self._v2_cycle_risk(fills)
        report = build_auto_self_evaluation(fills=fills, cycle_risk=cycle_risk)
        confidence = build_adaptive_confidence_from_fills(fills=fills, cycle_risk=cycle_risk)
        if confidence.by_strategy and not confidence.recent_available:
            # Hueco DECLARADO (no hay instantes legibles): la ventana reciente no se inventa.
            logger.warning("auto_sim v2 adaptive confidence gaps %s", confidence.as_dict()["notes"])
        # AUTO-19A — la INCERTIDUMBRE del edge (intervalo por episodios + ``edgeConfidence``) desde
        # el MISMO material ya leído: no añade I/O ni un segundo FIFO. Es un hecho MEDIDO, así que se
        # publica aunque el gate limite el encogimiento (igual que la banda): lo que el gate apaga es
        # el USO para repartir, no la evidencia. No mueve la regla ni el sello (``auto18-v1``).
        uncertainty = build_adaptive_uncertainty_from_fills(
            fills=fills, cycle_risk=cycle_risk, confidence=confidence
        )
        if uncertainty.by_strategy:
            gaps = sorted({note for row in uncertainty.by_strategy for note in row.notes})
            if gaps:
                # Huecos DECLARADOS del intervalo (sin ciclos o sin rachas suficientes). Un
                # intervalo que no se pudo medir no se disfraza de estrecho: se nombra.
                logger.info("auto_sim v2 adaptive uncertainty gaps %s", gaps)
        # AUTO-13 (§21/§22) — el gate de EVIDENCIA, entre medir y decidir. Se compone DESPUÉS de
        # la confianza porque la usa como insumo, y ANTES de repartir porque puede desactivarla
        # (``LIMITS``/``FREEZES``) o declarar el tick sin plan (``NO_ADAPT``). No añade I/O: son
        # hechos que el tick ya midió.
        reading = (
            gate
            if gate is not None
            else self._v2_adaptive_data_gate(report=report, confidence=confidence, regime=regime)
        )
        if reading.blocks_adaptation:
            # §21: evidencia durable muerta ⇒ el tick no adapta. El motor determinista decide sin
            # plan, y el journal de recomendación no escribe fila: el hueco se DECLARA, no se finge.
            logger.warning("auto_sim v2 adaptive data gate BLOCKED %s", reading.as_dict())
            return None
        if reading.limits_adaptation:
            # ``DEGRADED`` (deja de estrechar por evidencia fina) y ``STALE`` (además congela
            # reactivaciones): los dos conservan la protección y se declaran con nombre propio.
            logger.warning(
                "auto_sim v2 adaptive data gate %s %s", reading.status, reading.as_dict()
            )
        # V2.49/AUTO-8.1 — política versionada + estado de pausa previo (hysteresis y cooldown).
        # AUTO-11: el estado ya NO nace vacío en cada proceso — ``_v2_recover_adaptive_state`` lo
        # reconstruyó del journal durable en el arranque y ``_v2_next_paused_cycles`` lo encadena
        # turno a turno. Se copia ANTES de decidir porque la evidencia durable publica el contador
        # que ENTRÓ, no el de salida.
        self._v2_adaptive_paused_cycles_entered = dict(self._v2_adaptive_paused_cycles)
        policy = self._v2_adaptive_policy()

        # AUTO-13 (§24) — la RAMPA de reincorporación. Solo se aporta a las versiones que el lector
        # durable (o la transición observada en el proceso) declara RECUPERADAS (``reactivated_at``):
        # una que nunca estuvo pausada no tiene rampa y el plan sigue siendo el histórico. Se mide
        # con el MISMO material que la confianza (los fills del tick), así que no hay segundo
        # productor que pueda divergir.
        def _plan_with_recovery(evidence: dict[str, RecoveryEvidence]) -> AdaptivePlan:
            return build_adaptive_plan(
                report.by_strategy,
                to_market_regime(regime),
                policy=policy,
                paused_cycles=self._v2_adaptive_decision_cycles(reading, policy),
                by_regime=report.by_regime,
                # La protección NUNCA se apaga: la rotación recibe el mismo material. Lo que el gate
                # retira es el **uso** de la confianza para encoger el reparto —"no se estrecha por
                # evidencia que no es de fiar"— y, en ``STALE``, las reactivaciones nuevas (vía los
                # ciclos de decisión). La banda MEDIDA sigue publicándose en la evidencia (§29): lo
                # que se apaga es el encogimiento, no el hecho medido.
                confidence=confidence,
                shrink=not reading.limits_adaptation,
                recovery=evidence or None,
                # AUTO-19A — la incertidumbre es evidencia publicada: viaja aunque el gate límite el
                # encogimiento (lo medido no se oculta). No toca multiplicadores ni rotación: sin
                # ella el plan sería byte-idéntico al de ``AUTO-18``.
                uncertainty=uncertainty,
            )

        recovery = self._v2_adaptive_recovery_evidence(fills, cycle_risk, confidence)
        plan = _plan_with_recovery(recovery)
        # La transición pausa → activa se fecha en el tick en que OCURRE: si el plan acaba de
        # reactivar una versión, su rampa entra ya en ESTE tick con el escalón inicial. Sin esto la
        # versión correría un tick a peso pleno, que es justo el salto que §24 prohíbe. El recálculo
        # solo ocurre en ese tick (no paga I/O: es puro sobre el material ya leído).
        if self._v2_adaptive_observe_reactivations(plan):
            recovery = self._v2_adaptive_recovery_evidence(fills, cycle_risk, confidence)
            plan = _plan_with_recovery(recovery)
        if plan.recovery:
            # El estado operativo y el escalón se DECLARAN: un ``0.25`` congelado no se distinguiría
            # de una rampa que avanza si no viajara el motivo (``note``).
            logger.info(
                "auto_sim v2 adaptive recovery states %s",
                {
                    "operationalStates": dict(sorted(plan.operational_states.items())),
                    "recovery": {
                        version: value.as_dict() for version, value in sorted(plan.recovery.items())
                    },
                },
            )
        if plan.regime_undetermined:
            # §20 — el hueco del cruce ``strategy × regime`` se DECLARA con la salida declarada: sin
            # régimen determinado la rotación por régimen no aplica y decide la evidencia GLOBAL de
            # la estrategia. Campo propio (``regimeUndetermined``), separado del régimen del tick,
            # del estado operativo y del estado de datos del gate: los ejes no se mezclan (§29).
            logger.info(
                "auto_sim v2 adaptive regime undetermined %s",
                {
                    "regimeUndetermined": list(plan.regime_undetermined),
                    "fallback": "strategy_evidence",
                },
            )
        if plan.allocation.cell_used or plan.allocation.cell_fallback:
            # AUTO-14 (§20) — la base de CELDA del reparto se DECLARA: un multiplicador no dice por sí
            # solo si su número se midió en el régimen del tick o en el agregado global de la fila.
            # Campo propio (``allocationCells``) y separado del eje de evidencia, del estado operativo
            # y del gate de datos: los ejes no se mezclan. El frame sellado de ``allocation`` no se
            # toca; esto es la declaración del tick, como la del hueco de régimen.
            logger.info(
                "auto_sim v2 adaptive allocation cells %s",
                {
                    "allocationCells": {
                        "axis": plan.allocation.cell_axis,
                        "used": dict(sorted(plan.allocation.cell_used.items())),
                        "fallback": dict(sorted(plan.allocation.cell_fallback.items())),
                    },
                },
            )
        self._v2_adaptive_paused_cycles = self._v2_next_paused_cycles(plan)
        return plan

    def _v2_adaptive_data_gate(
        self, *, report: Any, confidence: Any, regime: str | None
    ) -> DataGateReading:
        """(AUTO-13) compone los HECHOS ya medidos del tick y gradúa la EVIDENCIA.

        No inventa insumos ni paga I/O: une lo que el tick ya midió —la completitud de la
        medición, la ventana reciente, la salud de la memoria durable, el contador del sink y la
        antigüedad del journal— y lo pasa a ``assess_data_gate`` (la ÚNICA casa de la gradación).

        La completitud que entra es la de los ejes que Adaptive **exige** para juzgar (resultados
        y riesgo), compuesta sobre las versiones del tick. NO se usa el ``measurement_completeness``
        de la confianza tal cual: ese combina también el eje **net-R opcional**, cuyo hueco cae por
        diseño al eje moneda (AUTO-9) y no es una deuda de datos — hacerlo degradaría el gate en
        cualquier despliegue sin coste medido y apagaría la confianza de AUTO-12 casi siempre.
        """
        reading = getattr(self, "_v2_adaptive_state_reading", None)
        rows = tuple(getattr(report, "by_strategy", ()) or ())
        completeness: MeasurementStatus | None = None
        if rows:
            completeness = combine_measurements(
                *(
                    combine_measurements(row.risk_measurement, row.results_measurement)
                    for row in rows
                )
            )
        recent_available = (
            bool(confidence.recent_available) if getattr(confidence, "by_strategy", None) else None
        )
        return assess_data_gate(
            sink_failures=int(getattr(self, "_v2_adaptive_sink_failures", 0) or 0),
            # AUTO-15: se DECLARA la procedencia de la racha (no cambia el estado): un 0 no puede
            # leerse como "el sink está sano" si en realidad no hay constancia durable.
            sink_failures_durable=bool(getattr(self, "_v2_adaptive_sink_failures_durable", False)),
            journal_age_cycles=self._v2_adaptive_gate_journal_age(),
            # P4 (auditoría .183): tri-estado, no un ``read_ok=True`` fabricado. Sin lectura
            # durable registrada el estado es ``unknown`` (no se leyó; tampoco se observó un
            # fallo); con lectura, ``ok``/``failed`` según lo que la lectura declaró. El gate de
            # producción degrada con ``unknown``: "no leí" ya no equivale a "está sano".
            read_state=("unknown" if reading is None else ("ok" if reading.read_ok else "failed")),
            measurement_completeness=completeness,
            recent_available=recent_available,
            regime_available=self._v2_regime_available(regime),
            unreadable_rows=0 if reading is None else int(reading.unreadable),
            policy_version_mismatch=(
                False if reading is None else bool(reading.policy_version_mismatch)
            ),
            insufficient_history=(False if reading is None else bool(reading.insufficient_history)),
            policy=self._v2_data_gate_policy(),
        )

    async def live_row_invariant_report(
        self,
        *,
        account_id: str | None = None,
        symbols: Sequence[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """R-2 — informe READ-ONLY de ``Σ filas vivas por MOTOR`` frente al canónico.

        El invariante que el defecto anterior rompía es agregado: la suma de las filas
        vivas de TODOS los motores debe igualar la posición de la CUENTA. Antes, cada
        motor podía escribir el total de la cuenta en su propia fila (300 con un worker y
        400 con dos) y la convergencia posterior a ``OK`` ocultaba la discrepancia.

        Este método NO cura ni corrige nada: una fila ya inflada no se repara con una
        heurística (el reparto entre motores no es determinable desde el total). Su único
        propósito es hacer la reconciliación EXPLÍCITA y medible por un operador. Un lector
        que falle se declara como no medible, nunca como cero.
        """
        store = self._position_store
        account = account_id or self._account_id or ""
        if store is None or not account:
            return {}
        engines_reader = getattr(store, "read_live_engines", None)
        if engines_reader is None:
            return {}
        candidates = (
            tuple(symbols)
            if symbols is not None
            else tuple(s for s in _watch_symbols() if s.strip())
        )
        if not candidates:
            return {}
        canonical_map: dict[str, Decimal] | None = None
        reader = self._canonical_positions_reader
        if reader is not None:
            try:
                canonical = await reader(account)
            except Exception:  # noqa: BLE001 — sin canónico el invariante no es medible.
                logger.exception("auto_sim live row invariant: canonical read failed")
            else:
                if canonical is not None:
                    canonical_map = {str(s): Decimal(str(q)) for s, q in dict(canonical).items()}
        try:
            own_rows = await store.read_projection(account, self._engine_id)
        except Exception:  # noqa: BLE001 — la fila propia ilegible se declara como tal.
            logger.exception("auto_sim live row invariant: own projection read failed")
            own_rows = {}
        report: dict[str, dict[str, Any]] = {}
        for symbol in candidates:
            try:
                engines = tuple(str(e) for e in await engines_reader(account, symbol))
            except Exception:  # noqa: BLE001 — sin lector fiable no hay informe.
                logger.exception(
                    "auto_sim live row invariant: engines read failed symbol=%s", symbol
                )
                continue
            if not engines:
                continue
            rows: dict[str, str] = {}
            unreadable: list[str] = []
            total = Decimal("0")
            for engine in engines:
                try:
                    projection = await store.read_projection(account, engine)
                except Exception:  # noqa: BLE001 — una fila ilegible no es un cero.
                    logger.exception(
                        "auto_sim live row invariant: engine row unreadable engine=%s symbol=%s",
                        engine,
                        symbol,
                    )
                    unreadable.append(engine)
                    continue
                row = projection.get(symbol)
                qty = Decimal(str(row.quantity)) if row is not None else Decimal("0")
                rows[engine] = str(qty)
                total += qty
            canonical_qty = (
                None if canonical_map is None else canonical_map.get(symbol, Decimal("0"))
            )
            delta = None if canonical_qty is None or unreadable else total - canonical_qty
            own = own_rows.get(symbol)
            entry: dict[str, Any] = {
                "engines": list(engines),
                "engineRows": rows,
                "unreadableEngines": unreadable,
                "ownRow": None if own is None else str(own.quantity),
                "projectedTotal": str(total),
                "canonical": None if canonical_qty is None else str(canonical_qty),
                "delta": None if delta is None else str(delta),
                "consistent": None if delta is None else delta == 0,
            }
            report[symbol] = entry
            if len(engines) > 1 or unreadable or (delta is not None and delta != 0):
                logger.warning(
                    "auto_sim live row invariant NOT proven symbol=%s engines=%s total=%s "
                    "canonical=%s delta=%s unreadable=%s",
                    symbol,
                    len(engines),
                    entry["projectedTotal"],
                    entry["canonical"],
                    entry["delta"],
                    unreadable,
                )
        return report

    async def _v2_flush_position_journal(self) -> None:
        """W-159-1 (Hueco C) — publica en el spine los eventos de gestión acumulados.

        ``_journal_position_event`` es síncrono y corre en varias ramas del turno; el
        sumidero M2 es asíncrono y va atado a la sesión del tick. Acumular y volcar al
        final del turno conserva la secuencia (los eventos se publican en el orden en que
        se produjeron) sin convertir en ``await`` cada punto de journalización.

        Best-effort declarado, igual que ``_v2_audit_emit``: sin sumidero es un no-op (Δ = 0
        en hermético) y un fallo se registra pero no tumba el turno (el dinero ya está
        comprometido aguas arriba). La cola se VACÍA siempre para no reintentar un hecho
        ya fallido en cada tick restante del día.

        M6: los eventos cuyo sink falló se REENCOLAN (acotado a ``_POSITION_JOURNAL_RETRY_CAP``,
        descartando los más antiguos con error) en vez de perderse: la evidencia no se pierde por
        un fallo transitorio del sink.
        """
        pending, self._v2_position_journal_pending = self._v2_position_journal_pending, []
        failed: list[Any] = []
        for entry in pending:
            ok = await self._v2_audit_emit(
                self._v2_seal_audit_identity(entry), label="position_management"
            )
            if not ok:
                failed.append(entry)
        if failed:
            keep = failed[-_POSITION_JOURNAL_RETRY_CAP:]
            if len(keep) < len(failed):
                logger.error(
                    "auto_sim position journal overflow: %d eventos descartados",
                    len(failed) - len(keep),
                )
            self._v2_position_journal_pending = keep + self._v2_position_journal_pending

    async def auto_turn(self) -> TurnReport:
        """Decide por símbolo y actúa con autoridad (Single Decision Spine).

        V2.23/A9 (Bloque 3): cada ``DecisionPackage`` DEBE pasar por el RiskGate
        determinista (``risk_gate_auto_paper_dry``) y la Simulation Gate antes de
        tocar el settlement SIM. NO existe el atajo ``DecisionProvider -> _settle``:
        el kill switch (fail-closed) y el venue AUTO-only (``simulation_gate_allows``)
        vetan primero; solo una propuesta que el RiskGate admite y que
        ``derive_execution_plan`` convierte en plan se liquida (BUY abre / SELL reduce).
        Un ``SELL qty > held`` NUNCA sobreexcede: se clampa a la posición (o se veta).
        """
        self._advance()
        venue = self._venue()
        report = TurnReport(decided=0, venue=venue)
        kill = self._kill_active()
        venue_ok = simulation_gate_allows(venue)
        reasons: list[str] = []
        # V2.24/A9.1 (P1-04): AUTO SIM exige cuenta inequívoca. En el camino durable
        # real (``require_account_id``) sin account_id NO se opera: fail-closed, jamás
        # una traza ``account_id=None``. La composición real ya bloquea el arranque;
        # esto es defensa en profundidad (el spine no puede saltarlo).
        account_required = self._require_account_id and not self._account_id
        if account_required:
            reasons.append("account_id_required")

        def _veto(reason: str) -> None:
            reasons.append(reason)
            report.vetoes += 1

        # AUTO 2.0 (V2): planifica las entradas del tick UNA vez (rankeo + decisión +
        # TradePlan) antes del bucle. El resultado lo consume el bucle por símbolo, y
        # sigue pasando por el MISMO spine (kill/sim-gate/RiskGate/settlement).
        self._v2_last_exit_reasons = {}
        self._v2_last_exit_label = {}
        self._v2_pending_exit = {}
        # S-6: el plan y el veredicto F5 son POR TURNO. Un plan del turno anterior no
        # puede autorizar una salida de éste (el mark y los motivos han cambiado).
        self._v2_last_exit_plans = {}
        self._v2_last_exit_reviews = {}
        if self._v2_enabled and not kill and venue_ok and not account_required:
            # W2 · Fase A: con el dato de barra ya cargado, el turno REUTILIZA ese dato y
            # se ahorra el I/O redundante (régimen, espejo de consumo, contexto de cartera,
            # órdenes pendientes, Adaptive, poda). La DECISIÓN se recalcula igual (función
            # pura) para que la contabilidad del tick no cambie: embudo, journal y
            # procedencia del ATR se publican en TODOS los turnos de la barra.
            same_bar_datum = self._v2_bar_short_circuit_applies()
            if same_bar_datum:
                self._v2_bar_short_circuit_ticks += 1
            try:
                self._v2_plan = await self._v2_plan_tick(reuse_bar_datum=same_bar_datum)
                if not same_bar_datum:
                    self._v2_bar_note_plan()
            except Exception:  # noqa: BLE001 — sin plan V2 se degrada a no operar.
                logger.exception("auto_sim v2 plan failed (tick sin entradas)")
                self._v2_plan = None
                # Fail-closed: un plan que no se materializó no acredita la barra, así que
                # el turno siguiente vuelve a releer el dato en vez de heredar el hueco.
                self._v2_bar_plan_bar = ""

        for symbol in _watch_symbols():
            symbol = symbol.strip()
            if not symbol:
                continue
            report.decided += 1
            if account_required:
                _veto("account_id_required")
                continue
            held = self._open.get(symbol, Decimal("0"))
            # V2.23/A9 (Bloque 6 · G8/G9): la protección tiene prioridad sobre el
            # decider cuando hay posición. Emite un SELL del total a través del MISMO
            # spine (kill/sim-gate/RiskGate/posición), nunca un atajo.
            raw_price = self._v2_price_exec(symbol, self._v2_bar_tick())
            if raw_price is None:
                # W4: precio AUSENTE ⇒ este símbolo no se marca/no genera señal (fail-closed
                # declarado). Antes ``... or 0`` producía un ``Decimal("0")`` que el
                # ``if price > 0`` descartaba EN SILENCIO: mismo efecto, sin declararlo.
                self._v2_note_price_missing(symbol)
                continue
            price = Decimal(str(raw_price))
            if held > 0 and price > 0:
                # Mantiene el máximo desde la entrada para el trailing (G9).
                prev_high = self._high_price.get(symbol, Decimal("0"))
                if price > prev_high:
                    self._high_price[symbol] = price
            prot: str | None = None
            v2_pkg: DecisionPackage | None = None
            # P-2: precio de ejecución DECLARADO cuando la salida la dispara un extremo
            # de la barra (stop objetivo). ``None`` ⇒ se liquida al precio de siempre.
            settle_price: Decimal | None = None
            if self._v2_enabled:
                # AUTO-2 (criterio de salida) · V2.42 slice 2c: con el motor V2 ON la
                # política legacy NO se evalúa — ni siquiera el caso ``held == 0``/``price
                # <= 0`` que antes la llamaba para acabar devolviendo ``None``. Es una
                # condición ESTRUCTURAL ("``ProtectionConfig`` sin ninguna lectura con
                # ``AUTO_ENGINE_SIM_V2=1``"), no de valor, y el sensor del día golden la
                # hace fallar si alguien vuelve a meter la llamada en el camino V2.
                if held > 0 and price > 0:
                    # AUTO 2.0 (V2): gestión por PositionManager (PositionState + ExitPlan
                    # + PositionDecision). AUTO-2: el ratchet de stop se aplica y se
                    # persiste AQUÍ mismo (aunque no haya orden).
                    bar_low, bar_high = self._v2_bar_extremes(symbol)
                    v2_pkg = await self._v2_position_package(
                        symbol, price, bar_low=bar_low, bar_high=bar_high
                    )
                    exit_reasons = self._v2_last_exit_reasons.get(symbol, ())
                    reasons.extend(exit_reasons)
                    # P-2: si el motivo DECISORIO es el stop (u objetivo) y la barra trajo
                    # extremos, el fill se declara al nivel que disparó la orden.
                    # ``protective_fill_price`` devuelve ``None`` para cualquier otro
                    # motivo o cuando no hay extremos (Δ = 0 en el camino hermético).
                    if exit_reasons and (bar_low is not None or bar_high is not None):
                        fill_price = protective_fill_price(
                            self._v2_positions.get(symbol),
                            open_price=float(price),
                            primary_reason=exit_reasons[0],
                        )
                        if fill_price is not None:
                            settle_price = Decimal(str(fill_price))
            else:
                prot = protection_exit_reason(
                    self._protection,
                    held=held > 0,
                    entry=self._entry_price.get(symbol, Decimal("0")),
                    high=self._high_price.get(symbol, Decimal("0")),
                    price=price,
                    minute=self._minute,
                )
                # T1 parcial ya tomado ⇒ no volver a disparar T1 (el resto lo gestiona
                # trailing/stop/sesión). Evita vender 30% en cada tick por encima de T1.
                if prot == "t1_exit" and symbol in self._t1_done:
                    prot = None
            pkg: DecisionPackage | None
            if v2_pkg is not None:
                # Intención V2 (reduce/sell) con su geometría por operación.
                pkg = v2_pkg
            elif prot is not None:
                # V2.24/A9.1 (P2-06): T1 PARCIAL. La protección puede vender solo una
                # fracción (p. ej. 30%) y dejar el resto gestionado por trailing/stop.
                fraction = protection_exit_fraction(self._protection, prot)
                sell_qty = held * Decimal(str(fraction)) if 0 < fraction < 1 else held
                pkg = DecisionPackage(
                    action="SELL",
                    instrument_id=symbol,
                    quantity=float(sell_qty),
                    source=f"protection:{prot}",
                )
                reasons.append(prot)
            elif self._v2_enabled:
                # AUTO 2.0 (V2): la propuesta viene del plan del tick (TradePlan →
                # DecisionPackage), no del decider directo.
                plan = self._v2_plan
                if plan is not None and symbol in self._v2_reservation_blocked:
                    # AUTO-1b: la reserva de esta aprobación NO llegó a ser durable ⇒ la
                    # orden no se emite (no existe aprobación sin reserva durable).
                    _veto(RESERVATION_UNMEASURABLE)
                    continue
                if symbol in self._v2_reservation_carryover:
                    # AUTO-1b: ya hay una reserva VIVA de un tick anterior para este
                    # instrumento (orden sin fill): no se apila un segundo compromiso.
                    _veto(RESERVATION_ALREADY_LIVE)
                    continue
                pkg = plan.entry_packages.get(symbol) if plan is not None else None
            else:
                pkg = self._decider(symbol) if self._decider else None
            action = str(getattr(pkg, "action", "HOLD")).upper() if pkg else "HOLD"
            if action not in {"BUY", "SELL"}:
                _veto("hold_no_op")
                continue
            # Narrowing explícito para mypy: una acción BUY/SELL sólo puede venir de un
            # ``pkg`` no nulo (``action`` se deriva de él). Sin esto, el tipo
            # ``DecisionPackage | None`` no estrecha y el RiskGate/plan lo rechazan.
            assert pkg is not None
            qty = positive_quantity(getattr(pkg, "quantity", None))
            if qty is None:
                # P9: una cantidad ``NaN``/``inf``/basura ya no revienta el tick en el
                # ``Decimal(...).quantize()`` ni viaja al libro: se veta y se declara.
                _veto("non_positive_qty")
                continue
            qty = qty.quantize(Decimal("0.000001"))
            if qty <= 0:
                _veto("non_positive_qty")
                continue
            # 1) Simulation Gate (kill fail-closed ANTES de nada AUTO).
            # P-1 (cierre 2026-10-26) — el latch DURABLE de la parada también veta
            # APERTURAS en el camino legacy (``AUTO_ENGINE_SIM_V2=0``): ``kill`` sólo
            # consulta la fuente de entorno, así que un HALT recuperado del espejo (o el
            # placeholder ``KILL_STATE_UNREADABLE``) no llegaba hasta aquí y un BUY podía
            # abrir con el motor parado. SELL sigue permitido: reducir/cerrar nunca
            # empeora el riesgo (mismo invariante que la reconciliación de posición).
            if kill or (action == "BUY" and self._v2_kill_switch_halted()):
                _veto("kill_switch_active")
                continue
            # 2) Simulation Gate: venue AUTO-only (paper/simulated).
            if not venue_ok:
                _veto("venue_not_auto_allowed")
                continue
            # 3) RiskGate determinista (nunca IA ejecuta por sí). Si no admite la
            #    propuesta o no deriva plan, NO se liquida nada.
            gate = risk_gate_auto_paper_dry(
                pkg,
                kill_switch_active=kill,
                venue=venue,
            )
            if not gate.allow_proposal:
                reasons.extend(r.value for r in gate.reasons)
                report.vetoes += 1
                continue
            plan = derive_execution_plan(pkg, venue=venue, kill_switch_active=kill)
            if plan is None or plan.action not in {"BUY", "SELL"}:
                _veto("no_execution_plan")
                continue
            # 4) Posición: BUY solo abre si no estoy expuesto; SELL solo contra una
            #    posición. SELL > held se clampa (veto upstream de sobreventa, nunca
            #    se manda 150 contra 100).
            if action == "BUY" and held > 0:
                continue  # ya expuesto: sin apilar (HOLD implícito).
            # V2.24/A9.1 (P1-01): una proyección divergente/no verificada NO autoriza
            # abrir. (SELL sí se permite: reducir/cerrar nunca empeora el riesgo.)
            # M7: con el control plane caducado el motivo es suyo (no se disfraza de
            # «reconciliación»): el operador debe poder leer por qué no se abrió.
            if action == "BUY" and self._control_plane_stale:
                _veto(CONTROL_PLANE_STALE)
                continue
            if action == "BUY" and self._openings_vetoed(symbol):
                _veto("position_reconciliation_not_ok")
                continue
            if action == "BUY" and self._book_equity_snapshot.unreadable:
                _veto("book_equity_unreadable")
                continue
            if action == "SELL" and held <= 0:
                _veto("sell_without_position")
                continue
            exec_qty = min(qty, held) if action == "SELL" else qty
            if exec_qty <= 0:
                _veto("clamped_sell_to_zero")
                continue
            if action == "SELL" and exec_qty < qty:
                _veto("sell_overshoot_clamped")
            if action == "SELL" and symbol in self._multi_engine_symbols:
                # R-2 (cierre 2026-10-26) — el cierre se PERMITE (reducir no empeora el
                # riesgo), pero se declara que la cantidad NO está reconciliada: con varios
                # motores vivos el total de la cuenta no identifica a esta fila, así que una
                # fila ya inflada dimensiona la venta por encima de lo propio. No se corrige
                # aquí (no hay reparto determinable): requiere reconciliación de operador.
                reasons.append(POSITION_ROW_UNRECONCILED)
            # S-6 (auditoría 2026-10-26 §5.8) — la salida CONSULTA F5 antes de emitirse,
            # sobre el mismo ``ExitPlan`` que la decidió, y declara el veredicto. No la
            # bloquea (contrato en ``auto_exit_gate``: la salida protectora reduce riesgo y
            # el venue es el simulador), pero deja de ser un hueco mudo: un DENY queda en
            # el journal con sus motivos y con la exención aplicada.
            if action == "SELL":
                review = self._consult_exit_permission(symbol, at=self._v2_instant())
                if review.denied:
                    report.exit_permission_denied += 1
            report.proposals += 1
            # V2.28/A10 (P1-02 real): atribuye el fill a la versión ACTIVE. La apertura
            # aporta la versión desde el ``source`` de la propuesta; el CIERRE (venta de
            # protección) hereda la versión que abrió la posición para no dejar la serie
            # con compras sin ventas. ``None`` = sin atribución (spine determinista).
            proposed_version = _strategy_version_from_source(getattr(pkg, "source", None))
            effective_version = proposed_version or self._position_version.get(symbol)
            # V2.44 · F9: la salida deja una reserva VIVA y DURABLE antes de emitirse. Con
            # fill parcial la cola queda comprometida (no se re-emite por duplicado) y un
            # reinicio la ve como compromiso explícito en vez de adivinar por las trazas.
            # V2.43.3 (P1-4, política B): si el intent de la salida no llega a ser durable
            # NI siquiera en su forma de emergencia, ``_v2_reserve_exit`` devuelve ``None`` y
            # la orden NO se emite (fail-closed): una salida sin identidad durable es una
            # salida que un reinicio no podrá reconciliar.
            if action == "SELL" and self._v2_enabled and self._reservation_store is not None:
                exit_order_id = await self._v2_reserve_exit(
                    symbol=symbol,
                    qty=exec_qty,
                    price=price,
                    sector=self._v2_sector(symbol, pkg),
                    at=self._v2_instant(),
                )
                if exit_order_id is None:
                    _veto("exit_intent_not_durable")
                    continue
            else:
                exit_order_id = None
            # v2.88.25: el ciclo se captura UNA vez y lo comparten el settlement y los hechos
            # durables (orden de entrada / liquidación) para que todos apunten al mismo ciclo.
            cycle_id = self._v2_cycle_for(symbol)
            # P-2 (verificación 2026-10-26 §8) — UN ÚNICO precio de ejecución para TODO el
            # cierre. El settlement ya liquidaba al nivel del stop (``exec_price``), pero el
            # fill aplicado, el P&L realizado y el ``PositionState`` seguían usando el
            # ``open(B)``: medido con entrada 100 · qty 200 · open 100 · low 80 · stop 95, el
            # fill quedaba en 95 y el P&L en 0 (la pérdida real es 1.000). El precio
            # declarado se propaga aquí una sola vez; sin extremo ni motivo protector es
            # exactamente ``price`` (Δ = 0 en el camino hermético).
            realized_price = (
                settle_price if settle_price is not None and settle_price > 0 else price
            )
            settlement = await self._settle(
                action.lower(),
                symbol,
                exec_qty,
                strategy_version_id=effective_version,
                # V2.43.3 (P0-2): la identidad del INTENT viaja a la orden para que cada
                # ``execution_id`` quede atribuido a la salida concreta (y no a un contador
                # de proceso que un reinicio reinicia).
                exit_order_id=exit_order_id,
                # V2.47: el fill (entrada o salida) queda atado a su ciclo financiero.
                cycle_id=cycle_id,
                # P-2: precio declarado por el extremo que disparó la orden (o ``None``).
                exec_price=settle_price,
            )
            # AUTO-1A (P0) — SOLO lo materializado es posición/riesgo/protección. La
            # cantidad PEDIDA (`exec_qty`) se sigue liquidando y se journaliza como
            # orden; la cantidad APLICADA es la que mueve el libro. Antes se contaba la
            # pedida, de modo que un llenado parcial (73,5 de 100) dejaba una posición
            # inflada y un exit dimensionado contra ella.
            for pending in settlement.unapplied:
                self._emit(
                    JOURNAL_FILL_UNAPPLIED,
                    pending.venue,
                    pending.execution_id,
                    pending.side,
                    pending.qty,
                )
            if not settlement.applied:
                # Ningún chunk materializó dinero: no hay fill que contar. El capital
                # queda comprometido (libro de órdenes pendientes) y el journal lo dice.
                _veto(FILL_NOT_MATERIALIZED)
                continue
            applied_qty = settlement.applied_qty
            if settlement.is_partial:
                reasons.append(FILL_PARTIALLY_MATERIALIZED)
            # v2.88.25 — si esta venta CIERRA el ciclo (``new_held <= 0``) se sella el hecho
            # durable de liquidación DESPUÉS de persistir la posición. Se declara aquí porque
            # el instante del cierre solo se conoce en la rama SELL.
            closed_cycle_id: str | None = None
            close_reason: str | None = None
            self._emit(
                "order", venue, None, action.lower(), exec_qty, structural=settlement.structural
            )
            # S-3 — la orden de salida ya EXISTE (materializada arriba): sólo ahora el FSM
            # puede declarar ``EXIT_PENDING``. Antes se escribía al decidir, así que un
            # ``hold`` del manager o un veto posterior dejaba la posición «pedida» sin venta.
            if action == "SELL" and self._v2_enabled:
                await self._v2_confirm_exit_emitted(symbol, at=self._v2_instant())
            # v2.88.25 — la ORDEN DE ENTRADA deja de vivir sólo en el journal RAM: con el
            # sumidero M2 (flag ``AUTO_OPERATIONAL_AUDIT``) se sella como hecho durable por
            # ciclo, con la cantidad PEDIDA vs MATERIALIZADA y la FUENTE de precio real. Sin
            # sink es un no-op (Δ = 0). Sólo ENTRADA: la salida ya es durable en
            # ``auto_exit_orders``.
            if action == "BUY":
                await self._v2_journal_entry_order(
                    order_id=settlement.applied[0].order_id,
                    instrument_id=symbol,
                    requested_qty=exec_qty,
                    applied_qty=applied_qty,
                    partial=settlement.is_partial,
                    cycle_id=cycle_id,
                    # O-2: el hecho durable declara si se liquidó sin caja.
                    structural=settlement.structural,
                )
            for o in settlement.applied:
                self._emit(
                    "fill",
                    o.venue,
                    o.execution_id,
                    o.side,
                    o.qty,
                    structural=settlement.structural,
                )
                self._record_applied_event(symbol, o, realized_price)
            first_execution_id = settlement.applied[0].execution_id
            if action == "BUY":
                materialized = held + applied_qty
                self._emit(
                    "position_open",
                    venue,
                    first_execution_id,
                    "buy",
                    applied_qty,
                    # V2.45/AUTO-5 — la apertura se atribuye a la estrategia que la propuso.
                    strategy_version=effective_version,
                )
                self._open[symbol] = materialized
                # AUTO 2.0 (V2): la señal de esta barra queda CONSUMIDA al ejecutarse la
                # entrada. Si la posición muere después dentro de la misma barra (stop,
                # exit-only), esa misma señal no puede re-abrir: es la MISMA oportunidad
                # ya tomada, no una nueva.
                if self._v2_enabled:
                    await self._v2_mark_signal_consumed(symbol)
                # Referencia de protección: entrada = precio del tick de apertura.
                if held <= 0 and price > 0:
                    self._entry_price[symbol] = price
                    self._high_price[symbol] = price
                elif held > 0 and price > 0 and applied_qty > 0:
                    # M15: una ampliación mezcla el coste; el P&L parcial y el no realizado
                    # se miden contra el coste medio ponderado, no contra la primera entrada.
                    prior = self._entry_price.get(symbol)
                    if prior is not None and prior > 0:
                        self._entry_price[symbol] = _blend_entry_price(
                            prior, held, price, applied_qty
                        )
                # V2.28/A10 (P1-02 real): recuerda la versión que abrió la posición para
                # atribuir después los fills de cierre. Solo al abrir desde plano (una
                # ampliación sobre posición viva conserva la versión original).
                if held <= 0 and effective_version:
                    self._position_version[symbol] = effective_version
                # AUTO 2.0 (V2): crea el PositionState de la operación desde el
                # TradePlan que la originó (gestiona T1/T2/stop/trailing por estado).
                # AUTO-1A: con la cantidad MATERIALIZADA (T1/trailing/stop se calculan
                # sobre la posición real, no sobre lo pedido).
                if self._v2_enabled and held <= 0:
                    await self._v2_track_entry(symbol, price, applied_qty)
                await self._persist_position(symbol, materialized)
                # F2-1 — la POSICIÓN materializada por esta operación deja un hecho durable
                # append-only (solo al ABRIR desde plano). Así la escalera ``fill → posición``
                # sube con TRAZA y la reutilización del símbolo no borra la historia del ciclo.
                if held <= 0:
                    await self._v2_journal_position_materialized(
                        instrument_id=symbol,
                        quantity=applied_qty,
                        entry_price=price,
                        execution_id=first_execution_id,
                        strategy_version=effective_version,
                        cycle_id=cycle_id,
                    )
                report.opened += 1
                # AUTO-1b: lo MATERIALIZADO deja de ser reserva y pasa a ser posición.
                # Con fill parcial la liberación es parcial y la cola sigue comprometida.
                await self._v2_release_reservations_for_fill(
                    symbol=symbol, filled_qty=applied_qty, at=self._v2_instant()
                )
            else:
                # AUTO-1A — invariante DURO ``exit_qty <= materialized_position``. El
                # settlement ya va clampado a ``held``, así que esto es defensa en
                # profundidad: se declara y se aplana, nunca se inventa un corto.
                if applied_qty > held + _QTY_EPS:
                    _veto(EXIT_QTY_OVER_POSITION)
                new_held = max(Decimal("0"), held - applied_qty)
                # V2.43/AUTO-3 — P&L REALIZADO de lo MATERIALIZADO en esta venta. Es la
                # pata que faltaba para que la equity de marca no "olvide" una pérdida
                # cuando la posición se cierra. No emite filas ni cambia decisiones: solo
                # alimenta la serie de drawdown del gobernador (que solo se lee con el
                # flag ON). Referencia = entrada de la posición (la misma que usa la
                # protección); sin referencia no se inventa P&L.
                entry_ref = self._entry_price.get(symbol)
                if entry_ref is not None and applied_qty > 0:
                    # P-2: el P&L se mide contra el precio DECLARADO del cierre (stop/gap),
                    # no contra el ``open`` que sólo se usó para decidir.
                    self._sim_realized_pnl += (realized_price - entry_ref) * applied_qty
                # V2.45/AUTO-5 — MAE/MFE del ``mfe_mae`` del PositionState ANTES de reducir:
                # tras el cierre puede desaparecer del mapa y la medición se perdería. Se
                # RECOGE tal cual (si falta alguna pata, se declara sin números).
                mfe_mae = self._v2_mfe_mae_snapshot(symbol)
                # AUTO 2.0 (V2): actualiza el PositionState tras la venta (parcial o
                # total) para que T1/T2 no se re-disparen en ticks sucesivos.
                if self._v2_enabled:
                    await self._v2_track_reduce(
                        symbol,
                        applied_qty,
                        # P-2: el estado final usa el MISMO precio que el fill y el P&L.
                        realized_price,
                        self._v2_last_exit_reasons.get(symbol, ()),
                    )
                # V2.44 · F9 — lo vendido deja de ser reserva de salida; con fill parcial la
                # cola sigue viva (la MISMA orden no puede duplicarse al reiniciar).
                await self._v2_release_reservations_for_fill(
                    symbol=symbol,
                    filled_qty=applied_qty,
                    at=self._v2_instant(),
                    side=SIDE_SELL,
                )
                if prot == "t1_exit" and new_held > 0:
                    # T1 parcial ejecutado: marca para no repetirlo.
                    self._t1_done.add(symbol)
                if new_held <= 0:
                    close_reason = (
                        self._v2_last_exit_label.get(symbol, "")
                        if self._v2_enabled
                        else (prot or "")
                    )
                    closed_cycle_id = cycle_id
                    self._emit(
                        "position_close",
                        venue,
                        first_execution_id,
                        "sell",
                        applied_qty,
                        # V2.42 slice 2c: el motivo del cierre viaja en la fila del día.
                        # Con V2 ON es la etiqueta del motivo DECISORIO del plan
                        # (``time_exit``/``thesis_exit``/...); en el camino legacy, el
                        # motivo de protección (``protective_stop``/``t1_exit``/...).
                        # Un cierre del decider sin motivo de protección queda sin
                        # declarar y el día lo cuenta como ``undeclared``.
                        reason=close_reason,
                        # V2.45/AUTO-5 — el CIERRE hereda la versión que abrió la posición
                        # (para no dejar la serie con compras sin ventas).
                        strategy_version=effective_version,
                    )
                    # V2.45/AUTO-5 — MAE/MFE de la OPERACIÓN cerrada (medido en el JSONB y
                    # recogido aquí). Sin las dos patas no se publica: el día lo declara.
                    self._v2_record_operation_measurement(symbol, effective_version, mfe_mae)
                    report.closed += 1
                    self._entry_price.pop(symbol, None)
                    self._high_price.pop(symbol, None)
                    self._t1_done.discard(symbol)
                    # Posición cerrada: la atribución de versión deja de aplicar.
                    self._position_version.pop(symbol, None)
                self._open[symbol] = new_held
                await self._persist_position(symbol, new_held)
                # v2.88.25 — CIERRE del ciclo: el hecho durable de liquidación se sella DESPUÉS
                # de persistir la posición. Es lo único que enciende ``SETTLEMENT`` (un
                # ``CYCLE_CLOSED`` reconstruido de fills NO es una liquidación). Sin sink, no-op.
                if closed_cycle_id is not None:
                    await self._v2_journal_cycle_settlement(
                        instrument_id=symbol,
                        closed_qty=applied_qty,
                        cycle_id=closed_cycle_id,
                        exit_reason=close_reason,
                        # O-2: el settlement declara si se cerró sin mover caja.
                        structural=settlement.structural,
                    )
            report.orders += 1
            report.fills += len(settlement.applied)
        # S-3 — las salidas decididas que no emitieron orden se declaran aquí: la posición
        # conserva su estado real (nunca ``EXIT_PENDING`` sin venta) y el motivo no se pierde.
        self._v2_flush_unemitted_exits()
        await self._v2_flush_position_journal()
        self._v2_bar_note_settlement()
        self._last_gate_reason = tuple(dict.fromkeys(reasons))
        return report

    async def run_until_flat(
        self,
        *,
        controller: Callable[[int], DecisionProvider],
        max_minutes: int = 240,
    ) -> TurnReport:
        """Recorre turnos con el reloj determinista hasta dejar el libro plano."""
        aggregate = TurnReport(venue=self._venue())
        for _ in range(max_minutes):
            self._decider = controller(self._minute + 1)
            turn = await self.auto_turn()
            aggregate.merge(turn)
            if not self.open_symbols:
                break
        return aggregate

    async def persistent_turn(self) -> TurnReport:
        """auto_turn + (M4) persistencia durable cuando ``auto_store`` está fijado."""
        report = await self.auto_turn()
        if self._auto_store is not None:
            snap: AutoEngineSnapshot | None = await self._auto_store.read(self._engine_id)
            seq = (snap.ticks + 1) if snap is not None else 1
            # P3 — el estado durable expresa «¿está permitida la operativa?», no «¿está
            # vivo el proceso?» (eso es el latido). Kill activo (env o parada dura latcheada)
            # ⇒ BLOCKED, en coherencia exacta con derive_activity: nunca RUNNING + BLOCKED.
            blocked = self._kill_active() or self._v2_kill_switch_halted()
            await self._auto_store.record_tick(
                AutoEngineTickInput(
                    engine_id=self._engine_id,
                    venue=report.venue,
                    state="BLOCKED" if blocked else "RUNNING",
                    seq=seq,
                    proposals=report.proposals,
                    vetoes=report.vetoes,
                    pending_plans=len(self.open_symbols),
                    last_reason=("auto-sim-durable",),
                    occurred_at=self._time,
                    activity=derive_activity(
                        kill_active=blocked,
                        decided=report.decided,
                        proposals=report.proposals,
                        orders=report.orders,
                        fills=report.fills,
                    ),
                )
            )
        return report

    async def real_turn(
        self,
        *,
        exec_store: ExecutionEventStore,
        auto_store: AutoEngineStore | None,
        finance_applier: Callable[[Any], Awaitable[bool]] | None,
        account_id: str | None,
        context_store: Any = None,
        position_store: Any = None,
        canonical_positions_reader: Any = None,
        consumed_signal_store: Any = None,
        regime_source: Any = None,
        trade_context_source: Any = None,
        edge_source: Any = None,
        atr_source: Any = None,
        # V2.88 / TOP3 cross-asset: evidencia LAB del campeón ACTIVE por instrumento
        # (misma sesión del tick). Sin ella se conserva la del constructor ⇒ Δ = 0.
        evidence_source: Any = None,
        # V2.88.84 — sink durable del TOP3 cross-asset, atado a la MISMA sesión del tick.
        # Sin él se conserva el del constructor (hermético/tests) ⇒ Δ = 0.
        top3_opportunity_sink: Callable[[list[Any], str | None], Awaitable[None]] | None = None,
        # W4 (v2.88.17): fuente de precio REAL del tick (misma sesión que régimen y ATR).
        # Con ``None`` se conserva la del constructor (``price_script`` hermético) ⇒ Δ = 0.
        price_source: PriceSource | None = None,
        reservation_store: ReservationStore | None = None,
        kill_switch_store: KillSwitchStore | None = None,
        exit_order_store: ExitOrderStore | None = None,
        # AUTO-10: sink durable del régimen por ciclo, atado a la MISMA sesión del tick.
        cycle_regime_sink: Callable[[Any], Awaitable[None]] | None = None,
        # AUTO-10: lector de ese journal, también sobre la sesión del tick.
        cycle_regime_reader: Callable[[Sequence[str]], Awaitable[CycleRegimeReading]] | None = None,
        # AUTO Operational Monitor (``M2``): sink de la auditoría operativa, sobre la MISMA
        # sesión del tick. Sin él se conserva el del constructor (hermético/tests) ⇒ Δ = 0.
        operational_audit_sink: Callable[[Any], Awaitable[None]] | None = None,
        # v2.88.27: lector de deduplicación de los hechos M2 (``SETTLEMENT`` ya sellados), atado
        # a la MISMA sesión del tick. Sin él se conserva el del constructor ⇒ no se recupera nada.
        durable_fact_cycle_reader: Callable[[str], Awaitable[frozenset[str]]] | None = None,
        # AUTO-11: sink de la recomendación Adaptive durable, atado a la MISMA sesión del tick.
        adaptive_sink: Callable[[Any], Awaitable[None]] | None = None,
        # AUTO-11: lector del estado Adaptive reconstruible, también sobre la sesión del tick.
        adaptive_reader: Callable[[str | None], Awaitable[AdaptiveStateReading]] | None = None,
        # AUTO-15: la racha durable de fallos del sink, sobre la MISMA sesión del tick.
        adaptive_gate_store: AdaptiveGateStore | None = None,
        # Handoff durable ESTUDIO → AUTO (migración 058), atado a la MISMA sesión del tick.
        daily_proposal_source: (Callable[[str, str, Sequence[str]], Awaitable[Any]] | None) = None,
        daily_proposal_sink: Callable[[list[dict[str, Any]]], Awaitable[Any]] | None = None,
        # P7/P8 (auditoría .183): el ciclo RECLAMADO antes de ejecutar y el lease con el
        # que se conduce. Sin ellos el turno se matricula como siempre (hermético/tests).
        cycle_claim: AutoEngineCycleClaim | None = None,
        lease: AutoEngineLease | None = None,
    ) -> TurnReport:
        """Un turno con autoridad (gates) persistiendo tick durable (opcional).

        Se enlazan por-ciclo los stores/account (sesión por tick del scheduler) y se
        delega en ``auto_turn`` (misma Single Decision Spine del Bloque 3). El estado
        ``_open``/``_journal`` del worker se conserva entre turnos en el proceso; en
        el PRIMER turno de un proceso se readopta la posición durable (Bloque 5 /
        G7) para no re-comprar tras crash. Restaura los valores anteriores al
        terminar para no dejar fugas entre ticks.

        V2.40.1: las fuentes de DATO del tick (régimen, contexto de cartera y edge) se
        enlazan aquí igual que los stores, sobre la sesión viva. Fuera del camino real
        (hermético) se conservan las inyectadas en el constructor.
        """
        prev_exec, prev_auto, prev_fin, prev_acc, prev_ctx, prev_pos, prev_canon = (
            self._exec_store,
            self._auto_store,
            self._finance_applier,
            self._account_id,
            self._context_store,
            self._position_store,
            self._canonical_positions_reader,
        )
        prev_signals = self._consumed_signal_store
        prev_regime, prev_context, prev_edge, prev_reservations = (
            self._v2_regime_source,
            self._v2_trade_context_source,
            self._v2_edge_source,
            self._reservation_store,
        )
        prev_evidence = self._v2_evidence_source
        prev_top3_sink = self._top3_opportunity_sink
        prev_atr = self._v2_atr_source
        prev_price = self._price_source
        prev_kill_store = self._kill_switch_store
        prev_exit_store = self._exit_order_store
        prev_cycle_sink = self._cycle_regime_sink
        prev_cycle_reader = self._cycle_regime_reader
        prev_operational_audit_sink = self._operational_audit_sink
        prev_durable_fact_reader = self._durable_fact_cycle_reader
        prev_adaptive_sink = self._adaptive_sink
        prev_adaptive_reader = self._adaptive_reader
        prev_adaptive_gate_store = self._adaptive_gate_store
        prev_daily_proposal_source = self._daily_proposal_source
        prev_daily_proposal_sink = self._daily_proposal_sink
        # W2 · Fase A: el seam de la barra queda ENCENDIDO todo el turno durable y se
        # restaura al salir, para que el camino hermético (``auto_turn`` directo) siga
        # midiendo el plan completo aunque comparta instancia con el camino real.
        prev_bar_short_circuit = self._v2_bar_short_circuit
        try:
            self._v2_bar_short_circuit = True
            self._exec_store = exec_store
            self._auto_store = auto_store
            self._finance_applier = finance_applier
            self._account_id = account_id
            self._context_store = context_store if context_store is not None else prev_ctx
            self._position_store = position_store if position_store is not None else prev_pos
            self._canonical_positions_reader = (
                canonical_positions_reader if canonical_positions_reader is not None else prev_canon
            )
            # AUTO 2.0 · P4: el espejo de señales consumidas se enlaza igual (una
            # sesión por tick); sin él se conserva el que hubiera (hermético).
            self._consumed_signal_store = (
                consumed_signal_store if consumed_signal_store is not None else prev_signals
            )
            # AUTO 2.0 · V2.40.1: fuentes de dato del tick (misma sesión que los stores).
            self._v2_regime_source = regime_source if regime_source is not None else prev_regime
            self._v2_trade_context_source = (
                trade_context_source if trade_context_source is not None else prev_context
            )
            self._v2_edge_source = edge_source if edge_source is not None else prev_edge
            # V2.88 / TOP3 cross-asset: la evidencia se enlaza igual que el edge (misma sesión).
            self._v2_evidence_source = (
                evidence_source if evidence_source is not None else prev_evidence
            )
            # V2.88.84 — el sink del TOP3 cross-asset viaja con la sesión del tick (como los
            # demás espejos). Sin él se conserva el del constructor (hermético/tests).
            self._top3_opportunity_sink = (
                top3_opportunity_sink if top3_opportunity_sink is not None else prev_top3_sink
            )
            # Handoff ESTUDIO → AUTO: lector y sumidero viajan con la sesión del tick. Sin
            # ellos se conserva lo del constructor (hermético/tests) ⇒ Δ = 0.
            self._daily_proposal_source = (
                daily_proposal_source
                if daily_proposal_source is not None
                else prev_daily_proposal_source
            )
            self._daily_proposal_sink = (
                daily_proposal_sink if daily_proposal_sink is not None else prev_daily_proposal_sink
            )
            # E2: la fuente de ATR del tick se enlaza igual que el régimen (misma sesión).
            self._v2_atr_source = atr_source if atr_source is not None else prev_atr
            # W4: la fuente de precio REAL del tick se enlaza igual (misma sesión). Sin
            # ella queda la del constructor (``price_script`` hermético) ⇒ Δ = 0.
            self._price_source = price_source if price_source is not None else prev_price
            # AUTO-1b: el libro durable de reservas se enlaza también por sesión (una
            # sesión por tick). Sin él se conserva el del constructor (hermético/tests).
            self._reservation_store = (
                reservation_store if reservation_store is not None else prev_reservations
            )
            # V2.43.3: los espejos durables de la parada dura y de la identidad de salida
            # se enlazan igual (una sesión por tick).
            self._kill_switch_store = (
                kill_switch_store if kill_switch_store is not None else prev_kill_store
            )
            self._exit_order_store = (
                exit_order_store if exit_order_store is not None else prev_exit_store
            )
            # Medición 2026-10-23 — el espejo EFECTIVO de la salida, ya resuelto el merge de la
            # sesión. Existe porque un ``_exit_order_store = None`` persistía SIN RASTRO:
            # la identidad de la salida se minteaba y la orden se emitía, pero el INTENT no se
            # escribía y ningún log lo declaraba (``_v2_save_exit_order`` devuelve ``False`` en
            # silencio y el llamante no lo comprueba). Con esta línea, un espejo ausente deja de
            # ser invisible: dice qué tipo quedó en cada espejo, sin tocar ninguna decisión.
            _declare_effective_mirrors(
                account_id=self._account_id,
                engine_id=self._engine_id,
                mirrors=(
                    ("reservations", self._reservation_store),
                    ("exitOrders", self._exit_order_store),
                    ("kill", self._kill_switch_store),
                ),
            )
            # AUTO-10: el sink del régimen por ciclo viaja con la sesión del tick (como los
            # demás espejos). Sin él se conserva el del constructor (hermético/tests).
            self._cycle_regime_sink = (
                cycle_regime_sink if cycle_regime_sink is not None else prev_cycle_sink
            )
            # AUTO-10: y su mitad de lectura, con la misma regla.
            self._cycle_regime_reader = (
                cycle_regime_reader if cycle_regime_reader is not None else prev_cycle_reader
            )
            # AUTO Operational Monitor (``M2``): el sink de auditoría viaja con la sesión del
            # tick, con la misma regla (sin él se conserva el del constructor).
            self._operational_audit_sink = (
                operational_audit_sink
                if operational_audit_sink is not None
                else prev_operational_audit_sink
            )
            # v2.88.27 — la mitad de LECTURA para deduplicar/recuperar los hechos M2, misma regla.
            self._durable_fact_cycle_reader = (
                durable_fact_cycle_reader
                if durable_fact_cycle_reader is not None
                else prev_durable_fact_reader
            )
            # AUTO-11: la recomendación Adaptive durable y su lector, con la misma regla de sesión.
            self._adaptive_sink = adaptive_sink if adaptive_sink is not None else prev_adaptive_sink
            self._adaptive_reader = (
                adaptive_reader if adaptive_reader is not None else prev_adaptive_reader
            )
            # AUTO-15: la racha durable de fallos del sink, con la misma regla de sesión.
            self._adaptive_gate_store = (
                adaptive_gate_store if adaptive_gate_store is not None else prev_adaptive_gate_store
            )
            # M8 (auditoría .183) — un turno OPERATIVO sin sus espejos durables operaría con
            # la mitad del estado en RAM (parada dura, posición, compromiso de capital y libro
            # financiero se perderían en el siguiente reinicio). Se rechaza ANTES de readoptar,
            # reconciliar o decidir: ``real_turn`` no muta nada y el motivo queda declarado en
            # el tick durable (``durable_stores_missing:<seams>``).
            if self._require_durable_stores:
                missing = self._v2_missing_durable_seams()
                if missing:
                    logger.error(
                        "auto_sim turno RECHAZADO: faltan espejos durables engine=%s missing=%s",
                        self._engine_id,
                        ",".join(missing),
                    )
                    self.declare_skip(f"{DURABLE_STORES_MISSING}:{','.join(missing)}")
                    return TurnReport(venue=self._venue())
            # V2.43.3 (P0-1) — BOOT SAFETY GATE: la parada dura se LEE de su espejo durable
            # ANTES de readoptar posición y de reconciliar. Un reinicio NO puede reabrir el
            # motor: si el HALT estaba activo, sigue activo (el in-memory lo olvidaba).
            await self._v2_load_kill_state()
            # V2.24/A9.1 (P1-04): sin cuenta inequívoca NO se readopta ni opera el
            # camino durable; auto_turn veta igualmente (defensa en profundidad).
            if not self._readopted and self._account_id:
                # Readopción una sola vez por proceso (crash/restart ⇒ adoptar posición).
                await self.readopt_positions()
            # AUTO-1b: reconciliación de ARRANQUE del libro de reservas, una vez por
            # proceso (es independiente del libro de posición: son dos libros distintos).
            # Convierte ``execution_events`` en lo que siempre debió ser: el contraste de
            # qué se materializó, no el productor del capital comprometido.
            if not self._v2_reservations_reconciled:
                self._v2_reservations_reconciled = True
                await self._v2_reconcile_reservations(startup=True)
            # AUTO-11: el estado Adaptive se reconstruye del journal durable ANTES del primer
            # plan del proceso (si no, el primer turno decidiría con un cooldown a 0 y podría
            # levantar una pausa que aún no cumplió su ventana mínima). Una vez por proceso.
            await self._v2_recover_adaptive_state()
            # AUTO-11: y se cruza el rastro de ciclo —capital comprometido vs traza de régimen—
            # para que la ventana ``RESERVATION COMMITTED → CRASH → NO JOURNAL`` de AUTO-10 deje
            # de ser invisible. Read-only: solo declara, no corrige.
            await self._v2_reconcile_cycle_traces()
            # v2.88.27 — y se recuperan los HECHOS durables que un crash pudo dejar sin publicar:
            # un ciclo cerrado (demostrado por los fills) sin ``auto_cycle_settlement`` en el
            # spine se vuelve a sellar aquí. La identidad determinista hace el reenvío idempotente
            # y el lector confirma qué ciclos YA lo tienen, de modo que no se reescribe el pasado.
            await self._v2_recover_durable_facts()
            report = await self.auto_turn()
            # OBS-14 — CIERRE del ciclo de reservas del turno: retira las reservas MUERTAS
            # (la orden no llegó a materializarse dentro del tick) sobre la MISMA sesión del
            # turno, sin reiniciar. ``startup=False`` porque la reserva no murió por un
            # reinicio sino porque su orden no se materializó (``RESERVATION_RELEASED_BY_CANCEL``).
            # ``attribute_fills=False`` es OBLIGATORIO aquí: el camino caliente ya liberó los
            # fills del turno y la regla 1 es no idempotente, así que re-atribuirla en cada
            # turno drenaría la cola VIVA de una orden parcialmente llenada (fail-OPEN). El
            # cierre de turno solo retira el huérfano que NUNCA se materializó.
            #
            # OBS-14.b — el cierre retira las reservas de ESTA sesión (``only_ids``) y, además,
            # cualquier OTRA reserva que ya haya envejecido más de la ventana de gracia (su
            # dueño, sea quien sea, ya cerró su turno): es la retirada DIFERIDA que acota la
            # retención de la huérfana ajena a ~un turno, en vez de esperar a otro reinicio.
            # La reserva AJENA y JOVEN se conserva: en una carrera entre sesiones es
            # INDISTINGUIBLE de una orden muerta sin llenar hasta que esa otra sesión emite y
            # liquida, y retirarla devolvería al mercado un capital que sí se materializa
            # (fail-OPEN observado en ``test_concurrent_auto_pg.py``).
            await self._v2_reconcile_reservations(
                startup=False,
                attribute_fills=False,
                only_ids=frozenset(self._v2_owned_reservations),
            )
            if auto_store is not None:
                snap: AutoEngineSnapshot | None = await auto_store.read(self._engine_id)
                # P8: con ciclo RECLAMADO, la fila del ledger ya existe (``seq`` y
                # ``tick_id`` del claim): el turno la LIQUIDA en vez de matricular otra.
                # Sin claim se conserva la matrícula histórica (seq = ticks + 1).
                seq = (
                    cycle_claim.seq
                    if cycle_claim is not None
                    else ((snap.ticks + 1) if snap is not None else 1)
                )
                # P3 — estado durable = operativa permitida (no «proceso vivo»). Kill activo
                # (env o parada dura latcheada) ⇒ BLOCKED, en coherencia con derive_activity.
                blocked = self._kill_active() or self._v2_kill_switch_halted()
                await auto_store.record_tick(
                    AutoEngineTickInput(
                        engine_id=self._engine_id,
                        venue=report.venue,
                        state="BLOCKED" if blocked else "RUNNING",
                        seq=seq,
                        proposals=report.proposals,
                        vetoes=report.vetoes,
                        pending_plans=len(self.open_symbols),
                        last_reason=(self._last_gate_reason or ("idle",)),
                        occurred_at=self._time,
                        claim_tick_id=(cycle_claim.tick_id if cycle_claim is not None else None),
                        lease_owner=(lease.owner if lease is not None else None),
                        lease_generation=(lease.generation if lease is not None else None),
                        activity=derive_activity(
                            kill_active=blocked,
                            decided=report.decided,
                            proposals=report.proposals,
                            orders=report.orders,
                            fills=report.fills,
                        ),
                    )
                )
            return report
        finally:
            self._exec_store = prev_exec
            self._auto_store = prev_auto
            self._finance_applier = prev_fin
            self._account_id = prev_acc
            self._context_store = prev_ctx
            self._position_store = prev_pos
            self._canonical_positions_reader = prev_canon
            self._consumed_signal_store = prev_signals
            self._v2_regime_source = prev_regime
            self._v2_trade_context_source = prev_context
            self._v2_edge_source = prev_edge
            self._v2_evidence_source = prev_evidence
            self._top3_opportunity_sink = prev_top3_sink
            self._v2_atr_source = prev_atr
            self._price_source = prev_price
            self._reservation_store = prev_reservations
            self._kill_switch_store = prev_kill_store
            self._exit_order_store = prev_exit_store
            self._cycle_regime_sink = prev_cycle_sink
            self._cycle_regime_reader = prev_cycle_reader
            self._operational_audit_sink = prev_operational_audit_sink
            self._durable_fact_cycle_reader = prev_durable_fact_reader
            self._adaptive_sink = prev_adaptive_sink
            self._adaptive_reader = prev_adaptive_reader
            self._adaptive_gate_store = prev_adaptive_gate_store
            self._daily_proposal_source = prev_daily_proposal_source
            self._daily_proposal_sink = prev_daily_proposal_sink
            self._v2_bar_short_circuit = prev_bar_short_circuit

