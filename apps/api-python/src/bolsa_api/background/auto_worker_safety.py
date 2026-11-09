"""Seguridad y gobernanza: kill switch, reconciliacion, reservas y gates (slice 3).

Extraido con ``Delta motor = 0``: metodos movidos verbatim desde
``auto_simulation_worker``. El estado vive en la instancia (``self``).
"""
# mypy: disable-error-code="attr-defined"  # atributos definidos en __init__ del facade
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive import (
    AdaptivePlan,
    AdaptivePolicy,
    RecoveryEvidence,
)
from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    DATA_GATE_FREEZES,
    DataGatePolicy,
    DataGateReading,
)
from bolsa_analytics.cognitive.data_freshness import (
    FreshnessPolicy,
    assess_data_freshness,
)
from bolsa_analytics.cognitive.exit_order import (
    new_exit_order_id,
)
from bolsa_analytics.cognitive.hard_kill_switch import (
    KILL_STATE_UNREADABLE,
    HardKillSwitch,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    combine_measurements,
    measurement_from_counts,
)
from bolsa_analytics.cognitive.open_order import (
    OpenOrder,
    build_open_order,
)
from bolsa_analytics.cognitive.operational_governor import (
    assess_from_measurements,
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
    PortfolioReservation,
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
from bolsa_application.adaptive_gate_store import sink_failures_from_state
from bolsa_application.applied_fills import read_applied_fill_facts
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    adaptive_state_unread,
)
from bolsa_application.auto_cycle_reconciliation import (
    cycle_ids_with_reservations,
    reconcile_cycle_trace,
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
)
from bolsa_application.auto_self_evaluation_feed import (
    recovery_evidence_from_fills,
)
from bolsa_application.auto_v2_entry import (
    build_worker_snapshot,
)
from bolsa_application.kill_switch_store import KillState
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    POSITION_PROJECTION_OK,
    POSITION_PROJECTION_REBUILT,
    POSITION_PROJECTION_UNKNOWN,
    reconcile_sim_account,
)

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.


class _SafetyMixin:
    """Slice del worker AUTO; sin estado propio de clase."""

    def mark_control_stale(self, reason: str) -> None:
        """M7 — declara que el control plane dejó de estar fresco (veta aperturas)."""
        token = str(reason or "").strip()
        if not token:
            return
        if token not in self._control_plane_stale:
            logger.warning(
                "auto_sim control plane NO fresco (%s): aperturas vetadas engine=%s",
                token,
                self._engine_id,
            )
        self._control_plane_stale.add(token)

    def clear_control_stale(self, reason: str) -> None:
        """M7 — el refresco volvió a funcionar: se levanta SÓLO ese token."""
        self._control_plane_stale.discard(str(reason or "").strip())

    @property
    def control_plane_stale(self) -> tuple[str, ...]:
        """Tokens vigentes de control plane caducado (orden estable, para trazas)."""
        return tuple(sorted(self._control_plane_stale))

    def require_position_readopt(self) -> None:
        """P7 (auditoría .183) — exige readoptar la posición en el PRÓXIMO turno.

        ``real_turn`` readopta una sola vez por proceso. Cuando el lease cambia de
        generación (otro proceso condujo el motor y murió, o lo soltó), la RAM de este
        proceso ya no es la verdad: hay que reconstruir ``_open`` desde
        ``sim_auto_positions`` en vez de heredar una memoria que dejó de ser suya.
        """
        self._readopted = False

    def _v2_missing_durable_seams(self) -> tuple[str, ...]:
        """M8 — espejos durables que faltan para conducir un turno OPERATIVO.

        Sólo se consulta con ``require_durable_stores=True``: el camino hermético no
        promete durabilidad y no debe pagar el chequeo. Un espejo presente pero degradado
        (lectura caída) lo declara su propio canal; aquí sólo se detecta la AUSENCIA,
        que es la que deja el estado únicamente en RAM.
        """
        return tuple(
            name for name in OPERATIVE_DURABLE_SEAMS if getattr(self, f"_{name}", None) is None
        )

    def declare_skip(self, reason: str) -> None:
        """Declara POR QUÉ este proceso no ejecutó el turno (nunca un veto silencioso).

        P7: cuando otro proceso es el dueño del lease, este runtime no toca la cartera.
        Sin esta declaración el turno quedaría con el ``idle`` por defecto y el motivo
        real —no ser el dueño— se perdería, que es justo lo que la traza debe explicar.
        """
        self._last_gate_reason = (str(reason),)

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
            # R-1: el canónico tampoco se pudo leer ⇒ el latch de lectura sigue enganchado
            # (ni siquiera un watch vacío puede quedar sin veto).
            self._projection_read_failed = True
            return {}
        if canonical is None:
            # El lector no pudo determinar el canónico (distinto de "sin posiciones"):
            # no se reconstruye nada y NO se autorizan aperturas.
            self._reconciliation = {s: POSITION_PROJECTION_UNKNOWN for s in projection}
            self._projection_read_failed = True
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
        adopted_entries = _canonical_entry_prices(events)
        # W-159-2 (Hueco B): la base de coste del LIBRO se conserva para la adopción. Antes
        # solo se usaba para curar una fila ``OK`` sin ``entry_price``; el camino de
        # geometría reconstruida seguía fiándose del espejo (medido 2026-10-21: stop
        # 12.9144 sobre un coste real de 10.3335 ⇒ liquidación en el primer tick).
        self._canonical_entry_by_symbol = {
            str(sym): Decimal(str(value))
            for sym, value in adopted_entries.items()
            if value is not None
        }
        # W-159-3 (Hueco D): la versión y el ciclo del inventario VIVO se heredan del último
        # BUY aplicado. Es recuperación de un dato que ya existía, no acuñación: un
        # componente que el libro no declara queda en ``None`` (y el cierre lo declarará así).
        # La aplicación sobre ``_position_version`` se hace en ``readopt_positions`` DESPUÉS
        # del bucle de la proyección: el libro manda sobre el espejo.
        self._canonical_attribution = _canonical_open_attribution(events)
        for verdict in report.verdicts:
            symbol = verdict.symbol
            self._reconciliation[symbol] = verdict.status
            if verdict.status == POSITION_PROJECTION_REBUILT and self._position_store is not None:
                # Reconstruye la proyección desde el canónico (conserva protección si la hay).
                canonical_qty = canonical_map.get(symbol, Decimal("0"))
                prior = projection.get(symbol)
                prior_entry = getattr(prior, "entry_price", None)
                # V2.88.159 — una adopción NO puede perder la base de coste: el motor nuevo
                # no tiene proyección previa (``prior is None``), y heredar
                # ``entry_price=None`` dejaba una posición real sin stop, sin trailing y
                # sin plan de salida posible (inoperable hasta el fin de la serie). La base
                # de coste SÍ está en el libro de fills aplicados; se reconstruye de ahí.
                adopted_entry = (
                    prior_entry if prior_entry is not None else adopted_entries.get(symbol)
                )
                # R-2 (verificación 2026-10-26 §8) — el canónico es de CUENTA y esta fila
                # es de MOTOR. Con más de una fila viva el reparto no es determinable:
                # escribir ``canonical_qty`` aquí sumaba el total de la cuenta a cada motor
                # (medido: 300 con un worker, 400 si ambos reconstruyen) y la convergencia
                # posterior a OK ocultaba la discrepancia agregada. Se declara UNKNOWN, se
                # veta la apertura y NO se toca la cantidad: es preferible vetar a inventar.
                multiple_rows = await self._multiple_live_rows(account_id, symbol)
                if multiple_rows:
                    self._multi_engine_symbols.add(symbol)
                    self._reconciliation[symbol] = POSITION_PROJECTION_UNKNOWN
                    logger.warning(
                        "auto_sim rebuilt projection skipped symbol=%s canonical=%s "
                        "(varias filas vivas: el total de la cuenta no es de una fila)",
                        symbol,
                        canonical_qty,
                    )
                    continue
                # W-159-5 (Hueco E): con una sola fila viva el coste del libro sí
                # identifica a esta fila; el guard de ambigüedad queda cubierto arriba.
                if canonical_qty <= 0:
                    # El canónico dice "sin posición": la proyección estaba obsoleta.
                    await self._position_store.delete(account_id, self._engine_id, symbol)
                else:
                    await self._position_store.upsert(
                        account_id,
                        self._engine_id,
                        symbol,
                        canonical_qty,
                        entry_price=adopted_entry,
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
        # V2.88.159 — CURA de una proyección que YA coincide con el canónico pero nació
        # sin base de coste. El camino ``REBUILT`` de arriba solo se ejecuta cuando la
        # cantidad DIVERGE; si la fila se escribió con ``entry_price=NULL`` y la cantidad
        # es la correcta, el veredicto es ``OK`` y nadie la tocaba: la posición real seguía
        # sin stop, sin trailing y sin plan de salida (medido 2026-10-21: 0 fills con la
        # posición viva y muda). Se rellena SOLO con la base de coste del libro de fills
        # aplicados; sin ella no se inventa nada (se declara y se deja como estaba).
        if self._position_store is not None and adopted_entries:
            for verdict in report.verdicts:
                if verdict.status != POSITION_PROJECTION_OK:
                    continue
                symbol = verdict.symbol
                row = projection.get(symbol)
                if row is None or row.entry_price is not None:
                    continue
                if row.quantity is None or row.quantity <= 0:
                    continue
                entry = adopted_entries.get(symbol)
                if entry is None:
                    logger.warning(
                        "auto_sim adopted position without cost basis symbol=%s "
                        "(sin fills aplicados: sin stop ni plan de salida)",
                        symbol,
                    )
                    continue
                # W-159-5 (Hueco E): con más de una fila viva el coste medio de la cuenta
                # no identifica a esta fila; se deja declarado en vez de inventar el
                # reparto (la cantidad ya coincide, así que la operación no cambia).
                if await self._cost_basis_is_ambiguous(account_id, symbol):
                    logger.warning(
                        "auto_sim adopted position without unambiguous cost basis "
                        "symbol=%s (varias filas vivas: entry_price no se cura)",
                        symbol,
                    )
                    continue
                healed = Decimal(str(entry))
                await self._position_store.upsert(
                    account_id,
                    self._engine_id,
                    symbol,
                    row.quantity,
                    entry_price=healed,
                    high_watermark=row.high_watermark,
                    stop_price=row.stop_price,
                    t1_state=row.t1_state,
                    trailing_state=row.trailing_state,
                    strategy_version_id=row.strategy_version_id,
                    position_state=row.position_state,
                )
                self._entry_price[symbol] = healed
                logger.info(
                    "auto_sim adopted position healed symbol=%s entry=%s qty=%s",
                    symbol,
                    healed,
                    row.quantity,
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
        # M7: con el control plane caducado (watch/estrategia/turno) no hay universo ni
        # propuesta fresca que autorice una apertura, sea cual sea el símbolo.
        if self._control_plane_stale:
            return True
        # R-1: un fallo de LECTURA veta globalmente, sin depender de que el símbolo esté
        # enumerado en ``_watch_symbols()`` (que puede venir vacío con el universo ESTUDIO).
        if self._projection_read_failed:
            return True
        return self._reconciliation.get(symbol) in {
            POSITION_PROJECTION_DIVERGENT,
            POSITION_PROJECTION_UNKNOWN,
        }

    def _kill_active(self) -> bool:
        """True si el kill switch está activo (o NO se puede leer; fail-closed)."""
        try:
            return bool(self._kill_switch_source())
        except Exception:  # noqa: BLE001 — no saber ⇒ bloquear el motor AUTO.
            return True

    def _v2_mfe_mae_snapshot(self, symbol: str) -> Mapping[str, Any]:
        """``mfe_mae`` vigente del PositionState (copia), o vacío si no hay estado."""
        position = self._v2_positions.get(symbol)
        raw = getattr(position, "mfe_mae", None)
        return dict(raw) if isinstance(raw, Mapping) else {}

    def _v2_account_drawdowns(self) -> Any:
        """Actualiza la marca de equity y devuelve ``AccountDrawdowns`` (o ``None``).

        Se calcula cuando lo necesita el gobernador (drawdown diario) o el corte opt-in de
        drawdown pico-valle. Con AMBOS apagados devuelve ``None`` sin tocar el libro: el
        camino por defecto no paga el cómputo y queda byte-idéntico.

        La equity es la **marcada a mercado** del tick: base declarada
        (``AUTO_ENGINE_SIM_V2_EQUITY``) + P&L realizado acumulado + P&L no realizado de
        las posiciones vivas (marca vs entrada). ``EquityMarkBook`` deriva de ahí el
        drawdown diario/semanal y el pico-valle (``max_pct``).
        """
        if (
            not self._v2_tunables.governor_enabled
            and self._v2_tunables.account_max_drawdown_pct is None
        ):
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
        return self._v2_equity_marks.update(
            self._account_id or "auto-sim",
            float(equity),
            initial_deposit=base,
            now=self._v2_marks_now(),
        )

    def _v2_governor_drawdown_pct(self) -> float | None:
        """Drawdown diario MEDIDO de la cuenta para el gobernador (V2.43/AUTO-3)."""
        if not self._v2_tunables.governor_enabled:
            return None
        marks = self._v2_account_drawdowns()
        return None if marks is None else marks.daily_pct

    def _v2_account_max_drawdown_pct(self) -> float | None:
        """Drawdown PICO-VALLE medido (%), o ``None`` si no hay corte o no es medible.

        ``None`` con el corte OFF es "no consultado". Con el corte ON y ``initial_deposit``
        no positivo, ``EquityMarkBook.max_pct`` también es ``None``: no medido. El motor
        distingue ambos casos por su configuración, no por el valor.
        """
        if self._v2_tunables.account_max_drawdown_pct is None:
            return None
        marks = self._v2_account_drawdowns()
        return None if marks is None else marks.max_pct

    def _v2_kill_switch_halted(self) -> bool:
        """True si la parada DURA latcheada está activa (V2.44)."""
        switch = getattr(self, "_v2_kill_switch", None)
        return bool(switch is not None and switch.engaged)

    def _v2_kill_state(self, *, at: str | None = None) -> KillState | None:
        """Foto durable del latch actual; ``None`` sin cuenta/engine (no persistible).

        P-1b — el placeholder ``KILL_STATE_UNREADABLE`` devuelve ``None``: no es un HECHO
        durable (nace de no poder leer el espejo, y la escritura fallaría por la misma
        causa), así que no se persiste. Guardarlo como si fuera una parada real haría que
        un reinicio posterior la restaurase como ``SYSTEM_ERROR`` —un motivo inventado— y
        borrase el rastro de la parada de verdad. El latch local sigue activo: vetar
        entradas no depende de que esto sea persistible.
        """
        switch = self._v2_kill_switch
        account_id = self._account_id or ""
        engine_id = self._engine_id or ""
        if not account_id or not engine_id:
            return None
        if switch.reason == KILL_STATE_UNREADABLE:
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

        R-1 — la lectura sana SIN parada durable no cierra el caso cuando el latch local
        tiene una causa REAL: puede ser un HALT cuya escritura falló (store caído en el
        momento de la activación). Si no se reintenta, el siguiente reinicio lee «sin fila»
        y reabre el motor. Por eso, en las ramas en que el espejo no contiene ese halt, se
        reintenta persistirlo (idempotente); la liberación del placeholder y la regla de
        adopción no cambian.
        """
        store = self._kill_switch_store
        account_id = self._account_id or ""
        engine_id = self._engine_id or ""
        if store is None or not account_id or not engine_id:
            return
        try:
            state = await store.load(account_id, engine_id)
        except Exception:  # noqa: BLE001 — no poder leer no autoriza a operar.
            logger.exception("auto_sim v2 kill state load failed")
            # P-1 (verificación 2026-10-26 §8) — un store ilegible NO puede dejar el
            # latch desengajado: el proceso seguiría publicando ``RUNNING`` sin poder
            # afirmar que no hay un HALT persistido. Se engancha el latch LOCAL con el
            # motivo declarado ``KILL_STATE_UNREADABLE`` (no se persiste: la escritura
            # puede fallar por la misma causa) y las entradas quedan vetadas.
            self._v2_kill_switch.engage(KILL_STATE_UNREADABLE, at=self._v2_instant())
            return
        if state is None:
            # P-1 (cierre 2026-10-26) — lectura VÁLIDA y SIN fila durable: la tabla
            # significa "la parada nunca se activó". Si el latch local venía del
            # placeholder ``KILL_STATE_UNREADABLE``, se libera aquí: es la única vía de
            # recuperación tras un fallo TRANSITORIO de lectura. Sin esto el proceso
            # quedaba parado en memoria hasta reiniciarse, aunque la lectura ya fuese sana.
            self._release_unreadable_placeholder(detail="sin fila durable")
            # R-1 — una lectura sana sin fila NO demuestra que el latch local (con causa
            # real) sea un fantasma: puede ser un HALT cuya escritura falló. Se reintenta
            # persistirlo antes de devolver, o el reinicio siguiente reabriría el motor.
            await self._v2_repersist_local_halt()
            return
        if state.engaged:
            # El placeholder ``KILL_STATE_UNREADABLE`` NO oculta la causa durable: en
            # cuanto la lectura vuelve, el latch adopta el motivo/identidad persistidos.
            if (
                self._v2_kill_switch.engaged
                and self._v2_kill_switch.reason != KILL_STATE_UNREADABLE
            ):
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
        # P-1 (cierre 2026-10-26) — una fila RELEASED con reconciliación demuestra que no
        # hay HALT durable activo (y que el levantamiento fue explícito y auditable). Si el
        # latch local era el placeholder de lectura ilegible, se libera: un ``engaged_at``
        # del placeholder no es una activación durable, así que comparar instantes no
        # aplica aquí.
        if state.release_reconciliation_id:
            self._release_unreadable_placeholder(
                detail=f"fila durable liberada reconciliation={state.release_reconciliation_id}"
            )
        if not self._v2_kill_switch.engaged or not state.release_reconciliation_id:
            # R-1 — la fila liberada NO demuestra una liberación explícita, así que un
            # HALT local con causa real sigue vigente: se reintenta hacerlo durable.
            await self._v2_repersist_local_halt()
            return
        released_at = _instant(state.released_at)
        engaged_at = _instant(self._v2_kill_switch.engaged_at)
        if released_at is None or engaged_at is None or released_at < engaged_at:
            # R-1 — instantes no comparables o liberación ANTERIOR al halt local: la
            # parada local es posterior y manda, pero solo si sobrevive al reinicio.
            await self._v2_repersist_local_halt()
            return
        self._v2_kill_switch.release(reconciliation_ok=True)
        logger.warning(
            "auto_sim v2 hard kill RELEASED by durable reconciliation=%s actor=%s",
            state.release_reconciliation_id,
            state.release_actor,
        )

    def _release_unreadable_placeholder(self, *, detail: str) -> None:
        """P-1 — libera SÓLO el placeholder local ``KILL_STATE_UNREADABLE``.

        Un HALT con motivo real NO se libera aquí: es un hecho durable y sólo una
        reconciliación explícita lo levanta. La lectura VÁLIDA del espejo que demuestre
        que no hay parada activa (sin fila, o fila liberada con ``reconciliation_id``) es
        la única vía para deshacer el placeholder tras un fallo TRANSITORIO. Antes, el
        proceso quedaba parado en memoria hasta reiniciarse aunque el store ya leyese.

        P-1b — el predicado es la garantía, no una optimización: cuando una causa REAL
        aparece con el placeholder activo, ``HardKillSwitch.engage`` asciende el motivo
        (el placeholder deja de ser ``reason``), así que este método ya no puede liberar
        la parada. Sin ese ascenso, una lectura válida posterior habría borrado un HALT
        de verdad sin dejar rastro.
        """
        switch = self._v2_kill_switch
        if not switch.engaged or switch.reason != KILL_STATE_UNREADABLE:
            return
        if switch.release(reconciliation_ok=True):
            logger.warning(
                "auto_sim v2 hard kill placeholder RELEASED by a valid durable read (%s)",
                detail,
            )

    async def _v2_repersist_local_halt(self) -> None:
        """R-1 — reintenta escribir un HALT REAL que el espejo durable no refleja.

        El caso que cierra: el store está caído, el latch local se engancha con el
        placeholder y una causa REAL lo asciende (``HardKillSwitch.engage``) mientras la
        escritura sigue fallando. Cuando el store vuelve, la lectura es sana pero sin fila
        —o con una fila liberada anterior al halt— y antes se devolvía sin más: la parada
        vivía solo en RAM y el reinicio siguiente reabría el motor.

        Solo aplica a un latch engaged con motivo distinto del placeholder (el placeholder
        no es un hecho durable). Es idempotente: tras un ``save`` correcto la lectura
        siguiente ve la fila ``engaged`` y no se vuelve a escribir por esta vía.
        """
        switch = self._v2_kill_switch
        if not switch.engaged or switch.reason == KILL_STATE_UNREADABLE:
            return
        if await self._v2_persist_kill_state():
            logger.warning(
                "auto_sim v2 hard kill RE-PERSISTED from the local latch reason=%s engagement=%s",
                switch.reason,
                switch.engagement_id,
            )

    async def _v2_persist_kill_state(self, *, at: str | None = None) -> bool:
        """Persiste el latch actual; ``False`` si no fue durable.

        Fail-closed en la dirección que importa: un fallo de escritura NO desactiva la
        parada (el latch sigue in-memory y se declara). Lo que no se hace es creer que el
        sistema está protegido por un HALT que nadie podrá leer tras un crash.

        P-1b — el placeholder ``KILL_STATE_UNREADABLE`` no se persiste (``_v2_kill_state``
        devuelve ``None``): se declara el motivo en el log para que el tramo ilegible no
        desaparezca sin dejar rastro.
        """
        store = self._kill_switch_store
        state = self._v2_kill_state(at=at)
        if store is None or state is None:
            if (
                self._v2_kill_switch.engaged
                and self._v2_kill_switch.reason == KILL_STATE_UNREADABLE
            ):
                logger.warning(
                    "auto_sim v2 kill state NOT persisted: placeholder %s is not a durable fact",
                    KILL_STATE_UNREADABLE,
                )
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
        account_drawdowns = self._v2_account_drawdowns()
        governor_drawdown = (
            account_drawdowns.daily_pct
            if account_drawdowns is not None and self._v2_tunables.governor_enabled
            else None
        )
        account_max_drawdown = (
            account_drawdowns.max_pct if account_drawdowns is not None else None
        )
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
            drawdown_pct=governor_drawdown,
            max_drawdown_pct=account_max_drawdown,
            # V2.44: la frescura por dimensión entra en el snapshot. Con mercado stale el
            # motor veta APERTURAS (``stale_data``); las salidas protectoras no consultan
            # el snapshot, así que siguen vivas (invariante de la casa).
            data_freshness=self._v2_data_freshness().data_freshness,
        )

    @property
    def _v2_reservation_book_active(self) -> bool:
        """True cuando el libro durable de reservas es la autoridad del compromiso."""
        return self._reservation_store is not None

    def _v2_instant(self) -> str:
        """Instante del tick en ISO-UTC (mismo formato que el ``tick_id`` del plan)."""
        return self._time.strftime("%Y-%m-%dT%H:%M:%SZ")

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

        Sin espejo (``store is None``) el tick **veta** los instrumentos que el plan quería
        comprometer: la mitad durable del invariante no se puede cumplir, así que la
        aprobación no se emite. Salir con ``blocked`` vacío era fail-OPEN y es el defecto
        que dejó la ventana con fills y sin una sola fila de reserva (medido el 2026-10-23).
        """
        store = self._reservation_store
        previous = self._v2_reservations
        reservations = tuple(getattr(plan, "reservations", ()) or ())
        if store is None:
            # P1 (medido el 2026-10-23): sin espejo de reservas NO hay compromiso durable.
            # Antes se salía declarando ``blocked`` VACÍO —fail-OPEN—: la aprobación se
            # emitía igual y el fill nacía sin reserva. La ventana lo dejó medido: 24 fills
            # (19→22 oct) y **0 filas** en ``portfolio_reservations`` con los contadores de
            # inserción a 0 y ``stats_reset`` nulo (nunca hubo un alta). Se veta exactamente
            # lo que el plan pretendía comprometer; sin reservas que persistir, nada cambia
            # (un tick hermético sin espejo y sin entradas sigue siendo un no-op).
            self._v2_reservation_blocked = frozenset(
                reservation.instrument_id
                for reservation in reservations
                if getattr(reservation, "instrument_id", None)
            )
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
            # M5: la propiedad se REGISTRA tras el commit (abajo), no aquí: un ``save_claim``
            # ganado que no llegue a commitear no es un compromiso de nadie. Declararse dueño
            # de una reserva inexistente hacía que el cierre de turno intentara retirarla.
            persisted.append(reservation)
        try:
            await store.commit()
        except Exception:  # noqa: BLE001 — sin commit no hay compromiso durable: no se emite.
            logger.exception("auto_sim v2 reservation commit failed")
            # M5: no se asume autocommit. Lo no confirmado no cuenta como reservado y su
            # instrumento queda vetado este turno (fail-closed).
            blocked.update(row.instrument_id for row in persisted)
            # M5: los claims GANADOS que no llegaron a ser durables NO se publican como
            # hechos: el journal afirmaría la propiedad de un capital que no está reservado
            # y el monitor de concurrencia leería un dueño que no existe en el libro. Las
            # carreras PERDIDAS sí se publican (ocurrieron antes y sin depender del commit).
            claim_audits = [(row, won) for row, won in claim_audits if not won]
            persisted = []
        # M5: solo ahora (compromiso confirmado) esta sesión es dueña de las reservas.
        self._v2_owned_reservations.update(row.reservation_id for row in persisted)
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
                    else (RELEASE_REASON_DEAD_TAIL if materialized > 0.0 else RELEASE_REASON_CANCEL)
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
        self._v2_owned_reservations &= {row.reservation_id for row in self._v2_reservations}
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

        P4 (auditoría .183): ``require_evidence=True``. En producción el gate **no puede** publicar
        ``OK`` cuando el tick no midió completitud, ventana reciente o antigüedad del journal: eso
        se declaraba ``evidence_not_provided`` y se trataba como salud. Ahora degrada (``LIMITS``),
        que es la respuesta honesta a una deuda de datos.
        """
        return DataGatePolicy(require_evidence=True)

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
            version: min(int(count), ceiling) for version, count in live.items() if int(count) > 0
        }

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
            logger.exception("auto_sim v2 adaptive gate streak NOT durable consecutive=%s", local)
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

    def _consult_exit_permission(self, symbol: str, *, at: str) -> AutoExitReview:
        """S-6 — consulta F5 antes de emitir la salida del símbolo (no la bloquea).

        El plan es el que produjo la gestión de ESTE turno (``_v2_last_exit_plans``); si
        no hay (camino legacy sin ``PositionState``), F5 responde ``missing_exit_plan`` y
        se declara así: un plan inventado sería peor que un hueco confesado.

        El veredicto **no** se usa para vetar (contrato en ``auto_exit_gate``): se
        journaliza, se cuenta y se publica. Antes, estas condiciones no tenían ningún
        efecto **ni** rastro en AUTO (auditoría 2026-10-26 §5.8).
        """
        plan = self._v2_last_exit_plans.get(symbol)
        freshness = self._v2_data_freshness()
        # ``blocks_new_entry`` = mercado stale **o** sin fechar: es el mismo criterio con
        # el que el motor veta aperturas, así que F5 no juzga las salidas con otra vara.
        data_stale = bool(freshness.blocks_new_entry)
        portfolio_drift = self._v2_recon_status(symbol) == "drift"
        review = review_auto_exit(
            plan,
            data_stale=data_stale,
            portfolio_drift=portfolio_drift,
            kill_switch=self._kill_active(),
            at=at,
        )
        self._v2_last_exit_reviews[symbol] = review
        self._journal_position_event(
            symbol,
            AUTO_EXIT_PERMISSION_EVENT,
            at=at,
            detail={
                **review.to_dict(),
                "exitPlanId": plan.exit_plan_id if plan is not None else None,
                "primaryReason": plan.primary_reason if plan is not None else None,
                # Contexto JIT declarado: lo que el worker SÍ mide y lo que no. Un
                # ``marketClosed=None`` se lee "no medido", nunca "mercado abierto".
                "jit": {
                    "dataStale": data_stale,
                    "marketDataStale": bool(freshness.market_data_stale),
                    "marketClosed": None,
                    "portfolioDrift": portfolio_drift,
                },
            },
        )
        return review

