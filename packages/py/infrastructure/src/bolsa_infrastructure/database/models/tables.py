from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

TIMEFRAME_ENUM = ENUM(
    "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo",
    name="Timeframe",
    create_type=False,
)
SYNC_STATUS_ENUM = ENUM("success", "partial", "failed", name="SyncStatus", create_type=False)
DATA_PROVIDER_ENUM = ENUM("yahoo", "xtb", name="DataProvider", create_type=False)
TRANSACTION_TYPE_ENUM = ENUM("buy", "sell", name="TransactionType", create_type=False)
BACKTEST_STRATEGY_ENUM = ENUM(
    "sma_crossover",
    "rsi_mean_reversion",
    "ema_crossover",
    "golden_cross",
    "death_cross",
    "macd_signal_cross",
    "macd_zero_line",
    "rsi_momentum",
    "rsi_oversold_bounce",
    "stoch_oversold",
    "bollinger_lower_bounce",
    "bollinger_upper_breakout",
    "price_above_sma200",
    "ma_stack_bullish",
    "pullback_in_uptrend",
    "cci_oversold",
    "donchian_breakout",
    "adx_di_trend",
    "ichimoku_tk_cross",
    "vwap_reclaim",
    "supertrend_follow",
    name="BacktestStrategyType",
    create_type=False,
)
ALERT_CONDITION_ENUM = ENUM("above", "below", name="AlertCondition", create_type=False)
ALERT_PRICE_SOURCE_ENUM = ENUM("daily_close", "xtb_last", name="AlertPriceSource", create_type=False)
INSTRUMENT_TYPE_ENUM = ENUM("stock", name="InstrumentType", create_type=False)


class Base(DeclarativeBase):
    pass


class InstrumentRow(Base):
    __tablename__ = "instruments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    yahoo_symbol: Mapped[str] = mapped_column("yahoo_symbol", String, unique=True)
    isin: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String, default="ES")
    currency: Mapped[str] = mapped_column(String, default="EUR")
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(INSTRUMENT_TYPE_ENUM, default="stock")
    is_active: Mapped[bool] = mapped_column("is_active", Boolean, default=True)
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column("profile_snapshot", JSONB, nullable=True)
    last_xtb_validation: Mapped[dict[str, Any] | None] = mapped_column("last_xtb_validation", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    ohlcv_bars: Mapped[list["OhlcvBarRow"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sync_logs: Mapped[list["DataSyncLogRow"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    data_snapshots: Mapped[list["DataSnapshotRow"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    position_policies: Mapped[list["PositionPolicyRow"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OhlcvBarRow(Base):
    __tablename__ = "ohlcv_bars"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    timeframe: Mapped[str] = mapped_column(TIMEFRAME_ENUM, default="1d")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(BigInteger)
    adj_close: Mapped[Decimal | None] = mapped_column("adj_close", Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(DATA_PROVIDER_ENUM, default="yahoo")
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship(back_populates="ohlcv_bars")


class DataSyncLogRow(Base):
    __tablename__ = "data_sync_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(DATA_PROVIDER_ENUM)
    status: Mapped[str] = mapped_column(SYNC_STATUS_ENUM)
    bars_added: Mapped[int] = mapped_column("bars_added", Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column("synced_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship(back_populates="sync_logs")


class PortfolioRow(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="Cartera principal")
    currency: Mapped[str] = mapped_column(String, default="EUR")
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(100000))
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    positions: Mapped[list["PositionRow"]] = relationship(back_populates="portfolio")
    transactions: Mapped[list["TransactionRow"]] = relationship(back_populates="portfolio")


class PositionRow(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    portfolio_id: Mapped[str] = mapped_column("portfolio_id", ForeignKey("portfolios.id"))
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    avg_cost: Mapped[Decimal] = mapped_column("avg_cost", Numeric(18, 6))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    portfolio: Mapped[PortfolioRow] = relationship(back_populates="positions")
    instrument: Mapped[InstrumentRow] = relationship()


class TransactionRow(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "idempotency_key", name="transactions_portfolio_id_idempotency_key_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    portfolio_id: Mapped[str] = mapped_column("portfolio_id", ForeignKey("portfolios.id"))
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(TRANSACTION_TYPE_ENUM)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    executed_at: Mapped[datetime] = mapped_column("executed_at", DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column("idempotency_key", String, nullable=True)

    portfolio: Mapped[PortfolioRow] = relationship(back_populates="transactions")
    instrument: Mapped[InstrumentRow] = relationship()


class BacktestRunRow(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    strategy_type: Mapped[str] = mapped_column("strategy_type", BACKTEST_STRATEGY_ENUM)
    initial_cash: Mapped[Decimal] = mapped_column("initial_cash", Numeric(18, 6))
    final_equity: Mapped[Decimal] = mapped_column("final_equity", Numeric(18, 6))
    total_return_pct: Mapped[Decimal] = mapped_column("total_return_pct", Numeric(10, 4))
    max_drawdown_pct: Mapped[Decimal] = mapped_column("max_drawdown_pct", Numeric(10, 4))
    trade_count: Mapped[int] = mapped_column("trade_count", Integer)
    win_count: Mapped[int] = mapped_column("win_count", Integer)
    bar_count: Mapped[int] = mapped_column("bar_count", Integer)
    first_date: Mapped[date] = mapped_column("first_date", Date)
    last_date: Mapped[date] = mapped_column("last_date", Date)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    timeframe: Mapped[str] = mapped_column(String, default="1d")
    data_version: Mapped[str | None] = mapped_column("data_version", String, nullable=True)
    commission_bps: Mapped[int] = mapped_column("commission_bps", Integer, default=0)
    slippage_bps: Mapped[int] = mapped_column("slippage_bps", Integer, default=0)
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    data_epoch: Mapped[str | None] = mapped_column("data_epoch", String, nullable=True)
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id",
        ForeignKey("strategy_definitions.id"),
        nullable=True,
    )

    instrument: Mapped[InstrumentRow] = relationship()
    strategy_definition: Mapped["StrategyDefinitionRow | None"] = relationship()
    trades: Mapped[list["BacktestTradeRow"]] = relationship(back_populates="backtest_run")
    research_trials: Mapped[list["ResearchTrialRow"]] = relationship(back_populates="backtest_run")


class StrategyDefinitionRow(Base):
    __tablename__ = "strategy_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    preset_key: Mapped[str | None] = mapped_column("preset_key", String, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="manual")
    timeframe: Mapped[str] = mapped_column(String, default="1d")
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    backtest_runs: Mapped[list["BacktestRunRow"]] = relationship(back_populates="strategy_definition")
    research_trials: Mapped[list["ResearchTrialRow"]] = relationship(back_populates="strategy_definition")
    signal_alert_subscriptions: Mapped[list["SignalAlertSubscriptionRow"]] = relationship(
        back_populates="strategy_definition",
    )
    tracker_definitions: Mapped[list["TrackerDefinitionRow"]] = relationship(
        back_populates="strategy_definition",
    )
    scan_manifests: Mapped[list["ScanManifestRow"]] = relationship(back_populates="strategy_definition")
    execution_policies: Mapped[list["ExecutionPolicyRow"]] = relationship(
        back_populates="strategy_definition",
    )
    position_policies_exit_strategy: Mapped[list["PositionPolicyRow"]] = relationship(
        back_populates="exit_strategy_definition",
    )


class BacktestTradeRow(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    backtest_run_id: Mapped[str] = mapped_column("backtest_run_id", ForeignKey("backtest_runs.id"))
    type: Mapped[str] = mapped_column(TRANSACTION_TYPE_ENUM)
    timestamp: Mapped[date] = mapped_column(Date)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    equity_after: Mapped[Decimal] = mapped_column("equity_after", Numeric(18, 6))

    backtest_run: Mapped[BacktestRunRow] = relationship(back_populates="trades")


class InstrumentListRow(Base):
    __tablename__ = "instrument_lists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="custom")
    kind: Mapped[str | None] = mapped_column(String, nullable=True)
    universe_code: Mapped[str | None] = mapped_column("universe_code", String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        "last_synced_at",
        DateTime(timezone=True),
        nullable=True,
    )
    content_hash: Mapped[str | None] = mapped_column("content_hash", String, nullable=True)
    membership_changelog: Mapped[dict[str, Any] | None] = mapped_column(
        "membership_changelog",
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    items: Mapped[list["InstrumentListItemRow"]] = relationship(
        back_populates="list",
        cascade="all, delete-orphan",
        order_by="InstrumentListItemRow.sort_order",
    )


class IndexSubscribeJobRow(Base):
    __tablename__ = "index_subscribe_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        "completed_at",
        DateTime(timezone=True),
        nullable=True,
    )


class InstrumentListItemRow(Base):
    __tablename__ = "instrument_list_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    list_id: Mapped[str] = mapped_column("list_id", ForeignKey("instrument_lists.id"))
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column("sort_order", Integer, default=0)

    list: Mapped[InstrumentListRow] = relationship(back_populates="items")
    instrument: Mapped[InstrumentRow] = relationship()


class PriceAlertRow(Base):
    __tablename__ = "price_alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String)
    condition: Mapped[str] = mapped_column(ALERT_CONDITION_ENUM)
    price_source: Mapped[str] = mapped_column("price_source", ALERT_PRICE_SOURCE_ENUM, default="daily_close")
    target_price: Mapped[Decimal] = mapped_column("target_price", Numeric(18, 6))
    is_active: Mapped[bool] = mapped_column("is_active", Boolean, default=True)
    triggered_at: Mapped[datetime | None] = mapped_column("triggered_at", DateTime(timezone=True), nullable=True)
    triggered_price: Mapped[Decimal | None] = mapped_column(
        "triggered_price",
        Numeric(18, 6),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship()


class SignalAlertSubscriptionRow(Base):
    __tablename__ = "signal_alert_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String)
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id",
        ForeignKey("strategy_definitions.id"),
        nullable=True,
    )
    preset_key: Mapped[str | None] = mapped_column("preset_key", String, nullable=True)
    timeframe: Mapped[str] = mapped_column(String, default="1d")
    signal_kinds: Mapped[list[Any]] = mapped_column("signal_kinds", JSONB, default=list)
    channels: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    webhook_url: Mapped[str | None] = mapped_column("webhook_url", String, nullable=True)
    email_to: Mapped[str | None] = mapped_column("email_to", String, nullable=True)
    is_active: Mapped[bool] = mapped_column("is_active", Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        "last_triggered_at",
        DateTime(timezone=True),
        nullable=True,
    )
    last_bar_timestamp: Mapped[str | None] = mapped_column("last_bar_timestamp", String, nullable=True)
    last_signal_kind: Mapped[str | None] = mapped_column("last_signal_kind", String, nullable=True)
    last_signal_price: Mapped[Decimal | None] = mapped_column(
        "last_signal_price",
        Numeric(18, 6),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship()
    strategy_definition: Mapped["StrategyDefinitionRow | None"] = relationship(
        back_populates="signal_alert_subscriptions",
    )


class ScanJobRow(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cache_hits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_misses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tracker_definition_id: Mapped[str | None] = mapped_column(
        "tracker_definition_id",
        String,
        ForeignKey("tracker_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        "completed_at",
        DateTime(timezone=True),
        nullable=True,
    )

    tracker_definition: Mapped["TrackerDefinitionRow | None"] = relationship(
        back_populates="scan_jobs",
    )
    scan_manifest: Mapped["ScanManifestRow | None"] = relationship(
        back_populates="scan_job",
        uselist=False,
    )


class DataSnapshotRow(Base):
    __tablename__ = "data_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        String,
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    timeframe: Mapped[str] = mapped_column(String)
    data_version: Mapped[str] = mapped_column("data_version", String)
    bar_count: Mapped[int] = mapped_column("bar_count", Integer)
    from_ts: Mapped[str] = mapped_column("from_ts", String)
    to_ts: Mapped[str] = mapped_column("to_ts", String)
    source: Mapped[str] = mapped_column(String, default="postgres")
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    instrument: Mapped["InstrumentRow"] = relationship(back_populates="data_snapshots")


class ScanManifestRow(Base):
    __tablename__ = "scan_manifests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scan_job_id: Mapped[str | None] = mapped_column(
        "scan_job_id",
        String,
        ForeignKey("scan_jobs.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    tracker_definition_id: Mapped[str | None] = mapped_column(
        "tracker_definition_id",
        String,
        ForeignKey("tracker_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id",
        String,
        ForeignKey("strategy_definitions.id"),
        nullable=True,
    )
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    scan_job: Mapped["ScanJobRow | None"] = relationship(back_populates="scan_manifest")
    tracker_definition: Mapped["TrackerDefinitionRow | None"] = relationship(
        back_populates="scan_manifests",
    )
    strategy_definition: Mapped["StrategyDefinitionRow"] = relationship(
        back_populates="scan_manifests",
    )


class ExecutionPolicyRow(Base):
    __tablename__ = "execution_policies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    mode: Mapped[str] = mapped_column(String)
    account_id: Mapped[str | None] = mapped_column(
        "account_id",
        String,
        ForeignKey("investment_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id",
        String,
        ForeignKey("strategy_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    origin: Mapped[str] = mapped_column(String, default="manual")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[str | None] = mapped_column("user_id", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    account: Mapped["InvestmentAccountRow | None"] = relationship(back_populates="execution_policies")
    strategy_definition: Mapped["StrategyDefinitionRow | None"] = relationship(
        back_populates="execution_policies",
    )
    position_policies: Mapped[list["PositionPolicyRow"]] = relationship(
        back_populates="execution_policy",
    )


class PositionPolicyRow(Base):
    __tablename__ = "position_policies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        "account_id",
        String,
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
    )
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        String,
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    mode: Mapped[str] = mapped_column(String, default="manual")
    exit_strategy_definition_id: Mapped[str | None] = mapped_column(
        "exit_strategy_definition_id",
        String,
        ForeignKey("strategy_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    execution_policy_id: Mapped[str | None] = mapped_column(
        "execution_policy_id",
        String,
        ForeignKey("execution_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    account: Mapped["InvestmentAccountRow"] = relationship(back_populates="position_policies")
    instrument: Mapped["InstrumentRow"] = relationship(back_populates="position_policies")
    exit_strategy_definition: Mapped["StrategyDefinitionRow | None"] = relationship(
        back_populates="position_policies_exit_strategy",
    )
    execution_policy: Mapped["ExecutionPolicyRow | None"] = relationship(
        back_populates="position_policies",
    )


class PlatformEventRow(Base):
    __tablename__ = "platform_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    correlation_id: Mapped[str | None] = mapped_column("correlation_id", String, nullable=True)
    user_id: Mapped[str | None] = mapped_column("user_id", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class LlmCallRow(Base):
    """ART-LLM-CALL — append-only (RFC-007)."""

    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt_template_id: Mapped[str] = mapped_column("prompt_template_id", String)
    prompt_rendered: Mapped[str] = mapped_column("prompt_rendered", Text)
    response_raw: Mapped[str | None] = mapped_column("response_raw", Text, nullable=True)
    response_parsed: Mapped[dict[str, Any] | None] = mapped_column("response_parsed", JSONB, nullable=True)
    validation_passed: Mapped[bool] = mapped_column("validation_passed", Boolean)
    validation_errors: Mapped[list[Any]] = mapped_column("validation_errors", JSONB, default=list)
    elapsed_ms: Mapped[int] = mapped_column("elapsed_ms", Integer)
    cost_usd: Mapped[Decimal] = mapped_column("cost_usd", Numeric(12, 6), default=Decimal(0))
    status: Mapped[str] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column("trace_id", String)
    causation_id: Mapped[str | None] = mapped_column("causation_id", String, nullable=True)
    producer_version: Mapped[str] = mapped_column("producer_version", String)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class DecisionMemoryRow(Base):
    """ART-DECISION-MEMORY — append-only (RFC-008)."""

    __tablename__ = "decision_memory"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_id: Mapped[str] = mapped_column("decision_id", String)
    instrument_id: Mapped[str] = mapped_column("instrument_id", String)
    account_id: Mapped[str | None] = mapped_column("account_id", String, nullable=True)
    outcome: Mapped[str] = mapped_column(String)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    policy_rule_ids: Mapped[list[Any]] = mapped_column("policy_rule_ids", JSONB, default=list)
    reevaluate_when: Mapped[list[Any]] = mapped_column("reevaluate_when", JSONB, default=list)
    opportunity_intact: Mapped[bool] = mapped_column("opportunity_intact", Boolean)
    policy_id: Mapped[str | None] = mapped_column("policy_id", String, nullable=True)
    policy_version: Mapped[str | None] = mapped_column("policy_version", String, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class DecisionSessionRow(Base):
    """ART-DECISION-SESSION — fotografía completa del razonamiento."""

    __tablename__ = "decision_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    instrument_id: Mapped[str] = mapped_column("instrument_id", String)
    account_id: Mapped[str | None] = mapped_column("account_id", String, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column("recommendation_id", String, nullable=True)
    decision_id: Mapped[str | None] = mapped_column("decision_id", String, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class ModelArtifactRow(Base):
    """ART-MODEL — registro cuantitativo (sin binario; payload JSON)."""

    __tablename__ = "model_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    model_id: Mapped[str] = mapped_column("model_id", String, unique=True)
    model_version: Mapped[str] = mapped_column("model_version", String)
    framework: Mapped[str] = mapped_column(String)
    feature_set_id: Mapped[str] = mapped_column("feature_set_id", String)
    composition_hash: Mapped[str | None] = mapped_column("composition_hash", String, nullable=True)
    model_checksum: Mapped[str | None] = mapped_column("model_checksum", String, nullable=True)
    trained_at: Mapped[datetime | None] = mapped_column("trained_at", DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class PredictionRow(Base):
    """ART-PREDICTION — append-only (no ordena)."""

    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", String)
    model_id: Mapped[str] = mapped_column("model_id", String)
    model_version: Mapped[str] = mapped_column("model_version", String)
    horizon: Mapped[str | None] = mapped_column(String, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    as_of: Mapped[datetime | None] = mapped_column("as_of", DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class TrialRecordRow(Base):
    """Trial / hipótesis — fila plana para TrialsLog (RFC-008)."""

    __tablename__ = "trial_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    log_id: Mapped[str] = mapped_column("log_id", String)
    strategy_family_ref: Mapped[str] = mapped_column("strategy_family_ref", String)
    hypothesis_ref: Mapped[str] = mapped_column("hypothesis_ref", String)
    params_hash: Mapped[str] = mapped_column("params_hash", String)
    sharpe_is: Mapped[Decimal | None] = mapped_column("sharpe_is", Numeric(12, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[str | None] = mapped_column("account_id", String, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class ConfidenceStateRow(Base):
    """ART-CONFIDENCE-STATE — mutable (RFC-008 D7)."""

    __tablename__ = "confidence_states"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_id: Mapped[str] = mapped_column("decision_id", String)
    instrument_id: Mapped[str] = mapped_column("instrument_id", String)
    account_id: Mapped[str | None] = mapped_column("account_id", String, nullable=True)
    confidence_0: Mapped[Decimal] = mapped_column("confidence_0", Numeric(8, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    hint: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime | None] = mapped_column("expires_at", DateTime(timezone=True), nullable=True)
    expired: Mapped[bool] = mapped_column(Boolean, default=False)
    events: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    notes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class EdgeReportRow(Base):
    """ART-EDGE-REPORT — append-only snapshot (RFC-008)."""

    __tablename__ = "edge_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[str] = mapped_column(String)
    strategy_or_signal_ref: Mapped[str] = mapped_column("strategy_or_signal_ref", String)
    instrument_universe_ref: Mapped[str | None] = mapped_column(
        "instrument_universe_ref", String, nullable=True
    )
    account_id: Mapped[str | None] = mapped_column("account_id", String, nullable=True)
    credibility: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    edge_score: Mapped[Decimal] = mapped_column("edge_score", Numeric(8, 2))
    band: Mapped[str] = mapped_column(String)
    suite: Mapped[dict[str, Any]] = mapped_column(JSONB)
    notes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class TrackerDefinitionRow(Base):
    __tablename__ = "tracker_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    strategy_definition_id: Mapped[str] = mapped_column(
        "strategy_definition_id",
        String,
        ForeignKey("strategy_definitions.id"),
    )
    strategy_version: Mapped[int | None] = mapped_column("strategy_version", Integer, nullable=True)
    timeframe: Mapped[str] = mapped_column(String, default="1d")
    evaluation_mode: Mapped[str] = mapped_column("evaluation_mode", String, default="bar_close")
    origin: Mapped[str] = mapped_column(String, default="manual")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[str | None] = mapped_column("user_id", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    strategy_definition: Mapped["StrategyDefinitionRow"] = relationship(
        back_populates="tracker_definitions",
    )
    scan_jobs: Mapped[list["ScanJobRow"]] = relationship(back_populates="tracker_definition")
    scan_manifests: Mapped[list["ScanManifestRow"]] = relationship(back_populates="tracker_definition")


class OptimizationRunRow(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine: Mapped[str | None] = mapped_column(String, nullable=True)
    best_score: Mapped[Decimal | None] = mapped_column(
        "best_score",
        Numeric(12, 4),
        nullable=True,
    )
    trial_count: Mapped[int | None] = mapped_column("trial_count", Integer, nullable=True)
    bar_count: Mapped[int | None] = mapped_column("bar_count", Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        "completed_at",
        DateTime(timezone=True),
        nullable=True,
    )

    instrument: Mapped[InstrumentRow] = relationship()
    research_trials: Mapped[list["ResearchTrialRow"]] = relationship(back_populates="optimization_run")


class HypothesisRow(Base):
    """Hypothesis — ADR-018 P2.A/B."""

    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, default="hypothesis")
    statement: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    falsifiers: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class HypothesisBeliefRow(Base):
    """Mutable Belief state — ADR-011 D13 / P2.C."""

    __tablename__ = "hypothesis_beliefs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(
        "hypothesis_id",
        ForeignKey("hypotheses.id", ondelete="CASCADE"),
        unique=True,
    )
    belief: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    belief_ci_low: Mapped[Decimal] = mapped_column("belief_ci_low", Numeric(8, 4))
    belief_ci_high: Mapped[Decimal] = mapped_column("belief_ci_high", Numeric(8, 4))
    n_experiments: Mapped[int] = mapped_column("n_experiments", Integer, default=0)
    evidence_weight: Mapped[Decimal] = mapped_column(
        "evidence_weight", Numeric(12, 4), default=Decimal(0)
    )
    contexts_ok: Mapped[list[Any]] = mapped_column("contexts_ok", JSONB, default=list)
    contexts_fail: Mapped[list[Any]] = mapped_column("contexts_fail", JSONB, default=list)
    evidence_ids: Mapped[list[Any]] = mapped_column("evidence_ids", JSONB, default=list)
    trial_ids: Mapped[list[Any]] = mapped_column("trial_ids", JSONB, default=list)
    math_version: Mapped[str] = mapped_column("math_version", String)
    last_reviewed_at: Mapped[datetime] = mapped_column(
        "last_reviewed_at", DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class KnowledgeNodeRow(Base):
    """Knowledge node — ADR-013 / P2.D (Consolidation explicit)."""

    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(
        "hypothesis_id",
        ForeignKey("hypotheses.id", ondelete="CASCADE"),
    )
    stage: Mapped[str] = mapped_column(String, default="EMERGING")
    statement: Mapped[str] = mapped_column(Text)
    knowledge_confidence: Mapped[Decimal] = mapped_column(
        "knowledge_confidence", Numeric(8, 4)
    )
    validity_context: Mapped[dict[str, Any]] = mapped_column(
        "validity_context", JSONB, default=dict
    )
    evidence_ids: Mapped[list[Any]] = mapped_column("evidence_ids", JSONB, default=list)
    belief_snapshot: Mapped[dict[str, Any]] = mapped_column("belief_snapshot", JSONB)
    consolidation_report: Mapped[dict[str, Any]] = mapped_column("consolidation_report", JSONB)
    math_version: Mapped[str] = mapped_column("math_version", String)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    consolidated_at: Mapped[datetime] = mapped_column(
        "consolidated_at", DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class ResearchTreeEdgeRow(Base):
    """Research Tree edge — ADR-011 D20 / P2.E."""

    __tablename__ = "research_tree_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    from_ref_type: Mapped[str] = mapped_column("from_ref_type", String)
    from_ref_id: Mapped[str] = mapped_column("from_ref_id", String)
    to_ref_type: Mapped[str] = mapped_column("to_ref_type", String)
    to_ref_id: Mapped[str] = mapped_column("to_ref_id", String)
    edge_type: Mapped[str] = mapped_column("edge_type", String)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        "deleted_at", DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class MklSyncEventRow(Base):
    """MKL sync stub log — RFC-008 / P2.F."""

    __tablename__ = "mkl_sync_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    knowledge_node_id: Mapped[str] = mapped_column(
        "knowledge_node_id",
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(String)
    fact_payload: Mapped[dict[str, Any]] = mapped_column("fact_payload", JSONB)
    math_version: Mapped[str] = mapped_column("math_version", String)
    notes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class BeliefHistoryRow(Base):
    """Append-only Belief snapshots — P2.C / L-T."""

    __tablename__ = "belief_history"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(
        "hypothesis_id",
        ForeignKey("hypotheses.id", ondelete="CASCADE"),
    )
    belief_id: Mapped[str] = mapped_column(
        "belief_id",
        ForeignKey("hypothesis_beliefs.id", ondelete="CASCADE"),
    )
    belief: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    belief_ci_low: Mapped[Decimal] = mapped_column("belief_ci_low", Numeric(8, 4))
    belief_ci_high: Mapped[Decimal] = mapped_column("belief_ci_high", Numeric(8, 4))
    n_experiments: Mapped[int] = mapped_column("n_experiments", Integer)
    evidence_weight: Mapped[Decimal] = mapped_column("evidence_weight", Numeric(12, 4))
    trigger_evidence_id: Mapped[str | None] = mapped_column(
        "trigger_evidence_id", String, nullable=True
    )
    delta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    math_version: Mapped[str] = mapped_column("math_version", String)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class ResearchEvidenceRow(Base):
    """Evidence snapshot append-only — ADR-018 P2.A / ADR-012 levels."""

    __tablename__ = "research_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    trial_id: Mapped[str | None] = mapped_column(
        "trial_id",
        ForeignKey("research_trials.id", ondelete="SET NULL"),
        nullable=True,
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        "hypothesis_id",
        ForeignKey("hypotheses.id", ondelete="SET NULL"),
        nullable=True,
    )
    edge_report_id: Mapped[str | None] = mapped_column("edge_report_id", String, nullable=True)
    level: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    evidence_weight: Mapped[Decimal] = mapped_column(
        "evidence_weight", Numeric(8, 4), default=Decimal(0)
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    math_version: Mapped[str | None] = mapped_column("math_version", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))


class ResearchTrialRow(Base):
    """QROS scientific ledger (K) — ADR-016. Distinct from trial_records (RFC-008)."""

    __tablename__ = "research_trials"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        "hypothesis_id",
        ForeignKey("hypotheses.id", ondelete="SET NULL"),
        nullable=True,
    )
    research_question_id: Mapped[str | None] = mapped_column(
        "research_question_id", String, nullable=True
    )
    backtest_run_id: Mapped[str | None] = mapped_column(
        "backtest_run_id",
        ForeignKey("backtest_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    optimization_run_id: Mapped[str | None] = mapped_column(
        "optimization_run_id",
        ForeignKey("optimization_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id",
        ForeignKey("strategy_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    preset_key: Mapped[str | None] = mapped_column("preset_key", String, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column("strategy_name", String, nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    blocks: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_metrics: Mapped[dict[str, Any]] = mapped_column("is_metrics", JSONB)
    is_score: Mapped[Decimal | None] = mapped_column("is_score", Numeric(18, 6), nullable=True)
    k_contribution: Mapped[int] = mapped_column("k_contribution", Integer, default=1)
    proposed_by: Mapped[str] = mapped_column("proposed_by", String)
    parent_trial_id: Mapped[str | None] = mapped_column(
        "parent_trial_id",
        ForeignKey("research_trials.id", ondelete="SET NULL"),
        nullable=True,
    )
    fail_code: Mapped[str | None] = mapped_column("fail_code", String, nullable=True)
    manifest_ref: Mapped[dict[str, Any] | None] = mapped_column("manifest_ref", JSONB, nullable=True)
    data_epoch: Mapped[str | None] = mapped_column("data_epoch", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship()
    backtest_run: Mapped[BacktestRunRow | None] = relationship(back_populates="research_trials")
    optimization_run: Mapped[OptimizationRunRow | None] = relationship(
        back_populates="research_trials",
    )
    strategy_definition: Mapped[StrategyDefinitionRow | None] = relationship(
        back_populates="research_trials",
    )


class WorkspaceRow(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column("user_id", String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dock_layout: Mapped[dict[str, Any] | None] = mapped_column("dock_layout", JSONB, nullable=True)
    is_default: Mapped[bool] = mapped_column("is_default", Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class SyncSettingsRow(Base):
    __tablename__ = "sync_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    auto_sync_enabled: Mapped[bool] = mapped_column("auto_sync_enabled", Boolean, default=True)
    scan_interval_minutes: Mapped[int] = mapped_column("scan_interval_minutes", Integer, default=30)
    min_delay_seconds: Mapped[int] = mapped_column("min_delay_seconds", Integer, default=3)
    post_market_only: Mapped[bool] = mapped_column("post_market_only", Boolean, default=False)
    max_retries: Mapped[int] = mapped_column("max_retries", Integer, default=5)
    retry_backoff_minutes: Mapped[int] = mapped_column("retry_backoff_minutes", Integer, default=45)
    scope: Mapped[str] = mapped_column(String, default="lists")
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class SyncQueueItemRow(Base):
    __tablename__ = "sync_queue"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String, default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_at: Mapped[datetime] = mapped_column("scheduled_at", DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column("last_error", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship()


class PendingOrderRow(Base):
    __tablename__ = "pending_orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str | None] = mapped_column(
        "account_id",
        ForeignKey("investment_accounts.id"),
        nullable=True,
    )
    instrument_id: Mapped[str] = mapped_column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)
    order_type: Mapped[str] = mapped_column("order_type", String, default="stop_limit")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    limit_price: Mapped[Decimal] = mapped_column("limit_price", Numeric(18, 6))
    expiry_at: Mapped[datetime | None] = mapped_column("expiry_at", DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    instrument: Mapped[InstrumentRow] = relationship()


class InvestorProfileRow(Base):
    """ART-PROFILE — catálogo (RFC-008)."""

    __tablename__ = "investor_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String, default="1.0.0")
    user_id: Mapped[str | None] = mapped_column("user_id", String, nullable=True)
    horizon: Mapped[str] = mapped_column(String)
    objectives: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    risk_tolerance: Mapped[str] = mapped_column("risk_tolerance", String)
    experience: Mapped[str] = mapped_column(String)
    max_acceptable_loss_pct: Mapped[Decimal | None] = mapped_column(
        "max_acceptable_loss_pct", Numeric(8, 4), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_policy_template_id: Mapped[str] = mapped_column(
        "suggested_policy_template_id", String
    )
    selected_policy_template_id: Mapped[str] = mapped_column(
        "selected_policy_template_id", String
    )
    observed_json: Mapped[dict[str, Any] | None] = mapped_column("observed_json", JSONB, nullable=True)
    updated_by: Mapped[str] = mapped_column("updated_by", String, default="user")
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    accounts: Mapped[list["InvestmentAccountRow"]] = relationship(back_populates="active_profile")


class InvestmentAccountRow(Base):
    __tablename__ = "investment_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column("user_id", String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="simulated")
    status: Mapped[str] = mapped_column(String, default="active")
    currency: Mapped[str] = mapped_column(String, default="EUR")
    base_currency: Mapped[str] = mapped_column("base_currency", String, default="EUR")
    initial_deposit: Mapped[Decimal] = mapped_column("initial_deposit", Numeric(18, 6), default=Decimal(100000))
    leverage: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal(1))
    margin_call_level_pct: Mapped[Decimal | None] = mapped_column(
        "margin_call_level_pct",
        Numeric(10, 4),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column("is_default", Boolean, default=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    settings_json: Mapped[dict[str, Any] | None] = mapped_column("settings_json", JSONB, nullable=True)
    active_profile_id: Mapped[str | None] = mapped_column(
        "active_profile_id",
        String,
        ForeignKey("investor_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id",
        ForeignKey("strategy_definitions.id"),
        nullable=True,
    )
    source_backtest_run_id: Mapped[str | None] = mapped_column(
        "source_backtest_run_id",
        String,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(
        "last_activity_at",
        DateTime(timezone=True),
        nullable=True,
    )

    active_profile: Mapped["InvestorProfileRow | None"] = relationship(
        back_populates="accounts",
    )
    portfolios: Mapped[list["InvestmentPortfolioRow"]] = relationship(back_populates="account")
    ledger_entries: Mapped[list["LedgerEntryRow"]] = relationship(back_populates="account")
    execution_policies: Mapped[list["ExecutionPolicyRow"]] = relationship(back_populates="account")
    position_policies: Mapped[list["PositionPolicyRow"]] = relationship(back_populates="account")


class InvestmentPortfolioRow(Base):
    __tablename__ = "investment_portfolios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column("account_id", ForeignKey("investment_accounts.id"))
    legacy_portfolio_id: Mapped[str | None] = mapped_column(
        "legacy_portfolio_id",
        ForeignKey("portfolios.id"),
        nullable=True,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    strategy_tag: Mapped[str | None] = mapped_column("strategy_tag", String, nullable=True)
    sort_order: Mapped[int] = mapped_column("sort_order", Integer, default=0)
    is_default: Mapped[bool] = mapped_column("is_default", Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))

    account: Mapped[InvestmentAccountRow] = relationship(back_populates="portfolios")
    legacy_portfolio: Mapped[PortfolioRow | None] = relationship()
    ledger_entries: Mapped[list["LedgerEntryRow"]] = relationship(back_populates="portfolio")


class LedgerEntryRow(Base):
    __tablename__ = "ledger_entries"
    # Fase 3 (L-M3/M-5): cierra la ventana de concurrency de la idempotencia A-2
    # (external) y A-1/M-7 (custody). Por-cuenta + type para no romper trade+fee
    # (misma cuenta/tx, type distinto) ni custodia/migration multi-cuenta. Parcial
    # para excluir filas con references NULL (seeds). Espejo de la migración
    # 004_ledger_reference_unique.
    __table_args__ = (
        Index(
            "uq_ledger_entries_account_reference",
            "account_id",
            "reference_type",
            "reference_id",
            "type",
            unique=True,
            postgresql_where=text(
                "reference_type IS NOT NULL AND reference_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column("account_id", ForeignKey("investment_accounts.id"))
    portfolio_id: Mapped[str | None] = mapped_column(
        "portfolio_id",
        ForeignKey("investment_portfolios.id"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String, default="EUR")
    balance_after: Mapped[Decimal] = mapped_column("balance_after", Numeric(18, 6))
    instrument_id: Mapped[str | None] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="SET NULL"),
        nullable=True,
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    reference_type: Mapped[str | None] = mapped_column("reference_type", String, nullable=True)
    reference_id: Mapped[str | None] = mapped_column("reference_id", String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    executed_at: Mapped[datetime] = mapped_column("executed_at", DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))

    account: Mapped[InvestmentAccountRow] = relationship(back_populates="ledger_entries")
    portfolio: Mapped[InvestmentPortfolioRow | None] = relationship(back_populates="ledger_entries")
    instrument: Mapped[InstrumentRow | None] = relationship()


class InstrumentStrategyTopRow(Base):
    """TOP-3 estrategias AT por instrumento (semifinal del embudo coach)."""

    __tablename__ = "instrument_strategy_tops"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    timeframe: Mapped[str] = mapped_column(String, default="1d")
    period_label: Mapped[str | None] = mapped_column("period_label", String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="semifinal")
    version: Mapped[int] = mapped_column(Integer, default=1)
    evidence_level: Mapped[str] = mapped_column("evidence_level", String, default="in_sample_only")
    slots: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    coach_headline: Mapped[str | None] = mapped_column("coach_headline", Text, nullable=True)
    coach_facts: Mapped[dict[str, Any] | None] = mapped_column("coach_facts", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class InstrumentDailyOpinionRow(Base):
    """Dictamen diario Estudio (O3-C / ADR-022)."""

    __tablename__ = "instrument_daily_opinions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    account_id: Mapped[str | None] = mapped_column("account_id", String, nullable=True)
    as_of_bar_date: Mapped[date] = mapped_column("as_of_bar_date", Date)
    stance: Mapped[str] = mapped_column(String)
    dictamen_stars: Mapped[int] = mapped_column("dictamen_stars", Integer)
    strategy_stars: Mapped[int | None] = mapped_column("strategy_stars", Integer, nullable=True)
    io_score: Mapped[float | None] = mapped_column("io_score", Float, nullable=True)
    fa_score: Mapped[float | None] = mapped_column("fa_score", Float, nullable=True)
    ta_score: Mapped[float | None] = mapped_column("ta_score", Float, nullable=True)
    distress: Mapped[bool] = mapped_column(Boolean, default=False)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    gate_status: Mapped[str | None] = mapped_column("gate_status", String, nullable=True)
    top_id: Mapped[str | None] = mapped_column("top_id", String, nullable=True)
    top_version: Mapped[int | None] = mapped_column("top_version", Integer, nullable=True)
    source: Mapped[str] = mapped_column(String, default="on_demand")
    engine_version: Mapped[str] = mapped_column("engine_version", String, default="opinion_v1")
    idempotency_key: Mapped[str] = mapped_column("idempotency_key", String, unique=True)
    computed_at: Mapped[datetime] = mapped_column("computed_at", DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class InstrumentNarrativeRow(Base):
    """Resumen corto de evolución por instrumento (scope estudio/global/trading)."""

    __tablename__ = "instrument_narratives"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    scope: Mapped[str] = mapped_column(String, default="estudio")
    body: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="user")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class MandateTenureRow(Base):
    """ADR-020 — tenure de mandato operativo por cuenta×instrumento."""

    __tablename__ = "mandate_tenures"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        "account_id",
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
    )
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    timeframe: Mapped[str | None] = mapped_column(String, nullable=True)
    strategy_definition_id: Mapped[str | None] = mapped_column(
        "strategy_definition_id", String, nullable=True
    )
    strategy_label_snapshot: Mapped[str | None] = mapped_column(
        "strategy_label_snapshot", String, nullable=True
    )
    effective_from: Mapped[datetime] = mapped_column("effective_from", DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(
        "effective_to", DateTime(timezone=True), nullable=True
    )
    actor: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    source_top_id: Mapped[str | None] = mapped_column("source_top_id", String, nullable=True)
    source_top_version: Mapped[int | None] = mapped_column(
        "source_top_version", Integer, nullable=True
    )
    evidence_level: Mapped[str | None] = mapped_column("evidence_level", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=True))


class MandateTradeLinkRow(Base):
    """ADR-020 — enlace fill DEMO → tenure de mandato."""

    __tablename__ = "mandate_trade_links"

    transaction_id: Mapped[str] = mapped_column("transaction_id", String, primary_key=True)
    mandate_tenure_id: Mapped[str] = mapped_column(
        "mandate_tenure_id",
        ForeignKey("mandate_tenures.id", ondelete="CASCADE"),
    )
    instrument_id: Mapped[str] = mapped_column(
        "instrument_id",
        ForeignKey("instruments.id", ondelete="CASCADE"),
    )
    account_id: Mapped[str] = mapped_column(
        "account_id",
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
    )
    linked_at: Mapped[datetime] = mapped_column("linked_at", DateTime(timezone=True))
    engine: Mapped[str] = mapped_column(String, default="mandate-trade-links-v1")


class CoreRAccountStateRow(Base):
    """Q3.4 — blob CORE-R (queue/reports/scheduler) por cuenta."""

    __tablename__ = "core_r_account_state"

    account_id: Mapped[str] = mapped_column(
        "account_id",
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    queue_json: Mapped[list[Any]] = mapped_column("queue_json", JSONB, default=list)
    reports_json: Mapped[dict[str, Any]] = mapped_column("reports_json", JSONB, default=dict)
    scheduler_json: Mapped[dict[str, Any]] = mapped_column("scheduler_json", JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), default=lambda: datetime.now(tz=UTC)
    )


class SupervisedF3AccountStateRow(Base):
    """SEMI Confirm F3 — blob cola supervisada por cuenta."""

    __tablename__ = "supervised_f3_account_state"

    account_id: Mapped[str] = mapped_column(
        "account_id",
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    queue_json: Mapped[list[Any]] = mapped_column("queue_json", JSONB, default=list)
    active_id: Mapped[str | None] = mapped_column("active_id", String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), default=lambda: datetime.now(tz=UTC)
    )


class CustodyObligationRow(Base):
    """MULTI-periodo (R-11 C1 / R-10.6) — obligaciones de custodia por (cuenta, año).

    Fuente de verdad de la deuda de custodia. PK ``id`` autoincremental +
    ``UNIQUE(account_id, period)``: UNA fila por (cuenta, año). Un PENDING de 2026
    permanece representado aunque llegue 2027 (no se sobrescribe). ``status`` solo
    ``PENDING`` | ``APPLIED``; ``outstanding`` = importe pendiente; ``total_fee`` =
    importe total original.

    La tabla obsoleta ``custody_obligation`` (005, PK ``account_id``, una fila por
    cuenta) ya NO se usa.
    """

    __tablename__ = "custody_obligations"

    id: Mapped[int] = mapped_column("id", Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        "account_id",
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
    )
    period: Mapped[str] = mapped_column("period", String)
    status: Mapped[str] = mapped_column("status", String)
    outstanding: Mapped[Decimal] = mapped_column("outstanding", Numeric(18, 6))
    total_fee: Mapped[Decimal] = mapped_column("total_fee", Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), default=lambda: datetime.now(tz=UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), default=lambda: datetime.now(tz=UTC)
    )

    __table_args__ = (
        UniqueConstraint("account_id", "period", name="uq_custody_obligations_account_period"),
    )


class UserRow(Base):
    """Usuario autenticado (R12-AUTH F5 / ADR-027)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    login: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column("password_hash", String, nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    session_version: Mapped[int] = mapped_column(
        "session_version", Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(
        "disabled_at", DateTime(timezone=True), nullable=True
    )
