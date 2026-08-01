-- ADR-018 / P2.C — Belief Engine v0 (mutable state + append-only history)

CREATE TABLE IF NOT EXISTS "hypothesis_beliefs" (
  "id" TEXT NOT NULL,
  "hypothesis_id" TEXT NOT NULL,
  "belief" DECIMAL(8,4) NOT NULL,
  "belief_ci_low" DECIMAL(8,4) NOT NULL,
  "belief_ci_high" DECIMAL(8,4) NOT NULL,
  "n_experiments" INTEGER NOT NULL DEFAULT 0,
  "evidence_weight" DECIMAL(12,4) NOT NULL DEFAULT 0,
  "contexts_ok" JSONB NOT NULL DEFAULT '[]',
  "contexts_fail" JSONB NOT NULL DEFAULT '[]',
  "evidence_ids" JSONB NOT NULL DEFAULT '[]',
  "trial_ids" JSONB NOT NULL DEFAULT '[]',
  "math_version" TEXT NOT NULL,
  "last_reviewed_at" TIMESTAMPTZ(3) NOT NULL,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "hypothesis_beliefs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "hypothesis_beliefs_hypothesis_id_key"
  ON "hypothesis_beliefs"("hypothesis_id");

CREATE INDEX IF NOT EXISTS "hypothesis_beliefs_last_reviewed_at_idx"
  ON "hypothesis_beliefs"("last_reviewed_at" DESC);

CREATE TABLE IF NOT EXISTS "belief_history" (
  "id" TEXT NOT NULL,
  "hypothesis_id" TEXT NOT NULL,
  "belief_id" TEXT NOT NULL,
  "belief" DECIMAL(8,4) NOT NULL,
  "belief_ci_low" DECIMAL(8,4) NOT NULL,
  "belief_ci_high" DECIMAL(8,4) NOT NULL,
  "n_experiments" INTEGER NOT NULL,
  "evidence_weight" DECIMAL(12,4) NOT NULL,
  "trigger_evidence_id" TEXT,
  "delta" JSONB,
  "math_version" TEXT NOT NULL,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "belief_history_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "belief_history_hypothesis_id_created_at_idx"
  ON "belief_history"("hypothesis_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "belief_history_belief_id_created_at_idx"
  ON "belief_history"("belief_id", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'hypothesis_beliefs_hypothesis_id_fkey'
  ) THEN
    ALTER TABLE "hypothesis_beliefs"
      ADD CONSTRAINT "hypothesis_beliefs_hypothesis_id_fkey"
      FOREIGN KEY ("hypothesis_id") REFERENCES "hypotheses"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'belief_history_hypothesis_id_fkey'
  ) THEN
    ALTER TABLE "belief_history"
      ADD CONSTRAINT "belief_history_hypothesis_id_fkey"
      FOREIGN KEY ("hypothesis_id") REFERENCES "hypotheses"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'belief_history_belief_id_fkey'
  ) THEN
    ALTER TABLE "belief_history"
      ADD CONSTRAINT "belief_history_belief_id_fkey"
      FOREIGN KEY ("belief_id") REFERENCES "hypothesis_beliefs"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
