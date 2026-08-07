-- Narrativa corta de evolución por instrumento (alcance estudio/global/trading)

CREATE TABLE IF NOT EXISTS "instrument_narratives" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "scope" TEXT NOT NULL DEFAULT 'estudio',
  "body" TEXT NOT NULL,
  "source" TEXT NOT NULL DEFAULT 'user',
  "version" INTEGER NOT NULL DEFAULT 1,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "instrument_narratives_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "instrument_narratives_instrument_id_scope_key"
  ON "instrument_narratives"("instrument_id", "scope");

CREATE INDEX IF NOT EXISTS "instrument_narratives_instrument_id_updated_at_idx"
  ON "instrument_narratives"("instrument_id", "updated_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'instrument_narratives_instrument_id_fkey'
  ) THEN
    ALTER TABLE "instrument_narratives"
      ADD CONSTRAINT "instrument_narratives_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
