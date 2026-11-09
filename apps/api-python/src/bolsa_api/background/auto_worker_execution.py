"""Ejecucion: fills, stops, gaps, adopcion de posiciones y turnos internos (slice 4).

Extraido con ``Delta motor = 0``: metodos movidos verbatim desde
``auto_simulation_worker``. El estado vive en la instancia (``self``).
"""
# Los atributos de instancia viven en ``__init__`` del facade (patron mixin).
# mypy: disable-error-code="attr-defined"
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, cast

from bolsa_analytics.cognitive.auto_portfolio_snapshot import UNKNOWN_SECTOR
from bolsa_analytics.cognitive.exit_order import (
    build_exit_order,
    new_exit_order_id,
)
from bolsa_analytics.cognitive.exit_plan import (
    is_thesis_invalidated,
)
from bolsa_analytics.cognitive.exit_policy import (
    resolve_exit_policy,
    resolve_holding_horizon,
)
from bolsa_analytics.cognitive.measurement import (
    combine_measurements,
)
from bolsa_analytics.cognitive.open_order import (
    OpenOrder,
    summarize_open_orders,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    SIDE_SELL,
    PortfolioReservation,
    build_reservation,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    advance_lifecycle,
    compute_trail_stop,
    derive_lifecycle_state,
    is_trail_armed,
    protection_state_dict,
    trailing_status,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    apply_position_current_stop,
    apply_position_reduce,
    build_position_state_from_fill,
    seal_protection_transition,
)
from bolsa_analytics.cognitive.trade_context import TradeContext
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
from bolsa_api.background.paper_auto_engine_worker import (
    _effective_venue,
)
from bolsa_application.auto_daily_journal import OpportunityRow, SimJournalRow
from bolsa_application.auto_reason_codes import (
    ATR_GEOMETRY,
    ATR_SOURCE_REAL,
    LIFECYCLE_TRANSITION_REJECTED,
    POSITION_UNMANAGED,
    PROTECT_REQUESTED,
    PROTECTION_MISSING,
    RECONCILIATION_REQUIRED,
    STOP_RATCHET_APPLIED,
    STOP_RATCHET_REJECTED,
    day_exit_reason,
)
from bolsa_application.auto_v2_entry import (
    V2Signal,
    build_active_strategy_hold_journal_entry,
    plan_v2_position_outcome,
    position_manager_package,
    position_manager_stop_update,
    sector_from_package,
    signal_identity_for_bar,
)
from bolsa_application.auto_v2_entry import (
    edge_from_package as _edge_from_package,
)
from bolsa_application.decision_contract import (
    DecisionPackage,
)
from bolsa_application.position_manager import (
    KILL_SWITCH,
    RISK_EXIT,
    PositionManagerResult,
    PositionManagerSkip,
)
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    POSITION_PROJECTION_UNKNOWN,
)
from bolsa_application.simulated_settlement import (
    normalized_auto_venue,
)

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.


class _ExecutionMixin:
    """Slice del worker AUTO; el estado vive en la instancia, declarado aquí para mypy."""

    _v2_intent_bar: str
    _v2_reservations: tuple[PortfolioReservation, ...]
    _v2_unmanaged_bar: str
    _minute: int
    _time: datetime
    _open: dict[str, Decimal]
    _settlement_failures: int
    _v2_enabled: bool

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

    @property
    def minute(self) -> int:
        return self._minute

    @property
    def time(self) -> datetime:
        return self._time

    @property
    def open_symbols(self) -> tuple[str, ...]:
        return tuple(s for s, q in self._open.items() if q > 0)

    def holds_long(self, symbol: str) -> bool:
        """¿El libro **real** tiene posición larga abierta en ``symbol``? (B-3).

        Es la fuente de verdad del estado ``gated``: la posición puede haberse abierto
        antes de la ventana de barras, y en ese caso el replay de la ventana no la vería.
        """
        return self._open.get(str(symbol).strip(), Decimal("0")) > 0

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

    @property
    def settlement_failures(self) -> int:
        """O-1: nº de settlements que LANZARON en este proceso (no solo en el log).

        Es el contador que el informe del día publica como ``settlementFailures``; cada fallo
        deja además su fila de journal (``settlement_failed``), que es la fuente del conteo.
        """
        return self._settlement_failures

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
        structural: bool = False,
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
            # O-2 — la fila declara si el settlement fue ESTRUCTURAL (sin caja).
            structural=structural,
        )
        self._journal.append(row)
        return row

    def v2_enabled(self) -> bool:
        """True si el pipeline AUTO 2.0 gestiona la decisión (env-gated, default OFF)."""
        return self._v2_enabled

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
                # B-5: un HOLD CON MOTIVO no depende del precio —no ejecuta ni marca—. Si se
                # callara aquí, «la señal de la ACTIVE está apagada» desaparecería justo en el
                # caso en que el operador más necesita leerlo. Se declara con precio 0 y sin
                # geometría; el precio ausente sigue declarándose por su propio canal (W4).
                if (
                    str(getattr(pkg, "action", "HOLD")).upper() == "HOLD"
                    and str(getattr(pkg, "hold_reason", None) or "").strip()
                ):
                    signals.append(self._v2_hold_signal(symbol, pkg))
                continue
            price = Decimal(str(raw_price))
            action = str(getattr(pkg, "action", "HOLD")).upper()
            version = _strategy_version_from_source(getattr(pkg, "source", None))
            # H1 — la identidad EXACTA de la estrategia (preset) viaja con la señal para
            # aterrizar en el journal de decisión sin migración; ausente ⇒ ``None``.
            preset = _strategy_preset_from_source(getattr(pkg, "source", None))
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
            # Handoff ESTUDIO → AUTO: si el parte publicó una propuesta ADOPTABLE para este
            # instrumento, la IDENTIDAD de la señal es la del parte (``signalId``) y no la
            # que deriva la barra. Así el ciclo durable nace con la identidad que el
            # usuario vio en pantalla; sin propuesta se conserva la histórica (Δ = 0).
            proposal = self._v2_tick_proposals.get(symbol) or self._v2_tick_proposals.get(
                symbol.upper()
            )
            if proposal is not None:
                declared = str(proposal.get("signalId") or "").strip()
                if declared:
                    signal_id = declared
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
            if atr_source != ATR_SOURCE_REAL:
                # R1 — un ATR de FALLBACK no es una MEDICIÓN. El journal ya lo declara
                # (``ATR_GEOMETRY``/``atrSource``) y ``plan_v2_tick`` deriva la MISMA
                # geometría sintética desde ``atr_pct_fallback``: pasar ``None`` no cambia
                # el tamaño ni el stop, pero impide medir el hueco decisión→ejecución
                # contra un ATR inventado (un «1 ATR» sintético vetaría todo hueco > 2 %).
                # Con ``atr_required`` el efecto es el de siempre: el candidato NO entra.
                signal_atr: float | None = None
            else:
                signal_atr = atr
            signals.append(
                V2Signal(
                    instrument_id=symbol,
                    action=action,
                    price=float(price),
                    # D-1 — el precio de FILL del tick viaja con la señal: el contraste de
                    # la geometría del parte tiene que hacerse contra el precio al que la
                    # orden se liquida (``open(B)``), no solo contra la decisión
                    # (``close(B-1)``). Sin fuente real ambos coinciden (Δ = 0); sin precio
                    # de ejecución se declara ``None`` y el plan usa la decisión.
                    execution_price=self._v2_price_exec(symbol, self._v2_bar_tick()),
                    atr=signal_atr,
                    edge=self._v2_edge(pkg, version or "unversioned"),
                    sector=context.sector,
                    liquidity_notional=context.liquidity_notional,
                    trade_context=context,
                    strategy_version=version,
                    strategy_preset_key=preset,
                    # O-6 — la procedencia viaja con la señal hasta el journal: es lo que
                    # permite leer «HOLD por no haber señal» distinto de «HOLD porque la
                    # ventana no alcanzaba» sin abrir el motor.
                    feature_source=getattr(pkg, "feature_source", None),
                    signal_window_bars=getattr(pkg, "signal_window_bars", None),
                    # B-1 — la ventana efectiva viaja con la señal hasta el journal.
                    warmup_bars=getattr(pkg, "warmup_bars", None),
                    signal_window_source=getattr(pkg, "signal_window_source", None),
                    # ADR-048 — el estado ``gated`` del libro viaja con la señal.
                    gated_state=getattr(pkg, "gated_state", None),
                    # B-5 — el motivo del HOLD viaja con la señal: sin este eslabón el
                    # paquete lo declaraba y el plan del tick nunca lo veía.
                    hold_reason=getattr(pkg, "hold_reason", None),
                    hold_detail=str(getattr(pkg, "memo", "") or ""),
                    signal_id=signal_id,
                    bar_timestamp=identity.bar_timestamp if identity is not None else "",
                    valid_until=identity.valid_until if identity is not None else "",
                )
            )
        return signals

    def _v2_hold_signal(self, symbol: str, pkg: Any) -> V2Signal:
        """B-5 — señal HOLD con motivo para un símbolo SIN precio.

        Un HOLD declarado no ejecuta ni marca, así que su motivo no depende del precio. Se
        emite con ``price=0`` y SIN geometría (nada aguas abajo construye una entrada con
        ella: el plan sólo la lee para declarar el motivo). La identidad de barra se calcula
        igual que en el resto, para que la declaración sea una por barra y no una por turno.
        """
        action = "HOLD"
        version = _strategy_version_from_source(getattr(pkg, "source", None))
        preset = _strategy_preset_from_source(getattr(pkg, "source", None))
        identity = signal_identity_for_bar(
            instrument_id=symbol,
            action=action,
            strategy_version=version or "unversioned",
            timeframe=self._v2_granularity.decision.timeframe,
            moment=self._time,
        )
        return V2Signal(
            instrument_id=symbol,
            action=action,
            price=0.0,
            strategy_version=version,
            strategy_preset_key=preset,
            feature_source=getattr(pkg, "feature_source", None),
            signal_window_bars=getattr(pkg, "signal_window_bars", None),
            warmup_bars=getattr(pkg, "warmup_bars", None),
            signal_window_source=getattr(pkg, "signal_window_source", None),
            gated_state=getattr(pkg, "gated_state", None),
            hold_reason=str(getattr(pkg, "hold_reason", None) or "").strip() or None,
            hold_detail=str(getattr(pkg, "memo", "") or ""),
            signal_id=identity.signal_id if identity is not None else "",
            bar_timestamp=identity.bar_timestamp if identity is not None else "",
            valid_until=identity.valid_until if identity is not None else "",
        )

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
                return cast("str | None", context.sector)
            return None
        if self._v2_sector_source is None:
            return None
        try:
            return cast("str | None", self._v2_sector_source(symbol))
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
        return cast(
            "float | None", source.edge_for(strategy_version or "unversioned")
        )

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

    def _v2_evidence_lookup(
        self, packages: Mapping[str, Any]
    ) -> dict[str, dict[str, float | None]] | None:
        """Lookup síncrono ``instrument_id → components`` para ``plan_v2_tick``.

        ``None`` cuando no hay fuente o ningún instrumento tiene evidencia: el motor
        conserva el scoring histórico (solo edge+liquidity). Dentro de una entrada, un
        componente a ``None`` significa NO medido (C-3): el ranker lo clampa para el
        combinado pero no lo cuenta en ``measured_components``.
        """
        source = self._v2_evidence_source
        if source is None:
            return None
        components_for = getattr(source, "components_for", None)
        if not callable(components_for):
            return None
        lookup: dict[str, dict[str, float | None]] = {}
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

    def _v2_declare_active_strategy_holds(self, plan: Any) -> list[Any]:
        """B-5 — entradas de journal de los HOLD con motivo de la estrategia ACTIVE.

        El plan del tick trae las declaraciones (``active_strategy_holds``) y aquí se filtran
        por ``(símbolo, motivo, barra)`` para no reescribir el mismo hecho en cada turno. No
        son decisiones de entrada: viajan con el evento propio
        ``auto_active_strategy_hold``, que el censo de operabilidad no cuenta.
        """
        entries: list[Any] = []
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        for hold in tuple(getattr(plan, "active_strategy_holds", ()) or ()):
            key = hold.dedupe_key
            if key in self._v2_active_hold_journaled:
                continue
            self._v2_active_hold_journaled.add(key)
            entries.append(
                build_active_strategy_hold_journal_entry(hold, actor=self._engine_id, as_of=at)
            )
        return entries

    async def _v2_apply_exit_fill(self, exit_order_id: str | None, qty: Any, *, at: str) -> None:
        """Aplica un fill materializado al INTENT de salida (V2.43.3 · separación I/O/F).

        Un fill no positivo o un intent desconocido no mueven nada (fail-closed: no se
        inventa materialización). ``filled_qty``/``remaining_qty`` del intent quedan así en
        fase con el fill real, no con la cantidad pedida.
        """
        key = str(exit_order_id or "").strip()
        if not key:
            return
        await self._v2_retry_unpersisted_exit_orders()
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
        await self._v2_save_exit_order_or_pend(updated)
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

        P1 (medido el 2026-10-23): la política alcanza también al INTENT. Antes se ignoraba el
        retorno de ``_v2_save_exit_order(order)``: con el espejo ausente se emitía la salida
        con una identidad que ningún reinicio podía reconciliar y sin un solo log. Ahora, si
        el INTENT no es durable, se intenta uno de emergencia y, si tampoco, se para el
        sistema y no se emite.
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
        if not await self._v2_save_exit_order(order):
            # P1 (medido el 2026-10-23): el INTENT es la identidad durable de la salida. Antes
            # se emitía igual aunque no quedara escrito — el fill viajaba con un
            # ``exit_order_id`` que ningún reinicio podía reconciliar y sin un solo log que lo
            # dijera. Se aplica la MISMA política B que a la reserva: INTENT de emergencia o
            # parada; nunca una salida sin rastro. Se devuelve aquí, sin crear la reserva de
            # salida, para no reescribir después la fila ``EMERGENCY`` con un estado normal.
            emergency = order.as_emergency("exit_intent_persist_failed", at=at)
            if not await self._v2_save_exit_order(emergency):
                logger.error(
                    "auto_sim v2 exit intent persist failed intent=%s; HALT", exit_order_id
                )
                await self.engage_kill_switch_durable("SYSTEM_ERROR", at=at)
                return None
            self._v2_exit_orders[exit_order_id] = emergency
            return exit_order_id
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
        await self._v2_save_exit_order_or_pend(reserved)
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

    def _v2_adopt_position(
        self,
        symbol: str,
        price: Decimal,
        *,
        ledger_cost_ambiguous: bool = False,
    ) -> PositionState | None:
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

        C-4 (auditoría .161) — ``ledger_cost_ambiguous`` lo mide el llamante async
        (:meth:`_cost_basis_is_ambiguous`); esta función se mantiene síncrona para no
        romper la batería de crash. Con el libro ambiguo la adopción usa el espejo del
        motor y se declara degradada: el nivel deja de fingir que el coste de la CUENTA es
        el coste de ESTA fila.
        """
        held = self._open.get(symbol, Decimal("0"))
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if held <= 0 or price <= 0:
            return None
        # W-159-2 (Hueco B) — base de coste de la adopción: el LIBRO canónico manda y el
        # espejo es respaldo declarado. Medido 2026-10-21: el espejo traía una entrada que
        # no era el coste del libro (10,3335) y la geometría reconstruida nació con un stop
        # POR ENCIMA del mercado, que liquidó la posición en el primer tick.
        entry, entry_source = self._adoption_cost_basis(
            symbol, canonical_ambiguous=ledger_cost_ambiguous
        )
        if entry is None or entry <= 0:
            if entry_source == ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS:
                # C-4 — un plan durable trae su PROPIA geometría: no necesita el coste del
                # libro. Se intenta antes de declarar el hueco de coste.
                restored = self._v2_restore_durable_position(symbol, held)
                if restored is not None:
                    if restored.lifecycle_state is None:
                        return self._v2_degrade_adoption(
                            symbol,
                            restored,
                            source="plan",
                            reason="durable_plan_without_lifecycle_state",
                            at=at,
                            entry=None,
                            price=price,
                            entry_source=entry_source,
                        )
                    return cast("PositionState | None", restored)
            reason = (
                "cost_basis_ambiguous"
                if entry_source == ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS
                else "cost_basis_missing"
            )
            self._journal_position_event(
                symbol,
                RECONCILIATION_REQUIRED,
                at=at,
                detail={
                    "source": "none",
                    "reason": reason,
                    "reasonCode": PROTECTION_MISSING,
                    "entrySource": entry_source,
                    "price": float(price),
                    "quantity": float(held),
                    "attention": "high",
                },
            )
            logger.warning(
                "auto_sim v2 adoption without cost basis symbol=%s qty=%s reason=%s "
                "(sin stop: se declara)",
                symbol,
                held,
                reason,
            )
            return None
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
                    entry=entry,
                    price=price,
                    entry_source=entry_source,
                )
            return cast("PositionState | None", restored)
        # W-159-3 (Hueco D): el ciclo del inventario vivo se HEREDA del libro (si el fill lo
        # declara). Sin esto, la salida de una posición adoptada nacía sin ciclo y no podía
        # casar con su entrada; con esto, el cierre se atribuye al ciclo que de verdad abrió.
        adopted_cycle = (self._canonical_attribution.get(symbol) or {}).get("cycleId")
        # E2: la geometría reconstruida usa el ATR REAL si existe; el sintético se declara
        # como tal (antes se usaba siempre el 2% del precio, también para adoptar).
        atr_value, atr_source = self._v2_atr_geometry(symbol, float(entry))
        if atr_source != ATR_SOURCE_REAL:
            self._journal_position_event(
                symbol,
                ATR_GEOMETRY,
                at=at,
                detail={
                    "atrSource": atr_source,
                    "atr": atr_value,
                    "entry": float(entry),
                    "entrySource": entry_source,
                    "price": float(price),
                    "phase": "adoption",
                },
            )
        if atr_value is None:
            # Ni siquiera la geometría de emergencia es construible sin ATR.
            atr_value = float(entry) * self._v2_tunables.atr_pct_fallback
        stop, stop_reason = self._v2_adoption_stop(
            entry=entry, price=price, atr_value=atr_value, atr_source=atr_source
        )
        if stop is None:
            # Ni la geometría de emergencia es construible: se declara la ausencia de
            # protección SIN stop sintético (no se inventa un número), pero la posición SÍ
            # se adopta: gestionarla sin estado era peor y dejarla muda, peor aún.
            return self._v2_declare_adoption_without_stop(
                symbol,
                held=held,
                entry=entry,
                price=price,
                atr_value=atr_value,
                atr_source=atr_source,
                entry_source=entry_source,
                reason=stop_reason,
                at=at,
            )
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
            # W-159-3 (Hueco D): ciclo heredado del libro canónico (``None`` si no lo declara).
            cycle_id=str(adopted_cycle) if adopted_cycle else None,
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
            # C-4 — con el libro ambiguo se usa el espejo del motor: el plan se declara
            # degradado por el COSTE, no por «no hay plan durable» (el plan es reconstruido
            # en ambos casos y el motivo real es el que viaja al journal).
            reason=(
                "cost_basis_ambiguous"
                if entry_source == ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER
                else "no_durable_plan"
            ),
            at=at,
            entry=entry,
            price=price,
            atr_value=atr_value,
            atr_source=atr_source,
            entry_source=entry_source,
        )

    async def _multiple_live_rows(self, account_id: str, symbol: str) -> bool:
        """R-2 — ¿hay más de un MOTOR con fila viva para ``symbol``?

        Es el predicado de ``_cost_basis_is_ambiguous`` extraído para reusarlo en la
        reconstrucción: la cantidad canónica es de la CUENTA, y con dos filas vivas no
        hay forma determinista de repartirla entre motores.
        """
        return cast("bool", await self._cost_basis_is_ambiguous(account_id, symbol))

    def _v2_adoption_stop(
        self,
        *,
        entry: Decimal,
        price: Decimal,
        atr_value: Any,
        atr_source: str | None,
    ) -> tuple[Decimal | None, str]:
        """W-159-2 (Hueco B) — stop reconstruido y el motivo DECLARADO si no lo hay.

        Tres condiciones, todas necesarias, y el motivo del rechazo viaja al journal:

        1. ``atr_value`` finito y **positivo** (un ATR ≤ 0 no construye geometría; antes se
           aceptaba un producto negativo, que colocaba el stop ENCIMA de la entrada).
        2. ``0 < stop < entry`` (el guard histórico).
        3. ``stop < price · (1 − min_gap)``: el stop de una posición LARGA tiene que quedar
           por DEBAJO del precio de mercado. Sin (3), una entrada equivocada producía un
           stop por encima del mercado que se disparaba en el mismo tick de la adopción
           (medido 2026-10-21: stop 12,9144 sobre mercado 10,42).
        """
        multiplier = Decimal(str(self._v2_tunables.atr_multiplier))
        if multiplier <= 0:
            return None, "atr_multiplier_not_positive"
        try:
            atr_decimal = Decimal(str(atr_value))
        except (InvalidOperation, TypeError, ValueError):
            return None, "atr_not_numeric"
        if not atr_decimal.is_finite() or atr_decimal <= 0:
            return None, "atr_not_positive"
        candidate = entry - multiplier * atr_decimal
        if candidate <= 0:
            return None, "stop_not_positive"
        if candidate >= entry:
            return None, "stop_above_entry"
        ceiling = price * (Decimal("1") - _ADOPTION_MIN_STOP_GAP)
        if candidate >= ceiling:
            return None, "stop_above_market"
        return candidate, "ok"

    def _v2_declare_adoption_without_stop(
        self,
        symbol: str,
        *,
        held: Decimal,
        entry: Decimal,
        price: Decimal,
        atr_value: Any,
        atr_source: str | None,
        entry_source: str,
        reason: str,
        at: str,
    ) -> PositionState | None:
        """W-159-2 — adopta la posición SIN stop y lo declara con los datos medidos.

        Antes este caso devolvía ``None``: la posición quedaba fuera de ``_v2_positions`` y
        el turno la vetaba como ``hold_no_op``, es decir, VIVA y MUDA (con V2 ON la política
        legacy no se evalúa). Adoptar sin stop la deja gestionada y visible: el estado es
        ``RECONCILIATION_REQUIRED``/``PROTECTION_MISSING`` y el journal durable guarda la
        entrada, el precio, el ATR y su fuente — lo que faltó para depurar el 2026-10-21.
        """
        plan: dict[str, object] = {
            "decisionId": f"adopted-{symbol}",
            "instrumentId": symbol,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": float(entry),
            # Sin stop: no se inventa un nivel que el plan nunca tuvo.
            "structuralStop": None,
            "target1": None,
            "target2": None,
            "adopted": True,
        }
        adopted_cycle = (self._canonical_attribution.get(symbol) or {}).get("cycleId")
        position = build_position_state_from_fill(
            plan,
            fill_price=float(entry),
            fill_quantity=float(held),
            filled_at=at,
            max_holding_period_days=resolve_holding_horizon(
                self._v2_tunables.exit_template
            ).max_holding_period_days,
            cycle_id=str(adopted_cycle) if adopted_cycle else None,
        )
        if position is None:
            return None
        logger.warning(
            "auto_sim v2 adoption without valid geometry symbol=%s entry=%s price=%s "
            "atr=%s atrSource=%s entrySource=%s (sin stop: se declara)",
            symbol,
            entry,
            price,
            atr_value,
            atr_source,
            entry_source,
        )
        return self._v2_degrade_adoption(
            symbol,
            position,
            source="none",
            reason=reason,
            at=at,
            entry=entry,
            price=price,
            atr_value=atr_value,
            atr_source=atr_source,
            entry_source=entry_source,
        )

    def _v2_degrade_adoption(
        self,
        symbol: str,
        position: PositionState,
        *,
        source: Literal["plan", "reconstructed", "none"],
        reason: str,
        at: str,
        entry: Decimal | None = None,
        price: Decimal | None = None,
        atr_value: Any = None,
        atr_source: str | None = None,
        entry_source: str | None = None,
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
        detail: dict[str, Any] = {
            "source": source,
            "reason": reason,
            "reasonCode": PROTECTION_MISSING,
            "stop": degraded.current_stop,
            "attention": "high",
        }
        # W-159-1 (Hueco C): los datos con los que se construyó (o no) la geometría van al
        # hecho durable. Sin ellos, un stop imposible no es depurable a posteriori.
        if entry is not None:
            detail["entry"] = float(entry)
        if entry_source is not None:
            detail["entrySource"] = entry_source
        if price is not None:
            detail["price"] = float(price)
        if atr_value is not None:
            detail["atr"] = atr_value
        if atr_source is not None:
            detail["atrSource"] = atr_source
        self._journal_position_event(symbol, RECONCILIATION_REQUIRED, at=at, detail=detail)
        logger.warning(
            "auto_sim v2 adoption degraded symbol=%s source=%s reason=%s stop=%s",
            symbol,
            source,
            reason,
            degraded.current_stop,
        )
        return degraded

    def _v2_declare_unmanaged_position(self, symbol: str, price: Decimal) -> None:
        """S-5 — la posición está VIVA y AUTO **no la gestiona**: se declara, no se calla.

        El caso es fail-safe por diseño: sin ``PositionState`` y con la adopción imposible
        (sin base de coste, sin ATR o con un plan ilegible) el worker NO inventa una venta.
        Lo que no era aceptable es que el hueco fuese indistinguible de «no hay nada que
        hacer»: ``_v2_position_package`` devolvía ``None`` y el turno lo contaba como
        ``hold_no_op``. La causa ya viaja por su propio motivo (``reconciliation_required``
        / ``protection_missing``); esta fila publica la CONSECUENCIA —el símbolo queda fuera
        del motor V2 y sólo una intervención humana lo devuelve— con la cantidad y el precio
        medidos en el instante.

        Una vez por símbolo y barra: la condición persiste, así que repetirla cada 60 s
        convertiría el journal en un latido. El set se reinicia al cambiar de barra: si la
        posición sigue sin gestión, el día siguiente vuelve a declararlo.
        """
        bar = self._v2_current_bar_start()
        if bar != self._v2_unmanaged_bar:
            self._v2_unmanaged_bar = bar
            self._v2_unmanaged_symbols.clear()
        if symbol in self._v2_unmanaged_symbols:
            return
        self._v2_unmanaged_symbols.add(symbol)
        at = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        held = self._open.get(symbol, Decimal("0"))
        self._journal_position_event(
            symbol,
            POSITION_UNMANAGED,
            at=at,
            detail={
                "held": str(held),
                "price": float(price),
                "bar": bar,
                "reason": "no_position_state",
                "management": "none",
                "attention": "high",
            },
        )
        logger.warning(
            "auto_sim v2 position unmanaged symbol=%s held=%s (sin estado V2 y sin adopción)",
            symbol,
            held,
        )

    async def _v2_position_package(
        self,
        symbol: str,
        price: Decimal,
        *,
        bar_low: float | None = None,
        bar_high: float | None = None,
    ) -> DecisionPackage | None:
        """Intención de gestión de la posición abierta (PositionManager) o ``None``.

        Requiere un ``PositionState`` V2 vivo para el símbolo. Si no lo hay (posición
        readoptada tras un reinicio) se ADOPTA (degradada si el estado no es verificable)
        para no dejar la posición sin stop; solo si la adopción no es posible se devuelve
        ``None`` y la gestión cae a la política clásica (fail-safe).

        AUTO-2: además de la orden, esta función **aplica y persiste el ratchet de stop**
        (``stop_update`` de un ``PROTECT``) y journaliza el resultado. Antes el stop
        propuesto se descartaba y ``current_stop`` quedaba congelado en el valor de
        nacimiento: ni break-even ni trailing existían en AUTO.

        C-4: la adopción consulta aquí (async, una sola vez por símbolo y sólo cuando no
        hay estado V2 vivo) si el coste del LIBRO es ambiguo — dos motores vivos sobre el
        mismo símbolo hacen que el medio de la cuenta no identifique a esta fila.
        """
        position: PositionState | None = self._v2_positions.get(symbol)
        degraded = False
        if position is None:
            # C-4 — la ambigüedad del coste del libro se mide UNA vez aquí (async) y viaja
            # como dato: ``_v2_adopt_position`` se mantiene síncrona (batería de crash).
            account_id = self._account_id or ""
            ledger_cost_ambiguous = (
                await self._cost_basis_is_ambiguous(account_id, symbol) if account_id else False
            )
            position = self._v2_adopt_position(
                symbol, price, ledger_cost_ambiguous=ledger_cost_ambiguous
            )
            if position is None:
                # S-5 — la causa (sin base de coste, sin ATR, plan ilegible) ya la declara
                # ``_v2_adopt_position``; lo que faltaba era la CONSECUENCIA: la posición
                # queda FUERA de la gestión V2. Sin esta fila el turno la contaba como un
                # ``hold_no_op`` benigno y la UI mostraba una posición abierta que AUTO no
                # iba a vender. Fail-safe igual (no se inventa una venta), pero ya no mudo.
                self._v2_declare_unmanaged_position(symbol, price)
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
            # P-2: el rango de la barra entra en la MISMA decisión; ``None`` conserva el
            # comportamiento previo (sólo ``open(B)``).
            bar_low=bar_low,
            bar_high=bar_high,
        )
        if isinstance(outcome, PositionManagerSkip):
            # AUTO-1A: la posición NO se pudo gestionar (mark rechazado / decisión no
            # construible). Antes el motivo se perdía y el libro de motivos del símbolo
            # quedaba vacío, indistinguible de "sin gestión pendiente".
            self._v2_last_exit_reasons[symbol] = (outcome.reason,)
            self._v2_last_exit_plans[symbol] = None
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
        # S-6 — el plan que produjo la decisión queda disponible para F5. ``None`` cuando
        # no hay gestión (hold benigno): la salida no existe, así que no hay nada que
        # autorizar y no se inventa un plan.
        self._v2_last_exit_plans[symbol] = outcome.exit_plan if outcome is not None else None
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
        # S-3: se anota la INTENCIÓN, no la transición. ``EXIT_PENDING`` sólo se sella
        # cuando la orden de venta sale de verdad (``_v2_confirm_exit_emitted``).
        self._v2_note_exit_intent(symbol, outcome, thesis_invalid=thesis_invalid)
        return position_manager_package(outcome)

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
        if position.holding_deadline_at is None:
            # Alarma: sin techo de mantenimiento TIME_STOP es inalcanzable y la posición
            # puede vivir indefinidamente. No cambia el comportamiento: lo hace visible.
            logger.warning("auto_sim position without holding_deadline symbol=%s", symbol)
            self._journal_position_event(
                symbol, "holding_deadline_missing", at=at, detail={"timeStop": "unreachable"}
            )
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
                    if any(
                        kind in ("TRAIL_ARMED", "TRAIL_ADVANCED") for kind, _ in protection_events
                    )
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

