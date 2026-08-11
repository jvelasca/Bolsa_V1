"""schema baseline del runtime completo (Prisma takeover) — D2/F3a. Generado por `dump_alembic_prisma_baseline`. NO editar a mano; regenerar.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from bolsa_infrastructure.database.models import Base

revision = "003_prisma_schema_baseline"
down_revision = "002_research_data_epoch"
branch_labels = None
depends_on = None


def _type_exists(bind, name: str) -> bool:
    return bind.scalar(sa.text("SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = :n AND n.nspname = 'public'"), {'n': name}) is not None


def upgrade() -> None:
    bind = op.get_bind()

    # ---- PostgreSQL enum types (nombre EXACTO, quoted: Prisma crea enum en Mayúscula) ----
    if not _type_exists(bind, "InstrumentType"):
        op.execute('CREATE TYPE "InstrumentType" AS ENUM (\'stock\')')
    if not _type_exists(bind, "BacktestStrategyType"):
        op.execute('CREATE TYPE "BacktestStrategyType" AS ENUM (\'sma_crossover\', \'rsi_mean_reversion\', \'ema_crossover\', \'golden_cross\', \'death_cross\', \'macd_signal_cross\', \'macd_zero_line\', \'rsi_momentum\', \'rsi_oversold_bounce\', \'stoch_oversold\', \'bollinger_lower_bounce\', \'bollinger_upper_breakout\', \'price_above_sma200\', \'ma_stack_bullish\', \'pullback_in_uptrend\', \'cci_oversold\', \'donchian_breakout\', \'adx_di_trend\', \'ichimoku_tk_cross\', \'vwap_reclaim\', \'supertrend_follow\')')
    if not _type_exists(bind, "DataProvider"):
        op.execute('CREATE TYPE "DataProvider" AS ENUM (\'yahoo\', \'xtb\')')
    if not _type_exists(bind, "SyncStatus"):
        op.execute('CREATE TYPE "SyncStatus" AS ENUM (\'success\', \'partial\', \'failed\')')
    if not _type_exists(bind, "Timeframe"):
        op.execute('CREATE TYPE "Timeframe" AS ENUM (\'1m\', \'5m\', \'15m\', \'30m\', \'1h\', \'4h\', \'1d\', \'1wk\', \'1mo\')')
    if not _type_exists(bind, "AlertCondition"):
        op.execute('CREATE TYPE "AlertCondition" AS ENUM (\'above\', \'below\')')
    if not _type_exists(bind, "AlertPriceSource"):
        op.execute('CREATE TYPE "AlertPriceSource" AS ENUM (\'daily_close\', \'xtb_last\')')
    if not _type_exists(bind, "TransactionType"):
        op.execute('CREATE TYPE "TransactionType" AS ENUM (\'buy\', \'sell\')')

    # ---- tablas (orden topológico -> FKs referencian tipos ya creados) ----
    op.create_table(
        "confidence_states",
        *Base.metadata.tables["confidence_states"].columns.values(),
        *(c for c in Base.metadata.tables["confidence_states"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "decision_memory",
        *Base.metadata.tables["decision_memory"].columns.values(),
        *(c for c in Base.metadata.tables["decision_memory"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "decision_sessions",
        *Base.metadata.tables["decision_sessions"].columns.values(),
        *(c for c in Base.metadata.tables["decision_sessions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "edge_reports",
        *Base.metadata.tables["edge_reports"].columns.values(),
        *(c for c in Base.metadata.tables["edge_reports"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "hypotheses",
        *Base.metadata.tables["hypotheses"].columns.values(),
        *(c for c in Base.metadata.tables["hypotheses"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "index_subscribe_jobs",
        *Base.metadata.tables["index_subscribe_jobs"].columns.values(),
        *(c for c in Base.metadata.tables["index_subscribe_jobs"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "instrument_lists",
        *Base.metadata.tables["instrument_lists"].columns.values(),
        *(c for c in Base.metadata.tables["instrument_lists"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "instruments",
        *Base.metadata.tables["instruments"].columns.values(),
        *(c for c in Base.metadata.tables["instruments"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "investor_profiles",
        *Base.metadata.tables["investor_profiles"].columns.values(),
        *(c for c in Base.metadata.tables["investor_profiles"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "llm_calls",
        *Base.metadata.tables["llm_calls"].columns.values(),
        *(c for c in Base.metadata.tables["llm_calls"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "model_artifacts",
        *Base.metadata.tables["model_artifacts"].columns.values(),
        *(c for c in Base.metadata.tables["model_artifacts"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "platform_events",
        *Base.metadata.tables["platform_events"].columns.values(),
        *(c for c in Base.metadata.tables["platform_events"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "portfolios",
        *Base.metadata.tables["portfolios"].columns.values(),
        *(c for c in Base.metadata.tables["portfolios"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "predictions",
        *Base.metadata.tables["predictions"].columns.values(),
        *(c for c in Base.metadata.tables["predictions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "research_tree_edges",
        *Base.metadata.tables["research_tree_edges"].columns.values(),
        *(c for c in Base.metadata.tables["research_tree_edges"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "strategy_definitions",
        *Base.metadata.tables["strategy_definitions"].columns.values(),
        *(c for c in Base.metadata.tables["strategy_definitions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "sync_settings",
        *Base.metadata.tables["sync_settings"].columns.values(),
        *(c for c in Base.metadata.tables["sync_settings"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "trial_records",
        *Base.metadata.tables["trial_records"].columns.values(),
        *(c for c in Base.metadata.tables["trial_records"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "workspaces",
        *Base.metadata.tables["workspaces"].columns.values(),
        *(c for c in Base.metadata.tables["workspaces"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "backtest_runs",
        *Base.metadata.tables["backtest_runs"].columns.values(),
        *(c for c in Base.metadata.tables["backtest_runs"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "data_snapshots",
        *Base.metadata.tables["data_snapshots"].columns.values(),
        *(c for c in Base.metadata.tables["data_snapshots"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "data_sync_log",
        *Base.metadata.tables["data_sync_log"].columns.values(),
        *(c for c in Base.metadata.tables["data_sync_log"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "hypothesis_beliefs",
        *Base.metadata.tables["hypothesis_beliefs"].columns.values(),
        *(c for c in Base.metadata.tables["hypothesis_beliefs"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "instrument_daily_opinions",
        *Base.metadata.tables["instrument_daily_opinions"].columns.values(),
        *(c for c in Base.metadata.tables["instrument_daily_opinions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "instrument_list_items",
        *Base.metadata.tables["instrument_list_items"].columns.values(),
        *(c for c in Base.metadata.tables["instrument_list_items"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "instrument_narratives",
        *Base.metadata.tables["instrument_narratives"].columns.values(),
        *(c for c in Base.metadata.tables["instrument_narratives"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "instrument_strategy_tops",
        *Base.metadata.tables["instrument_strategy_tops"].columns.values(),
        *(c for c in Base.metadata.tables["instrument_strategy_tops"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "investment_accounts",
        *Base.metadata.tables["investment_accounts"].columns.values(),
        *(c for c in Base.metadata.tables["investment_accounts"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "knowledge_nodes",
        *Base.metadata.tables["knowledge_nodes"].columns.values(),
        *(c for c in Base.metadata.tables["knowledge_nodes"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "ohlcv_bars",
        *Base.metadata.tables["ohlcv_bars"].columns.values(),
        *(c for c in Base.metadata.tables["ohlcv_bars"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "optimization_runs",
        *Base.metadata.tables["optimization_runs"].columns.values(),
        *(c for c in Base.metadata.tables["optimization_runs"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "positions",
        *Base.metadata.tables["positions"].columns.values(),
        *(c for c in Base.metadata.tables["positions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "price_alerts",
        *Base.metadata.tables["price_alerts"].columns.values(),
        *(c for c in Base.metadata.tables["price_alerts"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "signal_alert_subscriptions",
        *Base.metadata.tables["signal_alert_subscriptions"].columns.values(),
        *(c for c in Base.metadata.tables["signal_alert_subscriptions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "sync_queue",
        *Base.metadata.tables["sync_queue"].columns.values(),
        *(c for c in Base.metadata.tables["sync_queue"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "tracker_definitions",
        *Base.metadata.tables["tracker_definitions"].columns.values(),
        *(c for c in Base.metadata.tables["tracker_definitions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "transactions",
        *Base.metadata.tables["transactions"].columns.values(),
        *(c for c in Base.metadata.tables["transactions"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "backtest_trades",
        *Base.metadata.tables["backtest_trades"].columns.values(),
        *(c for c in Base.metadata.tables["backtest_trades"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "belief_history",
        *Base.metadata.tables["belief_history"].columns.values(),
        *(c for c in Base.metadata.tables["belief_history"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "core_r_account_state",
        *Base.metadata.tables["core_r_account_state"].columns.values(),
        *(c for c in Base.metadata.tables["core_r_account_state"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "execution_policies",
        *Base.metadata.tables["execution_policies"].columns.values(),
        *(c for c in Base.metadata.tables["execution_policies"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "investment_portfolios",
        *Base.metadata.tables["investment_portfolios"].columns.values(),
        *(c for c in Base.metadata.tables["investment_portfolios"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "mandate_tenures",
        *Base.metadata.tables["mandate_tenures"].columns.values(),
        *(c for c in Base.metadata.tables["mandate_tenures"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "mkl_sync_events",
        *Base.metadata.tables["mkl_sync_events"].columns.values(),
        *(c for c in Base.metadata.tables["mkl_sync_events"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "pending_orders",
        *Base.metadata.tables["pending_orders"].columns.values(),
        *(c for c in Base.metadata.tables["pending_orders"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "research_trials",
        *Base.metadata.tables["research_trials"].columns.values(),
        *(c for c in Base.metadata.tables["research_trials"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "scan_jobs",
        *Base.metadata.tables["scan_jobs"].columns.values(),
        *(c for c in Base.metadata.tables["scan_jobs"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "supervised_f3_account_state",
        *Base.metadata.tables["supervised_f3_account_state"].columns.values(),
        *(c for c in Base.metadata.tables["supervised_f3_account_state"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "ledger_entries",
        *Base.metadata.tables["ledger_entries"].columns.values(),
        *(c for c in Base.metadata.tables["ledger_entries"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "mandate_trade_links",
        *Base.metadata.tables["mandate_trade_links"].columns.values(),
        *(c for c in Base.metadata.tables["mandate_trade_links"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "position_policies",
        *Base.metadata.tables["position_policies"].columns.values(),
        *(c for c in Base.metadata.tables["position_policies"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "research_evidence",
        *Base.metadata.tables["research_evidence"].columns.values(),
        *(c for c in Base.metadata.tables["research_evidence"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )
    op.create_table(
        "scan_manifests",
        *Base.metadata.tables["scan_manifests"].columns.values(),
        *(c for c in Base.metadata.tables["scan_manifests"].constraints if isinstance(c, sa.ForeignKeyConstraint) or (isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns))),
        if_not_exists=True,
    )

    # ---- (sin Index separados; PK de columnas, FK/Unique pasados arriba) ----

def downgrade() -> None:
    # Takeover de esquema: sobre la BD de Prisma el upgrade es no-op, por lo que
    # un downgrade destructivo (drop de tablas) NO se emite para no borrar datos
    # de produccion. En una BD limpia el schema se recrea via seed/ciclo normal.
    return
