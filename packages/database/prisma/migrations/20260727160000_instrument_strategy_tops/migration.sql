-- Embudo coach: TOP-3 estrategias AT por instrumento (semifinal)

CREATE TABLE IF NOT EXISTS "instrument_strategy_tops" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "symbol" TEXT,
  "timeframe" TEXT NOT NULL DEFAULT '1d',
  "period_label" TEXT,
  "status" TEXT NOT NULL DEFAULT 'semifinal',
  "version" INTEGER NOT NULL DEFAULT 1,
  "evidence_level" TEXT NOT NULL DEFAULT 'in_sample_only',
  "slots" JSONB NOT NULL DEFAULT '[]',
  "coach_headline" TEXT,
  "coach_facts" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "instrument_strategy_tops_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "instrument_strategy_tops_instrument_timeframe_uq"
  ON "instrument_strategy_tops"("instrument_id", "timeframe");

CREATE INDEX IF NOT EXISTS "instrument_strategy_tops_instrument_updated_idx"
  ON "instrument_strategy_tops"("instrument_id", "updated_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'instrument_strategy_tops_instrument_id_fkey'
  ) THEN
    ALTER TABLE "instrument_strategy_tops"
      ADD CONSTRAINT "instrument_strategy_tops_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
