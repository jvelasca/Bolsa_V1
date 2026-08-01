-- Preferir auto-sync del universo de listas (screeners) sin saturar Yahoo.
UPDATE "sync_settings"
SET "scope" = 'lists'
WHERE "id" = 'default' AND "scope" = 'stale';

ALTER TABLE "sync_settings" ALTER COLUMN "scope" SET DEFAULT 'lists';
