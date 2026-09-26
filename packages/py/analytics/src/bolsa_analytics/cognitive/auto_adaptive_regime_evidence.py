"""AUTO-21 — EVIDENCIA del RÉGIMEN ACTUAL por estrategia (PURA y READ-ONLY).

Qué pregunta: el régimen de mercado que manda AHORA, ¿tiene evidencia propia en el material, o solo
una lectura agregada que lo esconde? ``AUTO-19A`` ya publicaba un intervalo por celda
``strategy × regime``; ``AUTO-18`` ya declaraba qué regímenes son adversos para rotar. Lo que faltaba
era juntar ambas cosas en una lectura que el humano pueda ver de un vistazo: **para el régimen actual,
qué mide cada estrategia** (o el hueco, declarado).

Cómo lo mide, sin inventar evidencia:

* **El régimen actual se declara.** Si el llamante lo aporta, se usa; si no, se toma el del ciclo MÁS
  RECIENTE con régimen declarable; si no hay, ``None`` y el hueco se nombra (``no_current_regime``).
* **Se reutiliza el productor único de incertidumbre.** El intervalo, la ``P(R > 0)`` (por CICLOS) y
  la ``P(edge>0)`` de cada celda salen de ``build_adaptive_uncertainty`` (mismo bootstrap por
  episodios): no hay una segunda aritmética de la celda que pudiera divergir del informe.
* **Una estrategia sin celda para ese régimen se declara** (``no_evidence_for_regime``): no se le
  atribuye la lectura agregada ni la de otro régimen.
* **El carácter adverso es el declarado** por ``ADAPTIVE_ADVERSE_REGIMES`` (la misma fuente que la
  rotación); aquí solo se publica, no se decide nada.

Read-only por contrato: no toca el reparto, la rotación, el plan, el journal ni el gobernador.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive import ADAPTIVE_ADVERSE_REGIMES
from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    measured_r,
    order_cycles_by_instant,
    regime_of,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_EDGE_UNKNOWN,
    ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    ADAPTIVE_INTERVAL_SEED_DEFAULT,
    build_adaptive_uncertainty,
)

__all__ = [
    "CURRENT_REGIME_EVIDENCE_METHOD",
    "REGIME_EVIDENCE_NOTE_NO_CURRENT_REGIME",
    "REGIME_EVIDENCE_NOTE_NO_CYCLES",
    "REGIME_EVIDENCE_NOTE_NO_EVIDENCE_FOR_REGIME",
    "REGIME_EVIDENCE_NOTE_UNDATED_CYCLES",
    "CurrentRegimeEvidence",
    "RegimeStrategyEvidence",
    "build_current_regime_evidence",
    "current_regime_from_cycles",
]

#: Método declarado de la lectura. No es un bootstrap propio: reutiliza el de ``AUTO-19A``, pero la
#: SELECCIÓN del régimen actual es una lectura nueva y por eso viaja con su propio sello.
#:
#: La corrección de ``v2.71`` sube el sello a ``v2``: ``probability_positive`` pasa a ser la
#: ``P(R>0)`` por CICLOS (``cycle_positive_share``), no la ``P(edge>0)`` del bootstrap; y se publica
#: además ``edgePositiveProbability`` de forma aditiva.
CURRENT_REGIME_EVIDENCE_METHOD = "current_regime_evidence_v2"

REGIME_EVIDENCE_NOTE_NO_CYCLES = "no_cycles"
REGIME_EVIDENCE_NOTE_NO_CURRENT_REGIME = "no_current_regime"
REGIME_EVIDENCE_NOTE_NO_EVIDENCE_FOR_REGIME = "no_evidence_for_regime"
REGIME_EVIDENCE_NOTE_UNDATED_CYCLES = "undated_cycles"


def _regime_key(value: Any) -> str:
    return str(value or "").strip().upper()


def current_regime_from_cycles(cycles: Iterable[Any] | None = None) -> str | None:
    """(PURA) régimen del ciclo MÁS RECIENTE con régimen declarable, o ``None``.

    ``UNKNOWN`` no es un régimen: un ciclo que no declara régimen no puede fijar el "actual", así que
    se sigue mirando hacia atrás. Sin ningún ciclo con régimen, el hueco es ``None`` (no se supone).
    """
    rows = list(cycles or ())
    if not rows:
        return None
    ordered, _undated = order_cycles_by_instant(rows)
    for row in reversed(ordered):
        if measured_r(row) is None:
            continue
        regime = regime_of(row)
        if _regime_key(regime) and _regime_key(regime) != "UNKNOWN":
            return regime
    return None


@dataclass(frozen=True, slots=True)
class RegimeStrategyEvidence:
    """La evidencia de UNA estrategia para el régimen actual (o su hueco declarado)."""

    strategy_version: str
    regime: str
    measured_n: int
    episodes: int
    expectancy_r: float | None
    probability_positive: float | None
    edge_confidence: str
    #: ``v2.71`` — ``P(edge>0)`` del bootstrap (fracción de medias > 0). Aditivo: ``probability_positive``
    #: es la ``P(R>0)`` por CICLOS; esta es la probabilidad del EDGE. ``None`` sin bootstrap.
    edge_positive_probability: float | None = None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "regime": self.regime,
            "measuredN": self.measured_n,
            "episodes": self.episodes,
            "expectancyR": self.expectancy_r,
            "probabilityPositive": self.probability_positive,
            "edgePositiveProbability": self.edge_positive_probability,
            "edgeConfidence": self.edge_confidence,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class CurrentRegimeEvidence:
    """La lectura del régimen actual: por estrategia, con su intervalo y su ``P(R > 0)``."""

    regime: str | None
    adverse: bool | None
    by_strategy: tuple[RegimeStrategyEvidence, ...]
    method: str = CURRENT_REGIME_EVIDENCE_METHOD
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT
    notes: tuple[str, ...] = ()

    def evidence_for(self, strategy_version: str) -> RegimeStrategyEvidence | None:
        key = str(strategy_version or "")
        for row in self.by_strategy:
            if row.strategy_version == key:
                return row
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "regime": self.regime,
            "adverse": self.adverse,
            "level": self.level,
            "resamples": self.resamples,
            "seed": self.seed,
            "byStrategy": {
                row.strategy_version: row.as_dict() for row in self.by_strategy
            },
            "notes": list(self.notes),
        }


def build_current_regime_evidence(
    cycles: Iterable[Any] | None = None,
    *,
    current_regime: str | None = None,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    min_episodes: int = ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
) -> CurrentRegimeEvidence:
    """(PURA) la evidencia del régimen actual, por estrategia, reutilizando el bootstrap de ``AUTO-19A``.

    Sin ciclos devuelve una lectura VACÍA declarada. ``current_regime`` es OPCIONAL: sin él se toma el
    del ciclo más reciente con régimen declarable y, si no hay, el hueco queda ``no_current_regime``.
    Cada estrategia publica la celda de ese régimen o ``no_evidence_for_regime`` —nunca la lectura
    agregada disfrazada de régimen—.
    """
    rows = list(cycles or ())
    resolved_level = level
    resolved_resamples = max(1, int(resamples))
    resolved_min = max(1, int(min_episodes))
    provided = _regime_key(current_regime)
    if not rows:
        return CurrentRegimeEvidence(
            regime=provided or None,
            adverse=(provided in ADAPTIVE_ADVERSE_REGIMES) if provided else None,
            by_strategy=(),
            level=resolved_level,
            resamples=resolved_resamples,
            seed=int(seed),
            notes=(REGIME_EVIDENCE_NOTE_NO_CYCLES,),
        )

    ordered, undated = order_cycles_by_instant(rows)
    resolved_regime = current_regime if provided else current_regime_from_cycles(ordered)
    key = _regime_key(resolved_regime)
    uncertainty = build_adaptive_uncertainty(
        ordered,
        level=resolved_level,
        resamples=resolved_resamples,
        seed=int(seed),
        min_episodes=resolved_min,
    )

    by_strategy: list[RegimeStrategyEvidence] = []
    for strategy in uncertainty.by_strategy:
        cell = next(
            (
                candidate
                for candidate in strategy.by_regime
                if _regime_key(candidate.regime) == key
            ),
            None,
        )
        if cell is None:
            by_strategy.append(
                RegimeStrategyEvidence(
                    strategy_version=strategy.strategy_version,
                    regime=resolved_regime or "",
                    measured_n=0,
                    episodes=0,
                    expectancy_r=None,
                    probability_positive=None,
                    edge_confidence=ADAPTIVE_EDGE_UNKNOWN,
                    notes=(REGIME_EVIDENCE_NOTE_NO_EVIDENCE_FOR_REGIME,),
                )
            )
            continue
        by_strategy.append(
            RegimeStrategyEvidence(
                strategy_version=strategy.strategy_version,
                regime=cell.regime,
                measured_n=cell.interval.measured_n,
                episodes=cell.interval.episodes,
                expectancy_r=cell.interval.point,
                probability_positive=cell.interval.cycle_positive_share,
                edge_confidence=cell.edge_confidence,
                edge_positive_probability=cell.interval.edge_positive_probability,
                notes=tuple(cell.notes),
            )
        )

    notes: list[str] = []
    if undated:
        notes.append(REGIME_EVIDENCE_NOTE_UNDATED_CYCLES)
    if not key:
        notes.append(REGIME_EVIDENCE_NOTE_NO_CURRENT_REGIME)
    return CurrentRegimeEvidence(
        regime=resolved_regime,
        adverse=(key in ADAPTIVE_ADVERSE_REGIMES) if key else None,
        by_strategy=tuple(by_strategy),
        level=resolved_level,
        resamples=resolved_resamples,
        seed=int(seed),
        notes=tuple(notes),
    )
