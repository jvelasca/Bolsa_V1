from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.pattern_uptrend_v1 import score_uptrend_pattern_v1


def _uptrend_bars(count: int = 120) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    price = 100.0
    for index in range(count):
        wave = (index % 8) - 4
        price += 0.35 + wave * 0.08
        bars.append(
            OhlcvBar(
                timestamp=f"2024-02-{(index % 28) + 1:02d}",
                open=price - 0.3,
                high=price + 0.8,
                low=price - 0.8,
                close=price,
                volume=500_000.0,
            )
        )
    return bars


def test_uptrend_pattern_scores_high() -> None:
    score = score_uptrend_pattern_v1(_uptrend_bars(120))
    assert score is not None
    assert score.score >= 50


def test_uptrend_pattern_requires_minimum_bars() -> None:
    assert score_uptrend_pattern_v1(_uptrend_bars(20)) is None
