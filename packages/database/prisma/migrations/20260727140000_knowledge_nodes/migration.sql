-- ADR-018 / P2.D — Knowledge nodes v0 + Consolidation stub (explicit only)

CREATE TABLE IF NOT EXISTS "knowledge_nodes" (
  "id" TEXT NOT NULL,
  "hypothesis_id" TEXT NOT NULL,
  "stage" TEXT NOT NULL DEFAULT 'EMERGING',
  "statement" TEXT NOT NULL,
  "knowledge_confidence" DECIMAL(8,4) NOT NULL,
  "validity_context" JSONB NOT NULL DEFAULT '{}',
  "evidence_ids" JSONB NOT NULL DEFAULT '[]',
  "belief_snapshot" JSONB NOT NULL,
  "consolidation_report" JSONB NOT NULL,
  "math_version" TEXT NOT NULL,
  "notes" TEXT,
  "consolidated_at" TIMESTAMPTZ(3) NOT NULL,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "knowledge_nodes_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "knowledge_nodes_hypothesis_id_created_at_idx"
  ON "knowledge_nodes"("hypothesis_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "knowledge_nodes_stage_updated_at_idx"
  ON "knowledge_nodes"("stage", "updated_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'knowledge_nodes_hypothesis_id_fkey'
  ) THEN
    ALTER TABLE "knowledge_nodes"
      ADD CONSTRAINT "knowledge_nodes_hypothesis_id_fkey"
      FOREIGN KEY ("hypothesis_id") REFERENCES "hypotheses"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
