"""DTOs HTTP de AI Governance (RFC-007/008 D7+) y Effectiveness / cognitive persist."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AiGovernanceStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    preferred_provider: str = Field(alias="preferredProvider")
    ollama_available: bool = Field(alias="ollamaAvailable")
    openai_available: bool = Field(alias="openaiAvailable")
    calls_recorded: int = Field(alias="callsRecorded")
    mode: str
    audit_sink: str = Field(alias="auditSink")
    producer_version: str = Field(alias="producerVersion")


class AiGovernanceStatusResponseDto(BaseModel):
    data: AiGovernanceStatusDto


class AiEffectivenessResponseDto(BaseModel):
    data: dict[str, Any]


class AppendDecisionMemoryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    decision_id: str = Field(alias="decisionId")
    instrument_id: str = Field(alias="instrumentId")
    outcome: Literal["accepted", "rejected", "deferred"]
    reasons: list[str] = Field(default_factory=list)
    policy_rule_ids: list[str] = Field(default_factory=list, alias="policyRuleIds")
    reevaluate_when: list[str] = Field(default_factory=list, alias="reevaluateWhen")
    opportunity_intact: bool = Field(default=True, alias="opportunityIntact")
    policy_id: str | None = Field(default=None, alias="policyId")
    policy_version: str | None = Field(default=None, alias="policyVersion")
    account_id: str | None = Field(default=None, alias="accountId")


class AppendTrialRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    log_id: str = Field(alias="logId")
    strategy_family_ref: str = Field(alias="strategyFamilyRef")
    hypothesis_ref: str = Field(alias="hypothesisRef")
    params_hash: str = Field(alias="paramsHash")
    sharpe_is: float | None = Field(default=None, alias="sharpeIs")
    notes: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")


class AppendEdgeReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    strategy_or_signal_ref: str = Field(alias="strategyOrSignalRef")
    trials_n: int = Field(alias="trialsN", ge=0)
    walk_forward_efficiency: float | None = Field(default=None, alias="walkForwardEfficiency")
    monte_carlo_p_value: float | None = Field(default=None, alias="monteCarloPValue")
    psr: float | None = None
    dsr: float | None = None
    bootstrap_alpha_ci_lower: float | None = Field(default=None, alias="bootstrapAlphaCiLower")
    bootstrap_alpha_ci_upper: float | None = Field(default=None, alias="bootstrapAlphaCiUpper")
    stress_survival_rate: float | None = Field(default=None, alias="stressSurvivalRate")
    account_id: str | None = Field(default=None, alias="accountId")
    notes: list[str] = Field(default_factory=list)


class CloseSessionOutcomeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["auto", "manual"] = "auto"
    verdict: Literal["hit", "miss", "neutral", "invalid", "skipped"] | None = None
    return_pct: float | None = Field(default=None, alias="returnPct")
    price_at_eval: float | None = Field(default=None, alias="priceAtEval")
    notes: str | None = None
    force: bool = False


class ProposeRecommendationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")
    suggested_quantity: float = Field(alias="suggestedQuantity", gt=0)
    suggested_price: float | None = Field(default=None, alias="suggestedPrice")
    action: Literal["recommend_long", "recommend_short", "wait"] | None = None
    include_fundamentals: bool = Field(default=True, alias="includeFundamentals")
    include_macro: bool = Field(default=True, alias="includeMacro")
    include_evidence: bool = Field(default=True, alias="includeEvidence")
    include_news: bool = Field(default=True, alias="includeNews")
    include_predictions: bool = Field(default=True, alias="includePredictions")
    strategy_or_signal_ref: str | None = Field(default=None, alias="strategyOrSignalRef")
    horizon: Literal["intraday", "swing", "position", "long_term"] = "swing"
    macro: dict[str, Any] | None = None


class ConfirmIntentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommendation: dict[str, Any]
    account_id: str = Field(alias="accountId")
    execute: bool = False
    session_id: str | None = Field(default=None, alias="sessionId")
    risk_override_reason: str | None = Field(default=None, alias="riskOverrideReason")


class BacktestCoachAnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    context: str
    battery: str
    local_summary: str = Field(default="", alias="localSummary")
    facts: dict[str, Any] | None = None
    """narrate = coach narrador+auditor; adversary = auditor C (solo findings tipados)."""
    mode: str = "narrate"


class FundamentalExplainRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId", min_length=1)


class DiaDSessionEvidenceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    mode: str
    symbol: str
    strategy_label: str = Field(alias="strategyLabel")
    dia_d: str = Field(alias="diaD")
    end_date: str = Field(alias="endDate")
    initial_cash: float = Field(default=10_000, alias="initialCash")
    auto: dict[str, Any]
    gated: dict[str, Any]
    gate: dict[str, Any]


class CoreRReviewEvidenceRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    verdict: str
    reason: str = ""


class CoreRReviewEvidenceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    list_id: str = Field(alias="listId")
    timeframe: str = "1d"
    rows: list[CoreRReviewEvidenceRow]


class FilingSummarizeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    filing_id: str = Field(alias="filingId")


class FilingAskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    filing_id: str = Field(alias="filingId")
    question: str = Field(min_length=1, max_length=800)
    top_k: int | None = Field(default=None, alias="topK", ge=1, le=8)


class DecisionSessionSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    session_id: str = Field(alias="sessionId")
    kind: str
    status: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str | None = Field(default=None, alias="symbol")
    account_id: str | None = Field(default=None, alias="accountId")
    recommendation_id: str | None = Field(default=None, alias="recommendationId")
    decision_id: str | None = Field(default=None, alias="decisionId")
    created_at: str = Field(alias="createdAt")


class ListDecisionSessionsResponseDto(BaseModel):
    data: list[DecisionSessionSummaryDto]
