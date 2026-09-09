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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from bolsa_application.auto_daily_journal import SimJournalRow
from bolsa_application.auto_engine_state_store import (
    AutoEngineSnapshot,
    AutoEngineStore,
    AutoEngineTickInput,
)
from bolsa_application.execution_event import ExecutionEventStore
from bolsa_application.simulated_settlement import (
    normalized_auto_venue,
    submit_simulated_order,
)

from bolsa_api.background.paper_auto_engine_worker import (
    DecisionProvider,
    _effective_venue,
    _watch_symbols,
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


# ── Modelo del día autónomo SIM ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FillObservation:
    """Un fill real confirmado por el settlement SIM (fuente del journal M7)."""

    side: str
    venue: str
    execution_id: str
    order_id: str
    qty: Decimal


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
        engine_id: str = "auto-sim",
    ) -> None:
        self._decider = decider
        self._exec_store = exec_store
        self._auto_store = auto_store
        self._price_script = price_script
        self._clock = clock if clock is not None else default_clock
        self._engine_id = engine_id
        # V2.22/a9 finance seam: un ``ApplyFinanceCallable`` opcional. Con None (default
        # hermético) los fills SIM quedan como hoy (``CAPTURED``, sin dinero). Con un
        # applier real, ``_settle`` lo reenvía como ``apply_finance`` de la liquidación.
        self._finance_applier = finance_applier
        self._minute = 0
        self._time = self._clock()
        self._open: dict[str, Decimal] = {}
        self._journal: list[SimJournalRow] = []

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
        result, _out = await submit_simulated_order(
            self._exec_store,
            instrument_id=symbol,
            side=side,
            quantity=qty,
            account_id=None,
            venue=venue,
            seed=self._minute * 100_003 + sum(map(ord, symbol)) % 9999,
            base_mid=self._price_script(symbol, self._minute) or 100.0,
            fill_chunks=_FILL_CHUNKS,
            order_id=f"auto-{side}-{symbol}-{self._minute}",
            owner="auto-sim-worker",
            apply_finance=self._finance_applier,
        )
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
        """Decide por símbolo y actúa (BUY abre / SELL reduce o cierra) SIM-ONLY."""
        self._advance()
        venue = self._venue()
        report = TurnReport(decided=0, venue=venue)
        for symbol in _watch_symbols():
            symbol = symbol.strip()
            if not symbol:
                continue
            report.decided += 1
            pkg = self._decider(symbol) if self._decider else None
            action = str(getattr(pkg, "action", "HOLD")).upper()
            qty = Decimal(str(getattr(pkg, "quantity", None) or 0)).quantize(Decimal("0.000001"))
            if action not in {"BUY", "SELL"} or qty <= 0:
                report.vetoes += 1
                continue
            held = self._open.get(symbol, Decimal("0"))
            if action == "BUY" and held > 0:
                continue  # ya expuesto: sin apilar.
            report.proposals += 1
            fills = await self._settle(action.lower(), symbol, qty)
            if not fills:
                continue  # fila no abierta: la cola SIM no confirmó fill (no LIVE).
            self._emit("order", venue, None, action.lower(), qty)
            for o in fills:
                self._emit("fill", o.venue, o.execution_id, o.side, o.qty)
            if action == "BUY":
                self._emit("position_open", venue, fills[0].execution_id, "buy", qty)
                self._open[symbol] = held + qty
                report.opened += 1
            else:
                new_held = (held - qty) if held >= qty else Decimal("0")
                if new_held == 0:
                    self._emit(
                        "position_close",
                        venue,
                        fills[0].execution_id,
                        "sell",
                        qty if held >= qty else held,
                    )
                    report.closed += 1
                self._open[symbol] = new_held
            report.orders += 1
            report.fills += len(fills)
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


async def auto_sim_loop(
    worker: AutoSimulationWorker,
    *,
    interval_seconds: float = 60.0,
) -> None:
    """Task periódica (SIM-ONLY) del scheduler; no avanza si el gate está OFF."""
    logger.info("AutoSimulationWorker (SIM-ONLY) loop iniciado (tick=%ss)", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        if not sim_worker_enabled():
            continue
        try:
            await worker.auto_turn()
        except Exception:  # noqa: BLE001 — un turno no debe tumbar el loop.
            logger.exception("auto_sim tick failed")


def start_auto_sim_worker(
    session_factory: Any = None,  # noqa: ARG001 — compatible con el scheduler.
    *,
    worker: AutoSimulationWorker | None = None,
    interval_seconds: float = 60.0,
) -> asyncio.Task[None] | None:
    """start hook para ``_event_loop_starters()`` (env-gated; default OFF, SIM)."""
    if not sim_worker_enabled():
        logger.info(
            "AutoSimulationWorker (%s) desactivado — SIM-ONLY por defecto.", AUTO_SIM_WORKER_ENABLED
        )
        return None
    if worker is None:
        worker = AutoSimulationWorker()
    return asyncio.create_task(auto_sim_loop(worker, interval_seconds=interval_seconds))
