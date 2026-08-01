"""Opportunity Engine — construye Assessments y delega al DecisionRuntime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bolsa_analytics.cognitive.market_state import MarketState
from bolsa_analytics.cognitive.weight_rules import (
    HorizonHint,
    WeightRuleResult,
    resolve_weight_rules,
    weight_rules_for_horizon,
)
from bolsa_analytics.knowledge.decision_package_ta import DecisionPackageTa
from bolsa_analytics.knowledge.decision_runtime import run_decision_runtime
from bolsa_analytics.knowledge.fundamental_assessment import build_fundamental_assessment
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.macro_assessment import build_macro_assessment
from bolsa_analytics.knowledge.models import FactSet, TechnicalInputs
from bolsa_analytics.knowledge.score_fund import ScoreFundResult
from bolsa_analytics.knowledge.score_ta import ScoreTaResult
from bolsa_analytics.knowledge.technical_assessment import build_technical_assessment

__all__ = [
    "HorizonHint",
    "WeightRuleResult",
    "weight_rules_for_horizon",
    "resolve_weight_rules",
    "OpportunityResult",
    "build_opportunity_package",
]


@dataclass(frozen=True, slots=True)
class OpportunityResult:
    package: DecisionPackageTa
    score_ta: ScoreTaResult
    score_fund: ScoreFundResult | None
    score_macro: float | None
    combined_score: float
    weights: WeightRuleResult
    fact_set_ta: FactSet
    fact_set_fund: FactSet | None
    market_state: MarketState | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package.to_dict(),
            "scoreTa": self.score_ta.score,
            "scoreFund": None if self.score_fund is None else self.score_fund.score,
            "scoreMacro": self.score_macro,
            "combinedScore": self.combined_score,
            "weights": {
                "ta": self.weights.w_ta,
                "fund": self.weights.w_fund,
                "macro": self.weights.w_macro,
                "news": self.weights.w_news,
                "horizon": self.weights.horizon,
                "regime": self.weights.regime,
                "rationale": self.weights.rationale,
                "sizeHint": self.weights.size_hint,
                "vetoNewLong": self.weights.veto_new_long,
            },
            "factSetTaRef": self.fact_set_ta.fact_set_id,
            "factSetFundRef": None
            if self.fact_set_fund is None
            else self.fact_set_fund.fact_set_id,
            "marketStateId": None
            if self.market_state is None
            else self.market_state.state_id,
        }


def build_opportunity_package(
    instrument_id: str,
    technical: TechnicalInputs | dict | FactSet,
    fundamental: FundamentalInputs | dict | FactSet | None = None,
    *,
    horizon: HorizonHint = "swing",
    market_state: MarketState | None = None,
    timestamp: str | None = None,
    profile_snapshot_ref: str | None = None,
    policy_version: str | None = None,
) -> OpportunityResult:
    """
    Opportunity = Assessments (TA [+ FUND] [+ Macro]) → DecisionRuntime.
    Ya no construye la acción aquí; el Runtime es el único cerebro.
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    regime = market_state.regime if market_state is not None else "neutral"

    ta_assess, fact_ta, score_ta = build_technical_assessment(
        instrument_id, technical, timestamp=ts
    )
    assessments: list[Any] = [ta_assess]

    score_fund: ScoreFundResult | None = None
    fact_fund: FactSet | None = None
    if fundamental is not None:
        fa, fact_fund, score_fund = build_fundamental_assessment(
            instrument_id, fundamental, timestamp=ts
        )
        assessments.append(fa)

    score_macro_val: float | None = None
    if market_state is not None:
        ma, _, score_macro = build_macro_assessment(
            instrument_id, market_state, timestamp=ts
        )
        assessments.append(ma)
        score_macro_val = score_macro.score

    runtime = run_decision_runtime(
        instrument_id=instrument_id,
        assessments=assessments,
        horizon=horizon,
        regime=regime,
        profile_snapshot_ref=profile_snapshot_ref,
        policy_version=policy_version,
        evaluate_policy_gate=False,
    )

    weights = runtime.weights or resolve_weight_rules(horizon, regime)

    return OpportunityResult(
        package=runtime.package,
        score_ta=score_ta,
        score_fund=score_fund,
        score_macro=score_macro_val,
        combined_score=runtime.combined_score,
        weights=weights,
        fact_set_ta=fact_ta,
        fact_set_fund=fact_fund,
        market_state=market_state,
    )
