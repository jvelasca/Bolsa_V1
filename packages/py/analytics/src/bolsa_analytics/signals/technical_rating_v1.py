"""Technical rating v1 — scorer determinista y explicable (P10a)."""

from __future__ import annotations

from dataclasses import dataclass

from bolsa_analytics.indicators.compute import (
    OhlcvBar,
    compute_atr,
    compute_bollinger,
    compute_cci,
    compute_macd_line,
    compute_rsi,
    compute_sma,
    compute_stoch_k,
)
from bolsa_analytics.signals.pattern_uptrend_v1 import score_uptrend_pattern_v1

TECHNICAL_RATING_V1_VERSION = "1.1.0"
MODEL_ID = "technical_rating_v1"


@dataclass(frozen=True, slots=True)
class TechnicalRatingBreakdown:
    trend: float
    momentum: float
    volatility: float
    mean_reversion: float
    pattern: float
    total: float
    model_id: str = MODEL_ID
    model_version: str = TECHNICAL_RATING_V1_VERSION

    def to_dict(self) -> dict[str, float | str]:
        return {
            "trend": round(self.trend, 2),
            "momentum": round(self.momentum, 2),
            "volatility": round(self.volatility, 2),
            "meanReversion": round(self.mean_reversion, 2),
            "pattern": round(self.pattern, 2),
            "total": round(self.total, 2),
            "modelId": self.model_id,
            "modelVersion": self.model_version,
        }


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _last_value(series: list[float | None]) -> float | None:
    if not series:
        return None
    return series[-1]


def _score_trend(closes: list[float], index: int) -> float:
    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    sma200 = compute_sma(closes, 200)
    price = closes[index]
    s20 = sma20[index]
    s50 = sma50[index]
    s200 = sma200[index]

    score = 50.0
    if s20 is not None and s50 is not None:
        score += 15 if s20 > s50 else -15
    if s50 is not None and s200 is not None:
        score += 15 if s50 > s200 else -15
    if s200 is not None:
        score += 20 if price > s200 else -20
    return _clamp(score)


def _score_momentum(closes: list[float], index: int) -> float:
    rsi = _last_value(compute_rsi(closes, 14))
    macd = _last_value(compute_macd_line(closes, 12, 26))

    score = 50.0
    if rsi is not None:
        if rsi >= 55:
            score += min(30.0, (rsi - 50) * 1.2)
        elif rsi <= 45:
            score -= min(30.0, (50 - rsi) * 1.2)
    if macd is not None:
        score += 20 if macd > 0 else -20
    return _clamp(score)


def _score_volatility(bars: list[OhlcvBar], closes: list[float], index: int) -> float:
    price = closes[index]
    _, upper, lower = compute_bollinger(closes, 20, 2.0)
    upper_v = upper[index]
    lower_v = lower[index]
    atr = _last_value(compute_atr(bars, 14))

    score = 50.0
    if upper_v is not None and lower_v is not None and upper_v > lower_v:
        position = (price - lower_v) / (upper_v - lower_v)
        if position >= 0.55:
            score += 25
        elif position <= 0.35:
            score -= 10
        else:
            score += 10
    if atr is not None and index >= 20:
        window = [bar.close for bar in bars[index - 19 : index + 1]]
        avg = sum(window) / len(window)
        if avg > 0:
            atr_pct = (atr / avg) * 100
            if 1.0 <= atr_pct <= 4.0:
                score += 10
            elif atr_pct > 6.0:
                score -= 10
    return _clamp(score)


def _score_mean_reversion(closes: list[float], bars: list[OhlcvBar], index: int) -> float:
    stoch = _last_value(compute_stoch_k(bars, 14))
    cci = _last_value(compute_cci(bars, 20))

    score = 50.0
    if stoch is not None:
        if 40 <= stoch <= 60:
            score += 10
        elif stoch < 25:
            score += 15
        elif stoch > 80:
            score -= 15
    if cci is not None:
        if -50 <= cci <= 50:
            score += 5
        elif cci < -100:
            score += 10
        elif cci > 100:
            score -= 10
    return _clamp(score)


def compute_technical_rating_v1(bars: list[OhlcvBar]) -> TechnicalRatingBreakdown | None:
    if len(bars) < 50:
        return None

    closes = [bar.close for bar in bars]
    index = len(closes) - 1

    trend = _score_trend(closes, index)
    momentum = _score_momentum(closes, index)
    volatility = _score_volatility(bars, closes, index)
    mean_reversion = _score_mean_reversion(closes, bars, index)
    pattern_result = score_uptrend_pattern_v1(bars)
    pattern = pattern_result.score if pattern_result is not None else 50.0

    total = (
        trend * 0.38
        + momentum * 0.28
        + volatility * 0.14
        + mean_reversion * 0.14
        + pattern * 0.06
    )

    return TechnicalRatingBreakdown(
        trend=trend,
        momentum=momentum,
        volatility=volatility,
        mean_reversion=mean_reversion,
        pattern=pattern,
        total=_clamp(total),
    )


def compute_technical_rating_at_index(bars: list[OhlcvBar], index: int) -> TechnicalRatingBreakdown | None:
    if index + 1 < 50:
        return None
    slice_bars = bars[: index + 1]
    closes = [bar.close for bar in slice_bars]
    idx = len(closes) - 1
    trend = _score_trend(closes, idx)
    momentum = _score_momentum(closes, idx)
    volatility = _score_volatility(slice_bars, closes, idx)
    mean_reversion = _score_mean_reversion(closes, slice_bars, idx)
    pattern_result = score_uptrend_pattern_v1(slice_bars)
    pattern = pattern_result.score if pattern_result is not None else 50.0
    total = (
        trend * 0.38
        + momentum * 0.28
        + volatility * 0.14
        + mean_reversion * 0.14
        + pattern * 0.06
    )
    return TechnicalRatingBreakdown(
        trend=trend,
        momentum=momentum,
        volatility=volatility,
        mean_reversion=mean_reversion,
        pattern=pattern,
        total=_clamp(total),
    )


def compute_technical_rating_series_v1(
    bars: list[OhlcvBar],
    *,
    warmup: int = 50,
) -> list[float | None]:
    out: list[float | None] = []
    for index in range(len(bars)):
        if index + 1 < warmup:
            out.append(None)
            continue
        rating = compute_technical_rating_at_index(bars, index)
        out.append(rating.total if rating is not None else None)
    return out
