"""V2.36 (incremento 1) — Prior de evidencia para el carril ``adaptive`` del allocator.

Cierra la primera mitad del bucle ``evidence → aprender → ajustar búsqueda``: agrega la
evidencia **ya persistida** (research trials del LAB) en pesos por familia H0, deriva un
peso para el carril ``adaptive`` del ``DiscoveryBudgetAllocator`` y lo materializa en un
``DiscoveryEvidenceSnapshot`` inmutable y versionado.

Principios (invariantes del repo):

- **Determinismo**: función pura de la evidencia de entrada. Orden canónico por familia,
  redondeo fijo y hash estable (``sort_keys`` + separadores compactos), igual que
  ``definition_hash`` de ``strategy_promotion_phase``. Misma evidencia ⇒ mismo hash.
- **Fail-closed**: sin evidencia suficiente el peso adaptativo es ``0.0`` explícito: no
  se inventa señal. El comportamiento del ciclo es entonces byte-idéntico al histórico.
- **Sin LLM, sin red**: solo aritmética sobre agregados ya calculados por el repo.
- **Aprendizaje fuera del hot path**: este módulo se invoca desde un job batch/CLI; el
  worker solo LEE el snapshot vigente.
- **Muestra mínima**: una familia con pocos trials no debe dominar el reparto; se exige
  ``min_samples`` por familia y ``min_total_samples`` global antes de habilitar el carril.
- **Cota del prior**: el peso adaptativo se acota a ``[0, max_adaptive_weight]`` para no
  dejar sin presupuesto a catálogo/gramática por una racha de suerte (multiple testing).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V0,
    DiscoveryEvidenceSnapshot,
)

# --- Parámetros por defecto del prior (deterministas y conservadores) ---------------

# Muestra mínima por familia para que su score cuente (evita sobreajuste a 1 trial).
DEFAULT_MIN_SAMPLES = 3
# Muestra mínima total para habilitar el carril adaptativo (si no, peso 0).
DEFAULT_MIN_TOTAL_SAMPLES = 12
# Peso máximo que puede alcanzar el carril adaptativo (cota anti-multiple-testing).
DEFAULT_MAX_ADAPTIVE_WEIGHT = 0.5
# Peso adaptativo por defecto del allocator (histórico: carril apagado).
DEFAULT_ADAPTIVE_WEIGHT = 0.0

# Pesos base del allocator (deben coincidir con los defaults de
# ``discovery_catalog.DiscoveryBudgetAllocator`` para no alterar catálogo/gramática).
_DEFAULT_LANE_WEIGHTS: dict[str, float] = {
    "catalog": 2.0,
    "grammar_simple": 1.0,
    "grammar_composite": 1.0,
    "adaptive": DEFAULT_ADAPTIVE_WEIGHT,
}


def _round(value: float, places: int = 6) -> float:
    """Redondeo fijo para que la aritmética sea reproducible entre ejecuciones."""
    return round(float(value), places)


def _family_strength(row: Mapping[str, Any]) -> float:
    """Fuerza observada de una familia a partir de su agregado (en ``[0, 1]``).

    Combina el score medio del LAB (acotado a ``[0, 1]`` por convención del repo: el
    ``is_score`` de un trial sano ronda 1.0-1.5) con una penalización por fracasos
    (trials sin operaciones o con ``fail_code``). Es deliberadamente simple y monótona:
    no pretende ser una probabilidad, solo ordenar familias para repartir presupuesto.
    """
    trials = int(row.get("trials") or 0)
    if trials <= 0:
        return 0.0
    avg_score = row.get("avgScore")
    score_component = 0.0 if avg_score is None else max(0.0, min(1.0, float(avg_score)))
    failed = int(row.get("zeroTrade") or 0) + int(row.get("failures") or 0)
    success_ratio = max(0.0, (trials - failed) / trials)
    return _round(score_component * success_ratio)


def compute_family_weights(
    aggregates: Iterable[Mapping[str, Any]],
    *,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> tuple[dict[str, float], dict[str, int]]:
    """Pesos por familia H0 y tamaños de muestra, a partir de los agregados del repo.

    Orden canónico por ``presetKey``. Las familias por debajo de ``min_samples`` se
    excluyen del mapa de pesos (no aportan señal) pero conservan su tamaño de muestra
    para auditoría.
    """
    family_weights: dict[str, float] = {}
    sample_sizes: dict[str, int] = {}
    for row in sorted(aggregates, key=lambda r: str(r.get("presetKey") or "")):
        family = str(row.get("presetKey") or "").strip()
        if not family:
            continue
        trials = int(row.get("trials") or 0)
        sample_sizes[family] = trials
        if trials >= int(min_samples):
            family_weights[family] = _family_strength(row)
    return family_weights, sample_sizes


def compute_lane_weights(
    family_weights: Mapping[str, float],
    sample_sizes: Mapping[str, int],
    *,
    min_total_samples: int = DEFAULT_MIN_TOTAL_SAMPLES,
    max_adaptive_weight: float = DEFAULT_MAX_ADAPTIVE_WEIGHT,
) -> dict[str, float]:
    """Deriva el peso del carril ``adaptive`` a partir de la evidencia agregada.

    Fail-closed: sin muestra total suficiente o sin familias con señal, el peso
    adaptativo queda en ``0.0`` y el resto de carriles conservan sus defaults (el ciclo
    no cambia). El peso crece con la **fuerza media** de las familias observadas,
    acotado por ``max_adaptive_weight``.
    """
    lane_weights = dict(_DEFAULT_LANE_WEIGHTS)
    total_samples = sum(int(n) for n in sample_sizes.values())
    if total_samples < int(min_total_samples) or not family_weights:
        lane_weights["adaptive"] = DEFAULT_ADAPTIVE_WEIGHT
        return lane_weights

    mean_strength = sum(family_weights.values()) / len(family_weights)
    bounded = max(0.0, min(float(max_adaptive_weight), mean_strength * float(max_adaptive_weight)))
    lane_weights["adaptive"] = _round(bounded)
    return lane_weights


def snapshot_hash(
    *,
    math_version: str,
    window_from: str,
    window_to: str,
    family_weights: Mapping[str, float],
    lane_weights: Mapping[str, float],
    sample_sizes: Mapping[str, int],
) -> str:
    """Hash estable del contenido del snapshot (orden-insensible)."""
    canonical = json.dumps(
        {
            "mathVersion": math_version,
            "windowFrom": window_from,
            "windowTo": window_to,
            "familyWeights": dict(family_weights),
            "laneWeights": dict(lane_weights),
            "sampleSizes": dict(sample_sizes),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:32]}"


def build_discovery_evidence_snapshot(
    *,
    snapshot_id: str,
    created_at: str,
    window_from: str,
    window_to: str,
    aggregates: Iterable[Mapping[str, Any]],
    min_samples: int = DEFAULT_MIN_SAMPLES,
    min_total_samples: int = DEFAULT_MIN_TOTAL_SAMPLES,
    max_adaptive_weight: float = DEFAULT_MAX_ADAPTIVE_WEIGHT,
    math_version: str = MATH_VERSION_DISCOVERY_EVIDENCE_V0,
) -> DiscoveryEvidenceSnapshot:
    """Construye el snapshot determinista (función pura de ``aggregates``).

    No tiene efectos secundarios: el llamante (job batch/CLI) decide si persiste el
    resultado y es idempotente por ``snapshot_hash``.
    """
    family_weights, sample_sizes = compute_family_weights(
        aggregates, min_samples=min_samples
    )
    lane_weights = compute_lane_weights(
        family_weights,
        sample_sizes,
        min_total_samples=min_total_samples,
        max_adaptive_weight=max_adaptive_weight,
    )
    digest = snapshot_hash(
        math_version=math_version,
        window_from=window_from,
        window_to=window_to,
        family_weights=family_weights,
        lane_weights=lane_weights,
        sample_sizes=sample_sizes,
    )
    payload: dict[str, Any] = {
        "mathVersion": math_version,
        "windowFrom": window_from,
        "windowTo": window_to,
        "familyWeights": family_weights,
        "laneWeights": lane_weights,
        "sampleSizes": sample_sizes,
        "familyCount": len(family_weights),
        "totalSamples": sum(sample_sizes.values()),
    }
    return DiscoveryEvidenceSnapshot(
        id=snapshot_id,
        snapshot_hash=digest,
        math_version=math_version,
        window_from=window_from,
        window_to=window_to,
        family_weights=family_weights,
        lane_weights=lane_weights,
        sample_sizes=sample_sizes,
        payload=payload,
        created_at=created_at,
    )
