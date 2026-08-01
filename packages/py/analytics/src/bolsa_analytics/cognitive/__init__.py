"""RFC-008 Cognitive Decision Architecture — D1…D7."""

from bolsa_analytics.cognitive.auto_live import AutoLiveCheck, check_auto_live
from bolsa_analytics.cognitive.confidence_lifecycle import (
    ConfidenceEvent,
    ConfidenceState,
    apply_confidence_event,
    apply_time_decay,
    open_confidence_state,
)
from bolsa_analytics.cognitive.decision_memory import DecisionMemoryEntry, build_memory_entry
from bolsa_analytics.cognitive.decision_session import (
    DecisionSession,
    WeightContext,
    attach_execution_to_payload,
    build_auto_session,
    build_propose_session,
    new_session_id,
)
from bolsa_analytics.cognitive.decision_outcome import (
    OUTCOME_CRITERIA_VERSION,
    SessionOutcome,
    attach_outcome_to_payload,
    build_manual_outcome,
    build_outcome_from_prices,
    resolve_eval_price_from_bars,
    summarize_session_outcomes,
)
from bolsa_analytics.cognitive.decision_replay import DecisionReplay, ReplayStep, build_decision_replay
from bolsa_analytics.cognitive.effectiveness import (
    EffectivenessSummary,
    build_effectiveness_summary,
)
from bolsa_analytics.cognitive.edge_report import (
    EdgeReport,
    StatisticalSuiteResult,
    build_edge_report,
    compute_credibility,
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
from bolsa_analytics.cognitive.market_events import (
    EventBlackoutContext,
    MarketEvent,
    MarketEventCalendar,
    build_market_event,
    event_decay_weight,
)
from bolsa_analytics.cognitive.market_state import (
    ContextValidationResult,
    MarketState,
    build_market_state,
    classify_regime,
    validate_context,
)
from bolsa_analytics.cognitive.policy_gate import evaluate_policy_gate
from bolsa_analytics.cognitive.psr_dsr import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    psr_dsr_from_returns,
)
from bolsa_analytics.cognitive.score_macro import ScoreMacroResult, score_macro_from_facts
from bolsa_analytics.cognitive.stats_suite import (
    monte_carlo_permutation_p_value,
    walk_forward_efficiency,
)
from bolsa_analytics.cognitive.observe_profile import (
    BehaviorTradeSample,
    PolicyBehaviorLimits,
    observe_investor_profile,
)
from bolsa_analytics.cognitive.order_intent import OrderIntent, intent_from_recommendation
from bolsa_analytics.cognitive.recommendation import (
    Recommendation,
    recommendation_from_decision_package,
)
from bolsa_analytics.cognitive.suggest_policy import suggest_policy_template_from_declared
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
    "InvestorProfile",
    "DeclaredInvestorProfile",
    "ObservedInvestorProfile",
    "TradingPolicy",
    "open_confidence_state",
    "apply_confidence_event",
    "apply_time_decay",
    "ConfidenceState",
    "ConfidenceEvent",
    "observe_investor_profile",
    "BehaviorTradeSample",
    "PolicyBehaviorLimits",
    "build_effectiveness_summary",
    "EffectivenessSummary",
    "Evidence",
    "EvidenceBundle",
    "EdgeReport",
    "StatisticalSuiteResult",
    "compute_credibility",
    "build_edge_report",
    "evaluate_policy_gate",
    "gate_decision_package",
    "GatedDecision",
    "ProposedTradeContext",
    "DecisionMemoryEntry",
    "build_memory_entry",
    "DecisionSession",
    "WeightContext",
    "build_propose_session",
    "build_auto_session",
    "attach_execution_to_payload",
    "new_session_id",
    "DecisionReplay",
    "ReplayStep",
    "build_decision_replay",
    "OUTCOME_CRITERIA_VERSION",
    "SessionOutcome",
    "attach_outcome_to_payload",
    "build_manual_outcome",
    "build_outcome_from_prices",
    "resolve_eval_price_from_bars",
    "summarize_session_outcomes",
    "WEIGHT_RULES_VERSION",
    "WeightRuleResult",
    "resolve_weight_rules",
    "weight_rules_for_horizon",
    "TrialsLog",
    "TrialRecord",
    "probabilistic_sharpe_ratio",
    "deflated_sharpe_ratio",
    "psr_dsr_from_returns",
    "run_evidence_suite",
    "EvidenceEngineInput",
    "EvidenceEngineResult",
    "check_auto_live",
    "AutoLiveCheck",
    "monte_carlo_permutation_p_value",
    "walk_forward_efficiency",
    "CONSERVATIVE_POLICY",
    "MODERATE_POLICY",
    "AGGRESSIVE_SWING_POLICY",
    "POLICY_TEMPLATES",
    "get_policy_template",
    "suggest_policy_template_from_declared",
    "MarketEvent",
    "MarketEventCalendar",
    "EventBlackoutContext",
    "build_market_event",
    "event_decay_weight",
    "MacroInputs",
    "build_macro_fact_set",
    "score_macro_from_facts",
    "ScoreMacroResult",
    "MarketState",
    "build_market_state",
    "classify_regime",
    "validate_context",
    "ContextValidationResult",
    "WeightRuleResult",
    "weight_rules_for_horizon",
    "resolve_weight_rules",
    "HorizonHint",
    "MarketRegime",
    "Recommendation",
    "recommendation_from_decision_package",
    "OrderIntent",
    "intent_from_recommendation",
]
