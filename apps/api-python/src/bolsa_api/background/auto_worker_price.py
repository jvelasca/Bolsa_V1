"""Precio, barras, regimen y coste del worker AUTO (slice 1).

Extraido con ``Delta motor = 0``: metodos movidos verbatim desde
``auto_simulation_worker``. El estado vive en la instancia (``self``).
"""
# mypy: disable-error-code="attr-defined"  # atributos definidos en __init__ del facade
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_REGIME_UNKNOWN,
)
from bolsa_analytics.cognitive.operational_governor import (
    coerce_market_regime,
    to_market_regime,
)
from bolsa_analytics.cognitive.signal_identity import bar_window
from bolsa_api.background.auto_price_provider import (
    price_source_kind,
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
from bolsa_application.auto_reason_codes import (
    ATR_SOURCE_FALLBACK,
    ATR_SOURCE_MISSING,
    ATR_SOURCE_REAL,
    OPPORTUNITY_TRADED,
)
from bolsa_application.price_source_kind import (
    PRICE_SOURCE_SCRIPT,
    PRICE_SOURCE_SYNTHETIC,
)

# P9 (auditoría .183): normalizadores FINITOS del dominio (``isfinite``). Los locales del camino
# de dinero solo filtraban ``NaN``, así que un ``inf`` de una división por cero llegaba a precios,
# cantidades y marcas y pasaba el filtro ``> 0``.
from bolsa_domain.numeric import finite_float, finite_positive, finite_range


class _PriceMixin:
    """Slice del worker AUTO; sin estado propio de clase."""

    def atr_source_counts(self) -> Mapping[str, int]:
        """V2.42 slice 2c: procedencia del ATR de las candidatas del día (medición).

        Cuenta las señales evaluadas por origen (``real``/``fallback``/``missing``): es la
        medición con la que se decide el flip del veto de ATR (D3), no un juicio. Sin
        señales el mapa queda a cero (jamás se asume una procedencia).
        """
        return dict(self._v2_atr_source_counts)

    def _safe_price_script(self, symbol: str, tick: int) -> Any:
        """M9: una excepción del ``price_script`` es «no hay precio» (como en ``PriceSource``)."""
        try:
            return self._price_script(symbol, tick)
        except Exception:  # noqa: BLE001 — un fallo de precio ES «no hay precio».
            logger.exception("auto_sim v2 price_script failed symbol=%s", symbol)
            return None

    def _v2_price_exec(self, symbol: str, tick: int) -> float | None:
        """Precio de EJECUCIÓN/MARCA del tick — o ``None`` si **no hay precio**.

        Sin fuente real (``price_source is None``) se lee ``price_script`` **en vivo** con
        el MISMO ``tick`` que usaba cada llamante ⇒ comportamiento byte a byte idéntico al
        anterior (``Δ = 0``): el fail-closed sólo puede dispararse con una fuente real.
        """
        source = self._price_source
        if source is None:
            value = self._safe_price_script(symbol, tick)
            if value is None:
                return None
            # P9: ``NaN``/``inf`` de la fuente hermética tampoco es un precio.
            price = finite_float(value)
            if price is None:
                self._v2_note_price_missing(symbol)
            return price
        try:
            price = finite_float(source.execution(symbol))
        except Exception:  # noqa: BLE001 — un fallo de precio ES «no hay precio».
            logger.exception("auto_sim v2 price_source.execution failed symbol=%s", symbol)
            return None
        if price is None:
            # P9: la fuente respondió algo que no es un número finito. Se declara como precio
            # AUSENTE en vez de propagar ``inf`` a precios, marcas y equity.
            self._v2_note_price_missing(symbol)
        return price

    def _v2_price_mid(self, symbol: str, tick: int) -> float | None:
        """Precio de DECISIÓN (con fuente real, ``close`` de la última barra cerrada).

        Mismo contrato de ``Δ = 0`` que ``_v2_price_exec`` para el camino hermético.
        """
        source = self._price_source
        if source is None:
            value = self._safe_price_script(symbol, tick)
            return None if value is None else finite_float(value)
        try:
            price = finite_float(source.mid(symbol))
        except Exception:  # noqa: BLE001
            logger.exception("auto_sim v2 price_source.mid failed symbol=%s", symbol)
            return None
        if price is None:
            # P9: el precio de DECISIÓN no puede ser ``inf``: se trata como ausente.
            self._v2_note_price_missing(symbol)
        return price

    def _v2_bar_extremes(self, symbol: str) -> tuple[float | None, float | None]:
        """``(low, high)`` de la barra corriente — ``(None, None)`` si la fuente no los da.

        P-2: sin fuente real (``price_script`` hermético) no hay extremos y la gestión es
        **byte-idéntica** a la anterior. Un campo ausente o un lector que falle se declara
        ``None`` (nunca se fabrica un rango): el fail-closed es "no verlo", no inventarlo.
        """
        source = self._price_source
        if source is None:
            return (None, None)

        def _read(name: str) -> float | None:
            reader = getattr(source, name, None)
            if not callable(reader):
                return None
            try:
                value = reader(symbol)
            except Exception:  # noqa: BLE001 — un extremo ilegible no tumba el tick.
                logger.exception("auto_sim v2 price_source.%s failed symbol=%s", name, symbol)
                return None
            return None if value is None else finite_float(value)

        # P9: un rango invertido o no finito es un dato corrupto, no una señal: ``(None, None)``.
        return finite_range(_read("low"), _read("high")) or (None, None)

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

    def _v2_regime(self) -> str | None:
        """Régimen operativo del tick (override de env > fuente inyectada > None).

        Sin régimen el pipeline V2 queda en UNKNOWN ⇒ exit-only (fail-closed): no se
        abren entradas nuevas si no se puede determinar el régimen.

        ADR-047: este valor es el **agregado** del tick y se usa como DECLARACIÓN de
        contexto (``marketRegime``) y como dial del gobernador; el veto de entrada usa
        ``_v2_regime_by_symbol``.
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

    def _v2_regime_by_symbol(self) -> dict[str, str] | None:
        """Régimen de barras por símbolo del tick (ADR-047).

        ``None`` deja el comportamiento histórico (un solo eje global): ocurre cuando la
        fuente no expone ``by_symbol`` o cuando hay ``regime_override`` (dial de
        entorno/test, no una medición por símbolo). Con mapa, un símbolo ausente será
        ``UNKNOWN`` para la barrera: se declara el hueco, no se hereda un mercado benigno.
        """
        if self._v2_tunables.regime_override:
            return None
        reader = getattr(self._v2_regime_source, "by_symbol", None)
        if reader is None or not callable(reader):
            return None
        try:
            labels = reader() or {}
        except Exception:  # noqa: BLE001 — sin mapa se conserva el eje global.
            logger.exception("auto_sim v2 regime by_symbol failed")
            return None
        return {str(symbol): str(label or "") for symbol, label in dict(labels).items()}

    def _v2_equity(self) -> float:
        """Equity del tick.

        El turno real (``load_book_equity``) usa el cash y el valor de mercado del
        libro. Si esa lectura falta o no es positiva, devuelve 0 y las aperturas
        quedan vetadas: no hay caída a ``AUTO_ENGINE_SIM_V2_EQUITY`` ni a 100_000.
        El camino hermético, que no carga el libro, conserva el env o 100_000.
        """
        equity, _unreadable = turn_equity_from_book(
            self._book_equity_snapshot.equity,
            required=self._book_equity_required,
            unreadable=self._book_equity_snapshot.unreadable,
            env_raw=(os.getenv("AUTO_ENGINE_SIM_V2_EQUITY") or "").strip(),
        )
        return equity

    @property
    def book_equity_as_of(self) -> str | None:
        """M14: instante de la foto de equity vigente (``None`` = no medido este turno)."""
        return self._book_equity_snapshot.as_of

    @property
    def book_equity_unreadable(self) -> bool:
        """M14: la foto vigente declara que la lectura no se pudo hacer."""
        return self._book_equity_snapshot.unreadable

    def _v2_marks_now(self) -> Any:
        """Instante UTC de la marca de equity (inyectable en tests vía ``_time``)."""
        raw = self._time.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

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
        # P9: la liquidez es un DENOMINADOR; un ``inf``/``NaN`` aquí no es un dato medido.
        return finite_positive(value)

    def _v2_bar_datum_loaded(self) -> bool:
        """``W2`` — ¿el dato de barra (régimen y ATR) está cargado en ESTA instancia?

        El cortocircuito por barra reutiliza el dato entre ticks, pero el runtime real
        (`AutoSimRuntime.run_tick`) **recompone las fuentes por sesión/tick**: la instancia
        que llega al turno reutilizado es NUEVA y está vacía. Asumir lo contrario dejaba el
        régimen sin etiquetas y el ATR ausente durante toda la barra.

        Medido 2026-10-21 (ventana PAPER, motor `auto-window-1484e253`): 275 de 280
        entradas evaluadas cayeron por `regime_invalid` con `entryRegime=UNKNOWN`
        (`entryRegimeScope=per_symbol`, es decir mapa presente pero vacío) y el ATR real
        no llegó nunca con `AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` ⇒ 0 propuestas, 0 fills.
        Con el mapa real, la misma función pura aprueba los símbolos en rango.

        Fail-closed: una fuente sin lector de estado se da por cargada (no se inventa I/O
        nuevo para fuentes que no lo declaran); una fuente que declara ``loaded()=False``
        fuerza el refresco aunque el dato de barra se reutilice.
        """
        for source in (self._v2_regime_source, self._v2_atr_source):
            probe = getattr(source, "loaded", None)
            if probe is None or not callable(probe):
                continue
            try:
                if not probe():
                    return False
            except Exception:  # noqa: BLE001 — sin poder afirmar el dato, se relee.
                logger.exception("auto_sim v2 bar datum probe failed")
                return False
        return True

    async def _v2_refresh_regime(self) -> None:
        """Refresca el régimen y el ATR si las fuentes lo soportan (async + lectura sync).

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
            self._v2_consumed_unpersisted.clear()

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
            self._v2_tick_signals.get(symbol) not in self._v2_consumed_signals for symbol in entries
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

    def _adoption_cost_basis(
        self,
        symbol: str,
        *,
        canonical_ambiguous: bool = False,
    ) -> tuple[Decimal | None, str]:
        """W-159-2 — base de coste de una adopción: el LIBRO manda, el espejo respalda.

        El espejo (``sim_auto_positions.entry_price``) es una proyección: puede venir de una
        fila obsoleta de otro motor o de una reconstrucción anterior. El libro de fills
        aplicados es el hecho financiero. Se devuelve la fuente usada para que el journal
        durable (Hueco C) pueda distinguir "coste del libro" de "coste del espejo" sin
        reinterpretar nada.

        C-4 (auditoría .161) — ``canonical_ambiguous`` (lo mide
        :meth:`_cost_basis_is_ambiguous`, que es async) significa que el coste del libro es
        el MEDIO DE LA CUENTA y no identifica a esta fila: hay más de un motor vivo sobre
        el símbolo. En ese caso el libro no autoriza el número y la adopción usa el espejo,
        que sí es de ESTE motor, declarando la fuente. Sin espejo no se inventa un coste:
        se devuelve ``None`` con ``ledger_ambiguous`` para que el llamante lo declare.
        """
        canonical = self._canonical_entry_by_symbol.get(symbol)
        if canonical is not None and canonical > 0:
            if not canonical_ambiguous:
                return canonical, ADOPTION_COST_SOURCE_LEDGER
            mirror = self._entry_price.get(symbol)
            if mirror is not None and mirror > 0:
                return mirror, ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER
            return None, ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS
        mirror = self._entry_price.get(symbol)
        if mirror is not None and mirror > 0:
            return mirror, ADOPTION_COST_SOURCE_PROJECTION
        return None, ADOPTION_COST_SOURCE_NONE

    async def _cost_basis_is_ambiguous(self, account_id: str, symbol: str) -> bool:
        """W-159-5 (Hueco E) — ¿el coste del LIBRO identifica a ESTA fila?

        La cura de ``entry_price`` (V2.88.159) escribe el coste medio de la CUENTA sobre
        una fila POR MOTOR. Mientras el símbolo tenga UNA sola fila viva eso es
        exactamente la posición; con dos motores vivos (medido 2026-10-21: ``3204115d``
        ×2 con 1933.3953 cada uno, ``ver=None`` en uno) el coste de la cuenta ya no
        identifica a ninguna de las dos filas. No se inventa un reparto: se declara y no
        se cura. Un lector que falle también se lee como ambiguo (no se autoriza el
        número), y un store sin la capacidad se lee como el caso canónico de un motor.
        """
        store = self._position_store
        reader = getattr(store, "read_live_engines", None)
        if reader is None:
            return False
        try:
            engines = await reader(account_id, symbol)
        except Exception:  # noqa: BLE001 — sin lector fiable no se fabrica un coste.
            logger.exception("auto_sim live engine rows read failed symbol=%s", symbol)
            return True
        return len({str(engine) for engine in engines}) > 1

