-- RD-3b: optimization_runs (histórico + cola async)
CREATE TABLE IF NOT EXISTS "optimization_runs" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "symbol" TEXT NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'pending',
  "payload" JSONB NOT NULL,
  "result" JSONB,
  "error" TEXT,
  "engine" TEXT,
  "best_score" DECIMAL(12,4),
  "trial_count" INTEGER,
  "bar_count" INTEGER,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completed_at" TIMESTAMPTZ(3),
  CONSTRAINT "optimization_runs_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "optimization_runs_status_created_at_idx"
  ON "optimization_runs"("status", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'optimization_runs_instrument_id_fkey'
  ) THEN
    ALTER TABLE "optimization_runs"
      ADD CONSTRAINT "optimization_runs_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
