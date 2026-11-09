"""Estado durable, journal, auditoria y proyecciones del worker AUTO (slice 2).

Extraido con ``Delta motor = 0``: metodos movidos verbatim desde
``auto_simulation_worker``. El estado vive en la instancia (``self``).
"""
# mypy: disable-error-code="attr-defined"  # atributos definidos en __init__ del facade
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive import (
    AdaptivePlan,
)
from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    journal_age_cycles,
)
from bolsa_analytics.cognitive.exit_order import (
    ExitOrder,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    combine_measurements,
)
from bolsa_analytics.cognitive.open_order import (
    OpenOrder,
    summarize_open_orders,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    PortfolioReservation,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    advance_lifecycle,
    derive_lifecycle_state,
    trailing_status,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    position_state_from_dict,
    seal_protection_transition,
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
from bolsa_application.auto_adaptive_journal import (
    build_adaptive_recommendation_entry,
)
from bolsa_application.auto_adaptive_recovery import (
    AdaptiveStateReading,
)
from bolsa_application.auto_cycle_journal import build_auto_cycle_regime_entry
from bolsa_application.auto_daily_journal import OperationMeasurement, SimJournalRow
from bolsa_application.auto_operational_audit import (
    build_cycle_settlement_entry,
    build_entry_order_entry,
    build_position_materialized_entry,
    build_protection_entry,
    build_reservation_claim_entry,
    build_reservation_reconciliation_entry,
    durable_fact_dedupe_key,
)
from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
from bolsa_application.auto_reason_codes import (
    EXIT_NOT_EMITTED,
    LIFECYCLE_TRANSITION_REJECTED,
    THESIS_EXIT,
    TIME_EXIT,
)
from bolsa_application.auto_self_evaluation_feed import (
    cycles_from_fills,
)
from bolsa_application.auto_v2_entry import (
    build_position_management_journal_entry,
)
from bolsa_application.execution_event import (
    UNAPPLIED_EXECUTION_EVENT_STATUSES,
)
from bolsa_application.position_manager import (
    KILL_SWITCH,
    RISK_EXIT,
    PositionManagerResult,
)
from bolsa_application.top3_opportunities import (
    HISTORICAL_SCORING_NO_CHAMPION,
    select_top3_records,
)

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.


class _StateMixin:
    """Slice del worker AUTO; sin estado propio de clase."""

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

    def journal_pairs(self) -> tuple[SimJournalRow, ...]:
        """Filas de journal completas del día simulado hasta ahora (M7)."""
        return tuple(self._journal)

    def operation_measurements(self) -> tuple[OperationMeasurement, ...]:
        """V2.45/AUTO-5 — MAE/MFE por operación cerrada (recogido del JSONB, no calibrado)."""
        return tuple(self._v2_operation_measurements)

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

    async def _v2_audit_emit(self, entry: Any, *, label: str) -> bool:
        """Publica UNA entrada de auditoría; best-effort declarado (``M2``).

        Sin sink es un no-op silencioso: no hay nada que fingir. Un fallo del sink NO puede
        tumbar el turno (el dinero ya está comprometido aguas arriba), pero se registra —
        un silencio aquí volvería a convertir el hueco en mentira por omisión. Devuelve
        ``False`` solo si el sink falló (M6: el llamante decide si reencolar).
        """
        sink = self._operational_audit_sink
        if sink is None or entry is None:
            return True
        try:
            await sink(entry)
        except Exception:  # noqa: BLE001 — publicar no puede tumbar el turno.
            logger.exception("auto_sim operational audit failed (%s)", label)
            return False
        return True

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
        structural: bool = False,
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
            structural=structural,
        )
        await self._v2_audit_emit(self._v2_seal_audit_identity(entry), label="entry_order")

    async def _v2_journal_position_materialized(
        self,
        *,
        instrument_id: str,
        quantity: Any,
        entry_price: Any,
        execution_id: str | None,
        strategy_version: str | None,
        cycle_id: str | None,
    ) -> None:
        """(F2-1) sella el HECHO durable append-only de materialización de POSICIÓN.

        Cierra ``position_not_durable``: la escalera ``fill → posición`` solo sube con una traza
        por operación. El espejo ``sim_auto_positions`` es por ``(cuenta, motor, símbolo)`` y se
        reescribe al reutilizar el símbolo; esta entrada, ligada a su ``cycle_id``, es historia.
        Best-effort y aditivo: sin sink es un no-op (Δ = 0).
        """
        if self._operational_audit_sink is None:
            return
        entry = build_position_materialized_entry(
            instrument_id=instrument_id,
            quantity=quantity,
            entry_price=entry_price,
            execution_id=execution_id,
            strategy_version=strategy_version,
            cycle_id=cycle_id,
            actor=self._engine_id,
            as_of=self._v2_instant(),
            account_id=self._account_id,
        )
        await self._v2_audit_emit(
            self._v2_seal_audit_identity(entry), label="position_materialized"
        )

    async def _v2_journal_cycle_settlement(
        self,
        *,
        instrument_id: str,
        closed_qty: Any,
        cycle_id: str | None,
        exit_reason: str | None,
        structural: bool = False,
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
            settlement_id=(f"settle-{cycle_id}" if cycle_id else None),
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
            structural=structural,
        )
        await self._v2_audit_emit(self._v2_seal_audit_identity(entry), label="cycle_settlement")

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
        await self._v2_audit_emit(self._v2_seal_audit_identity(entry), label="protection")

    async def _v2_read_cycle_fills(self, cycle_id: str) -> tuple[list[Any], MeasurementStatus]:
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

    async def _v2_cycle_pnl(self, cycle_id: str | None) -> tuple[float | None, MeasurementStatus]:
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
                row = next((r for r in rows if str(r.get("cycleId") or "").strip() == cycle), None)
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
            logger.info("auto_sim durable facts recovery: re-emitted %d settlement(s)", recovered)

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

    async def _v2_save_exit_order_or_pend(self, order: ExitOrder) -> bool:
        """P6: persiste una transición del INTENT; si falla, queda pendiente de reintento.

        La versión más reciente por ``exit_order_id`` sustituye a la anterior. Antes el retorno
        se ignoraba y el INTENT durable se quedaba atrás del fill real sin rastro.
        """
        if await self._v2_save_exit_order(order):
            self._v2_exit_unpersisted.pop(order.exit_order_id, None)
            return True
        logger.error("auto_sim v2 exit order transition pending retry id=%s", order.exit_order_id)
        self._v2_exit_unpersisted[order.exit_order_id] = order
        return False

    async def _v2_retry_unpersisted_exit_orders(self) -> None:
        for order in list(self._v2_exit_unpersisted.values()):
            await self._v2_save_exit_order_or_pend(order)

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
        await self._v2_retry_unpersisted_consumed()
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
        if not await self._v2_persist_consumed(signal_id, symbol, bar_start):
            self._v2_consumed_unpersisted[signal_id] = (symbol, bar_start)

    async def _v2_persist_consumed(self, signal_id: str, symbol: str, bar_start: str) -> bool:
        try:
            await self._consumed_signal_store.mark(
                self._account_id,
                self._engine_id,
                signal_id,
                instrument_id=symbol,
                bar_timestamp=bar_start,
            )
        except Exception:  # noqa: BLE001 — el fill ya ocurrió; se reintenta en el tick siguiente.
            logger.exception("auto_sim v2 consumed signal persist failed symbol=%s", symbol)
            return False
        return True

    async def _v2_retry_unpersisted_consumed(self) -> None:
        """P5: reintenta las marcas durables que fallaron (sin esto un crash re-autoriza la señal)."""
        if self._consumed_signal_store is None or not self._account_id:
            return
        current = self._v2_current_bar_start()
        for signal_id, (symbol, bar_start) in list(self._v2_consumed_unpersisted.items()):
            if bar_start != current or await self._v2_persist_consumed(
                signal_id, symbol, bar_start
            ):
                self._v2_consumed_unpersisted.pop(signal_id, None)

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

    def _v2_tick_proposal_map(self) -> dict[str, dict[str, Any]]:
        """Propuestas adoptables del tick (normalmente vacío: sin parte no hay handoff)."""
        return dict(self._v2_tick_proposals)

    def _v2_tick_proposal_map_from_bar(self) -> dict[str, dict[str, Any]]:
        """Copia defensiva del mapa de la barra (el tick no muta el de la barra)."""
        return {key: dict(value) for key, value in self._v2_bar_proposals.items()}

    async def _v2_settle_daily_proposals(self, plan: Any) -> None:
        """Sella el desenlace de las propuestas que el motor evaluó en este tick.

        * Aprobada con ciclo ⇒ ``consumed`` + ``consumed_cycle_id`` (atribución exacta).
        * Veto del motor ⇒ ``rejected`` con el motivo (NO se busca otro plan).
        * Propuesta caducada por frescura ⇒ ``expired`` con el motivo.

        Sin sumidero es un no-op (Δ = 0). Un fallo se declara y NO tumba el turno: la
        decisión ya está tomada y el hueco queda visible en la cadena.
        """
        sink = self._daily_proposal_sink
        if sink is None or (not self._v2_tick_proposals and not self._v2_tick_expired):
            return
        outcomes: list[dict[str, Any]] = []
        for entry in tuple(getattr(plan, "journal_entries", ()) or ()):
            payload = getattr(entry, "payload", None) or {}
            proposal_payload = payload.get("dailyProposal")
            if not isinstance(proposal_payload, Mapping):
                continue
            proposal_id = str(proposal_payload.get("proposalId") or "").strip()
            if not proposal_id:
                continue
            cycle_id = str(payload.get("cycleId") or "").strip()
            approved = bool(payload.get("approved"))
            reason = ",".join(str(code) for code in (payload.get("reasonCodes") or []) if code)
            outcomes.append(
                {
                    "proposalId": proposal_id,
                    "status": "consumed" if approved and cycle_id else "rejected",
                    "cycleId": cycle_id or None,
                    "reason": None if approved and cycle_id else (reason or "engine_rejected"),
                }
            )
        for proposal_id, reason in self._v2_tick_expired:
            outcomes.append({"proposalId": proposal_id, "status": "expired", "reason": reason})
        if not outcomes:
            return
        try:
            await sink(outcomes)
        except Exception:  # noqa: BLE001 — el desenlace es traza, no dinero.
            logger.exception("auto_sim v2 daily proposal outcome sink failed")

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

    def _v2_note_exit_intent(
        self,
        symbol: str,
        outcome: PositionManagerResult | None,
        *,
        thesis_invalid: bool,
    ) -> None:
        """S-3 — registra la INTENCIÓN de salir sin tocar el FSM.

        ``EXIT_PENDING`` significa «hay una orden de salida viva», así que no puede
        escribirse al DECIDIR: entre la decisión y la orden están los gates (kill,
        venue, RiskGate, reserva durable, materialización), y el manager puede incluso
        devolver ``hold`` (p. ej. ``TIME_STOP`` degradado a ``REVIEW`` bajo
        reconciliación ``CRITICAL``). Antes el FSM avanzaba aquí, antes de esos gates, y
        una salida sin venta dejaba la posición marcada como «salida pedida» para
        siempre: el fantasma de S-3.

        Aquí sólo se conserva el motivo. ``_v2_confirm_exit_emitted`` lo convierte en
        transición cuando la orden ha salido de verdad, y ``_v2_flush_unemitted_exits``
        declara al cerrar el turno lo que no salió (``exit_not_emitted``).
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
        self._v2_pending_exit[symbol] = PendingExitIntent(
            event=event,
            reason_code=reason_code,
            primary_reason=primary,
            thesis_invalid=thesis_invalid,
            exit_reasons=tuple(outcome.exit_reasons),
        )

    def _v2_flush_unemitted_exits(self) -> None:
        """S-3 — el turno termina sin orden: se declara la salida que NO se emitió.

        La posición conserva su estado real (no hay ``EXIT_PENDING``) y el operador ve
        por qué: el motivo decisorio y el evento que se habría aplicado. Silenciarlo
        volvería a confundir «no quiso salir» con «quiso y no pudo».
        """
        if not self._v2_pending_exit:
            return
        at = self._v2_instant()
        for symbol, intent in sorted(self._v2_pending_exit.items()):
            current = self._v2_positions.get(symbol)
            self._journal_position_event(
                symbol,
                EXIT_NOT_EMITTED,
                at=at,
                detail={
                    "primaryReason": intent.primary_reason,
                    "plannedEvent": intent.event,
                    "thesisInvalid": intent.thesis_invalid,
                    "exitReasons": list(intent.exit_reasons),
                    "lifecycle": (derive_lifecycle_state(current) if current is not None else None),
                    "emitted": False,
                },
            )
        self._v2_pending_exit.clear()

    async def _v2_confirm_exit_emitted(self, symbol: str, *, at: str) -> None:
        """S-3 — la orden de salida YA salió: ahora sí se sella ``EXIT_PENDING``.

        Se llama en el camino SELL, después de materializar la venta. Sin intención
        pendiente es un no-op: una salida por stop/objetivo no pasa por aquí (su FSM lo
        escribe el propio cierre).
        """
        intent = self._v2_pending_exit.pop(symbol, None)
        if intent is None:
            return
        # Partimos de la posición VIVA (el ratchet pudo reescribir el JSONB): si se usara
        # la copia previa, el evento pisaría el stop recién ratcheado.
        current = self._v2_positions.get(symbol)
        if current is None:
            return
        event = intent.event
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
            intent.reason_code,
            at=at,
            detail={
                "primaryReason": intent.primary_reason,
                "lifecycle": transition.to_state,
                "deadline": current.holding_deadline_at,
                "invalidationPrice": current.invalidation_price,
                "thesisInvalid": intent.thesis_invalid,
                "exitReasons": list(intent.exit_reasons),
                "emitted": True,
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
        # W-159-1 (Hueco C): además de la RAM del proceso, el hecho entra en la cola del
        # spine durable. Se publica al final del turno (``_v2_flush_position_journal``),
        # mientras la sesión del tick sigue abierta.
        self._v2_position_journal_pending.append(entry)
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

