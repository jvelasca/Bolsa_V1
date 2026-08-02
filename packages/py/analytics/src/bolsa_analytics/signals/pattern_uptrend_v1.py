"""P13 MVP — detección heurística de estructura alcista (HH + HL)."""

from __future__ import annotations

from dataclasses import dataclass

from bolsa_analytics.indicators.compute import OhlcvBar

PATTERN_UPTREND_V1_VERSION = "1.0.0"
MIN_BARS = 40


@dataclass(frozen=True, slots=True)
class UptrendPatternScore:
    score: float
    higher_highs: int
    higher_lows: int
    model_version: str = PATTERN_UPTREND_V1_VERSION

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "score": round(self.score, 2),
            "higherHighs": self.higher_highs,
            "higherLows": self.higher_lows,
            "modelVersion": self.model_version,
        }


def _pivot_indices(values: list[float], *, kind: str, window: int = 3) -> list[int]:
    pivots: list[int] = []
    for index in range(window, len(values) - window):
        segment = values[index - window : index + window + 1]
        center = values[index]
        if kind == "high" and center == max(segment) or kind == "low" and center == min(segment):
            pivots.append(index)
    return pivots


def score_uptrend_pattern_v1(bars: list[OhlcvBar]) -> UptrendPatternScore | None:
    if len(bars) < MIN_BARS:
        return None

    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    closes = [bar.close for bar in bars]
    high_pivots = _pivot_indices(highs, kind="high")
    low_pivots = _pivot_indices(lows, kind="low")

    higher_highs = 0
    higher_lows = 0
    if len(high_pivots) >= 2:
        recent_highs = [highs[index] for index in high_pivots[-3:]]
        higher_highs = sum(
            1 for left, right in zip(recent_highs, recent_highs[1:], strict=False) if right > left
        )
    if len(low_pivots) >= 2:
        recent_lows = [lows[index] for index in low_pivots[-3:]]
        higher_lows = sum(
            1 for left, right in zip(recent_lows, recent_lows[1:], strict=False) if right > left
        )

    score = 50.0 + higher_highs * 15.0 + higher_lows * 15.0
    if len(closes) >= 20 and closes[-1] > closes[-20]:
        score += 10.0
    if closes[-1] > closes[0]:
        score += 5.0
    score = max(0.0, min(100.0, score))

    if higher_highs == 0 and higher_lows == 0 and closes[-1] <= closes[0]:
        return None

    return UptrendPatternScore(
        score=score,
        higher_highs=higher_highs,
        higher_lows=higher_lows,
    )
