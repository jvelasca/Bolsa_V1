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
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from bolsa_api.background.paper_auto_engine_worker import (
    DecisionProvider,
    _effective_venue,
    _kill_switch_env_on,
    _watch_symbols,
)
from bolsa_application.auto_daily_journal import SimJournalRow
from bolsa_application.auto_engine_state_store import (
    AutoEngineSnapshot,
    AutoEngineStore,
    AutoEngineTickInput,
)
from bolsa_application.decision_contract import (
    DecisionPackage,
    derive_execution_plan,
    risk_gate_auto_paper_dry,
    simulation_gate_allows,
)
from bolsa_application.execution_event import ExecutionEventStore
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    POSITION_PROJECTION_REBUILT,
    POSITION_PROJECTION_UNKNOWN,
    expected_position_from_events,
    reconcile_sim_position,
)
from bolsa_application.simulated_settlement import (
    auto_venue_order_id,
    normalized_auto_venue,
    submit_simulated_order,
)

logger = logging.getLogger(__name__)

AUTO_SIM_WORKER_ENABLED = "AUTO_SIMULATION_WORKER_ENABLED"
_FILL_CHUNKS = 4


def sim_worker_enabled() -> bool:
    """Env de habilitación (default OFF) del worker SIM-ONLY de A9/M5."""
    return (os.getenv(AUTO_SIM_WORKER_ENABLED) or "").strip().lower() not in {
        "",
        "0",
        "false",
        "no",
        "off",
    }


# ── Reloj / precio SIM deterministas (inyectables; "minutos simulados") ─────────
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


def flat_price_script(_symbol: str, _minute: int) -> float:
    """Precio plano determinista por defecto (sin movimientos del mercado)."""
    return 100.0


@dataclass(frozen=True, slots=True)
class ProtectionConfig:
    """V2.23/A9 (Bloque 6 · G8/G9) — protección autónoma determinista de posición.

    Es política pura (sin I/O): el worker la evalúa con el precio del ``price_script``
    y la posición abierta para forzar un SELL de protección (mismo gate/spine).
    """

    stop_pct: float = 0.02  # SL: cae ≥2% desde la entrada ⇒ salir.
    t1_pct: float = 0.02  # T1: sube ≥2% desde la entrada ⇒ tomar beneficio.
    trailing_pct: float = 0.015  # Trailing: retrocede ≥1.5% desde el máximo ⇒ salir.
    session_end_minute: int = 0  # >0 ⇒ cierre por fin de sesión (minuto simulado).
    # V2.24 / A9.1 (P2-06): T1 PARCIAL. Fracción de la posición que se toma en T1
    # (0.3 = vender 30%, dejar 70% con trailing). 1.0 = comportamiento antiguo (cierre
    # total). El resto se gestiona con trailing/stop.
    t1_fraction: float = 1.0
    enabled: bool = False  # fail-closed: sin activar, ninguna salida automática.

    def exit_reason(self, *, held: bool, entry: Decimal, high: Decimal, price: Decimal,
                    minute: int) -> str | None:
        """Razón de salida de protección (o None si no procede). Sólo con posición.

        V2.24 / A9.1 (P2-06): el ORDEN importa. Si el máximo ya superó el umbral T1
        (``high > entry*(1+t1_pct)``) el precio actual puede seguir por encima de T1 y
        haber retrocedido desde el máximo: eso es un ``trailing_stop`` real, no un
        ``t1_exit``. Antes se comprobaba T1 primero y se etiquetaba mal el motivo
        (misma acción, distinta historia en el journal). Ahora se evalúa el trailing
        antes que T1 cuando el máximo rebasó T1.
        """
        if not self.enabled or not held:
            return None
        if entry <= 0 or price <= 0:
            return None
        if self.session_end_minute and minute >= self.session_end_minute:
            return "session_close"
        if self.stop_pct > 0 and price <= entry * (Decimal(1) - Decimal(str(self.stop_pct))):
            return "protective_stop"
        high_above_t1 = (
            self.t1_pct > 0 and high > entry * (Decimal(1) + Decimal(str(self.t1_pct)))
        )
        trailing_hit = (
            self.trailing_pct > 0
            and high > entry
            and price <= high * (Decimal(1) - Decimal(str(self.trailing_pct)))
        )
        # Trailing tiene prioridad sobre T1 cuando el máximo ya rebasó T1 (un
        # retroceso desde un máximo alto es un trailing real, no una toma en T1).
        if trailing_hit and high_above_t1:
            return "trailing_stop"
        if self.t1_pct > 0 and price >= entry * (Decimal(1) + Decimal(str(self.t1_pct))):
            return "t1_exit"
        if trailing_hit:
            return "trailing_stop"
        return None

    def exit_fraction(self, reason: str | None) -> float:
        """Fracción de la posición a vender para una razón T1 (parcial) / resto 1.0."""
        if reason == "t1_exit" and 0 < self.t1_fraction < 1:
            return self.t1_fraction
        return 1.0


def _protection_config_from_env() -> ProtectionConfig:
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
    return ProtectionConfig(
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


class AutoSimulationWorker:
    """Driver determinista del día autónomo (por tick; hard SIM-ONLY).

    Mantiene el libro de posiciones abiertas entre turnos (``self._open`` por
    símbolo) y el journal completo del día. El settlement de cada intención
    aprobada va por ``submit_simulated_order`` (M1/M2). Sin ``exec_store`` la
    liquidación falla-cerrado (no abre ni llena; sin dinero). Sin LIVE nunca.
    """

    def __init__(
        self,
        *,
        decider: DecisionProvider | None = None,
        exec_store: ExecutionEventStore | None = None,
        auto_store: AutoEngineStore | None = None,
        price_script: PriceScript = flat_price_script,
        clock: Clock | None = None,
        finance_applier: Callable[[Any], Awaitable[bool]] | None = None,
        context_store: Any = None,
        position_store: Any = None,
        engine_id: str = "auto-sim",
        account_id: str | None = None,
        kill_switch_source: Callable[[], bool] | None = None,
        canonical_positions_reader: Any = None,
        require_account_id: bool = False,
    ) -> None:
        self._decider = decider
        self._exec_store = exec_store
        self._auto_store = auto_store
        self._price_script = price_script
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
        # V2.24/A9.1 (P2-06): T1 parcial ya ejecutado por símbolo (no re-dispara T1).
        self._t1_done: set[str] = set()
        self._minute = 0
        self._time = self._clock()
        self._open: dict[str, Decimal] = {}
        # V2.24/A9.1 (P1-03): identidades de orden lógicas únicas por intención, para
        # namespacear el ``execution_id`` (no colisión entre cuentas/engines).
        self._order_seq: int = 0
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
        events = getattr(self, "_applied_execution_events", None)
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
        canonical_map: dict[str, Decimal] = {
            str(s): Decimal(str(q)) for s, q in dict(canonical).items()
        }
        symbols = set(canonical_map) | set(projection)
        for symbol in symbols:
            verdict = reconcile_sim_position(
                symbol=symbol,
                execution_events=events,
                financial_positions=canonical_map,
                sim_auto_positions={s: r.quantity for s, r in projection.items()},
            )
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
                    )
            if verdict.status in {POSITION_PROJECTION_DIVERGENT, POSITION_PROJECTION_UNKNOWN}:
                logger.warning(
                    "auto_sim position reconciliation=%s symbol=%s (aperturas vetadas)",
                    verdict.status,
                    symbol,
                )
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
                )
        except Exception:  # noqa: BLE001 — el espejo durable nunca tumba el turno SIM.
            logger.exception("auto_sim persist_position failed symbol=%s", symbol)

    def _next_logical_order_id(self, symbol: str, side: str) -> str:
        """P1-03: identidad lógica única por INTENCIÓN (namespace del execution_id)."""
        self._order_seq += 1
        return f"{self._engine_id}-{self._minute}-{side}-{symbol}-{self._order_seq}"

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

    def _venue(self) -> str:
        return normalized_auto_venue(_effective_venue()) or "paper"

    def _advance(self) -> datetime:
        self._minute += 1
        self._time = self._clock()
        return self._time

    # ---- settlement vía dominio (M1/M2). Fail-closed sin exec_store. ----------
    async def _settle(self, side: str, symbol: str, qty: Decimal) -> list[FillObservation]:
        if self._exec_store is None:
            return []
        venue = self._venue()
        logical_order_id = self._next_logical_order_id(symbol, side)
        try:
            result, _out = await submit_simulated_order(
                self._exec_store,
                instrument_id=symbol,
                side=side,
                quantity=qty,
                # V2.23/A9 (P2-12): cuenta SIM inequívoca (nunca ``None`` en motor real).
                account_id=self._account_id,
                venue=venue,
                seed=self._minute * 100_003 + sum(map(ord, symbol)) % 9999,
                base_mid=self._price_script(symbol, self._minute) or 100.0,
                fill_chunks=_FILL_CHUNKS,
                order_id=f"auto-{side}-{symbol}-{self._minute}",
                # V2.24/A9.1 (P1-03): namespace de identidad (no colisión entre cuentas).
                engine_id=self._engine_id,
                logical_order_id=logical_order_id,
                owner="auto-sim-worker",
                apply_finance=self._finance_applier,
                context_store=self._context_store,
            )
        except Exception:  # noqa: BLE001 — un fallo de settlement no tumba el motor.
            # Fail-closed: un problema al persistir contexto/aplicar dinero NO debe
            # romper el turno AUTOnomo (se degrada a "sin fill este tick"). El motor
            # reintentará; jamás se fabrica una posición sin settlement confirmado.
            logger.exception("auto_sim settle failed symbol=%s side=%s", symbol, side)
            return []
        if not result.fills:
            return []
        vid = str(result.venue_order_id or "").strip() or f"sim-{side}-{symbol}"
        return [
            FillObservation(
                side=side,
                venue=venue,
                execution_id=f"{vid}#{f.fill_seq}",
                order_id=vid,
                qty=abs(f.qty_delta),
            )
            for f in result.fills
            if abs(f.qty_delta) > 0
        ]

    # ---- journal de fila: mantiene el día y ofrece el turno --------------------
    def _record_applied_event(
        self, symbol: str, fill: FillObservation, price: Decimal
    ) -> None:
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
        self, kind: str, venue: str, exec_id: str | None, side: str, qty: Decimal
    ) -> SimJournalRow:
        row = SimJournalRow(
            kind=kind,
            venue=venue,
            execution_id=exec_id or f"noex-{kind}",
            side=side,
            qty=qty,
        )
        self._journal.append(row)
        return row

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
            price = Decimal(str(self._price_script(symbol, self._minute) or 0))
            if held > 0 and price > 0:
                # Mantiene el máximo desde la entrada para el trailing (G9).
                prev_high = self._high_price.get(symbol, Decimal("0"))
                if price > prev_high:
                    self._high_price[symbol] = price
            prot = self._protection.exit_reason(
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
            if prot is not None:
                # V2.24/A9.1 (P2-06): T1 PARCIAL. La protección puede vender solo una
                # fracción (p. ej. 30%) y dejar el resto gestionado por trailing/stop.
                fraction = self._protection.exit_fraction(prot)
                sell_qty = (
                    held * Decimal(str(fraction))
                    if 0 < fraction < 1
                    else held
                )
                pkg = DecisionPackage(
                    action="SELL",
                    instrument_id=symbol,
                    quantity=float(sell_qty),
                    source=f"protection:{prot}",
                )
                reasons.append(prot)
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
            qty = Decimal(str(getattr(pkg, "quantity", None) or 0)).quantize(
                Decimal("0.000001")
            )
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
            fills = await self._settle(action.lower(), symbol, exec_qty)
            if not fills:
                continue  # fila no abierta: la cola SIM no confirmó fill (no LIVE).
            self._emit("order", venue, None, action.lower(), exec_qty)
            for o in fills:
                self._emit("fill", o.venue, o.execution_id, o.side, o.qty)
                self._record_applied_event(symbol, o, price)
            if action == "BUY":
                self._emit("position_open", venue, fills[0].execution_id, "buy", exec_qty)
                self._open[symbol] = held + exec_qty
                # Referencia de protección: entrada = precio del tick de apertura.
                if held <= 0 and price > 0:
                    self._entry_price[symbol] = price
                    self._high_price[symbol] = price
                await self._persist_position(symbol, held + exec_qty)
                report.opened += 1
            else:
                new_held = held - exec_qty
                if prot == "t1_exit" and new_held > 0:
                    # T1 parcial ejecutado: marca para no repetirlo.
                    self._t1_done.add(symbol)
                if new_held <= 0:
                    self._emit(
                        "position_close",
                        venue,
                        fills[0].execution_id,
                        "sell",
                        exec_qty,
                    )
                    report.closed += 1
                    self._entry_price.pop(symbol, None)
                    self._high_price.pop(symbol, None)
                    self._t1_done.discard(symbol)
                self._open[symbol] = new_held
                await self._persist_position(symbol, new_held)
            report.orders += 1
            report.fills += len(fills)
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
            await self._auto_store.record_tick(
                AutoEngineTickInput(
                    engine_id=self._engine_id,
                    venue=report.venue,
                    state="RUNNING",
                    seq=seq,
                    proposals=report.proposals,
                    vetoes=report.vetoes,
                    pending_plans=len(self.open_symbols),
                    last_reason=("auto-sim-durable",),
                    occurred_at=self._time,
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
    ) -> TurnReport:
        """Un turno con autoridad (gates) persistiendo tick durable (opcional).

        Se enlazan por-ciclo los stores/account (sesión por tick del scheduler) y se
        delega en ``auto_turn`` (misma Single Decision Spine del Bloque 3). El estado
        ``_open``/``_journal`` del worker se conserva entre turnos en el proceso; en
        el PRIMER turno de un proceso se readopta la posición durable (Bloque 5 /
        G7) para no re-comprar tras crash. Restaura los valores anteriores al
        terminar para no dejar fugas entre ticks.
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
        try:
            self._exec_store = exec_store
            self._auto_store = auto_store
            self._finance_applier = finance_applier
            self._account_id = account_id
            self._context_store = context_store if context_store is not None else prev_ctx
            self._position_store = (
                position_store if position_store is not None else prev_pos
            )
            self._canonical_positions_reader = (
                canonical_positions_reader
                if canonical_positions_reader is not None
                else prev_canon
            )
            # V2.24/A9.1 (P1-04): sin cuenta inequívoca NO se readopta ni opera el
            # camino durable; auto_turn veta igualmente (defensa en profundidad).
            if not self._readopted and self._account_id:
                # Readopción una sola vez por proceso (crash/restart ⇒ adoptar posición).
                await self.readopt_positions()
            report = await self.auto_turn()
            if auto_store is not None:
                snap: AutoEngineSnapshot | None = await auto_store.read(self._engine_id)
                seq = (snap.ticks + 1) if snap is not None else 1
                await auto_store.record_tick(
                    AutoEngineTickInput(
                        engine_id=self._engine_id,
                        venue=report.venue,
                        state="RUNNING",
                        seq=seq,
                        proposals=report.proposals,
                        vetoes=report.vetoes,
                        pending_plans=len(self.open_symbols),
                        last_reason=(self._last_gate_reason or ("idle",)),
                        occurred_at=self._time,
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


def _compose_canonical_reader(session: Any) -> Any:
    """V2.24/A9.1 (P1-01): lector del estado financiero CANÓNICO de la cuenta.

    Devuelve ``account_id -> {symbol: qty}`` desde las posiciones canónicas
    (``position_state`` abiertas del portfolio). Es la autoridad contra la que se
    reconcilia/reconstruye la proyección ``sim_auto_positions``. Fail-safe: si el
    repositorio no está disponible, devuelve ``{}`` (el reconciliador marcará
    ``UNKNOWN`` y vetará aperturas, sin inventar posición).
    """
    from bolsa_infrastructure.database.repositories.position_state_repository import (  # noqa: PLC0415
        SqlAlchemyPositionStateRepository,
    )

    async def _read(account_id: str) -> dict[str, Decimal] | None:
        try:
            rows = await SqlAlchemyPositionStateRepository(session).list_open_for_account(
                account_id
            )
        except Exception:  # noqa: BLE001 — sin canónico no se inventa posición.
            logger.exception("auto_sim canonical positions read failed")
            return None
        out: dict[str, Decimal] = {}
        for row in rows:
            qty = row.position_state.get("remainingQuantity")
            if qty is None:
                qty = row.position_state.get("quantity")
            if qty is None:
                continue
            try:
                value = Decimal(str(qty))
            except (ArithmeticError, ValueError):
                continue
            if value > 0:
                out[str(row.instrument_id)] = out.get(str(row.instrument_id), Decimal("0")) + value
        return out

    return _read


async def auto_sim_loop(
    runtime: AutoSimRuntime,
    *,
    interval_seconds: float = 60.0,
) -> None:
    """Task periódica (SIM-ONLY) del scheduler; no avanza si el gate está OFF.

    V2.23/A9 (Bloque 2): cada tick corre ``runtime.run_tick()``, que abre UNA sesión
    de PostgreSQL y compone los stores + finanzas SIM reales sobre ella. El runtime
    conserva el ``AutoSimulationWorker`` entre turnos (estado ``_open`` del día en
    RAM; la materia durable de crash/restart es del Bloque 5). NUNCA arranca un
    ``AutoSimulationWorker()`` desnudo.
    """
    logger.info("AutoSimulationWorker (SIM-ONLY) loop iniciado (tick=%ss)", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        if not sim_worker_enabled():
            continue
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
    ) -> None:
        self._session_factory = session_factory
        self._engine_id = engine_id
        self._account_id = account_id
        self._finance_resolver = finance_resolver
        # V2.24/A9.1 (P1-01): lector canónico inyectable (por defecto se compone por
        # sesión desde ``position_state``). Sin él, la reconciliación es UNKNOWN.
        self._canonical_reader = canonical_positions_reader
        if worker is None:
            worker = AutoSimulationWorker(
                decider=decider,
                engine_id=engine_id,
                account_id=account_id,
                require_account_id=True,
            )
        self._worker = worker

    @property
    def worker(self) -> AutoSimulationWorker:
        return self._worker

    async def run_tick(self) -> TurnReport | None:
        """Un turno real: abre sesión, compone stores PG + finanzas, y lo conduce.

        Cada tick compone también el espejo durable de posición (``sim_auto_positions``,
        Bloque 5/P1-06) sobre la MISMA sesión. En el primer tick del proceso,
        ``real_turn`` readopta la posición durable (G7: no segundo BUY tras crash);
        los ticks siguientes ya operan con ``_open`` en memoria + espejo por cambio.
        """
        from bolsa_application.sim_durable_store import (  # noqa: PLC0415
            PostgresSimAutoPositionStore,
        )

        async with self._session_factory() as session:
            exec_store, auto_store, applier, context_store = _compose_real_stores(
                session,
                finance_resolver=self._finance_resolver,
            )
            position_store = PostgresSimAutoPositionStore(session)
            return await self._worker.real_turn(
                exec_store=exec_store,
                auto_store=auto_store,
                finance_applier=applier,
                account_id=self._account_id,
                context_store=context_store,
                position_store=position_store,
                canonical_positions_reader=self._canonical_reader or _compose_canonical_reader(
                    session
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
        "1", "true", "yes", "on",
    }
    lot = float(os.getenv("AUTO_ENGINE_SIM_LOT_QTY") or "100.0")
    return deterministic_auto_decider(watch, lot_qty=lot, enabled=enabled)


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
    if session_factory is None:
        # Sin composición PG no creamos un runtime "real"; degradamos al worker
        # inyectado (tests/hermético) o construimos uno SOLO si viene cableado.
        if worker is None:
            logger.warning(
                "auto_sim_worker sin session_factory y sin worker: no se arranca "
                "ningún runtime (evita un AutoSimulationWorker() desnudo)."
            )
            return None
        runtime: Any = _HermeticRuntime(worker)  # helper local definido abajo
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
        )
    return asyncio.create_task(
        auto_sim_loop(runtime, interval_seconds=_sim_interval_seconds(interval_seconds))
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

