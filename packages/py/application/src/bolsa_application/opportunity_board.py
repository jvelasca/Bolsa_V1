"""V2.88 — OpportunityBoard: ranking cross-asset de "3 mejores oportunidades (activos)".

Combina, POR ACTIVO, la evidencia de estrategia (adapter) + el encaje de régimen + el
veto operativo, y produce un ``OpportunityScore`` por activo listo para el ranker
``OpportunityRanker``. A diferencia de ``select_top3`` (que rankea ESTRATEGIAS dentro
de UN instrumento), el board rankea ACTIVOS del universo.

Sin DB ni IA: la resolución universo → campeón por activo y los predicados de veto se
inyectan como dependencias (puro/orquestable, igual que el resto del Strategy
Lifecycle). Fail-closed: un activo sin evidencia de campeón o vetado NO produce score;
se registra con su motivo real.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from bolsa_analytics.cognitive.opportunity_ranker import OpportunityScore, rank_opportunities
from bolsa_application.opportunity_evidence_adapter import score_instrument_opportunity
from bolsa_domain.entities.strategy_lifecycle import StrategyEvaluation, StrategyHealth

__all__ = [
    "AssetEvidence",
    "AssetExclusion",
    "OpportunityBoard",
    "OpportunityBoardResult",
    "NO_EVIDENCE",
]

#: Motivo de exclusión: el activo no tiene campeón evaluado en el LAB.
NO_EVIDENCE = "no_evidencia_campeon"


@dataclass(frozen=True, slots=True)
class AssetEvidence:
    """Evidencia de UN activo candidato a oportunidad (campeón + contexto de mercado)."""

    instrument_id: str
    evaluation: StrategyEvaluation | None = None
    health: StrategyHealth | None = None
    liquidity: float | None = None
    momentum: float | None = None
    risk_reward: float | None = None
    execution_quality: float | None = None


#: Callable de veto: recibe la evidencia del activo y devuelve un motivo si se veta.
Veto = Callable[[AssetEvidence], str | None]


@dataclass(frozen=True, slots=True)
class AssetExclusion:
    """Activo excluido del ranking con su motivo auditable."""

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class OpportunityBoardResult:
    """Resultado del board: scores rankeados + exclusiones con motivo."""

    scores: tuple[OpportunityScore, ...] = ()
    excluded: tuple[AssetExclusion, ...] = ()

    @property
    def ranked(self) -> tuple[OpportunityScore, ...]:
        return self.scores


class OpportunityBoard:
    """Ranking cross-asset de oportunidades (activos) con veto operativo inyectado.

    ``veto`` es opcional: si se aporta, decide la elegibilidad operativa por activo
    (liquidez, ATR, permitido/bloqueado, posición existente, conflicto de cartera, ...)
    devolviendo un motivo o ``None``. El board NO decide si operar: solo rankea; la
    decisión vive en ``PortfolioDecisionEngine`` (igual que el contrato del ranker).
    """

    def __init__(
        self,
        *,
        expected_regime: str | None = None,
        direction: str = "long",
        veto: Veto | None = None,
    ) -> None:
        self._expected_regime = expected_regime
        self._direction = direction
        self._veto = veto

    def score(self, evidence: Sequence[AssetEvidence]) -> OpportunityBoardResult:
        """Produce un ``OpportunityScore`` por activo elegible y sus exclusiones."""
        scores: list[OpportunityScore] = []
        excluded: list[AssetExclusion] = []

        for asset in evidence:
            if asset.evaluation is None and asset.health is None:
                excluded.append(AssetExclusion(asset.instrument_id, NO_EVIDENCE))
                continue
            if self._veto is not None:
                reason = self._veto(asset)
                if reason:
                    excluded.append(AssetExclusion(asset.instrument_id, reason))
                    continue
            scores.append(
                score_instrument_opportunity(
                    asset.instrument_id,
                    evaluation=asset.evaluation,
                    health=asset.health,
                    expected_regime=self._expected_regime,
                    direction=self._direction,
                    liquidity=asset.liquidity,
                    momentum=asset.momentum,
                    risk_reward=asset.risk_reward,
                    execution_quality=asset.execution_quality,
                )
            )

        return OpportunityBoardResult(
            scores=rank_opportunities(scores),
            excluded=tuple(excluded),
        )
