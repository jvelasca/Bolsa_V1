"""Market Knowledge Layer (RFC-008 D2/D5/D6) — Facts → Assessments → Runtime."""

from bolsa_analytics.cognitive.weight_rules import (
    HorizonHint,
    MarketRegime,
    WeightRuleResult,
    resolve_weight_rules,
    weight_rules_for_horizon,
)
from bolsa_analytics.knowledge.assessment import Assessment, AssessmentLike, AssessmentType
from bolsa_analytics.knowledge.decision_package_ta import build_decision_package_ta
from bolsa_analytics.knowledge.decision_runtime import (
    DecisionRuntimeResult,
    run_decision_runtime,
)
from bolsa_analytics.knowledge.evidence_assessment import (
    EvidenceAssessment,
    build_evidence_assessment,
)
from bolsa_analytics.knowledge.fundamental_assessment import (
    FundamentalAssessment,
    build_fundamental_assessment,
)
from bolsa_analytics.knowledge.composite_score import (
    COMPOSITE_SCHEMA_VERSION,
    COMPOSITE_SCORE_VERSION,
    build_composite_card,
    composite_to_chip,
)
from bolsa_analytics.knowledge.fundamental_card import (
    FUND_CARD_SCHEMA_VERSION,
    build_fundamental_card,
    compute_data_confidence,
    fund_score_to_display_100,
)
from bolsa_analytics.knowledge.fundamental_facts import build_fundamental_fact_set
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.macro_assessment import (
    MacroAssessment,
    build_macro_assessment,
)
from bolsa_analytics.knowledge.models import Fact, FactSet, TechnicalInputs
from bolsa_analytics.knowledge.news_assessment import (
    NewsAssessment,
    build_news_assessment,
)
from bolsa_analytics.knowledge.opportunity import (
    OpportunityResult,
    build_opportunity_package,
)
from bolsa_analytics.knowledge.score_fund import (
    SCORE_FUND_VERSION,
    ScoreFundResult,
    score_fund_from_facts,
)
from bolsa_analytics.knowledge.score_ta import ScoreTaResult, score_ta_from_facts
from bolsa_analytics.knowledge.technical_assessment import (
    TechnicalAssessment,
    bias_from_score,
    build_technical_assessment,
)
from bolsa_analytics.knowledge.technical_facts import build_technical_fact_set

__all__ = [
    "TechnicalInputs",
    "FundamentalInputs",
    "Fact",
    "FactSet",
    "Assessment",
    "AssessmentLike",
    "AssessmentType",
    "build_technical_fact_set",
    "build_fundamental_fact_set",
    "ScoreTaResult",
    "score_ta_from_facts",
    "ScoreFundResult",
    "score_fund_from_facts",
    "TechnicalAssessment",
    "build_technical_assessment",
    "bias_from_score",
    "FundamentalAssessment",
    "build_fundamental_assessment",
    "FUND_CARD_SCHEMA_VERSION",
    "build_fundamental_card",
    "compute_data_confidence",
    "fund_score_to_display_100",
    "COMPOSITE_SCHEMA_VERSION",
    "COMPOSITE_SCORE_VERSION",
    "build_composite_card",
    "composite_to_chip",
    "SCORE_FUND_VERSION",
    "MacroAssessment",
    "build_macro_assessment",
    "NewsAssessment",
    "build_news_assessment",
    "EvidenceAssessment",
    "build_evidence_assessment",
    "run_decision_runtime",
    "DecisionRuntimeResult",
    "build_decision_package_ta",
    "build_opportunity_package",
    "OpportunityResult",
    "WeightRuleResult",
    "weight_rules_for_horizon",
    "resolve_weight_rules",
    "HorizonHint",
    "MarketRegime",
]
