"""DTOs HTTP de research / Lab Health / trials."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchTrialDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    instrument_id: str = Field(alias="instrumentId")
    params: dict[str, Any]
    is_metrics: dict[str, Any] = Field(alias="isMetrics")
    proposed_by: str = Field(alias="proposedBy")
    k_contribution: int = Field(alias="kContribution")
    created_at: str = Field(alias="createdAt")
    hypothesis_id: str | None = Field(default=None, alias="hypothesisId")
    research_question_id: str | None = Field(default=None, alias="researchQuestionId")
    backtest_run_id: str | None = Field(default=None, alias="backtestRunId")
    optimization_run_id: str | None = Field(default=None, alias="optimizationRunId")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    preset_key: str | None = Field(default=None, alias="presetKey")
    strategy_name: str | None = Field(default=None, alias="strategyName")
    blocks: dict[str, Any] | None = None
    is_score: float | None = Field(default=None, alias="isScore")
    parent_trial_id: str | None = Field(default=None, alias="parentTrialId")
    fail_code: str | None = Field(default=None, alias="failCode")
    manifest_ref: dict[str, Any] | None = Field(default=None, alias="manifestRef")


class ResearchTrialsListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[ResearchTrialDto]
    total: int
    limit: int
    offset: int


class ResearchTrialDetailResponseDto(BaseModel):
    data: ResearchTrialDto


class InstrumentResearchSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    name: str
    trials: int
    k_consumed: int = Field(alias="kConsumed")
    avg_sharpe: float | None = Field(default=None, alias="avgSharpe")
    avg_sortino: float | None = Field(default=None, alias="avgSortino")
    avg_max_dd: float | None = Field(default=None, alias="avgMaxDD")
    best_sharpe: float | None = Field(default=None, alias="bestSharpe")
    last_trial_at: str | None = Field(default=None, alias="lastTrialAt")
    proposed_by: dict[str, int] = Field(default_factory=dict, alias="proposedBy")


class InstrumentResearchSummaryResponseDto(BaseModel):
    data: InstrumentResearchSummaryDto


class LabByInstrumentDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    trials: int
    k_consumed: int = Field(alias="kConsumed")
    avg_sharpe: float | None = Field(default=None, alias="avgSharpe")


class LabByPresetDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    preset_key: str = Field(alias="presetKey")
    trials: int
    k_consumed: int = Field(alias="kConsumed")


class LabByOriginDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    proposed_by: str = Field(alias="proposedBy")
    trials: int
    k_consumed: int = Field(alias="kConsumed")


class LaboratoryResearchSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    total_trials: int = Field(alias="totalTrials")
    total_k: int = Field(alias="totalK")
    active_instruments: int = Field(alias="activeInstruments")
    avg_sharpe: float | None = Field(default=None, alias="avgSharpe")
    avg_profit_factor: float | None = Field(default=None, alias="avgProfitFactor")
    avg_max_dd: float | None = Field(default=None, alias="avgMaxDD")
    last_trial_at: str | None = Field(default=None, alias="lastTrialAt")
    by_instrument: list[LabByInstrumentDto] = Field(alias="byInstrument")
    by_preset: list[LabByPresetDto] = Field(alias="byPreset")
    by_origin: list[LabByOriginDto] = Field(alias="byOrigin")


class LaboratoryResearchSummaryResponseDto(BaseModel):
    data: LaboratoryResearchSummaryDto


class LabHealthMetricCoverageDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    present: int
    pct: float


class LabHealthCampaignDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    campaign_id: str = Field(alias="campaignId")
    trials: int


class LabHealthDto(BaseModel):
    """Q0.1 — sanidad del ledger (cobertura métricas / zero-trades / campañas)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    total_trials: int = Field(alias="totalTrials")
    coverage: dict[str, LabHealthMetricCoverageDto]
    zero_trade_count: int = Field(alias="zeroTradeCount")
    zero_trade_pct: float = Field(alias="zeroTradePct")
    campaigns: list[LabHealthCampaignDto]
    campaign_count: int = Field(alias="campaignCount")
    instruments_with_trials: int = Field(alias="instrumentsWithTrials")
    active_instruments: int = Field(alias="activeInstruments")
    instruments_without_trials: int = Field(alias="instrumentsWithoutTrials")
    caveat: str


class LabHealthResponseDto(BaseModel):
    data: LabHealthDto


ResearchTrialSortParam = Literal[
    "created_at",
    "sharpe",
    "pnl",
    "commission",
    "k_contribution",
]

EvidenceLevelParam = Literal["A", "B", "C", "D"]


class ResearchEvidenceDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    instrument_id: str = Field(alias="instrumentId")
    level: str
    source: str
    evidence_weight: float = Field(alias="evidenceWeight")
    summary: dict[str, Any]
    created_at: str = Field(alias="createdAt")
    trial_id: str | None = Field(default=None, alias="trialId")
    hypothesis_id: str | None = Field(default=None, alias="hypothesisId")
    edge_report_id: str | None = Field(default=None, alias="edgeReportId")
    math_version: str | None = Field(default=None, alias="mathVersion")


class ResearchEvidenceListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[ResearchEvidenceDto]
    total: int
    limit: int
    offset: int


class ResearchEvidenceDetailResponseDto(BaseModel):
    data: ResearchEvidenceDto


class DiaDSessionEvidencePersistRequestDto(BaseModel):
    """Persistir informe Evidence sesión C DÍA D → research_evidence (source=dia_d_session)."""

    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    mode: str
    strategy_label: str = Field(alias="strategyLabel")
    dia_d: str = Field(alias="diaD")
    end_date: str = Field(alias="endDate")
    engine: str = "heuristic"
    evidence: dict[str, Any]


HypothesisKindParam = Literal["hypothesis", "anti"]
HypothesisStatusParam = Literal["open", "paused", "abandoned", "consolidated"]


class HypothesisDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    kind: str
    statement: str
    falsifiers: list[dict[str, Any]]
    status: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    domain: str | None = None
    context: dict[str, Any] | None = None


class HypothesisCreateRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    statement: str
    falsifiers: list[dict[str, Any]]
    kind: HypothesisKindParam = "hypothesis"
    domain: str | None = None
    context: dict[str, Any] | None = None
    status: HypothesisStatusParam = "open"


class HypothesisUpdateRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    statement: str | None = None
    falsifiers: list[dict[str, Any]] | None = None
    kind: HypothesisKindParam | None = None
    domain: str | None = None
    context: dict[str, Any] | None = None
    status: HypothesisStatusParam | None = None
    clear_domain: bool = Field(default=False, alias="clearDomain")
    clear_context: bool = Field(default=False, alias="clearContext")


class HypothesisDetailResponseDto(BaseModel):
    data: HypothesisDto


class HypothesesListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[HypothesisDto]
    total: int
    limit: int
    offset: int


class LinkTrialHypothesisRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hypothesis_id: str | None = Field(default=None, alias="hypothesisId")


class HypothesisBeliefDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    hypothesis_id: str = Field(alias="hypothesisId")
    belief: float
    belief_ci_low: float = Field(alias="beliefCiLow")
    belief_ci_high: float = Field(alias="beliefCiHigh")
    n_experiments: int = Field(alias="nExperiments")
    evidence_weight: float = Field(alias="evidenceWeight")
    contexts_ok: list[str] = Field(alias="contextsOk")
    contexts_fail: list[str] = Field(alias="contextsFail")
    evidence_ids: list[str] = Field(alias="evidenceIds")
    trial_ids: list[str] = Field(alias="trialIds")
    math_version: str = Field(alias="mathVersion")
    last_reviewed_at: str = Field(alias="lastReviewedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class HypothesisBeliefResponseDto(BaseModel):
    data: HypothesisBeliefDto


class BeliefHistoryEntryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    hypothesis_id: str = Field(alias="hypothesisId")
    belief_id: str = Field(alias="beliefId")
    belief: float
    belief_ci_low: float = Field(alias="beliefCiLow")
    belief_ci_high: float = Field(alias="beliefCiHigh")
    n_experiments: int = Field(alias="nExperiments")
    evidence_weight: float = Field(alias="evidenceWeight")
    math_version: str = Field(alias="mathVersion")
    created_at: str = Field(alias="createdAt")
    trigger_evidence_id: str | None = Field(default=None, alias="triggerEvidenceId")
    delta: dict[str, Any] | None = None


class BeliefHistoryListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[BeliefHistoryEntryDto]
    total: int
    limit: int
    offset: int


KnowledgeStageParam = Literal[
    "CANDIDATE", "EMERGING", "ACCEPTED", "CANONICAL", "DEPRECATED"
]


class KnowledgeNodeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    hypothesis_id: str = Field(alias="hypothesisId")
    stage: str
    statement: str
    knowledge_confidence: float = Field(alias="knowledgeConfidence")
    validity_context: dict[str, Any] = Field(alias="validityContext")
    evidence_ids: list[str] = Field(alias="evidenceIds")
    belief_snapshot: dict[str, Any] = Field(alias="beliefSnapshot")
    consolidation_report: dict[str, Any] = Field(alias="consolidationReport")
    math_version: str = Field(alias="mathVersion")
    consolidated_at: str = Field(alias="consolidatedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    notes: str | None = None


class KnowledgeNodeDetailResponseDto(BaseModel):
    data: KnowledgeNodeDto


class KnowledgeNodesListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[KnowledgeNodeDto]
    total: int
    limit: int
    offset: int


class ConsolidationRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    acknowledge_landscape_gap: bool = Field(
        default=False, alias="acknowledgeLandscapeGap"
    )
    notes: str | None = None
    validity_context: dict[str, Any] | None = Field(
        default=None, alias="validityContext"
    )
    dry_run: bool = Field(default=False, alias="dryRun")


class ConsolidationResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    created: bool
    node: KnowledgeNodeDto | None = None
    report: dict[str, Any]


class ConsolidationResultResponseDto(BaseModel):
    data: ConsolidationResultDto


class ConsolidationEligibilityResponseDto(BaseModel):
    data: dict[str, Any]


class ResearchTreeEdgeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    from_ref_type: str = Field(alias="fromRefType")
    from_ref_id: str = Field(alias="fromRefId")
    to_ref_type: str = Field(alias="toRefType")
    to_ref_id: str = Field(alias="toRefId")
    edge_type: str = Field(alias="edgeType")
    created_at: str = Field(alias="createdAt")
    notes: str | None = None
    payload: dict[str, Any] | None = None
    deleted_at: str | None = Field(default=None, alias="deletedAt")


class ResearchTreeEdgeCreateRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_ref_type: str = Field(alias="fromRefType")
    from_ref_id: str = Field(alias="fromRefId")
    to_ref_type: str = Field(alias="toRefType")
    to_ref_id: str = Field(alias="toRefId")
    edge_type: str = Field(alias="edgeType")
    notes: str | None = None
    payload: dict[str, Any] | None = None


class ResearchTreeEdgeDetailResponseDto(BaseModel):
    data: ResearchTreeEdgeDto


class ResearchTreeEdgesListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[ResearchTreeEdgeDto]
    total: int
    limit: int
    offset: int


class MklSyncRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dry_run: bool = Field(default=False, alias="dryRun")
    promote_to_accepted: bool = Field(default=True, alias="promoteToAccepted")


class MklSyncEventDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    knowledge_node_id: str = Field(alias="knowledgeNodeId")
    status: str
    fact_payload: dict[str, Any] = Field(alias="factPayload")
    math_version: str = Field(alias="mathVersion")
    created_at: str = Field(alias="createdAt")
    notes: list[str]


class MklSyncResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    synced: bool
    dry_run: bool = Field(alias="dryRun")
    event: MklSyncEventDto
    node: KnowledgeNodeDto
    fact_payload: dict[str, Any] = Field(alias="factPayload")


class MklSyncResultResponseDto(BaseModel):
    data: MklSyncResultDto


class MklSyncEventsListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: list[MklSyncEventDto]
    total: int
    limit: int
    offset: int
