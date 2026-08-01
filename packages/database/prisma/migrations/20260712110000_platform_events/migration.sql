-- ADR-010: bus append-only de eventos de plataforma (audit + handlers)
CREATE TABLE IF NOT EXISTS "platform_events" (
  "id" TEXT NOT NULL,
  "type" TEXT NOT NULL,
  "payload" JSONB NOT NULL,
  "correlation_id" TEXT,
  "user_id" TEXT,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "platform_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "platform_events_type_created_at_idx"
  ON "platform_events"("type", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "platform_events_correlation_id_idx"
  ON "platform_events"("correlation_id");
