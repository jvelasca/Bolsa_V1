-- ADR-010 P6: políticas por posición en cartera (PositionPolicyV1)
CREATE TABLE IF NOT EXISTS "position_policies" (
  "id" TEXT NOT NULL,
  "account_id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "definition" JSONB NOT NULL,
  "mode" TEXT NOT NULL DEFAULT 'manual',
  "exit_strategy_definition_id" TEXT,
  "execution_policy_id" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "position_policies_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "position_policies_account_instrument_idx"
  ON "position_policies"("account_id", "instrument_id");

CREATE INDEX IF NOT EXISTS "position_policies_account_id_idx"
  ON "position_policies"("account_id");

ALTER TABLE "position_policies"
  DROP CONSTRAINT IF EXISTS "position_policies_account_id_fkey";

ALTER TABLE "position_policies"
  ADD CONSTRAINT "position_policies_account_id_fkey"
  FOREIGN KEY ("account_id") REFERENCES "investment_accounts"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "position_policies"
  DROP CONSTRAINT IF EXISTS "position_policies_instrument_id_fkey";

ALTER TABLE "position_policies"
  ADD CONSTRAINT "position_policies_instrument_id_fkey"
  FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "position_policies"
  DROP CONSTRAINT IF EXISTS "position_policies_exit_strategy_definition_id_fkey";

ALTER TABLE "position_policies"
  ADD CONSTRAINT "position_policies_exit_strategy_definition_id_fkey"
  FOREIGN KEY ("exit_strategy_definition_id") REFERENCES "strategy_definitions"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "position_policies"
  DROP CONSTRAINT IF EXISTS "position_policies_execution_policy_id_fkey";

ALTER TABLE "position_policies"
  ADD CONSTRAINT "position_policies_execution_policy_id_fkey"
  FOREIGN KEY ("execution_policy_id") REFERENCES "execution_policies"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
