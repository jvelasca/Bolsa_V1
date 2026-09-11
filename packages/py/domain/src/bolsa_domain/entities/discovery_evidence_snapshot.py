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
# V2.37/P2-01: fórmula compuesta (varias métricas del LAB + evidencia posterior).
# Se mantiene la v0 para reproducir snapshots históricos; los nuevos usan la v1.
MATH_VERSION_DISCOVERY_EVIDENCE_V1 = "discovery_evidence_v1"


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

    **Tres identidades distintas (V2.37/P2-03, no confundir):**

    * ``snapshot_hash`` — identidad del **conocimiento**: cubre la fórmula (``math_version``),
      la ventana temporal y todos los pesos/muestras. Dos ejecuciones sobre la misma
      evidencia comparten hash; el hash es la clave natural idempotente de la tabla.
    * ``id`` — identidad de **instancia** persistida (una fila). No participa en el hash:
      el mismo conocimiento guardado dos veces tiene un solo hash.
    * ``created_at`` — instante de **persistencia**. Puede diferir entre dos filas con el
      mismo ``snapshot_hash`` sin que el conocimiento cambie: **"snapshot más nuevo" NO
      significa "conocimiento más reciente"**. Para juzgar vigencia se usa ``window_to``
      (freshness, fail-closed en el worker) y ``evidence_fingerprint``.
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
    # V2.37/P2-03: huella del conjunto de evidencia agregada (fuentes/ventana/cobertura).
    # Distingue "research dataset snapshot" de "event-time evidence" y permite detectar
    # reescrituras retrospectivas del dataset. Vacío = snapshots v0 previos (compat).
    evidence_fingerprint: str = ""

    def adaptive_weight(self) -> float:
        """Peso del carril adaptativo (0.0 si el snapshot no lo define — fail-closed)."""
        return float(self.lane_weights.get("adaptive", 0.0))

    def has_evidence(self) -> bool:
        """True si hay al menos una familia con observaciones (si no, no hay señal)."""
        return bool(self.family_weights) and sum(self.sample_sizes.values()) > 0

    def is_fresh(self, *, now: str, max_staleness_days: int) -> bool:
        """V2.37/P2-03: ¿el corte ``window_to`` está dentro de la ventana de vigencia?

        Fail-closed: sin ``window_to`` parseable o sin ``max_staleness_days`` positivo el
        snapshot **no** se considera vigente (el allocator queda con peso 0). Compara por
        *tiempo de evento* (``window_to``), no por ``created_at``: un snapshot recién
        persistido sobre evidencia vieja sigue siendo evidencia vieja.
        """
        if int(max_staleness_days) <= 0 or not self.window_to:
            return False
        from datetime import UTC, datetime

        try:
            cut = datetime.fromisoformat(self.window_to)
            reference = datetime.fromisoformat(now)
        except (TypeError, ValueError):
            return False
        if cut.tzinfo is None:
            cut = cut.replace(tzinfo=UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        age_days = (reference - cut).total_seconds() / 86400.0
        return age_days <= float(max_staleness_days)
