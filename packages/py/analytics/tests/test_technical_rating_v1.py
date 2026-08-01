from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.technical_rating_v1 import compute_technical_rating_v1


def _synthetic_uptrend_bars(count: int = 120) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    price = 100.0
    for index in range(count):
        price += 0.35 + (index % 5) * 0.05
        bars.append(
            OhlcvBar(
                timestamp=f"2024-01-{index + 1:02d}",
                open=price - 0.2,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=1_000_000.0,
            )
        )
    return bars


def test_technical_rating_v1_uptrend_scores_high() -> None:
    rating = compute_technical_rating_v1(_synthetic_uptrend_bars())
    assert rating is not None
    assert rating.total >= 55
    assert rating.trend >= 50


def test_technical_rating_requires_minimum_bars() -> None:
    assert compute_technical_rating_v1(_synthetic_uptrend_bars(30)) is None
