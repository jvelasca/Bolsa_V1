-- SC-6: canales de alerta (toast, webhook, email)
ALTER TABLE "signal_alert_subscriptions"
  ADD COLUMN IF NOT EXISTS "channels" JSONB NOT NULL DEFAULT '["toast"]'::jsonb,
  ADD COLUMN IF NOT EXISTS "webhook_url" TEXT,
  ADD COLUMN IF NOT EXISTS "email_to" TEXT;
