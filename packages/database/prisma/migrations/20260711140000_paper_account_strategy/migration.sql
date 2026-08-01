-- BT-7: paper account ← strategy bridge
ALTER TABLE "investment_accounts"
  ADD COLUMN IF NOT EXISTS "strategy_definition_id" TEXT,
  ADD COLUMN IF NOT EXISTS "source_backtest_run_id" TEXT;

CREATE INDEX IF NOT EXISTS "investment_accounts_type_idx" ON "investment_accounts"("type");
CREATE INDEX IF NOT EXISTS "investment_accounts_strategy_definition_id_idx"
  ON "investment_accounts"("strategy_definition_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'investment_accounts_strategy_definition_id_fkey'
  ) THEN
    ALTER TABLE "investment_accounts"
      ADD CONSTRAINT "investment_accounts_strategy_definition_id_fkey"
      FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
