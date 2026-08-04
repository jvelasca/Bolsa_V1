-- Dictamen diario Estudio (O3-C / ADR-022)

CREATE TABLE IF NOT EXISTS "instrument_daily_opinions" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "account_id" TEXT,
  "as_of_bar_date" DATE NOT NULL,
  "stance" TEXT NOT NULL,
  "dictamen_stars" INTEGER NOT NULL,
  "strategy_stars" INTEGER,
  "io_score" DOUBLE PRECISION,
  "fa_score" DOUBLE PRECISION,
  "ta_score" DOUBLE PRECISION,
  "distress" BOOLEAN NOT NULL DEFAULT false,
  "reasons" JSONB NOT NULL DEFAULT '[]',
  "gate_status" TEXT,
  "top_id" TEXT,
  "top_version" INTEGER,
  "source" TEXT NOT NULL DEFAULT 'on_demand',
  "engine_version" TEXT NOT NULL DEFAULT 'opinion_v1',
  "idempotency_key" TEXT NOT NULL,
  "computed_at" TIMESTAMPTZ(3) NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "instrument_daily_opinions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "instrument_daily_opinions_idempotency_key_key"
  ON "instrument_daily_opinions"("idempotency_key");

CREATE UNIQUE INDEX IF NOT EXISTS "instrument_daily_opinions_instrument_id_as_of_bar_date_source_key"
  ON "instrument_daily_opinions"("instrument_id", "as_of_bar_date", "source");

CREATE INDEX IF NOT EXISTS "instrument_daily_opinions_instrument_id_as_of_bar_date_idx"
  ON "instrument_daily_opinions"("instrument_id", "as_of_bar_date");

CREATE INDEX IF NOT EXISTS "instrument_daily_opinions_stance_as_of_bar_date_idx"
  ON "instrument_daily_opinions"("stance", "as_of_bar_date");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'instrument_daily_opinions_instrument_id_fkey'
  ) THEN
    ALTER TABLE "instrument_daily_opinions"
      ADD CONSTRAINT "instrument_daily_opinions_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
