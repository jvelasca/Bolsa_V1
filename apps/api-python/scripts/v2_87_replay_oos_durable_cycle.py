"""V2.87 · AUTO-MATERIAL-15 — Replay OOS con CICLO DURABLE de reserva→fill→liberación.

Continúa la fase de INVESTIGACIÓN de ``v2.86``. Su hallazgo principal fue que el replay se
**truncaba** tras el primer episodio (``2022-05-06``): el motor dejaba de proponer con
``risk_budget_exceeded`` aunque quedaban 266 días operables. La causa medida no era el
mercado sino el instrumento: el **libro de compromisos** (``portfolio_reservations``) no se
retiraba nunca.

Qué cambia esta fase
--------------------
1. **Ciclo durable al cierre de tick.** Tras cada ``auto_turn`` se invoca el método de
   PRODUCCIÓN ``_v2_reconcile_reservations(startup=False)``, el mismo que el motor real usa
   en el arranque del proceso. En el motor SIM la orden se liquida DENTRO del mismo tick, de
   modo que una reserva que sigue viva al cierre del tick es una reserva cuya orden murió
   sin llenarse: liberarla es fiel, no un atajo. Con ``startup=False`` la liberación se
   declara ``RELEASED_BY_CANCEL`` (no por reinicio) y la regla de ``in_flight`` conserva la
   reserva cuyo fill esté capturado y sin aplicar.
2. **Guardarraíl de horizonte.** El motor reconcilia leyendo los fills aplicados con un tope
   de ``1000`` filas; en un replay multianual ese libro puede superarlo, la lectura quedaría
   truncada (``UNKNOWN``) y la reconciliación se pararía. El espejo en memoria conserva las
   últimas ``_APPLIED_RETENTION`` filas ``APPLIED`` —las únicas que el cierre de tick
   necesita: el ciclo vivo se libera dentro del tick en que nace— y la ventana se DECLARA en
   el artefacto (``retention``). Las trazas no aplicadas (capital en vuelo) nunca se
   descartan. Si además el libro deja de ser medible (``UNKNOWN``) o la parada dura se
   engancha, el replay PARA y publica ``truncationReason`` + el día exacto: una truncación
   se declara, jamás se disimula con narración.
3. **Instrumentación del libro.** Cada tick publica su foto (reservas vivas, capital y
   riesgo comprometidos, órdenes pendientes, medición) y las RETIRADAS por estado destino:
   un pico de ``RELEASED_BY_CANCEL`` es la firma del compromiso huérfano, ahora medida.
4. **Puntuación por año** (``score.byYear``): es lo que permite leer si la muestra es
   multianual o sigue siendo un único episodio.
5. **Evidencia POR RESERVA en la reconciliación (``OBS-18``).** La regla 2 decidía por el
   AGREGADO de fills del instrumento+lado (``filled == 0.0``): una reserva que NUNCA
   materializó quedaba viva para siempre en cuanto una hermana suya llenaba, y la COLA de un
   fill parcial no la retiraba nadie (la regla 1 solo libera lo materializado). El motor
   decide ahora por la EVIDENCIA DE LA RESERVA (``released_qty``, lo que ESTA fila liberó) y
   declara el motivo de la retirada: ``tail_dead`` cuando la fila sí registró fill parcial (se
   retira la cola, no lo materializado) y ``cancel`` cuando no materializó nada. El replay
   publica los motivos (``releases.reasons``): sin ellos ``byDeadTail`` sería un **cero
   silencioso** —«no medí el motivo» leído como «ninguna retirada fue una cola muerta»—, y la
   corrida sellada mide **36 colas muertas** de las 64 retiradas por CANCEL.
6. **Guardarraíl de estancamiento.** Un libro que conserva capital comprometido y deja de
   producir actividad durante ``STALL_OPERABLE_DAYS`` días operables se declara
   ``truncationReason=stalled_book`` en vez de presentarse como corrida completa: la
   contraprueba A/B cerraba con **15 reservas vivas** y ``$6000`` comprometidos, **266 días
   operables** sin una sola orden, y aun así publicaba ``completed=true``.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO sustituye la ventana PAPER** ni cierra ``P3-2``/``P3-3``: el cubo de calendario sale
  del reloj de pared y este replay usa un reloj simulado.
* **NO** se baja ningún umbral, **no** se fuerza régimen, **no** se backdatea y **no** se
  escribe en PostgreSQL: el motor sigue congelado y la cuarentena es por construcción.
* La reconciliación de cierre es el comportamiento del ARRANQUE del motor real aplicado a
  cada tick. Sus dos consecuencias declaradas: (a) un chunk en ``RETRY`` de un llenado
  parcial puede liberarse como si hubiese llenado —el mismo sobre-consumo que el arranque
  real— y (b) la retirada ocurre antes que en producción, donde solo un reinicio la hace.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import pathlib
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Filas ``APPLIED`` que conserva el espejo en memoria. Por debajo del tope de lectura del
#: motor (``DEFAULT_APPLIED_LIMIT = 1000``) para que la reconciliación lea el libro ENTERO
#: en cada tick y su medición siga siendo ``COMPLETE``.
_APPLIED_RETENTION = 900

#: Identidad de la ventana PAPER que se replica (MISMOS valores que ``v2.86``: sin una
#: cuenta/versión idénticas los números no serían contrastables). El edge sigue siendo un
#: DATO declarado del seam (no una medición): la BD no se escribe.
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_EDGE = 0.9

logger = logging.getLogger("v2_87_replay_oos_durable_cycle")


def _load_v86_module() -> Any:
    """Carga el runner de ``v2.86`` para reutilizar sus helpers (mismo patrón que v2.86→v2.76).

    Se reutilizan tal cual: la derivación del watch del catálogo, la lectura read-only de
    barras/sectores, el port de barras, el envoltorio de contexto, el applier confirmador y
    los helpers de impresión. Lo único que esta fase reescribe es el BUCLE del replay.
    """
    path = pathlib.Path(__file__).with_name("v2_86_replay_oos_viability.py")
    spec = importlib.util.spec_from_file_location("v2_86_replay_oos_viability", path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _management_rows_with_cycle(
    journal: Sequence[Any],
    *,
    cycle_by_symbol_day: Mapping[tuple[str, str], str],
) -> list[dict[str, Any]]:
    """Proyección read-only de los eventos de gestión, UNIDOS a su ``cycleId`` (capa v6).

    El join es por ``(instrumento, día)``: en D1 hay UN solo ciclo abierto por símbolo, así que
    el evento de gestión del tick pertenece a ese ciclo. Un evento del día de ENTRADA (sin
    posición previa) queda ``cycleId = None``: es un hueco DECLARADO, nunca un ciclo inventado.
    """
    rows: list[dict[str, Any]] = []
    for entry in journal:
        if str(getattr(entry, "event_type", "") or "") != "auto_position_management":
            continue
        payload = getattr(entry, "payload", None) or {}
        instrument = str(getattr(entry, "instrument_id", "") or "")
        day = str(getattr(entry, "created_at", "") or "")[:10]
        rows.append(
            {
                "cycleId": cycle_by_symbol_day.get((instrument, day)),
                "instrumentId": instrument,
                "day": day,
                "reasonCodes": list(payload.get("reasonCodes") or []),
                "primaryReason": payload.get("primaryReason"),
                "exitReasons": list(payload.get("exitReasons") or []),
                "thesisInvalid": payload.get("thesisInvalid"),
            }
        )
    return rows


def _minted_exit_cycles(
    pre_exit_ids: set[str], exit_orders: Mapping[str, Any]
) -> set[str]:
    """Cycle ids que ESTRENARON un INTENT de salida en el tick (capa v7, read-only).

    El spine mintea un ``ExitOrder`` durable por ciclo ANTES de liquidar (``_v2_reserve_exit``):
    si el ciclo del toque estrena identidad en ``_v2_exit_orders`` este tick, la ORDEN llegó a
    crearse; si no, un veto previo la dejó sin orden. Es la señal POR CICLO que ``dayOrders``
    (global de DÍA) no puede dar. Sólo se comparan las claves NUEVAS respecto al pre-tick; un
    ``cycle_id`` vacío no vota (hueco declarado, nunca un ciclo inventado).
    """
    return {
        str(getattr(order, "cycle_id", "") or "")
        for exit_id, order in (exit_orders or {}).items()
        if exit_id not in pre_exit_ids
    } - {""}


# ── Espejos en memoria con instrumentación DECLARADA ─────────────────────────────


class _RetentionExecutionEventStore:
    """Espejo en memoria de ``execution_events`` con RETENCIÓN declarada de los ``APPLIED``.

    El motor reconcilia con ``read_applied_fill_facts(..., limit=1000)``; recibir ``>= 1000``
    filas marca la lectura ``truncated`` ⇒ ``UNKNOWN`` ⇒ no libera y **engancha la parada
    dura** (``RECONCILIATION_FAILURE``). Un replay multianual puede superar ese tope y
    reintroducir una truncación con otro nombre, así que este espejo conserva las últimas
    ``retention`` filas ``APPLIED`` y ARCHIVA las anteriores (``archived_applied`` lo declara).

    Honestidad del recorte: ``list_applied`` devuelve TODO lo que el espejo contiene, de modo
    que ``len(rows) >= limit`` solo puede ocurrir si de verdad hay ``limit`` filas dentro. La
    ventana es suficiente porque la reconciliación corre en CADA tick y el ciclo que libera
    nace en ese mismo tick: nunca necesita un fill antiguo. Las trazas NO aplicadas (capital
    en vuelo) no se tocan nunca — son el input de la guardia de ``in_flight``.
    """

    def __init__(self, *, retention: int = _APPLIED_RETENTION) -> None:
        from bolsa_application.execution_event import InMemoryExecutionEventStore

        self._inner = InMemoryExecutionEventStore()
        self._retention = max(1, int(retention))
        self._applied_archived = 0
        self._applied_peak = 0

    @property
    def archived_applied(self) -> int:
        """Filas ``APPLIED`` retiradas de la ventana (declaradas en el artefacto)."""
        return self._applied_archived

    @property
    def peak_applied(self) -> int:
        """Máximo de filas ``APPLIED`` que llegó a tener el espejo (hueco hasta el tope)."""
        return self._applied_peak

    def _prune_applied(self) -> None:
        """Archiva las ``APPLIED`` más VIEJAS hasta dejar la ventana en ``retention``.

        Se ordena por ``applied_at`` (el mismo orden cronológico que publica el store real)
        con desempate por identidad, para que el recorte sea determinista y reproducible.
        """
        rows = getattr(self._inner, "_rows", None)  # noqa: SLF001 — espejo test-double.
        if not isinstance(rows, dict):
            return  # internals cambiados: sin recorte; el guardarraíl declarará el tope.
        epoch = datetime.min.replace(tzinfo=UTC)
        applied = sorted(
            (
                (row.applied_at or epoch, execution_id)
                for execution_id, row in rows.items()
                if str(getattr(row, "status", "")) == "APPLIED"
            ),
            key=lambda item: item,
        )
        self._applied_peak = max(self._applied_peak, len(applied))
        excess = len(applied) - self._retention
        if excess <= 0:
            return
        for _, execution_id in applied[:excess]:
            rows.pop(execution_id, None)
            self._applied_archived += 1

    async def mark_applied(
        self,
        execution_id: str,
        *,
        lease_owner: str | None = None,
        lease_generation: int | None = None,
    ) -> bool:
        marked = await self._inner.mark_applied(
            execution_id,
            lease_owner=lease_owner,
            lease_generation=lease_generation,
        )
        if marked:
            self._prune_applied()
        return marked

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _AccountingReservationStore:
    """Espejo en memoria de reservas que REGISTRA cada retirada (log append-only).

    Delega en ``InMemoryReservationStore`` (cuarentena: cero PG) y añade un log de eventos
    de liberación. El conteo por log es EXACTO y no depende de releer el libro con un tope
    que un replay largo podría agotar: ``release`` devuelve ``None`` cuando no había nada que
    liberar (idempotente), así que cada entrada del log es una retirada REAL.

    El log publica también el MOTIVO de la retirada (``reason``). Sin él, ``byDeadTail``
    habría sido un **cero silencioso**: "no se midió el motivo" leído como "ninguna retirada
    fue una cola muerta". La autoridad es la fila que devuelve el libro.
    """

    def __init__(self) -> None:
        from bolsa_application.reservation_store import InMemoryReservationStore

        self._inner = InMemoryReservationStore()
        self.releases: list[dict[str, Any]] = []

    async def release(
        self,
        reservation_id: str,
        *,
        status: Any = None,
        reason: str | None = None,
        released_qty: Any = None,
        at: str | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {"reason": reason, "released_qty": released_qty, "at": at}
        if status is not None:
            kwargs["status"] = status
        row = await self._inner.release(reservation_id, **kwargs)
        if row is not None:
            self.releases.append(
                {
                    "reservationId": str(reservation_id),
                    "status": str(getattr(row, "status", "") or ""),
                    "instrumentId": str(getattr(row, "instrument_id", "") or ""),
                    "at": str(at or ""),
                    # OBS-18: el MOTIVO viaja al log. La autoridad es la fila devuelta por el
                    # libro (si el llamante no lo declara, se conserva el que ya tuviera), de
                    # modo que la cola de un fill parcial (``tail_dead``) sea MEDIBLE y no un
                    # cero silencioso: no medir un motivo no es medir "sin motivo".
                    "reason": str(getattr(row, "release_reason", "") or reason or ""),
                    "releasedQty": getattr(row, "released_qty", None),
                }
            )
        return row

    def __len__(self) -> int:
        return len(self._inner)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ── Paso 2 · replay con ciclo durable ────────────────────────────────────────────


async def _run_durable_replay(
    *,
    watch: list[str],
    bars_by_symbol: dict[str, list[Any]],
    sectors: dict[str, str],
    days: list[str],
    start_index: int,
    max_ticks: int,
    edge: float,
    account_id: str,
    version_a: str,
    engine_id: str,
    operable_days: Sequence[bool] = (),
    durable_cycle: bool = True,
    capture_cycle_detail: bool = False,
) -> dict[str, Any]:
    """Replay hermético con el ciclo durable de reservas CERRADO en cada tick.

    ``capture_cycle_detail`` (default ``False``, INERTE: con él apagado el comportamiento es
    idéntico) captura, al terminar, los fills durables con su ``reference_mid``/``cycle_id`` y los
    motivos de cierre ``position_close`` del journal. Es la materia prima —ya producida por el
    motor— del diagnóstico de dónde nace la pérdida; no cambia ninguna decisión de trading. La
    capa v7 añade, por fotograma, ``orderCreated`` (¿el tick ESTRENÓ el INTENT de salida del
    ciclo?) leyendo el diff de ``_v2_exit_orders`` antes/después de ``auto_turn``: es la señal por
    ciclo que separa «no se creó orden» de «orden sin fill» (``dayOrders`` es de DÍA, no de ciclo)."""
    capture_cycle_detail = bool(capture_cycle_detail)
    from bolsa_analytics.cognitive.measurement import MEASUREMENT_UNKNOWN
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.auto_forward_deciders import build_forward_pair_decider, split_watch
    from bolsa_application.auto_v2_entry import (
        AUTO_ENTRY_DIRECTION,
        AtrSource,
        DiscoveryRegimeSource,
    )
    from bolsa_application.exit_order_store import InMemoryExitOrderStore
    from bolsa_application.kill_switch_store import InMemoryKillSwitchStore
    from bolsa_application.replay_oos import (
        STALL_OPERABLE_DAYS,
        ReplayCursor,
        ReplayFill,
        ReplayTick,
        close_tick,
        declare_book_measurement,
        declare_horizon,
        declare_stall,
        make_as_of_bar_loader,
        operable_days_without_activity,
        score_replay,
        snapshot_book,
        tally_releases,
    )
    from bolsa_application.sim_durable_store import (
        InMemorySimAutoPositionStore,
        InMemorySimConsumedSignalStore,
    )

    v86 = _load_v86_module()
    cursor = ReplayCursor(days, v86._opens_by_symbol(bars_by_symbol), start_index=start_index)
    loader = make_as_of_bar_loader(v86._ReadOnlyBarPort(bars_by_symbol), watch, cursor.as_of)
    regime_source = DiscoveryRegimeSource(bars_provider=loader)

    contexts = v86._RecordingContextStore()
    reservations = _AccountingReservationStore()
    events = _RetentionExecutionEventStore(retention=_APPLIED_RETENTION)

    worker = AutoSimulationWorker(
        engine_id=engine_id,
        account_id=account_id,
        # Hermético: la cuenta no se toca en PG, así que no se exige su presencia.
        require_account_id=False,
        price_script=cursor.price_script,
        clock=cursor.clock,
        regime_source=regime_source,
        atr_source=AtrSource(bars_provider=loader),
        sector_source=lambda symbol: sectors.get(str(symbol)),
        liquidity_source=lambda _symbol: 1_000_000.0,
        edge_source=v86._edge_source(edge),
        kill_switch_source=lambda: False,
        exec_store=events,
        context_store=contexts,
        position_store=InMemorySimAutoPositionStore(),
        consumed_signal_store=InMemorySimConsumedSignalStore(),
        # AUTO-1b: la reserva es la AUTORIDAD del compromiso (no la traza de ejecución).
        reservation_store=reservations,
        # Applier confirmador: cierra cada captura sin mover dinero (todo en memoria).
        finance_applier=v86._ConfirmingFinanceApplier(),
        # V2.87: la identidad de SALIDA y el latch de la parada dura también existen en el
        # replay, de modo que el ciclo durable esté completo (y su parada sea observable).
        exit_order_store=InMemoryExitOrderStore(),
        kill_switch_store=InMemoryKillSwitchStore(),
    )
    watch_a, watch_b = split_watch(watch, a_share=0.5)
    pair = build_forward_pair_decider(
        watch_a=list(watch) if not watch_b else watch_a,
        version_a=version_a,
        decider_b=v86._hold_decider("replay:no-secondary"),
        held_quantity=lambda symbol: float(worker._open.get(symbol, 0)),  # noqa: SLF001
        lot_qty=100.0,
    )
    worker._decider = pair  # noqa: SLF001 — cableado (el worker no se edita).

    ticks: list[ReplayTick] = []
    book_rows: list[dict[str, Any]] = []
    per_day: list[dict[str, Any]] = []
    totals = {"decided": 0, "proposals": 0, "vetoes": 0, "orders": 0, "fills": 0}
    consumed = 0
    release_mark = 0
    partial_book_days = 0
    cancel_release_days = 0
    truncation_reason: str | None = None
    refused_day: str | None = None
    last_active_index: int | None = None
    end = len(days) if int(max_ticks) <= 0 else min(len(days), start_index + int(max_ticks))

    # COSTURA INERTE (capa v5, Δ motor = 0): estado CONGELADO de cada posición ABIERTA al empezar el
    # tick —incluida la que se cierra EN este tick— keyed por ``cycle_id``. Antes del cierre el stop
    # vigente es el del último ratchet y el nivel de invalidación está congelado al nacer. NO toca el
    # motor: sólo LEE lo que ya produjo; con ``capture_cycle_detail`` apagado el replay es idéntico.
    # La capa v5 ACUMULA además la SECUENCIA día a día por ciclo (mark, stop vigente y MAE/MFE
    # persistido) para poder reconstruir POR QUÉ ruta se invalidó la tesis y no sólo el último
    # fotograma. El ``set_index`` se adelanta al muestreo: sólo fija el día del cursor (no muta el
    # estado del worker) y permite etiquetar cada fotograma con su día.
    invalidation_by_cycle: dict[str, dict[str, Any]] = {}
    cycle_timeline: dict[str, list[dict[str, Any]]] = {}
    # Capa v6 (DÍA-D-3g): mapa (símbolo, día) -> cycle_id del ciclo abierto al empezar el tick.
    # Es la clave del join decisión↔ciclo: hay UN solo ciclo abierto por símbolo en D1, así que
    # un evento de gestión journalizado en ese tick pertenece a ese ciclo. Sólo se puebla con la
    # costura encendida; nunca se inventa un ciclo para un símbolo sin posición previa.
    cycle_by_symbol_day: dict[tuple[str, str], str] = {}
    for index in range(start_index, end):
        cursor.set_index(index)
        open_frames: dict[str, dict[str, Any]] = {}
        if capture_cycle_detail:
            day = cursor.current_day()
            for symbol, position in (getattr(worker, "_v2_positions", {}) or {}).items():
                cid = str(getattr(position, "cycle_id", "") or "")
                if not cid:
                    continue
                mfe_mae = getattr(position, "mfe_mae", None)
                mfe_mae = mfe_mae if isinstance(mfe_mae, Mapping) else {}
                invalidation_by_cycle[cid] = {
                    "invalidationPrice": getattr(position, "invalidation_price", None),
                    "actualEntry": getattr(position, "actual_entry", None),
                    "initialStop": getattr(position, "initial_stop", None),
                    "initialRisk": getattr(position, "initial_risk", None),
                    "currentStop": getattr(position, "current_stop", None),
                    "direction": str(getattr(position, "direction", "") or ""),
                }
                frame = {
                    "day": day,
                    "symbol": str(symbol),
                    "mark": cursor.price_script(str(symbol)),
                    "currentStop": getattr(position, "current_stop", None),
                    "invalidationPrice": getattr(position, "invalidation_price", None),
                    "initialStop": getattr(position, "initial_stop", None),
                    "actualEntry": getattr(position, "actual_entry", None),
                    "initialRisk": getattr(position, "initial_risk", None),
                    "direction": str(getattr(position, "direction", "") or ""),
                    "maeR": mfe_mae.get("maeR"),
                    "mfeR": mfe_mae.get("mfeR"),
                    "remainingQty": getattr(position, "remaining_quantity", None),
                }
                cycle_timeline.setdefault(cid, []).append(frame)
                # Referencia al fotograma de HOY: tras ``auto_turn`` se le añade la huella de
                # decisión del tick (mismos campos del mismo día; no se crea un segundo frame).
                open_frames[str(symbol)] = frame
                cycle_by_symbol_day[(str(symbol), day)] = cid
        # Capa v7 (DÍA-D-3h): identificar qué ciclos ESTRENARON un INTENT de salida en este tick
        # (``_v2_exit_orders`` crece en ``_v2_reserve_exit`` antes de liquidar). El diff se toma
        # ANTES de ``auto_turn`` y se resuelve tras él, PERO antes de ``close_tick`` (que corre
        # ``_v2_sync_exit_orders`` y poda los INTENT cerrados). Sólo LEE; con la costura apagada
        # no se ejecuta (Δ motor = 0).
        pre_exit_ids = (
            set(getattr(worker, "_v2_exit_orders", {}) or {}) if capture_cycle_detail else set()
        )
        report = await worker.auto_turn()
        minted_exit_cycles = (
            _minted_exit_cycles(pre_exit_ids, getattr(worker, "_v2_exit_orders", {}) or {})
            if capture_cycle_detail
            else set()
        )
        for key in totals:
            totals[key] += int(getattr(report, key, 0) or 0)

        # ── CICLO DURABLE (v2.87) ────────────────────────────────────────────────
        # La costura del instrumento cierra el ciclo: el MISMO método de producción que el
        # motor real corre al arrancar, aquí al cerrar el tick. En SIM la orden se liquida
        # dentro del tick, así que la reserva que sigue viva es la de una orden que NO
        # materializó; ``close_tick`` la retira (CANCEL) y conserva la que tenga un fill
        # capturado sin aplicar.
        await close_tick(worker, durable_cycle=durable_cycle)

        measurement = worker._v2_pending_book_measurement()  # noqa: SLF001
        stops = dict(worker._v2_stop_map())  # noqa: SLF001 — lectura de estado del tick.
        shelf = snapshot_book(
            cursor.current_day(),
            reservations=worker._v2_reservations,  # noqa: SLF001 — libro vivo del motor.
            pending_orders=worker._v2_pending_open_orders(),  # noqa: SLF001
            measurement=measurement,
        )
        tally = tally_releases(reservations.releases[:release_mark], reservations.releases)
        release_mark = len(reservations.releases)
        if int(tally.delta_by_cancel) > 0:
            cancel_release_days += 1
        # GUARDARRAÍL DE ESTANCAMIENTO: "actividad" = el tick produjo orden, llenado o
        # retiró un compromiso. Un libro con presupuesto comprometido que deja de tener
        # actividad N días operables NO es una corrida completa: se declara.
        if (
            int(getattr(report, "orders", 0) or 0) > 0
            or int(getattr(report, "fills", 0) or 0) > 0
            or int(tally.delta_by_fill) > 0
            or int(tally.delta_by_cancel) > 0
        ):
            last_active_index = index

        rows = contexts.order[consumed:]
        consumed = len(contexts.order)
        # Capa v6 (DÍA-D-3g): huella de DECISIÓN del tick —¿el decider evaluó el stop?— anotada en
        # el MISMO fotograma del día. Se LEE el estado que el worker ya dejó tras ``auto_turn``
        # (``_v2_last_exit_reasons``/``_v2_last_exit_label``) y el resultado durable (fill por
        # ciclo + posición viva). NO toca el motor; con la costura apagada no se ejecuta.
        if capture_cycle_detail and open_frames:
            reasons_map = getattr(worker, "_v2_last_exit_reasons", {}) or {}
            label_map = getattr(worker, "_v2_last_exit_label", {}) or {}
            live_positions = getattr(worker, "_v2_positions", {}) or {}
            filled_by_cycle: dict[str, float] = {}
            for row in rows:
                cycle = str(getattr(row, "cycle_id", "") or "")
                if not cycle:
                    continue
                filled_by_cycle[cycle] = filled_by_cycle.get(cycle, 0.0) + float(
                    getattr(row, "quantity", 0.0) or 0.0
                )
            for symbol, frame in open_frames.items():
                cid = cycle_by_symbol_day.get((symbol, cursor.current_day()), "")
                live = live_positions.get(symbol)
                frame["decisionReasons"] = [
                    str(reason) for reason in (reasons_map.get(symbol, ()) or ())
                ]
                frame["decisionLabel"] = str(label_map.get(symbol, "") or "")
                # Sobrevive si sigue viva la MISMA posición del ciclo (no una reapertura).
                frame["survived"] = (
                    live is not None and str(getattr(live, "cycle_id", "") or "") == cid
                )
                frame["filledQty"] = filled_by_cycle.get(cid, 0.0)
                # Capa v7 (DÍA-D-3h): ¿el tick ESTRENÓ el INTENT de salida del ciclo? Sólo se
                # puede afirmar con un ``cycle_id`` conocido; sin él es un hueco declarado (None).
                frame["orderCreated"] = (cid in minted_exit_cycles) if cid else None
                # Señal de DÍA (declarada NO por-ciclo): el tick produjo órdenes/fills globales.
                frame["dayOrders"] = int(getattr(report, "orders", 0) or 0)
                frame["dayFills"] = int(getattr(report, "fills", 0) or 0)
        fills = tuple(
            ReplayFill(
                day=cursor.current_day(),
                symbol=str(row.instrument_id),
                side=str(row.side),
                quantity=float(row.quantity),
                price=float(row.price),
                strategy_version=row.strategy_version_id,
                cycle_id=row.cycle_id,
                # La dirección sale de la ÚNICA fuente del motor (no de un literal).
                direction=AUTO_ENTRY_DIRECTION,
            )
            for row in rows
        )
        tick_open = {
            str(s): float(q)
            for s, q in worker._open.items()
            if q > 0  # noqa: SLF001
        }
        ticks.append(
            ReplayTick(
                day=cursor.current_day(),
                regime=regime_source(),
                prices={str(s): cursor.price_script(str(s)) for s in watch},
                open_positions=tick_open,
                entry_prices={
                    str(s): float(p)
                    for s, p in worker._entry_price.items()  # noqa: SLF001
                },
                stops=stops,
                fill_rows=fills,
                proposals=int(getattr(report, "proposals", 0) or 0),
                vetoes=int(getattr(report, "vetoes", 0) or 0),
                orders=int(getattr(report, "orders", 0) or 0),
                fills=int(getattr(report, "fills", 0) or 0),
            )
        )
        book_rows.append({**shelf.to_dict(), **tally.to_dict(), "regime": regime_source()})

        day_row: dict[str, Any] = {
            "day": cursor.current_day(),
            "regime": regime_source(),
            "proposals": int(getattr(report, "proposals", 0) or 0),
            "vetoes": int(getattr(report, "vetoes", 0) or 0),
            "orders": int(getattr(report, "orders", 0) or 0),
            "fills": int(getattr(report, "fills", 0) or 0),
            "openPositions": len(tick_open),
            "liveReservations": int(shelf.live_reservations),
            "reservedRisk": float(shelf.reserved_risk),
            "bookMeasurement": shelf.measurement,
            "releasedByCancel": int(tally.delta_by_cancel),
            "releasedByFill": int(tally.delta_by_fill),
        }
        if fills:
            day_row["fillRows"] = [
                {
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "stop": stops.get(fill.symbol),
                    "version": fill.strategy_version,
                }
                for fill in fills
            ]
        per_day.append(day_row)

        # ── GUARDARRAÍL DE HORIZONTE (fail-loud) ────────────────────────────────
        # ``UNKNOWN`` es "no puedo afirmar el libro": el motor mismo lo trata como parada
        # dura, así que el replay se detiene y DECLARA por qué. ``PARTIAL`` es un suelo
        # legítimo (una reserva viva sin dimensiones): el motor ya veta aperturas con
        # ``risk_measurement_partial``, de modo que se cuenta y se declara, no se trunca.
        label = declare_book_measurement(measurement)
        if label == MEASUREMENT_UNKNOWN:
            truncation_reason = "book_measurement_unknown"
            refused_day = cursor.current_day()
            break
        if label != "COMPLETE":
            partial_book_days += 1
        if worker._v2_kill_switch_halted():  # noqa: SLF001 — parada dura observable.
            truncation_reason = "hard_kill_switch_engaged"
            refused_day = cursor.current_day()
            break

        done = len(ticks)
        if done % 100 == 0 or done == (end - start_index):
            print(
                f"  [replay] {done}/{end - start_index} días · {cursor.current_day()} · "
                f"fills={totals['fills']} vetoes={totals['vetoes']} "
                f"vivas={shelf.live_reservations} riesgo={shelf.reserved_risk:.2f} "
                f"libro={shelf.measurement}",
                flush=True,
            )

    score = score_replay(ticks)
    regimes: dict[str, int] = {}
    for tick in ticks:
        key = str(tick.regime or "UNKNOWN")
        regimes[key] = regimes.get(key, 0) + 1

    journal_reasons: dict[str, int] = {}
    try:
        from bolsa_application.market_operability import (
            ENTRY_DECISION_EVENT,
            collect_journal_reasons,
        )

        journal_reasons = dict(
            collect_journal_reasons(
                list(getattr(worker, "_v2_journal", ()) or ()),
                events=frozenset({ENTRY_DECISION_EVENT}),
            )
        )
    except Exception:  # noqa: BLE001 — sin lectura del journal se declara el hueco.
        logger.exception("no se pudieron leer los motivos del journal")

    # ── GUARDARRAÍL DE ESTANCAMIENTO (fail-loud) ───────────────────────────────
    # Un replay que agota su presupuesto y deja de producir actividad NO ha terminado el
    # ciclo: se ha quedado sin gasolina. Antes esto se leía como «corrida completa» (el
    # libro sucio solo se veía en los conteos). Ahora se DECLARA la truncación.
    replayed = start_index + len(ticks)
    operable_without_activity = operable_days_without_activity(
        operable_days, last_active_index=last_active_index, end_index=replayed
    )
    final_row = book_rows[-1] if book_rows else {}
    stall_reason = declare_stall(
        operable_days_without_activity=operable_without_activity,
        live_reservations=int(final_row.get("liveReservations", 0) or 0),
        reserved_risk=final_row.get("reservedRisk"),
    )
    if truncation_reason is None:
        truncation_reason = stall_reason

    horizon = declare_horizon(
        ticks=len(ticks),
        total_ticks=max(0, end - start_index),
        last_day=ticks[-1].day if ticks else None,
        truncation_reason=truncation_reason,
    )
    releases = tally_releases([], reservations.releases)
    live_max = max((int(row["liveReservations"]) for row in book_rows), default=0)

    # Diagnóstico de la pérdida (inerte por defecto): los fills durables (con ``cycle_id`` y
    # ``reference_mid``) y el motivo de cada cierre. La costura NO toca el motor: sólo LEE lo que
    # ya se produjo. El emparejamiento motivo↔ciclo se resuelve por ``executionId`` en el ledger.
    cycle_detail: dict[str, Any] | None = None
    if capture_cycle_detail:
        cycle_detail = {
            "costRows": list(getattr(contexts, "order", ()) or ()),
            # Capa v4: geometría de la invalidación por ciclo (nivel congelado + stop vigente al
            # cierre), leída del estado de la posición. Aditiva y sin efecto en la decisión.
            "invalidationByCycle": invalidation_by_cycle,
            # Capa v5: SECUENCIA día a día por ciclo. Permite saber el mark de cada día, cuándo
            # el MAE persistido alcanzó el nivel y si el stop cambió (break-even/trailing), sin
            # volver a mirar el motor. Un ciclo sin fotogramas es un hueco declarado.
            "cycleTimeline": cycle_timeline,
            "closeRows": [
                {
                    "executionId": str(getattr(row, "execution_id", "") or ""),
                    "reason": str(getattr(row, "reason", "") or ""),
                }
                # El motivo del cierre viaja en la fila ``position_close`` del journal del día
                # (``journal_pairs()``, lectura pública); ``_v2_journal`` NO lo contiene.
                for row in (worker.journal_pairs() or ())
                if str(getattr(row, "kind", "") or "") == "position_close"
            ],
            # Cross-check de la ruta: los eventos RICOS de gestión (``auto_position_management``)
            # declaran ``primaryReason``/``exitReasons``/``thesisInvalid``. Se proyectan de forma
            # read-only para verificar que un ``THESIS_EXIT`` no trae ``structural_stop`` como
            # motivo co-disparado (la precedencia lo impediría por construcción).
            # Capa v6 (DÍA-D-3g): cada evento se une a su ``cycleId`` por ``(instrumento, día)``
            # —el ciclo abierto del símbolo en ese tick— para poder reconstruir la DECISIÓN del
            # día de un ciclo concreto. Un evento del día de ENTRADA (sin posición previa) queda
            # con ``cycleId`` None (hueco declarado, nunca un ciclo inventado).
            "managementRows": _management_rows_with_cycle(
                getattr(worker, "_v2_journal", ()) or (),
                cycle_by_symbol_day=cycle_by_symbol_day,
            ),
        }

    payload: dict[str, Any] = {
        "startDay": days[start_index] if 0 <= start_index < len(days) else None,
        "endDay": ticks[-1].day if ticks else None,
        "ticks": len(ticks),
        "totals": totals,
        "regimeCounts": regimes,
        "journalReasons": journal_reasons,
        "perDay": per_day,
        "daysWithFills": sum(1 for tick in ticks if tick.fill_rows),
        "watchA": list(watch_a),
        "watchB": list(watch_b),
        "pairActive": False,
        "score": score.to_dict(),
        "durableCycle": bool(durable_cycle),
        "book": {
            "perDay": book_rows,
            "liveMax": live_max,
            "partialDays": int(partial_book_days),
            "cancelReleaseDays": int(cancel_release_days),
            "measuredUnknownDays": [row["day"] for row in book_rows if not row["measurable"]],
            "finalReservedCash": (book_rows[-1]["reservedCash"] if book_rows else None),
            "finalReservedRisk": (book_rows[-1]["reservedRisk"] if book_rows else None),
            "stall": {
                "thresholdOperableDays": int(STALL_OPERABLE_DAYS),
                "operableDaysWithoutActivity": int(operable_without_activity),
                "lastActiveDay": (
                    days[last_active_index]
                    if last_active_index is not None and last_active_index < len(days)
                    else None
                ),
                "declared": stall_reason is not None,
            },
        },
        "releases": releases.to_dict(),
        "finalBook": await _final_book_detail(worker),
        "retention": {
            "appliedRetention": _APPLIED_RETENTION,
            "appliedArchived": int(events.archived_applied),
            "appliedPeak": int(events.peak_applied),
            "engineReadLimit": 1000,
        },
        "horizon": horizon.to_dict(),
        "refusedDay": refused_day,
    }
    if capture_cycle_detail:
        # Costura INERTE (Δ motor = 0): con `capture_cycle_detail` apagado —el default— la clave
        # NO se añade, de modo que el artefacto congelado de `replay-repro` sale byte a byte igual.
        payload["cycleDetail"] = cycle_detail
    return payload


# ── Informe ──────────────────────────────────────────────────────────────────────


async def _final_book_detail(worker: Any) -> dict[str, Any]:
    """Declara el LIBRO FINAL con IDENTIDAD, no solo con conteos.

    El artefacto de ``v2.87`` publicaba ``liveMax``/``finalReservedRisk``, que dicen que el
    libro gotea pero **no** qué lo gotea. Un replay que se declara «viable» con el libro
    sucio necesita poder auditarse: aquí se publican las reservas vivas una a una (identidad,
    lado, dimensiones, alta) y las trazas de ``execution_events``, **más** el conjunto
    ``inFlight`` con el que la regla 2 decide (una traza sin aplicar CONSERVA el compromiso:
    es el candidato natural a explicar una reserva que no se retira nunca).
    """
    live = [
        {
            "reservationId": str(getattr(row, "reservation_id", "") or ""),
            "instrument": str(getattr(row, "instrument_id", "") or ""),
            "side": str(getattr(row, "side", "") or ""),
            "status": str(getattr(row, "status", "") or ""),
            "createdAt": getattr(row, "created_at", None),
            "quantity": getattr(row, "quantity", None),
            "remainingQty": getattr(row, "remaining_qty", None),
            "releasedQty": getattr(row, "released_qty", None),
            "entry": getattr(row, "entry", None),
            "reservedCash": getattr(row, "reserved_cash", None),
            "reservedRisk": getattr(row, "reserved_risk", None),
            "strategyVersion": getattr(row, "strategy_version_id", None),
        }
        for row in (getattr(worker, "_v2_reservations", ()) or ())
    ]
    read = getattr(worker, "_v2_read_unapplied", None)
    rows: list[Any] = []
    read_measurement: Any = None
    if callable(read):
        rows, read_measurement = await read()
    in_flight_read = getattr(worker, "_v2_in_flight_instruments", None)
    in_flight = None
    if callable(in_flight_read):
        in_flight = sorted(str(x) for x in await in_flight_read(rows))
    traces = [order.to_dict() for order in (getattr(worker, "_v2_open_orders", ()) or ())]
    owned = getattr(worker, "_v2_owned_reservations", None)
    return {
        "liveReservations": live,
        "unappliedRows": [str(getattr(row, "execution_id", "") or "") for row in rows],
        "unappliedMeasurement": str(read_measurement),
        "inFlight": in_flight,
        "pendingTraces": traces,
        "pendingTraceCount": len(traces),
        "ownedReservationIds": sorted(str(x) for x in owned) if owned is not None else None,
    }


def _print_census(census: dict[str, Any]) -> None:
    """Censo desde el DICT del payload.

    El ``_print_census`` de ``v2.86`` espera el OBJETO ``CensusReport`` y el payload guarda
    ``to_dict()``: reutilizarlo tal cual reventaría (el informe en texto de ``v2.86`` nunca
    se ejercitó; solo se usó ``--json``). Aquí se lee el dict, que es lo que el artefacto
    publica.
    """
    print("PASO 0 · CENSO DE DÍAS OPERABLES (read-only, sin lookahead)")
    print("-" * 64)
    print(f"watch                     {census.get('watch')} símbolos")
    print(f"días de historia          {census.get('totalDays')}")
    print(f"días OPERABLES (long)     {census.get('operableDays')}")
    print(f"  por eje operativo       {census.get('operableByOperational')}")
    print(f"racha operable máxima     {census.get('maxOperableStreak')}")
    print(f"distribución de régimen   {census.get('aggregateCounts')}")
    print("  (muestra de días operables, máx. 10)")
    shown = 0
    for row in census.get("days") or ():
        if not row.get("entriesAllowedLong"):
            continue
        print(f"    {row['day']}  {row['operational']:16s} {dict(row.get('counts') or {})}")
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        print("    (ninguno)")


def _print_book(replay: dict[str, Any]) -> None:
    book = replay["book"]
    horizon = replay["horizon"]
    print()
    print("PASO 2b · LIBRO DE COMPROMISOS (reserva → fill → liberación)")
    print("-" * 64)
    print(f"reservas vivas (máx.)     {book['liveMax']}")
    print(f"días con medición parcial {book['partialDays']}")
    print(f"días con retirada CANCEL  {book['cancelReleaseDays']}")
    print(f"retiradas acumuladas      {replay['releases']['total']}")
    print(f"riesgo comprometido final {book['finalReservedRisk']}")
    stall = book.get("stall") or {}
    if stall.get("lastActiveDay") is not None or stall.get("operableDaysWithoutActivity"):
        print(
            f"actividad                 último día {stall.get('lastActiveDay')} · "
            f"{stall.get('operableDaysWithoutActivity')} días operables sin actividad "
            f"(umbral {stall.get('thresholdOperableDays')})"
        )
    print(
        f"retención APPLIED         {replay['retention']['appliedRetention']} "
        f"(archivadas {replay['retention']['appliedArchived']}, "
        f"pico {replay['retention']['appliedPeak']})"
    )
    print(f"ciclo durable             {'ON' if replay['durableCycle'] else 'OFF (control)'}")
    print(
        f"horizonte                 {horizon['ticks']}/{horizon['totalTicks']} "
        f"completo={horizon['completed']}"
    )
    if horizon["truncationReason"]:
        print(f"TRUNCACIÓN declarada      {horizon['truncationReason']} @ {replay['refusedDay']}")
    if "byYear" in replay["score"]:
        print(f"R por año (salida)        {replay['score']['byYear']}")


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    v86 = _load_v86_module()
    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        watch = v86._watch_from_cli(args.watch)
        if not watch:
            v76 = v86._load_v76_module()
            watch = await v76._watch_from_catalog(  # noqa: SLF001 — MISMA derivación del watch.
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector e historia")
        v86._configure_env(watch=watch, venue=str(args.venue), edge=float(args.edge))

        bars_by_symbol = await v86._read_bars(factory, watch)
        days = v86._trading_days(bars_by_symbol)
        if int(args.history_days) > 0:
            days = days[-int(args.history_days) :]
        if not days:
            raise RuntimeError("no hay barras D1 para censar")

        census = census_operable_days(bars_by_symbol, days)
        evidence: dict[str, Any] = {
            "bump": "2.11.0-beta",
            "phase": "V2.87 AUTO-MATERIAL-15 REPLAY OOS CICLO DURABLE",
            "nature": "INVESTIGACION",
            "venue": str(args.venue),
            "account": str(args.account_id),
            "versionA": str(args.version_a),
            "watch": list(watch),
            "watchSize": len(watch),
            "historyDays": len(days),
            "census": census.to_dict(),
            "replay": None,
            "reconcilesAtTickClose": bool(args.durable_cycle),
            "limits": [
                "NO sustituye la ventana PAPER: el cubo de calendario sale del reloj de pared.",
                "NO cierra P3-2/P3-3: es evidencia de INVESTIGACION.",
                "Aproximacion D1: un dia = un tick.",
                "Version B = HOLD (la ACTIVE exigiria su propia fuente de barras acotada).",
                f"Edge = {float(args.edge)} (dato declarado del seam, NO una medicion).",
                "Liquidez = 1e6 plana (dato declarado del seam, NO una medicion).",
                "Cero escrituras a PostgreSQL: stores en memoria (cuarentena).",
                "La reconciliacion de cierre es el comportamiento del ARRANQUE del motor real: "
                "retira antes que produccion (que solo lo hace al reiniciar) y puede liberar "
                "como llenado un chunk en RETRY de un llenado parcial.",
                f"Ventana declarada del espejo APPLIED: {_APPLIED_RETENTION} filas "
                "(por debajo del tope de lectura 1000 del motor).",
                "Medicion PARTIAL del libro NO trunca (el motor ya veta con "
                "risk_measurement_partial); UNKNOWN si trunca y se declara.",
            ],
        }

        if not args.no_replay and census.operable_days > 0:
            start_index = int(args.start_index)
            if start_index < 0:
                first_full = next(
                    (
                        index
                        for index, row in enumerate(census.days)
                        if len(watch) > 0 and row.measured_symbols == len(watch)
                    ),
                    None,
                )
                start_index = (first_full + 1) if first_full is not None else 1
            sectors = await v86._load_sectors(factory, watch)
            evidence["sectorsKnown"] = len(sectors)
            evidence["replay"] = await _run_durable_replay(
                watch=watch,
                bars_by_symbol=bars_by_symbol,
                sectors=sectors,
                days=days,
                start_index=max(1, start_index),
                max_ticks=int(args.max_ticks),
                edge=float(args.edge),
                account_id=str(args.account_id),
                version_a=str(args.version_a),
                engine_id=f"replay-oos-durable-{os.urandom(3).hex()}",
                operable_days=tuple(bool(row.entries_allowed_long) for row in census.days),
                durable_cycle=bool(args.durable_cycle),
            )
        elif not args.no_replay:
            evidence["replaySkipped"] = "census_gate: 0 dias operables (el paso 2 no aporta)"
        return evidence
    finally:
        await engine.dispose()


def _use_utf8_console() -> None:
    """Fuerza UTF-8 en la consola: el informe y la ayuda usan ``→``/``⇒``.

    La consola por defecto de Windows (cp1252) NO sabe codificar esos caracteres: sin esto,
    ``--help`` y el informe revientan con ``UnicodeEncodeError``. Se declara explícitamente
    con ``errors="replace"`` para que una consola exótica degrade el glifo, no la corrida.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover — stream cerrado o redirigido.
            continue


def main(argv: list[str] | None = None) -> int:
    _use_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch", default=None, help="instrumentos separados por coma (si falta, catálogo)"
    )
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument(
        "--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado"
    )
    parser.add_argument(
        "--history-days", type=int, default=0, help="acota a los últimos N días (0 = todo)"
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=-1,
        help="índice del primer día simulado (-1 = automático: tras el warm-up de régimen)",
    )
    parser.add_argument("--max-ticks", type=int, default=0, help="tope de ticks (0 = todos)")
    parser.add_argument(
        "--edge", type=float, default=_DEFAULT_EDGE, help="valor declarado del seam de edge"
    )
    parser.add_argument("--no-replay", action="store_true", help="solo el censo (paso 0)")
    parser.add_argument(
        "--no-durable-cycle",
        dest="durable_cycle",
        action="store_false",
        help="modo CONTROL: no reconcilia al cierre del tick (reproduce el goteo de v2.86)",
    )
    parser.add_argument(
        "--account-id", default=_DEFAULT_ACCOUNT, help="cuenta de la ventana (solo etiqueta)"
    )
    parser.add_argument("--version-a", default=_DEFAULT_VERSION_A, help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument("--json", action="store_true", help="emite el payload como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        evidence = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo ejercitar el replay ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    if args.out:
        pathlib.Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.json:
        print(payload)
    else:
        v86 = _load_v86_module()
        print(
            f"REPLAY OOS · CICLO DURABLE (V2.87 · AUTO-MATERIAL-15) · {datetime.now(UTC):%Y-%m-%d}"
        )
        print("=" * 64)
        print(f"cuenta / versión A        {evidence['account']} / {evidence['versionA']}")
        print(f"watch                     {evidence['watchSize']} símbolos")
        _print_census(evidence["census"])
        if evidence.get("replay"):
            v86._print_replay(evidence["replay"])
            _print_book(evidence["replay"])
        v86._print_verdict(evidence)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
