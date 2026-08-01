import json
from pathlib import Path

import pytest

from bolsa_analytics.indicators.compute import IndicatorSpecInput, OhlcvBar, compute_spec

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "indicator_golden.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _bars_from_rows(rows: list[dict]) -> list[OhlcvBar]:
    return [
        OhlcvBar(
            timestamp=row["timestamp"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for row in rows
    ]


def _bars_for_case(data: dict, case: dict) -> list[OhlcvBar]:
    if case.get("barsRef") == "extended":
        return _bars_from_rows(data["barsExtended"])
    return _bars_from_rows(data["bars"])


def test_sma_matches_reference_window() -> None:
    result = compute_spec(
        _bars_from_rows(_load_fixture()["bars"]),
        IndicatorSpecInput(definition_id="sma", parameters={"period": 3}),
    )
    main = next(line for line in result.lines if line.key == "main")
    assert main.points[0].timestamp == "2024-01-03"
    assert main.points[0].value == pytest.approx(104.0)
    assert main.points[-1].value == pytest.approx(111.0)


@pytest.mark.parametrize("case", _load_fixture()["cases"], ids=lambda c: f"{c['definitionId']}:{c['lineKey']}")
def test_golden_cases(case: dict) -> None:
    data = _load_fixture()
    bars = _bars_for_case(data, case)
    result = compute_spec(
        bars,
        IndicatorSpecInput(definition_id=case["definitionId"], parameters=case["parameters"]),
    )
    line = next(item for item in result.lines if item.key == case["lineKey"])
    assert len(line.points) == len(case["points"])
    for actual, expected in zip(line.points, case["points"], strict=True):
        assert actual.timestamp == expected["timestamp"]
        assert actual.value == pytest.approx(expected["value"], rel=1e-9, abs=1e-9)


def test_bb_returns_three_lines() -> None:
    bars = _bars_from_rows(_load_fixture()["bars"])
    result = compute_spec(
        bars,
        IndicatorSpecInput(definition_id="bb", parameters={"period": 3, "stdDev": 2}),
    )
    keys = {line.key for line in result.lines}
    assert keys == {"upper", "mid", "lower"}


def test_unsupported_definition_raises() -> None:
    bars = _bars_from_rows(_load_fixture()["bars"])
    with pytest.raises(ValueError, match="Unsupported"):
        compute_spec(bars, IndicatorSpecInput(definition_id="unknown", parameters={}))
