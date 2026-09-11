"""Entidad de dominio del snapshot de evidencia para el allocator adaptativo — sin deps.

V2.36 (incremento 1) — Strategy Intelligence adaptativa: el carril ``adaptive`` del
``DiscoveryBudgetAllocator`` deja de ser un hueco de peso 0 y pasa a alimentarse de un
**snapshot de evidencia inmutable y versionado**, calculado FUERA del hot path por un
job batch/CLI y consumido por el discovery como dependencia inyectada.

Invariante de diseño: el discovery sigue siendo una **función pura dada la tupla
``(instrument_id, snapshot)``**. El aprendizaje no se calcula dentro del motor; se
materializa aquí y se inyecta. Sin ello la búsqueda dejaría de ser reproducible.

Este snapshot es SOLO un prior de reparto de presupuesto: no decide promociones, no
relaja gates y no introduce estado mutable en el ciclo. Fail-closed: sin snapshot
vigente el carril adaptativo vale 0 (comportamiento histórico).
"""
from dataclasses import dataclass
from typing import Any

# Versión de la matemática del snapshot (separada del esquema persistido): permite
# auditar con qué fórmula se derivaron los pesos y reproducirlos. Análoga a
# ``MATH_VERSION_BELIEF_V0`` del motor de creencias.
MATH_VERSION_DISCOVERY_EVIDENCE_V0 = "discovery_evidence_v0"


@dataclass(frozen=True, slots=True)
class DiscoveryEvidenceSnapshot:
    """Prior determinista de reparto de presupuesto derivado de evidencia persistida.

    ``family_weights``: peso observado por familia H0 del catálogo (clave = ``preset_key``
    normalizado), en ``[0, 1]``. Es la evidencia en bruto agregada.
    ``lane_weights``: pesos finales por carril del ``DiscoveryBudgetAllocator``
    (``catalog`` / ``grammar_simple`` / ``grammar_composite`` / ``adaptive``). El
    incremento 1 solo mueve ``adaptive``; el resto conserva sus defaults.
    ``sample_sizes``: nº de observaciones por familia (para exigir muestra mínima y no
    sobreajustar a una familia con un único trial afortunado).
    """

    id: str
    snapshot_hash: str
    math_version: str
    window_from: str
    window_to: str
    family_weights: dict[str, float]
    lane_weights: dict[str, float]
    sample_sizes: dict[str, int]
    payload: dict[str, Any]
    created_at: str

    def adaptive_weight(self) -> float:
        """Peso del carril adaptativo (0.0 si el snapshot no lo define — fail-closed)."""
        return float(self.lane_weights.get("adaptive", 0.0))

    def has_evidence(self) -> bool:
        """True si hay al menos una familia con observaciones (si no, no hay señal)."""
        return bool(self.family_weights) and sum(self.sample_sizes.values()) > 0
