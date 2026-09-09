"""V2.21 / A8 (M4) — PaperAutoEngineWorker continuo (SAFE /**dry**), telemetría.

Unifica el espina continuo (antes solo disparado por HTTP PaperDesk/Paper-D) bajo
UN worker autónomo no-HTTP, cableado en el scheduler. **SAFE/dry (decisión de
alcance)**: cada tick NADA ejecuta dinero por sí; solo corre el RiskGate
determinista sobre DecisionPackage (proposiciones) y publica telemetría de estado
AUTO: RUNNING / PAUSED / BLOCKED / DEGRADED / REQUIRES_ATTENTION (solo lectura
para la UI). Ningún camino toca la vía LIVE real (M0 la mantiene doble cerrada).

Seguridad P0: aunque una propuesta fuera BUY/SELL agresiva, este worker JAMÁS
resuelve un broker ni llena; guarda el estado sim. Pasar a EJECUCIÓN real en
PAPER/Simulated (un capa M4.futura) requeriría un paso posterior que venza
RiskGate + Simulation Gate + ``PAPER_D_EXECUTE`` — fuera de este alcance SAFE/dry.

Habilitado por config ``AUTO_ENGINE_DRY_ENABLED`` (default OFF). Cadencia
``AUTO_ENGINE_DRY_INTERVAL_SECONDS``. Watch por ``AUTO_ENGINE_DRY_WATCH``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from bolsa_application.decision_contract import (
    DecisionPackage,
    risk_gate_auto_paper_dry,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
_ENV_ENABLED = "AUTO_ENGINE_DRY_ENABLED"
_ENV_INTERVAL = "AUTO_ENGINE_DRY_INTERVAL_SECONDS"
_ENV_WATCH = "AUTO_ENGINE_DRY_WATCH"

AutoEngineState = Literal[
    "RUNNING",
    "PAUSED",
    "BLOCKED",
    "DEGRADED",
    "REQUIRES_ATTENTION",
]


def _enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "0").strip().lower()
    return raw not in {"", "0", "false", "no", "off"}


def _interval_seconds(default: float) -> float:
    raw = (os.getenv(_ENV_INTERVAL) or "").strip()
    try:
        return float(raw) if raw and float(raw) > 0 else default
    except ValueError:
        return default


def _watch_symbols() -> list[str]:
    raw = os.getenv(_ENV_WATCH) or "AAA,IBEX"
    return [s.strip() for s in raw.split(",") if s.strip()]


def _kill_switch_env_on() -> bool:
    """Kill switch READ-only (sin Redis): env Settings + runtime memory. El motor
    AUTO SAFE/dry nunca escribe nada; solo lo observa para estado."""
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
    # En SAFE no fabricamos adaptador: solo observamos el editorial broker_venue
    # config para decidir estado; AUTO es SOLO paper/simulated de todos modos.
    return (os.getenv("AUTO_ENGINE_DRY_VENUE") or "paper").strip().lower()


@dataclass(frozen=True, slots=True)
class PaperAutoEngineDryReport:
    proposals: int
    vetoes: int
    reasons: tuple[str, ...]


def dry_tick(
    *,
    watch: list[str] | None = None,
    kill_switch: bool,
    venue: str,
) -> PaperAutoEngineDryReport:
    """Un ciclo dry puro y determinista: propone HOLD-safe por símbolo y lo corre
    por el RiskGate. Nunca ejecuta nada. Devuelve conteos + razones resumidas."""
    syms = list(watch) if watch is not None else _watch_symbols()
    prop = 0
    vetoes = 0
    reasons: set[str] = set()
    for sym in syms:
        sym = sym.strip()
        if not sym:
            continue
        pkg = DecisionPackage(
            action="HOLD",  # SAFE: nunca ni siquiera BUY en este modo.
            instrument_id=sym,
            quantity=0.0,
            source="paper_auto_engine_dry",
        )
        gate = risk_gate_auto_paper_dry(pkg, kill_switch_active=kill_switch, venue=venue)
        if gate.allow_proposal:
            prop += 1
        else:
            vetoes += 1
            reasons.update(r.value for r in gate.reasons)
    return PaperAutoEngineDryReport(
        proposals=prop,
        vetoes=vetoes,
        reasons=tuple(sorted(reasons)),
    )


class PaperAutoEngine:
    """Motor AUTO SAFE/dry autónomo (telemetr�a en proceso, solo lectura UI)."""

    def __init__(self) -> None:
        self._state: AutoEngineState = "PAUSED"
        self._last_tick: str | None = None
        self._proposals = 0
        self._vetoes = 0
        self._last_reason: tuple[str, ...] = ("idle",)

    def run_tick(self) -> None:
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
        rep = dry_tick(kill_switch=kill, venue=venue)
        self._proposals += rep.proposals
        self._vetoes += rep.vetoes
        self._last_reason = rep.reasons or ("ok",)
        self._state = "RUNNING"
        self._last_tick = datetime.now(UTC).isoformat()

    def telemetry(self) -> dict[str, object]:
        return {
            "state": self._state,
            "lastTick": self._last_tick,
            "dryProposals": self._proposals,
            "dryVetoes": self._vetoes,
            "lastReason": ", ".join(self._last_reason),
        }


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
            engine.run_tick()
        except Exception:  # noqa: BLE001 — un tick no tumba el motor.
            logger.exception("paper_auto_engine tick failed")
            engine._state = "DEGRADED"  # noqa: SLF001


def start_paper_auto_engine_worker(
    session_factory: object = None,  # unused (SAFE/dry no necesita BD de tick).
    *,
    engine: PaperAutoEngine | None = None,
    interval_seconds: float | None = None,
):
    """start hook para ``_event_loop_starters()`` del scheduler (SAFE/dry)."""
    if not _enabled():
        logger.info("PaperAutoEngineWorker desactivado (%s=false/off)", _ENV_ENABLED)
        return None
    eng = engine if engine is not None else PaperAutoEngine()
    eff = _interval_seconds(interval_seconds or TICK_SECONDS)
    return asyncio.create_task(paper_auto_engine_loop(eng, interval_seconds=eff))
