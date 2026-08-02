-- ADR-020 M1b: mandato operativo multi-dispositivo (tenures + trade links)

CREATE TABLE IF NOT EXISTS "mandate_tenures" (
  "id" TEXT NOT NULL,
  "account_id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "timeframe" TEXT,
  "strategy_definition_id" TEXT,
  "strategy_label_snapshot" TEXT,
  "effective_from" TIMESTAMPTZ(3) NOT NULL,
  "effective_to" TIMESTAMPTZ(3),
  "actor" TEXT NOT NULL,
  "reason" TEXT NOT NULL,
  "source_top_id" TEXT,
  "source_top_version" INTEGER,
  "evidence_level" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "mandate_tenures_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "mandate_tenures_account_instrument_from_idx"
  ON "mandate_tenures"("account_id", "instrument_id", "effective_from");

CREATE UNIQUE INDEX IF NOT EXISTS "mandate_tenures_one_open_uq"
  ON "mandate_tenures"("account_id", "instrument_id")
  WHERE "effective_to" IS NULL;

CREATE TABLE IF NOT EXISTS "mandate_trade_links" (
  "transaction_id" TEXT NOT NULL,
  "mandate_tenure_id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "account_id" TEXT NOT NULL,
  "linked_at" TIMESTAMPTZ(3) NOT NULL,
  "engine" TEXT NOT NULL DEFAULT 'mandate-trade-links-v1',
  CONSTRAINT "mandate_trade_links_pkey" PRIMARY KEY ("transaction_id")
);

CREATE INDEX IF NOT EXISTS "mandate_trade_links_tenure_idx"
  ON "mandate_trade_links"("mandate_tenure_id");

CREATE INDEX IF NOT EXISTS "mandate_trade_links_account_instrument_idx"
  ON "mandate_trade_links"("account_id", "instrument_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mandate_tenures_account_id_fkey'
  ) THEN
    ALTER TABLE "mandate_tenures"
      ADD CONSTRAINT "mandate_tenures_account_id_fkey"
      FOREIGN KEY ("account_id") REFERENCES "investment_accounts"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mandate_tenures_instrument_id_fkey'
  ) THEN
    ALTER TABLE "mandate_tenures"
      ADD CONSTRAINT "mandate_tenures_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mandate_trade_links_tenure_id_fkey'
  ) THEN
    ALTER TABLE "mandate_trade_links"
      ADD CONSTRAINT "mandate_trade_links_tenure_id_fkey"
      FOREIGN KEY ("mandate_tenure_id") REFERENCES "mandate_tenures"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mandate_trade_links_account_id_fkey'
  ) THEN
    ALTER TABLE "mandate_trade_links"
      ADD CONSTRAINT "mandate_trade_links_account_id_fkey"
      FOREIGN KEY ("account_id") REFERENCES "investment_accounts"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mandate_trade_links_instrument_id_fkey'
  ) THEN
    ALTER TABLE "mandate_trade_links"
      ADD CONSTRAINT "mandate_trade_links_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
