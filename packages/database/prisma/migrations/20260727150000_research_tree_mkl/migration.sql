-- ADR-018 / P2.E Research Tree + P2.F MKL sync stub

CREATE TABLE IF NOT EXISTS "research_tree_edges" (
  "id" TEXT NOT NULL,
  "from_ref_type" TEXT NOT NULL,
  "from_ref_id" TEXT NOT NULL,
  "to_ref_type" TEXT NOT NULL,
  "to_ref_id" TEXT NOT NULL,
  "edge_type" TEXT NOT NULL,
  "notes" TEXT,
  "payload" JSONB,
  "deleted_at" TIMESTAMPTZ(3),
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "research_tree_edges_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "research_tree_edges_from_ref_type_from_ref_id_idx"
  ON "research_tree_edges"("from_ref_type", "from_ref_id");

CREATE INDEX IF NOT EXISTS "research_tree_edges_to_ref_type_to_ref_id_idx"
  ON "research_tree_edges"("to_ref_type", "to_ref_id");

CREATE INDEX IF NOT EXISTS "research_tree_edges_edge_type_created_at_idx"
  ON "research_tree_edges"("edge_type", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "research_tree_edges_deleted_at_idx"
  ON "research_tree_edges"("deleted_at");

CREATE TABLE IF NOT EXISTS "mkl_sync_events" (
  "id" TEXT NOT NULL,
  "knowledge_node_id" TEXT NOT NULL,
  "status" TEXT NOT NULL,
  "fact_payload" JSONB NOT NULL,
  "math_version" TEXT NOT NULL,
  "notes" JSONB NOT NULL DEFAULT '[]',
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "mkl_sync_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "mkl_sync_events_knowledge_node_id_created_at_idx"
  ON "mkl_sync_events"("knowledge_node_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "mkl_sync_events_status_created_at_idx"
  ON "mkl_sync_events"("status", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mkl_sync_events_knowledge_node_id_fkey'
  ) THEN
    ALTER TABLE "mkl_sync_events"
      ADD CONSTRAINT "mkl_sync_events_knowledge_node_id_fkey"
      FOREIGN KEY ("knowledge_node_id") REFERENCES "knowledge_nodes"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
