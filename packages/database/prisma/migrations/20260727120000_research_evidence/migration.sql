-- ADR-018 P2.A — hypotheses stub + research_evidence (append-only)

CREATE TABLE IF NOT EXISTS "hypotheses" (
  "id" TEXT NOT NULL,
  "kind" TEXT NOT NULL DEFAULT 'hypothesis',
  "statement" TEXT NOT NULL,
  "domain" TEXT,
  "context" JSONB,
  "falsifiers" JSONB NOT NULL DEFAULT '[]',
  "status" TEXT NOT NULL DEFAULT 'open',
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "hypotheses_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "hypotheses_status_created_at_idx"
  ON "hypotheses"("status", "created_at" DESC);

CREATE TABLE IF NOT EXISTS "research_evidence" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "trial_id" TEXT,
  "hypothesis_id" TEXT,
  "edge_report_id" TEXT,
  "level" TEXT NOT NULL,
  "source" TEXT NOT NULL,
  "evidence_weight" DECIMAL(8,4) NOT NULL DEFAULT 0,
  "summary" JSONB NOT NULL,
  "math_version" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "research_evidence_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "research_evidence_instrument_id_created_at_idx"
  ON "research_evidence"("instrument_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "research_evidence_trial_id_idx"
  ON "research_evidence"("trial_id");

CREATE INDEX IF NOT EXISTS "research_evidence_hypothesis_id_idx"
  ON "research_evidence"("hypothesis_id");

CREATE INDEX IF NOT EXISTS "research_evidence_level_created_at_idx"
  ON "research_evidence"("level", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_evidence_instrument_id_fkey'
  ) THEN
    ALTER TABLE "research_evidence"
      ADD CONSTRAINT "research_evidence_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_evidence_trial_id_fkey'
  ) THEN
    ALTER TABLE "research_evidence"
      ADD CONSTRAINT "research_evidence_trial_id_fkey"
      FOREIGN KEY ("trial_id") REFERENCES "research_trials"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_evidence_hypothesis_id_fkey'
  ) THEN
    ALTER TABLE "research_evidence"
      ADD CONSTRAINT "research_evidence_hypothesis_id_fkey"
      FOREIGN KEY ("hypothesis_id") REFERENCES "hypotheses"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'research_trials_hypothesis_id_fkey'
  ) THEN
    ALTER TABLE "research_trials"
      ADD CONSTRAINT "research_trials_hypothesis_id_fkey"
      FOREIGN KEY ("hypothesis_id") REFERENCES "hypotheses"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
