"""RFC-008 Cognitive Decision Architecture — D1…D7."""

from bolsa_domain.entities.market_event import (
    EventBlackoutContext,
    MarketEvent,
    MarketEventCalendar,
    build_market_event,
    event_decay_weight,
)

from bolsa_analytics.cognitive.auto_live import AutoLiveCheck, check_auto_live
from bolsa_analytics.cognitive.confidence_lifecycle import (
    ConfidenceEvent,
    ConfidenceState,
    apply_confidence_event,
    apply_time_decay,
    open_confidence_state,
)
from bolsa_analytics.cognitive.decision_memory import DecisionMemoryEntry, build_memory_entry
from bolsa_analytics.cognitive.decision_outcome import (
    OUTCOME_CRITERIA_VERSION,
    SessionOutcome,
    attach_outcome_to_payload,
    build_manual_outcome,
    build_outcome_from_prices,
    resolve_eval_price_from_bars,
    summarize_session_outcomes,
)
from bolsa_analytics.cognitive.decision_replay import (
    DecisionReplay,
    ReplayStep,
    build_decision_replay,
)
from bolsa_analytics.cognitive.decision_session import (
    DecisionSession,
    WeightContext,
    attach_execution_to_payload,
    build_auto_session,
    build_propose_session,
    new_session_id,
)
from bolsa_analytics.cognitive.edge_report import (
    EdgeReport,
    StatisticalSuiteResult,
    build_edge_report,
    compute_credibility,
)
from bolsa_analytics.cognitive.effectiveness import (
    EffectivenessSummary,
    build_effectiveness_summary,
)
from bolsa_analytics.cognitive.evidence import Evidence, EvidenceBundle
from bolsa_analytics.cognitive.evidence_engine import (
    EvidenceEngineInput,
    EvidenceEngineResult,
    run_evidence_suite,
)
from bolsa_analytics.cognitive.gate_decision import (
    GatedDecision,
    ProposedTradeContext,
    gate_decision_package,
)
from bolsa_analytics.cognitive.investor_profile import (
    DeclaredInvestorProfile,
    InvestorProfile,
    ObservedInvestorProfile,
)
from bolsa_analytics.cognitive.macro_facts import build_macro_fact_set
from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.cognitive.market_state import (
    ContextValidationResult,
    MarketState,
    build_market_state,
    classify_regime,
    validate_context,
)
from bolsa_analytics.cognitive.observe_profile import (
    BehaviorTradeSample,
    PolicyBehaviorLimits,
    observe_investor_profile,
)
from bolsa_analytics.cognitive.order_intent import OrderIntent, intent_from_recommendation
from bolsa_analytics.cognitive.policy_gate import evaluate_policy_gate
from bolsa_analytics.cognitive.portfolio_fit import (
    UNKNOWN_SECTOR,
    BasketPosition,
    PortfolioFitSignal,
    compute_portfolio_fit,
)
from bolsa_analytics.cognitive.psr_dsr import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    psr_dsr_from_returns,
)
from bolsa_analytics.cognitive.recommendation import (
    Recommendation,
    recommendation_from_decision_package,
)
from bolsa_analytics.cognitive.score_macro import ScoreMacroResult, score_macro_from_facts
from bolsa_analytics.cognitive.stats_suite import (
    monte_carlo_permutation_p_value,
    walk_forward_efficiency,
)
from bolsa_analytics.cognitive.suggest_policy import suggest_policy_template_from_declared
from bolsa_analytics.cognitive.trade_plan import (
    TradePlan,
    build_trade_plan,
    build_v0_trade_plan_dict,
    compute_risk_size,
)
from bolsa_analytics.cognitive.trading_policy import TradingPolicy
from bolsa_analytics.cognitive.trading_policy_templates import (
    AGGRESSIVE_SWING_POLICY,
    CONSERVATIVE_POLICY,
    MODERATE_POLICY,
    POLICY_TEMPLATES,
    get_policy_template,
)
from bolsa_analytics.cognitive.trials_log import TrialRecord, TrialsLog
from bolsa_analytics.cognitive.weight_rules import (
    WEIGHT_RULES_VERSION,
    HorizonHint,
    MarketRegime,
    WeightRuleResult,
    resolve_weight_rules,
    weight_rules_for_horizon,
)

__all__ = [
    "AGGRESSIVE_SWING_POLICY",
    "CONSERVATIVE_POLICY",
    "MODERATE_POLICY",
    "OUTCOME_CRITERIA_VERSION",
    "POLICY_TEMPLATES",
    "WEIGHT_RULES_VERSION",
    "AutoLiveCheck",
    "BasketPosition",
    "BehaviorTradeSample",
    "ConfidenceEvent",
    "ConfidenceState",
    "ContextValidationResult",
    "DecisionMemoryEntry",
    "DecisionReplay",
    "DecisionSession",
    "DeclaredInvestorProfile",
    "EdgeReport",
    "EffectivenessSummary",
    "EventBlackoutContext",
    "Evidence",
    "EvidenceBundle",
    "EvidenceEngineInput",
    "EvidenceEngineResult",
    "GatedDecision",
    "HorizonHint",
    "InvestorProfile",
    "MacroInputs",
    "MarketEvent",
    "MarketEventCalendar",
    "MarketRegime",
    "MarketState",
    "ObservedInvestorProfile",
    "OrderIntent",
    "PolicyBehaviorLimits",
    "PortfolioFitSignal",
    "ProposedTradeContext",
    "Recommendation",
    "ReplayStep",
    "ScoreMacroResult",
    "SessionOutcome",
    "StatisticalSuiteResult",
    "TradePlan",
    "TradingPolicy",
    "TrialRecord",
    "TrialsLog",
    "UNKNOWN_SECTOR",
    "WeightContext",
    "WeightRuleResult",
    "apply_confidence_event",
    "apply_time_decay",
    "attach_execution_to_payload",
    "attach_outcome_to_payload",
    "build_auto_session",
    "build_decision_replay",
    "build_edge_report",
    "build_effectiveness_summary",
    "build_macro_fact_set",
    "build_manual_outcome",
    "build_market_event",
    "build_market_state",
    "build_memory_entry",
    "build_outcome_from_prices",
    "build_propose_session",
    "build_trade_plan",
    "build_v0_trade_plan_dict",
    "check_auto_live",
    "classify_regime",
    "compute_credibility",
    "compute_portfolio_fit",
    "compute_risk_size",
    "deflated_sharpe_ratio",
    "evaluate_policy_gate",
    "event_decay_weight",
    "gate_decision_package",
    "get_policy_template",
    "intent_from_recommendation",
    "monte_carlo_permutation_p_value",
    "new_session_id",
    "observe_investor_profile",
    "open_confidence_state",
    "probabilistic_sharpe_ratio",
    "psr_dsr_from_returns",
    "recommendation_from_decision_package",
    "resolve_eval_price_from_bars",
    "resolve_weight_rules",
    "run_evidence_suite",
    "score_macro_from_facts",
    "suggest_policy_template_from_declared",
    "summarize_session_outcomes",
    "validate_context",
    "walk_forward_efficiency",
    "weight_rules_for_horizon",
]
