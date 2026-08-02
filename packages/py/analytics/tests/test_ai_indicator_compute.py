from bolsa_analytics.indicators.compute import IndicatorSpecInput, OhlcvBar, compute_spec


def _bars(count: int = 120) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    price = 100.0
    for index in range(count):
        price += 0.2
        bars.append(
            OhlcvBar(
                timestamp=f"2024-01-{(index % 28) + 1:02d}",
                open=price - 0.1,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=1_000_000.0,
            )
        )
    return bars


def test_compute_technical_rating_v1_series() -> None:
    result = compute_spec(
        _bars(),
        IndicatorSpecInput(definition_id="technical_rating_v1", parameters={"warmupBars": 50}),
    )
    assert result.lines
    points = result.lines[0].points
    assert len(points) > 0
    assert all(0 <= point.value <= 100 for point in points)


def test_compute_ai_global_score_v1_series() -> None:
    result = compute_spec(
        _bars(),
        IndicatorSpecInput(
            definition_id="ai_global_score_v1",
            parameters={"setupWeight": 70, "dataWeight": 30, "warmupBars": 50},
        ),
    )
    points = result.lines[0].points
    assert len(points) > 0
    assert all(0 <= point.value <= 100 for point in points)
