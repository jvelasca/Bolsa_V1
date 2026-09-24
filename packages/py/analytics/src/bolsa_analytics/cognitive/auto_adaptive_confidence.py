"""AUTO-12 — Confidence y calidad estadística del Adaptive AUTO (PURA y READ-ONLY).

Cierra la deuda que declaró la propia ``V2.52``: Adaptive ya recuerda su estado (journal
durable), pero todavía no sabía **cuánto creer** a lo que estaba aprendiendo. Hasta aquí el
único gate de muestra era **binario** (``decisive``, ``trades >= min_trades``): dentro de él,
una celda de ``N = 12`` pesaba exactamente igual que una de ``N = 180``.

Qué publica, por ``strategyVersion`` (y por celda ``strategy × regime``):

* **``sample_size`` / ``measured_n`` / ``episodes`` / ``effective_n``** — la muestra bruta; la
  muestra que de verdad **sostiene** el número (los ciclos con R medido, el denominador real de
  ``expectancy_r``); cuántas **rachas de régimen** (episodios) cubren esos ciclos medidos; y la
  muestra **efectiva**, que es la que la independencia permite afirmar
  (``effective_n = min(measured_n, episodes)``). Una celda de 40 ciclos con 3 R medidos no es una
  muestra de 40, y 100 ciclos dentro de una **misma fase de mercado** no son 100 observaciones
  independientes (``AUTO-18``).
* **``measurement_completeness``** — el peor estado de medición del ciclo
  (R / R neto / PnL): ``COMPLETE`` es lo único que autoriza a confiar sin descuento. El R
  neto depende de un coste **estimado**, así que un ``PARTIAL`` se declara en vez de leerse
  como medido.
* **``risk_coverage`` / ``cost_coverage`` / ``regime_coverage``** — qué fracción de la
  muestra aportó cada eje. El régimen ausente cuenta como no cubierto (un ciclo sin régimen
  declarado no prueba el cruce).
* **``long_expectancy_r`` / ``recent_expectancy_r``** — la ventana LARGA y la RECIENTE del
  MISMO material. Es el hueco que el audit nombra: ``LONG +0.21R`` con ``RECENT -0.15R`` era
  invisible porque solo existía una agregación.
* **``decay``** — ``NONE`` / ``MILD`` / ``SEVERE`` / ``UNKNOWN``: el deterioro reciente
  **declarado**. Nunca pausa por sí solo (la pausa es de la rotación); aquí es evidencia.
* **``confidence``** — ``LOW`` / ``MEDIUM`` / ``HIGH``: bandas **declaradas**, no inferidas,
  con techo explícito cuando la lectura no se pudo completar. La banda mide la **calidad de la
  medición** (muestra medida + completitud + deterioro), como desde ``AUTO-12``.
* **``coverage``** (``AUTO-18``) — ``HIGH`` / ``MEDIUM`` / ``LOW`` / ``UNCOVERED``: la
  **cobertura por independencia** de cada celda ``strategy × regime``, derivada de su
  ``effective_n``. Es un eje **distinto** de la banda: una celda puede estar bien medida
  (``confidence = HIGH``) y cubrir una sola fase de mercado (``coverage = LOW``), y las dos
  lecturas se publican por separado para que nadie las lea como una.
* **``shrunk_expectancy_r``** (``AUTO-18``) — la expectancy **encogida por muestra efectiva**
  (``r · n/(n + prior)``), publicada como evidencia read-only. El **uso** de ese encogimiento
  en el reparto vive en ``auto_adaptive`` (la política versionada); aquí solo se **mide**.
* **``calibration``** (``AUTO-18``) — la tabla **descriptiva** banda → qué se observó en ella
  (``n`` medido, expectativa y win rate realizados, dispersión) comparada con el **suelo de
  muestra** que la banda promete. Es un diagnóstico **read-only**: NO mueve la banda ni el
  reparto, y NO afirma nada sobre la calidad del edge (una banda alta significa "bien medido",
  no "bueno").

Disciplina de medición (la del repo, y aquí es el punto entero del módulo):

* **Lo que no se midió se declara.** Sin fechas legibles no hay ventana reciente: se publica
  ``recent_unavailable`` y ``decay = UNKNOWN`` — jamás se ordena por posición de lista
  fingiendo cronología (la lección que ``cycle_risk`` cerró en ``V2.52``).
* **Ausencia de dato ≠ dato malo.** Una muestra fina NO se castiga a ciegas: se declara
  ``LOW``. El encogimiento del reparto por tamaño de muestra vive en ``auto_adaptive`` (la
  política), no aquí.
* **``AUTO-18`` — una racha no es una muestra.** Los ciclos MEDIDOS se agrupan en **rachas de
  régimen** sobre el orden por instante: ``episodes`` las cuenta y ``effective_n`` es el mínimo
  entre la muestra medida y esos episodios. Es una cota **conservadora declarada** (no una
  varianza muestral): no pretende medir la autocorrelación exacta, solo impedir que 100 ciclos
  de una misma fase se lean como 100 observaciones independientes. Un ciclo con régimen
  ``UNKNOWN`` es su propio valor de racha (nunca se funde con un régimen conocido).
* **La agregación es la MISMA que ``AUTO-7``/``AUTO-9``.** Las ventanas se agregan con
  ``evaluate_auto_self_evaluation``, así que la deduplicación por identidad, el cubo
  ``UNKNOWN`` de régimen y los huecos de medición son exactamente los del informe; este
  módulo no reimplementa ninguna de esas semánticas.

**Read-only por contrato**: no modifica pesos, ni sizing, ni estado. ``confidence`` es una
BANDA de lectura, nunca un permiso.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from statistics import pstdev
from typing import Any

from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_COST_BASIS_APPLIED,
    SELF_EVAL_COST_BASIS_ESTIMATED,
    SELF_EVAL_COST_BASIS_MIXED,
    SELF_EVAL_COST_BASIS_UNDECLARED,
    SELF_EVAL_COST_MODEL_MIXED,
    SELF_EVAL_COST_MODEL_UNDECLARED,
    SELF_EVAL_MIN_TRADES_DEFAULT,
    SELF_EVAL_REGIME_UNKNOWN,
    AutoSelfEvaluation,
    NetRBasisSeries,
    StrategyRegimeEvaluation,
    StrategySelfEvaluation,
    cycle_r,
    evaluate_auto_self_evaluation,
)
from bolsa_analytics.cognitive.expectancy import sample_quality_from_n
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MeasurementStatus,
    combine_measurements,
    measurement_from_counts,
)

__all__ = [
    "ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED",
    "ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT",
    "ADAPTIVE_CONFIDENCE_HIGH",
    "ADAPTIVE_CONFIDENCE_LOW",
    "ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE",
    "ADAPTIVE_CONFIDENCE_MEDIUM",
    "ADAPTIVE_CONFIDENCE_NO_CYCLES",
    "ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT",
    "ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE",
    "ADAPTIVE_CONFIDENCE_RECENT_UNDATED",
    "ADAPTIVE_CONFIDENCE_THIN_SAMPLE",
    "ADAPTIVE_COVERAGE_HIGH",
    "ADAPTIVE_COVERAGE_LOW",
    "ADAPTIVE_COVERAGE_MEDIUM",
    "ADAPTIVE_COVERAGE_UNCOVERED",
    "ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT",
    "ADAPTIVE_BASIS_MIXED",
    "ADAPTIVE_BASIS_STABLE_APPLIED",
    "ADAPTIVE_BASIS_STABLE_ESTIMATED",
    "ADAPTIVE_BASIS_COST_MODEL_TRANSITION",
    "ADAPTIVE_BASIS_DATA_DEGRADED",
    "ADAPTIVE_BASIS_TRANSITION",
    "ADAPTIVE_BASIS_UNKNOWN",
    "ADAPTIVE_DECAY_MILD",
    "ADAPTIVE_DECAY_NONE",
    "ADAPTIVE_DECAY_SEVERE",
    "ADAPTIVE_DECAY_THRESHOLD",
    "ADAPTIVE_DECAY_UNKNOWN",
    "ADAPTIVE_LONG_WINDOW_DEFAULT",
    "ADAPTIVE_RECENT_WINDOW_DEFAULT",
    "AdaptiveConfidence",
    "BasisTransition",
    "ConfidenceCalibration",
    "RegimeConfidence",
    "StrategyConfidence",
    "build_adaptive_confidence",
]

#: Ventana LARGA por defecto (últimos ciclos): el histórico contra el que se compara.
ADAPTIVE_LONG_WINDOW_DEFAULT = 200
#: Ventana RECIENTE por defecto (últimos ciclos): el presente que puede contradecir al histórico.
ADAPTIVE_RECENT_WINDOW_DEFAULT = 30
#: Umbral de deterioro: por debajo de ``long * 0.75`` la expectativa reciente ya decae.
ADAPTIVE_DECAY_THRESHOLD = 0.75

#: Bandas de confianza (vocabulario PROPIO del módulo: ``StrategyHealth.confidence`` las lleva).
ADAPTIVE_CONFIDENCE_LOW = "LOW"
ADAPTIVE_CONFIDENCE_MEDIUM = "MEDIUM"
ADAPTIVE_CONFIDENCE_HIGH = "HIGH"
#: Orden creciente: se usa para bajar/poner techo sin ramas dispersas.
_CONFIDENCE_ORDER: tuple[str, ...] = (
    ADAPTIVE_CONFIDENCE_LOW,
    ADAPTIVE_CONFIDENCE_MEDIUM,
    ADAPTIVE_CONFIDENCE_HIGH,
)

#: Estados de deterioro. ``UNKNOWN`` NO es "sin deterioro": es "no se pudo comparar".
ADAPTIVE_DECAY_NONE = "NONE"
ADAPTIVE_DECAY_MILD = "MILD"
ADAPTIVE_DECAY_SEVERE = "SEVERE"
ADAPTIVE_DECAY_UNKNOWN = "UNKNOWN"

# ── AUTO-18 — la COBERTURA por independencia (rachas de régimen) ────────────────────
#
# ``AUTO-12`` midió la muestra que sostiene el número (ciclos con R medido); ``AUTO-18`` mide
# cuántas **fases de mercado** independientes la sostienen. 100 ciclos dentro de una sola racha
# de régimen no son 100 observaciones: son una. La cobertura es un eje PROPIO (distinto de la
# banda), y su vocabulario se declara en lugar de inferirse.
#: La celda cubre varias fases de mercado con muestra efectiva de sobra.
ADAPTIVE_COVERAGE_HIGH = "HIGH"
#: Cobertura intermedia: hay más de una fase, pero la muestra efectiva aún es fina.
ADAPTIVE_COVERAGE_MEDIUM = "MEDIUM"
#: Una o pocas fases: la evidencia existe, pero no prueba generalidad.
ADAPTIVE_COVERAGE_LOW = "LOW"
#: Ningún ciclo medido: no hay nada que cubrir, y se declara (nunca un cero mudo).
ADAPTIVE_COVERAGE_UNCOVERED = "UNCOVERED"

#: Suelo de muestra MEDIDA que cada banda **promete** (el mínimo que su construcción exige: la
#: banda base sale de ``sample_quality_from_n(measured_n)``). Es la mitad declarada de la
#: calibración: si una lectura observara una banda por debajo de su suelo, habría un fallo en el
#: constructor (la banda solo BAJA desde la base por medición/deterioro; nunca sube).
_PROMISED_MIN_N: dict[str, int] = {
    ADAPTIVE_CONFIDENCE_LOW: 0,
    ADAPTIVE_CONFIDENCE_MEDIUM: 20,
    ADAPTIVE_CONFIDENCE_HIGH: 50,
}

#: Prior del encogimiento por muestra efectiva (AUTO-18): ``shrink = n / (n + prior)``. Es la
#: MISMA constante que sella ``AdaptivePolicy.confidence_prior`` en ``auto_adaptive`` (un solo
#: número, declarado una vez) y se publica aquí para que la lectura de confianza pueda publicar
#: su ``shrunk_expectancy_r`` sin depender de la capa de política.
ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT = 20.0

# ── AUTO-17/18 — la TRANSICIÓN de población del R neto (base y modelo de coste) ─────
#
# La base del R neto es una dimensión estadística: si la ventana LARGA y la RECIENTE no se
# midieron contra el mismo modelo de coste, comparar sus expectativas no mide deterioro ni
# mejora —mide el cambio de metro—. Estos estados lo declaran, y solo ``TRANSITION``/``MIXED``/
# ``COST_MODEL_TRANSITION`` bloquean la comparación (un ``UNKNOWN`` significa "no hay net con el
# que decidirlo": se deja el comportamiento histórico intacto, porque el desconocido no es un
# defecto).
#
# ``AUTO-18`` añade el SEGUNDO eje: la población comparable es ``(base, versión del modelo)``.
# ``MIXED`` es la **heterogeneidad interna** de una ventana (mezcla bases, o mezcla metros) y
# ``COST_MODEL_TRANSITION`` el **cambio temporal** del metro entre ventanas: son dos ejes
# distintos y se publican por separado.
class BasisTransition(StrEnum):
    """(AUTO-18, §16) vocabulario CERRADO de los estados de población del R neto.

    ``str`` ⇒ ``json.dumps`` los serializa igual que los literales de siempre (JSON byte-idéntico).
    El enum distingue los DOS ejes que ``AUTO-17/18`` publican por separado:

    * **Heterogeneidad INTERNA** de una ventana → :attr:`MIXED` (la ventana mezcla bases, o
      mezcla metros).
    * **Cambio TEMPORAL** entre la ventana larga y la reciente → :attr:`TRANSITION` (cambió la
      BASE) y :attr:`COST_MODEL_TRANSITION` (cambió el METRO con la base intacta).

    :attr:`DATA_DEGRADED` es el neto PRESENTE cuya base nadie declaró (``undeclared``): un número
    sin metro, que se lee con **baja confianza**. Es distinto del :attr:`UNKNOWN` inocuo (no hay
    neto con el que decidir, y por eso el comportamiento histórico se conserva intacto).
    Estados que BLOQUEAN la comparación de expectativas: ``TRANSITION``, ``MIXED`` y
    ``COST_MODEL_TRANSITION``.
    """

    STABLE_ESTIMATED = "STABLE_ESTIMATED"
    STABLE_APPLIED = "STABLE_APPLIED"
    TRANSITION = "TRANSITION"
    MIXED = "MIXED"
    COST_MODEL_TRANSITION = "COST_MODEL_TRANSITION"
    DATA_DEGRADED = "DATA_DEGRADED"
    UNKNOWN = "UNKNOWN"


#: La ventana larga mide contra el coste que el decisor SUPUSO.
ADAPTIVE_BASIS_STABLE_ESTIMATED = BasisTransition.STABLE_ESTIMATED.value
#: La ventana larga mide contra la fricción que el simulador APLICÓ.
ADAPTIVE_BASIS_STABLE_APPLIED = BasisTransition.STABLE_APPLIED.value
#: La base cambió entre ventanas: la comparación NO es deterioro ni mejora.
ADAPTIVE_BASIS_TRANSITION = BasisTransition.TRANSITION.value
#: El agregado mezcla bases (no hay un único modelo que comparar).
ADAPTIVE_BASIS_MIXED = BasisTransition.MIXED.value
#: AUTO-18 — la base es la misma, pero el METRO (versión del modelo de coste) cambió entre
#: ventanas: la comparación mide el instrumento, no el rendimiento. Es un eje propio, distinto de
#: ``MIXED`` (heterogeneidad interna) y de ``TRANSITION`` (cambio temporal de BASE).
ADAPTIVE_BASIS_COST_MODEL_TRANSITION = BasisTransition.COST_MODEL_TRANSITION.value
#: AUTO-18 — hay neto, pero la fila no declara la base (``undeclared``): un número sin metro. No
#: es el ``UNKNOWN`` inocuo de "no hay neto": se declara **baja confianza** y NO afirma una
#: estabilidad que nadie firmó. No bloquea la comparación (no hay una base que comparar), pero la
#: banda se rebaja y el hueco se nombra.
ADAPTIVE_BASIS_DATA_DEGRADED = BasisTransition.DATA_DEGRADED.value
#: No hay base declarada con la que decidir la transición (net ausente: el desconocido no es un
#: defecto y el comportamiento histórico se conserva intacto).
ADAPTIVE_BASIS_UNKNOWN = BasisTransition.UNKNOWN.value

# ── Huecos declarados (vocabulario propio: nunca se rellenan, se nombran) ───────────
ADAPTIVE_CONFIDENCE_NO_CYCLES = "no_cycles"
ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE = "recent_unavailable"
ADAPTIVE_CONFIDENCE_RECENT_UNDATED = "recent_undated"
ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT = "recent_insufficient"
ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE = "measurement_incomplete"
ADAPTIVE_CONFIDENCE_THIN_SAMPLE = "thin_sample"
#: AUTO-18 — la muestra efectiva quedó por debajo de la medida porque los ciclos forman menos
#: rachas de régimen que observaciones: el descuento por falta de independencia se declara.
ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT = "episode_discount"
#: AUTO-18 — hay neto pero su base no está declarada (``DATA_DEGRADED``): el número se lee con
#: baja confianza porque nadie firmó con qué metro se midió. Se nombra, no se inventa la base.
ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED = "basis_undeclared"

#: Bandas de ``sample_quality_from_n`` → banda de confianza (la MISMA convención del repo).
_QUALITY_BAND: dict[str, str] = {
    "insufficient": ADAPTIVE_CONFIDENCE_LOW,
    "preliminary": ADAPTIVE_CONFIDENCE_MEDIUM,
    "developing": ADAPTIVE_CONFIDENCE_HIGH,
    "useful": ADAPTIVE_CONFIDENCE_HIGH,
}


# ── Coerción tolerante del instante de cierre (dict u objeto, snake_case o camelCase) ──


def _field(raw: Any, *names: str) -> Any:
    """Primer campo presente de ``names`` en un ``Mapping`` o en un objeto; ``None`` si no."""
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
        return None
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return None


def _instant(value: Any) -> datetime | None:
    """Instante legible de un ``closedAt`` (ISO-8601), o ``None`` si no lo es.

    Mismo criterio que ``cycle_risk._instant`` (área de aplicación, que este paquete NO puede
    importar por la dirección de dependencia del repo): se parsea de verdad, y sin zona horaria
    se asume UTC — nunca se ordena comparando texto, que solo coincide con el orden
    cronológico mientras TODOS los orígenes serialicen con el mismo ancho fijo.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _identity(raw: Any) -> str:
    """Identidad del ciclo (para desempatar dos instantes idénticos de forma determinista)."""
    value = _field(raw, "cycleId", "cycle_id", "signalId", "signal_id")
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _closed_instant(raw: Any) -> datetime | None:
    return _instant(_field(raw, "closedAt", "closed_at"))


def _order_by_instant(rows: Sequence[Any]) -> tuple[list[Any], int]:
    """Ordena de VIEJA a NUEVA y devuelve ``(filas, nº sin instante legible)``.

    Las filas sin instante legible van **al final** y se cuentan: el orden no las esconde.
    El desempate por identidad hace el resultado independiente del orden de llegada.
    """
    dated: list[tuple[datetime, str, int, Any]] = []
    undated: list[Any] = []
    for index, raw in enumerate(rows):
        instant = _closed_instant(raw)
        if instant is None:
            undated.append(raw)
        else:
            dated.append((instant, _identity(raw), index, raw))
    dated.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in dated] + undated, len(undated)


def _coverage(valued: int, total: int) -> float:
    """Fracción cubierta (``0.0`` sin muestra: no hay nada que cubrir, y se declara)."""
    if total <= 0:
        return 0.0
    return round(max(0, valued) / total, 4)


def _round4(value: float) -> float:
    """Redondeo de la casa (4 decimales), el mismo de ``AUTO-7``/``AUTO-9``."""
    return round(value, 4)


def _regime_of(raw: Any) -> str:
    """Régimen declarado por una fila de ciclo, o el cubo ``UNKNOWN`` (espejo de ``AUTO-9``).

    Un ciclo que se declara literalmente ``unknown`` (en cualquier caja) es el cubo ``UNKNOWN``,
    no un régimen: nunca se le atribuye el de otro ciclo.
    """
    value = _field(raw, "regime", "marketRegime", "market_regime")
    text = str(value).strip() if isinstance(value, str) and value.strip() else ""
    if not text or text.upper() == SELF_EVAL_REGIME_UNKNOWN:
        return SELF_EVAL_REGIME_UNKNOWN
    return text


def _measured_r(raw: Any) -> float | None:
    """R medido de una fila de ciclo, con la MISMA regla que el informe (sin segundo cociente).

    Si la fila ya declara su R se cree (es una medida de su productor); si no, se calcula con
    ``cycle_r`` —el cociente de ``AUTO-9``— desde el PnL y el riesgo comprometido. Un ciclo sin
    riesgo positivo no tiene R: ``None`` (nunca un ``0``, que diría "no pasó nada").
    """
    value = _field(raw, "r_multiple", "rMultiple", "r")
    if value is not None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number
    return cycle_r(
        pnl=_field(raw, "pnl", "realized_pnl", "realizedPnl", "pnl_currency"),
        risk_amount=_field(raw, "risk_amount", "riskAmount", "reserved_risk", "reservedRisk"),
    ).r_multiple


def _episodes(rows: Sequence[Any]) -> dict[str, dict[str, int]]:
    """(PURA, ``AUTO-18``) rachas de régimen por versión, sobre los ciclos MEDIDOS ordenados.

    Devuelve ``{version: {regimen: nº de rachas}}``. Una racha se corta cuando cambia el régimen
    (``UNKNOWN`` es un valor de racha PROPIO: nunca se funde con un régimen conocido). Los ciclos
    de una misma fase de mercado cuentan como **una** observación independiente, no como N. Solo
    entran los ciclos con R medido: un ciclo sin medida no aporta al denominador del número.

    El orden de ``rows`` es responsabilidad del llamante (las ventanas ya vienen ordenadas por
    instante): la racha se define sobre el orden cronológico, no sobre el de llegada.
    """
    runs: dict[str, dict[str, int]] = {}
    previous: dict[str, str] = {}
    for row in rows:
        version = str(_field(row, "strategyVersion", "strategy_version") or "")
        if not version or _measured_r(row) is None:
            continue
        regime = _regime_of(row)
        counts = runs.setdefault(version, {})
        if previous.get(version) != regime:
            counts[regime] = counts.get(regime, 0) + 1
        previous[version] = regime
    return runs


def _coverage_band(measured_n: int, effective_n: int) -> str:
    """Nivel de COBERTURA por independencia de una celda (``AUTO-18``).

    Sin ciclos medidos no hay nada que cubrir: ``UNCOVERED`` (nunca un cero mudo). Con muestra,
    el nivel sale de la muestra EFECTIVA (episodios) con la MISMA convención de bandas del repo
    (``sample_quality_from_n``): ``insufficient`` ⇒ ``LOW``, ``preliminary`` ⇒ ``MEDIUM``,
    ``developing``/``useful`` ⇒ ``HIGH``. Es un eje PROPIO, distinto de la banda de confianza.
    """
    if measured_n <= 0 or effective_n <= 0:
        return ADAPTIVE_COVERAGE_UNCOVERED
    quality = sample_quality_from_n(effective_n)
    if quality in ("developing", "useful"):
        return ADAPTIVE_COVERAGE_HIGH
    if quality == "preliminary":
        return ADAPTIVE_COVERAGE_MEDIUM
    return ADAPTIVE_COVERAGE_LOW


def _shrunk(expectancy_r: float | None, effective_n: int, prior: float) -> float | None:
    """(PURA, ``AUTO-18``) la expectancy encogida por muestra efectiva, o ``None``.

    ``r · n/(n + prior)``: sin muestra efectiva (``n = 0``) no hay número que encoger —se
    declara la ausencia (``None``), no un ``0`` que diría "sin edge"— y sin expectativa medida
    tampoco. El encogimiento **solo** reduce —nunca premia— y es la MISMA aritmética que el
    reparto aplica al peso; aquí se publica como evidencia read-only.
    """
    if expectancy_r is None:
        return None
    n = max(0, int(effective_n))
    if n <= 0:
        return None
    denominator = n + max(0.0, float(prior))
    if denominator <= 0:
        return None
    return _round4(expectancy_r * (n / denominator))


def _lower(level: str, *, steps: int = 1) -> str:
    """Baja una banda (o dos); el suelo es ``LOW``."""
    index = max(0, _CONFIDENCE_ORDER.index(level) - max(0, steps))
    return _CONFIDENCE_ORDER[index]


def _ceiling(level: str, cap: str) -> str:
    """Pone techo a una banda: no se premia por encima de ``cap``."""
    return _CONFIDENCE_ORDER[min(_CONFIDENCE_ORDER.index(level), _CONFIDENCE_ORDER.index(cap))]


def _band(
    *,
    measured_n: int,
    completeness: MeasurementStatus,
    decay: str,
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN,
) -> str:
    """Banda de confianza declarada a partir de la muestra, la medición y el deterioro.

    Orden de aplicación (el techo SIEMPRE al final: no se premia lo que no se pudo leer):

    1. Base por ``sample_quality_from_n(measured_n)`` — la convención del repo.
    2. Medición incompleta baja un nivel (``PARTIAL``) o dos (``UNKNOWN``).
    3. ``decay == SEVERE`` baja un nivel.
    4. ``AUTO-18``: ``basis_transition == DATA_DEGRADED`` (hay neto sin base declarada) baja un
       nivel — un número sin metro no se lee como uno bien medido.
    5. ``decay == UNKNOWN`` pone techo ``MEDIUM``.

    ``AUTO-18`` la deja sobre la muestra **medida** (la que sostiene el número): la independencia
    (episodios) tiene su propio eje publicado (``coverage``) y su propio consumidor (el
    encogimiento), así que colapsar los dos ejes en la banda escondería cuál falla. Una celda
    puede estar bien medida (``HIGH``) y cubrir una sola fase (``coverage = LOW``).
    """
    level = _QUALITY_BAND[sample_quality_from_n(measured_n)]
    if completeness == MEASUREMENT_PARTIAL:
        level = _lower(level, steps=1)
    elif completeness != MEASUREMENT_COMPLETE:
        level = _lower(level, steps=2)
    if decay == ADAPTIVE_DECAY_SEVERE:
        level = _lower(level, steps=1)
    if basis_transition == ADAPTIVE_BASIS_DATA_DEGRADED:
        level = _lower(level, steps=1)
    if decay == ADAPTIVE_DECAY_UNKNOWN:
        level = _ceiling(level, ADAPTIVE_CONFIDENCE_MEDIUM)
    return level


def _declared_cost_model(value: str | None) -> str | None:
    """(PURA, ``AUTO-18``) la versión de modelo DECLARADA, o ``None`` si la fila no la declara.

    ``undeclared`` (histórico anterior a la fase) y la ausencia valen lo mismo: no hay metro
    afirmable. La ausencia **no se reconstruye** desde los bps de hoy, que podrían no ser los que
    midieron la operación.
    """
    text = str(value).strip() if isinstance(value, str) and value.strip() else ""
    if not text or text == SELF_EVAL_COST_MODEL_UNDECLARED:
        return None
    return text


def _basis_transition(
    long_basis: str | None,
    recent_basis: str | None,
    *,
    long_cost_model: str | None = None,
    recent_cost_model: str | None = None,
) -> str:
    """(PURA, AUTO-17/18) ¿comparten POBLACIÓN la ventana LARGA y la RECIENTE?

    La regla dura de la fase: si la base del R neto —o el **metro** con el que se midió— cambió
    entre las dos ventanas, comparar sus expectativas mide el instrumento, no el rendimiento. La
    población comparable es ``(base, versión del modelo de coste)``, y los estados que la
    declaran son tres, en dos ejes distintos:

    * ``MIXED`` — **heterogeneidad interna**: alguna ventana mezcla bases, o mezcla metros.
    * ``TRANSITION`` — **cambio temporal de la base** (``estimated`` ↔ ``applied``).
    * ``COST_MODEL_TRANSITION`` — misma base, **cambio temporal del metro**.
    * ``DATA_DEGRADED`` — hay neto pero la base no está declarada (``undeclared``): número sin
      metro, de lectura con baja confianza. NO es un cambio, así que no bloquea la comparación,
      pero tampoco se confunde con el ``UNKNOWN`` inocuo.

    ``UNKNOWN`` (sin net, o con el metro declarado en una sola de las dos ventanas) NO bloquea
    nada, porque el desconocido no es un defecto y el comportamiento histórico debe conservarse
    intacto. Tampoco bloquea la ausencia de metro **en las dos** ventanas: la misma ausencia no
    demuestra ningún cambio, y sigue devolviendo los ``STABLE_*`` de ``AUTO-17``.
    """
    if long_basis == SELF_EVAL_COST_BASIS_MIXED or recent_basis == SELF_EVAL_COST_BASIS_MIXED:
        return ADAPTIVE_BASIS_MIXED
    if (
        long_cost_model == SELF_EVAL_COST_MODEL_MIXED
        or recent_cost_model == SELF_EVAL_COST_MODEL_MIXED
    ):
        # Heterogeneidad INTERNA del metro: no es un cambio temporal (``COST_MODEL_TRANSITION``)
        # sino una ventana que promedia metros distintos, y el mismo estado que la base mixta.
        return ADAPTIVE_BASIS_MIXED
    if (
        long_basis == SELF_EVAL_COST_BASIS_UNDECLARED
        or recent_basis == SELF_EVAL_COST_BASIS_UNDECLARED
    ):
        # Hay neto (la base es ``undeclared``, no ``None``) pero nadie firmó el metro: se declara
        # la baja confianza con nombre propio en vez de diluirla en el ``UNKNOWN`` inocuo.
        return ADAPTIVE_BASIS_DATA_DEGRADED
    stable = {SELF_EVAL_COST_BASIS_APPLIED, SELF_EVAL_COST_BASIS_ESTIMATED}
    if long_basis in stable and recent_basis in stable:
        if long_basis != recent_basis:
            return ADAPTIVE_BASIS_TRANSITION
        model = _declared_cost_model(long_cost_model)
        recent_model = _declared_cost_model(recent_cost_model)
        if model is not None and recent_model is not None:
            if model != recent_model:
                return ADAPTIVE_BASIS_COST_MODEL_TRANSITION
        elif (model is None) != (recent_model is None):
            # Solo una ventana declara su metro: no hay comparación posible y NO se afirma
            # estabilidad. ``UNKNOWN`` no bloquea (el desconocido no es un defecto).
            return ADAPTIVE_BASIS_UNKNOWN
        return (
            ADAPTIVE_BASIS_STABLE_APPLIED
            if long_basis == SELF_EVAL_COST_BASIS_APPLIED
            else ADAPTIVE_BASIS_STABLE_ESTIMATED
        )
    return ADAPTIVE_BASIS_UNKNOWN


def _decay(
    long_r: float | None,
    recent_r: float | None,
    *,
    recent_measured_n: int,
    min_trades: int,
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN,
) -> str:
    """Deterioro reciente frente al histórico, o ``UNKNOWN`` si no se pudo comparar.

    ``UNKNOWN`` cubre los tres casos honestos: ventana reciente no disponible, expectativa de
    alguna ventana no medida, o muestra reciente por debajo del mínimo. En los tres, la
    ausencia se declara y NO se lee como "sin deterioro".

    **AUTO-17** añade un cuarto: si la base del R neto **cambió** entre las ventanas
    (``TRANSITION``) o el agregado mezcla bases (``MIXED``), comparar las expectativas mide el
    metro, no el rendimiento, así que el deterioro se declara ``UNKNOWN``. Un ``UNKNOWN`` de base
    NO bloquea: sin net con el que decidir la transición se conserva el comportamiento histórico.

    **AUTO-18** añade el quinto por el OTRO eje de la población: con la misma base pero distinta
    **versión del modelo de coste** entre las ventanas (``COST_MODEL_TRANSITION``), el cambio de
    instrumento también se declara ``UNKNOWN``. Un metro declarado en una sola ventana deja la
    transición en ``UNKNOWN``, que no bloquea.

    Con el histórico en positivo: ``recent < 0`` es ``SEVERE`` y por debajo de
    ``long * ADAPTIVE_DECAY_THRESHOLD`` es ``MILD``. Con el histórico no positivo el
    deterioro no es el eje (la rotación ya lo atiende), así que solo se distingue mejor/peor.

    ``AUTO-18`` deja el suelo de muestra sobre lo **medido** de la ventana reciente
    (``recent_measured_n``), no sobre los episodios: la pregunta del decay es "¿hay bastantes
    observaciones MEDIDAS para comparar?", y una ventana reciente es por construcción contigua
    —exigirle varias rachas apagaría el decay casi siempre—. La independencia pesa donde debe
    (la confianza y el encogimiento del peso), no en el detector de cambio.
    """
    if basis_transition in (
        ADAPTIVE_BASIS_TRANSITION,
        ADAPTIVE_BASIS_MIXED,
        ADAPTIVE_BASIS_COST_MODEL_TRANSITION,
    ):
        return ADAPTIVE_DECAY_UNKNOWN
    if long_r is None or recent_r is None:
        return ADAPTIVE_DECAY_UNKNOWN
    if recent_measured_n < max(1, min_trades):
        return ADAPTIVE_DECAY_UNKNOWN
    if long_r <= 0:
        return ADAPTIVE_DECAY_NONE if recent_r >= long_r else ADAPTIVE_DECAY_MILD
    if recent_r < 0:
        return ADAPTIVE_DECAY_SEVERE
    if recent_r < long_r * ADAPTIVE_DECAY_THRESHOLD:
        return ADAPTIVE_DECAY_MILD
    return ADAPTIVE_DECAY_NONE


# ── Contratos publicados ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RegimeConfidence:
    """Confianza de UNA celda ``strategyVersion × regime``.

    ``measurement_completeness`` combina R y R neto de la celda. El PnL **no** entra aquí: el
    embudo no tiene dimensión de régimen (``funnel_not_dimensioned_by_regime``, declarado por
    ``AUTO-9``), así que una cobertura de PnL por celda sería un número inventado. La cobertura
    de PnL sí se mide a nivel de estrategia.
    """

    regime: str
    sample_size: int
    effective_n: int
    measurement_completeness: MeasurementStatus
    risk_coverage: float
    cost_coverage: float
    long_expectancy_r: float | None
    recent_expectancy_r: float | None
    decay: str
    confidence: str
    notes: tuple[str, ...]
    #: AUTO-17 — la base del R neto de la celda (``estimated``/``applied``/``mixed``/
    #: ``undeclared``/``None``) y su desglose por base. Sin ellos, la confianza no puede decir si
    #: su expectativa se midió contra un solo modelo de coste.
    net_r_basis: str | None = None
    net_r_series: tuple[NetRBasisSeries, ...] = ()
    #: AUTO-17/18 — ``STABLE_ESTIMATED``/``STABLE_APPLIED``/``TRANSITION``/``MIXED``/
    #: ``COST_MODEL_TRANSITION``/``DATA_DEGRADED``/``UNKNOWN``. AUTO-18 añade el cambio temporal
    #: del METRO y la baja confianza declarada del neto sin base.
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN
    #: AUTO-18 — la muestra MEDIDA de la celda (ciclos con R medido), las RACHAS de régimen que
    #: esos ciclos cubren, y la muestra EFECTIVA (``min(measured_n, episodes)``) que la
    #: independencia permite afirmar. ``effective_n`` es esa última: 100 ciclos de una sola fase
    #: de mercado valen 1.
    measured_n: int = 0
    episodes: int = 0
    #: AUTO-18 — COBERTURA por independencia (``HIGH``/``MEDIUM``/``LOW``/``UNCOVERED``): eje
    #: PROPIO, distinto de ``confidence``. Una celda bien medida puede cubrir una sola fase.
    coverage: str = ADAPTIVE_COVERAGE_UNCOVERED
    #: AUTO-18 — la expectancy de la celda **encogida por muestra efectiva** (read-only). Es la
    #: lectura de lo que el reparto hará con el peso; el uso vive en ``auto_adaptive``.
    shrunk_expectancy_r: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "sampleSize": self.sample_size,
            "measuredN": self.measured_n,
            "episodes": self.episodes,
            "effectiveN": self.effective_n,
            "coverage": self.coverage,
            "shrunkExpectancyR": self.shrunk_expectancy_r,
            "measurementCompleteness": self.measurement_completeness,
            "riskCoverage": self.risk_coverage,
            "costCoverage": self.cost_coverage,
            "longExpectancyR": self.long_expectancy_r,
            "recentExpectancyR": self.recent_expectancy_r,
            "decay": self.decay,
            "confidence": self.confidence,
            "netRBasis": self.net_r_basis,
            "netRBasisSeries": [series.as_dict() for series in self.net_r_series],
            "basisTransition": self.basis_transition,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class StrategyConfidence:
    """Confianza agregada de UNA ``strategyVersion`` (con su desglose por régimen).

    Es la vista que consume el reparto (``auto_adaptive``): el peso de un edge medido se
    encoge por ``effective_n``, no por la banda — la banda es evidencia publicada.
    """

    strategy_version: str
    sample_size: int
    effective_n: int
    measurement_completeness: MeasurementStatus
    risk_coverage: float
    cost_coverage: float
    regime_coverage: float
    long_expectancy_r: float | None
    recent_expectancy_r: float | None
    decay: str
    confidence: str
    by_regime: tuple[RegimeConfidence, ...]
    notes: tuple[str, ...]
    #: AUTO-17 — la base del R neto de la estrategia y su desglose por base (``mixed`` cuando
    #: conviven, con el pooled sin publicar). La base viaja con la banda para que un neto medido
    #: contra otro modelo de coste no se lea como comparable.
    net_r_basis: str | None = None
    net_r_series: tuple[NetRBasisSeries, ...] = ()
    #: AUTO-17/18 — ``STABLE_ESTIMATED``/``STABLE_APPLIED``/``TRANSITION``/``MIXED``/
    #: ``COST_MODEL_TRANSITION``/``DATA_DEGRADED``/``UNKNOWN``: si la base —o el METRO— cambió
    #: entre la ventana larga y la reciente, el deterioro no se mide. ``DATA_DEGRADED`` (hay neto
    #: sin base declarada) rebaja la banda sin bloquear; ``UNKNOWN`` (no hay neto) no rebaja.
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN
    #: AUTO-18 — muestra MEDIDA (ciclos con R medido), RACHAS de régimen (``episodes``) que la
    #: sostienen y muestra EFECTIVA (``min(measured_n, episodes)``). Es la muestra con la que el
    #: reparto encoge el peso: 100 ciclos de una misma fase de mercado no son 100 observaciones.
    measured_n: int = 0
    episodes: int = 0
    #: AUTO-18 — COBERTURA por independencia de la estrategia (eje propio, distinto de
    #: ``confidence`` y de ``regime_coverage``).
    coverage: str = ADAPTIVE_COVERAGE_UNCOVERED
    #: AUTO-18 — la expectancy agregada **encogida por muestra efectiva** (read-only).
    shrunk_expectancy_r: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "sampleSize": self.sample_size,
            "measuredN": self.measured_n,
            "episodes": self.episodes,
            "effectiveN": self.effective_n,
            "coverage": self.coverage,
            "shrunkExpectancyR": self.shrunk_expectancy_r,
            "measurementCompleteness": self.measurement_completeness,
            "riskCoverage": self.risk_coverage,
            "costCoverage": self.cost_coverage,
            "regimeCoverage": self.regime_coverage,
            "longExpectancyR": self.long_expectancy_r,
            "recentExpectancyR": self.recent_expectancy_r,
            "decay": self.decay,
            "confidence": self.confidence,
            "netRBasis": self.net_r_basis,
            "netRBasisSeries": [series.as_dict() for series in self.net_r_series],
            "basisTransition": self.basis_transition,
            "byRegime": [cell.as_dict() for cell in self.by_regime],
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ConfidenceCalibration:
    """(AUTO-18) lectura DESCRIPTIVA de una banda de confianza sobre el periodo.

    Qué se **observó** donde la banda prometía algo: cuántas celdas la llevan, cuánta muestra
    medida (``measured_n``) y cuánta EFECTIVA (``effective_n``, tras el descuento por
    independencia) suman, qué expectativa y win rate realizados tienen, y cuánta dispersión hay
    entre ellas. La columna ``reliable`` comprueba el **suelo de muestra medida** que la banda
    declara (``_PROMISED_MIN_N``): una lectura con una banda por debajo de su suelo sería un
    fallo del constructor, no un hallazgo estadístico. El hueco entre ``measured_n`` y
    ``effective_n`` de una fila es la parte que la independencia retiró, y se publica para que
    se vea —cuantificar y juzgar es de quien audita—.

    Es read-only y **no** mueve la banda ni el reparto. Tampoco afirma nada sobre la calidad del
    edge: una banda ``HIGH`` significa "bien medido", nunca "bueno" (una estrategia medida con
    claridad y expectancy negativa es ``HIGH`` y sigue siendo mala).
    """

    level: str
    cells: int
    measured_n: int
    effective_n: int
    observed_expectancy_r: float | None
    observed_win_rate: float | None
    observed_stdev_r: float | None
    promised_min_n: int
    observed_min_n: int
    reliable: bool
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "cells": self.cells,
            "measuredN": self.measured_n,
            "effectiveN": self.effective_n,
            "observedExpectancyR": self.observed_expectancy_r,
            "observedWinRate": self.observed_win_rate,
            "observedStdevR": self.observed_stdev_r,
            "promisedMinN": self.promised_min_n,
            "observedMinN": self.observed_min_n,
            "reliable": self.reliable,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveConfidence:
    """Lectura de confianza del período: por estrategia (y sus celdas), con huecos declarados."""

    by_strategy: tuple[StrategyConfidence, ...]
    recent_window: int
    long_window: int
    recent_available: bool
    notes: tuple[str, ...]
    #: AUTO-18 — la tabla DESCRIPTIVA banda → observado (una fila por banda presente). Read-only:
    #: publica qué se midió donde la banda prometía, sin mover la banda ni el reparto.
    calibration: tuple[ConfidenceCalibration, ...] = ()

    def confidence_for(self, strategy_version: str) -> StrategyConfidence | None:
        key = str(strategy_version or "")
        for row in self.by_strategy:
            if row.strategy_version == key:
                return row
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "recentWindow": self.recent_window,
            "longWindow": self.long_window,
            "recentAvailable": self.recent_available,
            "byStrategy": {row.strategy_version: row.as_dict() for row in self.by_strategy},
            "calibration": [row.as_dict() for row in self.calibration],
            "notes": list(self.notes),
        }


# ── Agregación de una ventana ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _WindowFacts:
    """Lo que una ventana aporta de UNA estrategia: recuentos y expectativa."""

    sample_size: int
    measured_n: int
    episodes: int
    cost_n: int
    expectancy_r: float | None
    completeness: MeasurementStatus
    net_r_basis: str | None = None
    net_r_series: tuple[NetRBasisSeries, ...] = ()
    #: AUTO-18 — la versión del modelo de coste de la ventana (``cm:<preset|bps>:...``,
    #: ``undeclared`` o ``None``): el otro eje de la población comparable. Viaja con la base para
    #: que el detector de transición pueda ver si el METRO cambió entre ventanas.
    cost_model_version: str | None = None

    @property
    def effective_n(self) -> int:
        """Muestra EFECTIVA (``AUTO-18``): la independencia nunca puede AUMENTAR la muestra."""
        return min(max(0, self.measured_n), max(0, self.episodes))


def _cells_of(report: AutoSelfEvaluation, version: str) -> tuple[StrategyRegimeEvaluation, ...]:
    return tuple(cell for cell in report.by_regime if cell.strategy_version == version)


def _row_of(
    report: AutoSelfEvaluation, version: str
) -> StrategySelfEvaluation | None:
    for row in report.by_strategy:
        if row.strategy_version == version:
            return row
    return None


def _facts(
    report: AutoSelfEvaluation,
    version: str,
    *,
    runs: Mapping[str, int] | None = None,
) -> _WindowFacts:
    """Recuentos de una versión en una ventana: los cuenta el CRUCE (única casa del detalle).

    ``measured_n`` sale de ``cycles_without_risk`` de las celdas (el mismo dato que sostiene
    ``expectancy_r``) y la completitud de la fila de estrategia, que es la que mide PnL.
    ``AUTO-18`` añade ``episodes``: las rachas de régimen de esos ciclos medidos, que el llamante
    cuenta sobre la ventana ORDENADA (``_episodes``). Sin ``runs`` (una ventana que no se pudo
    ordenar) los episodios son ``0`` y la muestra efectiva colapsa: la ausencia se declara, no se
    rellena con la muestra medida. ``AUTO-18`` propaga además la **versión del modelo de coste**
    de la ventana tal cual la declara la fila (``None``/``undeclared`` incluidos): el metro de la
    población se lee, no se supone.
    """
    cells = _cells_of(report, version)
    sample_size = sum(cell.cycles for cell in cells)
    measured_n = sum(cell.cycles - cell.cycles_without_risk for cell in cells)
    episodes = min(measured_n, sum((runs or {}).values())) if measured_n > 0 else 0
    cost_n = sum(cell.cycles - cell.cycles_without_cost for cell in cells)
    row = _row_of(report, version)
    if row is None:
        completeness = measurement_from_counts(valued=0, unvalued=0)
        return _WindowFacts(sample_size, measured_n, episodes, cost_n, None, completeness)
    completeness = combine_measurements(
        row.risk_measurement,
        row.net_r_measurement,
        row.results_measurement,
    )
    return _WindowFacts(
        sample_size=sample_size,
        measured_n=measured_n,
        episodes=episodes,
        cost_n=cost_n,
        expectancy_r=row.expectancy_r,
        completeness=completeness,
        net_r_basis=row.net_r_basis,
        net_r_series=row.net_r_series,
        cost_model_version=row.cost_model_version,
    )


def _cell_notes(
    *,
    effective_n: int,
    measured_n: int,
    completeness: MeasurementStatus,
    min_trades: int,
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN,
) -> tuple[str, ...]:
    notes: list[str] = []
    if completeness != MEASUREMENT_COMPLETE:
        notes.append(ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE)
    if measured_n < max(1, min_trades):
        notes.append(ADAPTIVE_CONFIDENCE_THIN_SAMPLE)
    if effective_n < measured_n:
        # AUTO-18: el descuento por falta de independencia se declara, nunca se esconde.
        notes.append(ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT)
    if basis_transition == ADAPTIVE_BASIS_DATA_DEGRADED:
        # AUTO-18: hay neto pero su base no está declarada: se nombra el hueco (no se inventa).
        notes.append(ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED)
    return tuple(notes)


def _regime_cells(
    *,
    long_report: AutoSelfEvaluation,
    recent_report: AutoSelfEvaluation | None,
    version: str,
    min_trades: int,
    runs: Mapping[str, int] | None,
    shrink_prior: float,
) -> tuple[RegimeConfidence, ...]:
    cells: list[RegimeConfidence] = []
    for cell in _cells_of(long_report, version):
        recent = next(
            (
                candidate
                for candidate in (recent_report.by_regime if recent_report else ())
                if candidate.strategy_version == version and candidate.regime == cell.regime
            ),
            None,
        )
        sample_size = cell.cycles
        measured_n = cell.cycles - cell.cycles_without_risk
        cost_n = cell.cycles - cell.cycles_without_cost
        episodes = min(measured_n, int((runs or {}).get(cell.regime, 0))) if measured_n else 0
        recent_r = recent.expectancy_r if recent is not None else None
        recent_measured_n = (
            recent.cycles - recent.cycles_without_risk if recent is not None else 0
        )
        basis_transition = _basis_transition(
            cell.net_r_basis,
            recent.net_r_basis if recent is not None else None,
            long_cost_model=cell.cost_model_version,
            recent_cost_model=recent.cost_model_version if recent is not None else None,
        )
        decay = _decay(
            cell.expectancy_r,
            recent_r,
            recent_measured_n=recent_measured_n,
            min_trades=min_trades,
            basis_transition=basis_transition,
        )
        completeness = combine_measurements(cell.r_measurement, cell.net_r_measurement)
        effective_n = min(measured_n, episodes)
        cells.append(
            RegimeConfidence(
                regime=cell.regime,
                sample_size=sample_size,
                effective_n=effective_n,
                measurement_completeness=completeness,
                risk_coverage=_coverage(measured_n, sample_size),
                cost_coverage=_coverage(cost_n, sample_size),
                long_expectancy_r=cell.expectancy_r,
                recent_expectancy_r=recent_r,
                decay=decay,
                confidence=_band(
                    measured_n=measured_n,
                    completeness=completeness,
                    decay=decay,
                    basis_transition=basis_transition,
                ),
                notes=_cell_notes(
                    effective_n=effective_n,
                    measured_n=measured_n,
                    completeness=completeness,
                    min_trades=min_trades,
                    basis_transition=basis_transition,
                ),
                net_r_basis=cell.net_r_basis,
                net_r_series=cell.net_r_series,
                basis_transition=basis_transition,
                measured_n=measured_n,
                episodes=episodes,
                coverage=_coverage_band(measured_n, effective_n),
                shrunk_expectancy_r=_shrunk(cell.expectancy_r, effective_n, shrink_prior),
            )
        )
    return tuple(cells)


def _regime_calibration(
    report: AutoSelfEvaluation,
    by_strategy: Sequence[StrategyConfidence],
) -> tuple[ConfidenceCalibration, ...]:
    """(PURA, ``AUTO-18``) tabla DESCRIPTIVA banda → observado sobre las celdas del periodo.

    Agrupa las celdas ``strategy × regime`` por su banda y publica, por banda, cuántas celdas la
    llevan, cuánta muestra medida suman, la expectativa y el win rate realizados y su dispersión.
    ``reliable`` comprueba el suelo de muestra que la banda declara (``_PROMISED_MIN_N``): una
    banda por debajo de su propio suelo sería un fallo del constructor. NO mueve la banda ni el
    reparto, y NO afirma nada sobre la calidad del edge. Una banda sin celdas no se publica
    (sería una fila inventada).
    """
    index: dict[tuple[str, str], RegimeConfidence] = {}
    for strategy in by_strategy:
        for reading in strategy.by_regime:
            index[(strategy.strategy_version, reading.regime)] = reading
    grouped: dict[str, list[tuple[RegimeConfidence, int, int]]] = {}
    for cell in report.by_regime:
        matched = index.get((cell.strategy_version, cell.regime))
        if matched is None:
            continue
        grouped.setdefault(matched.confidence, []).append((matched, cell.wins, cell.losses))

    calibration: list[ConfidenceCalibration] = []
    for level in _CONFIDENCE_ORDER:
        entries = grouped.get(level)
        if not entries:
            continue
        values = [
            reading.long_expectancy_r
            for reading, _wins, _losses in entries
            if reading.long_expectancy_r is not None
        ]
        wins = sum(wins for _reading, wins, _losses in entries)
        losses = sum(losses for _reading, _wins, losses in entries)
        measured_n = sum(reading.measured_n for reading, _wins, _losses in entries)
        effective_n = sum(reading.effective_n for reading, _wins, _losses in entries)
        promised = _PROMISED_MIN_N[level]
        observed_min = min(
            (reading.measured_n for reading, _wins, _losses in entries), default=0
        )
        notes: list[str] = []
        if not values:
            notes.append(ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE)
        calibration.append(
            ConfidenceCalibration(
                level=level,
                cells=len(entries),
                measured_n=measured_n,
                effective_n=effective_n,
                observed_expectancy_r=(
                    _round4(sum(values) / len(values)) if values else None
                ),
                observed_win_rate=(
                    _round4(wins / (wins + losses)) if (wins + losses) > 0 else None
                ),
                observed_stdev_r=(_round4(pstdev(values)) if len(values) > 1 else None),
                promised_min_n=promised,
                observed_min_n=observed_min,
                reliable=bool(entries) and observed_min >= promised,
                notes=tuple(notes),
            )
        )
    return tuple(calibration)


def _strategy_confidence(
    *,
    long_report: AutoSelfEvaluation,
    recent_report: AutoSelfEvaluation | None,
    row: StrategySelfEvaluation,
    recent_available: bool,
    min_trades: int,
    runs: Mapping[str, int] | None,
    recent_runs: Mapping[str, int] | None,
    shrink_prior: float,
) -> StrategyConfidence:
    version = row.strategy_version
    long_facts = _facts(long_report, version, runs=runs)
    recent_facts = (
        _facts(recent_report, version, runs=recent_runs)
        if recent_report is not None
        else None
    )
    cells = _regime_cells(
        long_report=long_report,
        recent_report=recent_report,
        version=version,
        min_trades=min_trades,
        runs=runs,
        shrink_prior=shrink_prior,
    )
    sample_size = long_facts.sample_size or row.trades
    measured_n = long_facts.measured_n
    effective_n = long_facts.effective_n
    known_regime = sum(
        cell.cycles
        for cell in _cells_of(long_report, version)
        if cell.regime != SELF_EVAL_REGIME_UNKNOWN
    )
    recent_r = recent_facts.expectancy_r if recent_facts is not None else None
    recent_measured_n = recent_facts.measured_n if recent_facts is not None else 0
    basis_transition = _basis_transition(
        long_facts.net_r_basis,
        recent_facts.net_r_basis if recent_facts is not None else None,
        long_cost_model=long_facts.cost_model_version,
        recent_cost_model=recent_facts.cost_model_version if recent_facts is not None else None,
    )
    decay = _decay(
        long_facts.expectancy_r,
        recent_r,
        recent_measured_n=recent_measured_n,
        min_trades=min_trades,
        basis_transition=basis_transition,
    )
    completeness = long_facts.completeness

    notes: list[str] = []
    if completeness != MEASUREMENT_COMPLETE:
        notes.append(ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE)
    if measured_n < max(1, min_trades):
        notes.append(ADAPTIVE_CONFIDENCE_THIN_SAMPLE)
    if effective_n < measured_n:
        notes.append(ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT)
    if basis_transition == ADAPTIVE_BASIS_DATA_DEGRADED:
        # AUTO-18: hay neto sin base declarada: baja confianza declarada, nunca silenciada.
        notes.append(ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED)
    if not recent_available:
        notes.append(ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE)
    elif recent_facts is None or recent_measured_n < max(1, min_trades):
        # La ventana existe pero no alcanza muestra interpretable: se declara el suelo.
        notes.append(ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT)

    return StrategyConfidence(
        strategy_version=version,
        sample_size=sample_size,
        effective_n=effective_n,
        measurement_completeness=completeness,
        risk_coverage=_coverage(measured_n, sample_size),
        cost_coverage=_coverage(long_facts.cost_n, sample_size),
        regime_coverage=_coverage(known_regime, sample_size),
        long_expectancy_r=long_facts.expectancy_r,
        recent_expectancy_r=recent_r,
        decay=decay,
        confidence=_band(
            measured_n=measured_n,
            completeness=completeness,
            decay=decay,
            basis_transition=basis_transition,
        ),
        by_regime=cells,
        notes=tuple(dict.fromkeys(notes)),
        net_r_basis=long_facts.net_r_basis,
        net_r_series=long_facts.net_r_series,
        basis_transition=basis_transition,
        measured_n=measured_n,
        episodes=long_facts.episodes,
        coverage=_coverage_band(measured_n, effective_n),
        shrunk_expectancy_r=_shrunk(long_facts.expectancy_r, effective_n, shrink_prior),
    )


def build_adaptive_confidence(
    cycles: Iterable[Any] | None = None,
    *,
    recent_window: int = ADAPTIVE_RECENT_WINDOW_DEFAULT,
    long_window: int = ADAPTIVE_LONG_WINDOW_DEFAULT,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
    shrink_prior: float = ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT,
) -> AdaptiveConfidence:
    """(PURA) confianza estadística de Adaptive sobre los ciclos del período.

    ``cycles`` son las filas de ciclo del MISMO productor que alimenta el informe de
    ``AUTO-7``/``AUTO-9`` (``cycles_from_fills`` + ``cycle_risk``): cada una declara su
    ``closedAt`` cuando se pudo medir. Las ventanas se recortan de los ciclos **ordenados por
    instante**: la LARGA es el histórico contra el que se compara y la RECIENTE el presente.

    Sin ningún ``closedAt`` legible no hay ventana reciente honesta: se declara
    ``recent_unavailable``, ``recent_expectancy_r`` queda ``None`` y ``decay`` es ``UNKNOWN``.
    Sin ciclos se devuelve una lectura VACÍA declarada (``no_cycles``), nunca ``[]`` mudo.

    ``shrink_prior`` (``AUTO-18``) es el prior del encogimiento que la lectura publica en
    ``shrunk_expectancy_r``: la MISMA constante que sella ``AdaptivePolicy.confidence_prior``
    (un solo número declarado). El USO del encogimiento vive en ``auto_adaptive``.
    """
    rows = list(cycles or ())
    resolved_recent = max(1, int(recent_window))
    resolved_long = max(1, int(long_window))
    if not rows:
        return AdaptiveConfidence(
            by_strategy=(),
            recent_window=resolved_recent,
            long_window=resolved_long,
            recent_available=False,
            notes=(ADAPTIVE_CONFIDENCE_NO_CYCLES,),
        )

    ordered, undated = _order_by_instant(rows)
    notes: list[str] = []
    if undated >= len(ordered):
        # Ninguna fila declara instante: no se inventa cronología.
        long_rows = ordered
        recent_rows: list[Any] = []
        recent_report: AutoSelfEvaluation | None = None
        recent_available = False
        notes.append(ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE)
    else:
        long_rows = ordered[-resolved_long:]
        recent_rows = ordered[-resolved_recent:]
        recent_report = evaluate_auto_self_evaluation(cycles=recent_rows, min_trades=min_trades)
        recent_available = True
        if undated:
            # Hay filas sin instante: van al final y la ventana reciente puede contenerlas.
            notes.append(ADAPTIVE_CONFIDENCE_RECENT_UNDATED)

    # AUTO-18: las rachas de régimen se cuentan sobre las MISMAS ventanas ordenadas que el
    # informe (la independencia se mide donde se mide la muestra, sin un segundo orden).
    long_runs = _episodes(long_rows)
    recent_runs = _episodes(recent_rows) if recent_available else {}
    long_report = evaluate_auto_self_evaluation(cycles=long_rows, min_trades=min_trades)
    by_strategy = tuple(
        _strategy_confidence(
            long_report=long_report,
            recent_report=recent_report,
            row=row,
            recent_available=recent_available,
            min_trades=min_trades,
            runs=long_runs.get(row.strategy_version),
            recent_runs=recent_runs.get(row.strategy_version),
            shrink_prior=shrink_prior,
        )
        for row in long_report.by_strategy
    )
    return AdaptiveConfidence(
        by_strategy=by_strategy,
        recent_window=resolved_recent,
        long_window=resolved_long,
        recent_available=recent_available,
        notes=tuple(dict.fromkeys(notes)),
        calibration=_regime_calibration(long_report, by_strategy),
    )
