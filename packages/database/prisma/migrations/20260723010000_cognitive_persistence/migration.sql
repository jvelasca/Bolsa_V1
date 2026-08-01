-- RFC-008 D7+ — persistencia cognitiva (Decision Memory, Trials, Confidence, Edge)

CREATE TABLE IF NOT EXISTS "decision_memory" (
  "id" TEXT NOT NULL,
  "decision_id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "account_id" TEXT,
  "outcome" TEXT NOT NULL,
  "reasons" JSONB NOT NULL DEFAULT '[]',
  "policy_rule_ids" JSONB NOT NULL DEFAULT '[]',
  "reevaluate_when" JSONB NOT NULL DEFAULT '[]',
  "opportunity_intact" BOOLEAN NOT NULL,
  "policy_id" TEXT,
  "policy_version" TEXT,
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "decision_memory_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "decision_memory_decision_id_idx"
  ON "decision_memory"("decision_id");
CREATE INDEX IF NOT EXISTS "decision_memory_instrument_id_created_at_idx"
  ON "decision_memory"("instrument_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "decision_memory_account_id_created_at_idx"
  ON "decision_memory"("account_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "decision_memory_outcome_created_at_idx"
  ON "decision_memory"("outcome", "created_at" DESC);

CREATE TABLE IF NOT EXISTS "trial_records" (
  "id" TEXT NOT NULL,
  "log_id" TEXT NOT NULL,
  "strategy_family_ref" TEXT NOT NULL,
  "hypothesis_ref" TEXT NOT NULL,
  "params_hash" TEXT NOT NULL,
  "sharpe_is" DECIMAL(12, 4),
  "notes" TEXT,
  "account_id" TEXT,
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "trial_records_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "trial_records_log_id_idx"
  ON "trial_records"("log_id");
CREATE INDEX IF NOT EXISTS "trial_records_strategy_family_ref_created_at_idx"
  ON "trial_records"("strategy_family_ref", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "trial_records_account_id_created_at_idx"
  ON "trial_records"("account_id", "created_at" DESC);

CREATE TABLE IF NOT EXISTS "confidence_states" (
  "id" TEXT NOT NULL,
  "decision_id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "account_id" TEXT,
  "confidence_0" DECIMAL(8, 4) NOT NULL,
  "confidence" DECIMAL(8, 4) NOT NULL,
  "hint" TEXT NOT NULL,
  "expires_at" TIMESTAMPTZ(3),
  "expired" BOOLEAN NOT NULL DEFAULT false,
  "events" JSONB NOT NULL DEFAULT '[]',
  "notes" JSONB NOT NULL DEFAULT '[]',
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "confidence_states_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "confidence_states_decision_id_idx"
  ON "confidence_states"("decision_id");
CREATE INDEX IF NOT EXISTS "confidence_states_instrument_id_updated_at_idx"
  ON "confidence_states"("instrument_id", "updated_at" DESC);
CREATE INDEX IF NOT EXISTS "confidence_states_expired_updated_at_idx"
  ON "confidence_states"("expired", "updated_at" DESC);
CREATE INDEX IF NOT EXISTS "confidence_states_account_id_updated_at_idx"
  ON "confidence_states"("account_id", "updated_at" DESC);

CREATE TABLE IF NOT EXISTS "edge_reports" (
  "id" TEXT NOT NULL,
  "version" TEXT NOT NULL,
  "strategy_or_signal_ref" TEXT NOT NULL,
  "instrument_universe_ref" TEXT,
  "account_id" TEXT,
  "credibility" DECIMAL(8, 2) NOT NULL,
  "edge_score" DECIMAL(8, 2) NOT NULL,
  "band" TEXT NOT NULL,
  "suite" JSONB NOT NULL,
  "notes" JSONB NOT NULL DEFAULT '[]',
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "edge_reports_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "edge_reports_strategy_or_signal_ref_created_at_idx"
  ON "edge_reports"("strategy_or_signal_ref", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "edge_reports_band_created_at_idx"
  ON "edge_reports"("band", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "edge_reports_account_id_created_at_idx"
  ON "edge_reports"("account_id", "created_at" DESC);
