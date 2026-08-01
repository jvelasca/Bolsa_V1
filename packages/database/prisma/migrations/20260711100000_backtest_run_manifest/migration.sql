-- BT-1: manifest, data version hash, execution params (H0 research platform)
ALTER TABLE "backtest_runs" ADD COLUMN IF NOT EXISTS "timeframe" TEXT NOT NULL DEFAULT '1d';
ALTER TABLE "backtest_runs" ADD COLUMN IF NOT EXISTS "data_version" TEXT;
ALTER TABLE "backtest_runs" ADD COLUMN IF NOT EXISTS "commission_bps" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "backtest_runs" ADD COLUMN IF NOT EXISTS "slippage_bps" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "backtest_runs" ADD COLUMN IF NOT EXISTS "manifest" JSONB;
