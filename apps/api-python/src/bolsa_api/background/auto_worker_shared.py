"""Piezas compartidas del worker AUTO (precio/coste, estado durable, DTOs, helpers).

Extraido de ``auto_simulation_worker`` con ``Delta motor = 0``: cada funcion, constante
y dataclass conserva su cuerpo identico; solo cambia de modulo.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.open_order import (
    OpenOrder,
    build_open_order,
)
from bolsa_analytics.cognitive.position_ledger import (
    build_position_ledger,
    coerce_applied_fill_fact,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    high_watermark_from_position,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
)
from bolsa_application.auto_engine_state_store import (
    AutoActivity,
)
from bolsa_application.flags import env_finite_float, env_flag
from bolsa_application.protection_compat import (
    ProtectionPolicy,
)

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.

logger = logging.getLogger("bolsa_api.background.auto_simulation_worker")

#: Medición 2026-10-23 — combinaciones (cuenta, motor) cuyo enlace de espejos ya se declaró.
#: La declaración es de PROCESO (una vez por binomio): un espejo ausente se grita una vez, no
#: en cada tick.
_MIRRORS_DECLARED: set[tuple[str, str]] = set()


def _declare_effective_mirrors(
    *,
    account_id: str | None,
    engine_id: str | None,
    mirrors: Sequence[tuple[str, Any]],
) -> None:
    """Declara UNA vez qué store quedó en cada espejo durable y si falta alguno.

    Nace de un hecho medido el 2026-10-21/23: dos salidas se emitieron con su identidad
    (``{engine}-sell-{symbol}-{exit_order_id}``) y **sin fila en ``auto_exit_orders``**, sin un
    solo log que lo dijera. ``_v2_save_exit_order`` devuelve ``False`` cuando el store no está
    y el llamante no comprueba el retorno, así que la ausencia del espejo era invisible.

    El nivel no es cosmético: ``alembic.ini`` fija el root logger en ``WARN`` al migrar
    (``fileConfig`` desde ``ensure_migrated``), de modo que un ``logger.info`` aquí **no se ve**
    justo en la ruta de la ventana. Por eso grita en ``WARNING`` cuando falta un espejo y se
    queda en ``INFO`` (silencioso) cuando están todos: la anomalía se ve, el día normal no
    ensucia el log.
    """
    key = (str(account_id or ""), str(engine_id or ""))
    if key in _MIRRORS_DECLARED:
        return
    _MIRRORS_DECLARED.add(key)
    missing = [name for name, store in mirrors if store is None]
    logger.log(
        logging.WARNING if missing else logging.INFO,
        "auto_sim v2 espejos account=%s engine=%s %s%s",
        key[0] or "-",
        key[1] or "-",
        " ".join(f"{name}={type(store).__name__}" for name, store in mirrors),
        f" FALTAN={','.join(missing)}" if missing else "",
    )


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

# W-159-2 (Hueco B) — holgura mínima entre el stop de una posición LARGA y el precio de
# mercado. Un stop reconstruido que nace por encima (o pegado) al mercado no es protección:
# es una liquidación programada en el mismo tick de la adopción (medido 2026-10-21).
_ADOPTION_MIN_STOP_GAP = Decimal("0.002")

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
        fill for fill in fills if str(getattr(fill, "side", "") or "").strip().lower() == "sell"
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
    """Env de habilitación (default OFF) del worker SIM-ONLY de A9/M5.

    P1 (auditoría .183): lista blanca. ``disabled``/``n``/``of`` ya NO encienden AUTO;
    un valor desconocido deja el default OFF y avisa con el valor crudo.
    """
    return env_flag(AUTO_SIM_WORKER_ENABLED, default=False)


#: W4 (v2.88.17): interruptor DECLARADO del precio REAL. Default **OFF** ⇒ el runtime conserva
#: el ``price_script`` hermético (``Δ = 0`` y todos los tests PG en verde, que es como se selló
#: el tramo ``W3.x``). Activarlo es un acto **explícito** y es lo que mide el criterio de éxito
#: de ``W4`` (que el camino de PRODUCCIÓN/PAPER deje de fabricar un precio):
#: ``AUTO_ENGINE_SIM_REAL_PRICE=1``.
AUTO_REAL_PRICE_ENV = "AUTO_ENGINE_SIM_REAL_PRICE"


def real_price_enabled() -> bool:
    """¿Está habilitado el proveedor de precio REAL? (default OFF = costura inerte).

    P1 (auditoría .183): lista blanca, igual que ``sim_worker_enabled``. Que un valor
    basura encienda el precio real era el peor caso del fail-open: cambia de dónde sale
    el precio de ejecución.
    """
    return env_flag(AUTO_REAL_PRICE_ENV, default=False)


# ── Base de coste de una ADOPCIÓN (W-159-2 · C-4) ───────────────────────────────
#: Fuente del coste con el que se reconstruye la geometría de una posición adoptada.
#: Viaja al journal durable (``entrySource``) para que un stop imposible sea depurable
#: a posteriori sin reinterpretar nada.
ADOPTION_COST_SOURCE_LEDGER = "ledger"
ADOPTION_COST_SOURCE_PROJECTION = "projection"
#: C-4 — el libro es AMBIGUO (dos motores vivos) y se usa el espejo de ESTE motor.
ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER = "projection_ambiguous_ledger"
#: C-4 — el libro es ambiguo y no hay espejo: no se autoriza ningún coste.
ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS = "ledger_ambiguous"
ADOPTION_COST_SOURCE_NONE = "none"


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

#: M6: tope de eventos de gestión de posición pendientes de reintento (cola acotada).
_POSITION_JOURNAL_RETRY_CAP = 500

#: M8 (auditoría .183) — espejos DURABLES que hacen honesto un turno OPERATIVO.
#:
#: Sin ellos el estado vive sólo en RAM y el motor puede operar con media cartera
#: olvidada: la parada dura, la posición, el compromiso de capital y el libro financiero
#: desaparecen en el siguiente reinicio. El camino hermético (tests, replay) los deja
#: fuera a propósito; el runtime real los compone por sesión y declara
#: ``require_durable_stores=True``, de modo que un turno al que le falte uno se RECHAZA
#: en vez de operar a medias.
OPERATIVE_DURABLE_SEAMS: tuple[str, ...] = (
    "exec_store",
    "auto_store",
    "finance_applier",
    "position_store",
    "reservation_store",
    "kill_switch_store",
)

#: Motivo declarado (``declare_skip``) cuando el turno operativo no tiene sus espejos.
DURABLE_STORES_MISSING = "durable_stores_missing"

#: M10 — motivo declarado cuando una intención durable ``OFF`` impide conducir el turno.
OPERATOR_INTENT_OFF = "operator_intent_off"

#: M10 — la intención no se pudo LEER: no hay permiso declarado, así que no se opera.
OPERATOR_INTENT_UNREADABLE = "operator_intent_unreadable"

#: M7 (auditoría .183) — el CONTROL PLANE (universo del watch o estrategia ACTIVE) dejó
#: de refrescarse. El proceso sigue vivo y conserva el último dato válido, así que no se
#: detiene —un cierre reduce riesgo y debe seguir siendo posible—, pero NINGUNA apertura
#: se autoriza: elegir un instrumento con un universo caducado es inventar una
#: oportunidad que este proceso no vio.
CONTROL_PLANE_STALE = "control_plane_stale"

#: M7 — tokens concretos de frescura. Cada uno se levanta cuando su refresco vuelve a
#: funcionar; el veto de aperturas sólo depende de que la lista no esté vacía.
WATCH_REFRESH_FAILED = "watch_refresh_failed"
DECIDER_REFRESH_FAILED = "decider_refresh_failed"
TICK_FAILED = "tick_failed"
CIRCUIT_BREAKER_PAUSED = "circuit_breaker_paused"

#: M7 — fallos CONSECUTIVOS del turno que abren el breaker a ``PAUSED``. ``0`` lo
#: desactiva (queda el backoff). Un turno que revienta no es «un turno sin actividad»:
#: si se repite, el motor deja de ser fiable y se PAUSA en vez de reintentar a ciegas.
AUTO_SIM_TICK_BREAKER_FAILURES = "AUTO_SIM_TICK_BREAKER_FAILURES"

#: M7 — tope del backoff exponencial entre reintentos (segundos).
AUTO_SIM_BACKOFF_MAX_SECONDS = "AUTO_SIM_BACKOFF_MAX_SECONDS"


def auto_sim_breaker_failures() -> int:
    """M7 — umbral de fallos consecutivos del breaker (default 3; ``0`` = sin breaker).

    Se valida como finito antes de convertir (un ``inf`` de entorno reventaría en
    ``int``) y un valor ilegible cae al default: la protección no depende de que la
    configuración sea correcta.
    """
    value = env_finite_float(AUTO_SIM_TICK_BREAKER_FAILURES, default=None)
    if value is None:
        return 3
    try:
        return max(0, int(value))
    except (OverflowError, ValueError):  # pragma: no cover — ``env_finite_float`` ya filtra.
        return 3


def auto_sim_backoff_seconds(
    base: float,
    failures: int,
    *,
    cap: float | None = None,
) -> float:
    """M7 — espera antes del siguiente intento tras ``failures`` fallos consecutivos.

    Sin fallos se respeta el intervalo configurado (Δ = 0 respecto del loop histórico).
    Con fallos, el intervalo se duplica por fallo hasta el tope: un motor que sólo falla
    deja de martillear la BD cada 60 s, pero sigue reintentando (el breaker es el que
    detiene del todo). La exponenciación va acotada por el tope ANTES de multiplicar para
    que ``2 ** 10**9`` no sea un número que haya que calcular.
    """
    intervalo = max(0.0, float(base))
    if failures <= 0:
        return intervalo
    techo: float = float(cap) if cap is not None else _auto_sim_backoff_cap()
    techo = max(intervalo, techo)
    factor: int = 2 ** min(int(failures), 16)
    espera: float = min(intervalo * factor, techo)
    return max(intervalo, espera)


def _auto_sim_backoff_cap() -> float:
    value = env_finite_float(AUTO_SIM_BACKOFF_MAX_SECONDS, default=None)
    if value is None or value <= 0:
        return 300.0
    return float(value)


def _protection_config_from_env() -> ProtectionPolicy:
    """Lee la política de protección de env (default OFF = fail-closed).

    ``AUTO_ENGINE_SIM_PROTECTION=1`` activa. ``AUTO_ENGINE_SIM_STOP_PCT``/``_T1_PCT``/
    ``_TRAILING_PCT`` (fracción, p.ej. 0.02) y ``AUTO_ENGINE_SIM_SESSION_END_MINUTE``
    afinan los umbrales. Cualquier valor inválido se ignora (default seguro).
    """

    def _f(name: str, default: float) -> float:
        # P9: un ``NaN``/``inf`` de entorno no es configuración: cae al default con warning.
        value = env_finite_float(name, default=None)
        return default if value is None else value

    def _i(name: str, default: int) -> int:
        # P9: se valida como float finito ANTES de convertir (``int`` de ``inf`` revienta con
        # ``OverflowError``, que nadie capturaba) y un valor raro cae al default.
        value = env_finite_float(name, default=None)
        if value is None:
            return default
        try:
            return int(value)
        except (OverflowError, ValueError):
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


#: S-3 (cierre 2026-10-27) — una salida DECIDIDA que todavía no ha emitido orden.
#: ``EXIT_PENDING`` afirma «hay una venta pedida»; hasta que la orden sale de verdad (tras
#: kill/venue/RiskGate/reserva/materialización) esa afirmación sería falsa. El motivo se
#: guarda aquí y sólo se convierte en transición cuando la venta existe.
@dataclass(frozen=True, slots=True)
class PendingExitIntent:
    event: str
    reason_code: str
    primary_reason: str
    thesis_invalid: bool
    exit_reasons: tuple[str, ...]


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

    H1 — la identidad EXACTA viaja con un sufijo ADITIVO ``::<presetKey>``
    (``active-strategy:<v>::<preset>``). La versión es lo anterior al separador ``::``: se
    recorta PRIMERO, antes de quitar el prefijo, para no arrastrar el preset dentro de la
    versión y para no cambiar NINGUNA salida de las fuentes SIN ``::`` (que son las de hoy).
    """
    text = str(source or "").strip()
    # H1 — ``::`` (dos caracteres) separa versión de preset; sin él ``text`` queda igual.
    text = text.split("::", 1)[0].strip()
    for prefix in (_ACTIVE_STRATEGY_SOURCE_PREFIX, _V2_ENTRY_SOURCE_PREFIX):
        if text.startswith(prefix):
            version_id = text[len(prefix) :].strip()
            return version_id or None
    return None


def _strategy_preset_from_source(source: Any) -> str | None:
    """H1 — extrae el ``preset_key`` ADITIVO de ``DecisionPackage.source``.

    El decider marca la identidad EXACTA de la estrategia como
    ``active-strategy:<version>::<preset_key>`` (separador de DOS caracteres ``::``). Sólo
    esa fuente ``active-strategy:`` CON sufijo lleva preset: cualquier otra (``auto-2.0:<v>``,
    una fuente sin ``::``, la propia ``active-strategy:<v>`` de hoy) NO declara preset y
    devuelve ``None``. Un sufijo vacío o de sólo espacios también es ``None``: la ausencia de
    preset es información, jamás un relleno.
    """
    text = str(source or "").strip()
    if not text.startswith(_ACTIVE_STRATEGY_SOURCE_PREFIX) or "::" not in text:
        return None
    preset = text.split("::", 1)[1].strip()
    return preset or None


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
class BookEquitySnapshot:
    """M14 — la equity del LIBRO como foto inmutable de un turno.

    Tres campos que antes eran tres atributos sueltos y se escribían por separado: un
    lector entre asignaciones podía ver «equity nueva» junto a «unreadable viejo» (o al
    revés). Con la foto, el turno se publica de una sola vez.

    ``equity=None`` + ``unreadable=True`` es «no medido» y veta aperturas. La exigencia de
    haber leído el libro no vive aquí (es ``_book_equity_required``, un hecho del turno, no
    de la foto): el camino hermético nunca llama a ``load_book_equity`` y conserva el env o
    100_000.
    """

    equity: float | None = None
    as_of: str | None = None
    unreadable: bool = False


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
    #: O-1 (cierre 2026-10-27) — el settlement LANZÓ. Se distingue de «no hubo fill»: la
    #: orden quedó confirmada por el schedule pero nada se materializó (o no se sabe).
    failed: bool = False

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
    #: S-6 — salidas emitidas en las que F5 (``ExitPermission``) negó y la exención
    #: declarada las dejó pasar. El contador no veta: hace visible la asimetría.
    exit_permission_denied: int = 0

    def merge(self, other: TurnReport) -> None:
        self.decided += other.decided
        self.proposals += other.proposals
        self.vetoes += other.vetoes
        self.orders += other.orders
        self.fills += other.fills
        self.opened += other.opened
        self.closed += other.closed
        self.exit_permission_denied += other.exit_permission_denied
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


def _blend_entry_price(prior: Decimal, held: Decimal, price: Decimal, qty: Decimal) -> Decimal:
    """Coste medio ponderado tras ampliar una posición viva (M15)."""
    total = held + qty
    if total <= 0:
        return prior
    return (prior * held + price * qty) / total


def _canonical_entry_prices(events: Any) -> dict[str, float]:
    """Coste medio por instrumento derivado de los fills APLICADOS del libro canónico.

    Una posición ADOPTADA por un motor sin proyección previa no trae ``entry_price``
    (``prior is None``). Si se adopta así, la exposición es real pero la base de coste
    desaparece: no hay stop ni trailing calculables y ningún plan puede proponer salida
    — la posición queda viva y muda hasta el fin de la serie (medido 2026-10-21: fila de
    ``sim_auto_positions`` con ``avg_price=NULL`` escrita 3 ms antes del primer tick).

    La base de coste no se inventa: sale del MISMO fold contable que usa la conciliación
    (``build_position_ledger``: coste medio ponderado de lo que queda abierto, neto de
    recortes). Sin fills legibles devuelve ``{}`` y la adopción conserva ``None``
    (fail-closed declarado, nunca un precio de relleno).
    """
    # Las trazas llegan en DOS formas (``_AppliedFill`` del libro en RAM y
    # ``AppliedFillFact`` del lector canónico). Se normalizan al hecho contable con la
    # misma coerción tolerante que usa la reconciliación: el fold solo entiende
    # ``AppliedFillFact`` (``is_buy``/``quantity``/``applied_at``), así que pasarle una
    # traza cruda reventaba y devolvía ``{}`` en silencio.
    facts = _canonical_applied_facts(events)
    if not facts:
        return {}
    try:
        ledger = build_position_ledger(facts)
    except Exception:  # noqa: BLE001 — sin fold no hay base de coste que heredar.
        logger.exception("auto_sim canonical entry price fold failed")
        return {}
    return {
        str(position.instrument_id): float(position.average_entry)
        for position in ledger.positions
        if position.average_entry is not None and position.remaining_qty > 0
    }


def _canonical_applied_facts(events: Any) -> list[Any]:
    """Normaliza las trazas del libro canónico a ``AppliedFillFact`` (puerta ÚNICA).

    Las trazas llegan en DOS formas (``_AppliedFill`` del libro en RAM y
    ``AppliedFillFact`` del lector canónico). Se normalizan al hecho contable con la misma
    coerción tolerante que usa la reconciliación: el fold solo entiende ``AppliedFillFact``
    (``is_buy``/``quantity``/``applied_at``), así que pasarle una traza cruda reventaba y
    devolvía ``{}`` en silencio. La atribución (``strategy_version_id``/``cycle_id``) viaja
    en el hecho: es lo que permite heredarla sin inventarla (Hueco D).
    """
    facts: list[Any] = []
    for event in tuple(events or ()):
        status = getattr(event, "status", None)
        if status is not None and str(status).strip().lower() not in {
            "applied",
            "apply_filled",
        }:
            continue
        qty = getattr(event, "qty", None)
        if qty is None:
            qty = getattr(event, "quantity", None)
        fact = coerce_applied_fill_fact(
            execution_id=getattr(event, "execution_id", None),
            instrument_id=(getattr(event, "instrument_id", None) or getattr(event, "symbol", None)),
            side=getattr(event, "side", None),
            quantity=qty,
            price=getattr(event, "price", None),
            applied_at=getattr(event, "applied_at", None),
            strategy_version_id=(
                getattr(event, "strategy_version_id", None)
                or getattr(event, "strategy_version", None)
            ),
            account_id=getattr(event, "account_id", None),
            cycle_id=getattr(event, "cycle_id", None),
        )
        if fact is not None:
            facts.append(fact)
    return facts


def _canonical_open_attribution(events: Any) -> dict[str, dict[str, Any]]:
    """W-159-3 (Hueco D) — atribución de la posición viva, derivada del LIBRO canónico.

    Un motor nuevo adopta una posición que otro abrió: sin versión ni ciclo, sus fills de
    cierre nacen huérfanos y ``paper_material_readiness`` no puede casar el ciclo (medido
    2026-10-21: 4 ventas con ``ver=None cycle=None`` ⇒ 0 ciclos medibles). Ambos datos
    EXISTEN en el último BUY aplicado del inventario vivo; aquí se recuperan.

    ``None`` en un componente = el libro no lo declara: no se acuña nada. Acuñar un ciclo
    de adopción es una decisión de diseño (mediría algo distinto de lo que dice medir) y
    queda FUERA de este arreglo; lo que sí se hace es no perder el que ya existía.
    """
    facts = _canonical_applied_facts(events)
    if not facts:
        return {}
    try:
        ledger = build_position_ledger(facts)
    except Exception:  # noqa: BLE001 — sin fold no hay atribución que heredar.
        logger.exception("auto_sim canonical attribution fold failed")
        return {}
    attribution: dict[str, dict[str, Any]] = {}
    for position in ledger.positions:
        if position.remaining_qty <= 0:
            continue
        buys = [fact for fact in position.fills if getattr(fact, "is_buy", False)]
        if not buys:
            continue
        # El ÚLTIMO buy aplicado es el que abrió (o amplió) el inventario que sigue vivo.
        latest = max(buys, key=lambda fact: _instant_sort_key(fact.applied_at))
        attribution[str(position.instrument_id)] = {
            "strategyVersion": latest.strategy_version_id,
            "cycleId": latest.cycle_id,
            "openedAt": latest.applied_at,
            "entry": float(position.average_entry) if position.average_entry is not None else None,
        }
    return attribution


def _instant_sort_key(value: Any) -> float:
    """``applied_at`` → instante comparable; un valor ilegible ordena primero (-inf)."""
    if value is None:
        return float("-inf")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()




#: v2.88.27 - ventana de lectura de los ciclos con ``SETTLEMENT`` durable.
_DURABLE_FACTS_READ_WINDOW = 500

#: v2.88.27 - tope de ciclos recientes examinados al recuperar un ``SETTLEMENT``.
_DURABLE_FACTS_RECOVERY_CYCLES = 200

def _sim_interval_seconds(default: float = 60.0) -> float:
    """Intervalo del loop AUTO (env ``AUTO_ENGINE_SIM_INTERVAL_SECONDS``; default 60s).

    V2.24/A9.1 (P2-04): parametrizable para que la prueba Reina pueda arrancar el
    scheduler real sin esperar minutos. Valor inválido ⇒ default seguro.
    """
    raw = (os.getenv("AUTO_ENGINE_SIM_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return default
    # P9: ``Infinity``/``NaN`` no son intervalos. El helper declara el valor crudo y cae al
    # default; sin esto un ``Infinity`` suspendía el loop para siempre.
    value = env_finite_float("AUTO_ENGINE_SIM_INTERVAL_SECONDS", default=default, minimum=0.0)
    if value is None or value <= 0:
        return default
    return value


__all__ = [
    'ADOPTION_COST_SOURCE_LEDGER',
    'ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS',
    'ADOPTION_COST_SOURCE_NONE',
    'ADOPTION_COST_SOURCE_PROJECTION',
    'ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER',
    'AUTO_REAL_PRICE_ENV',
    'AUTO_SIM_BACKOFF_MAX_SECONDS',
    'AUTO_SIM_TICK_BREAKER_FAILURES',
    'AUTO_SIM_WORKER_ENABLED',
    'BookEquitySnapshot',
    'CIRCUIT_BREAKER_PAUSED',
    'CONTROL_PLANE_STALE',
    'Clock',
    'DECIDER_REFRESH_FAILED',
    'DURABLE_STORES_MISSING',
    'FillObservation',
    'JOURNAL_FILL_UNAPPLIED',
    'OPERATIVE_DURABLE_SEAMS',
    'OPERATOR_INTENT_OFF',
    'OPERATOR_INTENT_UNREADABLE',
    'PendingExitIntent',
    'PriceScript',
    'ProtectionConfig',
    'TICK_FAILED',
    'TurnReport',
    'V2_RESERVATION_GRACE_STAMP_RESOLUTION',
    'V2_RESERVATION_GRACE_TURNS',
    'WATCH_REFRESH_FAILED',
    '_ACTIVE_STRATEGY_SOURCE_PREFIX',
    '_ADOPTION_MIN_STOP_GAP',
    '_APPLIED_OUTCOMES',
    '_AppliedFill',
    '_CANONICAL_LEDGER_LIMIT',
    '_DURABLE_FACTS_READ_WINDOW',
    '_DURABLE_FACTS_RECOVERY_CYCLES',
    '_FILL_CHUNKS',
    '_MIRRORS_DECLARED',
    '_POSITION_JOURNAL_RETRY_CAP',
    '_QTY_EPS',
    '_SETTLEMENT_FILL_WINDOW',
    '_Settlement',
    '_V2_CYCLE_RISK_READ_LIMIT',
    '_V2_ENTRY_SOURCE_PREFIX',
    '_V2_OPEN_ORDERS_LIMIT',
    '_V2_RESERVATIONS_LIMIT',
    '_auto_sim_backoff_cap',
    '_blend_entry_price',
    '_canonical_applied_facts',
    '_canonical_entry_prices',
    '_canonical_open_attribution',
    '_dec_or_none',
    '_declare_effective_mirrors',
    '_instant',
    '_instant_sort_key',
    '_mark_observation_changed',
    '_open_order_from_fill',
    '_protection_config_from_env',
    '_sim_interval_seconds',
    '_strategy_preset_from_source',
    '_strategy_version_from_source',
    'auto_sim_backoff_seconds',
    'auto_sim_breaker_failures',
    'default_clock',
    'derive_activity',
    'flat_price_script',
    'logger',
    'read_account_book_equity',
    'real_price_enabled',
    'reservation_grace_window',
    'settlement_snapshot_from_fills',
    'sim_worker_enabled',
    'step_minute_clock',
    'turn_equity_from_book',
]
