"""Índice Operativo (IO) v1 — fórmula de ranking (ADR-031 Ciclo I2).

Espejo de ``computeIndiceOperativo`` en ``operativa-index.ts``.
Base: Composite display 0–100. Distress FA → suelo IO ≤ 40.

Ranking Estudio (orden entre ids) sigue en cliente. IO ≠ permiso:
no entra en ``check_opening``.
"""

from __future__ import annotations

import math
from typing import Any

IO_DISTRESS_FLOOR = 40


def compute_indice_operativo(
    composite_display_100: Any,
    *,
    distress: bool = False,
) -> int | None:
    """Composite 0–100, clamp, suelo distress. ``None`` si no hay base finita."""
    if composite_display_100 is None:
        return None
    try:
        base = float(composite_display_100)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(base):
        return None
    io = int(round(max(0.0, min(100.0, base))))
    if distress:
        io = min(io, IO_DISTRESS_FLOOR)
    return io
