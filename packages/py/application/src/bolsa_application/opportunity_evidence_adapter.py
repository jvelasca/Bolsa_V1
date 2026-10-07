"""V2.88 — adapter de evidencia → componentes de oportunidad (TOP3 cross-asset).

Puente entre la evidencia de estrategia (LAB: IS/OOS/WFE/PBO/DSR/CPCV/drawdown) y el
ranker cross-asset ``OpportunityRanker`` (AUTO 2.0). El ranker ya existe y está
enchufado en el hot path V2, pero solo recibe ``edge`` + ``liquidity``: este módulo
completa los componentes de robustez, régimen y el resto a partir de la evidencia que
el Strategy Lifecycle ya calcula.

Sin IA, sin red, sin DB: transformaciones deterministas y fail-closed. Un componente
ausente o no finito vale ``0`` (nunca se inventa evidencia); el ``score_opportunity``
del ranker ya clampa a [0, 1] y no redistribuye pesos.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_analytics.cognitive.market_regime_gate import (
    regime_allows_entry_for,
    resolve_operational_regime,
)
from bolsa_analytics.cognitive.opportunity_ranker import OpportunityScore, score_opportunity
from bolsa_domain.entities.strategy_lifecycle import StrategyEvaluation, StrategyHealth

logger = logging.getLogger(__name__)

__all__ = [
    "EDGE_SCALE",
    "StrategyEvidenceBundle",
    "StrategyEvidenceSource",
    "evidence_components",
    "regime_fit_component",
    "robustness_component",
    "score_instrument_opportunity",
]

#: Escala de normalización del borde (calibrable; esqueleto V1): un score de borde
#: (``return% - 0.25 * dd%``) igual a ``EDGE_SCALE`` satura el componente ``edge`` a 1.
EDGE_SCALE: float = 10.0


def _finite(value: Any) -> float | None:
    """Devuelve ``value`` como float finito, o ``None`` (fail-closed)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number
    return None


def _clamp01(value: Any) -> float:
    """Normaliza a [0, 1]; ausente/no finito ⇒ 0.0 (fail-closed)."""
    number = _finite(value)
    if number is None:
        return 0.0
    return min(1.0, max(0.0, number))


def _normalize_edge(score: Any) -> float:
    """Mapea un score de borde (return% - 0.25·dd%) a [0, 1].

    Negativo ⇒ 0 (sin borde). Lineal hasta ``EDGE_SCALE`` (saturación), transparente y
    calibrable. Es un proxy del ``edge`` (EV / expectancy operacional) del ranker.
    """
    number = _finite(score)
    if number is None or number <= 0.0:
        return 0.0
    return _clamp01(number / EDGE_SCALE)


def _metric(
    evaluation: StrategyEvaluation | None,
    health: StrategyHealth | None,
    key: str,
    health_key: str | None = None,
) -> Any:
    """Lee una métrica del LAB (``evaluation.metrics``) con fallback a la salud ACTIVE."""
    if evaluation is not None:
        value = evaluation.metrics.get(key)
        if value is not None:
            return value
    if health is not None and health_key is not None:
        return getattr(health, health_key, None)
    return None


def robustness_component(
    evaluation: StrategyEvaluation | None = None,
    health: StrategyHealth | None = None,
) -> float:
    """Componente ``robustness`` = media de (WFE, DSR, 1 - PBO) presentes.

    Ninguno presente ⇒ 0.0 (fail-closed). Los componentes se claman a [0, 1]:
    WFE es OOS/IS (puede superar 1), DSR es una probabilidad [0, 1] y ``1 - PBO``
    también es [0, 1].
    """
    wfe = _finite(_metric(evaluation, health, "wfe", "walk_forward_efficiency"))
    dsr = _finite(_metric(evaluation, health, "dsr", "dsr"))
    pbo = _finite(_metric(evaluation, health, "pbo"))
    parts: list[float] = []
    if wfe is not None:
        parts.append(_clamp01(wfe))
    if dsr is not None:
        parts.append(_clamp01(dsr))
    if pbo is not None:
        parts.append(_clamp01(1.0 - pbo))
    return round(sum(parts) / len(parts), 4) if parts else 0.0


def regime_fit_component(
    evaluation: StrategyEvaluation | None = None,
    *,
    expected_regime: str | None = None,
    direction: str = "long",
) -> float:
    """Componente ``regime_fit``: 1.0 si el régimen permite la entrada, else 0.0.

    Con ``expected_regime`` se compara el régimen persistido del trial (match exacto).
    Sin ``expected_regime`` se usa el gate direccional fail-closed de
    ``market_regime_gate`` (UNKNOWN/RISK_OFF/BEAR bloquean LONG).
    """
    candidate_regime = None
    if evaluation is not None:
        candidate_regime = evaluation.metrics.get("regime")
    if expected_regime:
        if isinstance(candidate_regime, str) and candidate_regime.strip():
            return 1.0 if candidate_regime.strip() == str(expected_regime).strip() else 0.0
        return 0.0
    if isinstance(candidate_regime, str) and candidate_regime.strip():
        regime = resolve_operational_regime(trial_regime=candidate_regime)
        return 1.0 if regime_allows_entry_for(regime, direction) else 0.0
    return 0.0


def evidence_components(
    evaluation: StrategyEvaluation | None = None,
    *,
    health: StrategyHealth | None = None,
    expected_regime: str | None = None,
    direction: str = "long",
    liquidity: Any = None,
    momentum: Any = None,
    risk_reward: Any = None,
    execution_quality: Any = None,
) -> dict[str, float]:
    """Mapea la evidencia de estrategia a los 7 componentes del ``OpportunityScore``.

    - ``edge``            ← score de borde robusto (OOS preferido, IS fallback).
    - ``robustness``      ← media de (WFE, DSR, 1 - PBO).
    - ``regime_fit``      ← encaje de régimen (gate direccional / match esperado).
    - ``momentum``        ← aportado por el llamante (0 si no se aporta).
    - ``liquidity``       ← aportado por el llamante (0 si no se aporta).
    - ``risk_reward``     ← aportado por el llamante (0 si no se aporta).
    - ``execution_quality`` ← aportado por el llamante (0 si no se aporta).
    """
    edge_score = _metric(evaluation, health, "robust_score")
    if edge_score is None:
        edge_score = _metric(evaluation, health, "oos_score", "edge")
    if edge_score is None:
        edge_score = _metric(evaluation, health, "is_score")
    if edge_score is None and evaluation is not None:
        edge_score = evaluation.score

    return {
        "edge": _normalize_edge(edge_score),
        "robustness": robustness_component(evaluation, health),
        "regime_fit": regime_fit_component(
            evaluation, expected_regime=expected_regime, direction=direction
        ),
        "momentum": _clamp01(momentum),
        "liquidity": _clamp01(liquidity),
        "risk_reward": _clamp01(risk_reward),
        "execution_quality": _clamp01(execution_quality),
    }


def score_instrument_opportunity(
    instrument_id: str,
    *,
    evaluation: StrategyEvaluation | None = None,
    health: StrategyHealth | None = None,
    expected_regime: str | None = None,
    direction: str = "long",
    liquidity: Any = None,
    momentum: Any = None,
    risk_reward: Any = None,
    execution_quality: Any = None,
) -> OpportunityScore:
    """``OpportunityScore`` explicable de UN instrumento a partir de su evidencia."""
    components = evidence_components(
        evaluation,
        health=health,
        expected_regime=expected_regime,
        direction=direction,
        liquidity=liquidity,
        momentum=momentum,
        risk_reward=risk_reward,
        execution_quality=execution_quality,
    )
    return score_opportunity(instrument_id, **components)


@dataclass(frozen=True, slots=True)
class StrategyEvidenceBundle:
    """Par (evaluación, salud) del campeón ACTIVE de un instrumento."""

    evaluation: StrategyEvaluation | None = None
    health: StrategyHealth | None = None


@dataclass
class StrategyEvidenceSource:
    """Fuente de evidencia LAB por instrumento para el hot path SIM (TOP3 cross-asset).

    ``reader`` (async) devuelve, por instrumento, el par (evaluación, salud) del campeón
    ACTIVE; ``refresh()`` lo precarga UNA vez por tick y ``components_for()`` es la
    lectura SÍNCRONA del hot path (mismo patrón que ``EdgeReportSource``). Un fallo de
    lectura deja el mapa vacío ⇒ ``components_for`` devuelve ``None`` ⇒ el scoring es
    byte-idéntico al histórico (fail-closed: no se inventa evidencia).
    """

    reader: Callable[
        [Sequence[str], str | None], Awaitable[Mapping[str, StrategyEvidenceBundle]]
    ]
    _by_symbol: dict[str, dict[str, float]] = field(default_factory=dict, init=False, repr=False)

    async def refresh(self, symbols: Iterable[str], *, regime: str | None = None) -> None:
        wanted = [str(s).strip() for s in symbols if str(s).strip()]
        self._by_symbol = {}
        if not wanted:
            return
        try:
            bundles = await self.reader(wanted, regime) or {}
        except Exception:  # noqa: BLE001 — sin evidencia no se inventa una (fail-closed).
            logger.exception("auto_v2 strategy evidence read failed")
            return
        for symbol, bundle in bundles.items():
            key = str(symbol).strip()
            if not key:
                continue
            self._by_symbol[key] = evidence_components(
                bundle.evaluation,
                health=bundle.health,
                expected_regime=regime,
                direction="long",
            )

    def components_for(self, symbol: str) -> dict[str, float] | None:
        key = str(symbol).strip()
        return self._by_symbol.get(key) if key else None
