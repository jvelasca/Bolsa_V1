-- L2: metadatos linked-universe en listas + jobs de suscripción de índices
ALTER TABLE "instrument_lists" ADD COLUMN IF NOT EXISTS "kind" TEXT;
ALTER TABLE "instrument_lists" ADD COLUMN IF NOT EXISTS "universe_code" TEXT;
ALTER TABLE "instrument_lists" ADD COLUMN IF NOT EXISTS "last_synced_at" TIMESTAMPTZ(3);
ALTER TABLE "instrument_lists" ADD COLUMN IF NOT EXISTS "content_hash" TEXT;
ALTER TABLE "instrument_lists" ADD COLUMN IF NOT EXISTS "membership_changelog" JSONB;

CREATE INDEX IF NOT EXISTS "instrument_lists_kind_idx" ON "instrument_lists"("kind");
CREATE INDEX IF NOT EXISTS "instrument_lists_universe_code_idx" ON "instrument_lists"("universe_code");

-- Backfill: catalog → linked_universe; custom → personal
UPDATE "instrument_lists"
SET "kind" = CASE
  WHEN "source" = 'catalog' THEN 'linked_universe'
  ELSE 'personal'
END
WHERE "kind" IS NULL;

CREATE TABLE IF NOT EXISTS "index_subscribe_jobs" (
  "id" TEXT NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'pending',
  "payload" JSONB NOT NULL,
  "result" JSONB,
  "error" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completed_at" TIMESTAMPTZ(3),
  CONSTRAINT "index_subscribe_jobs_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "index_subscribe_jobs_status_created_at_idx"
  ON "index_subscribe_jobs"("status", "created_at" DESC);
