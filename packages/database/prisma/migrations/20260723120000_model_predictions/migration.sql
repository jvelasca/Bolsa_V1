-- ART-MODEL + ART-PREDICTION — registry cuantitativo (F2)

CREATE TABLE IF NOT EXISTS "model_artifacts" (
  "id" TEXT NOT NULL,
  "model_id" TEXT NOT NULL,
  "model_version" TEXT NOT NULL,
  "framework" TEXT NOT NULL,
  "feature_set_id" TEXT NOT NULL,
  "composition_hash" TEXT,
  "model_checksum" TEXT,
  "trained_at" TIMESTAMPTZ(3),
  "payload" JSONB,
  "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "model_artifacts_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "model_artifacts_model_id_key"
  ON "model_artifacts"("model_id");
CREATE INDEX IF NOT EXISTS "model_artifacts_framework_idx"
  ON "model_artifacts"("framework");

CREATE TABLE IF NOT EXISTS "predictions" (
  "id" TEXT NOT NULL,
  "instrument_id" TEXT NOT NULL,
  "model_id" TEXT NOT NULL,
  "model_version" TEXT NOT NULL,
  "horizon" TEXT,
  "value" DOUBLE PRECISION,
  "confidence" DOUBLE PRECISION,
  "as_of" TIMESTAMPTZ(3),
  "payload" JSONB,
  "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "predictions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "predictions_instrument_id_created_at_idx"
  ON "predictions"("instrument_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "predictions_model_id_created_at_idx"
  ON "predictions"("model_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS "predictions_instrument_model_created_at_idx"
  ON "predictions"("instrument_id", "model_id", "created_at" DESC);
