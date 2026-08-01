-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "public"."AlertCondition" AS ENUM ('above', 'below');

-- CreateEnum
CREATE TYPE "public"."AlertPriceSource" AS ENUM ('daily_close', 'xtb_last');

-- CreateEnum
CREATE TYPE "public"."BacktestStrategyType" AS ENUM ('sma_crossover', 'rsi_mean_reversion');

-- CreateEnum
CREATE TYPE "public"."DataProvider" AS ENUM ('yahoo', 'xtb');

-- CreateEnum
CREATE TYPE "public"."InstrumentType" AS ENUM ('stock');

-- CreateEnum
CREATE TYPE "public"."SyncStatus" AS ENUM ('success', 'partial', 'failed');

-- CreateEnum
CREATE TYPE "public"."Timeframe" AS ENUM ('1m', '5m', '15m', '1h', '1d');

-- CreateEnum
CREATE TYPE "public"."TransactionType" AS ENUM ('buy', 'sell');

-- CreateTable
CREATE TABLE "public"."backtest_runs" (
    "id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "strategy_type" "public"."BacktestStrategyType" NOT NULL,
    "initial_cash" DECIMAL(18,6) NOT NULL,
    "final_equity" DECIMAL(18,6) NOT NULL,
    "total_return_pct" DECIMAL(10,4) NOT NULL,
    "max_drawdown_pct" DECIMAL(10,4) NOT NULL,
    "trade_count" INTEGER NOT NULL,
    "win_count" INTEGER NOT NULL,
    "bar_count" INTEGER NOT NULL,
    "first_date" DATE NOT NULL,
    "last_date" DATE NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "backtest_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."backtest_trades" (
    "id" TEXT NOT NULL,
    "backtest_run_id" TEXT NOT NULL,
    "type" "public"."TransactionType" NOT NULL,
    "timestamp" DATE NOT NULL,
    "price" DECIMAL(18,6) NOT NULL,
    "quantity" DECIMAL(18,6) NOT NULL,
    "equity_after" DECIMAL(18,6) NOT NULL,

    CONSTRAINT "backtest_trades_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."data_sync_log" (
    "id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "provider" "public"."DataProvider" NOT NULL,
    "status" "public"."SyncStatus" NOT NULL,
    "bars_added" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "synced_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "data_sync_log_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."instrument_list_items" (
    "id" TEXT NOT NULL,
    "list_id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "sort_order" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "instrument_list_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."instrument_lists" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'custom',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "instrument_lists_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."instruments" (
    "id" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "yahoo_symbol" TEXT NOT NULL,
    "isin" TEXT,
    "name" TEXT NOT NULL,
    "exchange" TEXT NOT NULL,
    "country" TEXT NOT NULL DEFAULT 'ES',
    "currency" TEXT NOT NULL DEFAULT 'EUR',
    "sector" TEXT,
    "type" "public"."InstrumentType" NOT NULL DEFAULT 'stock',
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "instruments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."ohlcv_bars" (
    "id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "timeframe" "public"."Timeframe" NOT NULL DEFAULT '1d',
    "timestamp" DATE NOT NULL,
    "open" DECIMAL(18,6) NOT NULL,
    "high" DECIMAL(18,6) NOT NULL,
    "low" DECIMAL(18,6) NOT NULL,
    "close" DECIMAL(18,6) NOT NULL,
    "volume" BIGINT NOT NULL,
    "adj_close" DECIMAL(18,6),
    "source" "public"."DataProvider" NOT NULL DEFAULT 'yahoo',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ohlcv_bars_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."pending_orders" (
    "id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "side" TEXT NOT NULL,
    "order_type" TEXT NOT NULL DEFAULT 'stop_limit',
    "quantity" DECIMAL(18,6) NOT NULL,
    "limit_price" DECIMAL(18,6) NOT NULL,
    "expiry_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "pending_orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."portfolios" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL DEFAULT 'Cartera principal',
    "currency" TEXT NOT NULL DEFAULT 'EUR',
    "cash" DECIMAL(18,6) NOT NULL DEFAULT 100000,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "portfolios_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."positions" (
    "id" TEXT NOT NULL,
    "portfolio_id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "quantity" DECIMAL(18,6) NOT NULL,
    "avg_cost" DECIMAL(18,6) NOT NULL,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "positions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."price_alerts" (
    "id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "condition" "public"."AlertCondition" NOT NULL,
    "target_price" DECIMAL(18,6) NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "triggered_at" TIMESTAMP(3),
    "triggered_price" DECIMAL(18,6),
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "price_source" "public"."AlertPriceSource" NOT NULL DEFAULT 'daily_close',

    CONSTRAINT "price_alerts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."sync_queue" (
    "id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "priority" INTEGER NOT NULL DEFAULT 0,
    "scheduled_at" TIMESTAMP(3) NOT NULL,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "last_error" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sync_queue_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."sync_settings" (
    "id" TEXT NOT NULL DEFAULT 'default',
    "auto_sync_enabled" BOOLEAN NOT NULL DEFAULT true,
    "scan_interval_minutes" INTEGER NOT NULL DEFAULT 30,
    "min_delay_seconds" INTEGER NOT NULL DEFAULT 3,
    "post_market_only" BOOLEAN NOT NULL DEFAULT false,
    "max_retries" INTEGER NOT NULL DEFAULT 5,
    "retry_backoff_minutes" INTEGER NOT NULL DEFAULT 45,
    "scope" TEXT NOT NULL DEFAULT 'stale',
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sync_settings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."transactions" (
    "id" TEXT NOT NULL,
    "portfolio_id" TEXT NOT NULL,
    "instrument_id" TEXT NOT NULL,
    "type" "public"."TransactionType" NOT NULL,
    "quantity" DECIMAL(18,6) NOT NULL,
    "price" DECIMAL(18,6) NOT NULL,
    "total" DECIMAL(18,6) NOT NULL,
    "executed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "transactions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."workspaces" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "document" JSONB NOT NULL,
    "dock_layout" JSONB,
    "is_default" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "workspaces_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "backtest_runs_instrument_id_created_at_idx" ON "public"."backtest_runs"("instrument_id" ASC, "created_at" DESC);

-- CreateIndex
CREATE INDEX "backtest_trades_backtest_run_id_timestamp_idx" ON "public"."backtest_trades"("backtest_run_id" ASC, "timestamp" ASC);

-- CreateIndex
CREATE INDEX "data_sync_log_instrument_id_synced_at_idx" ON "public"."data_sync_log"("instrument_id" ASC, "synced_at" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "instrument_list_items_list_id_instrument_id_key" ON "public"."instrument_list_items"("list_id" ASC, "instrument_id" ASC);

-- CreateIndex
CREATE INDEX "instrument_list_items_list_id_sort_order_idx" ON "public"."instrument_list_items"("list_id" ASC, "sort_order" ASC);

-- CreateIndex
CREATE INDEX "instruments_exchange_idx" ON "public"."instruments"("exchange" ASC);

-- CreateIndex
CREATE INDEX "instruments_is_active_idx" ON "public"."instruments"("is_active" ASC);

-- CreateIndex
CREATE UNIQUE INDEX "instruments_symbol_exchange_key" ON "public"."instruments"("symbol" ASC, "exchange" ASC);

-- CreateIndex
CREATE UNIQUE INDEX "instruments_yahoo_symbol_key" ON "public"."instruments"("yahoo_symbol" ASC);

-- CreateIndex
CREATE INDEX "ohlcv_bars_instrument_id_timeframe_timestamp_idx" ON "public"."ohlcv_bars"("instrument_id" ASC, "timeframe" ASC, "timestamp" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "ohlcv_bars_instrument_id_timeframe_timestamp_key" ON "public"."ohlcv_bars"("instrument_id" ASC, "timeframe" ASC, "timestamp" ASC);

-- CreateIndex
CREATE INDEX "pending_orders_created_at_idx" ON "public"."pending_orders"("created_at" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "positions_portfolio_id_instrument_id_key" ON "public"."positions"("portfolio_id" ASC, "instrument_id" ASC);

-- CreateIndex
CREATE INDEX "price_alerts_is_active_created_at_idx" ON "public"."price_alerts"("is_active" ASC, "created_at" DESC);

-- CreateIndex
CREATE INDEX "sync_queue_instrument_id_status_idx" ON "public"."sync_queue"("instrument_id" ASC, "status" ASC);

-- CreateIndex
CREATE INDEX "sync_queue_status_scheduled_at_idx" ON "public"."sync_queue"("status" ASC, "scheduled_at" ASC);

-- CreateIndex
CREATE INDEX "transactions_portfolio_id_executed_at_idx" ON "public"."transactions"("portfolio_id" ASC, "executed_at" DESC);

-- CreateIndex
CREATE INDEX "workspaces_is_default_idx" ON "public"."workspaces"("is_default" ASC);

-- AddForeignKey
ALTER TABLE "public"."backtest_runs" ADD CONSTRAINT "backtest_runs_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."backtest_trades" ADD CONSTRAINT "backtest_trades_backtest_run_id_fkey" FOREIGN KEY ("backtest_run_id") REFERENCES "public"."backtest_runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."data_sync_log" ADD CONSTRAINT "data_sync_log_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."instrument_list_items" ADD CONSTRAINT "instrument_list_items_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."instrument_list_items" ADD CONSTRAINT "instrument_list_items_list_id_fkey" FOREIGN KEY ("list_id") REFERENCES "public"."instrument_lists"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."ohlcv_bars" ADD CONSTRAINT "ohlcv_bars_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."pending_orders" ADD CONSTRAINT "pending_orders_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."positions" ADD CONSTRAINT "positions_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."positions" ADD CONSTRAINT "positions_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."price_alerts" ADD CONSTRAINT "price_alerts_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."sync_queue" ADD CONSTRAINT "sync_queue_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."transactions" ADD CONSTRAINT "transactions_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."transactions" ADD CONSTRAINT "transactions_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE CASCADE ON UPDATE CASCADE;

