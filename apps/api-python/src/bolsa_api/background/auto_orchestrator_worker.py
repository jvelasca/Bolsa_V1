"""V2.26 / A10 — worker del Auto Orchestrator (env-gated, SIM-only).

Reloj de fondo que invoca ``AutoOrchestrator.run_cycle`` y ``watch_active`` con el
gate de entorno (default **OFF**), siguiendo el patrón de los workers A9:

* ``AUTO_ORCHESTRATOR_ENABLED=1`` — activa el bucle (default OFF, fail-closed).
* ``AUTO_ORCHESTRATOR_INSTRUMENTS`` — lista CSV de instrumentos a orquestar.
* ``AUTO_ORCHESTRATOR_INTERVAL_SECONDS`` — periodo del bucle (default 3600).
* ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` — permite promocionar (default OFF: sin
  shadow no hay promoción, coherente con el Promotion Gate).

**SIM-only**: este worker no abre venues ni habilita LIVE. La ejecución sigue en el
worker AUTO SIM, cuyo ``DecisionProvider`` puede leer la estrategia ACTIVE del store
(``active_strategy_decider``) sin saltarse RiskGate/SimulationGate.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

AUTO_ORCHESTRATOR_ENABLED = "AUTO_ORCHESTRATOR_ENABLED"
AUTO_ORCHESTRATOR_INSTRUMENTS = "AUTO_ORCHESTRATOR_INSTRUMENTS"
AUTO_ORCHESTRATOR_INTERVAL_SECONDS = "AUTO_ORCHESTRATOR_INTERVAL_SECONDS"
AUTO_ORCHESTRATOR_SHADOW_VALIDATED = "AUTO_ORCHESTRATOR_SHADOW_VALIDATED"


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def orchestrator_enabled() -> bool:
    """Gate del bucle (default OFF, fail-closed)."""
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_ENABLED))


def instrument_watch() -> tuple[str, ...]:
    raw = (os.getenv(AUTO_ORCHESTRATOR_INSTRUMENTS) or "").strip()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _interval_seconds(default: float = 3600.0) -> float:
    raw = (os.getenv(AUTO_ORCHESTRATOR_INTERVAL_SECONDS) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def shadow_validated() -> bool:
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_SHADOW_VALIDATED))


async def auto_orchestrator_loop(
    orchestrator: Any,
    *,
    interval_seconds: float | None = None,
) -> None:
    """Bucle del orquestador: corre el ciclo y vigila la activa por instrumento."""
    period = interval_seconds if interval_seconds is not None else _interval_seconds()
    watch = instrument_watch()
    if not watch:
        logger.warning(
            "auto_orchestrator activo pero sin %s — no se orquesta nada.",
            AUTO_ORCHESTRATOR_INSTRUMENTS,
        )
        return
    allow_promotion = shadow_validated()
    while True:
        for instrument_id in watch:
            try:
                result = await orchestrator.run_cycle(
                    instrument_id=instrument_id,
                    shadow_validated=allow_promotion,
                    run_id=f"orchestrator:{instrument_id}",
                )
                logger.info(
                    "auto_orchestrator cycle instrument=%s status=%s promoted=%s",
                    instrument_id,
                    result.status,
                    result.promoted,
                )
                # Vigilancia de la activa (si la hay) con las métricas disponibles.
                await orchestrator.watch_active(
                    instrument_id=instrument_id,
                    metrics={},
                    as_of=result.status,
                )
            except Exception:  # noqa: BLE001 — un fallo por instrumento no tumba el bucle.
                logger.exception("auto_orchestrator cycle failed for %s", instrument_id)
        await asyncio.sleep(period)


def start_auto_orchestrator(
    session_factory: Any = None,
    *,
    orchestrator: Any = None,
    interval_seconds: float | None = None,
) -> asyncio.Task[None] | None:
    """Starter env-gated para ``_event_loop_starters`` (default OFF, SIM).

    Con ``session_factory`` compone el store Postgres del lifecycle; sin él permite un
    ``orchestrator`` inyectado (hermético). Sin ninguno de los dos no arranca nada.
    """
    if not orchestrator_enabled():
        logger.info(
            "AutoOrchestrator (%s) desactivado — SIM-ONLY por defecto.",
            AUTO_ORCHESTRATOR_ENABLED,
        )
        return None
    if orchestrator is None:
        if session_factory is None:
            logger.warning(
                "auto_orchestrator habilitado sin session_factory ni orchestrator: "
                "no se arranca (evita un orquestador sin store)."
            )
            return None
        orchestrator = _default_orchestrator(session_factory)
    return asyncio.create_task(
        auto_orchestrator_loop(orchestrator, interval_seconds=interval_seconds)
    )


def _default_orchestrator(session_factory: Any) -> Any:
    """Compone el orquestador real (store Postgres por sesión, SIM-only).

    El ``run_optimize`` real queda pendiente de cablear al LAB (``RunSmaGridOptimize``)
    en el proceso API; hasta entonces el ciclo solo puede crear candidatas (sin
    evidencia no promociona, que es el comportamiento fail-closed correcto).
    """
    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

    class _SessionScopedStore:
        """Store que abre una sesión por operación (imports diferidos)."""

        def __getattr__(self, name: str) -> Any:
            async def _call(*args: Any, **kwargs: Any) -> Any:
                async with session_factory() as session:
                    store = PostgresStrategyLifecycleStore(session)
                    return await getattr(store, name)(*args, **kwargs)

            return _call

    return AutoOrchestrator(OrchestratorDeps(store=_SessionScopedStore()))
