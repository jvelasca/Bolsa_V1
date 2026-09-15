"""OpportunityRanker — ranking explicable de oportunidades (AUTO 2.0 · P0).

AUTO no debe operar solo porque UNA estrategia genera UNA señal: debe comparar TODAS
las oportunidades disponibles y elegir un subconjunto operativo. Este módulo aporta el
score **explicable** (cada componente visible y auditable) y la selección del TOP N.

Pesos (V1, calibrables — NO son definitivos, son el primer esqueleto de decisión):

* ``edge``                30%  — ventaja esperada (EV / expectancy operacional).
* ``robustness``          20%  — robustez de la hipótesis (WFE/DSR/credibilidad).
* ``regime_fit``          15%  — encaje con el régimen de mercado vigente.
* ``momentum``            10%  — momentum/tendencia a favor.
* ``liquidity``           10%  — liquidez/tradability del instrumento.
* ``risk_reward``         10%  — relación riesgo/recompensa.
* ``execution_quality``    5%  — calidad de ejecución prevista (spread, tamaño).

Fail-closed: un componente ausente o no finito vale **0** (nunca se inventa evidencia).
Cada componente se normaliza a [0, 1]. El score combinado es la suma ponderada y el
ranking es estrictamente descendente por ``combined`` (empates: orden estable por
``instrument_id`` para reproducibilidad).

No es un gate: solo ORDENA. La decisión de operar (y el veto) vive en el
``PortfolioDecisionEngine``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Pesos del score V1. Suma = 1.0 por construcción.
OPPORTUNITY_WEIGHTS: dict[str, float] = {
    "edge": 0.30,
    "robustness": 0.20,
    "regime_fit": 0.15,
    "momentum": 0.10,
    "liquidity": 0.10,
    "risk_reward": 0.10,
    "execution_quality": 0.05,
}

# Componentes canónicos (orden documental; el peso de cada uno vive en WEIGHTS).
OPPORTUNITY_COMPONENTS: tuple[str, ...] = (
    "edge",
    "robustness",
    "regime_fit",
    "momentum",
    "liquidity",
    "risk_reward",
    "execution_quality",
)


def _clamp01(value: Any) -> float:
    """Normaliza a [0,1]; ausente/no finito ⇒ 0.0 (fail-closed)."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if number != number:
        return 0.0
    return min(1.0, max(0.0, number))


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


@dataclass(frozen=True, slots=True)
class OpportunityScore:
    """Score explicable de una oportunidad (componentes visibles + combinado)."""

    instrument_id: str
    components: dict[str, float] = field(default_factory=dict)
    combined: float = 0.0
    rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "components": dict(self.components),
            "combined": self.combined,
            "rank": self.rank,
        }


def score_opportunity(
    instrument_id: str,
    *,
    edge: Any = None,
    robustness: Any = None,
    regime_fit: Any = None,
    momentum: Any = None,
    liquidity: Any = None,
    risk_reward: Any = None,
    execution_quality: Any = None,
) -> OpportunityScore:
    """Score ponderado y explicable de UNA oportunidad.

    Solo los componentes presentes y finitos aportan; los ausentes cuentan como 0 y
    además **no** redistribuyen su peso (el combinado baja, honestamente, en vez de
    inflar el resto).
    """
    raw: dict[str, Any] = {
        "edge": edge,
        "robustness": robustness,
        "regime_fit": regime_fit,
        "momentum": momentum,
        "liquidity": liquidity,
        "risk_reward": risk_reward,
        "execution_quality": execution_quality,
    }
    components = {name: _clamp01(raw[name]) for name in OPPORTUNITY_COMPONENTS}
    combined = _round4(
        sum(components[name] * OPPORTUNITY_WEIGHTS[name] for name in OPPORTUNITY_COMPONENTS)
    )
    return OpportunityScore(
        instrument_id=str(instrument_id).strip(),
        components=components,
        combined=combined,
    )


def rank_opportunities(scores: Iterable[OpportunityScore]) -> tuple[OpportunityScore, ...]:
    """Ordena descendente por ``combined`` y asigna ``rank`` (1-based).

    Empate: desempate determinista por ``instrument_id`` (reproducible).
    """
    ordered = sorted(
        scores,
        key=lambda s: (-s.combined, str(s.instrument_id)),
    )
    return tuple(
        OpportunityScore(
            instrument_id=s.instrument_id,
            components=dict(s.components),
            combined=s.combined,
            rank=index + 1,
        )
        for index, s in enumerate(ordered)
    )


def select_top_opportunities(
    scores: Iterable[OpportunityScore],
    *,
    top_n: int,
) -> tuple[OpportunityScore, ...]:
    """Devuelve el TOP ``top_n`` operativo (ya rankeado).

    ``top_n <= 0`` ⇒ vacío (fail-closed, no se inventa un top). Orden estable.
    """
    if top_n <= 0:
        return ()
    return rank_opportunities(scores)[:top_n]
