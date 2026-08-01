-- SC-3: alertas v2 suscritas a StrategyDefinitionV1 / preset
CREATE TABLE IF NOT EXISTS "signal_alert_subscriptions" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "symbol" TEXT NOT NULL,
  "strategy_definition_id" TEXT,
  "preset_key" TEXT,
  "timeframe" TEXT NOT NULL DEFAULT '1d',
  "signal_kinds" JSONB NOT NULL DEFAULT '["entry_long","exit"]'::jsonb,
  "is_active" BOOLEAN NOT NULL DEFAULT true,
  "last_triggered_at" TIMESTAMPTZ(3),
  "last_bar_timestamp" TEXT,
  "last_signal_kind" TEXT,
  "last_signal_price" DECIMAL(18,6),
  "note" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "signal_alert_subscriptions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "signal_alert_subscriptions_is_active_created_at_idx"
  ON "signal_alert_subscriptions"("is_active", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'signal_alert_subscriptions_instrument_id_fkey'
  ) THEN
    ALTER TABLE "signal_alert_subscriptions"
      ADD CONSTRAINT "signal_alert_subscriptions_instrument_id_fkey"
      FOREIGN KEY ("instrument_id") REFERENCES "instruments"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'signal_alert_subscriptions_strategy_definition_id_fkey'
  ) THEN
    ALTER TABLE "signal_alert_subscriptions"
      ADD CONSTRAINT "signal_alert_subscriptions_strategy_definition_id_fkey"
      FOREIGN KEY ("strategy_definition_id") REFERENCES "strategy_definitions"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
