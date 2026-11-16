"""R2 — cuerpo del ciclo AUTO reutilizable (worker y disparador gobernado).

Antes de este módulo, el "qué hace un ciclo para un instrumento" vivía dentro del bucle
del worker (``background/auto_orchestrator_worker.py``): ``run_cycle`` → forward paper →
vigilancia. El disparador gobernado (``POST /api/auto/orchestrator/run``) necesitaba
exactamente eso, y reimplementarlo habría creado un segundo embudo —justo lo que la
auditoría LAB 2026-11-16 prohíbe—.

Aquí se extrae **una sola** implementación:

* ``run_cycle_once`` ejecuta una pasada y devuelve las tres piezas por separado
  (resultado del ciclo, forward, vigilancia) para que el llamante decida qué registrar.
* ``max_phase`` se propaga tal cual al orquestador (el techo ``finalista`` del
  disparador gobernado: nunca escribe ACTIVE). ``watch=False`` evita la vigilancia, que
  es una escritura de salud sobre la ACTIVA y queda fuera del techo.
* El fallo del forward **no** tumba la pasada (se registra); el del ciclo/vigilancia sí
  se propaga para que el llamante lo declare (fail-closed, nunca un éxito inventado).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from bolsa_application.auto_orchestrator import PHASE_ACTIVE

logger = logging.getLogger(__name__)

__all__ = ["CycleOutcome", "build_cycle_run_id", "run_cycle_once"]


@dataclass(slots=True)
class CycleOutcome:
    """Resultado de una pasada: ciclo + (opcional) forward + (opcional) vigilancia."""

    result: Any
    forward: Any | None = None
    vigilance: Any | None = None


def build_cycle_run_id(instrument_id: str, cycle_id: str) -> str:
    """Identidad de trazabilidad de un ciclo (misma forma que usaba el worker).

    V2.32.1 (auditoría P2-05): el ``cycle_id`` distingue ciclos, reintentos y re-LAB.
    Se conserva el formato histórico para no romper la trazabilidad ya persistida.
    """
    return f"orchestrator:{instrument_id}:{cycle_id}"


async def run_cycle_once(
    orchestrator: Any,
    *,
    instrument_id: str,
    cycle_id: str,
    run_id: str | None = None,
    max_phase: str = PHASE_ACTIVE,
    forward_runner: Any = None,
    watch: bool = True,
) -> CycleOutcome:
    """Ejecuta una pasada del ciclo para ``instrument_id`` y devuelve sus piezas.

    ``run_id`` por defecto se compone con ``build_cycle_run_id`` (formato del worker).
    ``forward_runner`` y ``watch`` son opcionales: el disparador gobernado corre con
    ``watch=False`` porque la vigilancia escribe salud sobre la ACTIVA.
    """
    effective_run_id = run_id or build_cycle_run_id(instrument_id, cycle_id)
    result = await orchestrator.run_cycle(
        instrument_id=instrument_id,
        run_id=effective_run_id,
        max_phase=max_phase,
    )

    forward: Any | None = None
    if forward_runner is not None:
        try:
            forward = await forward_runner(instrument_id)
        except Exception:  # noqa: BLE001 — el forward no rompe la vigilancia.
            logger.exception(
                "orchestrator cycle forward failed for %s", instrument_id
            )

    vigilance: Any | None = None
    if watch:
        # S7: el ``as_of`` es la identidad del ciclo, no su estado.
        vigilance = await orchestrator.watch_active(
            instrument_id=instrument_id,
            as_of=f"vigilancia:{instrument_id}:{cycle_id}",
        )

    return CycleOutcome(result=result, forward=forward, vigilance=vigilance)
