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


def _merge_aggregates_by_key(
    aggregates: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Fusiona filas con la MISMA clave compuesta ``familia|region`` (P2 nuevo).

    El productor SQL agrupa por ``(preset_key, param_region, regime)``: cuando una misma
    familia|región aparece en varios regímenes llegan VARIAS filas con la misma clave
    compuesta. Agregar con asignación (``sample_sizes[key] = trials``) descartaba todas
    menos la última, perdiendo evidencia real (medido: 60 trials reportados como 30, y una
    familia con 12 trials quedaba por debajo de ``min_total_samples``).

    Reglas de fusión (deterministas):

    * **Contadores** (``trials``, ``zeroTrade``, ``failures``): SUMA.
    * **Ratios** (``avgScore``, ``avgSharpe``, ``avgProfitFactor``, ``avgMaxDrawdownPct``):
      media ponderada por la **cobertura real** de cada métrica, no por ``trials``. El SQL
      calcula cada ratio con ``func.avg`` sobre las filas donde la métrica NO es nula, de
      modo que el denominador correcto es ``metricCoverage[<métrica>]`` (ya expuesto en la
      fila para las cuatro métricas). Ponderar por ``trials`` mezclaría denominadores
      distintos: medido, un sesgo de hasta ~23 % en el Sharpe fusionado y mucho mayor en
      ``avgScore``. Si una fila no trae cobertura (API pura, no el productor SQL) se usa
      ``trials`` como fallback documentado.
    * **Posterior** (``posteriorWeighted``, ``posteriorCount``): SUMA (ya son conteos).
    * **Presupuesto / cobertura**: ``kConsumed`` (``sum(k_contribution)`` en SQL) y
      ``metricCoverage`` (``count(<métrica>)``) SUMAN. ``bestScore``
      (``max(is_score)``) toma el MÁXIMO. Preservar estos campos evita el descarte
      silencioso que sufría la fusión (P3 del revisor).
    * ``regime`` se descarta en el resultado fusionado: NO entra en la clave de
      granularidad (es dimensión paralela, V2.39). El desglose por régimen se publica
      aparte en ``regimeGranularity`` del payload, no aquí.

    Orden canónico por clave compuesta ⇒ salida reproducible. Una entrada con una sola
    fila por clave devuelve exactamente las mismas métricas (compatibilidad byte a byte).
    """
    # Métrica de ratio -> clave de ``metricCoverage`` que da su tamaño de muestra real.
    ratio_coverage: dict[str, str] = {
        "avgScore": "score",
        "avgSharpe": "sharpeRatio",
        "avgProfitFactor": "profitFactor",
        "avgMaxDrawdownPct": "maxDrawdownPct",
    }
    ratio_keys = tuple(ratio_coverage)
    # Orden de entrada canónico ANTES de acumular: la suma flotante es sensible al orden
    # en el último bit; ordenar aquí garantiza que dos ejecuciones con distinto orden de
    # BD produzcan bit a bit el mismo acumulador (robustez de determinismo).
    ordered_rows = sorted(
        aggregates,
        key=lambda r: (
            str(r.get("presetKey") or ""),
            str(r.get("paramRegion") or ""),
            str(r.get("regime") or ""),
        ),
    )
    merged: dict[str, dict[str, Any]] = {}
    for row in ordered_rows:
        family = str(row.get("presetKey") or "").strip()
        if not family:
            continue
        region = str(row.get("paramRegion") or "").strip()
        key = compose_granularity_key(family, region)
        entry = merged.get(key)
        if entry is None:
            entry = {
                "presetKey": family,
                "paramRegion": region,
                "trials": 0,
                "zeroTrade": 0,
                "failures": 0,
                "posteriorWeighted": 0.0,
                "posteriorCount": 0.0,
                # Presupuesto consumido: ``sum(k_contribution)`` en SQL -> SUMA.
                "kConsumed": 0,
                # Mejor score observado: ``max(is_score)`` en SQL -> MAXIMO.
                "bestScore": None,
                # Cobertura real por metrica: ``count(<metrica>)`` -> SUMA por contador.
                "_coverage": {
                    "score": 0,
                    "sharpeRatio": 0,
                    "profitFactor": 0,
                    "maxDrawdownPct": 0,
                },
                # Acumulador interno: suma ponderada por métrica. No se publica.
                "_weighted_sum": {name: 0.0 for name in ratio_keys},
                "_weighted_n": {name: 0 for name in ratio_keys},
            }
            merged[key] = entry
        trials = int(row.get("trials") or 0)
        entry["trials"] += trials
        entry["zeroTrade"] += int(row.get("zeroTrade") or 0)
        entry["failures"] += int(row.get("failures") or 0)
        entry["kConsumed"] += int(row.get("kConsumed") or 0)
        best = _as_float(row.get("bestScore"))
        if best is not None:
            current_best = entry["bestScore"]
            entry["bestScore"] = best if current_best is None else max(current_best, best)
        entry["posteriorWeighted"] += float(_as_float(row.get("posteriorWeighted")) or 0.0)
        entry["posteriorCount"] += float(_as_float(row.get("posteriorCount")) or 0.0)
        coverage = row.get("metricCoverage")
        coverage = coverage if isinstance(coverage, Mapping) else {}
        for cov_key in entry["_coverage"]:
            entry["_coverage"][cov_key] += int(coverage.get(cov_key) or 0)
        for name, coverage_key in ratio_coverage.items():
            value = _as_float(row.get(name))
            if value is None:
                continue
            # Peso = tamaño de muestra real de la métrica (su cobertura). Si la fila no la
            # declara (API pura) se cae a ``trials`` como cota superior documentada.
            weight = int(coverage.get(coverage_key) or 0)
            if weight <= 0:
                weight = trials
            if weight <= 0:
                continue
            entry["_weighted_sum"][name] += value * weight
            entry["_weighted_n"][name] += weight

    result: list[dict[str, Any]] = []
    for key in sorted(merged):
        entry = merged[key]
        out: dict[str, Any] = {
            "presetKey": entry["presetKey"],
            "paramRegion": entry["paramRegion"],
            "trials": entry["trials"],
            "zeroTrade": entry["zeroTrade"],
            "failures": entry["failures"],
            "kConsumed": entry["kConsumed"],
        }
        # ``bestScore`` solo si alguna fila lo trajo (ausente != 0).
        if entry["bestScore"] is not None:
            out["bestScore"] = entry["bestScore"]
        # Cobertura real por metrica, acumulada por contador (no mezclar con ratios).
        out["metricCoverage"] = {
            cov_key: int(value) for cov_key, value in entry["_coverage"].items()
        }
        # Posterior solo si hubo evidencia (coherente con ``_posterior_component``).
        if entry["posteriorCount"] > 0:
            out["posteriorWeighted"] = entry["posteriorWeighted"]
            out["posteriorCount"] = entry["posteriorCount"]
        for name in ratio_keys:
            n = entry["_weighted_n"][name]
            if n > 0:
                out[name] = _round(entry["_weighted_sum"][name] / n)
            # Si n == 0 la métrica queda ausente (no se emite la clave).
        result.append(out)
    return result


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

    P2 nuevo: la entrada se FUSIONA primero por clave compuesta
    (``_merge_aggregates_by_key``). El productor SQL rompe por régimen, de modo que una
    misma familia|región puede llegar en varias filas; sin la fusión, la última fila
    sobrescribía el resto y se descartaba evidencia real.
    """
    family_weights: dict[str, float] = {}
    sample_sizes: dict[str, int] = {}
    for row in _merge_aggregates_by_key(aggregates):
        family = str(row.get("presetKey") or "").strip()
        region = str(row.get("paramRegion") or "").strip()
        key = compose_granularity_key(family, region)
        trials = int(row.get("trials") or 0)
        sample_sizes[key] = trials
        if trials >= int(min_samples):
            family_weights[key] = _family_strength(row, math_version=math_version)
    return family_weights, sample_sizes


def _effective_total_samples(
    family_weights: Mapping[str, float],
    sample_sizes: Mapping[str, int],
) -> int:
    """Suma SOLO el tamaño de muestra de las familias que sí aportan peso.

    P2 (v2.39.3): ``sample_sizes`` guarda el tamaño de TODAS las familias (incluso las
    que no superaron ``min_samples`` y nunca aportaron peso a ``family_weights``), para
    auditoría. ``min_total_samples`` debe medir cuánta evidencia ÚTIL hay detrás del
    carril adaptativo, no cualquier evidencia: sin este filtro, un puñado de familias
    descartadas por tener pocos trials podía inflar el contador global y dejar que una
    única familia con el mínimo (``min_samples``) activase el carril.
    """
    return sum(int(n) for key, n in sample_sizes.items() if key in family_weights)


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
    total_samples = _effective_total_samples(family_weights, sample_sizes)
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

    ALCANCE DEL CONTRATO (importante): esta huella se calcula sobre las filas CRUDAS, con
    el régimen como dimensión (V2.39), mientras que ``compute_family_weights`` opera sobre
    las filas FUSIONADAS por ``familia|region`` (el régimen colapsa, P2). Son dos
    granularidades deliberadamente distintas: el fingerprint es **trazabilidad del input
    crudo** (identidad del dataset), NO una clave de equivalencia de pesos. Dos datasets
    que difieren solo en el reparto por régimen comparten ``snapshot_hash`` (el reparto de
    cupos es el mismo) pero tienen fingerprints distintos. No usar el fingerprint para
    deduplicar snapshots ni para inferir que los pesos coinciden.
    """
    canonical = json.dumps(
        {
            "families": [
                {
                    "presetKey": str(row.get("presetKey") or ""),
                    "paramRegion": str(row.get("paramRegion") or ""),
                    # V2.39 (incremento 4): regimen como dimension de identidad del
                    # dataset. Es paralelo a la clave de granularidad: no altera
                    # `compute_family_weights` ni el reparto de cupos.
                    "regime": str(row.get("regime") or ""),
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
                # V2.38.1/P2-02: orden canonico por clave COMPUESTA (familia, region),
                # identico al de ``compute_family_weights``. Ordenar solo por ``presetKey``
                # dejaba el orden entre regiones de una misma familia a merced del orden de
                # entrada (fragilidad latente en un valor que es identidad del dataset).
                # V2.39: se anade el regimen como tercer criterio, por la misma razon.
                for row in sorted(
                    aggregates,
                    key=lambda r: (
                        str(r.get("presetKey") or ""),
                        str(r.get("paramRegion") or ""),
                        str(r.get("regime") or ""),
                    ),
                )
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
    # V2.39 (incremento 4): regimen de mercado (clasificador determinista v0), derivado de
    # las barras del trial. Dimension PARALELA a la clave de granularidad: se publica
    # aparte, no entra en ``compute_family_weights`` ni en la clave ``familia|region``, y
    # tampoco en el ``snapshot_hash``. Aditivo: sin regimen queda vacio.
    regime_granularity: dict[str, Any] = {}
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
        regime = str(row.get("regime") or "").strip()
        if regime:
            composite = compose_granularity_key(family, region)
            regimes = regime_granularity.setdefault(composite, {})
            # ACUMULA, no sobrescribe: por API pura pueden llegar dos filas con el mismo
            # ``(familia, region, regime)``; asignar perdía trials y dejaba el payload
            # incoherente con ``sampleSizes`` (que sí suma).
            regimes[regime] = regimes.get(regime, 0) + int(row.get("trials") or 0)
    payload: dict[str, Any] = {
        "mathVersion": math_version,
        "windowFrom": window_from,
        "windowTo": window_to,
        "familyWeights": family_weights,
        "laneWeights": lane_weights,
        "sampleSizes": sample_sizes,
        "familyCount": len(family_weights),
        "totalSamples": _effective_total_samples(family_weights, sample_sizes),
        "evidenceFingerprint": fingerprint,
        "posteriorCut": str(posterior_cut or ""),
        "familyGranularity": granularity,
        "regimeGranularity": regime_granularity,
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
