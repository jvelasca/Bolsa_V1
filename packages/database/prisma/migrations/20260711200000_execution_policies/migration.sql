-- ADR-010 P5: políticas de ejecución (ExecutionPolicyV1)
CREATE TABLE IF NOT EXISTS "execution_policies" (
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "definition" JSONB NOT NULL,
  "mode" TEXT NOT NULL,
  "account_id" TEXT,
  "strategy_definition_id" TEXT,
  "origin" TEXT NOT NULL DEFAULT 'manual',
  "enabled" BOOLEAN NOT NULL DEFAULT true,
  "user_id" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "execution_policies_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "execution_policies_enabled_updated_at_idx"
  ON "execution_policies"("enabled", "updated_at" DESC);

ALTER TABLE "execution_policies"
  DROP CONSTRAINT IF EXISTS "execution_policies_account_id_fkey";

ALTER TABLE "execution_policies"
  ADD CONSTRAINT "execution_policies_account_id_fkey"
  FOREIGN KEY ("account_id") REFERENCES "investment_accounts"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "execution_policies"
  DROP CONSTRAINT IF EXISTS "execution_policies_strategy_definition_id_fkey";

ALTER TABLE "execution_policies"
  ADD CONSTRAINT "execution_policies_strategy_definition_id_fkey"
  FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
