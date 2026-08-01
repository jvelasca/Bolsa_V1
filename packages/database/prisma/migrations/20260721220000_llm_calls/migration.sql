-- RFC-007 ART-LLM-CALL — append-only audit table
CREATE TABLE IF NOT EXISTS "llm_calls" (
  "id" TEXT NOT NULL,
  "provider" TEXT NOT NULL,
  "model" TEXT NOT NULL,
  "prompt_template_id" TEXT NOT NULL,
  "prompt_rendered" TEXT NOT NULL,
  "response_raw" TEXT,
  "response_parsed" JSONB,
  "validation_passed" BOOLEAN NOT NULL,
  "validation_errors" JSONB NOT NULL DEFAULT '[]',
  "elapsed_ms" INTEGER NOT NULL,
  "cost_usd" DECIMAL(12, 6) NOT NULL DEFAULT 0,
  "status" TEXT NOT NULL,
  "error" TEXT,
  "trace_id" TEXT NOT NULL,
  "causation_id" TEXT,
  "producer_version" TEXT NOT NULL,
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "llm_calls_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "llm_calls_created_at_idx"
  ON "llm_calls"("created_at" DESC);

CREATE INDEX IF NOT EXISTS "llm_calls_provider_created_at_idx"
  ON "llm_calls"("provider", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "llm_calls_trace_id_idx"
  ON "llm_calls"("trace_id");

CREATE INDEX IF NOT EXISTS "llm_calls_status_created_at_idx"
  ON "llm_calls"("status", "created_at" DESC);
