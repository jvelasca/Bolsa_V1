"""V2.22 / A9 (M3·M4) — PaperAutoEngineWorker continuo (SAFE/dry + DecisionSpine + durable).

Unifica el espina continuo (antes solo disparado por HTTP PaperDesk/Paper-D) bajo
un worker autónomo no-HTTP, cableado en el scheduler. **SAFE/dry**: cada tick
nada ejecuta dinero real por sí; solo corre el RiskGate determinista sobre un
``DecisionPackage`` (proposiciones/planes SIM) y publica telemetría de estado
AUTO: RUNNING / PAUSED / BLOCKED / DEGRADED / REQUIRES_ATTENTION (solo lectura).

A9 (M3/M4) hace durable + decider SIN tocar la SAFE de V2.21 ni la doble barrera
LIVE (M0 intacta; AUTO es SOLO paper/simulated; nunca se construye bridge LIVE):

* **M3 (Decision Spine)**: `PaperAutoEngine` acepta un ``DecisionProvider``
  inyectado (no-HOLD real) cuyo default sigue HOLD-safe. El RiskGate determinista
  otorga/veta y jamás ejecuta dinero por proponer.
* **M4 (estado durable, P2 audit)**: la telemetría en-memoria se puede espejar en
  PostgreSQL via ``bolsa_application.auto_engine_state_store`` (Protocol +
  InMemory + Postgres) y la migración Alembic ``027`` (``auto_engine_runs`` /
  ``auto_engine_ticks``). Un worker reiniciado readopta RUNNING + contadores SIN
  doblar tick tras crash. Fail-closed: sin store (DB off / tests hermeticos) sigue
  en-memoria exactamente como V2.21/A8.

Env (M4): nombres canónicos ``AUTO_ENGINE_SIMULATED_*`` se prefieren sobre los
alias retrocompat ``AUTO_ENGINE_DRY_*`` (que se mantienen funcionando; los tests
existentes siguen fijando los DRY y el worker los lee ambos, prefiriendo SIM).
Default OFF: sin env de enable no se arranca task.

Seguridad P0: ninguna fase abre la vía REAL ni cierra la doble barrera LIVE;
kill switch activo ⇒ BLOCKED; venue fuera de {paper, simulated} ⇒
REQUIRES_ATTENTION. AUTO es SIM-ONLY por diseño.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from bolsa_application.auto_engine_state_store import (
    AutoEngineSnapshot,
    AutoEngineStore,
    AutoEngineTickInput,
)
from bolsa_application.decision_contract import (
    DecisionPackage,
    derive_execution_plan,
    risk_gate_auto_paper_dry,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
# V2.22/A9 (M4): alias retrocompat ``AUTO_ENGINE_DRY_*`` (se mantienen; los tests
# existentes los fijan); canónicos ``AUTO_ENGINE_SIMULATED_*`` (se prefieren).
_ENV_ENABLED = "AUTO_ENGINE_DRY_ENABLED"
_ENV_INTERVAL = "AUTO_ENGINE_DRY_INTERVAL_SECONDS"
_ENV_WATCH = "AUTO_ENGINE_DRY_WATCH"
_ENV_VENUE = "AUTO_ENGINE_DRY_VENUE"
_ENV_SIM_ENABLED = "AUTO_ENGINE_SIMULATED_ENABLED"
_ENV_SIM_INTERVAL = "AUTO_ENGINE_SIMULATED_INTERVAL_SECONDS"
_ENV_SIM_WATCH = "AUTO_ENGINE_SIMULATED_WATCH"
_ENV_SIM_VENUE = "AUTO_ENGINE_SIMULATED_VENUE"


AutoEngineState = Literal[
    "RUNNING",
    "PAUSED",
    "BLOCKED",
    "DEGRADED",
    "REQUIRES_ATTENTION",
]


def _prefer_sim(name_sim: str, name_dry: str) -> str | None:
    """Lee una env prefiriendo el nombre canónico SIM over el alias retrocompat."""
    sim = (os.getenv(name_sim) or "").strip()
    if sim:
        return sim
    return (os.getenv(name_dry) or "").strip() or None


def _env_on(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() not in {"", "0", "false", "no", "off"}


def _enabled() -> bool:
    # Canónico SIM si está fijado; si no, alias DRY retrocompat.
    if (os.getenv(_ENV_SIM_ENABLED) or "").strip():
        return _env_on(_ENV_SIM_ENABLED)
    return _env_on(_ENV_ENABLED)


def _interval_seconds(default: float) -> float:
    raw = (_prefer_sim(_ENV_SIM_INTERVAL, _ENV_INTERVAL) or "").strip()
    try:
        return float(raw) if raw and float(raw) > 0 else default
    except ValueError:
        return default


def _watch_symbols() -> list[str]:
    raw = _prefer_sim(_ENV_SIM_WATCH, _ENV_WATCH) or "AAA,IBEX"
    return [s.strip() for s in raw.split(",") if s.strip()]


def _kill_switch_env_on() -> bool:
    """Kill switch READ-only (sin Redis): Settings + runtime memory. Nunca escribe."""
    from bolsa_application.risk_runtime import get_runtime_kill_switch_memory
    from bolsa_infrastructure.config import get_settings

    try:
        if bool(get_settings().risk_kill_switch):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return bool(get_runtime_kill_switch_memory())
    except Exception:  # noqa: BLE001
        return False


def _effective_venue() -> str:
    # A9/M4: canónico AUTO_ENGINE_SIMULATED_VENUE; alias DRY retrocompat.
    v = _prefer_sim(_ENV_SIM_VENUE, _ENV_VENUE) or "paper"
    return str(v).strip().lower()


@dataclass(frozen=True, slots=True)
class PaperAutoEngineDryReport:
    """Veredicto puro de un dry_tick sobre el Decision Spine."""

    proposals: int
    vetoes: int
    reasons: tuple[str, ...]
    # V2.22/A9 (M3): nº de símbolos cuyo DecisionPackage (no-HOLD) produjo un
    # ExecutionPlan SIM-ONLY válido a través del RiskGate (candidato a simular).
    pending_plans: int = 0


# V2.22/A9 (M3) — "IA / Decision Spine" conectada al AUTO como PROVEEDOR de
# propuestas. La puerta determinista (RiskGate) sigue otorgando/vetando; el
# proveedor inyectable solo indica intención por símbolo. Default HOLD-safe.
DecisionProvider = Callable[[str], DecisionPackage]


def _hold_decision_provider(symbol: str) -> DecisionPackage:
    """Proveedor por defecto del motor (A8): HOLD-safe, nunca ejecuta."""
    return DecisionPackage(
        action="HOLD",
        instrument_id=symbol,
        quantity=0.0,
        source="paper_auto_engine_dry",
    )


def dry_tick(
    *,
    watch: list[str] | None = None,
    kill_switch: bool,
    venue: str,
    decider: DecisionProvider | None = None,
) -> PaperAutoEngineDryReport:
    """Un ciclo puro y determinista por símbolo corriendo el RiskGate.

    Con ``decider=None`` (default) propone HOLD-safe por símbolo (A8); con un
    ``decider`` inyectado propone lo que el spine decida (A9/M3), pero SOLO pasa a
    *ExecutionPlan* (candidato sim) si el venue es AUTO-permitido y el kill switch
    está OFF. Nunca ejecuta dinero; devuelve conteos + razones + pending_plans.
    """
    syms = list(watch) if watch is not None else _watch_symbols()
    provider = decider if decider is not None else _hold_decision_provider
    prop = 0
    vetoes = 0
    pending_plans = 0
    reasons: set[str] = set()
    for sym in syms:
        sym = sym.strip()
        if not sym:
            continue
        pkg = provider(sym)
        gate = risk_gate_auto_paper_dry(pkg, kill_switch_active=kill_switch, venue=venue)
        if gate.allow_proposal:
            prop += 1
            if pkg.action != "HOLD":
                # A9/M3: una propuesta REAL puede emitir plan sim pendiente.
                plan = derive_execution_plan(pkg, venue=venue, kill_switch_active=kill_switch)
                if plan is not None:
                    pending_plans += 1
        else:
            vetoes += 1
            reasons.update(r.value for r in gate.reasons)
    return PaperAutoEngineDryReport(
        proposals=prop,
        vetoes=vetoes,
        reasons=tuple(sorted(reasons)),
        pending_plans=pending_plans,
    )


class PaperAutoEngine:
    """Motor AUTO SAFE / autónomo (telemetría en proceso; A9 M3 admite un
    proveedor de propuestas; A9 M4 puede espejarse a un store durable).

    Sin store (default) permanece totalmente en-memoria y SAFE — igual que
    V2.21/A8, de modo que los tests hermeticos siguen pasando con DB off.
    Con ``store`` un bucle durable puede readoptar/persistir ticks sin doblar.
    ``run_tick()`` es síncrono y no persiste; para persistir use el driver
    asíncrono durable (ver ``PaperAutoEngine.persist_tick`` / reina).
    """

    def __init__(
        self,
        decider: DecisionProvider | None = None,
        *,
        store: AutoEngineStore | None = None,
        engine_id: str = "paper-auto",
    ) -> None:
        self._state: AutoEngineState = "PAUSED"
        self._last_tick: str | None = None
        self._proposals = 0
        self._vetoes = 0
        self._pending_plans = 0
        self._last_reason: tuple[str, ...] = ("idle",)
        self._decider = decider
        self._store: AutoEngineStore | None = store
        self._engine_id = engine_id

    def readopt(self, snapshot: AutoEngineSnapshot | None) -> None:
        """Readopta del store durable (tras crash/relaunch; M4). Sin fila aún
        mantiene PAUSED en-memoria (primer run por venir)."""
        if snapshot is None:
            self._state = "PAUSED"
            return
        self._state = snapshot.state
        self._proposals = snapshot.proposals
        self._vetoes = snapshot.vetoes
        self._pending_plans = snapshot.pending_plans
        self._last_reason = snapshot.last_reason
        self._last_tick = snapshot.last_tick_at.isoformat() if snapshot.last_tick_at else None
        self._engine_id = snapshot.engine_id

    def counters(self) -> tuple[int, int, int]:
        """Acumulados actuales (proposals, vetoes, pending_plans) para perseguir."""
        return (self._proposals, self._vetoes, self._pending_plans)

    def apply_delta(self, report: PaperAutoEngineDryReport) -> None:
        """Suma un dry_tick al actor (acumulado monotónico)."""
        self._proposals += report.proposals
        self._vetoes += report.vetoes
        self._pending_plans += report.pending_plans
        self._last_reason = report.reasons or ("ok",)
        self._last_tick = datetime.now(UTC).isoformat()

    def run_tick(self) -> None:
        """Un tick (SAFE/dry) SIN persistir: reproduce V2.21/A8 exactamente, de
        modo que los tests existentes (y un tick sin store) siguen igual."""
        kill = _kill_switch_env_on()
        venue = _effective_venue()
        if kill:
            self._state = "BLOCKED"
            self._last_reason = ("kill_switch_active",)
            return
        if venue not in {"paper", "simulated"}:
            self._state = "REQUIRES_ATTENTION"
            self._last_reason = (f"venue_auto_restricted:{venue}",)
            return
        rep = dry_tick(kill_switch=kill, venue=venue, decider=self._decider)
        self._proposals += rep.proposals
        self._vetoes += rep.vetoes
        self._pending_plans += rep.pending_plans
        self._last_reason = rep.reasons or ("ok",)
        self._state = "RUNNING"
        self._last_tick = datetime.now(UTC).isoformat()

    async def persist_tick(
        self,
        store: AutoEngineStore,
        *,
        venue: str | None = None,
        occurred_at: datetime | None = None,
        seq_override: int | None = None,
    ) -> AutoEngineSnapshot | None:
        """Persiste (M4) un tick ya aplicado en-memoria sobre un store durable.

        Construye el tick durable carry los acumulados actuales con el siguiente
        ``seq`` (del snapshot readoptado si existe) y lo matricula. Devuelve el
        snapshot readoptado. No duplica: ``record_tick`` ignora seq ya presente.
        """
        eff_venue = venue if venue is not None else _effective_venue()
        prev = await store.read(self._engine_id)
        if seq_override is not None:
            seq = seq_override
        else:
            seq = (prev.ticks + 1) if prev is not None else 1
        tick = AutoEngineTickInput(
            engine_id=self._engine_id,
            venue=eff_venue,
            state=self._state,
            seq=seq,
            proposals=self._proposals,
            vetoes=self._vetoes,
            pending_plans=self._pending_plans,
            last_reason=self._last_reason or ("idle",),
            occurred_at=occurred_at or datetime.now(UTC),
        )
        await store.record_tick(tick)
        return await store.read(self._engine_id)

    def telemetry(self) -> dict[str, object]:
        return {
            "state": self._state,
            "lastTick": self._last_tick,
            "dryProposals": self._proposals,
            "dryVetoes": self._vetoes,
            "pendingPlans": self._pending_plans,
            "lastReason": ", ".join(self._last_reason),
        }


async def durable_tick(
    engine: PaperAutoEngine,
    store: AutoEngineStore,
    *,
    occurred_at: datetime | None = None,
) -> AutoEngineSnapshot | None:
    """Driver durable de un tick (M4): evalúa+persiste SIN doble matrícula.

    1. Readopta el snapshot durable (si no existe → arranque).
    2. Aplica un dry_tick sobre el motor.
    3. Persiste via ``engine.persist_tick``.
    Devuelve el snapshot final (la vista que un crash/relaunch releería).
    """
    snap = await store.read(engine._engine_id)
    if snap is not None:
        engine.readopt(snap)
    engine.run_tick()
    return await engine.persist_tick(
        store,
        occurred_at=occurred_at,
    )


async def paper_auto_engine_loop(
    engine: PaperAutoEngine,
    *,
    interval_seconds: float = TICK_SECONDS,
) -> None:
    logger.info("PaperAutoEngineWorker (SAFE/dry) iniciado tick=%ss", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        if not _enabled():
            continue
        try:
            if engine._store is not None:  # noqa: SLF001 — M4 durable
                await durable_tick(engine, engine._store)
            else:
                engine.run_tick()
        except Exception:  # noqa: BLE001 — un tick no tumba el motor.
            logger.exception("paper_auto_engine tick failed")
            engine._state = "DEGRADED"  # noqa: SLF001


def start_paper_auto_engine_worker(
    session_factory: object = None,  # legacy unused (SAFE/dry); M4 via store kwarg.
    *,
    engine: PaperAutoEngine | None = None,
    interval_seconds: float | None = None,
    store: AutoEngineStore | None = None,
) -> asyncio.Task[None] | None:
    """start hook para ``_event_loop_starters()`` del scheduler (SAFE/dry + M4).

    Sin env habilitado no arranca task (default OFF). Con ``store`` proporciona
    persistencia durable (Alembic 027); sin él queda el en-memoria SAFE clásico.
    """
    if not _enabled():
        logger.info("PaperAutoEngineWorker desactivado (%s=false/off)", _ENV_ENABLED)
        return None
    eng = engine if engine is not None else PaperAutoEngine(store=store)
    eff = _interval_seconds(interval_seconds or TICK_SECONDS)
    return asyncio.create_task(paper_auto_engine_loop(eng, interval_seconds=eff))
