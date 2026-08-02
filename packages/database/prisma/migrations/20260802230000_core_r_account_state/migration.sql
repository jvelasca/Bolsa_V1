-- Q3.4: CORE-R queue/report/scheduler multi-dispositivo (blob por cuenta)

CREATE TABLE IF NOT EXISTS "core_r_account_state" (
  "account_id" TEXT NOT NULL,
  "queue_json" JSONB NOT NULL DEFAULT '[]',
  "reports_json" JSONB NOT NULL DEFAULT '{}',
  "scheduler_json" JSONB NOT NULL DEFAULT '{}',
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "core_r_account_state_pkey" PRIMARY KEY ("account_id")
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'core_r_account_state_account_id_fkey'
  ) THEN
    ALTER TABLE "core_r_account_state"
      ADD CONSTRAINT "core_r_account_state_account_id_fkey"
      FOREIGN KEY ("account_id") REFERENCES "investment_accounts"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
