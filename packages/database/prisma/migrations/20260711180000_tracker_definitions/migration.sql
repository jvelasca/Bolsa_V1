-- ADR-010 P3: rastreadores persistidos (TrackerDefinitionV1)
CREATE TABLE IF NOT EXISTS "tracker_definitions" (
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "definition" JSONB NOT NULL,
  "strategy_definition_id" TEXT NOT NULL,
  "strategy_version" INTEGER,
  "timeframe" TEXT NOT NULL DEFAULT '1d',
  "evaluation_mode" TEXT NOT NULL DEFAULT 'bar_close',
  "origin" TEXT NOT NULL DEFAULT 'manual',
  "enabled" BOOLEAN NOT NULL DEFAULT true,
  "user_id" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "tracker_definitions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "tracker_definitions_enabled_updated_at_idx"
  ON "tracker_definitions"("enabled", "updated_at" DESC);

ALTER TABLE "tracker_definitions"
  DROP CONSTRAINT IF EXISTS "tracker_definitions_strategy_definition_id_fkey";

ALTER TABLE "tracker_definitions"
  ADD CONSTRAINT "tracker_definitions_strategy_definition_id_fkey"
  FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "scan_jobs" ADD COLUMN IF NOT EXISTS "tracker_definition_id" TEXT;

ALTER TABLE "scan_jobs"
  DROP CONSTRAINT IF EXISTS "scan_jobs_tracker_definition_id_fkey";

ALTER TABLE "scan_jobs"
  ADD CONSTRAINT "scan_jobs_tracker_definition_id_fkey"
  FOREIGN KEY ("tracker_definition_id") REFERENCES "tracker_definitions"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX IF NOT EXISTS "scan_jobs_tracker_definition_id_idx"
  ON "scan_jobs"("tracker_definition_id");
