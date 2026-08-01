from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BacktestRunDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    name: str
    strategy_type: str = Field(alias="strategyType")
    initial_cash: float = Field(alias="initialCash")
    final_equity: float = Field(alias="finalEquity")
    total_return_pct: float = Field(alias="totalReturnPct")
    max_drawdown_pct: float = Field(alias="maxDrawdownPct")
    trade_count: int = Field(alias="tradeCount")
    win_count: int = Field(alias="winCount")
    bar_count: int = Field(alias="barCount")
    first_date: str = Field(alias="firstDate")
    last_date: str = Field(alias="lastDate")
    created_at: str = Field(alias="createdAt")
    timeframe: str | None = None
    data_version: str | None = Field(default=None, alias="dataVersion")
    commission_bps: int | None = Field(default=None, alias="commissionBps")
    slippage_bps: int | None = Field(default=None, alias="slippageBps")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    manifest: dict | None = None


class BacktestTradeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    type: str
    timestamp: str
    price: float
    quantity: float
    equity_after: float = Field(alias="equityAfter")
    reason: dict | None = None


class BacktestEquityPointDto(BaseModel):
    timestamp: str
    equity: float


class BacktestRunDetailDto(BacktestRunDto):
    trades: list[BacktestTradeDto]
    equity_curve: list[BacktestEquityPointDto] | None = Field(default=None, alias="equityCurve")


class BacktestListResponseDto(BaseModel):
    data: list[BacktestRunDto]


class PruneBacktestsRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    keep: int = Field(default=20, ge=0, le=500, description="Newest runs to keep")


class PruneBacktestsResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    deleted: int
    keep: int


class BacktestDetailResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    data: BacktestRunDetailDto
    trial_id: str | None = Field(default=None, alias="trialId")
    metrics: dict | None = None


class BacktestRunRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    strategy_type: str | None = Field(default=None, alias="strategyType")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    initial_cash: float | None = Field(default=None, alias="initialCash")
    limit: int | None = None
    date_from: str | None = Field(default=None, alias="dateFrom")
    date_to: str | None = Field(default=None, alias="dateTo")
    timeframe: str | None = None
    commission_bps: int | None = Field(default=None, alias="commissionBps")
    slippage_bps: int | None = Field(default=None, alias="slippageBps")
    spread_bps: int | None = Field(default=None, alias="spreadBps")
    # P9 — optional lab provenance for adopt→H0 trial.blocks (not re-validation).
    lab_evidence: dict | None = Field(default=None, alias="labEvidence")
    # P2.B — optional link to scientific hypothesis.
    hypothesis_id: str | None = Field(default=None, alias="hypothesisId")


class OosMetricsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    total_return_pct: float = Field(alias="totalReturnPct")
    max_drawdown_pct: float = Field(alias="maxDrawdownPct")
    trade_count: int = Field(alias="tradeCount")
    score: float
    sharpe_ratio: float | None = Field(default=None, alias="sharpeRatio")


class SmaGridTrialDto(BaseModel):
    """Optimize trial (SMA / RSI / MACD). Param fields are family-dependent."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    fast_period: int | None = Field(default=None, alias="fastPeriod")
    slow_period: int | None = Field(default=None, alias="slowPeriod")
    signal_period: int | None = Field(default=None, alias="signalPeriod")
    period: int | None = None
    oversold: float | None = None
    overbought: float | None = None
    total_return_pct: float = Field(alias="totalReturnPct")
    max_drawdown_pct: float = Field(alias="maxDrawdownPct")
    trade_count: int = Field(alias="tradeCount")
    score: float
    oos_metrics: OosMetricsDto | None = Field(default=None, alias="oosMetrics")


class OptimizeSmaGridRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    strategy_family: str | None = Field(default=None, alias="strategyFamily")
    fast_periods: list[int] | None = Field(default=None, alias="fastPeriods")
    slow_periods: list[int] | None = Field(default=None, alias="slowPeriods")
    periods: list[int] | None = None
    oversold_levels: list[float] | None = Field(default=None, alias="oversoldLevels")
    overbought_levels: list[float] | None = Field(default=None, alias="overboughtLevels")
    macd_triples: list[list[int]] | None = Field(default=None, alias="macdTriples")
    initial_cash: float | None = Field(default=None, alias="initialCash")
    bar_limit: int | None = Field(default=None, alias="barLimit")
    timeframe: str | None = None
    max_trials: int | None = Field(default=None, alias="maxTrials")
    engine: str | None = "auto"
    # Hold-out fraction (e.g. 0.2 = last 20% OOS). Null/0 = off.
    oos_pct: float | None = Field(default=None, alias="oosPct")
    # Expanding walk-forward folds (2–5). When set, overrides oosPct; H0 only.
    walk_forward_folds: int | None = Field(default=None, alias="walkForwardFolds")
    # CPCV ligero groups (4–6). Overrides WF and hold-out; H0 only.
    cpcv_groups: int | None = Field(default=None, alias="cpcvGroups")
    cpcv_purge_bars: int | None = Field(default=None, alias="cpcvPurgeBars")
    cpcv_embargo_bars: int | None = Field(default=None, alias="cpcvEmbargoBars")


class WalkForwardFoldDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    index: int
    train_bar_count: int = Field(alias="trainBarCount")
    test_bar_count: int = Field(alias="testBarCount")
    test_start_timestamp: str | None = Field(default=None, alias="testStartTimestamp")
    best_params: dict[str, Any] = Field(default_factory=dict, alias="bestParams")
    is_score: float = Field(alias="isScore")
    oos_metrics: OosMetricsDto | None = Field(default=None, alias="oosMetrics")
    walk_forward_efficiency: float | None = Field(
        default=None, alias="walkForwardEfficiency"
    )


class WalkForwardSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    n_folds: int = Field(alias="nFolds")
    mode: str = "expanding"
    mean_oos_score: float = Field(alias="meanOosScore")
    std_oos_score: float = Field(alias="stdOosScore")
    fold_count: int = Field(alias="foldCount")
    fold_scores: list[float] = Field(default_factory=list, alias="foldScores")
    folds: list[WalkForwardFoldDto] = Field(default_factory=list)
    mean_is_score: float | None = Field(default=None, alias="meanIsScore")
    walk_forward_efficiency: float | None = Field(
        default=None, alias="walkForwardEfficiency"
    )
    positive_oos_fold_share: float | None = Field(
        default=None, alias="positiveOosFoldShare"
    )
    oos_cv: float | None = Field(default=None, alias="oosCv")


class CpcvPathDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    index: int
    test_group_indices: list[int] = Field(alias="testGroupIndices")
    train_bar_count: int = Field(alias="trainBarCount")
    test_bar_count: int = Field(alias="testBarCount")
    test_start_timestamp: str | None = Field(default=None, alias="testStartTimestamp")
    best_params: dict[str, Any] = Field(default_factory=dict, alias="bestParams")
    is_score: float = Field(alias="isScore")
    oos_metrics: OosMetricsDto | None = Field(default=None, alias="oosMetrics")
    walk_forward_efficiency: float | None = Field(
        default=None, alias="walkForwardEfficiency"
    )


class CpcvSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    n_groups: int = Field(alias="nGroups")
    n_test_groups: int = Field(alias="nTestGroups")
    purge_bars: int = Field(alias="purgeBars")
    embargo_bars: int = Field(alias="embargoBars")
    path_count: int = Field(alias="pathCount")
    mode: str = "combinatorial_purged"
    mean_oos_score: float = Field(alias="meanOosScore")
    std_oos_score: float = Field(alias="stdOosScore")
    fold_count: int = Field(alias="foldCount")
    fold_scores: list[float] = Field(default_factory=list, alias="foldScores")
    paths: list[CpcvPathDto] = Field(default_factory=list)
    mean_is_score: float | None = Field(default=None, alias="meanIsScore")
    walk_forward_efficiency: float | None = Field(
        default=None, alias="walkForwardEfficiency"
    )
    positive_oos_fold_share: float | None = Field(
        default=None, alias="positiveOosFoldShare"
    )
    oos_cv: float | None = Field(default=None, alias="oosCv")
    pbo: dict[str, Any] | None = None


class OptimizeSmaGridResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    bar_count: int = Field(alias="barCount")
    baseline: SmaGridTrialDto
    trials: list[SmaGridTrialDto]
    engine: str
    trials_total: int | None = Field(default=None, alias="trialsTotal")
    strategy_family: str | None = Field(default=None, alias="strategyFamily")
    oos_pct: float | None = Field(default=None, alias="oosPct")
    is_bar_count: int | None = Field(default=None, alias="isBarCount")
    oos_bar_count: int | None = Field(default=None, alias="oosBarCount")
    split_timestamp: str | None = Field(default=None, alias="splitTimestamp")
    walk_forward: WalkForwardSummaryDto | None = Field(default=None, alias="walkForward")
    cpcv: CpcvSummaryDto | None = None
    edge_report: dict[str, Any] | None = Field(default=None, alias="edgeReport")
    pbo: dict[str, Any] | None = None


class OptimizeSmaGridResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    data: OptimizeSmaGridResultDto
    run_id: str | None = Field(default=None, alias="runId")


OptimizationRunStatus = Literal["pending", "processing", "completed", "failed"]


class OptimizationRunDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    status: OptimizationRunStatus
    payload: dict[str, object]
    result: OptimizeSmaGridResultDto | None = None
    error: str | None = None
    engine: str | None = None
    best_score: float | None = Field(default=None, alias="bestScore")
    trial_count: int | None = Field(default=None, alias="trialCount")
    bar_count: int | None = Field(default=None, alias="barCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")


class OptimizationRunResponseDto(BaseModel):
    data: OptimizationRunDto


class OptimizationRunsListResponseDto(BaseModel):
    data: list[OptimizationRunDto]
