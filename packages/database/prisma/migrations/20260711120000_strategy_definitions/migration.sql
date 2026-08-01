-- BT-2: estrategias guardadas (StrategyDefinitionV1)
CREATE TABLE IF NOT EXISTS "strategy_definitions" (
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "definition" JSONB NOT NULL,
  "preset_key" TEXT,
  "origin" TEXT NOT NULL DEFAULT 'manual',
  "timeframe" TEXT NOT NULL DEFAULT '1d',
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "strategy_definitions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "strategy_definitions_updated_at_idx"
  ON "strategy_definitions" ("updated_at" DESC);

ALTER TABLE "backtest_runs" ADD COLUMN IF NOT EXISTS "strategy_definition_id" TEXT;

ALTER TABLE "backtest_runs"
  DROP CONSTRAINT IF EXISTS "backtest_runs_strategy_definition_id_fkey";

ALTER TABLE "backtest_runs"
  ADD CONSTRAINT "backtest_runs_strategy_definition_id_fkey"
  FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
