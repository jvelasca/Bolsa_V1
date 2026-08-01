-- Expand BacktestStrategyType enum with professional screener presets
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'ema_crossover';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'golden_cross';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'death_cross';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'macd_signal_cross';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'macd_zero_line';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'rsi_momentum';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'rsi_oversold_bounce';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'stoch_oversold';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'bollinger_lower_bounce';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'bollinger_upper_breakout';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'price_above_sma200';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'ma_stack_bullish';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'pullback_in_uptrend';
ALTER TYPE "public"."BacktestStrategyType" ADD VALUE IF NOT EXISTS 'cci_oversold';
