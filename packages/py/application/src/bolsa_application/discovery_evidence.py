"""V2.36/V2.37 — Prior de evidencia para el carril ``adaptive`` del allocator.

Cierra el bucle ``evidence → aprender → ajustar búsqueda``: agrega la evidencia **ya
persistida** (research trials del LAB + evidencia posterior shadow/paper-forward) en
pesos por familia H0, deriva un peso para el carril ``adaptive`` del
``DiscoveryBudgetAllocator`` y lo materializa en un ``DiscoveryEvidenceSnapshot``
inmutable y versionado.

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

V2.37/P2-01 — señal enriquecida (``math_version = discovery_evidence_v1``):

La v0 usaba ``clamp(avgScore, 0, 1) * success_ratio``. Problema: el ``is_score`` sano
ronda 1.0-1.5 y el clamp **saturaba** toda la información por encima de 1.0, además de
ignorar el resto de la evidencia ya persistida. La v1 combina varios componentes
deterministas con cobertura explícita (una métrica ausente **no puntúa**, no vale 0):

    component            fuente                          dirección
    -------------------  ------------------------------  --------------------------
    is_score             research_trials.is_score        mayor mejor, normalizado
    success_ratio        trials vs zeroTrade+failures    mayor mejor
    sharpe               is_metrics.sharpeRatio          mayor mejor, tanh
    profit_factor        is_metrics.profitFactor         mayor mejor, tanh
    drawdown             is_metrics.maxDrawdownPct       menor mejor
    posterior            research_evidence (shadow/paper) mayor mejor, peso por nivel

El resultado sigue siendo un **orden**, no una probabilidad: sirve para repartir
presupuesto, nunca para promocionar. La v0 se conserva para reproducir snapshots
históricos (``MATH_VERSION_DISCOVERY_EVIDENCE_V0``).
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from typing import Any

from bolsa_application.discovery_param_region import compose_granularity_key
from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V0,
    MATH_VERSION_DISCOVERY_EVIDENCE_V1,
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

# Pesos relativos de los componentes de la señal v1. Deben sumar 1.0 (se normalizan
# igualmente, defensivo). Deliberadamente simples: el objetivo es ORDENAR familias, no
# estimar una probabilidad.
_V1_COMPONENT_WEIGHTS: dict[str, float] = {
    "is_score": 0.30,
    "success_ratio": 0.20,
    "sharpe": 0.15,
    "profit_factor": 0.10,
    "drawdown": 0.10,
    "posterior": 0.15,
}

# Peso relativo por nivel de evidencia posterior (ADR-012): A > B > C > D. La ponderación
# se aplica en la agregación SQL (``posterior_evidence_summary``), que devuelve ya
# ``posteriorWeighted``; aquí solo se consume. Se documenta para auditar la fórmula.

# Ancla neutral del *shrinkage* por cobertura: una métrica ausente arrastra la señal
# hacia este valor (ni premia ni castiga), en vez de puntuar como 0.
_V1_NEUTRAL_ANCHOR = 0.5


def _round(value: float, places: int = 6) -> float:
    """Redondeo fijo para que la aritmética sea reproducible entre ejecuciones."""
    return round(float(value), places)


def _as_float(value: Any) -> float | None:
    """Convierte a float; ``None``/no numérico ⇒ ``None`` (métrica AUSENTE, no 0)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or math.isinf(number):  # NaN/inf ⇒ ausente (fail-safe)
        return None
    return number


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _saturating(value: float, *, scale: float) -> float:
    """Comprime ``[0, ∞)`` en ``[0, 1)`` sin saturar: ``1 - exp(-value/scale)``.

    A diferencia del ``clamp`` de la v0, valores por encima de ``scale`` **siguen
    aportando señal** (monótono estricto), lo que elimina la pérdida de información
    detectada en la auditoría (P2-01).
    """
    if value <= 0:
        return 0.0
    return _clamp01(1.0 - math.exp(-float(value) / float(scale)))


def _normalize_is_score(avg_score: float | None) -> float | None:
    """Normaliza el ``is_score`` sin saturar: 1.0 (sano) ≈ 0.63, 1.5 ≈ 0.78."""
    score = _as_float(avg_score)
    if score is None:
        return None
    return _saturating(max(0.0, score), scale=1.0)


def _sharpe_component(avg_sharpe: float | None) -> float | None:
    """Sharpe medio: tanh con escala 1.0 (Sharpe 1 ⇒ 0.76; 2 ⇒ 0.96; negativo penaliza)."""
    sharpe = _as_float(avg_sharpe)
    if sharpe is None:
        return None
    return _clamp01(math.tanh(sharpe / 1.0))


def _profit_factor_component(avg_pf: float | None) -> float | None:
    """Profit factor: ``(pf - 1)`` comprimido con escala 1.0 (PF 2 ⇒ 0.63)."""
    pf = _as_float(avg_pf)
    if pf is None:
        return None
    return _saturating(pf - 1.0, scale=1.0)


def _drawdown_component(avg_max_dd_pct: float | None) -> float | None:
    """Drawdown medio: menor es mejor. 0 % ⇒ 1.0; 50 % ⇒ 0.37; ≥100 % ⇒ ~0.0.

    Se asume porcentaje (convención del repo: ``maxDrawdownPct``). Un valor negativo se
    interpreta como ausencia de dato útil.
    """
    dd = _as_float(avg_max_dd_pct)
    if dd is None or dd < 0:
        return None
    return _clamp01(math.exp(-dd / 50.0))


def _posterior_component(row: Mapping[str, Any]) -> float | None:
    """Evidencia posterior (shadow / paper forward) ponderada por nivel ADR-012.

    ``row`` puede traer ``posteriorWeighted`` (suma ya ponderada) y ``posteriorCount``.
    Sin evidencia posterior ⇒ ``None`` (el componente no puntúa; no se inventa 0).
    """
    weighted = _as_float(row.get("posteriorWeighted"))
    count = _as_float(row.get("posteriorCount"))
    if weighted is None or count is None or count <= 0:
        return None
    return _clamp01(weighted / count)


def _v1_components(row: Mapping[str, Any]) -> dict[str, float]:
    """Componentes presentes (cobertura real) de la señal v1, en ``[0, 1]``."""
    trials = int(row.get("trials") or 0)
    failed = int(row.get("zeroTrade") or 0) + int(row.get("failures") or 0)
    success_ratio = 1.0 if trials <= 0 else _clamp01((trials - failed) / trials)

    components: dict[str, float] = {"success_ratio": success_ratio}
    optional = {
        "is_score": _normalize_is_score(row.get("avgScore")),
        "sharpe": _sharpe_component(row.get("avgSharpe")),
        "profit_factor": _profit_factor_component(row.get("avgProfitFactor")),
        "drawdown": _drawdown_component(row.get("avgMaxDrawdownPct")),
        "posterior": _posterior_component(row),
    }
    for name, value in optional.items():
        if value is not None:
            components[name] = value
    return components


def _family_strength_v0(row: Mapping[str, Any]) -> float:
    """Fuerza v0 (histórica) de una familia a partir de su agregado (en ``[0, 1]``).

    Combina el score medio del LAB con una penalización por fracasos. Se conserva
    **sin cambios** para reproducir snapshots ``discovery_evidence_v0``.
    """
    trials = int(row.get("trials") or 0)
    if trials <= 0:
        return 0.0
    avg_score = row.get("avgScore")
    score_component = 0.0 if avg_score is None else max(0.0, min(1.0, float(avg_score)))
    failed = int(row.get("zeroTrade") or 0) + int(row.get("failures") or 0)
    success_ratio = max(0.0, (trials - failed) / trials)
    return _round(score_component * success_ratio)


def _family_strength_v1(row: Mapping[str, Any]) -> float:
    """Fuerza v1 (V2.37/P2-01): media ponderada con *shrinkage* por cobertura.

    Dos propiedades que la v0 no tenía:

    * **Sin saturación**: cada componente es monótono estricto (``1 - exp(-x)``, ``tanh``),
      de modo que un ``is_score`` de 1.5 aporta más señal que uno de 1.0.
    * **Cobertura neutra**: una métrica ausente no puntúa como 0 (castigo injusto) ni se
      ignora renormalizando (que podía premiar la ausencia). La señal observada se
      *encoge* hacia un ancla neutral ``0.5`` con un peso ``coverage`` igual a la fracción
      de peso de componentes presentes. Con cobertura total el resultado es la media
      ponderada; sin cobertura, el ancla. Monótona y determinista.
    """
    trials = int(row.get("trials") or 0)
    if trials <= 0:
        return 0.0
    components = _v1_components(row)
    present_weight = sum(
        weight for name, weight in _V1_COMPONENT_WEIGHTS.items() if name in components
    )
    total_weight = sum(_V1_COMPONENT_WEIGHTS.values())
    if present_weight <= 0 or total_weight <= 0:
        return 0.0
    observed = sum(
        _V1_COMPONENT_WEIGHTS[name] * value
        for name, value in components.items()
        if name in _V1_COMPONENT_WEIGHTS
    ) / present_weight
    coverage = _clamp01(present_weight / total_weight)
    strength = coverage * observed + (1.0 - coverage) * _V1_NEUTRAL_ANCHOR
    return _round(_clamp01(strength))


def _family_strength(row: Mapping[str, Any], *, math_version: str) -> float:
    """Despacha a la fórmula de fuerza según la versión de la matemática del snapshot."""
    if str(math_version) == MATH_VERSION_DISCOVERY_EVIDENCE_V0:
        return _family_strength_v0(row)
    return _family_strength_v1(row)


def compute_family_weights(
    aggregates: Iterable[Mapping[str, Any]],
    *,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    math_version: str = MATH_VERSION_DISCOVERY_EVIDENCE_V1,
) -> tuple[dict[str, float], dict[str, int]]:
    """Pesos por familia H0 (o clave compuesta familia|region) y tamaños de muestra.

    V2.38 (incremento 3): los agregados pueden venir ya granularizados por **region de
    parametros**. La clave canónica se compone con ``compose_granularity_key``: sin región
    es exactamente la familia (compatibilidad byte a byte con V2.36/V2.37); con región es
    ``familia|region``. Orden canónico por clave compuesta. Las claves por debajo de
    ``min_samples`` se excluyen del mapa de pesos (no aportan señal) pero conservan su
    tamaño de muestra para auditoría.
    """
    from bolsa_application.discovery_param_region import compose_granularity_key



    family_weights: dict[str, float] = {}
    sample_sizes: dict[str, int] = {}
    ordered = sorted(
        aggregates,
        key=lambda r: (
            str(r.get("presetKey") or ""),
            str(r.get("paramRegion") or ""),
        ),
    )
    for row in ordered:
        family = str(row.get("presetKey") or "").strip()
        if not family:
            continue
        region = str(row.get("paramRegion") or "").strip()
        key = compose_granularity_key(family, region)
        trials = int(row.get("trials") or 0)
        sample_sizes[key] = trials
        if trials >= int(min_samples):
            family_weights[key] = _family_strength(row, math_version=math_version)
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


def evidence_fingerprint(
    *,
    aggregates: Iterable[Mapping[str, Any]],
    posterior_cut: str = "",
) -> str:
    """V2.37/P2-03: huella del **conjunto de evidencia agregada** (research dataset).

    Distingue "event-time evidence" (cuándo ocurrió cada trial) de "research dataset
    snapshot" (qué conjunto exacto de filas se agregó). Incluye por familia la muestra y
    la cobertura de métricas, más el corte de evidencia posterior. No incluye
    ``created_at`` ni el reloj: es determinista sobre los datos.
    """
    canonical = json.dumps(
        {
            "families": [
                {
                    "presetKey": str(row.get("presetKey") or ""),
                    "paramRegion": str(row.get("paramRegion") or ""),
                    "trials": int(row.get("trials") or 0),
                    "zeroTrade": int(row.get("zeroTrade") or 0),
                    "failures": int(row.get("failures") or 0),
                    **{
                        key: _as_float(row.get(key))
                        for key in (
                            "avgScore",
                            "avgSharpe",
                            "avgProfitFactor",
                            "avgMaxDrawdownPct",
                        )
                    },
                }
                for row in sorted(aggregates, key=lambda r: str(r.get("presetKey") or ""))
            ],
            "posteriorCut": str(posterior_cut or ""),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:32]}"


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
    math_version: str = MATH_VERSION_DISCOVERY_EVIDENCE_V1,
    posterior_cut: str = "",
) -> DiscoveryEvidenceSnapshot:
    """Construye el snapshot determinista (función pura de ``aggregates``).

    No tiene efectos secundarios: el llamante (job batch/CLI) decide si persiste el
    resultado y es idempotente por ``snapshot_hash``.
    """
    aggregate_list = list(aggregates)
    family_weights, sample_sizes = compute_family_weights(
        aggregate_list, min_samples=min_samples, math_version=math_version
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
    fingerprint = evidence_fingerprint(aggregates=aggregate_list, posterior_cut=posterior_cut)
    # V2.37/P2-03 + V2.38 (incremento 3): desglose de granularidad. La dimension ACTIVA
    # hoy es la region de parametros (bucket determinista v0); regimen y clase de
    # instrumento quedan documentados como pendientes porque NO existen como dato
    # persistido. Aditivo y NO obligatorio: se publica por clave compuesta sin romper el
    # esquema. No participa en el ``snapshot_hash`` (observabilidad para la siguiente
    # evolucion); si participa en ``evidence_fingerprint`` (identidad del dataset).
    granularity: dict[str, Any] = {}
    for row in aggregate_list:
        family = str(row.get("presetKey") or "").strip()
        if not family:
            continue
        region = str(row.get("paramRegion") or "").strip()
        if region:
            granularity[compose_granularity_key(family, region)] = {
                "family": family,
                "paramRegion": region,
            }
    payload: dict[str, Any] = {
        "mathVersion": math_version,
        "windowFrom": window_from,
        "windowTo": window_to,
        "familyWeights": family_weights,
        "laneWeights": lane_weights,
        "sampleSizes": sample_sizes,
        "familyCount": len(family_weights),
        "totalSamples": sum(sample_sizes.values()),
        "evidenceFingerprint": fingerprint,
        "posteriorCut": str(posterior_cut or ""),
        "familyGranularity": granularity,
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
        evidence_fingerprint=fingerprint,
    )
