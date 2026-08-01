-- ADR-016 Fase 1: research_trials (QROS ledger K; ≠ trial_records cognitivo)
CREATE TABLE IF NOT EXISTS "research_trials" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "hypothesis_id" TEXT,
  "research_question_id" TEXT,
  "backtest_run_id" TEXT,
  "optimization_run_id" TEXT,
  "strategy_definition_id" TEXT,
  "preset_key" TEXT,
  "strategy_name" TEXT,
  "params" JSONB NOT NULL,
  "blocks" JSONB,
  "is_metrics" JSONB NOT NULL,
  "is_score" DECIMAL(18,6),
  "k_contribution" INTEGER NOT NULL DEFAULT 1,
  "proposed_by" TEXT NOT NULL,
  "parent_trial_id" TEXT,
  "fail_code" TEXT,
  "manifest_ref" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "research_trials_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "research_trials_instrument_id_created_at_idx"
  ON "research_trials"("instrument_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "research_trials_hypothesis_id_idx"
  ON "research_trials"("hypothesis_id");

CREATE INDEX IF NOT EXISTS "research_trials_backtest_run_id_idx"
  ON "research_trials"("backtest_run_id");

CREATE INDEX IF NOT EXISTS "research_trials_optimization_run_id_idx"
  ON "research_trials"("optimization_run_id");

CREATE INDEX IF NOT EXISTS "research_trials_proposed_by_created_at_idx"
  ON "research_trials"("proposed_by", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_trials_instrument_id_fkey'
  ) THEN
    ALTER TABLE "research_trials"
      ADD CONSTRAINT "research_trials_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_trials_backtest_run_id_fkey'
  ) THEN
    ALTER TABLE "research_trials"
      ADD CONSTRAINT "research_trials_backtest_run_id_fkey"
      FOREIGN KEY ("backtest_run_id") REFERENCES "backtest_runs"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_trials_optimization_run_id_fkey'
  ) THEN
    ALTER TABLE "research_trials"
      ADD CONSTRAINT "research_trials_optimization_run_id_fkey"
      FOREIGN KEY ("optimization_run_id") REFERENCES "optimization_runs"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_trials_strategy_definition_id_fkey'
  ) THEN
    ALTER TABLE "research_trials"
      ADD CONSTRAINT "research_trials_strategy_definition_id_fkey"
      FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_trials_parent_trial_id_fkey'
  ) THEN
    ALTER TABLE "research_trials"
      ADD CONSTRAINT "research_trials_parent_trial_id_fkey"
      FOREIGN KEY ("parent_trial_id") REFERENCES "research_trials"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
