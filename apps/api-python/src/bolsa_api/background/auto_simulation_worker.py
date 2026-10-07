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

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

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
from bolsa_analytics.cognitive.exit_plan import is_thesis_invalidated
from bolsa_analytics.cognitive.exit_policy import (
    resolve_exit_policy,
    resolve_holding_horizon,
)
from bolsa_analytics.cognitive.hard_kill_switch import HardKillSwitch
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
from bolsa_api.background.paper_auto_engine_worker import (
    DecisionProvider,
    _effective_venue,
    _kill_switch_env_on,
    _watch_symbols,
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
    AutoEngineSnapshot,
    AutoEngineStore,
    AutoEngineTickInput,
)
from bolsa_application.auto_operational_audit import (
    REASON_GRACE_WINDOW_KEEP,
    REASON_SESSION_OWNED,
    RECONCILIATION_KEEP,
    RECONCILIATION_RELEASE,
    build_cycle_settlement_entry,
    build_entry_order_entry,
    build_protection_entry,
    build_reservation_claim_entry,
    build_reservation_reconciliation_entry,
    durable_fact_dedupe_key,
    operational_audit_enabled,
)
from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
from bolsa_application.auto_reason_codes import (
    ATR_GEOMETRY,
    ATR_SOURCE_FALLBACK,
    ATR_SOURCE_MISSING,
    ATR_SOURCE_REAL,
    EXIT_QTY_OVER_POSITION,
    FILL_NOT_MATERIALIZED,
    FILL_PARTIALLY_MATERIALIZED,
    LIFECYCLE_TRANSITION_REJECTED,
    OPPORTUNITY_TRADED,
    PROTECT_REQUESTED,
    PROTECTION_MISSING,
    RECONCILIATION_REQUIRED,
    RESERVATION_ALREADY_LIVE,
    RESERVATION_UNMEASURABLE,
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

logger = logging.getLogger(__name__)

AUTO_SIM_WORKER_ENABLED = "AUTO_SIMULATION_WORKER_ENABLED"
_FILL_CHUNKS = 4
# V2.40.4 — tope de lectura del libro de órdenes pendientes por tick. Acotado a
# propósito (no hay índice por ``account_id``): si se alcanza, el libro NO se puede
# afirmar completo y el motor veta aperturas en vez de creer que no hay más.
_V2_OPEN_ORDERS_LIMIT = 200

# AUTO-1A — tope de lectura del libro de fills APLICADOS para reconstruir la posición
# canónica. La lectura ocurre UNA vez por proceso (readopción tras crash), no por tick.
# Sin índice parcial ``(account_id, status)``: deuda declarada, la migración llega en
# AUTO-1 (Reservation Engine). Agotar el tope NO se interpreta como "no hay más": la
# lectura queda NO medible y las aperturas se vetan (fail-closed) con log explícito.
_CANONICAL_LEDGER_LIMIT = 10_000

# AUTO-1b — tope de lectura del libro durable de RESERVAS (``portfolio_reservations``).
# Si se alcanza, no se puede afirmar que se vieron todas las reservas vivas: el libro de
# compromiso queda NO medible y las aperturas se vetan (agotar un tope ≠ no hay más).
_V2_RESERVATIONS_LIMIT = 500

# AUTO-9 — tope de lectura del material de RIESGO por ciclo (``list_by_cycle_ids``). A
# diferencia del libro de compromiso, agotar este tope NO veta: los ciclos que no cupieron
# quedan declarados SIN reserva (hueco honesto, ``cycle_without_risk``), nunca con el
# denominador de otro ciclo. El tope es 4× el del libro porque un ciclo tiene varias filas
# (entrada + salidas) y la consulta va por ``cycle_id`` (índice dedicado).
_V2_CYCLE_RISK_READ_LIMIT = 2000

# AUTO-1A — ``execution_events`` ya materializados. ``already_applied`` también cuenta:
# significa que OTRA instancia ya movió el dinero (idempotencia por ``execution_id``), que
# es exactamente el hecho que la posición debe reflejar.
_APPLIED_OUTCOMES: frozenset[str] = frozenset({"applied", "already_applied"})

# AUTO-1A — reason codes de materialización (observabilidad del P0 de la auditoría v2.40.4).
# Antes, una orden cuyo settlement no materializaba nada se contaba igual (con la cantidad
# PEDIDA) y el journal no distinguía pedido de aplicado. Los literales son únicos y viven
# en ``bolsa_application.auto_reason_codes``.

# Kind de journal para los chunks que NO materializaron dinero: son capital PENDIENTE
# (reservado), no posición ni realizado.
JOURNAL_FILL_UNAPPLIED = "fill_unapplied"

_QTY_EPS = Decimal("0.000001")

# v2.88.25 — ventana de lectura de fills del ciclo para sellar el PnL del settlement durable.
# Con la ventana LLENA (``len == limit``) la evidencia pudo truncarse y el PnL se declara
# ``PARTIAL``/``None``: la misma disciplina fail-closed que ``CYCLE_CLOSED``.
_SETTLEMENT_FILL_WINDOW = 500


def settlement_snapshot_from_fills(fills: Sequence[Any]) -> dict[str, Any] | None:
    """(PURA, v2.88.27) campos DEMOSTRABLES de un settlement a partir de los fills del ciclo.

    Sólo se derivan los datos que los fills declaran: el instrumento, la cantidad liquidada
    (Σ de las ventas) y la FUENTE de precio del fill de cierre. El motivo de salida NO se
    reconstruye (no viaja en el fill) y el PnL no se calcula aquí: lo publica el MISMO
    ``cycles_from_fills`` que alimenta ``CYCLE_CLOSED``, un único FIFO. Sin ventas —o sin un
    instrumento/cantidad utilizables— no hay settlement reconstruible: ``None``, nunca un
    hecho a medias.
    """
    sells = [
        fill
        for fill in fills
        if str(getattr(fill, "side", "") or "").strip().lower() == "sell"
    ]
    if not sells:
        return None
    instrument = str(getattr(sells[-1], "instrument_id", "") or "").strip()
    if not instrument:
        return None
    closed_qty = Decimal("0")
    for fill in sells:
        raw = getattr(fill, "quantity", None)
        if raw is None or isinstance(raw, bool):
            return None
        try:
            closed_qty += Decimal(str(raw))
        except (ArithmeticError, ValueError):
            return None
    if closed_qty <= 0:
        return None
    return {
        "instrument_id": instrument,
        "closed_qty": closed_qty,
        "price_source": getattr(sells[-1], "price_source", None),
    }


def sim_worker_enabled() -> bool:
    """Env de habilitación (default OFF) del worker SIM-ONLY de A9/M5."""
    return (os.getenv(AUTO_SIM_WORKER_ENABLED) or "").strip().lower() not in {
        "",
        "0",
        "false",
        "no",
        "off",
    }


#: W4 (v2.88.17): interruptor DECLARADO del precio REAL. Default **OFF** ⇒ el runtime conserva
#: el ``price_script`` hermético (``Δ = 0`` y todos los tests PG en verde, que es como se selló
#: el tramo ``W3.x``). Activarlo es un acto **explícito** y es lo que mide el criterio de éxito
#: de ``W4`` (que el camino de PRODUCCIÓN/PAPER deje de fabricar un precio):
#: ``AUTO_ENGINE_SIM_REAL_PRICE=1``.
AUTO_REAL_PRICE_ENV = "AUTO_ENGINE_SIM_REAL_PRICE"


def real_price_enabled() -> bool:
    """¿Está habilitado el proveedor de precio REAL? (default OFF = costura inerte)."""
    return (os.getenv(AUTO_REAL_PRICE_ENV) or "").strip().lower() not in {
        "",
        "0",
        "false",
        "no",
        "off",
    }


# ── Reloj / precio SIM deterministas (inyectables; "minutos simulados") ─────────
#: Precio por ``(símbolo, tick)``. ``tick`` es el índice temporal del CALENDARIO del
#: proveedor: el worker le pasa el **tick de BARRA** (``closed_bars.bar_tick``), que es
#: estable dentro de la barra, para que la referencia de EJECUCIÓN de un reintento
#: intra-barra sea la MISMA (idempotencia del fill). Los proveedores actuales ignoran el
#: argumento (constante, snapshot vivo, reloj del replay), así que pasar el tick de barra
#: en vez del minuto no mueve ningún precio; lo que fija es el CONTRATO temporal.
#:
#: **W4 (v2.88.17):** un ``PriceScript`` **no puede expresar ausencia** (su único recurso
#: era mentir con ``100.0``/``0``). Para el precio REAL el motor usa el seam
#: ``auto_price_provider.PriceSource`` (``execution``/``mid`` → ``float | None``), que sí
#: puede, y cae **fail-closed por símbolo** cuando no hay precio. ``PriceScript`` se
#: conserva como el camino hermético *declarado* (replay y tests): sin ``price_source``
#: el worker lee este script EN VIVO y el comportamiento es byte a byte el de antes.
PriceScript = Callable[[str, int], float]
Clock = Callable[[], datetime]


def default_clock() -> datetime:
    return datetime.now(UTC)


def step_minute_clock(
    start: datetime | None = None,
) -> tuple[datetime, Clock]:
    """(inicio, clock): cada llamada de ``clock()`` avanza UN minuto simulado."""
    cur: dict[str, datetime] = {"now": start if start is not None else default_clock()}

    def clock() -> datetime:
        cur["now"] = cur["now"] + timedelta(minutes=1)
        return cur["now"]

    return cur["now"], clock


def flat_price_script(_symbol: str, _tick: int) -> float:
    """Precio plano determinista por defecto (sin movimientos del mercado)."""
    return 100.0


# AUTO-2: la política de protección (y su implementación) vive en
# ``bolsa_application.protection_compat``. Aquí sólo queda el alias histórico que el
# worker y los tests consumían, para no romper imports: NO es un motor, es un value
# object con delegación.
ProtectionConfig = ProtectionPolicy


def _protection_config_from_env() -> ProtectionPolicy:
    """Lee la política de protección de env (default OFF = fail-closed).

    ``AUTO_ENGINE_SIM_PROTECTION=1`` activa. ``AUTO_ENGINE_SIM_STOP_PCT``/``_T1_PCT``/
    ``_TRAILING_PCT`` (fracción, p.ej. 0.02) y ``AUTO_ENGINE_SIM_SESSION_END_MINUTE``
    afinan los umbrales. Cualquier valor inválido se ignora (default seguro).
    """

    def _f(name: str, default: float) -> float:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    def _i(name: str, default: int) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    enabled = (os.getenv("AUTO_ENGINE_SIM_PROTECTION") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return ProtectionPolicy(
        stop_pct=_f("AUTO_ENGINE_SIM_STOP_PCT", 0.02),
        t1_pct=_f("AUTO_ENGINE_SIM_T1_PCT", 0.02),
        trailing_pct=_f("AUTO_ENGINE_SIM_TRAILING_PCT", 0.015),
        session_end_minute=_i("AUTO_ENGINE_SIM_SESSION_END_MINUTE", 0),
        t1_fraction=_f("AUTO_ENGINE_SIM_T1_FRACTION", 1.0),
        enabled=enabled,
    )


# ── Modelo del día autónomo SIM ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FillObservation:
    """Un fill real confirmado por el settlement SIM (fuente del journal M7)."""

    side: str
    venue: str
    execution_id: str
    order_id: str
    qty: Decimal


# V2.28 / A10 (P1-02 real): prefijo con que ``active_strategy_decider`` marca el
# ``DecisionPackage.source``. Es el único vínculo entre una propuesta y la versión de
# estrategia que la originó; aquí se extrae para atribuir el fill en el settlement.
_ACTIVE_STRATEGY_SOURCE_PREFIX = "active-strategy:"
# V2.45/AUTO-5: el pipeline V2 (``plan_v2_tick``) emite la propuesta de entrada con
# ``auto-2.0:<version>`` cuando la señal declara versión (y ``auto-2.0`` sin ella). Se
# reconoce para que la atribución de V2.28 NO se pierda en el camino V2: antes solo
# entendía ``active-strategy:`` y el fill/cierre del día V2 quedaba con versión NULL.
_V2_ENTRY_SOURCE_PREFIX = "auto-2.0:"


def _mark_observation_changed(
    current: PositionState | None,
    marked: PositionState,
) -> bool:
    """¿La marca del tick aporta un hecho NUEVO (extremo o peor adverso)?

    Compara sólo lo que la marca cambia de verdad: ``mfeMae`` (redondeado a 4dp por
    ``apply_position_mark``, así que cambia únicamente con un extremo nuevo) y el pico del
    trailing. No compara ``updatedAt``: si no, cada tick escribiría en el espejo durable.
    """
    if current is None:
        return False
    if dict(current.mfe_mae) != dict(marked.mfe_mae):
        return True
    return high_watermark_from_position(current) != high_watermark_from_position(marked)


def _strategy_version_from_source(source: Any) -> str | None:
    """Extrae la versión de estrategia de ``DecisionPackage.source``.

    Reconoce ``active-strategy:<v>`` (decider directo) y ``auto-2.0:<v>`` (propuesta del
    pipeline V2, V2.45/AUTO-5). Devuelve ``None`` cuando la propuesta no proviene de una
    estrategia con versión (spine determinista, protección, ``auto-2.0`` sin versión): la
    ausencia de atribución es información, nunca se inventa una versión.
    """
    text = str(source or "").strip()
    for prefix in (_ACTIVE_STRATEGY_SOURCE_PREFIX, _V2_ENTRY_SOURCE_PREFIX):
        if text.startswith(prefix):
            version_id = text[len(prefix) :].strip()
            return version_id or None
    return None


def _dec_or_none(value: Any) -> Decimal | None:
    """float|str|None → ``Decimal`` (o ``None``). Sin inventar ceros ni NaN."""
    if value is None:
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return dec if dec.is_finite() else None


# ── OBS-14.b — ventana de gracia del barrido de reservas: PROPIEDAD **o** EDAD ─────
#: Ventana de gracia, en TURNOS del motor, que acota la retirada de una reserva **ajena**
#: en el barrido de reservas (``_v2_reconcile_reservations``).
#:
#: Por qué existe: la regla 2 retira la reserva que "murió sin llenarse" con la MISMA
#: evidencia durable que el cierre de turno (sin ``APPLIED``, sin traza en vuelo, lecturas
#: medibles), y esa evidencia **no puede** distinguir una orden MUERTA de una orden que OTRA
#: sesión acaba de dar de alta y todavía no ha emitido ni liquidado. En el motor AUTO (solo
#: ``paper``/``simulated``, sin bridge LIVE) la orden liquida DENTRO del tick, así que una
#: reserva que ya superó un turno completo sin fill y sin traza en vuelo está muerta **por
#: construcción**: la EDAD es el discriminador, y sin él la regla 2 es fail-**OPEN** en un
#: reinicio rodante (devuelve al mercado un capital que la otra sesión SÍ materializa).
V2_RESERVATION_GRACE_TURNS = 1

#: Resolución del SELLO de alta de las reservas (``_v2_instant``: ISO-UTC **a segundos**, el
#: mismo formato que el ``tick_id`` del plan). La EDAD APARENTE de una reserva excede la real en
#: hasta este margen, así que la ventana lo SUMA: sin él la edad no es afirmable.
#:
#: Medido en la certificación concurrente (`test_concurrent_auto_pg`, cadencia ``1 s``): la
#: reserva sellada a ``16:08:09`` vista por un par con reloj ``16:08:10.009331`` daba una edad
#: aparente de ``1.009 s`` contra una ventana de ``1.000 s`` — con edad REAL de milisegundos —
#: y ese par AJENO (``mine=False``) la retiraba declarando ``cancel`` ("nunca materializó")
#: sobre un fill parcial que llegó después (``147/200``, dos tranchas, el MISMO ``cycle_id``):
#: fail-**OPEN**, capital de una orden en vuelo devuelto al mercado. Con la resolución sumada,
#: ``aged`` implica edad real ``>`` ventana, y el sello de segundos deja de poder mentir.
V2_RESERVATION_GRACE_STAMP_RESOLUTION = timedelta(seconds=1)


def reservation_grace_window(interval_seconds: float | None = None) -> timedelta:
    """Ventana de gracia del barrido de reservas, derivada de la cadencia REAL del loop.

    ``AUTO_ENGINE_SIM_INTERVAL_SECONDS`` (default ``60 s``) es la cadencia del turno del
    motor, así que la ventana se declara en TURNOS y **no** como un número mágico. Un turno
    que sobrepase su intervalo queda fuera del contrato del scheduler (``auto_sim_loop`` hace
    ``run_tick()`` y luego ``sleep(interval)``), pero el turno SIM real es trabajo en proceso
    + BD sin esperas de red: con la cadencia nominal la ventana deja un margen de dos órdenes
    de magnitud sobre la duración medida del turno.

    Se **suma** ``V2_RESERVATION_GRACE_STAMP_RESOLUTION`` porque la edad se mide contra un
    sello de SEGUNDOS: la ventana tiene que superar el error de medida del sello, no solo la
    cadencia, o una reserva recién creada puede parecer envejecida (ver la constante).
    """
    seconds = _sim_interval_seconds() if interval_seconds is None else interval_seconds
    return (
        timedelta(seconds=V2_RESERVATION_GRACE_TURNS * seconds)
        + V2_RESERVATION_GRACE_STAMP_RESOLUTION
    )


def _instant(value: Any) -> datetime | None:
    """Instante ISO (``Z``, con offset o naive) → ``datetime`` UTC; ``None`` si no se lee.

    Comparar instantes como TEXTO no vale: ``"…:00.500000+00:00"`` y ``"…:00Z"`` se ordenan
    al revés de como ocurrieron (``"." < "Z"``), y la reconciliación de reservas decide con
    esa comparación ("¿el fill es posterior al alta de la reserva?"). Se comparan instantes
    de verdad; sin fecha legible no se afirma nada (el llamante conserva la reserva).
    """
    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _open_order_from_fill(
    row: Any,
    context: Any,
    *,
    sector: str | None,
) -> OpenOrder:
    """Traduce una traza NO aplicada (+ contexto financiero) a ``OpenOrder``.

    El ``execution_events`` da la identidad y el estado; el
    ``sim_fill_finance_context`` da lado/cantidad/precio (su PK es ``execution_id``, ya
    indexada). Si el contexto falta, la orden queda SIN cuantificar a propósito: su
    capital no se declara como 0 (sería una afirmación falsa) y el resumen lo marca como
    libro no medible ⇒ el motor veta aperturas.
    """
    return build_open_order(
        execution_id=str(getattr(row, "execution_id", "") or ""),
        order_id=str(getattr(row, "order_id", "") or ""),
        venue_order_id=getattr(row, "venue_order_id", None),
        instrument_id=str(getattr(context, "instrument_id", "") or ""),
        side=getattr(context, "side", None),
        quantity=getattr(context, "quantity", None),
        price=getattr(context, "price", None),
        sector=sector,
        strategy_version_id=getattr(context, "strategy_version_id", None),
        status=getattr(row, "status", None),
    )


@dataclass(frozen=True, slots=True)
class _AppliedFill:
    """Fill aplicado, en la forma que la reconciliación entiende (P1-01/P2-02)."""

    symbol: str
    side: str
    qty: Decimal
    price: Decimal
    execution_id: str
    venue: str

    @property
    def instrument_id(self) -> str:
        return self.symbol


@dataclass(frozen=True, slots=True)
class _Settlement:
    """Resultado de liquidar una orden SIM, separando PEDIDO de MATERIALIZADO.

    AUTO-1A: una orden puede llenarse en parte (la cola noisy corta los chunks finales) o
    no llenarse nada. Solo ``applied`` movió dinero y por tanto **solo** ``applied`` es
    posición, riesgo, protección y realizado. Lo no aplicado queda como capital PENDIENTE
    (orden en vuelo) y lo recoge el libro de órdenes del siguiente tick.

    ``structural=True`` marca el modo smoke del worker (sin ``finance_applier``): no
    existe dinero que mover, la traza no puede llegar a ``APPLIED`` por construcción y la
    confirmación del schedule es el único hecho observable. En ese modo lo confirmado es
    lo aplicado — y sigue siendo la cantidad CONFIRMADA, nunca la pedida.
    """

    requested_qty: Decimal = Decimal("0")
    applied: tuple[FillObservation, ...] = ()
    unapplied: tuple[FillObservation, ...] = ()
    outcomes: Mapping[str, str] = field(default_factory=dict)
    structural: bool = False

    @property
    def applied_qty(self) -> Decimal:
        total = Decimal("0")
        for fill in self.applied:
            total += fill.qty
        return total

    @property
    def unapplied_qty(self) -> Decimal:
        total = Decimal("0")
        for fill in self.unapplied:
            total += fill.qty
        return total

    @property
    def is_partial(self) -> bool:
        return bool(self.applied) and bool(self.unapplied)


@dataclass
class TurnReport:
    """Conteos del turno + venue (no acumulado de día; el day-journal está aparte)."""

    decided: int = 0
    proposals: int = 0
    vetoes: int = 0
    orders: int = 0
    fills: int = 0
    opened: int = 0
    closed: int = 0
    venue: str = "paper"

    def merge(self, other: TurnReport) -> None:
        self.decided += other.decided
        self.proposals += other.proposals
        self.vetoes += other.vetoes
        self.orders += other.orders
        self.fills += other.fills
        self.opened += other.opened
        self.closed += other.closed
        if other.venue:
            self.venue = other.venue


def derive_activity(
    *,
    kill_active: bool,
    decided: int,
    proposals: int,
    orders: int,
    fills: int,
) -> AutoActivity:
    """Fase operacional del turno, derivada SOLO de hechos que el motor ya calculó.

    Regla de honestidad de la UI: no se deriva de ``RUNNING`` (un motor vivo no
    significa «analizando»). Cada fase responde a un hecho concreto del tick:
    kill activo → ``BLOCKED``; fill/settlement → ``APPLYING_RESULT``; orden emitida
    → ``WAITING_EXECUTION``; propuesta que pasó el gate → ``PREPARING_OPERATION``;
    el bucle evaluó símbolos → ``ANALYZING``; y un tick vivo sin nada concreto
    → ``NO_ACTIVITY`` («Sin actividad», distinto de la ausencia de dato).

    ``WAITING_SIGNAL`` queda reservado para telemetría futura: el motor no puede
    distinguirlo hoy de «analizó y no encontró señal», así que no se emite en vez
    de inventar una espera que no demuestra.
    """
    if kill_active:
        return "BLOCKED"
    if fills > 0:
        return "APPLYING_RESULT"
    if orders > 0:
        return "WAITING_EXECUTION"
    if proposals > 0:
        return "PREPARING_OPERATION"
    if decided > 0:
        return "ANALYZING"
    return "NO_ACTIVITY"


def turn_equity_from_book(
    book_equity: float | None,
    *,
    required: bool,
    unreadable: bool,
    env_raw: str,
) -> tuple[float, bool]:
    """Devuelve ``(equity, aperturas_vetadas)``.

    Con el libro exigido, un valor ausente o no positivo veta las aperturas y
    no cae al env ni a 100_000. Sin esa exigencia (tests herméticos) se conserva
    ``AUTO_ENGINE_SIM_V2_EQUITY`` o 100_000.
    """
    if required:
        if unreadable or book_equity is None or book_equity <= 0:
            return 0.0, True
        return float(book_equity), False
    if env_raw:
        try:
            value = float(env_raw)
        except ValueError:
            value = 0.0
        if value > 0:
            return value, False
    return 100_000.0, False


async def read_account_book_equity(session: Any, account_id: str | None) -> float:
    """Cash más valor de mercado (``GetPortfolioSummary.total_equity``)."""
    if not (account_id or "").strip():
        raise ValueError("book equity requires account_id")
    from bolsa_application.accounts.portfolio import GetPortfolioSummary
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    summary = await GetPortfolioSummary(
        SqlAlchemyAccountRepository(session),
        SqlAlchemyPortfolioRepository(session),
    ).execute(account_id=account_id)
    return float(summary.total_equity)


class AutoSimulationWorker:
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
        self._reconciliation: dict[str, str] = {}
        self._readopted = False
        # V2.23/A9 (Bloque 6): protección autónoma (SL/T1/trailing/cierre de sesión).
        # Configurable por env, OFF por defecto. El precio de entrada/máximo se toma
        # del ``price_script`` determinista al abrir (misma fuente que la liquidación).
        self._protection = _protection_config_from_env()
        self._entry_price: dict[str, Decimal] = {}
        self._high_price: dict[str, Decimal] = {}
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
        self._v2_granularity = resolve_operative_granularity(
            self._v2_tunables.signal_timeframe
        )
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
        # restaurarla. Con store, ``_v2_kill_state_loaded`` garantiza que el load ocurre una
        # vez por proceso y ANTES de cualquier evaluación del gobernador.
        self._kill_switch_store = kill_switch_store
        self._v2_kill_state_loaded = False
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
        # por proceso cada una (mismo patrón que ``_v2_kill_state_loaded``).
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
        # V2.42 slice 2c: etiqueta del DÍA del motivo de cierre (``time_exit``/...), la que
        # viaja en la fila ``position_close``. Se deriva del motivo DECISORIO del plan, así
        # que un stop-out no se cuenta como salida por tesis.
        self._v2_last_exit_label: dict[str, str] = {}
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
        self._book_equity: float | None = None
        self._book_equity_required = False
        self._book_equity_unreadable = False
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
        # V2.23/A9: última razón del gate determinista (para telemetría/durable).
        self._last_gate_reason: tuple[str, ...] = ("idle",)

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
            self._readopted = True
            return dict(self._open)
        # V2.32/A12: la proyección durable YA guarda la versión de estrategia que abrió
        # la posición (migración 033). Al readoptarla se restaura ``_position_version``,
        # de modo que los fills de cierre posteriores al crash vuelven a atribuirse a la
        # misma versión (antes quedaban en NULL y truncaban la serie observada).
        authoritative = await self._reconcile_before_trusting(account_id, projection)
        # La posición abierta se adopta desde la proyección Y, si la reconciliación
        # determinó un canónico fiable, también desde él (un espejo vacío no debe
        # hacer perder una posición real: P1-01).
        for symbol, qty in (authoritative or {}).items():
            if qty and qty > 0:
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
        self._readopted = True
        return dict(self._open)

    async def _read_projection(self, account_id: str) -> dict[str, Any]:
        """Lee la proyección rica (P2-01) con fallback al read_open clásico."""
        reader = getattr(self._position_store, "read_projection", None)
        if reader is not None:
            return dict(await reader(account_id, self._engine_id))
        # Fallback hermético/legado: solo cantidades.
        from bolsa_application.sim_durable_store import SimPositionProjection

        qty_map = await self._position_store.read_open(account_id, self._engine_id)
        return {
            symbol: SimPositionProjection(symbol=symbol, quantity=Decimal(str(qty)))
            for symbol, qty in qty_map.items()
            if Decimal(str(qty)) > 0
        }

    async def _reconcile_before_trusting(
        self, account_id: str, projection: Mapping[str, Any]
    ) -> dict[str, Decimal]:
        """P1-01 / P2-02: la proyección es un espejo, no una autoridad.

        Con lector canónico disponible, reconcilia ``ExecutionEvents`` ↔ posición
        canónica ↔ proyección. Si divergen, reconstruye la proyección desde el estado
        canónico; si no hay datos, marca ``UNKNOWN`` y NO se autorizan aperturas.
        Devuelve el mapa canónico fiable (``{}`` si no se pudo determinar).
        """
        reader = self._canonical_positions_reader
        if reader is None:
            self._reconciliation = {s: POSITION_PROJECTION_UNKNOWN for s in projection}
            return {}
        try:
            canonical = await reader(account_id)
        except Exception:  # noqa: BLE001 — sin canónico no se puede confiar en el espejo.
            logger.exception("auto_sim canonical positions read failed")
            self._reconciliation = {s: POSITION_PROJECTION_UNKNOWN for s in projection}
            return {}
        if canonical is None:
            # El lector no pudo determinar el canónico (distinto de "sin posiciones"):
            # no se reconstruye nada y NO se autorizan aperturas.
            self._reconciliation = {s: POSITION_PROJECTION_UNKNOWN for s in projection}
            return {}
        # AUTO-1A: ``expected`` sale del MISMO libro que el canónico (Σ fills aplicados)
        # cuando el lector lo aporta (``CanonicalPositions.facts``). Tras un crash el
        # libro en RAM está vacío, y con ``events=[]`` la reconciliación veía
        # ``expected=0 != actual`` ⇒ DIVERGENT y la proyección inflada sobrevivía al
        # reinicio (justo el hueco del P0). Con las trazas aplicadas, la proyección se
        # RECONSTRUYE a la posición materializada. Si el lector no las aporta (seam
        # hermético), se conserva el libro del worker.
        events = getattr(canonical, "facts", None) or getattr(
            self, "_applied_execution_events", None
        )
        canonical_map: dict[str, Decimal] = {
            str(s): Decimal(str(q)) for s, q in dict(canonical).items()
        }
        # V2.24.2 (P2-C): reconciliación GLOBAL de la cuenta (no símbolo a símbolo),
        # incluyendo símbolos fantasma presentes solo en la proyección.
        projection_qty = {s: r.quantity for s, r in projection.items()}
        report = reconcile_sim_account(
            account_id=account_id,
            engine_id=self._engine_id,
            symbols=tuple(set(canonical_map) | set(projection_qty)),
            execution_events=events,
            financial_positions=canonical_map,
            sim_auto_positions=projection_qty,
        )
        for verdict in report.verdicts:
            symbol = verdict.symbol
            self._reconciliation[symbol] = verdict.status
            if verdict.status == POSITION_PROJECTION_REBUILT and self._position_store is not None:
                # Reconstruye la proyección desde el canónico (conserva protección si la hay).
                canonical_qty = canonical_map.get(symbol, Decimal("0"))
                prior = projection.get(symbol)
                if canonical_qty <= 0:
                    # El canónico dice "sin posición": la proyección estaba obsoleta.
                    await self._position_store.delete(account_id, self._engine_id, symbol)
                else:
                    await self._position_store.upsert(
                        account_id,
                        self._engine_id,
                        symbol,
                        canonical_qty,
                        entry_price=getattr(prior, "entry_price", None),
                        high_watermark=getattr(prior, "high_watermark", None),
                        stop_price=getattr(prior, "stop_price", None),
                        t1_state=getattr(prior, "t1_state", None),
                        trailing_state=getattr(prior, "trailing_state", None),
                        # Una reconstrucción ajusta la CANTIDAD contra el canónico;
                        # jamás el plan operativo ni la atribución de estrategia (si
                        # siguen siendo válidos, sobreviven tal cual).
                        strategy_version_id=getattr(prior, "strategy_version_id", None),
                        position_state=getattr(prior, "position_state", None),
                    )
            if verdict.status in {POSITION_PROJECTION_DIVERGENT, POSITION_PROJECTION_UNKNOWN}:
                logger.warning(
                    "auto_sim position reconciliation=%s symbol=%s (aperturas vetadas)",
                    verdict.status,
                    symbol,
                )
        # V2.43.3 (P0-1) — productor real de la parada dura: una identidad de ejecución
        # DUPLICADA en el libro canónico significa que el mismo hecho financiero llegó dos
        # veces (o que una fuente lo reintrodujo). El fold lo deduplica y declara la
        # violación, pero un sistema que ve dinero duplicado no debe seguir abriendo: se
        # para HASTA que una reconciliación explícita lo levante.
        seen_execution_ids: set[str] = set()
        for fact in getattr(canonical, "facts", ()) or ():
            key = str(getattr(fact, "execution_id", "") or "").strip()
            if not key:
                continue
            if key in seen_execution_ids:
                logger.error("auto_sim duplicate execution id detected id=%s; HALT", key)
                await self.engage_kill_switch_durable("DUPLICATE_EXECUTION")
                break
            seen_execution_ids.add(key)
        return canonical_map

    def _openings_vetoed(self, symbol: str) -> bool:
        """True si la reconciliación de ese símbolo impide nuevas aperturas."""
        return self._reconciliation.get(symbol) in {
            POSITION_PROJECTION_DIVERGENT,
            POSITION_PROJECTION_UNKNOWN,
        }

    async def _persist_position(self, symbol: str, qty: Decimal) -> None:
        """Espeja la posición abierta + su estado de protección (P1-06 / P2-01).

        qty<=0 ⇒ ``delete`` (posición cerrada); qty>0 ⇒ ``upsert`` con
        ``entry_price``/``high_watermark`` durables. Sin ``position_store``
        (hermético) o ante error del espejo, NO se rompe el turno: la posición en RAM
        sigue siendo la autoridad del tick y el espejo se reintentará al siguiente
        (el dinero ya está aplicado idempotente por fill).
        """
        if self._position_store is None:
            return
        account_id = self._account_id
        if not account_id:
            return
        try:
            if qty is None or qty <= 0:
                await self._position_store.delete(account_id, self._engine_id, symbol)
                self._open.pop(symbol, None)
            else:
                await self._position_store.upsert(
                    account_id,
                    self._engine_id,
                    symbol,
                    qty,
                    entry_price=self._entry_price.get(symbol),
                    high_watermark=self._high_price.get(symbol),
                    # V2.32/A12: la versión que abrió la posición viaja al espejo
                    # durable para sobrevivir al crash y restaurarse en readopt.
                    strategy_version_id=self._position_version.get(symbol),
                    # AUTO 2.0 · P4: el plan operativo V2 (stop vigente, objetivos,
                    # parciales, trailing) se persiste en cada cambio de cantidad. Si
                    # no hay plan vivo, ``**{}`` deja las columnas V2 intactas.
                    **self._v2_durable_state(symbol),
                )
        except Exception:  # noqa: BLE001 — el espejo durable nunca tumba el turno SIM.
            logger.exception("auto_sim persist_position failed symbol=%s", symbol)

    def _v2_durable_state(self, symbol: str) -> dict[str, Any]:
        """AUTO 2.0 · P4: plan operativo vivo serializado para el espejo durable.

        Devuelve ``{}`` cuando no hay plan V2 vivo (V2 off, o sin ``PositionState`` para
        el símbolo): el espejo queda entonces SIN plan (NULL), que es la verdad — no se
        inventa un plan operativo que el motor no está siguiendo.
        El plan viaja como ``PositionState.to_dict()`` (rehidratable exacto con
        ``position_state_from_dict``): es el estado que DEBE sobrevivir al crash.
        """
        if not self._v2_enabled:
            return {}
        position = self._v2_positions.get(symbol)
        if position is None:
            return {}
        target1 = getattr(position, "target1_leg", None)
        # AUTO-2: la columna ``trailing_state`` refleja el FSM tipado (no el string de un
        # dict vacío). El FSM completo (``lifecycleState``, ``trailing``, ``protection``)
        # viaja DENTRO del JSONB ``position_state``: no hay columna nueva ni migración.
        return {
            "position_state": position.to_dict(),
            "avg_price": _dec_or_none(position.actual_entry),
            "stop_price": _dec_or_none(position.current_stop),
            "t1_state": getattr(target1, "status", None) if target1 else None,
            "trailing_state": trailing_status(position),
        }

    def _next_logical_order_id(
        self, symbol: str, side: str, exit_order_id: str | None = None
    ) -> str:
        """P1-03: identidad lógica única por INTENCIÓN (namespace del execution_id).

        V2.43.3: una salida con ``exit_order_id`` embebe su identidad durable, de modo que
        ``logical_order_id`` → ``venue_order_id`` → ``execution_id`` queden atribuidos al
        INTENT concreto (y un reinicio no re-genere la misma traza por casualidad).

        W3 (v2.88.16): la intención SIN identidad durable se ancla a la **barra** (tick de
        barra + ordinal de la intención dentro de esa barra), no al minuto. Es lo que hace
        que un reintento intra-barra del MISMO intento reproduzca el mismo ``execution_id``
        (el ledger lo resuelve ``already_applied``) en vez de abrir una segunda ejecución.
        El ordinal se reinicia al cambiar de barra: una intención NUEVA de otra barra no
        colisiona con la anterior.
        """
        if exit_order_id:
            return f"{self._engine_id}-{side}-{symbol}-{exit_order_id}"
        # ``_order_seq`` es el contador MONOTÓNICO de INTENT de entrada del worker
        # (telemetría y el invariante de AUTO-6 ``Σ _order_seq == 1``): se incrementa
        # exactamente donde lo hacía antes de W3 (una entrada emitida), mientras que la
        # IDENTIDAD de la orden pasa a anclarse a la barra.
        self._order_seq += 1
        bar = self._v2_current_bar_start()
        if bar != self._v2_intent_bar:
            self._v2_intent_bar = bar
            self._v2_intent_seq.clear()
        key = (str(side).strip().lower(), str(symbol).strip())
        ordinal = self._v2_intent_seq.get(key, 0) + 1
        self._v2_intent_seq[key] = ordinal
        return f"{self._engine_id}-{self._v2_bar_tick()}-{side}-{symbol}-{ordinal}"

    # ---- gate fail-closed / de autoridad (Bloque 3) --------------------------
    def _kill_active(self) -> bool:
        """True si el kill switch está activo (o NO se puede leer; fail-closed)."""
        try:
            return bool(self._kill_switch_source())
        except Exception:  # noqa: BLE001 — no saber ⇒ bloquear el motor AUTO.
            return True

    # ---- consulta / estado -----------------------------------------------------
    @property
    def minute(self) -> int:
        return self._minute

    @property
    def time(self) -> datetime:
        return self._time

    @property
    def open_symbols(self) -> tuple[str, ...]:
        return tuple(s for s, q in self._open.items() if q > 0)

    def journal_pairs(self) -> tuple[SimJournalRow, ...]:
        """Filas de journal completas del día simulado hasta ahora (M7)."""
        return tuple(self._journal)

    def atr_source_counts(self) -> Mapping[str, int]:
        """V2.42 slice 2c: procedencia del ATR de las candidatas del día (medición).

        Cuenta las señales evaluadas por origen (``real``/``fallback``/``missing``): es la
        medición con la que se decide el flip del veto de ATR (D3), no un juicio. Sin
        señales el mapa queda a cero (jamás se asume una procedencia).
        """
        return dict(self._v2_atr_source_counts)

    def opportunity_rows(self) -> tuple[OpportunityRow, ...]:
        """V2.45/AUTO-5 — embudo del día: oportunidades con su estado FINAL y su motivo.

        Cada fila es UNA oportunidad vista (o la mejor candidata por instrumento dentro del
        tick) con ``traded``/``rejected``/``expired``/``missed``. Las rechazadas llevan su
        ``reason`` tipificado y, cuando el dato existe, su precio posterior (coste de
        oportunidad). El agregado puro (``build_auto_daily_report``) certifica el cierre.
        """
        return tuple(self._v2_opportunities)

    def seen_signals(self) -> int:
        """V2.45/AUTO-5 — candidatas vistas en el día (contador INDEPENDIENTE de las filas)."""
        return int(self._v2_seen_signals)

    def operation_measurements(self) -> tuple[OperationMeasurement, ...]:
        """V2.45/AUTO-5 — MAE/MFE por operación cerrada (recogido del JSONB, no calibrado)."""
        return tuple(self._v2_operation_measurements)

    def _v2_mfe_mae_snapshot(self, symbol: str) -> Mapping[str, Any]:
        """``mfe_mae`` vigente del PositionState (copia), o vacío si no hay estado."""
        position = self._v2_positions.get(symbol)
        raw = getattr(position, "mfe_mae", None)
        return dict(raw) if isinstance(raw, Mapping) else {}

    def _v2_record_operation_measurement(
        self,
        symbol: str,
        strategy_version: str | None,
        mfe_mae: Mapping[str, Any],
    ) -> None:
        """Registra el MAE/MFE de la operación cerrada. Sin números NO se registra.

        ``mfeR``/``maeR`` viven en R en el JSONB del PositionState (fuente única): aquí solo
        se copian. Si el estado no los trae (o trae ``None``), la operación queda sin fila y
        el día publica la medición como ``UNKNOWN``/``PARTIAL`` — jamás un 0 inventado.
        """
        mfe = _dec_or_none(mfe_mae.get("mfeR"))
        mae = _dec_or_none(mfe_mae.get("maeR"))
        if mfe is None and mae is None:
            return
        self._v2_operation_measurements.append(
            OperationMeasurement(
                instrument_id=symbol,
                strategy_version=str(strategy_version or ""),
                mfe=mfe,
                mae=mae,
            )
        )

    @property
    def reconciliation_status(self) -> dict[str, str]:
        """V2.24.2 (P2-C) — estado de reconciliación por símbolo (observabilidad)."""
        return dict(self._reconciliation)

    @property
    def reconciliation_blocks_openings(self) -> bool:
        """True si ALGÚN símbolo reconciliado veta nuevas aperturas (fail-closed)."""
        return any(
            status in {POSITION_PROJECTION_DIVERGENT, POSITION_PROJECTION_UNKNOWN}
            for status in self._reconciliation.values()
        )

    def _venue(self) -> str:
        return normalized_auto_venue(_effective_venue()) or "paper"

    def _advance(self) -> datetime:
        self._minute += 1
        self._time = self._clock()
        return self._time

    # ---- W4 (v2.88.17): precio con estado «NO HAY PRECIO» (fail-closed) ------------
    def _v2_price_exec(self, symbol: str, tick: int) -> float | None:
        """Precio de EJECUCIÓN/MARCA del tick — o ``None`` si **no hay precio**.

        Sin fuente real (``price_source is None``) se lee ``price_script`` **en vivo** con
        el MISMO ``tick`` que usaba cada llamante ⇒ comportamiento byte a byte idéntico al
        anterior (``Δ = 0``): el fail-closed sólo puede dispararse con una fuente real.
        """
        source = self._price_source
        if source is None:
            value = self._price_script(symbol, tick)
            return None if value is None else float(value)
        try:
            return source.execution(symbol)
        except Exception:  # noqa: BLE001 — un fallo de precio ES «no hay precio».
            logger.exception("auto_sim v2 price_source.execution failed symbol=%s", symbol)
            return None

    def _v2_price_mid(self, symbol: str, tick: int) -> float | None:
        """Precio de DECISIÓN (con fuente real, ``close`` de la última barra cerrada).

        Mismo contrato de ``Δ = 0`` que ``_v2_price_exec`` para el camino hermético.
        """
        source = self._price_source
        if source is None:
            value = self._price_script(symbol, tick)
            return None if value is None else float(value)
        try:
            return source.mid(symbol)
        except Exception:  # noqa: BLE001
            logger.exception("auto_sim v2 price_source.mid failed symbol=%s", symbol)
            return None

    def _v2_note_price_missing(self, symbol: str) -> None:
        """Declara y CUENTA una ausencia de precio (una vez por símbolo en el log).

        Es la mitad declarativa del fail-closed: sin precios reales (default hermético)
        esto NO se ejecuta nunca, así que no altera ningún resultado (``Δ = 0``).
        """
        count = self._v2_price_missing.get(symbol, 0) + 1
        self._v2_price_missing[symbol] = count
        if count == 1:
            logger.warning(
                "auto_sim v2 precio AUSENTE symbol=%s: no se ejecuta/marca "
                "(HOLD fail-closed; jamás 100.0/0 silencioso)",
                symbol,
            )

    @property
    def price_missing_counts(self) -> Mapping[str, int]:
        """W4: nº de lecturas con precio AUSENTE por símbolo (observabilidad del fail-closed)."""
        return dict(self._v2_price_missing)

    def _v2_price_source_kind(self) -> str | None:
        """v2.88.25 — la FUENTE canónica que construye el precio del tick, o ``None``.

        Con ``PriceSource`` inyectada se lee su ``kind`` (``MARKET_CLOSE`` para el OHLCV real,
        ``SYNTHETIC`` para un script constante...). Sin ella se lee ``price_script`` en vivo: si
        es el ``flat_price_script`` hermético el precio es FABRICADO (``SYNTHETIC``); un script
        distinto (replay/tests) se declara ``SCRIPT``. Nunca un literal inventado."""
        source = self._price_source
        if source is None:
            return (
                PRICE_SOURCE_SYNTHETIC
                if self._price_script is flat_price_script
                else PRICE_SOURCE_SCRIPT
            )
        return price_source_kind(source)

    # ---- settlement vía dominio (M1/M2). Fail-closed sin exec_store. ----------
    async def _settle(
        self,
        side: str,
        symbol: str,
        qty: Decimal,
        strategy_version_id: str | None = None,
        exit_order_id: str | None = None,
        cycle_id: str | None = None,
    ) -> _Settlement:
        """Liquida la orden SIM y separa lo MATERIALIZADO de lo que quedó PENDIENTE.

        AUTO-1A (P0): antes se devolvían TODOS los fills del schedule y el llamante los
        contaba con la cantidad PEDIDA, de modo que un llenado parcial (p. ej. 50 + 23,5
        de 100) producía una posición de 100 y un exit de 100 sobre 73,5 reales. Ahora se
        cruza el resultado del settlement con el outcome durable del apply: solo
        ``applied``/``already_applied`` movió dinero.
        """
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
            )
        except Exception:  # noqa: BLE001 — un fallo de settlement no tumba el motor.
            # Fail-closed: un problema al persistir contexto/aplicar dinero NO debe
            # romper el turno AUTOnomo (se degrada a "sin fill este tick"). El motor
            # reintentará; jamás se fabrica una posición sin settlement confirmado.
            logger.exception("auto_sim settle failed symbol=%s side=%s", symbol, side)
            return _Settlement(requested_qty=qty, structural=structural)
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

    # ---- journal de fila: mantiene el día y ofrece el turno --------------------
    def _record_applied_event(self, symbol: str, fill: FillObservation, price: Decimal) -> None:
        """P1-01/P2-02: registra el fill aplicado para poder reconciliar la posición.

        La reconciliación compara los ``ExecutionEvents`` esperados (BUY − SELL) con
        la posición canónica y la proyección. Se guarda la identidad + lado + qty del
        fill confirmado por el settlement (misma fuente que el journal).
        """
        events = getattr(self, "_applied_execution_events", None)
        if events is None:
            events = []
            self._applied_execution_events = events
        events.append(
            _AppliedFill(
                symbol=symbol,
                side=fill.side,
                qty=Decimal(str(fill.qty)),
                price=price,
                execution_id=fill.execution_id,
                venue=fill.venue,
            )
        )

    def _emit(
        self,
        kind: str,
        venue: str,
        exec_id: str | None,
        side: str,
        qty: Decimal,
        *,
        reason: str = "",
        strategy_version: str | None = None,
    ) -> SimJournalRow:
        row = SimJournalRow(
            kind=kind,
            venue=venue,
            execution_id=exec_id or f"noex-{kind}",
            side=side,
            qty=qty,
            reason=reason,
            # V2.45/AUTO-5 — atribución por estrategia de la fila del día (aditiva): la
            # apertura la aporta la propuesta y el cierre la hereda de la posición. Sin
            # versión la fila NO se atribuye (la ausencia es información).
            strategy_version=str(strategy_version or ""),
        )
        self._journal.append(row)
        return row

    # ---- AUTO 2.0 (V2): decisión de entradas y de posición (env-gated) --------
    def v2_enabled(self) -> bool:
        """True si el pipeline AUTO 2.0 gestiona la decisión (env-gated, default OFF)."""
        return self._v2_enabled

    def _v2_regime(self) -> str | None:
        """Régimen operativo del tick (override de env > fuente inyectada > None).

        Sin régimen el pipeline V2 queda en UNKNOWN ⇒ exit-only (fail-closed): no se
        abren entradas nuevas si no se puede determinar el régimen.
        """
        override = self._v2_tunables.regime_override
        if override:
            return override
        if self._v2_regime_source is None:
            return None
        try:
            return self._v2_regime_source()
        except Exception:  # noqa: BLE001 — sin régimen no se inventan entradas.
            logger.exception("auto_sim v2 regime_source failed")
            return None

    def _v2_equity(self) -> float:
        """Equity del tick.

        El turno real (``load_book_equity``) usa el cash y el valor de mercado del
        libro. Si esa lectura falta o no es positiva, devuelve 0 y las aperturas
        quedan vetadas: no hay caída a ``AUTO_ENGINE_SIM_V2_EQUITY`` ni a 100_000.
        El camino hermético, que no carga el libro, conserva el env o 100_000.
        """
        equity, _unreadable = turn_equity_from_book(
            self._book_equity,
            required=self._book_equity_required,
            unreadable=self._book_equity_unreadable,
            env_raw=(os.getenv("AUTO_ENGINE_SIM_V2_EQUITY") or "").strip(),
        )
        return equity

    async def load_book_equity(self, session: Any) -> None:
        """Lee ``PortfolioSummary.total_equity`` y lo deja como autoridad del tick."""
        self._book_equity_required = True
        try:
            equity = await read_account_book_equity(session, self._account_id)
        except Exception:
            logger.exception(
                "auto_sim book equity unreadable account=%s",
                self._account_id,
            )
            self._book_equity = None
            self._book_equity_unreadable = True
            return
        if equity <= 0:
            self._book_equity = None
            self._book_equity_unreadable = True
            return
        self._book_equity = equity
        self._book_equity_unreadable = False

    def _v2_governor_drawdown_pct(self) -> float | None:
        """Drawdown diario MEDIDO de la cuenta para el gobernador (V2.43/AUTO-3).

        Se calcula sobre la equity **marcada a mercado** del tick: base declarada
        (``AUTO_ENGINE_SIM_V2_EQUITY``) + P&L realizado acumulado + P&L no realizado de
        las posiciones vivas (marca vs entrada). Es la contabilidad que el worker ya usa
        para valorar la cartera (``_v2_snapshot``), expuesta como serie temporal.

        Devuelve ``None`` con el flag OFF: así el camino por defecto no paga ni el
        cómputo y el eje de riesgo queda ``UNKNOWN`` (fail-closed) si alguien lo pidiera.
        """
        if not self._v2_tunables.governor_enabled:
            return None
        base = self._v2_equity()
        unrealized = Decimal("0")
        for symbol, qty in self._open.items():
            if qty <= 0:
                continue
            entry = self._entry_price.get(symbol)
            if entry is None:
                continue
            raw_price = self._v2_price_exec(symbol, self._v2_bar_tick())
            if raw_price is None:
                # W4: precio AUSENTE ⇒ este símbolo no se marca/no genera señal (fail-closed
                # declarado). Antes ``... or 0`` producía un ``Decimal("0")`` que el
                # ``if price > 0`` descartaba EN SILENCIO: mismo efecto, sin declararlo.
                self._v2_note_price_missing(symbol)
                continue
            price = Decimal(str(raw_price))
            if price > 0:
                unrealized += (price - entry) * qty
        equity = Decimal(str(base)) + self._sim_realized_pnl + unrealized
        marks = self._v2_equity_marks.update(
            self._account_id or "auto-sim",
            float(equity),
            initial_deposit=base,
            now=self._v2_marks_now(),
        )
        return marks.daily_pct

    def _v2_marks_now(self) -> Any:
        """Instante UTC de la marca de equity (inyectable en tests vía ``_time``)."""
        raw = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

    def _v2_kill_switch_halted(self) -> bool:
        """True si la parada DURA latcheada está activa (V2.44)."""
        switch = getattr(self, "_v2_kill_switch", None)
        return bool(switch is not None and switch.engaged)

    def _v2_kill_state(self, *, at: str | None = None) -> KillState | None:
        """Foto durable del latch actual; ``None`` sin cuenta/engine (no persistible)."""
        switch = self._v2_kill_switch
        account_id = self._account_id or ""
        engine_id = self._engine_id or ""
        if not account_id or not engine_id:
            return None
        return KillState(
            account_id=account_id,
            engine_id=engine_id,
            engaged=switch.engaged,
            reason=switch.reason,
            engaged_at=switch.engaged_at,
            engagement_id=switch.engagement_id,
            reengagements=switch.reengagements,
            updated_at=at or self._v2_instant(),
        )

    async def _v2_load_kill_state(self) -> None:
        """Restaura el latch desde su espejo durable (V2.43.3 · P0-1).

        Se llama en cada turno real ANTES de readoptar posición y de reconciliar. Regla de
        adopción, unidireccional a propósito:

        * una parada durable ``engaged`` se adopta SIEMPRE (jamás se ignora un HALT
          persistido: el reinicio no puede reabrir el motor);
        * una parada durable liberada NO levanta un halt local (el latch es monótono dentro
          del proceso: solo una liberación explícita lo quita, y esa liberación ya pasa por
          ``release_kill_switch``).

        Sin store (o sin cuenta/engine) no hay nada que leer: se declara y el latch local se
        conserva. Un fallo de lectura tampoco levanta la parada.
        """
        store = self._kill_switch_store
        account_id = self._account_id or ""
        engine_id = self._engine_id or ""
        self._v2_kill_state_loaded = True
        if store is None or not account_id or not engine_id:
            return
        try:
            state = await store.load(account_id, engine_id)
        except Exception:  # noqa: BLE001 — no poder leer no autoriza a operar.
            logger.exception("auto_sim v2 kill state load failed")
            return
        if state is None:
            return
        if state.engaged:
            if self._v2_kill_switch.engaged:
                return
            self._v2_kill_switch = HardKillSwitch.from_persisted(
                engaged=True,
                reason=state.reason,
                engaged_at=state.engaged_at,
                engagement_id=state.engagement_id,
                reengagements=state.reengagements,
            )
            logger.warning(
                "auto_sim v2 hard kill RESTORED from durable state reason=%s engagement=%s",
                state.reason,
                state.engagement_id,
            )
            return
        # La fila durable está LIBERADA. Un HALT local solo se levanta por una liberación
        # durable EXPLÍCITA (con reconciliación) y POSTERIOR a la activación: es la vía por
        # la que un operador (o el proceso de la API) levanta la parada de ESTE worker sin
        # reiniciarlo. Una fila liberada más ANTIGUA que el halt local no lo revive al revés
        # (una re-activación posterior manda sobre un release previo): por eso se comparan
        # instantes, nunca texto.
        if not self._v2_kill_switch.engaged or not state.release_reconciliation_id:
            return
        released_at = _instant(state.released_at)
        engaged_at = _instant(self._v2_kill_switch.engaged_at)
        if released_at is None or engaged_at is None or released_at < engaged_at:
            return
        self._v2_kill_switch.release(reconciliation_ok=True)
        logger.warning(
            "auto_sim v2 hard kill RELEASED by durable reconciliation=%s actor=%s",
            state.release_reconciliation_id,
            state.release_actor,
        )

    async def _v2_persist_kill_state(self, *, at: str | None = None) -> bool:
        """Persiste el latch actual; ``False`` si no fue durable.

        Fail-closed en la dirección que importa: un fallo de escritura NO desactiva la
        parada (el latch sigue in-memory y se declara). Lo que no se hace es creer que el
        sistema está protegido por un HALT que nadie podrá leer tras un crash.
        """
        store = self._kill_switch_store
        state = self._v2_kill_state(at=at)
        if store is None or state is None:
            return False
        try:
            await store.save(state)
            await store.commit()
        except Exception:  # noqa: BLE001 — no persistir no levanta la parada.
            logger.exception("auto_sim v2 kill state persist failed reason=%s", state.reason)
            return False
        return True

    def engage_kill_switch(
        self,
        reason: Any,
        *,
        at: str | None = None,
        engagement_id: str | None = None,
    ) -> bool:
        """Activa la parada dura con un motivo tipificado (V2.44 · V2.43.3).

        Es idempotente y latcheada: reavisar no reinicia el motivo original. Devuelve True
        si CAMBIÓ el estado. La activación asigna una identidad (``engagement_id``) para que
        el rastro sea auditable ("qué activación concreta paró el sistema"). Esta variante
        solo mueve el latch; la persistencia durable la hace ``engage_kill_switch_durable``.
        """
        changed = self._v2_kill_switch.engage(
            reason, at=at or self._v2_instant(), engagement_id=engagement_id
        )
        if changed and self._v2_kill_switch.engagement_id is None:
            self._v2_kill_switch.engagement_id = new_exit_order_id()
        return changed

    async def engage_kill_switch_durable(self, reason: Any, *, at: str | None = None) -> bool:
        """Activa la parada dura Y la persiste (P0-1), para que sobreviva al reinicio.

        Si el persist falla, el latch se mantiene (nunca se levanta la parada por un fallo
        de escritura) y el fallo queda declarado en el log.
        """
        changed = self.engage_kill_switch(reason, at=at)
        await self._v2_persist_kill_state(at=at)
        return changed

    def release_kill_switch(
        self,
        *,
        reconciliation_ok: bool,
        reconciliation_id: str | None = None,
    ) -> bool:
        """Libera la parada SOLO con reconciliación explícita (nunca por sí sola).

        V2.43.3: para liberar de verdad hace falta una ``reconciliation_id`` (la identidad
        de la reconciliación que autoriza el levantamiento): un halt que se levanta "porque
        sí" no es auditable. Esta variante mueve el latch; la persistencia del rastro la
        hace ``release_kill_switch_durable``.
        """
        if reconciliation_ok and not reconciliation_id:
            logger.error("auto_sim v2 kill release rejected: missing reconciliation_id")
            return False
        return self._v2_kill_switch.release(reconciliation_ok=reconciliation_ok)

    async def release_kill_switch_durable(
        self, *, reconciliation_ok: bool, reconciliation_id: str | None = None
    ) -> bool:
        """Libera la parada Y persiste el rastro de la liberación (P0-1)."""
        released = self.release_kill_switch(
            reconciliation_ok=reconciliation_ok, reconciliation_id=reconciliation_id
        )
        if not released:
            return False
        await self._v2_persist_kill_release(reconciliation_id=reconciliation_id)
        return True

    async def _v2_persist_kill_release(self, *, reconciliation_id: str | None) -> bool:
        """Persiste ``engaged=False`` con el actor y la identidad de reconciliación."""
        store = self._kill_switch_store
        account_id = self._account_id or ""
        engine_id = self._engine_id or ""
        if store is None or not account_id or not engine_id:
            return False
        at = self._v2_instant()
        state = KillState(
            account_id=account_id,
            engine_id=engine_id,
            engaged=False,
            reason=None,
            engaged_at=None,
            engagement_id=None,
            reengagements=self._v2_kill_switch.reengagements,
            released_at=at,
            release_actor="auto_sim_worker",
            release_reconciliation_id=reconciliation_id,
            updated_at=at,
        )
        try:
            await store.save(state)
            await store.commit()
        except Exception:  # noqa: BLE001 — se declara; el latch in-memory ya está liberado.
            logger.exception("auto_sim v2 kill state release persist failed")
            return False
        return True

    def _v2_governor_position_inputs(self) -> dict[str, Any]:
        """Lectura del gobernador para la GESTIÓN de posición (V2.44 · AUTO-3 slice 2).

        Con el gobernador OFF devuelve todo ``None``: el manager sigue gobernado solo por
        el régimen de mercado (byte-idéntico al histórico). Con el gobernador ON evalúa el
        permiso del tick con la MISMA tabla que las entradas, más la parada dura.

        Ojo con la semántica: ``EXIT_ONLY``/``ENTRY_RESTRICTED`` vetan APERTURAS, pero NO
        liquidan por sí solos. La liquidación la piden ``RiskRegime == RISK_OFF`` (⇒
        ``RISK_EXIT``) y ``OperationalState == HALTED`` (⇒ ``KILL_SWITCH``).

        La parada DURA es INDEPENDIENTE del flag: con la parada activa se evalúa la tabla
        aunque el gobernador esté OFF (un kill switch no puede quedar desactivado por un
        flag de conveniencia).
        """
        kill = self._v2_kill_switch_halted()
        if not self._v2_tunables.governor_enabled and not kill:
            return {"risk_regime": None, "drawdown_band": None, "operational_state": None}
        drawdown_pct = self._v2_governor_drawdown_pct()
        assessment = assess_from_measurements(
            operational_regime=self._v2_regime(),
            drawdown_pct=drawdown_pct,
            drawdown_measurement=(
                MEASUREMENT_COMPLETE if drawdown_pct is not None else MEASUREMENT_UNKNOWN
            ),
            # La gestión de posición no decide el tamaño por ATR/liquidez: se declaran
            # desconocidos (fail-closed) para no relajar el permiso por un dato ausente.
            atr_known=False,
            liquidity_known=False,
            liquidity_notional=None,
            policy=self._v2_tunables.governor_policy(),
            halted=self._v2_kill_switch_halted(),
        )
        return {
            "risk_regime": assessment.risk_regime,
            "drawdown_band": assessment.drawdown_band,
            "operational_state": assessment.state,
        }

    def _v2_data_freshness(self) -> Any:
        """Frescura por dimensión del tick (V2.44).

        Por defecto ``market_data``/``quote`` se consideran fechados AHORA (el sim genera
        precios cada tick); un test o un feed parado pueden fijar
        ``_v2_data_timestamps['market_data']`` a un instante viejo para provocar el veto.
        """
        now = self._v2_marks_now().timestamp()
        stamps = getattr(self, "_v2_data_timestamps", {})
        return assess_data_freshness(
            now=now,
            market_data_at=stamps.get("market_data", now),
            atr_at=stamps.get("atr"),
            quote_at=stamps.get("quote", stamps.get("market_data", now)),
            volume_at=stamps.get("volume"),
            policy=getattr(self, "_v2_freshness_policy", FreshnessPolicy()),
        )

    def _v2_snapshot(self, regime: str | None) -> Any:
        """Construye la foto canónica del tick desde el libro del worker."""
        equity = self._v2_equity()
        invested = Decimal("0")
        marks: dict[str, float] = {}
        for symbol, qty in self._open.items():
            if qty <= 0:
                continue
            raw_price = self._v2_price_exec(symbol, self._v2_bar_tick())
            if raw_price is None:
                # W4: precio AUSENTE ⇒ este símbolo no se marca/no genera señal (fail-closed
                # declarado). Antes ``... or 0`` producía un ``Decimal("0")`` que el
                # ``if price > 0`` descartaba EN SILENCIO: mismo efecto, sin declararlo.
                self._v2_note_price_missing(symbol)
                continue
            price = Decimal(str(raw_price))
            if price > 0:
                marks[symbol] = float(price)
                invested += qty * price
        cash = max(Decimal("0"), Decimal(str(equity)) - invested)
        return build_worker_snapshot(
            account_id=self._account_id or "auto-sim",
            equity=equity,
            cash=float(cash),
            open_positions={s: float(q) for s, q in self._open.items() if q > 0},
            entry_prices={s: float(p) for s, p in self._entry_price.items()},
            marks=marks,
            stops=self._v2_stop_map(),
            sectors=self._v2_open_sectors(),
            strategies=tuple(sorted(set(self._position_version.values()))),
            regime=regime,
            risk_budget_pct=self._v2_tunables.risk_budget_pct,
            reconciliation_ok=not self.reconciliation_blocks_openings,
            open_orders=self._v2_pending_open_orders(),
            order_book_measurement=self._v2_pending_book_measurement(),
            drawdown_pct=self._v2_governor_drawdown_pct(),
            # V2.44: la frescura por dimensión entra en el snapshot. Con mercado stale el
            # motor veta APERTURAS (``stale_data``); las salidas protectoras no consultan
            # el snapshot, así que siguen vivas (invariante de la casa).
            data_freshness=self._v2_data_freshness().data_freshness,
        )

    def _v2_open_sectors(self) -> dict[str, str]:
        """Sector (solo ``KNOWN``) de las posiciones ABIERTAS para el snapshot.

        V2.40.1: si el sector de una posición no es fiable (desconocido, en conflicto con
        el catálogo o caducado) NO se publica. La posición queda OPACA a propósito: así el
        motor detecta que la exposición sectorial no es verificable y veta nuevas entradas
        con ``sector_exposure_unverifiable``, en vez de que todas las posiciones caigan al
        cajón ``<unknown>`` y un candidato se mida solo contra sí mismo.
        """
        symbols = [symbol for symbol, qty in self._open.items() if qty > 0]
        return self._v2_sectors_for(symbols)

    def _v2_sectors_for(self, symbols: Sequence[str]) -> dict[str, str]:
        """Sector (solo ``KNOWN``) de los símbolos dados, con el seam inyectado.

        V2.40.1: un sector no fiable (desconocido, en conflicto con el catálogo o
        caducado) NO se publica: la posición queda OPACA a propósito. V2.40.4 reutiliza
        esta misma resolución para los instrumentos con orden pendiente.
        """
        if not symbols:
            return {}
        if self._v2_trade_context_source is not None:
            return self._v2_trade_context_source.known_sectors(list(symbols))
        if self._v2_sector_source is None:
            return {}
        sectors: dict[str, str] = {}
        for symbol in symbols:
            try:
                sector = self._v2_sector_source(symbol)
            except Exception:  # noqa: BLE001 — sin sector la posición queda opaca.
                logger.exception("auto_sim v2 sector_source failed symbol=%s", symbol)
                continue
            if isinstance(sector, str) and sector.strip():
                sectors[symbol] = sector.strip()
        return sectors

    def _v2_atr_geometry(self, symbol: str, price: float) -> tuple[float | None, str]:
        """ATR real si existe; si no, el fallback declarado; ``missing`` si nada.

        V2.42 slice 2b (E2 · D3). Antes ``_v2_signals`` FABRICABA el ATR sintético en el
        origen, pisando la rama de ``plan_v2_tick`` que ya prefería el real. Aquí se
        devuelve ``(atr, source)`` y NUNCA se disfraza la reserva de dato real.
        """
        real = None
        if self._v2_atr_source is not None:
            try:
                raw = self._v2_atr_source(symbol)
            except Exception:  # noqa: BLE001 — sin dato se cae al fallback declarado.
                logger.exception("auto_sim v2 atr_source failed symbol=%s", symbol)
                raw = None
            if raw is not None:
                try:
                    candidate = float(raw)
                except (TypeError, ValueError):
                    candidate = 0.0
                if candidate == candidate and candidate > 0 and candidate != float("inf"):
                    real = candidate
        if real is not None:
            return real, ATR_SOURCE_REAL
        if price > 0:
            return price * self._v2_tunables.atr_pct_fallback, ATR_SOURCE_FALLBACK
        return None, ATR_SOURCE_MISSING

    def _v2_stop_map(self) -> dict[str, float]:
        """Stop vivo por símbolo (del PositionState V2 si existe; si no, el implícito)."""
        stops: dict[str, float] = {}
        for symbol, position in self._v2_positions.items():
            stop = position.current_stop or position.initial_stop
            if stop is not None and stop > 0:
                stops[symbol] = float(stop)
        # Sin estado V2 (posición readoptada) el stop aún no está adoptado: se estima
        # con la misma geometría del pipeline para que el riesgo consumido no sea 0.
        # E2: la geometría usa el ATR REAL cuando existe (antes siempre el sintético).
        for symbol in self._open:
            if symbol in stops:
                continue
            entry = self._entry_price.get(symbol)
            if entry is None or entry <= 0:
                continue
            atr, _source = self._v2_atr_geometry(symbol, float(entry))
            if atr is None:
                continue
            atr_dec = Decimal(str(atr))
            stop = entry - Decimal(str(self._v2_tunables.atr_multiplier)) * atr_dec
            if 0 < stop < entry:
                stops[symbol] = float(stop)
        return stops

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

    def _v2_signals(self, packages: Mapping[str, Any] | None = None) -> list[V2Signal]:
        """Recoge las señales crudas del decider para el tick (una por símbolo)."""
        resolved = self._v2_collect_packages() if packages is None else dict(packages)
        signals: list[V2Signal] = []
        self._v2_tick_signals = {}
        for symbol, pkg in resolved.items():
            symbol = symbol.strip()
            if not symbol:
                continue
            # W4 §3.1: este precio es el ANCLA DE ENTRADA de la geometría (``signal.price``
            # → ``entry_price``/``atr = price * atr_pct``), es decir el precio de DECISIÓN
            # ⇒ lee ``mid`` (con fuente real, ``close(B-1)``; sin lookahead). El *fill*
            # ancla en ``execution`` (``open(B)``) en ``_settle``: son fronteras distintas
            # a propósito, y su diferencia ES el hueco decisión→ejecución del modelo.
            raw_price = self._v2_price_mid(symbol, self._v2_bar_tick())
            if raw_price is None:
                # W4: precio AUSENTE ⇒ este símbolo NO genera señal (fail-closed declarado).
                # Antes ``... or 0`` producía un ``Decimal("0")`` del que sólo el
                # ``signal.price > 0`` aguas abajo impedía una geometría con stop en 0.
                self._v2_note_price_missing(symbol)
                continue
            price = Decimal(str(raw_price))
            action = str(getattr(pkg, "action", "HOLD")).upper()
            version = _strategy_version_from_source(getattr(pkg, "source", None))
            identity = signal_identity_for_bar(
                instrument_id=symbol,
                action=action,
                # Sin versión declarada se deduplica por el centinela explícito
                # ``unversioned`` (una estrategia que no se identifica sigue sin poder
                # repetir la MISMA señal sobre la MISMA barra).
                strategy_version=version or "unversioned",
                timeframe=self._v2_granularity.decision.timeframe,
                moment=self._time,
            )
            signal_id = identity.signal_id if identity is not None else ""
            if signal_id:
                self._v2_tick_signals[symbol] = signal_id
            context = self._v2_context(symbol, pkg)
            atr, atr_source = self._v2_atr_geometry(symbol, float(price))
            self._v2_atr_source_counts[atr_source] = (
                self._v2_atr_source_counts.get(atr_source, 0) + 1
            )
            if atr_source != ATR_SOURCE_REAL:
                # E2: la reserva se DECLARA (nunca se disfraza de dato real). Con el veto
                # activo la señal además NO entra: el sintético no puede sostener una
                # geometría de riesgo que la política exige precisa.
                # Una sola entrada por (símbolo, origen): la ausencia de ATR real es una
                # propiedad de la geometría, no un suceso por turno.
                if self._v2_atr_journaled.get(symbol) != atr_source:
                    self._v2_atr_journaled[symbol] = atr_source
                    self._journal_position_event(
                        symbol,
                        ATR_GEOMETRY,
                        at=self._time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        detail={
                            "atrSource": atr_source,
                            "atr": atr,
                            "atrRequired": self._v2_tunables.atr_required,
                            "vetoed": self._v2_tunables.atr_required,
                        },
                    )
            elif self._v2_atr_journaled.get(symbol) != ATR_SOURCE_REAL:
                # Recuperación del dato real: se re-arma el memo para que una caída
                # posterior a sintético vuelva a declararse (una sola vez más).
                self._v2_atr_journaled[symbol] = ATR_SOURCE_REAL
            if self._v2_tunables.atr_required and atr_source != ATR_SOURCE_REAL:
                # Veto explícito: no se sustituye por el sintético. ``plan_v2_tick``
                # recibe ``atr=None`` y aplica su camino normal de NO ENTRY (que ya está
                # probado y journaliza su motivo), en vez de inventar geometría.
                signal_atr: float | None = None
            else:
                signal_atr = atr
            signals.append(
                V2Signal(
                    instrument_id=symbol,
                    action=action,
                    price=float(price),
                    atr=signal_atr,
                    edge=self._v2_edge(pkg, version or "unversioned"),
                    sector=context.sector,
                    liquidity_notional=context.liquidity_notional,
                    trade_context=context,
                    strategy_version=version,
                    signal_id=signal_id,
                    bar_timestamp=identity.bar_timestamp if identity is not None else "",
                    valid_until=identity.valid_until if identity is not None else "",
                )
            )
        return signals

    def _v2_sector(self, symbol: str, pkg: Any) -> str | None:
        """Sector del candidato para el gate de concentración sectorial.

        Prioridad: lo que declare la propia propuesta (``memo``, canal explícito de la
        estrategia) > el catálogo (contexto de cartera) > la fuente inyectada > ``None``
        (sector desconocido: el motor lo trata como caja opaca, nunca como "sin
        exposición sectorial").
        """
        declared = sector_from_package(pkg)
        if declared:
            return declared
        if self._v2_trade_context_source is not None:
            context = self._v2_trade_context_source.context_for(symbol, declared_sector=declared)
            if context.sector_is_known:
                return context.sector
            return None
        if self._v2_sector_source is None:
            return None
        try:
            return self._v2_sector_source(symbol)
        except Exception:  # noqa: BLE001 — sin sector no se inventa uno.
            logger.exception("auto_sim v2 sector_source failed symbol=%s", symbol)
            return None

    def _v2_context(self, symbol: str, pkg: Any) -> Any:
        """Estado explícito (sector/liquidez/frescura) del candidato.

        Con ``trade_context_source`` (producción) el estado sale del catálogo y su
        ``observed_at``: un dato caducado es ``STALE`` y uno en conflicto con el ``memo``
        es ``CONFLICTING``, así que el motor veta con motivo auditable. Sin esa fuente se
        construye desde lo declarado + la fuente sync de liquidez (presente ⇒ ``KNOWN``).
        """
        declared = sector_from_package(pkg)
        liquidity = self._v2_liquidity(symbol)
        if self._v2_trade_context_source is not None:
            return self._v2_trade_context_source.context_for(
                symbol,
                declared_sector=declared,
                liquidity_fallback=liquidity,
                as_of=self._time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        return TradeContext.from_legacy(
            sector=declared if declared else (self._v2_sector(symbol, pkg)),
            liquidity_notional=liquidity,
            correlation=None,
        )

    def _v2_liquidity(self, symbol: str) -> float | None:
        """ADV notional por símbolo de la fuente inyectada (``None`` si no hay dato)."""
        source = self._v2_liquidity_source
        if source is None:
            return None
        try:
            value = source(symbol)
        except Exception:  # noqa: BLE001 — sin liquidez no se inventa una.
            logger.exception("auto_sim v2 liquidity_source failed symbol=%s", symbol)
            return None
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _v2_edge(self, pkg: Any, strategy_version: str | None) -> float | None:
        """Edge de la oportunidad: ``memo edge=`` > EdgeReport persistido > nada.

        V2.40.1: no hay valor por defecto. "La estrategia no declara edge" NO puede
        significar "edge 0.9": el componente queda vacío (0) y el motor veta por
        ``edge_below_threshold``.

        La clave de búsqueda es la MISMA con la que se precarga el informe
        (``version or "unversioned"``, el centinela canónico de identidad de señal): sin
        esa normalización, una propuesta sin versión declarada nunca encontraría su
        EdgeReport persistido.
        """
        declared = _edge_from_package(pkg)
        if declared is not None:
            return declared
        source = self._v2_edge_source
        if source is None:
            return None
        return source.edge_for(strategy_version or "unversioned")

    async def _v2_refresh_trade_context(
        self, symbols: Sequence[str], versions: Sequence[str]
    ) -> None:
        """Precarga (async) el contexto de cartera y el edge del tick.

        El hot path decide de forma SÍNCRONA, así que el I/O se concentra aquí una vez por
        tick, igual que el régimen. Un fallo deja el dato ausente ⇒ el motor veta por
        ``sector_unknown``/``liquidity_unknown``/``edge_below_threshold`` (fail-closed),
        nunca asume que el instrumento es operable "porque no se pudo comprobar".
        """
        as_of = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        context_refresh = getattr(self._v2_trade_context_source, "refresh", None)
        if callable(context_refresh):
            try:
                await context_refresh(symbols, as_of=as_of)
            except Exception:  # noqa: BLE001 — sin contexto, el motor veta.
                logger.exception("auto_sim v2 trade context refresh failed")
        edge_refresh = getattr(self._v2_edge_source, "refresh", None)
        if callable(edge_refresh):
            try:
                await edge_refresh(versions, account_id=self._account_id)
            except Exception:  # noqa: BLE001 — sin edge, el motor veta.
                logger.exception("auto_sim v2 edge refresh failed")

    async def _v2_refresh_evidence(self, packages: Mapping[str, Any], regime: str | None) -> None:
        """Precarga (async) la evidencia LAB del campeón ACTIVE por instrumento.

        V2.88 / TOP3 cross-asset: mismo patrón que contexto/edge — I/O una vez por tick,
        lectura SÍNCRONA en el hot path. Sin fuente inyectada es un no-op (Δ = 0). Un
        fallo deja el mapa vacío ⇒ ``_v2_evidence_lookup`` devuelve ``None`` ⇒ scoring
        byte-idéntico al histórico (fail-closed: no se inventa evidencia).
        """
        source = self._v2_evidence_source
        if source is None:
            return
        refresh = getattr(source, "refresh", None)
        if not callable(refresh):
            return
        try:
            await refresh(tuple(packages), regime=regime)
        except Exception:  # noqa: BLE001 — sin evidencia, scoring histórico.
            logger.exception("auto_sim v2 strategy evidence refresh failed")

    def _v2_evidence_lookup(self, packages: Mapping[str, Any]) -> dict[str, dict[str, float]] | None:
        """Lookup síncrono ``instrument_id → components`` para ``plan_v2_tick``.

        ``None`` cuando no hay fuente o ningún instrumento tiene evidencia: el motor
        conserva el scoring histórico (solo edge+liquidity).
        """
        source = self._v2_evidence_source
        if source is None:
            return None
        components_for = getattr(source, "components_for", None)
        if not callable(components_for):
            return None
        lookup: dict[str, dict[str, float]] = {}
        for symbol in packages:
            comps = components_for(str(symbol))
            if isinstance(comps, dict):
                lookup[str(symbol)] = comps
        return lookup or None

    async def _v2_refresh_open_orders(self) -> None:
        """Precarga (async) las órdenes AUTO NO materializadas (V2.40.4 · P1).

        Productor real: ``execution_events`` en estado no-``APPLIED`` (fills capturados
        cuyo dinero aún no se ha movido) + ``sim_fill_finance_context`` (lado, cantidad,
        precio; su PK es ``execution_id``, ya indexada). Ese es el único rastro durable de
        capital comprometido que no está representado como posición.

        Dos filtros deliberados:

        * Solo cuentan las trazas cuyo fill **no está ya reconocido** por el libro del
          worker (``_applied_execution_events``). Si la posición ya está en ``self._open``
          su capital ya se descontó vía ``positions``; reservarlo otra vez contaría el
          mismo dinero dos veces. Tras un crash la memoria RAM está vacía ⇒ una traza
          huérfana SÍ aparece como pendiente (que es el caso que debe proteger).
          AUTO-1A: ese libro contiene SOLO fills materializados, de modo que un chunk en
          ``RETRY`` de un llenado parcial sigue apareciendo como capital pendiente (antes
          entraba como "conocido" y desaparecía del libro).
        * Los sectores de los instrumentos pendientes se resuelven con el mismo seam que
          los de las posiciones abiertas (sin I/O extra: la fuente ya se refrescó).

        Fail-closed: sin store no hay pendientes que afirmar (libro ``COMPLETE``); si la
        lectura falla o se agota el ``limit``, el libro queda ``UNKNOWN`` y el motor veta
        aperturas — nunca "no hay pendientes porque no pude leer".
        """
        rows, read_measurement = await self._v2_read_unapplied()
        known = self._v2_known_fill_ids()
        pending = [row for row in rows if str(getattr(row, "execution_id", "")) not in known]
        contexts = [await self._v2_fill_context(row) for row in pending]
        sectors = self._v2_sectors_for(
            sorted({str(getattr(c, "instrument_id", "") or "") for c in contexts} - {""})
        )
        orders: list[OpenOrder] = [
            _open_order_from_fill(
                row,
                context,
                sector=sectors.get(str(getattr(context, "instrument_id", "") or "")),
            )
            for row, context in zip(pending, contexts, strict=True)
        ]
        self._v2_open_orders = tuple(orders)
        self._v2_open_orders_read_measurement = read_measurement
        self._v2_order_book_measurement = combine_measurements(
            read_measurement,
            summarize_open_orders(self._v2_open_orders, equity=self._v2_equity()).measurement,
        )

    async def _v2_read_unapplied(self) -> tuple[list[Any], MeasurementStatus]:
        """Lee las trazas no aplicadas de la cuenta (o declara por qué no se pudo)."""
        store = self._exec_store
        if store is None:
            # Sin espejo durable no hay settlement: no puede haber dinero en vuelo.
            return [], MEASUREMENT_COMPLETE
        lister = getattr(store, "list_unapplied", None)
        if not callable(lister):
            # Store que no soporta el listado: NO se puede afirmar el libro.
            return [], MEASUREMENT_UNKNOWN
        try:
            rows = await lister(
                self._account_id,
                statuses=UNAPPLIED_EXECUTION_EVENT_STATUSES,
                limit=_V2_OPEN_ORDERS_LIMIT,
            )
        except Exception:  # noqa: BLE001 — sin lectura, el libro es desconocido.
            logger.exception("auto_sim v2 open orders read failed")
            return [], MEASUREMENT_UNKNOWN
        found = list(rows or ())
        if len(found) >= _V2_OPEN_ORDERS_LIMIT:
            # Puede haber más de las que se leyeron: el libro NO es afirmable.
            return found, MEASUREMENT_UNKNOWN
        return found, MEASUREMENT_COMPLETE

    async def _v2_fill_context(self, row: Any) -> Any:
        """Contexto financiero durable del fill (``None`` si no se puede resolver)."""
        store = self._context_store
        execution_id = str(getattr(row, "execution_id", "") or "")
        if store is None or not execution_id:
            return None
        try:
            return await store.get(execution_id)
        except Exception:  # noqa: BLE001 — sin contexto, la orden queda sin cuantificar.
            logger.exception("auto_sim v2 fill context read failed exec=%s", execution_id)
            return None

    def _v2_known_fill_ids(self) -> frozenset[str]:
        """Ids de fill ya reconocidos por el libro del worker (no son pendientes)."""
        events = getattr(self, "_applied_execution_events", None) or []
        return frozenset(str(getattr(event, "execution_id", "") or "") for event in events)

    # ---- AUTO-1: reservas durables (autoridad del compromiso) -------------------
    #
    # Invariante que sostiene esta sección: **no existe aprobación sin reserva, y no
    # existe reserva sin liberación**. La reserva explícita (identidad + siete
    # dimensiones + ciclo de vida) es la AUTORIDAD de ``reserved_cash``/``pending_risk``
    # entre ticks; ``execution_events`` deja de ser el productor y pasa a ser la
    # reconciliación de arranque (qué se materializó y qué orden murió sin llenarse).

    @property
    def _v2_reservation_book_active(self) -> bool:
        """True cuando el libro durable de reservas es la autoridad del compromiso."""
        return self._reservation_store is not None

    def _v2_instant(self) -> str:
        """Instante del tick en ISO-UTC (mismo formato que el ``tick_id`` del plan)."""
        return self._time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _v2_cycle_for(self, symbol: str) -> str | None:
        """V2.47 — ciclo financiero vivo del símbolo (fuente única de la cadena).

        Precedencia: la POSICIÓN abierta (su ciclo nació en el fill y es el que deben
        heredar su salida y su PnL) y, si no hay posición, el plan del tick corriente
        (donde el ciclo acaba de acuñarse junto a la decisión). ``None`` = no conocido:
        nunca se inventa un ciclo.
        """
        position = self._v2_positions.get(symbol)
        cycle_id = getattr(position, "cycle_id", None) if position is not None else None
        if str(cycle_id or "").strip():
            return str(cycle_id)
        cycle_for = getattr(self._v2_plan, "cycle_for", None)
        if callable(cycle_for):
            planned = cycle_for(symbol)
            return str(planned) if str(planned or "").strip() else None
        return None

    async def _v2_read_live_reservations(
        self, *, limit: int = _V2_RESERVATIONS_LIMIT
    ) -> tuple[tuple[PortfolioReservation, ...], MeasurementStatus]:
        """Reservas VIVAS de la cuenta + su estado de medición (fail-closed).

        Sin store no hay libro que afirmar y se devuelve vacío ``COMPLETE`` (el camino
        hermético sigue con el libro de ``execution_events``). Un fallo de lectura, un
        tope agotado o una reserva viva que no declara sus dimensiones **NO** se leen como
        "no hay compromiso": bajan la medición y el motor veta aperturas.
        """
        store = self._reservation_store
        if store is None:
            return (), MEASUREMENT_COMPLETE
        try:
            rows = list(await store.list_live(self._account_id, limit=limit))
        except Exception:  # noqa: BLE001 — sin lectura no se afirma el libro.
            logger.exception("auto_sim v2 reservations read failed")
            return (), MEASUREMENT_UNKNOWN
        if len(rows) >= limit:
            # Agotar el tope no es "no hay más": es no haber visto el libro entero.
            return tuple(rows), MEASUREMENT_UNKNOWN
        valued = sum(1 for row in rows if row.is_quantified)
        return tuple(rows), measurement_from_counts(valued=valued, unvalued=len(rows) - valued)

    def _v2_open_order_from_reservation(
        self, reservation: PortfolioReservation
    ) -> OpenOrder | None:
        """Proyecta una reserva viva como orden pendiente del libro (AUTO-1b).

        Es el puente con el ``AutoPortfolioSnapshot``: la reserva entra en el mismo libro
        que consumían las trazas de ``execution_events``, de modo que capital, riesgo y
        exposición comprometidos se descuentan una sola vez y con la MISMA aritmética.

        Capital y riesgo se aportan **explícitos** desde la reserva (que es la autoridad);
        la derivación ``cantidad × precio`` del helper sería una segunda aritmética que
        podría discrepar del compromiso real. Una reserva sin cuantificar deja importes a
        ``None`` y el agregado baja de medición (el motor veta nuevas aperturas).
        """
        if not reservation.instrument_id or reservation.remaining_qty <= 0:
            return None
        return build_open_order(
            execution_id=f"reservation:{reservation.reservation_id}",
            order_id=reservation.reservation_id,
            instrument_id=reservation.instrument_id,
            side=reservation.side,
            quantity=reservation.remaining_qty,
            price=reservation.entry,
            requested_qty=reservation.quantity,
            sector=reservation.sector,
            reserved_cash=reservation.reserved_cash,
            risk_amount=reservation.reserved_risk,
            strategy_version_id=reservation.strategy_version_id,
        )

    def _v2_pending_open_orders(self) -> tuple[OpenOrder, ...]:
        """Libro pendiente efectivo: reservas vivas (autoridad) + trazas huérfanas.

        Con libro de reservas activo, una traza de ``execution_events`` de un instrumento
        que YA tiene reserva viva no se suma otra vez (sería contar el mismo capital dos
        veces): la reserva la cubre. Las trazas de instrumentos SIN reserva viva sí se
        conservan — son el caso de crash entre la captura del fill y el alta de la
        reserva, y su capital sigue comprometido.
        """
        if not self._v2_reservation_book_active:
            return self._v2_open_orders
        covered = {
            reservation.instrument_id
            for reservation in self._v2_reservations
            if reservation.instrument_id
        }
        orders = [
            order
            for order in (
                self._v2_open_order_from_reservation(reservation)
                for reservation in self._v2_reservations
            )
            if order is not None
        ]
        orders.extend(order for order in self._v2_open_orders if order.instrument_id not in covered)
        return tuple(orders)

    def _v2_pending_book_measurement(self) -> MeasurementStatus:
        """Medición del libro pendiente efectivo (reservas + trazas huérfanas).

        Incluye la medición de LECTURA del libro de trazas (fallo de lectura o tope
        agotado ⇒ ``UNKNOWN``) y la del agregado filtrado: si una reserva viva no declara
        capital/riesgo/sector, el resumen es un suelo y el motor no debe autorizar nada.
        """
        if not self._v2_reservation_book_active:
            return self._v2_order_book_measurement
        return combine_measurements(
            self._v2_reservations_measurement,
            self._v2_open_orders_read_measurement,
            summarize_open_orders(
                self._v2_pending_open_orders(), equity=self._v2_equity()
            ).measurement,
        )

    async def _v2_persist_tick_reservations(self, plan: Any) -> None:
        """Persiste las reservas del tick ANTES de emitir la orden (AUTO-1b).

        Fail-closed: la aprobación cuya reserva no llega a ser durable **no se emite**.
        Esa es la mitad durable del invariante ("no existe aprobación sin reserva"): un
        crash inmediatamente después de emitir la orden no puede perder el compromiso, y
        el arranque siguiente lo reconcilia desde aquí, no adivinando desde las trazas.

        El resultado se publica en dos conjuntos:

        * ``_v2_reservation_blocked`` — instrumentos del tick cuya reserva NO se pudo
          persistir; el bucle de ejecución los veta con ``reservation_unmeasurable``.
        * ``_v2_reservation_carryover`` — instrumentos con reserva viva de ticks
          ANTERIORES (aún sin fill): no se apila un segundo compromiso sobre el mismo
          instrumento (``reservation_already_live``). Se captura ANTES de dar de alta las
          del tick para no vetar la propia aprobación de este tick.
        """
        store = self._reservation_store
        previous = self._v2_reservations
        reservations = tuple(getattr(plan, "reservations", ()) or ())
        if store is None:
            self._v2_reservation_blocked = frozenset()
            self._v2_reservation_carryover = frozenset()
            return
        self._v2_reservation_carryover = frozenset(
            reservation.instrument_id
            for reservation in previous
            if reservation.is_live and reservation.instrument_id
        )
        if not reservations:
            self._v2_reservation_blocked = frozenset()
            self._v2_reservations = previous
            return
        blocked: set[str] = set()
        claimed: set[str] = set()
        persisted: list[PortfolioReservation] = []
        # AUTO Operational Monitor (``M2``): carrera de claim por reserva (ganada/perdida) para
        # el spine. Se emite DESPUÉS del commit (primero el dinero, después la traza).
        claim_audits: list[tuple[PortfolioReservation, bool]] = []
        for reservation in reservations:
            try:
                claimed_ok = await store.save_claim(reservation)
            except Exception:  # noqa: BLE001 — una reserva no durable no se emite.
                logger.exception(
                    "auto_sim v2 reservation persist failed id=%s",
                    reservation.reservation_id,
                )
                blocked.add(reservation.instrument_id)
                continue
            claim_audits.append((reservation, bool(claimed_ok)))
            if not claimed_ok:
                # AUTO-6: la identidad de la reserva es DETERMINISTA por (cuenta, señal)
                # (``RES-dec-<hash>``), así que la PK de ``portfolio_reservations`` arbitra
                # la carrera sin locks extra: ``save_claim`` devuelve ``False`` SOLO si ya
                # había un compromiso VIVO con esa identidad — la ganó otro worker/proceso
                # (o un tick anterior). Es un CLAIM atómico: el perdedor veta su emisión en
                # vez de apilar un segundo compromiso sobre el mismo capital. No es un
                # fallo de medición, es una carrera perdida — se declara con
                # ``reservation_already_live``. Una identidad ya LIBERADA no llega aquí:
                # se re-compromete (re-intento legítimo dentro de la barra).
                claimed.add(reservation.instrument_id)
                continue
            # OBS-14.b — ``save_claim`` ganado: esta sesión es la DUEÑA del compromiso y
            # es la única con autoridad para retirarlo al cerrar SU turno.
            self._v2_owned_reservations.add(reservation.reservation_id)
            persisted.append(reservation)
        try:
            await store.commit()
        except Exception:  # noqa: BLE001 — con autocommit ya es durable; se declara.
            logger.exception("auto_sim v2 reservation commit failed")
        # AUTO-10 — el ciclo que acaba de abrir deja su régimen en el journal DURABLE. Se
        # publica DESPUÉS del commit de la reserva: primero el compromiso de capital, después
        # la traza (si la traza falla, el dinero sigue comprometido y el hueco se declara).
        await self._v2_journal_cycle_regime(persisted)
        # AUTO Operational Monitor (``M2``): la carrera de claim queda en el spine (ganada por
        # esta sesión o perdida ante otro compromiso vivo). Sin sink no se escribe nada.
        await self._v2_journal_reservation_claims(claim_audits)
        self._v2_reservation_blocked = frozenset(blocked)
        # Las carreras perdidas se suman al carryover: el veteo de emisión es el mismo
        # ("ya hay una reserva viva para este instrumento") y usa el mismo motivo.
        self._v2_reservation_carryover = self._v2_reservation_carryover | frozenset(claimed)
        merged: dict[str, PortfolioReservation] = {
            row.reservation_id: row for row in previous if row.is_live
        }
        for row in persisted:
            merged[row.reservation_id] = row
        self._v2_reservations = tuple(
            sorted(merged.values(), key=lambda r: (r.created_at or "", r.reservation_id))
        )

    def _v2_audit_session(self) -> str:
        """Identidad estable de esta sesión de motor para la auditoría operativa (``M2``).

        Se acuña perezosamente y sólo tiene sentido con el sink inyectado. Es el dueño que se
        publica en el claim y el ``caller`` del barrido: un ``NO MEDIDO`` en la UI es
        preferible a un dueño inventado, por eso sin sink no se acuña nada.
        """
        session = self._audit_session_id
        if session is None:
            from uuid import uuid4

            session = f"auto-{uuid4().hex[:12]}"
            self._audit_session_id = session
        return session

    async def _v2_audit_emit(self, entry: Any, *, label: str) -> None:
        """Publica UNA entrada de auditoría; best-effort declarado (``M2``).

        Sin sink es un no-op silencioso: no hay nada que fingir. Un fallo del sink NO puede
        tumbar el turno (el dinero ya está comprometido aguas arriba), pero se registra —
        un silencio aquí volvería a convertir el hueco en mentira por omisión.
        """
        sink = self._operational_audit_sink
        if sink is None or entry is None:
            return
        try:
            await sink(entry)
        except Exception:  # noqa: BLE001 — publicar no puede tumbar el turno.
            logger.exception("auto_sim operational audit failed (%s)", label)

    async def _v2_journal_cycle_regime(self, reservations: Sequence[PortfolioReservation]) -> None:
        """AUTO-10 — publica el régimen del ciclo recién abierto en el journal durable.

        El ciclo abre con su reserva de ENTRADA (``_v2_persist_tick_reservations``), así que
        el régimen que se publica es el del turno que **decidió** (``_v2_regime()``), no el de
        un instante posterior. Un ciclo sin régimen se publica igual: con
        ``marketRegime = None`` y ``regimeMeasurement = UNKNOWN`` **declarados**, para que el
        lector pueda distinguir "no medido" de "medido".

        El régimen y el sello del turno se leen UNA vez, fuera del bucle: todos los ciclos de un
        mismo turno publican así el régimen que de verdad **decidió** (no uno releído por ciclo,
        que podría diferir si la fuente no fuera pura) y el mismo ``asOf``.

        Fail-open **declarado**: sin sink no se escribe (no hay nada que fingir) y un fallo del
        sink no tumba el turno —el compromiso de capital ya es durable—, pero se registra: un
        silencio aquí volvería a convertir el hueco en mentira por omisión. Un ciclo que ya se
        publicó en este turno no se repite (una apertura, una traza).
        """
        sink = self._cycle_regime_sink
        if sink is None:
            return
        regime = self._v2_regime()
        as_of = self._v2_instant()
        published: set[str] = set()
        for reservation in reservations:
            cycle_id = str(getattr(reservation, "cycle_id", None) or "").strip()
            if not cycle_id or cycle_id in published:
                continue
            entry = build_auto_cycle_regime_entry(
                cycle_id=cycle_id,
                market_regime=regime,
                actor=self._engine_id,
                as_of=as_of,
                account_id=self._account_id,
                instrument_id=getattr(reservation, "instrument_id", None),
                strategy_version=getattr(reservation, "strategy_version_id", None),
            )
            if entry is None:
                continue
            published.add(cycle_id)
            try:
                await sink(entry)
            except Exception:  # noqa: BLE001 — publicar no puede tumbar el turno.
                logger.exception("auto_sim v2 cycle regime journal failed cycle=%s", cycle_id)

    async def _v2_journal_reservation_claims(
        self, claims: Sequence[tuple[PortfolioReservation, bool]]
    ) -> None:
        """(``M2``) publica en el spine la carrera de claim de cada reserva del tick.

        ``True`` = claim ganado por esta sesión (dueña del compromiso); ``False`` = perdido
        (ya había un compromiso vivo con la identidad determinista AUTO-6). Ambos hechos son
        materia prima de los paneles de ownership/concurrencia; sin sink no se escribe nada y
        el monitor los declara ``NO MEDIDO``.
        """
        if self._operational_audit_sink is None:
            return
        session = self._v2_audit_session()
        as_of = self._v2_instant()
        for reservation, claimed in claims:
            entry = build_reservation_claim_entry(
                reservation_id=getattr(reservation, "reservation_id", None),
                cycle_id=getattr(reservation, "cycle_id", None),
                claimed=claimed,
                actor=self._engine_id,
                session_id=session,
                as_of=as_of,
                account_id=self._account_id,
                instrument_id=getattr(reservation, "instrument_id", None),
            )
            await self._v2_audit_emit(entry, label="reservation_claim")

    async def _v2_journal_entry_decisions(self, entries: Sequence[Any]) -> None:
        """(``M2``) persiste en el spine el journal de decisión AUTO (hoy en RAM).

        Son las entradas ``auto_entry_decision`` que produce ``auto_v2_entry`` (con ``rank``/
        ``opportunityScore``/``cycleId``). Al hacerlas durables, ``SIGNAL``/``TOP_N``/``RISK``
        dejan de ser ``unknown`` y se enlazan por ``decision_id``/``cycleId`` sin migración.
        """
        if self._operational_audit_sink is None:
            return
        # La identidad (``decision_id``/``payload.cycleId``) la trae el productor: se persiste
        # tal cual, sin reescribir ningún hecho. SÓLO se sella ``account_id`` cuando el
        # productor NO lo trae: es lo que permite al monitor leer el último ``auto_entry_decision``
        # por ``account_id + event_type`` (índice) sin depender de las reservas visibles. No es
        # una decisión de inversión: es trazado. La columna ``session_id`` apunta por FK a
        # ``decision_sessions`` y no se invade: la sesión de motor vive en los claims.
        #
        # A4 (monitor): se sella ADEMÁS ``payload.engineId`` cuando falta, para que la lectura
        # global acote por motor y no mezcle dos motores de la misma cuenta. Aditivo e inerte
        # (con el flag de auditoría OFF este tramo no corre).
        for entry in entries:
            if entry is None:
                continue
            await self._v2_audit_emit(self._v2_seal_audit_identity(entry), label="entry_decision")

    def _v2_seal_audit_identity(self, entry: Any) -> Any:
        """(``M2``) sella ``account_id`` (si falta), ``payload.engineId`` (si falta) y la
        identidad determinista ``dedupe_key`` (v2.88.27).

        Es **trazado**, no decisión: la identidad del hecho la trae el productor y sólo se
        completa lo que falta, sin reescribir nada. ``account_id`` es lo que permite leer por el
        índice ``(account_id, ...)``; ``payload.engineId`` acota la lectura por motor (A4) para
        no mezclar dos motores de la misma cuenta y forma parte de la clave de deduplicación.
        ``dedupe_key`` la deriva ``durable_fact_dedupe_key`` (pura) SÓLO para los hechos M2 que
        declaran identidad natural: un reintento del sumidero o la recuperación de un hecho que
        un crash dejó sin publicar pasa a ser un no-op en vez de un duplicado. Con el flag OFF
        este tramo no corre.
        """
        if entry is None:
            return None
        if not getattr(entry, "account_id", None):
            entry = replace(entry, account_id=self._account_id)
        payload = dict(entry.payload or {})
        if not str(payload.get("engineId") or "").strip() and self._engine_id:
            payload["engineId"] = self._engine_id
            entry = replace(entry, payload=payload)
        if not getattr(entry, "dedupe_key", None):
            key = durable_fact_dedupe_key(
                event_type=getattr(entry, "event_type", None),
                account_id=getattr(entry, "account_id", None),
                engine_id=self._engine_id,
                cycle_id=payload.get("cycleId"),
                order_id=payload.get("orderId"),
                kind=payload.get("kind"),
                revision_id=payload.get("revisionId"),
            )
            if key is not None:
                entry = replace(entry, dedupe_key=key)
        return entry

    async def _v2_journal_entry_order(
        self,
        *,
        order_id: str | None,
        instrument_id: str,
        requested_qty: Any,
        applied_qty: Any,
        partial: bool,
        cycle_id: str | None,
    ) -> None:
        """(``M2``) sella la ORDEN DE ENTRADA emitida y materializada (v2.88.25).

        Cierra ``entry_order_not_durable`` del paso ``ORDER``: hasta hoy sólo las órdenes de
        SALIDA eran durables. Best-effort y aditivo: sin sink es un no-op (Δ = 0). La cantidad
        PEDIDA y la MATERIALIZADA viajan separadas (un fill parcial no se disfraza de completo).
        """
        if self._operational_audit_sink is None:
            return
        entry = build_entry_order_entry(
            order_id=order_id,
            instrument_id=instrument_id,
            side="buy",
            requested_qty=requested_qty,
            applied_qty=applied_qty,
            partial=partial,
            price_source=self._v2_price_source_kind(),
            cycle_id=cycle_id,
            actor=self._engine_id,
            as_of=self._v2_instant(),
            account_id=self._account_id,
        )
        await self._v2_audit_emit(
            self._v2_seal_audit_identity(entry), label="entry_order"
        )

    async def _v2_journal_cycle_settlement(
        self,
        *,
        instrument_id: str,
        closed_qty: Any,
        cycle_id: str | None,
        exit_reason: str | None,
    ) -> None:
        """(``M2``) sella el HECHO durable de liquidación de un ciclo cerrado (v2.88.25).

        Cierra ``settlement_not_durable`` del paso ``SETTLEMENT``. El PnL se lee del MISMO
        material durable que ``CYCLE_CLOSED`` (``cycles_from_fills`` sobre los fills del ciclo),
        nunca con un segundo FIFO que pueda divergir. Con la evidencia incompleta el PnL viaja
        ``None`` + ``PARTIAL``: jamás una cifra sobre un subconjunto. Sin sink es un no-op.
        """
        if self._operational_audit_sink is None:
            return
        pnl, pnl_measurement = await self._v2_cycle_pnl(cycle_id)
        entry = build_cycle_settlement_entry(
            settlement_id=(
                f"settle-{cycle_id}" if cycle_id else None
            ),
            instrument_id=instrument_id,
            side="sell",
            closed_qty=closed_qty,
            pnl=pnl,
            pnl_measurement=pnl_measurement,
            settled_at=self._v2_instant(),
            exit_reason=exit_reason,
            price_source=self._v2_price_source_kind(),
            cycle_id=cycle_id,
            actor=self._engine_id,
            as_of=self._v2_instant(),
            account_id=self._account_id,
        )
        await self._v2_audit_emit(
            self._v2_seal_audit_identity(entry), label="cycle_settlement"
        )

    async def _v2_journal_protection(
        self,
        *,
        kind: str,
        instrument_id: str,
        cycle_id: str | None,
        position_id: str | None = None,
        lifecycle_from: str | None = None,
        lifecycle_to: str | None = None,
        stop_before: Any = None,
        stop_after: Any = None,
        target: Any = None,
        trailing_status: str | None = None,
        revision_id: str | None = None,
        source: str | None = None,
    ) -> None:
        """(``M2``) sella el HECHO durable de una transición de PROTECCIÓN (v2.88.26).

        Cierra ``protection_not_durable`` del paso ``PROTECTION``: hasta hoy la protección vivía
        sólo en el ``position_state`` proyectado y no había traza append-only de *cuándo* cambió
        el stop, se alcanzó T1/T2, se armó el trailing o se pidió la salida. El hecho es la
        **traza** de la transición que ya produjo ``PositionState`` (la autoridad): NO re-deriva
        nada. Sin ``cycle_id``/``instrument_id`` el builder devuelve ``None`` y no se finge el
        hecho. Best-effort y aditivo: sin sink es un no-op (Δ = 0).
        """
        if self._operational_audit_sink is None:
            return
        entry = build_protection_entry(
            kind=kind,
            instrument_id=instrument_id,
            cycle_id=cycle_id,
            position_id=position_id,
            lifecycle_from=lifecycle_from,
            lifecycle_to=lifecycle_to,
            stop_before=stop_before,
            stop_after=stop_after,
            target=target,
            trailing_status=trailing_status,
            revision_id=revision_id,
            source=source,
            actor=self._engine_id,
            as_of=self._v2_instant(),
            account_id=self._account_id,
        )
        await self._v2_audit_emit(
            self._v2_seal_audit_identity(entry), label="protection"
        )

    async def _v2_read_cycle_fills(
        self, cycle_id: str
    ) -> tuple[list[Any], MeasurementStatus]:
        """Fills durables de UN ciclo, con la completitud de la ventana DECLARADA.

        Fail-closed: sin store o con la ventana LLENA (``len == limit``, pudo perderse una pata)
        la lectura NO es afirmable (``UNKNOWN``/``PARTIAL``). Es la ÚNICA puerta de lectura de
        fills del ciclo, compartida por el PnL del settlement y la recuperación de arranque, para
        que el FIFO sea uno solo.
        """
        if not cycle_id or self._context_store is None:
            return [], MEASUREMENT_UNKNOWN
        try:
            fills = await self._context_store.list_by_cycle_ids(
                self._account_id, [cycle_id], limit=_SETTLEMENT_FILL_WINDOW
            )
        except Exception:  # noqa: BLE001 — un fallo de lectura ES "no medido".
            logger.exception("auto_sim settlement pnl read failed cycle=%s", cycle_id)
            return [], MEASUREMENT_UNKNOWN
        if len(fills) >= _SETTLEMENT_FILL_WINDOW:
            return list(fills), MEASUREMENT_PARTIAL
        return list(fills), MEASUREMENT_COMPLETE

    async def _v2_cycle_pnl(
        self, cycle_id: str | None
    ) -> tuple[float | None, MeasurementStatus]:
        """PnL del ciclo desde el material durable (``cycles_from_fills``), o un hueco declarado.

        Sin ``cycle_id``/store se declara ``UNKNOWN``. Con la ventana de fills truncada
        (``len == limit``, pudo perderse una pata) el PnL se declara ``PARTIAL`` y ``None``: la
        misma disciplina fail-closed que ``CYCLE_CLOSED``, aplicada al settlement.
        """
        if not cycle_id:
            return None, MEASUREMENT_UNKNOWN
        fills, measurement = await self._v2_read_cycle_fills(cycle_id)
        if measurement == MEASUREMENT_UNKNOWN:
            return None, MEASUREMENT_UNKNOWN
        if measurement == MEASUREMENT_PARTIAL:
            return None, MEASUREMENT_PARTIAL
        for row in cycles_from_fills(fills):
            if str(row.get("cycleId") or "").strip() == cycle_id:
                pnl = row.get("pnl")
                # ``cycles_from_fills`` publica el PnL como ``Decimal`` (es dinero): aceptar
                # sólo ``int``/``float`` lo declaraba no medido, un hueco falso.
                if isinstance(pnl, (int, float, Decimal)) and not isinstance(pnl, bool):
                    return float(pnl), MEASUREMENT_COMPLETE
                return None, MEASUREMENT_UNKNOWN
        # El ciclo todavía no está cerrado según el FIFO de fills: no se afirma un PnL.
        return None, MEASUREMENT_PARTIAL

    async def _v2_recover_durable_facts(self) -> None:
        """v2.88.27 — reemite el ``SETTLEMENT`` que un crash dejó sin publicar (una vez/proceso).

        La ventana que cierra: ``persist_position(CLOSED)`` es durable, pero su
        ``auto_cycle_settlement`` va DESPUÉS por el sumidero best-effort. Un crash entre ambos
        dejaba el ciclo cerrado con el ``SETTLEMENT`` sin sellar y el monitor volvía a
        ``settlement_not_durable``. Aquí se cruzan los ciclos cerrados que los fills durables
        DEMUESTRAN con los ``cycleId`` que YA tienen settlement durable, y se sella SÓLO el hueco.
        El PnL sale del mismo ``cycles_from_fills`` (un solo FIFO) y la identidad determinista
        (``dedupe_key``) hace el reenvío idempotente: si ya existía, es un no-op.

        Fail-open DECLARADO: sin lector/sink/store, sin ciclos, con la ventana truncada o con la
        lectura rota NO se afirma nada (se registra); jamás se inventa un settlement.
        """
        if self._v2_durable_facts_recovered:
            return
        self._v2_durable_facts_recovered = True
        reader = self._durable_fact_cycle_reader
        store = self._context_store
        if reader is None or store is None or self._operational_audit_sink is None:
            return
        lister = getattr(store, "list_recent_cycle_ids", None)
        if not callable(lister):
            return
        try:
            recent = await lister(self._account_id, limit=_DURABLE_FACTS_RECOVERY_CYCLES)
        except Exception:  # noqa: BLE001 — sin ventana no se afirma nada.
            logger.exception("auto_sim durable facts recovery: cycle window read failed")
            return
        if not recent:
            return
        try:
            settled = await reader(AUTO_CYCLE_SETTLEMENT_EVENT)
        except Exception:  # noqa: BLE001 — sin saber qué existe, no se reemite a ciegas.
            logger.exception("auto_sim durable facts recovery: settled read failed")
            return
        recovered = 0
        for cycle_id in recent:
            cycle = str(cycle_id or "").strip()
            if not cycle or cycle in settled:
                continue
            try:
                fills, measurement = await self._v2_read_cycle_fills(cycle)
                if measurement != MEASUREMENT_COMPLETE or not fills:
                    continue
                rows = cycles_from_fills(fills)
                row = next(
                    (r for r in rows if str(r.get("cycleId") or "").strip() == cycle), None
                )
                if row is None:
                    # El FIFO no da el ciclo por cerrado (o no lo puede afirmar): no hay settlement.
                    continue
                snapshot = settlement_snapshot_from_fills(fills)
                if snapshot is None:
                    continue
                pnl = row.get("pnl")
                pnl_value = (
                    float(pnl)
                    if isinstance(pnl, (int, float, Decimal)) and not isinstance(pnl, bool)
                    else None
                )
                entry = build_cycle_settlement_entry(
                    settlement_id=f"settle-{cycle}",
                    instrument_id=snapshot["instrument_id"],
                    side="sell",
                    closed_qty=snapshot["closed_qty"],
                    pnl=pnl_value,
                    settled_at=row.get("closedAt"),
                    exit_reason=None,
                    price_source=snapshot["price_source"],
                    cycle_id=cycle,
                    actor=self._engine_id,
                    as_of=self._v2_instant(),
                    account_id=self._account_id,
                )
                await self._v2_audit_emit(
                    self._v2_seal_audit_identity(entry), label="cycle_settlement_recovery"
                )
                recovered += 1
            except Exception:  # noqa: BLE001 — la recuperación NUNCA tumba el turno.
                logger.exception(
                    "auto_sim durable facts recovery failed cycle=%s (declared, ignored)", cycle
                )
        if recovered:
            logger.info(
                "auto_sim durable facts recovery: re-emitted %d settlement(s)", recovered
            )

    async def _v2_save_exit_order(self, order: ExitOrder) -> bool:
        """Persiste un INTENT de salida; ``False`` si el store falta o no fue durable."""
        store = self._exit_order_store
        if store is None:
            return False
        try:
            await store.save(order)
            await store.commit()
        except Exception:  # noqa: BLE001 — se declara; el llamante decide (política B).
            logger.exception("auto_sim v2 exit order persist failed id=%s", order.exit_order_id)
            return False
        return True

    async def _v2_apply_exit_fill(self, exit_order_id: str | None, qty: Any, *, at: str) -> None:
        """Aplica un fill materializado al INTENT de salida (V2.43.3 · separación I/O/F).

        Un fill no positivo o un intent desconocido no mueven nada (fail-closed: no se
        inventa materialización). ``filled_qty``/``remaining_qty`` del intent quedan así en
        fase con el fill real, no con la cantidad pedida.
        """
        key = str(exit_order_id or "").strip()
        if not key:
            return
        order = self._v2_exit_orders.get(key)
        if order is None:
            store = self._exit_order_store
            if store is None:
                return
            try:
                order = await store.get(key)
            except Exception:  # noqa: BLE001 — no poder leer no autoriza a inventar.
                logger.exception("auto_sim v2 exit order get failed id=%s", key)
                return
        if order is None:
            return
        updated = order.apply_fill(qty, at=at)
        if updated is order:
            return
        await self._v2_save_exit_order(updated)
        if updated.is_open:
            self._v2_exit_orders[key] = updated
        else:
            self._v2_exit_orders.pop(key, None)

    async def _v2_reserve_exit(
        self,
        *,
        symbol: str,
        qty: Any,
        price: Any,
        sector: str | None,
        at: str,
    ) -> str | None:
        """Reserva VIVA de una orden de SALIDA con identidad DURABLE (V2.44 · F9 · V2.43.3).

        Un exit del gobernador (``RISK_EXIT``/``REGIME_EXIT``/``KILL_SWITCH``), un stop o un
        objetivo puede llenarse PARCIALMENTE. Sin reserva de venta, al reiniciar nadie sabe
        que había una salida en vuelo: la gestión vuelve a dimensionar contra la posición y
        emite otra vez la MISMA orden. La reserva de venta le da identidad y ciclo de vida a
        esa cola.

        V2.43.3 (P0-2): la identidad ya NO es ``exit:{engine}:{symbol}:{seq}`` con un
        contador de proceso que vuelve a 0 en cada arranque (lo que permitía REUTILIZAR una
        identidad histórica). Se mintea ``exit_order_id`` (ULID) y se persiste el INTENT
        ANTES de reservar y de emitir; la reserva lo referencia y su ``reservation_id`` lo
        incorpora. El valor devuelto es el ``exit_order_id`` (la identidad del INTENT).

        V2.43.3 (P1-4, política B): la salida protectora NUNCA se bloquea por un fallo de
        reserva (reducir riesgo no empeora la situación). Pero tampoco se emite jamás sin
        identidad durable: si la reserva no es durable se persiste un INTENT de emergencia
        (``EMERGENCY``) y, si eso tampoco es durable, el sistema se para (``SYSTEM_ERROR``)
        en vez de emitir una salida sin rastro.
        """
        store = self._reservation_store
        amount = _dec_or_none(qty)
        if store is None or amount is None or amount <= 0:
            return None
        entry = _dec_or_none(price)
        # V2.47 — el intent de salida HEREDA el ciclo de la posición que cierra: sin él,
        # el PnL del ciclo no se podría reconstruir desde la salida hacia atrás.
        cycle_id = self._v2_cycle_for(symbol)
        # P0-2 — la identidad se mintea UNA vez y se persiste antes de cualquier efecto.
        exit_order_id = new_exit_order_id()
        order = build_exit_order(
            exit_order_id=exit_order_id,
            instrument_id=symbol,
            side=SIDE_SELL,
            requested_qty=float(amount),
            account_id=self._account_id or "",
            engine_id=self._engine_id,
            created_at=at,
            updated_at=at,
            cycle_id=cycle_id,
        )
        if order is None:  # defensivo: la salida no tiene datos suficientes para un INTENT.
            logger.error("auto_sim v2 exit order not buildable symbol=%s qty=%s", symbol, qty)
            return None
        await self._v2_save_exit_order(order)
        reservation = build_reservation(
            reservation_id=f"exit:{exit_order_id}",
            account_id=self._account_id or "",
            tick_id=at,
            instrument_id=symbol,
            side=SIDE_SELL,
            quantity=float(amount),
            entry=float(entry) if entry is not None else None,
            sector=sector or UNKNOWN_SECTOR,
            reserved_cash=0.0,
            reserved_risk=0.0,
            created_at=at,
            exit_order_id=exit_order_id,
            cycle_id=cycle_id,
        )
        try:
            await store.save(reservation)
            await store.commit()
        except Exception:  # noqa: BLE001 — la salida no se bloquea por la reserva.
            logger.exception(
                "auto_sim v2 exit reservation persist failed id=%s intent=%s",
                reservation.reservation_id,
                exit_order_id,
            )
            # Política B: identidad durable de emergencia o parada. Nunca emitir sin rastro.
            emergency = order.as_emergency("reservation_persist_failed", at=at)
            if not await self._v2_save_exit_order(emergency):
                logger.error(
                    "auto_sim v2 exit intent emergency persist failed intent=%s; HALT",
                    exit_order_id,
                )
                await self.engage_kill_switch_durable("SYSTEM_ERROR", at=at)
                return None
            self._v2_exit_orders[exit_order_id] = emergency
            return exit_order_id
        reserved = order.with_reserved(reservation.reservation_id, at=at)
        await self._v2_save_exit_order(reserved)
        self._v2_exit_orders[exit_order_id] = reserved
        # OBS-14.b — la reserva de salida también es de ESTA sesión: si su orden no llega
        # a materializarse dentro del turno, el cierre de turno es quien debe retirarla.
        self._v2_owned_reservations.add(reservation.reservation_id)
        merged: dict[str, PortfolioReservation] = {
            row.reservation_id: row for row in self._v2_reservations if row.is_live
        }
        merged[reservation.reservation_id] = reservation
        self._v2_reservations = tuple(
            sorted(merged.values(), key=lambda r: (r.created_at or "", r.reservation_id))
        )
        return exit_order_id

    async def _v2_release_reservations_for_fill(
        self, *, symbol: str, filled_qty: Any, at: str, side: str = SIDE_BUY
    ) -> None:
        """Libera por FILL la reserva viva más reciente del instrumento y LADO (AUTO-1b).

        Es la pata del invariante que corre en el camino caliente: lo MATERIALIZADO deja
        de ser reserva y pasa a ser posición; con un fill parcial la liberación es parcial
        (``ReservationLedger.release`` escala las dimensiones) y la cola sigue siendo
        capital comprometido en ``RETRY``.

        V2.44 — el LADO filtra los candidatos: un fill de VENTA libera la reserva de la
        salida, no la de una compra viva (ni al revés). Antes solo se consumían compras, así
        que la cola de un ``RISK_EXIT`` parcial quedaba viva para siempre.

        Si la liberación no se puede persistir, la reserva se **conserva**: jamás se libera
        en memoria lo que no es durable (el arranque la reconciliará). Se elige la reserva
        más reciente del instrumento+lado (la del tick que acaba de llenar); una anterior, si
        existiera, la reconcilia el arranque con la misma regla de consumo progresivo.
        """
        store = self._reservation_store
        qty = _dec_or_none(filled_qty)
        if store is None or qty is None or qty <= 0:
            return
        wanted_side = str(side or "").strip().lower()
        candidates = [
            row
            for row in self._v2_reservations
            if row.is_live
            and row.instrument_id == symbol
            and (not wanted_side or row.side == wanted_side)
        ]
        if not candidates:
            return
        target = max(candidates, key=lambda r: (r.created_at or "", r.reservation_id))
        try:
            released = await store.release(
                target.reservation_id,
                status=RESERVATION_RELEASED_BY_FILL,
                reason=RELEASE_REASON_FILL,
                released_qty=float(qty),
                at=at,
            )
        except Exception:  # noqa: BLE001 — no se libera lo que no es durable.
            logger.exception("auto_sim v2 reservation release failed id=%s", target.reservation_id)
            return
        if released is None:
            return
        # V2.43.3: el INTENT de salida sigue al fill (identidad duradera). Se localiza por
        # la columna de la reserva o, para filas legadas, por el prefijo del
        # ``reservation_id`` (``exit:{exit_order_id}``).
        exit_order_id = getattr(target, "exit_order_id", None)
        if not exit_order_id and target.reservation_id.startswith("exit:"):
            exit_order_id = target.reservation_id.split(":", 1)[1]
        await self._v2_apply_exit_fill(exit_order_id, qty, at=at)
        remaining = [
            row
            for row in self._v2_reservations
            if row.reservation_id != released.reservation_id and row.is_live
        ]
        if released.is_live:
            remaining.append(released)
        self._v2_reservations = tuple(
            sorted(remaining, key=lambda r: (r.created_at or "", r.reservation_id))
        )

    async def _v2_in_flight_instruments(self, rows: Sequence[Any]) -> frozenset[str]:
        """Instrumentos con una traza NO materializada (capital en vuelo) del libro."""
        instruments: set[str] = set()
        for row in rows:
            context = await self._v2_fill_context(row)
            instrument = str(getattr(context, "instrument_id", "") or "").strip()
            if instrument:
                instruments.add(instrument)
        return frozenset(instruments)

    async def _v2_reconcile_reservations(
        self,
        *,
        startup: bool,
        attribute_fills: bool = True,
        only_ids: frozenset[str] | None = None,
    ) -> None:
        """Reconcilia el libro durable de reservas con lo MATERIALIZADO (AUTO-1b).

        Autoridad invertida respecto a V2.40.4: ``reserved_cash``/``pending_risk`` los
        dicta la reserva explícita (identidad + dimensiones), no una reconstrucción desde
        ``execution_events``. Esas trazas pasan a ser la **reconciliación de arranque**:
        qué se materializó de verdad y qué orden murió sin llenarse.

        Tres reglas, todas fail-closed:

        1. **Fill** — un APPLIED de compra del instrumento, posterior al alta de la
           reserva, libera esa cantidad (parcial: el resto sigue comprometido). El consumo
           es progresivo en orden de alta, así que dos reservas del mismo instrumento no
           cuentan el mismo fill dos veces.
        2. **Cancelación / reinicio** — solo si las DOS lecturas son MEDIBLES (``COMPLETE``)
           y la orden de esa reserva no está EN VUELO: la reserva no tiene nada que la vaya
           a consumir. Con una lectura incompleta la reserva se CONSERVA (liberar por un
           hueco de lectura sería fail-OPEN: devolvería al mercado un capital que quizá
           está comprometido).

           OBS-18 — la decisión se toma con la EVIDENCIA DE LA RESERVA (su cantidad
           materializada, ``released_qty``) y con la ausencia de traza en vuelo del
           instrumento, NUNCA con el agregado de fills del instrumento+lado: una reserva
           que no materializó nada quedaba viva para siempre en cuanto OTRA reserva del
           mismo instrumento+lado llenaba (``filled != 0``), y la COLA de un fill parcial
           no la retiraba nadie (la regla 1 solo libera lo materializado). Ambas cosas
           comprometían capital de forma indefinida hasta agotar el presupuesto.

           OBS-20 — esa evidencia se COMPLETA con la materialización EXACTA del CICLO:
           ``cycle_id`` ata un fill aplicado a la reserva que lo originó (ambos lo declaran,
           V2.47) y es el único vínculo sin heurísticas. Hace falta porque la liberación del
           camino caliente la ejecuta la sesión que LIQUIDA el fill y, si esa sesión no tiene
           la reserva en su libro, no llega a ocurrir — la fila se queda en ``0`` con el fill
           ya aplicado y el cierre declaraba ``cancel`` sobre una reserva que SÍ materializó
           (proveniencia falsa, con el ledger en contradicción). Instrumento+lado NO sirve
           como sustituto: dos órdenes del mismo instrumento y lado son ciclos distintos.
        3. **Lectura ilegible** — con reservas vivas que no se pudieron reconciliar, el
           libro queda ``UNKNOWN`` y el motor veta aperturas. "No pude leerlo" nunca se
           lee como "no había nada comprometido".

        Una reserva sin ``created_at`` legible no se puede ventanear y se conserva
        (sigue consumiendo presupuesto: el lado conservador del invariante).

        ``attribute_fills`` — la regla 1 SOLO es correcta cuando la llamada es la primera
        que ve esos fills (el arranque de un proceso, que parte de memoria vacía). La
        atribución es **no idempotente**: ``consumed`` se reinicia en cada llamada, así que
        re-atribuye el histórico COMPLETO de fills ≥ ``created_at`` de la reserva. En el
        CIERRE DE TURNO eso re-liberaría fills ya liberados por el camino caliente
        (``_v2_release_reservations_for_fill``) y drenaría el ``remaining_qty`` de una orden
        parcialmente llenada — la cola VIVA del fill parcial, capital realmente comprometido
        (fail-OPEN). El cierre de turno invoca con ``attribute_fills=False``: libera solo lo
        que NUNCA se materializó (regla 2), que es exactamente el huérfano del tick.

        ``only_ids`` — ALCANCE POR PROPIEDAD. ``None`` = la llamada NO tiene reservas a su
        cargo (es el caso del ARRANQUE: el proceso nace sin memoria y nada es suyo). Un
        conjunto explícito = esas reservas son de ESTA sesión, y es lo que usa el CIERRE DE
        TURNO con las SUYAS (``_v2_owned_reservations``). Sin ese acotado, dos sesiones
        concurrentes se pisan: la que cierra su turno ve la reserva viva de la otra —su orden
        todavía no se ha emitido ni liquidado— con las DOS lecturas medibles y SIN fill, y la
        regla 2 la declararía "muerta sin llenar", liberando un capital que la otra sesión SÍ
        materializará en su turno (fail-OPEN). La evidencia durable no puede distinguir "orden
        muerta" de "orden que otra sesión aún no ha emitido".

        Ventana de gracia por EDAD (``OBS-14.b``) — el segundo discriminador, y el que cierra
        esa indistinguibilidad sin identidad de sesión: una candidata solo se retira si es
        **de esta sesión** (``only_ids``) **o** si ya superó la ventana
        (``self._v2_reservation_grace``, ``V2_RESERVATION_GRACE_TURNS`` turnos de la cadencia
        real del loop). En el motor AUTO (solo ``paper``/``simulated``, sin bridge LIVE) la
        orden liquida DENTRO del tick, así que una reserva que superó un turno completo sin
        fill y sin traza en vuelo está muerta **por construcción**: su dueño —sea quien
        sea— ya cerró el turno. Una AJENA y JOVEN se CONSERVA (fail-closed: puede ser una
        orden que la otra sesión todavía no ha emitido). Consecuencia declarada: la huérfana
        de un crash que aún no envejeció no se retira en el barrido de arranque, sino en el
        primer cierre de turno posterior a la ventana (a lo sumo un turno más tarde), en vez
        de esperar a otro reinicio. Sin fecha legible, o con una fecha FUTURA respecto al
        reloj de esta sesión (relojes no comparables), no se afirma edad y se conserva.
        """
        store = self._reservation_store
        if store is None:
            self._v2_reservations = ()
            self._v2_reservations_measurement = MEASUREMENT_COMPLETE
            return
        live, book_measurement = await self._v2_read_live_reservations()
        if not live:
            self._v2_reservations = ()
            self._v2_reservations_measurement = book_measurement
            # OBS-14.b — sin reservas vivas no hay propiedad viva que conservar.
            self._v2_owned_reservations.clear()
            return
        facts_read = await read_applied_fill_facts(
            self._exec_store, self._context_store, self._account_id
        )
        rows, in_flight_read = await self._v2_read_unapplied()
        in_flight = (
            await self._v2_in_flight_instruments(rows)
            if in_flight_read == MEASUREMENT_COMPLETE
            else None
        )
        measurable = facts_read.measurement == MEASUREMENT_COMPLETE and in_flight is not None
        applied: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
        for fact in facts_read.facts:
            instant = _instant(fact.applied_at)
            if instant is None:
                continue
            # V2.44: el fill se casa con la reserva por LADO, no solo por instrumento. Un
            # ``RISK_EXIT`` (reserva sell) se libera con los fills de VENTA; antes solo se
            # consumían los ``is_buy``, así que la cola de una salida parcial se declaraba
            # "muerta sin llenar" y podía re-emitirse al reiniciar.
            applied.setdefault((fact.instrument_id, fact.side), []).append(
                (instant, float(fact.quantity))
            )
        # OBS-20 — materialización EXACTA por CICLO. ``cycle_id`` es la identidad que ata un
        # fill aplicado a la reserva que lo originó (la reserva lo declara y el fill lo hereda
        # del contexto financiero, V2.47): la única prueba SIN heurísticas. Hace falta porque la
        # liberación del camino caliente la ejecuta la sesión que LIQUIDA el fill y, si esa
        # sesión no tiene la reserva en su libro, no llega a ocurrir —la fila se queda en ``0``
        # con el fill YA aplicado— y el cierre declaraba ``cancel`` (proveniencia falsa) sobre
        # una reserva que SÍ materializó, con el ledger en contradicción. Se acota por LADO
        # porque un ciclo puede tener las DOS patas (entrada BUY y salida SELL); instrumento+lado
        # NO sirve de identidad: dos órdenes del mismo instrumento y lado son ciclos distintos,
        # que es justamente el defecto que OBS-18 corrigió y no se reintroduce ni para el motivo.
        cycle_fills: dict[tuple[str, str], float] = {}
        for fact in facts_read.facts:
            cycle = str(getattr(fact, "cycle_id", None) or "").strip()
            if not cycle:
                continue
            key = (cycle, fact.side)
            cycle_fills[key] = cycle_fills.get(key, 0.0) + float(fact.quantity)
        consumed: dict[tuple[str, str], float] = {}
        resolved: list[PortfolioReservation] = []
        outcomes: dict[str, tuple[float, PortfolioReservation | None]] = {}
        # AUTO Operational Monitor (``M2``): la decisión del barrido por reserva
        # (KEEP/RELEASE, dueño/caller, motivo, edad y ventana de gracia) para el spine.
        reconciliation_audits: list[
            tuple[PortfolioReservation, str, str | None, bool | None, bool | None]
        ] = []
        for reservation in live:
            created = _instant(reservation.created_at)
            instrument = reservation.instrument_id
            fill_key = (instrument, reservation.side)
            filled = 0.0
            if created is not None:
                for instant, qty in applied.get(fill_key, ()):
                    if instant >= created:
                        filled += qty
            available = max(0.0, filled - consumed.get(fill_key, 0.0))
            fill_qty = min(available, reservation.remaining_qty)
            # (``M2``) la edad se mide UNA vez y viaja declarada en la auditoría del barrido.
            aged = self._v2_reservation_is_aged(created)
            # OBS-14.b — FUERA DE ALCANCE y TODAVÍA JOVEN: ni se libera ni se toca su INTENT
            # de salida. Se conserva viva en el libro (su capital/riesgo SIGUE comprometido
            # para esta sesión) y no consume fills, así que el orden de lectura no la mezcla
            # con las propias. No se publica en ``outcomes``: sin entrada,
            # ``_v2_sync_exit_orders`` la lee como ``(0.0, None)`` y no actúa sobre una
            # identidad ajena. Una vez envejecida (su dueño ya cerró su turno) SÍ entra en la
            # regla 2 como candidata: es la retirada diferida que acota la retención.
            mine = only_ids is not None and reservation.reservation_id in only_ids
            if not mine and not aged:
                # (``M2``) AJENA y JOVEN: se CONSERVA por ventana de gracia. Es un KEEP con
                # causa medible — lo que el panel de concurrencia cuenta como ``graceWindowKeeps``.
                reconciliation_audits.append(
                    (reservation, RECONCILIATION_KEEP, REASON_GRACE_WINDOW_KEEP, False, False)
                )
                resolved.append(reservation)
                continue
            released: PortfolioReservation | None = None
            release_reason: str | None = None
            materialized = float(reservation.released_qty or 0.0)
            # OBS-20 — si el fill de ESTE ciclo ya está en el ledger, la reserva materializó
            # aunque su fila no lo haya registrado todavía (la liberación del camino caliente
            # la ejecuta la sesión que liquida el fill; si no tiene la reserva en su libro, no
            # ocurre). El hecho aplicado es evidencia durable: se toma como lo materializado de
            # ESTA reserva para no declarar ``cancel`` —"nunca materializó"— sobre una reserva
            # que sí lo hizo. Lo registrado en la fila nunca se rebaja, solo se completa.
            cycle = str(getattr(reservation, "cycle_id", None) or "").strip()
            if cycle:
                linked = cycle_fills.get((cycle, reservation.side), 0.0)
                if linked > 0.0:
                    # Cota por lo COMPROMETIDO: la evidencia dice qué materializó el ciclo, no
                    # puede declarar más de lo que esta reserva se comprometió a consumir.
                    committed = float(reservation.quantity or 0.0)
                    materialized = max(
                        materialized, min(linked, committed) if committed > 0.0 else linked
                    )
            if attribute_fills and fill_qty > 0:
                consumed[fill_key] = consumed.get(fill_key, 0.0) + fill_qty
                released = await self._v2_release_reservation(
                    reservation,
                    status=RESERVATION_RELEASED_BY_FILL,
                    reason=RELEASE_REASON_FILL,
                    released_qty=fill_qty,
                )
                release_reason = RELEASE_REASON_FILL
            elif (
                measurable and created is not None and instrument not in (in_flight or frozenset())
            ):
                # OBS-18 — "murió" se decide por la EVIDENCIA DE LA RESERVA (``released_qty``,
                # lo que el camino caliente liberó de ESTA fila), NUNCA por el agregado de
                # fills del instrumento+lado. Antes esta rama exigía ``filled == 0.0``: el
                # total de fills del instrumento posteriores al alta. Dos consecuencias
                # medidas en el replay multianual (16 reservas vivas, riesgo ``6000/6000``,
                # actividad congelada tras ``2022-05``):
                #
                # * una reserva que NUNCA materializó quedaba viva PARA SIEMPRE en cuanto
                #   otra reserva del mismo instrumento+lado llenaba (``filled != 0``), aunque
                #   su propia fila no registrara ni un lote (``released_qty == 0``);
                # * la COLA de un fill parcial no la retiraba NADIE: la regla 1 solo libera
                #   lo materializado y esta rama exigía ``filled == 0``.
                #
                # El sesgo fail-closed no cambia: la guardia de ``in_flight`` manda (una traza
                # sin aplicar del instrumento significa que la orden sigue trabajando y su cola
                # todavía puede materializar), con una lectura incompleta no se libera nada, y
                # el motivo declara la causa — ``tail_dead`` cuando la fila SÍ registró fill
                # parcial (se retira la cola, no lo materializado) y ``cancel`` cuando no
                # materializó nada. La liberación nunca supera la cantidad viva.
                dead_reason = (
                    RELEASE_REASON_RESTART
                    if startup
                    else (
                        RELEASE_REASON_DEAD_TAIL
                        if materialized > 0.0
                        else RELEASE_REASON_CANCEL
                    )
                )
                released = await self._v2_release_reservation(
                    reservation,
                    status=(
                        RESERVATION_RELEASED_BY_RESTART
                        if startup
                        else RESERVATION_RELEASED_BY_CANCEL
                    ),
                    reason=dead_reason,
                    released_qty=None,
                )
                release_reason = dead_reason
                # El outcome declara la evidencia DE LA RESERVA, no el agregado: una reserva
                # que no materializó no puede "marcar como llenado" el fill de su hermana al
                # sincronizar el INTENT de salida (lo cerraría como PARTIAL con cantidad ajena).
                fill_qty = materialized
            if released is not None:
                reconciliation_audits.append(
                    (reservation, RECONCILIATION_RELEASE, release_reason, True, aged)
                )
            else:
                # Sin liberación (lectura incompleta o traza en vuelo): se CONSERVA. El dueño
                # de la decisión se declara con ``mine`` para no confundirla con la gracia.
                reconciliation_audits.append(
                    (reservation, RECONCILIATION_KEEP, REASON_SESSION_OWNED, bool(mine), aged)
                )
            outcomes[reservation.reservation_id] = (fill_qty, released)
            resolved.append(released if released is not None else reservation)
        self._v2_reservations = tuple(row for row in resolved if row.is_live)
        # OBS-14.b — la PROPIEDAD solo se conserva mientras la reserva siga viva: una ya
        # liberada no vuelve a ser autoridad de retirada de nadie.
        self._v2_owned_reservations &= {
            row.reservation_id for row in self._v2_reservations
        }
        self._v2_reservations_measurement = (
            book_measurement
            if measurable
            else combine_measurements(book_measurement, MEASUREMENT_UNKNOWN)
        )
        # V2.43.3: los INTENT de salida siguen la misma reconciliación (identidad duradera).
        await self._v2_sync_exit_orders(outcomes)
        # V2.43.3 (P0-1) — productor real de la parada dura: un libro de compromiso que NO
        # se pudo medir CON reservas vivas es exactamente el caso que la auditoría pidió
        # escalar. No basta con vetar aperturas: el sistema queda HALTED (persistido) hasta
        # que una reconciliación explícita lo levante.
        if not measurable and self._v2_reservations:
            await self.engage_kill_switch_durable("RECONCILIATION_FAILURE")
        # AUTO Operational Monitor (``M2``): la decisión del barrido deja su traza en el spine
        # (última escritura del turno: el dinero y las salidas ya son durables). Sin sink es un
        # no-op y el panel de concurrencia declara los huecos.
        await self._v2_journal_reconciliation_decisions(reconciliation_audits)

    async def _v2_journal_reconciliation_decisions(
        self,
        decisions: Sequence[tuple[PortfolioReservation, str, str | None, bool | None, bool | None]],
    ) -> None:
        """(``M2``) publica en el spine cada KEEP/RELEASE del barrido con su dueño y causa.

        ``caller`` es la sesión que ejecuta el barrido (esta); ``mine`` distingue la reserva
        propia de la ajena conservada por gracia; ``aged``/``graceWindowSeconds`` viajan con su
        medición. Es lo que convierte ``ownerSession`` y ``graceWindowKeeps`` de ``NO MEDIDO``
        en hechos cuando el flag está ON.
        """
        if self._operational_audit_sink is None:
            return
        session = self._v2_audit_session()
        as_of = self._v2_instant()
        grace_seconds = self._v2_reservation_grace.total_seconds()
        for reservation, decision, reason, mine, aged in decisions:
            entry = build_reservation_reconciliation_entry(
                reservation_id=getattr(reservation, "reservation_id", None),
                cycle_id=getattr(reservation, "cycle_id", None),
                decision=decision,
                reason=reason,
                mine=mine,
                aged=aged,
                grace_window_seconds=grace_seconds,
                actor=self._engine_id,
                session_id=session,
                as_of=as_of,
                account_id=self._account_id,
                instrument_id=getattr(reservation, "instrument_id", None),
            )
            await self._v2_audit_emit(entry, label="reservation_reconciliation")

    def _v2_reservation_is_aged(self, created: datetime | None) -> bool:
        """¿La reserva ya superó la ventana de gracia? ``False`` si no se puede afirmar.

        OBS-14.b. Se compara contra el reloj de ESTA sesión (``self._time``, la misma
        autoridad temporal con la que se fecha el alta de las reservas propias). Sin fecha
        legible, o con una fecha FUTURA respecto a este reloj —dos procesos con relojes no
        comparables—, no se afirma edad: la reserva se conserva (fail-closed, el mismo
        criterio que la regla 2).
        """
        if created is None:
            return False
        return (self._time - created) > self._v2_reservation_grace

    async def _v2_sync_exit_orders(
        self, outcomes: Mapping[str, tuple[float, PortfolioReservation | None]]
    ) -> None:
        """Resincroniza los INTENT de salida con lo materializado (V2.43.3 · P0-2).

        Cada intent se actualiza con los fills que casaron contra SU reserva
        (``reservation_id``): un fill parcial deja el intent ``PARTIAL`` con su cola viva, y
        una reserva muerta sin fill lo deja ``ABANDONED``. Así el intent nunca queda "vivo
        para siempre" ni es re-emitible dos veces, y ``filled_qty``/``remaining_qty`` son la
        separación INTENT/ORDER/FILL que la auditoría pidió.
        """
        store = self._exit_order_store
        if store is None:
            return
        try:
            open_orders = await store.list_open(self._account_id)
        except Exception:  # noqa: BLE001 — no poder leer no autoriza a inventar estado.
            logger.exception("auto_sim v2 exit order read failed")
            return
        merged: dict[str, ExitOrder] = {}
        for order in open_orders:
            filled, released = outcomes.get(order.reservation_id or "", (0.0, None))
            updated = order
            if filled > 0:
                updated = order.apply_fill(filled, at=self._v2_instant())
            elif released is not None and not released.is_live:
                updated = order.abandon(released.release_reason or "cancel", at=self._v2_instant())
            if updated is not order:
                try:
                    await store.save(updated)
                except Exception:  # noqa: BLE001 — se declara; el intent no se pierde.
                    logger.exception(
                        "auto_sim v2 exit order save failed id=%s", order.exit_order_id
                    )
                    continue
            if updated.is_open:
                merged[updated.exit_order_id] = updated
        self._v2_exit_orders = merged

    async def _v2_release_reservation(
        self,
        reservation: PortfolioReservation,
        *,
        status: Any,
        reason: str,
        released_qty: float | None,
    ) -> PortfolioReservation | None:
        """Libera una reserva en el store durable; ``None`` si no se pudo (se conserva)."""
        store = self._reservation_store
        if store is None:
            return None
        try:
            return await store.release(
                reservation.reservation_id,
                status=status,
                reason=reason,
                released_qty=released_qty,
                at=self._v2_instant(),
            )
        except Exception:  # noqa: BLE001 — no se libera lo que no es durable.
            logger.exception(
                "auto_sim v2 reservation reconcile release failed id=%s",
                reservation.reservation_id,
            )
            return None

    async def _v2_refresh_regime(self) -> None:
        """Refresca el régimen y el ATR si las fuentes lo soportan (async + lectura sync).

        La lectura del régimen y del ATR en el tick es SÍNCRONA; el I/O (barras) se concentra
        aquí, una vez por barra, para que decidir no dependa de la red.

        E2: el ATR se refresca en el MISMO punto que el régimen para que la geometría de
        un tick sea consistente (una sola foto de barras por decisión).

        W4: el PRECIO **no** viaja aquí. Su frontera es otra (``<= B``, ``open`` de la barra
        corriente, distinta de la decisión ``<= B-1``) y, sobre todo, debe releerse en CADA
        turno: la fuente se recompone por sesión/tick y el short-circuit por barra no la
        refrescaría dentro de la misma barra (§3.1.b). Se refresca aparte en
        ``_v2_refresh_price``, siempre.
        """
        for source, label in (
            (self._v2_regime_source, "regime"),
            (self._v2_atr_source, "atr"),
        ):
            refresher = getattr(source, "refresh", None)
            if refresher is None or not callable(refresher):
                continue
            try:
                await refresher()
            except Exception:  # noqa: BLE001 — sin refresco el valor queda como estaba.
                logger.exception("auto_sim v2 %s refresh failed", label)

    async def _v2_refresh_price(self) -> None:
        """``W4`` — refresca la fuente de PRECIO en CADA turno (no sólo al rodar la barra).

        El runtime compone la fuente de precio sobre la MISMA sesión del tick, así que el
        objeto que llega al turno está VACÍO hasta que se refresca. A diferencia del régimen
        y del ATR (que se leen una vez por barra y quedan cacheados en RAM), el precio se
        consulta en vivo en cada turno —para marcar y para cerrar— y el short-circuit por
        barra (``reuse_bar_datum``) NO puede refrescarlo: si se omitiera, un turno dentro de
        la misma barra se quedaría con ``execution`` ausente y no podría marcar ni vender
        (fail-closed silencioso en el camino de precio real). Sin fuente real
        (``price_source is None``) es un no-op ⇒ ``Δ = 0`` para el ``price_script`` hermético.
        """
        source = self._price_source
        refresher = getattr(source, "refresh", None)
        if refresher is None or not callable(refresher):
            return
        try:
            await refresher()
        except Exception:  # noqa: BLE001 — sin refresco el valor queda como estaba.
            logger.exception("auto_sim v2 price refresh failed")

    def _v2_current_bar_start(self) -> str:
        """Inicio ISO-UTC de la barra corriente (``""`` si el timeframe no se entiende).

        Es la clave con la que se acotan las señales consumidas: lo consumido fuera de
        esta barra NO puede bloquear una oportunidad nueva (y no se guarda para siempre).
        """
        window = bar_window(self._time, self._v2_granularity.decision.timeframe)
        return window[0] if window is not None else ""

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

    def _v2_current_bar_day(self) -> str:
        """``W4`` — día de la barra **CORRIENTE** (``B``), frontera de EJECUCIÓN (§3.1.b).

        Es el ``as_of`` del precio de ejecución: la ventana ``<= B`` **incluye** la barra en
        curso, y de ella se toma sólo su ``open`` (la decisión sigue leyendo ``<= B-1``).
        Fail-closed: sin barra legible devuelve ``""`` ⇒ sin precio ⇒ HOLD declarado.
        """
        return self._v2_current_bar_start()[:10]

    def _v2_roll_consumed_bar(self) -> None:
        """Al cambiar de barra, la memoria de consumo se reinicia.

        Solo la barra corriente deduplica (la identidad de señal incluye la barra), así
        que el histórico no protege de nada y no debe crecer sin límite en un worker
        de larga vida. El espejo durable se poda en paralelo por la misma razón.
        """
        bar_start = self._v2_current_bar_start()
        if bar_start and bar_start != self._v2_consumed_bar:
            self._v2_consumed_bar = bar_start
            self._v2_consumed_signals.clear()

    # ---- W2 · Fase A: short-circuit por barra (seam en ``auto_turn``) ----------------
    def _v2_bar_short_circuit_applies(self) -> bool:
        """¿Este turno puede REUTILIZAR el dato de barra en vez de releerlo?

        Fase A (``W2``). Solo se afirma cuando las TRES cosas se sostienen: (a) el turno es
        durable (``real_turn`` encendió el seam), (b) el dato de decisión de la barra
        corriente ya se cargó en ESTE proceso, y (c) esa barra no dejó entradas aprobadas
        sin consumir — si quedara alguna, el reintento dentro de la barra es observable (el
        fill se ancla al minuto) y hay que releer como siempre.

        Fail-closed en los bordes: sin barra legible (timeframe no entendido) o sin dato de
        barra cargado NO se reutiliza nada.
        """
        if not self._v2_bar_short_circuit or not self._v2_bar_plan_bar:
            return False
        if self._v2_bar_pending:
            return False
        return self._v2_current_bar_start() == self._v2_bar_plan_bar

    def _v2_bar_note_plan(self) -> None:
        """Fija la barra cuyo dato de decisión acaba de cargarse en ESTE proceso."""
        self._v2_bar_plan_bar = self._v2_current_bar_start()
        self._v2_bar_pending = False

    def _v2_bar_note_settlement(self) -> None:
        """Cierra el turno: ¿quedó alguna entrada aprobada SIN consumir?

        La señal se marca consumida al materializarse el fill (``_v2_mark_signal_consumed``),
        así que una aprobación cuya señal sigue sin consumir es un reintento PENDIENTE que el
        short-circuit no puede saltarse (el fill depende del minuto).
        """
        plan = self._v2_plan
        if plan is None:
            return
        entries = getattr(plan, "entry_packages", None) or {}
        self._v2_bar_pending = any(
            self._v2_tick_signals.get(symbol) not in self._v2_consumed_signals
            for symbol in entries
        )

    async def _v2_load_consumed_signals(self) -> None:
        """Carga del espejo durable las señales consumidas de la barra corriente.

        Es lo que hace que el dedupe sobreviva al crash: sin esto, un reinicio
        volvería a autorizar la MISMA señal sobre la MISMA barra (el churn clásico:
        stop-out y re-entrada inmediata en la misma vela). Sin store (hermético) la
        RAM sigue siendo la única memoria. La lectura es fail-safe: si falla, se
        opera con lo que ya hubiera en RAM (no se bloquea el turno por telemetría).
        """
        if self._consumed_signal_store is None or not self._account_id:
            return
        bar_start = self._v2_current_bar_start()
        if not bar_start:
            return
        try:
            stored = await self._consumed_signal_store.list_bar(
                self._account_id, self._engine_id, bar_start
            )
        except Exception:  # noqa: BLE001 — sin lectura se conserva la memoria de RAM.
            logger.exception("auto_sim v2 consumed signals read failed")
            return
        self._v2_consumed_signals.update(str(s) for s in stored)

    async def _v2_prune_consumed_signals(self) -> None:
        """Descarta las señales consumidas de barras anteriores (tabla acotada).

        Solo la barra corriente puede deduplicar; conservar el histórico haría crecer
        la tabla sin límite y no aportaría ninguna protección extra.
        """
        if self._consumed_signal_store is None or not self._account_id:
            return
        bar_start = self._v2_current_bar_start()
        if not bar_start:
            return
        try:
            await self._consumed_signal_store.prune_before(
                self._account_id, self._engine_id, bar_start
            )
        except Exception:  # noqa: BLE001 — la poda es mantenimiento, no decide nada.
            logger.exception("auto_sim v2 consumed signals prune failed")

    async def _v2_mark_signal_consumed(self, symbol: str) -> None:
        """Marca la señal del símbolo (barra corriente) como ya consumida.

        Se llama SOLO cuando la entrada se ha ejecutado (fill confirmado): una propuesta
        vetada por el spine (kill/sim-gate/RiskGate/sin plan) no quema la señal, así que
        el turno siguiente puede volver a intentarla dentro de la misma barra. Lo que no
        puede repetirse es la MISMA oportunidad ya tomada.

        La marca se persiste ANTES de seguir: si el proceso muere justo después del
        fill, el reinicio debe seguir viendo la señal como consumida.
        """
        signal_id = self._v2_tick_signals.get(symbol)
        if not signal_id:
            return
        self._v2_consumed_signals.add(signal_id)
        if self._consumed_signal_store is None or not self._account_id:
            return
        bar_start = self._v2_current_bar_start()
        if not bar_start:
            return
        try:
            await self._consumed_signal_store.mark(
                self._account_id,
                self._engine_id,
                signal_id,
                instrument_id=symbol,
                bar_timestamp=bar_start,
            )
        except Exception:  # noqa: BLE001 — el fill ya ocurrió; la marca durable se
            # reintenta (la RAM ya la tiene y el tick siguiente la re-marcará).
            logger.exception("auto_sim v2 consumed signal persist failed symbol=%s", symbol)

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
        if not reuse_bar_datum:
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
        plan = plan_v2_tick(
            snapshot=snapshot,
            signals=self._v2_signals(packages),
            regime=regime,
            tunables=self._v2_tunables,
            as_of=self._time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            consumed_signal_ids=self._v2_consumed_signals,
            halted=self._v2_kill_switch_halted(),
            adaptive=adaptive,
            evidence=evidence_lookup,
        )
        # AUTO-1b: el compromiso se hace DURABLE antes de emitir la orden. Sin persistir
        # no hay aprobación que emitir (fail-closed, ver ``_v2_persist_tick_reservations``).
        # Con el dato de barra reutilizado la llamada se conserva: si la barra aún aprobara
        # algo nuevo (señal distinta aparecida a mitad de barra) su reserva DEBE persistirse.
        await self._v2_persist_tick_reservations(plan)
        # AUTO-11: la recomendación Adaptive se publica DESPUÉS de que el motor determinista la
        # consumió (mismo orden que AUTO-10: primero el dinero, después la traza). Así el journal
        # nunca registra una recomendación que no llegó a aplicarse.
        await self._v2_journal_adaptive_recommendation(adaptive)
        self._v2_journal.extend(plan.journal_entries)
        # AUTO Operational Monitor (``M2``): el journal de decisión del turno deja de vivir
        # sólo en RAM. Con el flag ON se persiste en el spine y ``SIGNAL``/``TOP_N``/``RISK``
        # pasan a ser enlazables por ``decision_id``/``cycleId``. Sin sink es un no-op.
        await self._v2_journal_entry_decisions(plan.journal_entries)
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
        # V2.88.84 — TOP3 cross-asset: la foto durable de «qué activos considera AUTO y por
        # qué». Una por barra; declara por slot si el score usó evidencia LAB o histórico.
        await self._v2_persist_top3(
            plan, regime=regime, evidenced_symbols=frozenset(evidence_lookup or {})
        )
        return plan

    async def _v2_persist_top3(
        self,
        plan: Any,
        *,
        regime: str | None,
        evidenced_symbols: frozenset[str],
    ) -> None:
        """V2.88.84 — escribe la foto durable del TOP3 cross-asset (``top3_opportunities``).

        Da el llamante PRODUCTIVO que faltaba a ``select_top3_records`` + el sink de la
        migración 052: sin esto, la tabla y ``GET /top3-opportunities/latest`` no tenían quién
        las escribiera (el hueco que dejó ``v2.88.82``: la cadena se probaba, pero no se cableaba).

        * **Una foto por barra**: el ``run_id`` se ancla a la barra de decisión y solo se
          reescribe cuando la barra cambia (idempotente dentro de la barra).
        * **Degradación DECLARADA**: un activo puntuado sin campeón ACTIVE (scoring histórico
          ``edge``+``liquidity``) lleva el motivo ``scoring_historico_sin_campeon``; la ausencia
          de evidencia deja de ser silenciosa.
        * Sin sink inyectado es un no-op (Δ = 0). Un fallo del sink se declara y NO tumba el
          turno: es observabilidad, no decisión.
        """
        sink = self._top3_opportunity_sink
        if sink is None:
            return
        ranked = tuple(getattr(plan, "ranked", ()) or ())
        if not ranked:
            return
        bar = self._v2_current_bar_start()
        if not bar or bar == self._v2_top3_bar:
            return
        run_id = f"top3-{self._account_id or 'sim'}-{bar}"
        records = select_top3_records(
            list(ranked), top_n=3, run_id=run_id, evidenced_symbols=evidenced_symbols
        )
        if not records:
            return
        degraded = [
            record.instrument_id
            for record in records
            if record.reason == HISTORICAL_SCORING_NO_CHAMPION
        ]
        try:
            await sink(records, regime)
        except Exception:  # noqa: BLE001 — la traza del TOP3 no puede tumbar el turno.
            logger.exception("auto_sim v2 TOP3 cross-asset sink failed")
            return
        self._v2_top3_bar = bar
        if degraded:
            logger.warning(
                "auto_sim v2 TOP3 cross-asset: %s sin campeón ACTIVE — scoring histórico "
                "declarado (run=%s)",
                ",".join(degraded),
                run_id,
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

    async def _v2_read_cycle_regimes(
        self, cycle_ids: Sequence[str]
    ) -> tuple[Mapping[str, str], bool]:
        """AUTO-10 — régimen por ciclo desde el journal durable, o huecos DECLARADOS.

        Devuelve ``(regime_by_cycle, source_durable)``. ``source_durable`` es ``True`` solo si
        la fuente durable se consultó de verdad: con él, un ciclo sin régimen se declara
        ``regime_not_found`` en vez de ``regime_not_durable``. Sin lector inyectado, o si el
        lector revienta, la fuente NO se consultó y el hueco se declara como siempre (por eso
        el par de valores viaja junto: un mapa vacío sin ese flag mentiría).

        Los huecos se registran como ``warning`` (con su motivo) y las filas de más de un
        reintento como ``info`` (el valor publicado no cambia: gana la confirmación más nueva).
        """
        reader = self._cycle_regime_reader
        if reader is None:
            return {}, False
        try:
            reading = await reader(cycle_ids)
        except Exception:  # noqa: BLE001 — sin lectura de régimen el R sigue midiéndose.
            logger.exception("auto_sim v2 adaptive cycle regime read failed")
            return {}, False
        summary = reading.as_dict()
        if summary["unconfirmed"] or summary["absent"] or summary["notDerivable"]:
            # Huecos declarados, con su motivo: silenciarlos convertiría el hueco en mentira.
            logger.warning("auto_sim v2 adaptive cycle regime gaps %s", summary)
        elif summary["collapsedRows"]:
            # Un reintento del tick reescribe la traza del mismo ciclo: no es un fallo, pero se
            # declara (AUTO-10 paso 4) para que un duplicado anómalo no sea invisible.
            logger.info("auto_sim v2 adaptive cycle regime duplicates %s", summary)
        return dict(reading.regime_by_cycle), True

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
            logger.warning(
                "auto_sim v2 adaptive confidence gaps %s", confidence.as_dict()["notes"]
            )
        # AUTO-19A — la INCERTIDUMBRE del edge (intervalo por episodios + ``edgeConfidence``) desde
        # el MISMO material ya leído: no añade I/O ni un segundo FIFO. Es un hecho MEDIDO, así que se
        # publica aunque el gate limite el encogimiento (igual que la banda): lo que el gate apaga es
        # el USO para repartir, no la evidencia. No mueve la regla ni el sello (``auto18-v1``).
        uncertainty = build_adaptive_uncertainty_from_fills(
            fills=fills, cycle_risk=cycle_risk, confidence=confidence
        )
        if uncertainty.by_strategy:
            gaps = sorted(
                {note for row in uncertainty.by_strategy for note in row.notes}
            )
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

    def _v2_adaptive_recovery_evidence(
        self, fills: Any, cycle_risk: Any, confidence: Any
    ) -> dict[str, RecoveryEvidence]:
        """La evidencia de la rampa del tick, medida con los fills y la confianza ya construidos."""
        return recovery_evidence_from_fills(
            fills=fills,
            cycle_risk=cycle_risk,
            reactivated_at=self._v2_adaptive_reactivated_at or None,
            confidence=confidence,
        )

    def _v2_adaptive_observe_reactivations(self, plan: AdaptivePlan) -> bool:
        """(AUTO-13 §24) fechas de reincorporación OBSERVADAS en el proceso; ``True`` si cambió.

        La memoria de la rampa es **derivada**, no persistida: el lector durable la **siembra** en el
        arranque (``reactivated_at``) y este seguimiento la completa con las transiciones que el
        propio proceso ve. Sin él, una versión que cumple su cooldown a mitad de proceso no entraría
        nunca en la rampa hasta el siguiente reinicio —y el proceso largo es el caso normal—, así que
        la mitad viva no es un adorno: es lo que hace que la rampa exista entre reinicios.

        Reglas, todas declaradas:

        * **Solo se fecha una reincorporación OBSERVADA**: la versión estaba pausada en el tick
          anterior (``_v2_adaptive_paused_cycles_entered``) y ya no lo está. Una versión que nunca
          estuvo pausada NO entra: no tiene reincorporación que fechar.
        * **Al volver a pausa se OLVIDA**: el escalón se descarta (§24) y el siguiente corte se
          fechará de nuevo cuando la rotación la reactive. Sin esto, la rampa reanudaría a mitad de
          camino con la evidencia de la etapa anterior.
        * **El instante es el del tick** (``_v2_instant``), el mismo reloj con el que se fechan las
          filas del journal: la evidencia que confirma la subida es la POSTERIOR a ese instante.
        """
        tracked = dict(self._v2_adaptive_reactivated_at)
        was_paused = {
            version
            for version, count in self._v2_adaptive_paused_cycles_entered.items()
            if int(count) > 0
        }
        paused = set(plan.rotation.paused)
        # Se fecha SOLO lo que cambia: si no hay ninguna reincorporación que fechar, el reloj no se
        # toca (una lectura de reloj por tick que no se usa sería un coste y un dato de más).
        fresh = [
            row.strategy_version
            for row in plan.health
            if row.strategy_version not in paused
            and row.strategy_version in was_paused
            and row.strategy_version not in tracked
        ]
        for row in plan.health:
            if row.strategy_version in paused:
                tracked.pop(row.strategy_version, None)
        if fresh:
            stamp = self._v2_instant()
            for version in fresh:
                tracked[version] = stamp
        if tracked == self._v2_adaptive_reactivated_at:
            return False
        self._v2_adaptive_reactivated_at = tracked
        return True

    def _v2_adaptive_policy(self) -> AdaptivePolicy:
        """La política Adaptive en curso, en UN solo sitio (la usan el plan y el lector).

        El lector de recuperación necesita sus dos datos de identidad —``policy_version`` y
        ``min_pause_cycles``— para juzgar la historia durable con los umbrales de HOY. Derivarlos
        de una segunda construcción de la política permitiría que divergieran en silencio.
        """
        return AdaptivePolicy(win_rate_floor=self._v2_tunables.adaptive_win_rate_floor)

    def _v2_next_paused_cycles(self, plan: AdaptivePlan) -> dict[str, int]:
        """Ciclos consecutivos de pausa por versión, para hysteresis/cooldown del próximo tick.

        Una versión que deja de estar pausada DESAPARECE del mapa (cuenta a 0): la
        reactivación efectiva del plan es la que manda, no la historia.
        """
        return {
            version: int(self._v2_adaptive_paused_cycles.get(version, 0)) + 1
            for version in plan.rotation.paused
        }

    def _v2_data_gate_policy(self) -> DataGatePolicy:
        """La política del Data Gate en UN solo sitio (la usan el ancla y, en el Paso 3, el plan).

        Mismo patrón que ``_v2_adaptive_policy``: derivar los umbrales de dos construcciones
        distintas permitiría que divergieran en silencio y el ancla se mediría con reglas que no son
        las que sella la versión.
        """
        return DataGatePolicy()

    @staticmethod
    def _v2_regime_available(regime: str | None) -> bool:
        """¿Declaró el tick un régimen **juzgable**? (insumo ``regime_available`` del gate).

        Se acepta cualquiera de los dos ejes —el de mercado ya canónico (``TREND_UP``) o el
        operativo que el plan traduce (``BULL_TREND``)— porque el llamante puede aportar
        cualquiera de los dos y los dos declaran un régimen. Lo que NO declara régimen es
        ``None``, la cadena vacía, ``UNKNOWN`` y ``RISK_OFF`` (el macro es un hecho de RIESGO,
        no un régimen de mercado: el plan lo traduce a ``UNKNOWN`` por diseño).
        """
        return (
            coerce_market_regime(regime) != ADAPTIVE_REGIME_UNKNOWN
            or to_market_regime(regime) != ADAPTIVE_REGIME_UNKNOWN
        )

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
            bool(confidence.recent_available)
            if getattr(confidence, "by_strategy", None)
            else None
        )
        return assess_data_gate(
            sink_failures=int(getattr(self, "_v2_adaptive_sink_failures", 0) or 0),
            # AUTO-15: se DECLARA la procedencia de la racha (no cambia el estado): un 0 no puede
            # leerse como "el sink está sano" si en realidad no hay constancia durable.
            sink_failures_durable=bool(
                getattr(self, "_v2_adaptive_sink_failures_durable", False)
            ),
            journal_age_cycles=self._v2_adaptive_gate_journal_age(),
            # Sin lectura durable registrada NO se declara un fallo de lectura: no se observó
            # ninguno (el hueco de "sin lector" lo declara AUTO-11 en el arranque, no el gate).
            read_ok=True if reading is None else bool(reading.read_ok),
            measurement_completeness=completeness,
            recent_available=recent_available,
            regime_available=self._v2_regime_available(regime),
            unreadable_rows=0 if reading is None else int(reading.unreadable),
            policy_version_mismatch=(
                False if reading is None else bool(reading.policy_version_mismatch)
            ),
            insufficient_history=(
                False if reading is None else bool(reading.insufficient_history)
            ),
            policy=self._v2_data_gate_policy(),
        )

    def _v2_adaptive_decision_cycles(
        self, reading: DataGateReading, policy: AdaptivePolicy
    ) -> dict[str, int]:
        """Los ciclos de pausa que ENTRAN en la decisión, según el efecto declarado del gate.

        Con ``ADAPTS``/``LIMITS`` son los reales (comportamiento histórico). Con ``FREEZES``
        (``STALE``) una pausa viva **no levanta** su cooldown: la evidencia con la que se
        confirmaría que ya cumplió su mínimo es justo la que no se pudo leer, así que no se
        confirma y la versión sigue pausada con el motivo declarado ``cooldown``. Las pausas
        NUEVAS por salud no se tocan: el material que entra en ``recommend_rotation`` es el mismo.

        El contador REAL sigue creciendo (``_v2_next_paused_cycles`` lee el mapa verdadero), de
        modo que al volver la evidencia la reactivación se juzga con la antigüedad verdadera, no
        con el valor retenido para la decisión.
        """
        live = dict(getattr(self, "_v2_adaptive_paused_cycles", {}) or {})
        if reading.effect != DATA_GATE_FREEZES or not live:
            return live
        ceiling = max(0, int(policy.min_pause_cycles) - 1)
        if ceiling <= 0:
            # ``min_pause_cycles <= 1`` no deja margen para retener por cooldown: no hay mecanismo,
            # y se DECLARA el hueco en vez de fingir una retención. Inalcanzable con la política de
            # la casa (``min_pause_cycles`` = 3); queda visible si alguien la cambia.
            logger.warning(
                "auto_sim v2 adaptive data gate STALE cannot hold pauses min_pause_cycles=%s",
                policy.min_pause_cycles,
            )
            return live
        return {
            version: min(int(count), ceiling)
            for version, count in live.items()
            if int(count) > 0
        }

    def _v2_measure_adaptive_journal_anchor(self, reading: AdaptiveStateReading) -> None:
        """Mide el ancla durable del journal —ciclos desde la última publicación— y la declara.

        El ancla es lo único de ``AUTO-13`` que **sobrevive a un reinicio**: sale del ``asOf`` de la
        última fila publicada y de la cadencia declarada, no de un contador de proceso. Un instante
        ilegible da ``None`` (no se puede juzgar la antigüedad), y eso **no** bloquea: se declara.
        """
        self._v2_adaptive_journal_anchor_age = journal_age_cycles(
            last_published_at=reading.last_published_at,
            now=self._v2_instant(),
            policy=self._v2_data_gate_policy(),
        )

    def _v2_adaptive_gate_journal_age(self) -> int | None:
        """Antigüedad del journal para el gate, **corroborada** por un fallo de escritura propio.

        El ancla durable sola no puede bloquear. Tras un arranque con Adaptive OFF (o una pausa)
        más larga que ``journal_gap_blocked`` ciclos, la última fila es antigua aunque el journal
        esté sano; y como ``BLOCKED`` ⇒ ``adaptive = None`` ⇒ no se escribe, el ancla **nunca** se
        curaría: un journal sano quedaría bloqueado para siempre. Por eso la antigüedad solo cuenta
        cuando el propio proceso ha fallado al publicar: así un journal muerto se sigue detectando
        (el fallo y la antigüedad crecen juntos, incluso tras un reinicio) y uno sano se cura con su
        primera escritura, que pone el ancla a 0.
        """
        failures = int(getattr(self, "_v2_adaptive_sink_failures", 0) or 0)
        if failures <= 0:
            return None
        anchor = int(getattr(self, "_v2_adaptive_journal_anchor_age", 0) or 0)
        return anchor + failures

    async def _v2_journal_adaptive_recommendation(self, adaptive: AdaptivePlan | None) -> None:
        """AUTO-11 — publica la recomendación Adaptive del turno en el journal durable.

        Es la pieza que hace DURABLE la memoria de la rotación: lo que antes solo existía como
        ``AdaptivePlan`` en RAM (y se perdía al volver del turno) queda como fila append-only, y el
        arranque puede reconstruir de ahí el cooldown. Se llama **después** de ``plan_v2_tick`` y
        del compromiso de capital, replicando el orden de AUTO-10: el journal nunca registra una
        recomendación que el motor determinista no llegó a consumir.

        Fail-open **declarado**: sin sink o sin plan no se escribe —y no se finge una fila vacía,
        que afirmaría "Adaptive evaluó y no recomendó nada"—; un fallo del sink no tumba el turno,
        pero se registra, porque un silencio aquí devuelve el cooldown a la memoria del proceso.

        **AUTO-13 (§21).** Un fallo del sink deja de ser solo un renglón de log: se cuenta el fallo
        CONSECUTIVO y un éxito RESETEA la racha. Ese contador vivía **solo** en el proceso (su
        límite, declarado); el ancla durable de antigüedad mide *publicación*, no *error*.

        **AUTO-15.** El contador deja de nacer en el proceso: el fallo se **persiste** en
        ``adaptive_gate_state`` (incremento atómico) y el arranque lo **lee** para sembrar la racha
        (``_v2_recover_adaptive_gate_streak``), de modo que un reinicio no devuelve el gate a
        «sano» ni pierde una racha a punto de ser ``STALE``. El reset en el éxito no amplifica (sin
        racha viva no escribe) y la procedencia de la racha se publica en el gate
        (``sinkFailuresDurable``): un ``0`` no se lee igual si es durable que si nació en el
        proceso.
        """
        sink = self._adaptive_sink
        if sink is None or adaptive is None:
            return
        entry = build_adaptive_recommendation_entry(
            plan=adaptive,
            actor=self._engine_id,
            as_of=self._v2_instant(),
            account_id=self._account_id,
            # El contador que ENTRÓ a decidir (no el de salida): es el dato con el que se
            # reconstruye la racha, y publicar el de salida afirmaría una decisión imposible.
            paused_cycles=self._v2_adaptive_paused_cycles_entered,
        )
        if entry is None:
            return
        try:
            await sink(entry)
        except Exception:  # noqa: BLE001 — publicar no puede tumbar el turno.
            # AUTO-13 (§21): el fallo se CUENTA (consecutivo), no solo se loguea. ``getattr``
            # porque un worker hermético de costura puede no traer el contador; en producción nace
            # en 0. Un éxito lo resetea justo abajo: un fallo aislado no arrastra.
            local = int(getattr(self, "_v2_adaptive_sink_failures", 0) or 0) + 1
            # AUTO-15: y se PERSISTE. La racha durable manda (puede venir de un proceso anterior);
            # si el store falta o falla, la de proceso es la que queda, declarada.
            failures = await self._v2_record_adaptive_sink_failure(local=local)
            self._v2_adaptive_sink_failures = failures
            logger.exception(
                "auto_sim v2 adaptive recommendation journal failed consecutive=%s", failures
            )
            return
        # Éxito: se RESETEA la racha (un fallo aislado no arrastra) y el ancla durable vuelve a 0
        # —se acaba de publicar evidencia—, que es lo que cura un journal que estuvo sin escribir.
        self._v2_adaptive_sink_failures = 0
        self._v2_adaptive_sink_last_success_at = entry.created_at
        # AUTO-15: el reset durable NO amplifica —sin racha viva no escribe—, para que un
        # despliegue sano no pague una escritura por tick.
        await self._v2_record_adaptive_sink_success(at=entry.created_at)
        self._v2_adaptive_journal_anchor_age = 0

    async def _v2_recover_adaptive_gate_streak(self) -> None:
        """(AUTO-15) siembra la racha DURABLE de fallos del sink, UNA vez por proceso.

        Cierra la ventana que ``AUTO-13`` declaró como límite suyo: el contador de fallos
        consecutivos del sink era **de proceso**, así que un reinicio lo devolvía a 0 y el gate
        volvía a creerse sano con un journal que llevaba fallando (o, al revés, olvidaba la racha
        que lo iba a llevar a ``STALE``). El journal **no** puede reconstruirla —una escritura que
        falló no dejó fila— y el ancla de antigüedad mide *publicación*, no *error*: de ahí la
        tabla propia.

        Fail-open **declarado**, sin fingir en ningún caso: sin store, con fila ausente o con una
        lectura rota, la racha arranca en 0 —el límite que sigue existiendo— y se registra el
        motivo. Un 0 aquí **no** afirma «el sink está sano»: afirma «no hay constancia durable de
        fallos», que es lo que se pudo medir.
        """
        store = getattr(self, "_adaptive_gate_store", None)
        if store is None:
            self._v2_adaptive_sink_failures_durable = False
            return
        try:
            state = await store.load(self._account_id or "", self._engine_id)
        except Exception:  # noqa: BLE001 — un store roto no puede reiniciar la racha en silencio.
            self._v2_adaptive_sink_failures_durable = False
            logger.exception(
                "auto_sim v2 adaptive gate streak UNREAD; arranca a 0 (sin constancia durable)"
            )
            return
        # La lectura durable CONTESTÓ (con fila o con su ausencia): la racha que entra al gate es
        # un hecho durable, aunque sea 0. Sin esto, un ``0`` restaurado no se distinguiría de uno
        # que nació en el proceso.
        self._v2_adaptive_sink_failures_durable = True
        self._v2_adaptive_sink_failures = sink_failures_from_state(state)
        if state is None:
            logger.info(
                "auto_sim v2 adaptive gate streak recovered none (%s)",
                {"sinkFailures": self._v2_adaptive_sink_failures, "durableRow": False},
            )
        else:
            logger.info("auto_sim v2 adaptive gate streak recovered %s", state.to_dict())

    async def _v2_record_adaptive_sink_failure(self, *, local: int) -> int:
        """(AUTO-15) persiste el fallo consecutivo y devuelve la racha que ENTRARÁ al gate.

        La racha durable es la fuente de verdad: si el store contesta, su valor manda (puede traer
        los fallos de un proceso anterior, que es justo lo que se quiere conservar). Si el store
        falta (camino hermético) o falla —probable: se acaba de caer una escritura—, la racha vive
        en el proceso y **se declara**: no se finge ni un éxito ni una persistencia que no ocurrió.
        """
        store = getattr(self, "_adaptive_gate_store", None)
        if store is None:
            self._v2_adaptive_sink_failures_durable = False
            return local
        try:
            persisted = await store.record_failure(
                self._account_id or "", self._engine_id, at=self._v2_instant()
            )
        except Exception:  # noqa: BLE001 — un store roto no puede tumbar el turno.
            self._v2_adaptive_sink_failures_durable = False
            logger.exception(
                "auto_sim v2 adaptive gate streak NOT durable consecutive=%s", local
            )
            return local
        self._v2_adaptive_sink_failures_durable = True
        return int(persisted)

    async def _v2_record_adaptive_sink_success(self, *, at: str | None) -> None:
        """(AUTO-15) resetea la racha durable SIN amplificar: sin racha viva no escribe nada."""
        store = getattr(self, "_adaptive_gate_store", None)
        if store is None:
            self._v2_adaptive_sink_failures_durable = False
            return
        try:
            await store.record_success(self._account_id or "", self._engine_id, at=at)
        except Exception:  # noqa: BLE001 — la publicación ya ocurrió; el reset no la tumba.
            self._v2_adaptive_sink_failures_durable = False
            logger.exception("auto_sim v2 adaptive gate streak reset failed")
            return
        # El store contestó (escribiendo o declarando que no había racha que resetear): la racha
        # que entra al gate es un hecho durable.
        self._v2_adaptive_sink_failures_durable = True

    async def _v2_recover_adaptive_state(self) -> None:
        """AUTO-11 — reconstruye el estado Adaptive del journal durable, UNA vez por proceso.

        Cierra el P1 de la auditoría de ``V2.51``: una estrategia pausada podía retirar su pausa
        antes de cumplir la ventana mínima porque el contador se reconstruía de la memoria y un
        reinicio lo devolvía a 0. Ahora la racha se rehace de las evaluaciones durables
        (``rebuild_paused_cycles``) y se siembra ``_v2_adaptive_paused_cycles`` antes del primer
        plan del proceso.

        Gateado por ``adaptive_enabled``: con el flag OFF no hay I/O y el comportamiento es
        byte-idéntico al de ``V2.51``. Fail-open **declarado** en tres casos, todos SIN fingir una
        reactivación: sin lector, con lector roto (``read_ok = False``) o con lectura incompleta, el
        contador arranca vacío —el límite que sigue existiendo— y se registra el motivo.
        """
        if self._v2_adaptive_state_recovered:
            return
        self._v2_adaptive_state_recovered = True
        if not self._v2_tunables.adaptive_enabled:
            return
        # AUTO-15: la racha DURABLE de fallos del sink se siembra ANTES del primer plan y ANTES de
        # los atajos del lector del journal: es un hecho de otro eje (el sink que escribe), y el
        # caso en que más importa —el journal fallando— es justo el que deja ``read_ok=False``. Si
        # se sembrara después de ese atajo, el reinicio durante un journal roto arrancaría a 0.
        await self._v2_recover_adaptive_gate_streak()
        reader = self._adaptive_reader
        if reader is None:
            # Sin lector no hay ni racha ni ancla: los DOS límites se declaran (no se finge salud).
            self._v2_adaptive_journal_anchor_age = None
            logger.warning(
                "auto_sim v2 adaptive state NOT durable: no reader; el cooldown arranca a 0 "
                "(journalAgeCycles=None)"
            )
            return
        window = ADAPTIVE_STATE_WINDOW_DEFAULT
        try:
            reading = await reader(self._account_id)
        except Exception:  # noqa: BLE001 — un lector roto NO puede reiniciar el cooldown.
            logger.exception("auto_sim v2 adaptive state read failed")
            reading = adaptive_state_unread("reader_failed", window=window)
        self._v2_adaptive_state_reading = reading
        if not reading.read_ok:
            # Contador vacío + hueco DECLARADO: "no se pudo leer" nunca se disfraza de "no había
            # pausas". El ancla durable tampoco se puede medir: ``None``, no juventud.
            self._v2_adaptive_paused_cycles = {}
            self._v2_adaptive_journal_anchor_age = None
            summary = reading.as_dict()
            summary["journalAgeCycles"] = None
            logger.warning("auto_sim v2 adaptive state UNREAD %s", summary)
            return
        self._v2_adaptive_paused_cycles = dict(reading.paused_cycles)
        # AUTO-13 (§24): se SIEMBRA la memoria de la rampa con los cortes durables. Es la mitad que
        # sobrevive al reinicio; el seguimiento de transiciones del proceso la completa después.
        self._v2_adaptive_reactivated_at = dict(reading.reactivated_at)
        # AUTO-13: el ancla durable del journal se mide con la cadencia declarada (``None`` si el
        # instante no se pudo leer: se declara y no bloquea). Es la mitad que sobrevive al reinicio.
        self._v2_measure_adaptive_journal_anchor(reading)
        summary = reading.as_dict()
        summary["journalAgeCycles"] = self._v2_adaptive_journal_anchor_age
        if reading.policy_version_mismatch:
            logger.warning("auto_sim v2 adaptive policy version mismatch %s", summary)
        if reading.insufficient_history or reading.saturated or reading.unreadable:
            logger.warning("auto_sim v2 adaptive state recovered (bounded) %s", summary)
        else:
            logger.info("auto_sim v2 adaptive state recovered %s", summary)

    async def _v2_reconcile_cycle_traces(self) -> None:
        """AUTO-11 — cruza capital reservado con traza de régimen, UNA vez por proceso.

        La ventana ``RESERVATION COMMITTED → CRASH → NO JOURNAL`` que AUTO-10 aceptó y declaró
        dejaba un ciclo con dinero comprometido y sin régimen, de forma **invisible**. Aquí se
        comprueba al arrancar y se declara por motivo (``auto_cycle_reconciliation``). Read-only:
        no corrige ni rescribe nada.

        Fail-open declarado: sin libro de reservas o sin lector de régimen no hay nada que cruzar
        (camino hermético) y una lectura rota se registra sin afirmar que todo está limpio.
        """
        if self._v2_cycle_trace_reconciled:
            return
        self._v2_cycle_trace_reconciled = True
        reader = self._cycle_regime_reader
        store = self._reservation_store
        window = getattr(store, "list_recent_with_cycle", None)
        if reader is None or not callable(window):
            return
        try:
            reservations = await window(self._account_id, limit=ADAPTIVE_STATE_WINDOW_DEFAULT)
        except Exception:  # noqa: BLE001 — sin ventana no se afirma nada.
            logger.exception("auto_sim v2 cycle trace reconciliation: reservations read failed")
            return
        cycle_ids = cycle_ids_with_reservations(list(reservations))
        if not cycle_ids:
            logger.info("auto_sim v2 cycle trace reconciliation: no reserved cycles in the window")
            return
        try:
            reading = await reader(cycle_ids)
        except Exception:  # noqa: BLE001 — el lector declara su hueco; no se inventa.
            logger.exception("auto_sim v2 cycle trace reconciliation: regime read failed")
            return
        report = reconcile_cycle_trace(reservation_cycle_ids=cycle_ids, reading=reading)
        if report.clean:
            logger.info("auto_sim v2 cycle trace reconciliation clean %s", report.as_dict())
        else:
            logger.warning("auto_sim v2 cycle trace reconciliation GAPS %s", report.as_dict())

    def _v2_measure_opportunity_costs(self) -> None:
        """V2.45/AUTO-5 — coste de oportunidad: precio POSTERIOR de las rechazadas.

        Para cada oportunidad NO operada que aún no tiene precio posterior, se toma el
        precio del símbolo en el tick corriente (el primero observado tras el descarte).
        Si el símbolo no cotiza este tick se deja ``None`` y el día lo declara
        ``unmeasured``: nunca se inventa un precio.
        """
        for index, row in enumerate(self._v2_opportunities):
            if row.status == OPPORTUNITY_TRADED or row.subsequent_price is not None:
                continue
            price = self._v2_price_exec(row.instrument_id, self._v2_bar_tick())
            if price is None:
                # W4: sin precio posterior la oportunidad queda ``unmeasured`` (el propio
                # contrato de este método ya lo exigía: nunca se inventa un precio).
                self._v2_note_price_missing(row.instrument_id)
                continue
            try:
                measured = Decimal(str(price))
            except (ArithmeticError, ValueError):
                continue
            if not measured.is_finite() or measured <= 0:
                continue
            self._v2_opportunities[index] = replace(row, subsequent_price=measured)

    def _v2_recon_status(self, symbol: str) -> str | None:
        """Estado de reconciliación que ve el PositionManager para ese símbolo.

        Solo un ``DIVERGENT`` *conocido* se reporta como ``drift`` (⇒ CRITICAL ⇒
        REVIEW). ``UNKNOWN`` (no se pudo verificar) NO debe degradar la protección:
        la reconciliación veta APERTURAS (``_openings_vetoed``), nunca cierres —
        reducir/cerrar no empeora el riesgo. Reportarlo como ``drift`` dejaría una
        posición con el stop rebasado sin vender, que es el peor fallo posible.
        Devuelve ``None`` cuando no hay veredicto (el spine lo trata como ATTENTION).
        """
        status = self._reconciliation.get(symbol)
        if status == POSITION_PROJECTION_DIVERGENT:
            return "drift"
        if status in {POSITION_PROJECTION_OK, POSITION_PROJECTION_REBUILT}:
            return "clean"
        return None

    def _v2_adopt_position(self, symbol: str, price: Decimal) -> PositionState | None:
        """Recupera el ``PositionState`` de una posición abierta sin estado V2 vivo.

        Dos caminos, en este orden:
        1. **Plan durable** (P4): si el espejo traía ``position_state``, se REHIDRATA
           exacto (``position_state_from_dict``) — mismo stop, mismos objetivos, mismas
           parciales y trailing que el motor seguía antes del crash. La cantidad se
           re-sincroniza con la posición real; el plan NO se reinterpreta.
        2. **Geometría reconstruida** (fallback): sin plan durable se adopta con la
           MISMA geometría que usa el pipeline (stop = entrada − atr_mult × ATR,
           objetivos en múltiplos de R) para que el stop siga vivo. El plan
           reconstruido se marca como ``adopted`` (auditoría explícita: no sobrevivió
           un plan real al reinicio) — gestionar sin estado es peor que un plan
           aproximado, pero nunca se disfraza de plan original.

        AUTO-2 (fail-closed): si el estado NO es verificable (blob de un tag anterior sin
        FSM, o geometría reconstruida) la adopción se DECLARA degradada
        (``RECONCILIATION_REQUIRED`` + ``PROTECTION_MISSING``) con atención alta, en vez
        de fingir que hay protección. El stop se conserva/reconstruye igual: una posición
        declarada sin protección sigue protegida por el mejor stop conocido; lo que no se
        puede fingir es la CERTEZA.
        """
        held = self._open.get(symbol, Decimal("0"))
        entry = self._entry_price.get(symbol)
        if held <= 0 or entry is None or entry <= 0 or price <= 0:
            return None
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        restored = self._v2_restore_durable_position(symbol, held)
        if restored is not None:
            if restored.lifecycle_state is None:
                # Plan de un tag anterior a AUTO-2: el estado no es verificable.
                return self._v2_degrade_adoption(
                    symbol,
                    restored,
                    source="plan",
                    reason="durable_plan_without_lifecycle_state",
                    at=at,
                )
            return restored
        # E2: la geometría reconstruida usa el ATR REAL si existe; el sintético se declara
        # como tal (antes se usaba siempre el 2% del precio, también para adoptar).
        atr_value, atr_source = self._v2_atr_geometry(symbol, float(entry))
        if atr_source != ATR_SOURCE_REAL:
            self._journal_position_event(
                symbol,
                ATR_GEOMETRY,
                at=at,
                detail={"atrSource": atr_source, "atr": atr_value, "phase": "adoption"},
            )
        if atr_value is None:
            # Ni siquiera la geometría de emergencia es construible sin ATR.
            atr_value = float(entry) * self._v2_tunables.atr_pct_fallback
        stop = entry - Decimal(str(self._v2_tunables.atr_multiplier)) * Decimal(str(atr_value))
        if stop <= 0 or stop >= entry:
            # Ni siquiera la geometría de emergencia es construible: se declara la
            # ausencia de protección SIN stop sintético (no se inventa un número).
            self._journal_position_event(
                symbol,
                PROTECTION_MISSING,
                at=at,
                detail={"source": "none", "reason": "geometry_not_constructible"},
            )
            logger.warning(
                "auto_sim v2 adoption without protection symbol=%s entry=%s", symbol, entry
            )
            return None
        r_multiple = entry - stop
        plan: dict[str, object] = {
            "decisionId": f"adopted-{symbol}",
            "instrumentId": symbol,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": float(entry),
            "structuralStop": float(stop),
            "target1": float(entry + Decimal(str(self._v2_tunables.target1_r)) * r_multiple),
            "target2": float(entry + Decimal(str(self._v2_tunables.target2_r)) * r_multiple),
            "adopted": True,
        }
        position = build_position_state_from_fill(
            plan,
            fill_price=float(entry),
            fill_quantity=float(held),
            filled_at=at,
            # E1: también una ADOPTADA necesita techo declarado; se congela desde el
            # instante de adopción (no hay fill original que consultar). Sin él, la
            # posición adoptada quedaría sin salida por tiempo para siempre.
            max_holding_period_days=resolve_holding_horizon(
                self._v2_tunables.exit_template
            ).max_holding_period_days,
        )
        if position is None:
            return None
        logger.warning(
            "auto_sim v2 adopted position without surviving plan symbol=%s stop=%s",
            symbol,
            stop,
        )
        return self._v2_degrade_adoption(
            symbol,
            position,
            source="reconstructed",
            reason="no_durable_plan",
            at=at,
        )

    def _v2_degrade_adoption(
        self,
        symbol: str,
        position: PositionState,
        *,
        source: Literal["plan", "reconstructed", "none"],
        reason: str,
        at: str,
    ) -> PositionState:
        """Declara la adopción como no verificable y journaliza con atención alta."""
        degraded = replace(
            position,
            lifecycle_state="RECONCILIATION_REQUIRED",
            protection_state=protection_state_dict(
                "PROTECTION_MISSING", source=source, reason=reason, at=at
            ),
            updated_at=at,
        )
        self._journal_position_event(
            symbol,
            RECONCILIATION_REQUIRED,
            at=at,
            detail={
                "source": source,
                "reason": reason,
                "reasonCode": PROTECTION_MISSING,
                "stop": degraded.current_stop,
                "attention": "high",
            },
        )
        logger.warning(
            "auto_sim v2 adoption degraded symbol=%s source=%s reason=%s stop=%s",
            symbol,
            source,
            reason,
            degraded.current_stop,
        )
        return degraded

    def _v2_restore_durable_position(self, symbol: str, held: Decimal) -> PositionState | None:
        """Rehidrata el plan V2 persistido (una sola vez) para ``symbol``.

        Fail-closed: un blob que no rehidrata (o cuyo ``instrumentId`` no coincide) NO
        se usa; se descarta y el símbolo cae al camino de geometría reconstruida. La
        cantidad se ajusta a la posición REAL (el plan manda en el CÓMO salir, no en el
        CUÁNTO queda: eso es del ledger).
        """
        blob = self._v2_durable_plans.pop(symbol, None)
        if not blob:
            return None
        try:
            position = position_state_from_dict(blob)
        except Exception:  # noqa: BLE001 — un plan ilegible no puede tumbar el turno.
            logger.exception("auto_sim v2 durable plan unreadable symbol=%s", symbol)
            return None
        if position is None or position.instrument_id != symbol:
            logger.warning(
                "auto_sim v2 durable plan discarded symbol=%s instrument=%s",
                symbol,
                getattr(position, "instrument_id", None),
            )
            return None
        remaining = float(held)
        if remaining != position.remaining_quantity:
            # El ledger es la autoridad de cantidad: el plan se re-ancla a lo real
            # (el plan manda en el CÓMO salir; el CUÁNTO lo dicta el ledger).
            position = replace(
                position,
                remaining_quantity=remaining,
                quantity=max(float(position.quantity), remaining),
            )
        logger.info(
            "auto_sim v2 position restored from durable plan symbol=%s stop=%s status=%s",
            symbol,
            position.current_stop,
            position.status,
        )
        return position

    async def _v2_position_package(self, symbol: str, price: Decimal) -> DecisionPackage | None:
        """Intención de gestión de la posición abierta (PositionManager) o ``None``.

        Requiere un ``PositionState`` V2 vivo para el símbolo. Si no lo hay (posición
        readoptada tras un reinicio) se ADOPTA (degradada si el estado no es verificable)
        para no dejar la posición sin stop; solo si la adopción no es posible se devuelve
        ``None`` y la gestión cae a la política clásica (fail-safe).

        AUTO-2: además de la orden, esta función **aplica y persiste el ratchet de stop**
        (``stop_update`` de un ``PROTECT``) y journaliza el resultado. Antes el stop
        propuesto se descartaba y ``current_stop`` quedaba congelado en el valor de
        nacimiento: ni break-even ni trailing existían en AUTO.
        """
        position: PositionState | None = self._v2_positions.get(symbol)
        degraded = False
        if position is None:
            position = self._v2_adopt_position(symbol, price)
            if position is None:
                return None
            degraded = derive_lifecycle_state(position) in (
                "RECONCILIATION_REQUIRED",
                "PROTECTION_MISSING",
            )
            self._v2_positions[symbol] = position
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        policy = resolve_exit_policy(self._v2_tunables.exit_template)
        high = self._high_price.get(symbol)
        high_watermark = float(high) if high is not None and high > 0 else None
        armed = is_trail_armed(position)
        trail_stop = (
            compute_trail_stop(
                position,
                trail_width=policy.trail_width,
                high_watermark=high_watermark,
            )
            if armed
            else None
        )
        # V2.42 slice 2b (E3 · D2): la invalidación CONFIRMADA de la tesis se deriva aquí,
        # de hechos PERSISTIDOS (nivel congelado al nacer + peor adverso del MAE). No hay
        # LLM ni recómputo del motor de señales: un reinicio conserva la invalidación.
        thesis_invalid = is_thesis_invalidated(position, mark_price=float(price))
        # V2.44 — AUTO-3 slice 2: el gobernador entra en la gestión, no solo en la
        # entrada. ``RISK_OFF`` ⇒ ``RISK_EXIT`` (exit total), ``HALTED`` ⇒ ``KILL_SWITCH``,
        # con precedencia sobre objetivo/trailing/tiempo. Con el gobernador OFF los tres
        # valores son ``None`` y el manager se gobierna solo por el régimen de mercado.
        governor = self._v2_governor_position_inputs()
        outcome = plan_v2_position_outcome(
            position,
            mark_price=float(price),
            regime=self._v2_regime(),
            portfolio_recon_status=self._v2_recon_status(symbol),
            thesis_invalid=thesis_invalid,
            exit_template=self._v2_tunables.exit_template,
            # V2.42 slice 2b (E1): el techo CONGELADO en el nacimiento es el único
            # ``expires_at`` que la gestión ve; ``now`` es el instante del tick. Sin ambos,
            # ``TIME_STOP`` era inalcanzable por construcción (``expires_at`` ausente).
            now=at,
            expires_at=position.holding_deadline_at,
            # Sólo se declara TRAIL cuando hay un stop REAL que proponer: una alerta de
            # trailing sin stop sería journal ruidoso, no gestión.
            trail_hint=trail_stop is not None,
            trail_stop=trail_stop,
            at=at,
            risk_regime=governor["risk_regime"],
            drawdown_band=governor["drawdown_band"],
            operational_state=governor["operational_state"],
        )
        if isinstance(outcome, PositionManagerSkip):
            # AUTO-1A: la posición NO se pudo gestionar (mark rechazado / decisión no
            # construible). Antes el motivo se perdía y el libro de motivos del símbolo
            # quedaba vacío, indistinguible de "sin gestión pendiente".
            self._v2_last_exit_reasons[symbol] = (outcome.reason,)
            logger.warning(
                "auto_sim v2 position skip symbol=%s reason=%s detail=%s",
                symbol,
                outcome.reason,
                outcome.detail,
            )
            self._journal_position_event(
                symbol, outcome.reason, at=at, detail={"detail": outcome.detail}
            )
            return None
        self._v2_last_exit_reasons[symbol] = outcome.exit_reasons if outcome is not None else ()
        # V2.44 — AUTO-3 slice 2: si el motivo DECISORIO es un exit de gobernador
        # (``RISK_EXIT``/``REGIME_EXIT``/``KILL_SWITCH``) se journaliza como evento de
        # gestión propio, con el detalle de la decisión, para que el operador vea POR QUÉ
        # se liquidó (antes era una venta indistinguible de un stop o de un objetivo).
        if outcome is not None:
            primary = outcome.decision.primary_reason
            if primary == RISK_EXIT.upper():
                self._journal_position_event(
                    symbol,
                    RISK_EXIT,
                    at=at,
                    detail={
                        "primary_reason": primary,
                        "secondary_reasons": list(outcome.decision.secondary_reasons),
                        "risk_regime": governor["risk_regime"],
                        "drawdown_band": governor["drawdown_band"],
                        "operational_state": governor["operational_state"],
                    },
                )
            elif primary == KILL_SWITCH.upper():
                self._journal_position_event(
                    symbol,
                    KILL_SWITCH,
                    at=at,
                    detail={
                        "primary_reason": primary,
                        "secondary_reasons": list(outcome.decision.secondary_reasons),
                        "kill_switch_reason": self._v2_kill_switch.reason,
                        "operational_state": governor["operational_state"],
                    },
                )
        # V2.42 slice 2c: etiqueta del día del motivo DECISORIO (mismo criterio que el
        # journal rico: ``primary_reason``, no el flag). Con esto la fila ``position_close``
        # del día puede contar ``time_exit``/``thesis_exit`` sin reinterpretar nada.
        self._v2_last_exit_label[symbol] = (
            day_exit_reason(outcome.decision.primary_reason) if outcome is not None else ""
        )
        await self._v2_apply_stop_update(
            symbol,
            position,
            outcome,
            at=at,
            trailing_armed=armed,
            degraded=degraded,
        )
        await self._v2_journal_exit_request(
            symbol, position, outcome, at=at, thesis_invalid=thesis_invalid
        )
        return position_manager_package(outcome)

    async def _v2_journal_exit_request(
        self,
        symbol: str,
        position: PositionState,
        outcome: PositionManagerResult | None,
        *,
        at: str,
        thesis_invalid: bool,
    ) -> None:
        """V2.42 slice 2b (E1/E3): declara POR QUÉ se pidió salir y avanza el FSM.

        El spine ya emite la orden de venta; lo que faltaba era (a) que el FSM registrara
        ``TIME_EXIT``/``THESIS_EXIT`` (hasta ahora cualquier salida era indistinguible de
        un ``EXIT_REQUESTED`` genérico) y (b) que la invalidación de tesis tuviera una
        traza propia. Sin esto, una salida por tiempo o por tesis era invisible al operador.

        No vende nada aquí: la orden es del ``DecisionPackage`` que devuelve el llamante.
        """
        if outcome is None:
            return
        primary = outcome.decision.primary_reason
        if primary == "TIME_STOP":
            event, reason_code = "TIME_EXIT", TIME_EXIT
        elif primary == "THESIS_INVALIDATION":
            # La tesis es el motivo DECISORIO. Cuando quien decide es el stop estructural
            # (``THESIS_INVALIDATION`` es posterior en ``EXIT_REASON_PRECEDENCE``), el flag
            # viaja en el detalle como contexto pero NO se declara una salida por tesis:
            # si no, todo stop-out se leería además como invalidación y el porqué real de
            # la venta se perdería en el journal.
            event, reason_code = "THESIS_EXIT", THESIS_EXIT
        elif primary in (RISK_EXIT.upper(), "REGIME_EXIT", KILL_SWITCH.upper()):
            # V2.44 — los exits de gobernador también avanzan el FSM (``EXIT_PENDING``):
            # sin esto la posición quedaba ``OPEN`` mientras la orden de venta viajaba, y
            # un reinicio en mitad del exit no veía el estado de salida.
            event, reason_code = "EXIT_REQUESTED", primary.lower()
        else:
            return
        # Partimos de la posición VIVA (el ratchet pudo reescribir el JSONB): si se usara
        # la copia previa, el evento pisaría el stop recién ratcheado.
        current = self._v2_positions.get(symbol) or position
        advanced, transition = advance_lifecycle(current, event, at=at)
        # v2.88.28 — toda transición de protección lleva una ``revision_id`` durable para
        # derivar un ``dedupe_key`` determinista (antes esta salida pedida viajaba sin ella y
        # el hecho era duplicable). La identidad procede del cambio real del ``PositionState``.
        advanced, protection_revision_id = seal_protection_transition(
            current,
            advanced,
            kind=event,
            origin="protect",
            at=at,
            reason=event,
        )
        self._v2_positions[symbol] = advanced
        if not transition.accepted:
            self._journal_position_event(
                symbol,
                LIFECYCLE_TRANSITION_REJECTED,
                at=at,
                detail={"event": event, "from": transition.from_state},
            )
        self._journal_position_event(
            symbol,
            reason_code,
            at=at,
            detail={
                "primaryReason": primary,
                "lifecycle": transition.to_state,
                "deadline": current.holding_deadline_at,
                "invalidationPrice": current.invalidation_price,
                "thesisInvalid": thesis_invalid,
                "exitReasons": list(outcome.exit_reasons),
            },
        )
        # v2.88.26 — HECHO durable de la salida pedida (cierra ``protection_not_durable``
        # cuando el primer hecho de protección de un ciclo es la salida). La transición se
        # sella tal cual la aceptó el FSM; sin ``cycle_id`` el builder no finge el hecho.
        await self._v2_journal_protection(
            kind=event,
            instrument_id=symbol,
            cycle_id=advanced.cycle_id or current.cycle_id,
            position_id=advanced.position_id,
            lifecycle_from=transition.from_state,
            lifecycle_to=transition.to_state,
            stop_before=current.current_stop,
            stop_after=advanced.current_stop,
            trailing_status=trailing_status(advanced),
            revision_id=protection_revision_id,
            source=None,
        )

    async def _v2_apply_stop_update(
        self,
        symbol: str,
        position: PositionState,
        outcome: PositionManagerResult | None,
        *,
        at: str,
        trailing_armed: bool,
        degraded: bool,
    ) -> None:
        """Aplica el ``stop_update`` de la gestión (monotonía H2) y lo persiste.

        Un ratchet NO vende: aunque no haya orden, el stop nuevo debe quedar persistido
        (si no, el próximo tick parte del stop viejo y la protección no existe). Todo
        desenlace se journaliza: aplicado, rechazado por empeorar, o pedido sin efecto.
        Nunca un ``PROTECT`` mudo.
        """
        proposed = position_manager_stop_update(outcome)
        # La base es la posición MARCADA del outcome (``apply_position_mark`` actualizó el
        # extremo favorable y ``mfe_mae``): si se partiera de la copia sin marcar, el pico
        # del JSONB se quedaría congelado y el trailing no tendría memoria propia.
        marked = getattr(outcome, "position", None)
        current = (
            marked
            if isinstance(marked, PositionState)
            else (self._v2_positions.get(symbol) or position)
        )
        # La MARCA del tick (pico observado + MFE/MAE) es un cambio de estado REAL aunque
        # no mueva el stop. Antes se quedaba dentro de la copia del outcome y se perdía:
        # el ancla del trailing y la memoria del peor adverso (de la que depende la
        # invalidación de tesis, E3) volvían al valor del último fill/ratchet — y un
        # reinicio las perdía del todo. Sólo se escribe cuando la observación cambia de
        # verdad (un extremo nuevo), no en cada tick.
        if isinstance(marked, PositionState) and _mark_observation_changed(
            self._v2_positions.get(symbol), marked
        ):
            self._v2_positions[symbol] = marked
            held = self._open.get(symbol, Decimal("0"))
            if held > 0:
                await self._persist_position(symbol, held)
        if proposed is None:
            # Los motivos del spine van en minúscula (``decision.primary_reason.lower()``).
            if outcome is not None and "trail" in {r.lower() for r in outcome.exit_reasons}:
                # Hubo intención de proteger y no produjo stop utilizable: se declara.
                self._journal_position_event(
                    symbol,
                    PROTECT_REQUESTED,
                    at=at,
                    detail={"exitReasons": list(outcome.exit_reasons)},
                )
                # v2.88.26 — el pedido sin efecto también es un HECHO durable de protección
                # (``PROTECT_REQUESTED``): sin esto, "se intentó proteger y no se pudo"
                # quedaría mudo en el monitor.
                # v2.88.28 — el hecho lleva identidad determinista (contenido) para que un
                # reintento del mismo tick no lo duplique.
                _, protection_revision_id = seal_protection_transition(
                    current,
                    current,
                    kind=PROTECT_REQUESTED,
                    origin="protect",
                    at=at,
                    reason=PROTECT_REQUESTED,
                )
                await self._v2_journal_protection(
                    kind=PROTECT_REQUESTED,
                    instrument_id=symbol,
                    cycle_id=current.cycle_id,
                    position_id=current.position_id,
                    lifecycle_from=current.lifecycle_state,
                    lifecycle_to=current.lifecycle_state,
                    stop_before=current.current_stop,
                    stop_after=current.current_stop,
                    trailing_status=trailing_status(current),
                    revision_id=protection_revision_id,
                    source=None,
                )
            return
        before = current.current_stop
        updated = apply_position_current_stop(
            current,
            proposed,
            at=at,
            origin="trail" if trailing_armed else "protect",
            reason="auto_v2_ratchet",
        )
        if updated is None:
            # H2: el stop propuesto empeoraba el vigente y no hay override auditado.
            self._journal_position_event(
                symbol,
                STOP_RATCHET_REJECTED,
                at=at,
                detail={"proposed": proposed, "current": before},
            )
            return
        event = "TRAIL_ADVANCED" if trailing_armed else "PROTECT_APPLIED"
        advanced, transition = advance_lifecycle(
            updated,
            event,
            at=at,
            mark_trailing=trailing_armed,
        )
        if not transition.accepted:
            # El estado vivo (o su proyección) no admite la transición: se declara y el
            # stop SÍ se conserva (la aplicación del stop no depende del FSM).
            self._journal_position_event(
                symbol,
                LIFECYCLE_TRANSITION_REJECTED,
                at=at,
                detail={"event": event, "from": transition.from_state},
            )
            advanced = updated
        self._v2_positions[symbol] = advanced
        changed = before != advanced.current_stop
        if changed:
            # v2.88.28 — se sella ANTES de persistir para que la revisión determinista del
            # movimiento viaje en el mismo ``position_state`` durable.
            advanced, protection_revision_id = seal_protection_transition(
                current,
                advanced,
                kind=event if transition.accepted else STOP_RATCHET_APPLIED,
                origin="trail" if trailing_armed else "protect",
                at=at,
                reason="auto_v2_ratchet",
            )
            self._v2_positions[symbol] = advanced
            held = self._open.get(symbol, Decimal("0"))
            if held > 0:
                await self._persist_position(symbol, held)
            self._journal_position_event(
                symbol,
                STOP_RATCHET_APPLIED,
                at=at,
                detail={
                    "from": before,
                    "to": advanced.current_stop,
                    "lifecycle": advanced.lifecycle_state,
                    "trailing": trailing_status(advanced),
                    "degraded": degraded,
                },
            )
            # v2.88.26 — HECHO durable del movimiento del stop. ``kind`` es la transición FSM
            # aceptada (``PROTECT_APPLIED``/``TRAIL_ADVANCED``); si el FSM la rechazó pero el
            # stop SÍ se movió, el hecho es el ratchet desnudo (``STOP_RATCHET_APPLIED``).
            revision = advanced.revisions[-1] if advanced.revisions else None
            await self._v2_journal_protection(
                kind=event if transition.accepted else STOP_RATCHET_APPLIED,
                instrument_id=symbol,
                cycle_id=advanced.cycle_id or current.cycle_id,
                position_id=advanced.position_id,
                lifecycle_from=transition.from_state,
                lifecycle_to=advanced.lifecycle_state,
                stop_before=before,
                stop_after=advanced.current_stop,
                trailing_status=trailing_status(advanced),
                revision_id=protection_revision_id,
                source=revision.origin if revision else None,
            )
        else:
            # Idempotente: el stop no cambia, pero la transición sí puede haber ocurrido.
            if advanced.lifecycle_state != current.lifecycle_state:
                # v2.88.28 — la transición FSM sin mover el stop también añade su revisión
                # determinista y se persiste, para que el hecho durable tenga identidad.
                advanced, protection_revision_id = seal_protection_transition(
                    current,
                    advanced,
                    kind=PROTECT_REQUESTED,
                    origin="protect",
                    at=at,
                    reason=PROTECT_REQUESTED,
                )
                self._v2_positions[symbol] = advanced
                held = self._open.get(symbol, Decimal("0"))
                if held > 0:
                    await self._persist_position(symbol, held)
                self._journal_position_event(
                    symbol,
                    PROTECT_REQUESTED,
                    at=at,
                    detail={
                        "stop": advanced.current_stop,
                        "lifecycle": advanced.lifecycle_state,
                    },
                )
                self._v2_protect_noop_stop.pop(symbol, None)
                # v2.88.26 — la transición FSM ocurrió sin mover el stop (break-even ya
                # alcanzado): es un hecho de protección durable, no un no-op mudo.
                await self._v2_journal_protection(
                    kind=PROTECT_REQUESTED,
                    instrument_id=symbol,
                    cycle_id=advanced.cycle_id or current.cycle_id,
                    position_id=advanced.position_id,
                    lifecycle_from=current.lifecycle_state,
                    lifecycle_to=advanced.lifecycle_state,
                    stop_before=before,
                    stop_after=advanced.current_stop,
                    trailing_status=trailing_status(advanced),
                    revision_id=protection_revision_id,
                    source=None,
                )
            elif advanced.current_stop is not None:
                # H-2: el stop ya estaba aplicado y el estado no cambió. Antes esto era
                # MUDO; ahora se declara UNA vez por stop (el journal no se inunda con un
                # trailing en régimen permanente, pero el tick nunca es un no-op invisible).
                if self._v2_protect_noop_stop.get(symbol) != advanced.current_stop:
                    self._v2_protect_noop_stop[symbol] = advanced.current_stop
                    self._journal_position_event(
                        symbol,
                        PROTECT_REQUESTED,
                        at=at,
                        detail={
                            "stop": advanced.current_stop,
                            "lifecycle": advanced.lifecycle_state,
                            "idempotent": True,
                            "reason": "stop_already_applied",
                        },
                    )

    def _journal_position_event(
        self,
        symbol: str,
        reason_code: str,
        *,
        at: str,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        """Journal de gestión de posición: registro rico + fila observable del día.

        El registro rico (``DecisionJournalEntryRecord``) conserva el detalle; la fila
        (``SimJournalRow``) es la que el día AUTO agrega de verdad. Sin la fila, el
        motivo quedaría en una lista que nadie consume (mudo a efectos de auditoría).
        """
        entry = build_position_management_journal_entry(
            instrument_id=symbol,
            reason_code=reason_code,
            actor=self._engine_id,
            as_of=at,
            detail=detail,
            # V2.45/AUTO-5 — la gestión de la posición se atribuye a la estrategia que la
            # abrió (aditivo en el payload).
            strategy_version=self._position_version.get(symbol),
        )
        self._v2_journal.append(entry)
        try:
            self._emit(
                "position_management",
                self._venue(),
                f"{reason_code}:{symbol}",
                "hold",
                Decimal("0"),
                # El motivo también viaja en la fila del día: es la traza del evento de
                # gestión (``time_exit``, ``protect_requested``, ...).
                reason=reason_code,
            )
        except Exception:  # noqa: BLE001 — journalizar nunca tumba el turno.
            logger.exception("auto_sim position journal emit failed symbol=%s", symbol)

    async def _v2_track_entry(self, symbol: str, price: Decimal, qty: Decimal) -> None:
        """Crea el ``PositionState`` V2 al abrir (desde el TradePlan que lo originó).

        AUTO-2: la entrada se registra como TRANSICIÓN del FSM
        (``ENTRY_PENDING`` → ``ENTRY_FILLED`` → ``OPEN``) y la protección se declara
        ``ACTIVE`` con ``source=plan``: el plan aporta el stop estructural. La
        persistencia la hace el llamante (``_persist_position``) en el mismo tick.

        v2.88.26 — además se sella el HECHO durable de protección del nacimiento
        (``PROTECT_APPLIED``): sin él, ``PROTECTION`` no tendría traza append-only hasta la
        primera gestión y el monitor lo declararía ``protection_not_durable``.
        """
        plan = getattr(self._v2_plan, "decisions", ()) if self._v2_plan else ()
        trade_plan_dict: dict[str, object] | None = None
        for decision in plan:
            if decision.instrument_id != symbol or decision.trade_plan is None:
                continue
            trade_plan_dict = dict(decision.trade_plan.to_dict())
            break
        if trade_plan_dict is None:
            return
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        position = build_position_state_from_fill(
            trade_plan_dict,
            fill_price=float(price),
            fill_quantity=float(qty),
            filled_at=at,
            # V2.42 slice 2b (E1): el techo de mantenimiento se congela AQUÍ, en el
            # nacimiento, desde la plantilla de salida vigente. Sin esto el plan de salida
            # nunca recibía ``expires_at`` y ``TIME_STOP`` era inalcanzable (una posición
            # de swing podía vivir indefinidamente).
            max_holding_period_days=resolve_holding_horizon(
                self._v2_tunables.exit_template
            ).max_holding_period_days,
            # V2.47: el ciclo se CONGELA en el nacimiento y viaja en el JSONB de la
            # posición, de modo que su salida y su PnL lo heredan.
            cycle_id=self._v2_cycle_for(symbol),
        )
        if position is None:
            return
        pending = replace(
            position,
            lifecycle_state="ENTRY_PENDING",
            protection_state=protection_state_dict("ACTIVE", source="plan", at=at),
        )
        entered, transition = advance_lifecycle(pending, "ENTRY_FILLED", at=at)
        if not transition.accepted:
            # Imposible en la tabla vigente; si el FSM cambiara, la entrada NO se pierde:
            # se declara y se conserva el estado nacido del fill.
            self._journal_position_event(
                symbol,
                LIFECYCLE_TRANSITION_REJECTED,
                at=at,
                detail={"event": "ENTRY_FILLED", "from": transition.from_state},
            )
            entered = replace(entered, lifecycle_state="OPEN")
        # v2.88.28 — el nacimiento de la protección es una TRANSICIÓN: se le añade su
        # revisión durable determinista para que el hecho ``PROTECT_APPLIED`` tenga
        # identidad (antes viajaba sin ``revision_id`` ⇒ clave ``None`` ⇒ duplicable).
        entered, protection_revision_id = seal_protection_transition(
            pending,
            entered,
            kind="PROTECT_APPLIED",
            origin="protect",
            at=at,
            reason="plan",
        )
        self._v2_positions[symbol] = entered
        # v2.88.26 — HECHO durable del nacimiento de la protección (``source=plan``: el stop
        # estructural del plan). La traza copia el estado que ya produjo el FSM; no lo deriva.
        await self._v2_journal_protection(
            kind="PROTECT_APPLIED",
            instrument_id=symbol,
            cycle_id=entered.cycle_id,
            position_id=entered.position_id,
            lifecycle_from=pending.lifecycle_state,
            lifecycle_to=entered.lifecycle_state,
            stop_before=pending.current_stop,
            stop_after=entered.current_stop,
            trailing_status=trailing_status(entered),
            revision_id=protection_revision_id,
            source="plan",
        )

    async def _v2_track_reduce(
        self,
        symbol: str,
        qty: Decimal,
        price: Decimal,
        exit_reasons: tuple[str, ...],
    ) -> None:
        """Actualiza el ``PositionState`` V2 tras un fill de venta (parcial o total).

        AUTO-2: emite las TRANSICIONES que el fill verifica (``T1_HIT``/``PARTIAL_FILL``/
        ``EXIT_FILLED``) en vez de dejar el FSM congelado en el estado de nacimiento.

        v2.88.26 — además sella los HECHOS durables de PROTECCIÓN: ``T1_HIT``/``T2_HIT``
        (objetivo alcanzado) y ``TRAIL_ARMED`` (el T1 arma el trailing). La traza copia la
        transición que ya produjo el FSM; no la re-deriva.
        """
        position: PositionState | None = self._v2_positions.get(symbol)
        if position is None:
            return
        reduced = apply_position_reduce(
            position,
            float(qty),
            exit_price=float(price),
            reason=",".join(exit_reasons) or None,
            mark_target1_achieved="target_1" in exit_reasons,
            mark_target2_achieved="target_2" in exit_reasons,
        )
        if reduced is None:
            return
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        events: list[str] = []
        if "target_1" in exit_reasons:
            events.append("T1_HIT")
        if reduced.status == "CLOSED":
            events.append("EXIT_FILLED")
        elif reduced.remaining_quantity < reduced.quantity:
            events.append("PARTIAL_FILL")
        advanced = reduced
        for event in events:
            advanced, transition = advance_lifecycle(
                advanced,
                event,
                at=at,
                # T1 es lo que ARMA el trailing (misma regla que el motor legacy): el
                # estado persistido lo declara para que el reinicio no lo re-derive.
                mark_trailing="target_1" in exit_reasons,
            )
            if not transition.accepted:
                self._journal_position_event(
                    symbol,
                    LIFECYCLE_TRANSITION_REJECTED,
                    at=at,
                    detail={"event": event, "from": transition.from_state},
                )
        # v2.88.26 — HECHOS durables de objetivo/armado. ``T1_HIT``/``T2_HIT`` declaran el
        # objetivo alcanzado; ``TRAIL_ARMED`` declara que el T1 armó el trailing. El
        # ``cycle_id`` se captura ANTES del posible ``pop`` de una posición cerrada.
        protection_events: list[tuple[str, int | None]] = []
        if "target_1" in exit_reasons:
            protection_events.append(("T1_HIT", 1))
        if "target_2" in exit_reasons:
            protection_events.append(("T2_HIT", 2))
        if "target_1" in exit_reasons:
            protection_events.append(("TRAIL_ARMED", 1))
        # v2.88.28 — se sella UNA revisión durable para la transición del fill y se comparte
        # como ``revision_id`` de sus hechos (T1/T2/armado). Las claves de deduplicación
        # difieren por ``kind``; el cambio durable referenciado es el mismo.
        protection_revision_id: str | None = None
        if protection_events:
            advanced, protection_revision_id = seal_protection_transition(
                position,
                advanced,
                kind=protection_events[0][0],
                origin=(
                    "trail"
                    if any(kind in ("TRAIL_ARMED", "TRAIL_ADVANCED") for kind, _ in protection_events)
                    else "protect"
                ),
                at=at,
                reason=",".join(exit_reasons) or None,
            )
        for kind, target in protection_events:
            await self._v2_journal_protection(
                kind=kind,
                instrument_id=symbol,
                cycle_id=advanced.cycle_id or position.cycle_id,
                position_id=advanced.position_id,
                lifecycle_from=position.lifecycle_state,
                lifecycle_to=advanced.lifecycle_state,
                stop_before=position.current_stop,
                stop_after=advanced.current_stop,
                target=target,
                trailing_status=trailing_status(advanced),
                revision_id=protection_revision_id,
                source=None,
            )
        if advanced.status == "CLOSED":
            self._v2_positions.pop(symbol, None)
        else:
            self._v2_positions[symbol] = advanced

    # ---- UN turno (decide + liquida SIM + actualiza el libro) ------------------
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
                    v2_pkg = await self._v2_position_package(symbol, price)
                    reasons.extend(self._v2_last_exit_reasons.get(symbol, ()))
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
            qty = Decimal(str(getattr(pkg, "quantity", None) or 0)).quantize(Decimal("0.000001"))
            if qty <= 0:
                _veto("non_positive_qty")
                continue
            # 1) Simulation Gate (kill fail-closed ANTES de nada AUTO).
            if kill:
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
            if action == "BUY" and self._openings_vetoed(symbol):
                _veto("position_reconciliation_not_ok")
                continue
            if action == "BUY" and self._book_equity_unreadable:
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
            self._emit("order", venue, None, action.lower(), exec_qty)
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
                )
            for o in settlement.applied:
                self._emit("fill", o.venue, o.execution_id, o.side, o.qty)
                self._record_applied_event(symbol, o, price)
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
                    self._sim_realized_pnl += (price - entry_ref) * applied_qty
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
                        price,
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
                    )
            report.orders += 1
            report.fills += len(settlement.applied)
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

    # ---- durable (M4) ----------------------------------------------------------
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

    # ---- V2.23/A9 (Bloque 2): turno REAL contra stores de una sesión por tick.
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
                seq = (snap.ticks + 1) if snap is not None else 1
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
            self._v2_bar_short_circuit = prev_bar_short_circuit


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
    # acepta resolver síncrono o asíncrono (durable).
    applier = build_simulated_execute_trade_applier(trade, resolver)
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


#: v2.88.27 — ventana de lectura con la que el arranque confirma qué ciclos ya tienen su
#: ``SETTLEMENT`` durable. Es una LECTURA de deduplicación: si la ventana se quedara corta, el
#: peor caso es reemitir un hecho que YA existe, y la identidad determinista lo vuelve un no-op.
_DURABLE_FACTS_READ_WINDOW = 500

#: v2.88.27 — tope de ciclos recientes que el arranque examina para recuperar un ``SETTLEMENT``
#: que un crash dejó sin publicar. La ventana acota el trabajo de arranque; el ciclo que quede
#: fuera no se pierde: su ``SETTLEMENT`` se sellará igualmente al reabrir ese ciclo (o en el
#: siguiente arranque), y mientras tanto el monitor lo declara ``settlement_not_durable``.
_DURABLE_FACTS_RECOVERY_CYCLES = 200


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
        read_applied_fill_facts,
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


async def load_active_strategy_decider(
    session_factory: Any,
    *,
    instrument_id: str,
    watch: Sequence[str],
    lot_qty: float = 100.0,
    ohlcv: Any = None,
    signal_enabled: bool = False,
    as_of: Any = None,
) -> DecisionProvider | None:
    """Carga la estrategia ACTIVE del store y la expone vía ``DecisionProvider``.

    V2.26/A10: éste es el ÚNICO punto por el que la estrategia promovida entra en el
    hot path del AUTO. Si no hay estrategia activa, o falla la lectura, devuelve
    ``None`` y el worker sigue con el spine determinista (comportamiento previo a
    V2.31, válido cuando la señal de la ACTIVE está deshabilitada).

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
    """
    if not active_strategy_enabled():
        return None
    try:
        from bolsa_application.auto_orchestrator import active_strategy_decider
        from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

        async with session_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
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
                    instrument_id=instrument_id,
                    as_of=as_of,
                )

        return active_strategy_decider(
            active=record.active,
            fallback=None,
            watch=watch,
            lot_qty=lot_qty,
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
    limit = _signal_snapshot_limit()
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
    )


async def auto_sim_loop(
    runtime: AutoSimRuntime,
    *,
    interval_seconds: float = 60.0,
    decider_refresher: Any = None,
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
    """
    logger.info("AutoSimulationWorker (SIM-ONLY) loop iniciado (tick=%ss)", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        if not sim_worker_enabled():
            continue
        if decider_refresher is not None:
            try:
                refreshed = await decider_refresher()
                if refreshed is not None:
                    runtime.set_decider(refreshed)
            except Exception:  # noqa: BLE001 — un refresh fallido no tumba el loop.
                logger.exception("auto_sim decider refresh failed")
        try:
            await runtime.run_tick()
        except Exception:  # noqa: BLE001 — un turno no debe tumbar el loop.
            logger.exception("auto_sim tick failed")


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
            worker = AutoSimulationWorker(
                decider=decider,
                engine_id=engine_id,
                account_id=account_id,
                require_account_id=True,
                regime_source=regime_source,
                liquidity_source=liquidity_source,
                trade_context_source=trade_context_source,
                edge_source=edge_source,
                evidence_source=evidence_source,
                atr_source=atr_source,
                price_source=price_source,
            )
        self._worker = worker

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

    async def run_tick(self) -> TurnReport | None:
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
            # durable de «qué activos considera AUTO y por qué», sobre la MISMA sesión del tick.
            # Cierra el hueco de ``v2.88.82`` (cadena probada pero sin productor cableado).
            top3_opportunity_sink = build_top3_opportunity_sink(session)
            # v2.88.70: la equity del turno es la del libro. Si falla, las aperturas
            # quedan vetadas dentro de ``auto_turn``. No se sustituye por 100_000.
            await self._worker.load_book_equity(session)
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
            )


class _HermeticRuntime:
    """Adapter para un ``worker`` inyectado sin PG (uso en tests/hermético)."""

    def __init__(self, worker: AutoSimulationWorker) -> None:
        self._worker = worker

    async def run_tick(self) -> None:
        await self._worker.auto_turn()


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
    lot = float(os.getenv("AUTO_ENGINE_SIM_LOT_QTY") or "100.0")
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
) -> asyncio.Task[None] | None:
    """start hook para ``_event_loop_starters()`` (env-gated; default OFF, SIM).

    V2.22 bug (P1-01): arrancaba ``AutoSimulationWorker()`` desnudo (sin exec_store/
    auto_store/decider/finance) y el camino autónomo real nunca liquidaba. V2.23
    (Bloque 2): con ``session_factory`` compone un ``AutoSimRuntime`` real con
    ``PostgresExecutionEventStore``/``AutoEngineStore``/finanzas SIM por sesión.
    El decider por defecto es el Spine determinista (Bloque 4), seguro (HOLD a menos
    que ``AUTO_ENGINE_SIM_SPINE_AUTO=1``). Sin ``session_factory`` (uso unit/hermético)
    permite seguir con un ``worker`` inyectado (p.ej. con ``InMemoryExecutionEventStore``).
    """
    if not sim_worker_enabled():
        logger.info(
            "AutoSimulationWorker (%s) desactivado — SIM-ONLY por defecto.", AUTO_SIM_WORKER_ENABLED
        )
        return None
    runtime: Any
    # V2.26/A10: refresco opcional del decider desde la estrategia ACTIVE (env-gated).
    decider_refresher: Any = None
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
        runtime = AutoSimRuntime(
            session_factory,
            worker=worker,
            decider=decider if decider is not None else _default_spine_decider(),
            engine_id=engine_id or _sim_engine_id(),
            account_id=effective_account,
            finance_resolver=finance_resolver,
            regime_source=regime_source,
            trade_context_source=trade_context_source,
            edge_source=edge_source,
            liquidity_source=liquidity_source,
            evidence_source=evidence_source,
        )
        # V2.26/A10: solo con runtime PG real y sin decider inyectado; el seam es el
        # ``DecisionProvider`` (no se toca RiskGate/SimulationGate ni se abre LIVE).
        if decider is None and active_strategy_enabled():
            spine_watch = tuple(
                s.strip()
                for s in (os.getenv("AUTO_ENGINE_SIM_WATCH") or "").split(",")
                if s.strip()
            )

            async def _refresh_active_decider() -> DecisionProvider | None:
                return await load_active_strategy_decider(
                    session_factory,
                    instrument_id=effective_account,
                    watch=spine_watch,
                    signal_enabled=active_strategy_signal_enabled(),
                    # W3: la señal se evalúa con las barras CERRADAS hasta la barra anterior
                    # (provider sobre el reloj del worker: el refresco es previo al turno,
                    # así que la frontera va como mínimo un tick por detrás del reloj vivo
                    # — estrictamente conservador, jamás por delante).
                    as_of=runtime.worker._v2_closed_bar_as_of,  # noqa: SLF001 — seam interno.
                )

            decider_refresher = _refresh_active_decider
    return asyncio.create_task(
        auto_sim_loop(
            runtime,
            interval_seconds=_sim_interval_seconds(interval_seconds),
            decider_refresher=decider_refresher,
        )
    )


def _sim_interval_seconds(default: float = 60.0) -> float:
    """Intervalo del loop AUTO (env ``AUTO_ENGINE_SIM_INTERVAL_SECONDS``; default 60s).

    V2.24/A9.1 (P2-04): parametrizable para que la prueba Reina pueda arrancar el
    scheduler real sin esperar minutos. Valor inválido ⇒ default seguro.
    """
    raw = (os.getenv("AUTO_ENGINE_SIM_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default
