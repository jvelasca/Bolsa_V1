"""RFC-008 Cognitive Decision Architecture — D1…D7."""

from bolsa_analytics.cognitive.auto_live import AutoLiveCheck, check_auto_live
from bolsa_analytics.cognitive.bracket_plan import (
    BRACKET_PLAN_KEY,
    build_bracket_plan_dict,
    map_bracket_plan,
)
from bolsa_analytics.cognitive.broker_adapter import (
    BROKER_ADAPTER_KEY,
    BROKER_ADAPTER_MOCK,
    BROKER_ADAPTER_PAPER,
    BROKER_ADAPTER_XTB,
    BrokerAdapterReceipt,
    broker_adapter_venue_copy,
    build_broker_adapter_receipt,
)
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
from bolsa_analytics.cognitive.execution_plan import (
    EXECUTION_PLAN_KEY,
    ExecutionPlan,
    build_execution_plan_from_exit_plan,
)
from bolsa_analytics.cognitive.execution_record import (
    EXECUTION_RECORD_KEY,
    ExecutionRecord,
    build_execution_record,
    execution_outcome_copy,
)
from bolsa_analytics.cognitive.submit_intent import (
    SUBMIT_INTENT_KEY,
    DurableSubmitIntent,
    bind_venue_order,
    mark_submit_filled,
    record_submit_intent,
    reconstruct_unknown,
    send_attempted_durable,
)
from bolsa_analytics.cognitive.exit_permission import (
    EXIT_PERMISSION_KEY,
    ExitPermission,
    check_exit_permission,
)
from bolsa_analytics.cognitive.exit_plan import (
    EXIT_PLAN_KEY,
    ExitPlan,
    build_exit_plan_from_position,
)
from bolsa_analytics.cognitive.exit_radar import (
    EXIT_RADAR_KEY,
    build_exit_radar_dict,
    map_exit_radar,
)
from bolsa_analytics.cognitive.expectancy import (
    EXPECTANCY_KEY,
    build_expectancy_dict,
    map_expectancy,
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
from bolsa_analytics.cognitive.live_ledger_reconciliation import (
    LIVE_LEDGER_RECONCILIATION_KEY,
    LiveHoldingSnap,
    LiveLedgerReconciliation,
    LivePositionSnap,
    LiveReconciliationCheck,
    build_live_ledger_reconciliation,
    live_ledger_reconciliation_status_copy,
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
from bolsa_analytics.cognitive.mfe_mae import (
    MFE_MAE_KEY,
    build_mfe_mae_dict,
    map_mfe_mae,
)
from bolsa_analytics.cognitive.observe_profile import (
    BehaviorTradeSample,
    PolicyBehaviorLimits,
    observe_investor_profile,
)
from bolsa_analytics.cognitive.order_intent import (
    OrderIntent,
    intent_from_recommendation,
    stable_intent_id_from_decision,
)
from bolsa_analytics.cognitive.paper_broker import (
    PAPER_BROKER_ADAPTER,
    PAPER_BROKER_KEY,
    PaperBrokerReceipt,
    build_paper_broker_receipt,
    paper_broker_venue_copy,
)
from bolsa_analytics.cognitive.paper_order import (
    PAPER_ORDER_KEY,
    PaperOrder,
    apply_paper_order_fill,
    build_paper_order,
    can_transition_paper_order,
    paper_order_status_copy,
    stable_order_id_from_decision,
    transition_paper_order,
)
from bolsa_analytics.cognitive.policy_gate import evaluate_policy_gate
from bolsa_analytics.cognitive.portfolio_fit import (
    UNKNOWN_SECTOR,
    BasketPosition,
    PortfolioFitSignal,
    compute_portfolio_fit,
)
from bolsa_analytics.cognitive.portfolio_reconciliation import (
    PORTFOLIO_RECONCILIATION_KEY,
    HoldingSnap,
    OpenPositionSnap,
    PortfolioReconciliation,
    ReconciliationCheck,
    build_portfolio_reconciliation,
    reconciliation_status_copy,
)
from bolsa_analytics.cognitive.position_revision import (
    POSITION_REVISIONS_KEY,
    PositionRevision,
    build_position_revision,
)
from bolsa_analytics.cognitive.position_state import (
    POSITION_STATE_KEY,
    PositionState,
    build_position_state_from_fill,
)
from bolsa_analytics.cognitive.protect_plan import (
    PROTECT_PLAN_KEY,
    build_protect_plan_dict,
    map_protect_plan,
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
from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature
from bolsa_analytics.cognitive.score_macro import ScoreMacroResult, score_macro_from_facts
from bolsa_analytics.cognitive.stats_suite import (
    monte_carlo_permutation_p_value,
    walk_forward_efficiency,
)
from bolsa_analytics.cognitive.suggest_policy import suggest_policy_template_from_declared
from bolsa_analytics.cognitive.thesis_health import (
    THESIS_HEALTH_KEY,
    build_thesis_health_dict,
    map_thesis_health,
)
from bolsa_analytics.cognitive.trade_plan import (
    TradePlan,
    build_trade_plan,
    build_v0_trade_plan_dict,
    classify_entry_setup,
    compute_risk_size,
    compute_structural_stop,
    entry_ready_from_ta,
    no_new_longs_blocks,
)
from bolsa_analytics.cognitive.trading_policy import TradingPolicy
from bolsa_analytics.cognitive.trading_policy_templates import (
    AGGRESSIVE_SWING_POLICY,
    CONSERVATIVE_POLICY,
    MODERATE_POLICY,
    POLICY_TEMPLATES,
    get_policy_template,
)
from bolsa_analytics.cognitive.trail_plan import (
    TRAIL_PLAN_KEY,
    build_trail_plan_dict,
    map_trail_plan,
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
from bolsa_domain.entities.market_event import (
    EventBlackoutContext,
    MarketEvent,
    MarketEventCalendar,
    build_market_event,
    event_decay_weight,
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
    "PositionState",
    "POSITION_STATE_KEY",
    "PositionRevision",
    "POSITION_REVISIONS_KEY",
    "ExitPlan",
    "EXIT_PLAN_KEY",
    "ExecutionPlan",
    "EXECUTION_PLAN_KEY",
    "ExecutionRecord",
    "EXECUTION_RECORD_KEY",
    "DurableSubmitIntent",
    "SUBMIT_INTENT_KEY",
    "PaperOrder",
    "PAPER_ORDER_KEY",
    "PaperBrokerReceipt",
    "PAPER_BROKER_KEY",
    "PAPER_BROKER_ADAPTER",
    "BrokerAdapterReceipt",
    "BROKER_ADAPTER_KEY",
    "BROKER_ADAPTER_PAPER",
    "BROKER_ADAPTER_MOCK",
    "BROKER_ADAPTER_XTB",
    "PortfolioReconciliation",
    "PORTFOLIO_RECONCILIATION_KEY",
    "HoldingSnap",
    "OpenPositionSnap",
    "ReconciliationCheck",
    "LiveLedgerReconciliation",
    "LIVE_LEDGER_RECONCILIATION_KEY",
    "LiveHoldingSnap",
    "LivePositionSnap",
    "LiveReconciliationCheck",
    "ExitPermission",
    "EXIT_PERMISSION_KEY",
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
    "build_position_state_from_fill",
    "build_position_revision",
    "evaluate_risk_signature",
    "build_exit_plan_from_position",
    "build_execution_plan_from_exit_plan",
    "build_execution_record",
    "execution_outcome_copy",
    "record_submit_intent",
    "bind_venue_order",
    "mark_submit_filled",
    "reconstruct_unknown",
    "send_attempted_durable",
    "build_paper_order",
    "stable_intent_id_from_decision",
    "stable_order_id_from_decision",
    "apply_paper_order_fill",
    "transition_paper_order",
    "can_transition_paper_order",
    "paper_order_status_copy",
    "build_paper_broker_receipt",
    "paper_broker_venue_copy",
    "build_broker_adapter_receipt",
    "broker_adapter_venue_copy",
    "build_portfolio_reconciliation",
    "reconciliation_status_copy",
    "build_live_ledger_reconciliation",
    "live_ledger_reconciliation_status_copy",
    "check_exit_permission",
    "build_thesis_health_dict",
    "build_protect_plan_dict",
    "build_exit_radar_dict",
    "build_mfe_mae_dict",
    "build_expectancy_dict",
    "build_trail_plan_dict",
    "build_bracket_plan_dict",
    "check_auto_live",
    "classify_regime",
    "compute_credibility",
    "compute_portfolio_fit",
    "compute_risk_size",
    "compute_structural_stop",
    "deflated_sharpe_ratio",
    "classify_entry_setup",
    "entry_ready_from_ta",
    "no_new_longs_blocks",
    "evaluate_policy_gate",
    "event_decay_weight",
    "gate_decision_package",
    "get_policy_template",
    "intent_from_recommendation",
    "map_thesis_health",
    "map_protect_plan",
    "map_exit_radar",
    "map_mfe_mae",
    "map_expectancy",
    "map_trail_plan",
    "map_bracket_plan",
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
    "THESIS_HEALTH_KEY",
    "PROTECT_PLAN_KEY",
    "EXIT_RADAR_KEY",
    "MFE_MAE_KEY",
    "EXPECTANCY_KEY",
    "TRAIL_PLAN_KEY",
    "BRACKET_PLAN_KEY",
    "validate_context",
    "walk_forward_efficiency",
    "weight_rules_for_horizon",
]
