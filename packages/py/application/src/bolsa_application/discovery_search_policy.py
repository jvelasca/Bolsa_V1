"""V2.37 (incremento 2) — Search policy adaptativa de Discovery (determinista, pura).

El incremento 1 (V2.36) asignó **cupo** al carril ``adaptive`` pero no emitía nada: el
sistema decidía cuánto presupuesto recibía el aprendizaje, no **qué** hipótesis merecía
explorarse. Este módulo cierra esa mitad: convierte el prior de evidencia por familia
(``DiscoveryEvidenceSnapshot.family_weights``) en una **política de búsqueda** — cuotas
de emisión por familia — que el motor de discovery consume como dependencia inyectada.

Principios (idénticos a ``discovery_evidence``):

* **Determinismo**: función pura del snapshot. Orden canónico por familia, redondeo fijo
  y hash estable. Mismo ``(snapshot, cupo)`` ⇒ misma política y mismas cuotas.
* **Sin LLM, sin red, sin BD**: solo aritmética sobre el prior ya persistido.
* **Exploración garantizada**: ninguna familia del catálogo puede quedarse sin cuota por
  completo (``min_quota``/``exploration_ratio``): el aprendizaje *reordena* la búsqueda,
  nunca la colapsa. Esto materializa la política "champion cannot teach itself" en la
  capa de generación, no solo en la de presupuesto.
* **Fail-closed**: sin snapshot o sin señal utilizable la política es **vacía** y el
  motor conserva el comportamiento histórico (catálogo + gramática).

La política NO relaja gates ni promociona nada: solo decide el orden y la cuota de
emisión de candidatas dentro del cupo que el allocator ya concede al carril adaptativo.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V0,
    DiscoveryEvidenceSnapshot,
)

# Versión de la matemática de la política (separada del snapshot que la alimenta): una
# política guardada/emitida se puede auditar y reproducir con su fórmula.
# V2.38 (incremento 3): v1 — la clave de reparto es la **clave compuesta** de
# granularidad (familia o familia|region), no solo la familia. La fórmula de reparto no
# cambia (ya era agnóstica a la clave); el bump marca que las claves pueden llevar región.
MATH_VERSION_SEARCH_POLICY_V0 = "discovery_search_policy_v1"

# Versión del esquema de clave de granularidad que alimenta la política. Se incluye en el
# ``policy_hash`` para que una política derivada de claves compuestas sea distinguible de
# una derivada solo por familia (reproducibilidad de extremo a extremo).
GRANULARITY_KEY_VERSION_V0 = "discovery_granularity_key_v0"

# Fracción mínima del cupo adaptativo reservada a exploración uniforme entre familias
# con evidencia. Garantiza que la explotación (familias con mejor prior) nunca absorbe
# el 100 % de la emisión adaptativa.
DEFAULT_EXPLORATION_RATIO = 0.25
# Nº de familias con mejor prior que reciben explotación (top-k). El resto explora.
DEFAULT_EXPLOITATION_TOP_K = 5


@dataclass(frozen=True, slots=True)
class FamilyQuota:
    """Cuota de emisión de una familia dentro del cupo adaptativo.

    ``family``: nombre de familia H0 (``preset_key``).
    ``quota``: nº máximo de candidatas a emitir de esa familia en el ciclo.
    ``weight``: peso normalizado del que deriva la cuota (auditoría, en ``[0, 1]``).
    ``exploration``: True si la cuota procede del tramo de exploración (no del top-k).
    """

    family: str
    quota: int
    weight: float
    exploration: bool = False


@dataclass(frozen=True, slots=True)
class SearchPolicy:
    """Política de búsqueda: cuotas de emisión por familia para el carril adaptativo.

    ``quotas`` va en orden canónico (peso descendente y, en empate, familia ascendente)
    para que la emisión sea reproducible. ``total_quota`` es la suma de cuotas y no
    excede el cupo solicitado. ``exploration_quota`` documenta cuánto del total se
    reservó a exploración. Una política con ``quotas`` vacío es el **fail-closed**:
    el motor no emite nada por el carril adaptativo.
    """

    quotas: tuple[FamilyQuota, ...]
    total_quota: int
    exploration_quota: int
    math_version: str = MATH_VERSION_SEARCH_POLICY_V0
    policy_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """True si no hay nada que emitir (fail-closed o cupo 0)."""
        return not self.quotas or self.total_quota <= 0

    def quota_for(self, family: str) -> int:
        """Cuota de una familia (0 si no aparece en la política)."""
        target = str(family or "").strip()
        return next((q.quota for q in self.quotas if q.family == target), 0)

    def families(self) -> tuple[str, ...]:
        return tuple(q.family for q in self.quotas)


def _round(value: float, places: int = 6) -> float:
    return round(float(value), places)


def _policy_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:32]}"


def _apportion(
    weights: Mapping[str, float],
    total: int,
    *,
    minimums: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Reparto determinista por resto mayor (mismo patrón que el allocator).

    ``total`` se reparte proporcionalmente a ``weights``; las quedas se asignan de mayor
    a menor con desempate por nombre de familia ascendente (orden canónico, ajeno al
    orden de iteración de dicts). Nunca se excede ``total``.
    """
    families = sorted(weights)
    if total <= 0 or not families:
        return {family: 0 for family in families}
    weight_sum = sum(max(0.0, float(weights[f])) for f in families)
    if weight_sum <= 0:
        # Sin señal: reparto uniforme determinista (exploración pura).
        quotas = {family: total // len(families) for family in families}
        for family in families[: total % len(families)]:
            quotas[family] += 1
    else:
        raw = {family: total * max(0.0, float(weights[family])) / weight_sum for family in families}
        quotas = {family: int(raw[family]) for family in families}
        remainder = total - sum(quotas.values())
        order = sorted(
            families,
            key=lambda family: (-round(raw[family] - quotas[family], 12), family),
        )
        for family in order[:remainder]:
            quotas[family] += 1
    # Pisos: garantizar el mínimo declarado cuando el presupuesto lo permite.
    for family, floor in (minimums or {}).items():
        if family in quotas and quotas[family] < int(floor):
            deficit = int(floor) - quotas[family]
            donors = [f for f in families if quotas[f] > int(floor) and quotas[f] - deficit >= 0]
            for donor in sorted(donors, key=lambda f: (-quotas[f], f)):
                if deficit <= 0:
                    break
                give = min(deficit, quotas[donor] - int(floor))
                if give <= 0:
                    continue
                quotas[donor] -= give
                quotas[family] += give
                deficit -= give
    return quotas


def build_search_policy(
    snapshot: DiscoveryEvidenceSnapshot | None,
    *,
    adaptive_cap: int,
    available_families: Sequence[str] | None = None,
    exploration_ratio: float = DEFAULT_EXPLORATION_RATIO,
    exploitation_top_k: int = DEFAULT_EXPLOITATION_TOP_K,
) -> SearchPolicy:
    """Deriva la política de búsqueda del snapshot vigente (función pura).

    Reparto en dos tramos sobre ``adaptive_cap``:

    * **Explotación** (``1 - exploration_ratio``): reservado al ``top-k`` de familias con
      mejor prior, repartido por peso.
    * **Exploración** (``exploration_ratio``): repartido uniformemente entre el resto de
      familias elegibles, de modo que una familia con poca o ninguna evidencia sigue
      recibiendo oportunidades (contra el sesgo de selección).

    Fail-closed: sin snapshot, sin ``family_weights``, sin familias elegibles o con
    ``adaptive_cap <= 0`` devuelve una política **vacía** (el motor no emite por el carril
    adaptativo y se conserva el comportamiento histórico).
    """
    if snapshot is None:
        return SearchPolicy(quotas=(), total_quota=0, exploration_quota=0, metadata={"reason": "no_snapshot"})
    cap = int(adaptive_cap)
    if cap <= 0:
        return SearchPolicy(quotas=(), total_quota=0, exploration_quota=0, metadata={"reason": "no_cap"})

    weights = {str(k).strip(): float(v) for k, v in (snapshot.family_weights or {}).items() if str(k).strip()}
    if not weights:
        return SearchPolicy(quotas=(), total_quota=0, exploration_quota=0, metadata={"reason": "no_evidence"})

    # Familias elegibles: la intersección con el catálogo disponible (si se declara), para
    # no emitir cuotas de familias que el motor no puede materializar.
    if available_families is not None:
        available = {str(f).strip() for f in available_families if str(f).strip()}
        weights = {family: weight for family, weight in weights.items() if family in available}
    if not weights:
        return SearchPolicy(quotas=(), total_quota=0, exploration_quota=0, metadata={"reason": "no_available_family"})

    ratio = max(0.0, min(1.0, float(exploration_ratio)))
    exploration_total = int(math.floor(cap * ratio))
    exploitation_total = cap - exploration_total

    ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    exploited = ranked[: max(0, int(exploitation_top_k))]
    explorers = ranked[max(0, int(exploitation_top_k)) :]
    # Si no hay familias fuera del top-k, la exploración recae sobre el propio top-k
    # (exploración dentro de las familias conocidas), nunca se pierde cupo.
    exploration_pool = explorers or ranked

    exploitation_weights = {family: weight for family, weight in exploited}
    exploration_weights = {family: 1.0 for family, _ in exploration_pool}

    exploit_quotas = _apportion(exploitation_weights, exploitation_total)
    explore_quotas = _apportion(exploration_weights, exploration_total)

    combined: dict[str, int] = {}
    is_exploration: dict[str, bool] = {}
    for family, quota in exploit_quotas.items():
        if quota > 0:
            combined[family] = combined.get(family, 0) + quota
            is_exploration.setdefault(family, False)
    for family, quota in explore_quotas.items():
        if quota > 0:
            combined[family] = combined.get(family, 0) + quota
            is_exploration[family] = is_exploration.get(family, True) and family not in exploit_quotas

    if not combined:
        return SearchPolicy(quotas=(), total_quota=0, exploration_quota=0, metadata={"reason": "empty_apportionment"})

    total = sum(combined.values())
    quotas = tuple(
        FamilyQuota(
            family=family,
            quota=int(combined[family]),
            weight=_round(
                weights.get(family, 0.0) / max(weights.values(), default=1.0)
            ),
            exploration=bool(is_exploration.get(family, False)),
        )
        for family in sorted(combined, key=lambda f: (-combined[f], f))
    )
    payload = {
        "mathVersion": MATH_VERSION_SEARCH_POLICY_V0,
        "snapshotHash": snapshot.snapshot_hash,
        "granularityKeyVersion": GRANULARITY_KEY_VERSION_V0,
        "adaptiveCap": cap,
        "explorationRatio": _round(ratio),
        "quotas": {q.family: q.quota for q in quotas},
    }
    return SearchPolicy(
        quotas=quotas,
        total_quota=total,
        exploration_quota=int(sum(explore_quotas.values())),
        math_version=MATH_VERSION_SEARCH_POLICY_V0,
        policy_hash=_policy_hash(payload),
        metadata={
            "snapshotHash": snapshot.snapshot_hash,
            "granularityKeyVersion": GRANULARITY_KEY_VERSION_V0,
            "saturationAware": snapshot.math_version != MATH_VERSION_DISCOVERY_EVIDENCE_V0,
        },
    )
