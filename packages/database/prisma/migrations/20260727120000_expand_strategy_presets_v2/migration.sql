-- Expand BacktestStrategyType with channel / ADX / Ichimoku / VWAP / SuperTrend presets
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'donchian_breakout';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'adx_di_trend';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'ichimoku_tk_cross';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'vwap_reclaim';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'supertrend_follow';
