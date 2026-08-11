-- F1/M4: idempotencia de trades — columna idempotency_key + UNIQUE(portfolio_id, idempotency_key)

ALTER TABLE "transactions" ADD COLUMN IF NOT EXISTS "idempotency_key" TEXT;

-- Los NULLs múltiples están permitidos en Postgres, así rows legacy sin key no colisionan.
CREATE UNIQUE INDEX IF NOT EXISTS "transactions_portfolio_id_idempotency_key_key"
  ON "transactions"("portfolio_id", "idempotency_key");
