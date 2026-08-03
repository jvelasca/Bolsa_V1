-- SEMI Confirm F3: cola supervisada multi-dispositivo (blob por cuenta)

CREATE TABLE IF NOT EXISTS "supervised_f3_account_state" (
  "account_id" TEXT NOT NULL,
  "queue_json" JSONB NOT NULL DEFAULT '[]',
  "active_id" TEXT,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "supervised_f3_account_state_pkey" PRIMARY KEY ("account_id")
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'supervised_f3_account_state_account_id_fkey'
  ) THEN
    ALTER TABLE "supervised_f3_account_state"
      ADD CONSTRAINT "supervised_f3_account_state_account_id_fkey"
      FOREIGN KEY ("account_id") REFERENCES "investment_accounts"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
