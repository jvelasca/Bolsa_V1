import json
from pathlib import Path

from bolsa_analytics.drawing_replay import OhlcvBar, evaluate_drawing_replay

FIXTURE = Path(__file__).parent / "fixtures" / "drawing_replay_golden.json"


def test_drawing_replay_golden() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bars = [OhlcvBar(timestamp=b["timestamp"], close=b["close"]) for b in payload["bars"]]
    markers = evaluate_drawing_replay(bars, payload["drawings"])
    assert len(markers) == len(payload["expectedMarkers"])
    for marker, expected in zip(markers, payload["expectedMarkers"], strict=True):
        assert marker.id == expected["id"]
        assert marker.drawing_id == expected["drawingId"]
        assert marker.timestamp == expected["timestamp"]
        assert marker.price == expected["price"]
        assert marker.level == expected["level"]
        assert marker.direction == expected["direction"]
        assert marker.drawing_type == expected["drawingType"]


def test_drawing_replay_skips_without_alert_flag() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bars = [OhlcvBar(timestamp=b["timestamp"], close=b["close"]) for b in payload["bars"]]
    drawings = [{**payload["drawings"][0], "alertOnCross": False}]
    assert evaluate_drawing_replay(bars, drawings) == []
