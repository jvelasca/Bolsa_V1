-- ADR-010 P4: snapshots OHLCV + manifests de scan
CREATE TABLE IF NOT EXISTS "data_snapshots" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "timeframe" TEXT NOT NULL,
  "data_version" TEXT NOT NULL,
  "bar_count" INTEGER NOT NULL,
  "from_ts" TEXT NOT NULL,
  "to_ts" TEXT NOT NULL,
  "source" TEXT NOT NULL DEFAULT 'postgres',
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "data_snapshots_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "data_snapshots_instrument_timeframe_version_idx"
  ON "data_snapshots"("instrument_id", "timeframe", "data_version");

ALTER TABLE "data_snapshots"
  DROP CONSTRAINT IF EXISTS "data_snapshots_instrument_id_fkey";

ALTER TABLE "data_snapshots"
  ADD CONSTRAINT "data_snapshots_instrument_id_fkey"
  FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS "scan_manifests" (
  "id" TEXT NOT NULL,
  "scan_job_id" TEXT,
  "tracker_definition_id" TEXT,
  "strategy_definition_id" TEXT,
  "manifest" JSONB NOT NULL,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "scan_manifests_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "scan_manifests_scan_job_id_idx"
  ON "scan_manifests"("scan_job_id");

CREATE INDEX IF NOT EXISTS "scan_manifests_tracker_definition_id_idx"
  ON "scan_manifests"("tracker_definition_id");

ALTER TABLE "scan_manifests"
  DROP CONSTRAINT IF EXISTS "scan_manifests_scan_job_id_fkey";

ALTER TABLE "scan_manifests"
  ADD CONSTRAINT "scan_manifests_scan_job_id_fkey"
  FOREIGN KEY ("scan_job_id") REFERENCES "scan_jobs"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "scan_manifests"
  DROP CONSTRAINT IF EXISTS "scan_manifests_tracker_definition_id_fkey";

ALTER TABLE "scan_manifests"
  ADD CONSTRAINT "scan_manifests_tracker_definition_id_fkey"
  FOREIGN KEY ("tracker_definition_id") REFERENCES "tracker_definitions"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "scan_manifests"
  DROP CONSTRAINT IF EXISTS "scan_manifests_strategy_definition_id_fkey";

ALTER TABLE "scan_manifests"
  ADD CONSTRAINT "scan_manifests_strategy_definition_id_fkey"
  FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;
