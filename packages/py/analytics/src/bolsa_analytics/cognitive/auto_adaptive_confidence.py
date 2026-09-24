"""AUTO-12 — Confidence y calidad estadística del Adaptive AUTO (PURA y READ-ONLY).

Cierra la deuda que declaró la propia ``V2.52``: Adaptive ya recuerda su estado (journal
durable), pero todavía no sabía **cuánto creer** a lo que estaba aprendiendo. Hasta aquí el
único gate de muestra era **binario** (``decisive``, ``trades >= min_trades``): dentro de él,
una celda de ``N = 12`` pesaba exactamente igual que una de ``N = 180``.

Qué publica, por ``strategyVersion`` (y por celda ``strategy × regime``):

* **``sample_size`` / ``effective_n``** — la muestra bruta y, sobre todo, la muestra que de
  verdad **sostiene** el número: los ciclos con R medido (el denominador real de
  ``expectancy_r``). Una celda de 40 ciclos con 3 R medidos no es una muestra de 40.
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
  con techo explícito cuando la lectura no se pudo completar.

Disciplina de medición (la del repo, y aquí es el punto entero del módulo):

* **Lo que no se midió se declara.** Sin fechas legibles no hay ventana reciente: se publica
  ``recent_unavailable`` y ``decay = UNKNOWN`` — jamás se ordena por posición de lista
  fingiendo cronología (la lección que ``cycle_risk`` cerró en ``V2.52``).
* **Ausencia de dato ≠ dato malo.** Una muestra fina NO se castiga a ciegas: se declara
  ``LOW``. El encogimiento del reparto por tamaño de muestra vive en ``auto_adaptive`` (la
  política), no aquí.
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
from typing import Any

from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_COST_BASIS_APPLIED,
    SELF_EVAL_COST_BASIS_ESTIMATED,
    SELF_EVAL_COST_BASIS_MIXED,
    SELF_EVAL_MIN_TRADES_DEFAULT,
    SELF_EVAL_REGIME_UNKNOWN,
    AutoSelfEvaluation,
    NetRBasisSeries,
    StrategyRegimeEvaluation,
    StrategySelfEvaluation,
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
    "ADAPTIVE_CONFIDENCE_HIGH",
    "ADAPTIVE_CONFIDENCE_LOW",
    "ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE",
    "ADAPTIVE_CONFIDENCE_MEDIUM",
    "ADAPTIVE_CONFIDENCE_NO_CYCLES",
    "ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT",
    "ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE",
    "ADAPTIVE_CONFIDENCE_RECENT_UNDATED",
    "ADAPTIVE_CONFIDENCE_THIN_SAMPLE",
    "ADAPTIVE_BASIS_MIXED",
    "ADAPTIVE_BASIS_STABLE_APPLIED",
    "ADAPTIVE_BASIS_STABLE_ESTIMATED",
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

# ── AUTO-17 — la TRANSICIÓN de base del R neto (``estimated`` ↔ ``applied``) ─────────
#
# La base del R neto es una dimensión estadística: si la ventana LARGA y la RECIENTE no se
# midieron contra el mismo modelo de coste, comparar sus expectativas no mide deterioro ni
# mejora —mide el cambio de metro—. Estos estados lo declaran, y solo ``TRANSITION``/``MIXED``
# bloquean la comparación (un ``UNKNOWN`` significa "no hay net con el que decidirlo": se deja el
# comportamiento histórico intacto, porque el desconocido no es un defecto).
#: La ventana larga mide contra el coste que el decisor SUPUSO.
ADAPTIVE_BASIS_STABLE_ESTIMATED = "STABLE_ESTIMATED"
#: La ventana larga mide contra la fricción que el simulador APLICÓ.
ADAPTIVE_BASIS_STABLE_APPLIED = "STABLE_APPLIED"
#: La base cambió entre ventanas: la comparación NO es deterioro ni mejora.
ADAPTIVE_BASIS_TRANSITION = "TRANSITION"
#: El agregado mezcla bases (no hay un único modelo que comparar).
ADAPTIVE_BASIS_MIXED = "MIXED"
#: No hay base declarada con la que decidir la transición (net ausente o sin declarar).
ADAPTIVE_BASIS_UNKNOWN = "UNKNOWN"

# ── Huecos declarados (vocabulario propio: nunca se rellenan, se nombran) ───────────
ADAPTIVE_CONFIDENCE_NO_CYCLES = "no_cycles"
ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE = "recent_unavailable"
ADAPTIVE_CONFIDENCE_RECENT_UNDATED = "recent_undated"
ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT = "recent_insufficient"
ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE = "measurement_incomplete"
ADAPTIVE_CONFIDENCE_THIN_SAMPLE = "thin_sample"

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


def _lower(level: str, *, steps: int = 1) -> str:
    """Baja una banda (o dos); el suelo es ``LOW``."""
    index = max(0, _CONFIDENCE_ORDER.index(level) - max(0, steps))
    return _CONFIDENCE_ORDER[index]


def _ceiling(level: str, cap: str) -> str:
    """Pone techo a una banda: no se premia por encima de ``cap``."""
    return _CONFIDENCE_ORDER[min(_CONFIDENCE_ORDER.index(level), _CONFIDENCE_ORDER.index(cap))]


def _band(
    *,
    effective_n: int,
    completeness: MeasurementStatus,
    decay: str,
) -> str:
    """Banda de confianza declarada a partir de la muestra, la medición y el deterioro.

    Orden de aplicación (el techo SIEMPRE al final: no se premia lo que no se pudo leer):

    1. Base por ``sample_quality_from_n(effective_n)`` — la convención del repo.
    2. Medición incompleta baja un nivel (``PARTIAL``) o dos (``UNKNOWN``).
    3. ``decay == SEVERE`` baja un nivel.
    4. ``decay == UNKNOWN`` pone techo ``MEDIUM``.
    """
    level = _QUALITY_BAND[sample_quality_from_n(effective_n)]
    if completeness == MEASUREMENT_PARTIAL:
        level = _lower(level, steps=1)
    elif completeness != MEASUREMENT_COMPLETE:
        level = _lower(level, steps=2)
    if decay == ADAPTIVE_DECAY_SEVERE:
        level = _lower(level, steps=1)
    if decay == ADAPTIVE_DECAY_UNKNOWN:
        level = _ceiling(level, ADAPTIVE_CONFIDENCE_MEDIUM)
    return level


def _basis_transition(long_basis: str | None, recent_basis: str | None) -> str:
    """(PURA, AUTO-17) ¿comparten base la ventana LARGA y la RECIENTE?

    La regla dura de la fase: si la base del R neto cambió entre las dos ventanas, comparar sus
    expectativas mide **el métro**, no el rendimiento. Solo ``TRANSITION`` y ``MIXED`` marcan la
    lectura como no comparable; ``UNKNOWN`` (sin net o sin base declarada) NO bloquea nada, porque
    el desconocido no es un defecto y el comportamiento histórico debe conservarse intacto.
    """
    if long_basis == SELF_EVAL_COST_BASIS_MIXED or recent_basis == SELF_EVAL_COST_BASIS_MIXED:
        return ADAPTIVE_BASIS_MIXED
    stable = {SELF_EVAL_COST_BASIS_APPLIED, SELF_EVAL_COST_BASIS_ESTIMATED}
    if long_basis in stable and recent_basis in stable:
        if long_basis != recent_basis:
            return ADAPTIVE_BASIS_TRANSITION
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
    recent_effective_n: int,
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

    Con el histórico en positivo: ``recent < 0`` es ``SEVERE`` y por debajo de
    ``long * ADAPTIVE_DECAY_THRESHOLD`` es ``MILD``. Con el histórico no positivo el
    deterioro no es el eje (la rotación ya lo atiende), así que solo se distingue mejor/peor.
    """
    if basis_transition in (ADAPTIVE_BASIS_TRANSITION, ADAPTIVE_BASIS_MIXED):
        return ADAPTIVE_DECAY_UNKNOWN
    if long_r is None or recent_r is None:
        return ADAPTIVE_DECAY_UNKNOWN
    if recent_effective_n < max(1, min_trades):
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
    #: AUTO-17 — ``STABLE_ESTIMATED``/``STABLE_APPLIED``/``TRANSITION``/``MIXED``/``UNKNOWN``.
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "sampleSize": self.sample_size,
            "effectiveN": self.effective_n,
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
    #: AUTO-17 — ``STABLE_ESTIMATED``/``STABLE_APPLIED``/``TRANSITION``/``MIXED``/``UNKNOWN``: si
    #: la base cambió entre la ventana larga y la reciente, el deterioro no se mide (``UNKNOWN``).
    basis_transition: str = ADAPTIVE_BASIS_UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "sampleSize": self.sample_size,
            "effectiveN": self.effective_n,
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
class AdaptiveConfidence:
    """Lectura de confianza del período: por estrategia (y sus celdas), con huecos declarados."""

    by_strategy: tuple[StrategyConfidence, ...]
    recent_window: int
    long_window: int
    recent_available: bool
    notes: tuple[str, ...]

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
            "notes": list(self.notes),
        }


# ── Agregación de una ventana ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _WindowFacts:
    """Lo que una ventana aporta de UNA estrategia: recuentos y expectativa."""

    sample_size: int
    effective_n: int
    cost_n: int
    expectancy_r: float | None
    completeness: MeasurementStatus
    net_r_basis: str | None = None
    net_r_series: tuple[NetRBasisSeries, ...] = ()


def _cells_of(report: AutoSelfEvaluation, version: str) -> tuple[StrategyRegimeEvaluation, ...]:
    return tuple(cell for cell in report.by_regime if cell.strategy_version == version)


def _row_of(
    report: AutoSelfEvaluation, version: str
) -> StrategySelfEvaluation | None:
    for row in report.by_strategy:
        if row.strategy_version == version:
            return row
    return None


def _facts(report: AutoSelfEvaluation, version: str) -> _WindowFacts:
    """Recuentos de una versión en una ventana: los cuenta el CRUCE (única casa del detalle).

    ``effective_n`` sale de ``cycles_without_risk`` de las celdas (el mismo dato que sostiene
    ``expectancy_r``) y la completitud de la fila de estrategia, que es la que mide PnL.
    """
    cells = _cells_of(report, version)
    sample_size = sum(cell.cycles for cell in cells)
    effective_n = sum(cell.cycles - cell.cycles_without_risk for cell in cells)
    cost_n = sum(cell.cycles - cell.cycles_without_cost for cell in cells)
    row = _row_of(report, version)
    if row is None:
        completeness = measurement_from_counts(valued=0, unvalued=0)
        return _WindowFacts(sample_size, effective_n, cost_n, None, completeness)
    completeness = combine_measurements(
        row.risk_measurement,
        row.net_r_measurement,
        row.results_measurement,
    )
    return _WindowFacts(
        sample_size=sample_size,
        effective_n=effective_n,
        cost_n=cost_n,
        expectancy_r=row.expectancy_r,
        completeness=completeness,
        net_r_basis=row.net_r_basis,
        net_r_series=row.net_r_series,
    )


def _cell_notes(
    *,
    effective_n: int,
    completeness: MeasurementStatus,
    min_trades: int,
) -> tuple[str, ...]:
    notes: list[str] = []
    if completeness != MEASUREMENT_COMPLETE:
        notes.append(ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE)
    if effective_n < max(1, min_trades):
        notes.append(ADAPTIVE_CONFIDENCE_THIN_SAMPLE)
    return tuple(notes)


def _regime_cells(
    *,
    long_report: AutoSelfEvaluation,
    recent_report: AutoSelfEvaluation | None,
    version: str,
    min_trades: int,
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
        effective_n = cell.cycles - cell.cycles_without_risk
        cost_n = cell.cycles - cell.cycles_without_cost
        recent_r = recent.expectancy_r if recent is not None else None
        recent_effective_n = (
            recent.cycles - recent.cycles_without_risk if recent is not None else 0
        )
        basis_transition = _basis_transition(
            cell.net_r_basis, recent.net_r_basis if recent is not None else None
        )
        decay = _decay(
            cell.expectancy_r,
            recent_r,
            recent_effective_n=recent_effective_n,
            min_trades=min_trades,
            basis_transition=basis_transition,
        )
        completeness = combine_measurements(cell.r_measurement, cell.net_r_measurement)
        cells.append(
            RegimeConfidence(
                regime=cell.regime,
                sample_size=sample_size,
                effective_n=effective_n,
                measurement_completeness=completeness,
                risk_coverage=_coverage(effective_n, sample_size),
                cost_coverage=_coverage(cost_n, sample_size),
                long_expectancy_r=cell.expectancy_r,
                recent_expectancy_r=recent_r,
                decay=decay,
                confidence=_band(
                    effective_n=effective_n,
                    completeness=completeness,
                    decay=decay,
                ),
                notes=_cell_notes(
                    effective_n=effective_n,
                    completeness=completeness,
                    min_trades=min_trades,
                ),
                net_r_basis=cell.net_r_basis,
                net_r_series=cell.net_r_series,
                basis_transition=basis_transition,
            )
        )
    return tuple(cells)


def _strategy_confidence(
    *,
    long_report: AutoSelfEvaluation,
    recent_report: AutoSelfEvaluation | None,
    row: StrategySelfEvaluation,
    recent_available: bool,
    min_trades: int,
) -> StrategyConfidence:
    version = row.strategy_version
    long_facts = _facts(long_report, version)
    recent_facts = _facts(recent_report, version) if recent_report is not None else None
    cells = _regime_cells(
        long_report=long_report,
        recent_report=recent_report,
        version=version,
        min_trades=min_trades,
    )
    sample_size = long_facts.sample_size or row.trades
    effective_n = long_facts.effective_n
    known_regime = sum(
        cell.cycles
        for cell in _cells_of(long_report, version)
        if cell.regime != SELF_EVAL_REGIME_UNKNOWN
    )
    recent_r = recent_facts.expectancy_r if recent_facts is not None else None
    recent_effective_n = recent_facts.effective_n if recent_facts is not None else 0
    basis_transition = _basis_transition(
        long_facts.net_r_basis, recent_facts.net_r_basis if recent_facts is not None else None
    )
    decay = _decay(
        long_facts.expectancy_r,
        recent_r,
        recent_effective_n=recent_effective_n,
        min_trades=min_trades,
        basis_transition=basis_transition,
    )
    completeness = long_facts.completeness

    notes: list[str] = []
    if completeness != MEASUREMENT_COMPLETE:
        notes.append(ADAPTIVE_CONFIDENCE_MEASUREMENT_INCOMPLETE)
    if effective_n < max(1, min_trades):
        notes.append(ADAPTIVE_CONFIDENCE_THIN_SAMPLE)
    if not recent_available:
        notes.append(ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE)
    elif recent_facts is None or recent_effective_n < max(1, min_trades):
        # La ventana existe pero no alcanza muestra interpretable: se declara el suelo.
        notes.append(ADAPTIVE_CONFIDENCE_RECENT_INSUFFICIENT)

    return StrategyConfidence(
        strategy_version=version,
        sample_size=sample_size,
        effective_n=effective_n,
        measurement_completeness=completeness,
        risk_coverage=_coverage(effective_n, sample_size),
        cost_coverage=_coverage(long_facts.cost_n, sample_size),
        regime_coverage=_coverage(known_regime, sample_size),
        long_expectancy_r=long_facts.expectancy_r,
        recent_expectancy_r=recent_r,
        decay=decay,
        confidence=_band(
            effective_n=effective_n,
            completeness=completeness,
            decay=decay,
        ),
        by_regime=cells,
        notes=tuple(dict.fromkeys(notes)),
        net_r_basis=long_facts.net_r_basis,
        net_r_series=long_facts.net_r_series,
        basis_transition=basis_transition,
    )


def build_adaptive_confidence(
    cycles: Iterable[Any] | None = None,
    *,
    recent_window: int = ADAPTIVE_RECENT_WINDOW_DEFAULT,
    long_window: int = ADAPTIVE_LONG_WINDOW_DEFAULT,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
) -> AdaptiveConfidence:
    """(PURA) confianza estadística de Adaptive sobre los ciclos del período.

    ``cycles`` son las filas de ciclo del MISMO productor que alimenta el informe de
    ``AUTO-7``/``AUTO-9`` (``cycles_from_fills`` + ``cycle_risk``): cada una declara su
    ``closedAt`` cuando se pudo medir. Las ventanas se recortan de los ciclos **ordenados por
    instante**: la LARGA es el histórico contra el que se compara y la RECIENTE el presente.

    Sin ningún ``closedAt`` legible no hay ventana reciente honesta: se declara
    ``recent_unavailable``, ``recent_expectancy_r`` queda ``None`` y ``decay`` es ``UNKNOWN``.
    Sin ciclos se devuelve una lectura VACÍA declarada (``no_cycles``), nunca ``[]`` mudo.
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
        recent_report: AutoSelfEvaluation | None = None
        recent_available = False
        notes.append(ADAPTIVE_CONFIDENCE_RECENT_UNAVAILABLE)
    else:
        long_rows = ordered[-resolved_long:]
        recent_report = evaluate_auto_self_evaluation(
            cycles=ordered[-resolved_recent:], min_trades=min_trades
        )
        recent_available = True
        if undated:
            # Hay filas sin instante: van al final y la ventana reciente puede contenerlas.
            notes.append(ADAPTIVE_CONFIDENCE_RECENT_UNDATED)

    long_report = evaluate_auto_self_evaluation(cycles=long_rows, min_trades=min_trades)
    by_strategy = tuple(
        _strategy_confidence(
            long_report=long_report,
            recent_report=recent_report,
            row=row,
            recent_available=recent_available,
            min_trades=min_trades,
        )
        for row in long_report.by_strategy
    )
    return AdaptiveConfidence(
        by_strategy=by_strategy,
        recent_window=resolved_recent,
        long_window=resolved_long,
        recent_available=recent_available,
        notes=tuple(dict.fromkeys(notes)),
    )
