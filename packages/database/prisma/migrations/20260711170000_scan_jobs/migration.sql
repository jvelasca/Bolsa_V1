-- SC-5: cola de scan jobs async (patrón sync_queue, evolución hacia Redis/Arq RD-2)
CREATE TABLE IF NOT EXISTS "scan_jobs" (
  "id" TEXT NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'pending',
  "payload" JSONB NOT NULL,
  "result" JSONB,
  "error" TEXT,
  "cache_hits" INTEGER,
  "cache_misses" INTEGER,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completed_at" TIMESTAMPTZ(3),
  CONSTRAINT "scan_jobs_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "scan_jobs_status_created_at_idx"
  ON "scan_jobs"("status", "created_at" DESC);
