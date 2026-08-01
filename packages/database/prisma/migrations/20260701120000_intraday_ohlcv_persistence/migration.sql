-- ADR-007: extend Timeframe enum and promote ohlcv_bars.timestamp to timestamptz.
-- Requires baseline migration 20250101000000_baseline on shadow DB.

-- AlterEnum
ALTER TYPE "Timeframe" ADD VALUE IF NOT EXISTS '30m';
ALTER TYPE "Timeframe" ADD VALUE IF NOT EXISTS '4h';
ALTER TYPE "Timeframe" ADD VALUE IF NOT EXISTS '1wk';
ALTER TYPE "Timeframe" ADD VALUE IF NOT EXISTS '1mo';

-- AlterTable
ALTER TABLE "ohlcv_bars"
  ALTER COLUMN "timestamp" SET DATA TYPE TIMESTAMPTZ(3)
  USING ("timestamp"::timestamp AT TIME ZONE 'UTC');
