-- ART-DECISION-SESSION — auditoría completa del razonamiento (propose+)

CREATE TABLE IF NOT EXISTS "decision_sessions" (
  "id" TEXT NOT NULL,
  "kind" TEXT NOT NULL,
  "status" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "account_id" TEXT,
  "symbol" TEXT,
  "recommendation_id" TEXT,
  "decision_id" TEXT,
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "decision_sessions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "decision_sessions_instrument_id_created_at_idx"
  ON "decision_sessions"("instrument_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "decision_sessions_account_id_created_at_idx"
  ON "decision_sessions"("account_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "decision_sessions_recommendation_id_idx"
  ON "decision_sessions"("recommendation_id");
CREATE INDEX IF NOT EXISTS "decision_sessions_decision_id_idx"
  ON "decision_sessions"("decision_id");
CREATE INDEX IF NOT EXISTS "decision_sessions_kind_created_at_idx"
  ON "decision_sessions"("kind", "created_at" DESC);
