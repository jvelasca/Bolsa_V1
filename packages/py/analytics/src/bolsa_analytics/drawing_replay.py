"""Replay histórico de cruces precio vs dibujos (BT-6 / ADR-006 backtest_marker)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class OhlcvBar:
    timestamp: str
    close: float


@dataclass(frozen=True, slots=True)
class DrawingReplayMarker:
    id: str
    drawing_id: str
    timestamp: str
    price: float
    level: float
    direction: Literal["up", "down"]
    drawing_type: str
    label: str | None = None


def _parse_bar_time_ms(timestamp: str) -> float:
    normalized = timestamp if "T" in timestamp else f"{timestamp}T00:00:00.000Z"
    dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp() * 1000


def _interpolate_price(p1: dict[str, Any], p2: dict[str, Any], bar_time: str) -> float:
    t1 = _parse_bar_time_ms(str(p1["time"]))
    t2 = _parse_bar_time_ms(str(p2["time"]))
    t = _parse_bar_time_ms(bar_time)
    if t1 == t2:
        return float(p1["price"])
    ratio = (t - t1) / (t2 - t1)
    return float(p1["price"]) + ratio * (float(p2["price"]) - float(p1["price"]))


def _is_visible(drawing: dict[str, Any]) -> bool:
    return drawing.get("visible", True) is not False


def drawing_supports_replay(drawing: dict[str, Any]) -> bool:
    if not _is_visible(drawing):
        return False
    dtype = drawing.get("type")
    return dtype in {
        "hline",
        "hray",
        "line",
        "ray",
        "ext-line",
        "info-line",
        "trend-angle",
        "regression",
    }


def drawing_level_at_bar(drawing: dict[str, Any], bar_time: str) -> float | None:
    dtype = drawing.get("type")
    if dtype == "hline":
        return float(drawing["price"])
    if dtype == "hray":
        return float(drawing["point"]["price"])

    if dtype not in {
        "line",
        "ray",
        "ext-line",
        "info-line",
        "trend-angle",
        "regression",
    }:
        return None

    p1 = drawing.get("p1")
    p2 = drawing.get("p2")
    if not isinstance(p1, dict) or not isinstance(p2, dict):
        return None

    t = _parse_bar_time_ms(bar_time)
    t1 = _parse_bar_time_ms(str(p1["time"]))
    t2 = _parse_bar_time_ms(str(p2["time"]))
    min_t = min(t1, t2)
    max_t = max(t1, t2)

    if dtype in {"line", "info-line", "trend-angle", "regression"}:
        if t < min_t or t > max_t:
            return None
    elif dtype == "ray":
        if t2 >= t1:
            if t < t1:
                return None
        elif t > t1:
            return None

    return _interpolate_price(p1, p2, bar_time)


def evaluate_drawing_replay(
    bars: list[OhlcvBar],
    drawings: list[dict[str, Any]],
    *,
    alert_drawings_only: bool = True,
) -> list[DrawingReplayMarker]:
    eligible: list[dict[str, Any]] = []
    for drawing in drawings:
        if not drawing_supports_replay(drawing):
            continue
        if alert_drawings_only and drawing.get("alertOnCross") is not True:
            continue
        eligible.append(drawing)

    if len(bars) < 2 or not eligible:
        return []

    markers: list[DrawingReplayMarker] = []
    prev_side: dict[str, Literal["above", "below"]] = {}

    for drawing in eligible:
        drawing_id = str(drawing["id"])
        level0 = drawing_level_at_bar(drawing, bars[0].timestamp)
        if level0 is None:
            continue
        prev_side[drawing_id] = "above" if bars[0].close >= level0 else "below"

    for index in range(1, len(bars)):
        bar = bars[index]
        for drawing in eligible:
            drawing_id = str(drawing["id"])
            stored = prev_side.get(drawing_id)
            level_curr = drawing_level_at_bar(drawing, bar.timestamp)
            if level_curr is None:
                continue

            side_curr: Literal["above", "below"] = (
                "above" if bar.close >= level_curr else "below"
            )

            if stored is None:
                prev_side[drawing_id] = side_curr
                continue

            if stored != side_curr:
                label = drawing.get("label") or drawing.get("text")
                markers.append(
                    DrawingReplayMarker(
                        id=f"{drawing_id}:{bar.timestamp}",
                        drawing_id=drawing_id,
                        timestamp=bar.timestamp,
                        price=bar.close,
                        level=level_curr,
                        direction="up" if side_curr == "above" else "down",
                        drawing_type=str(drawing["type"]),
                        label=str(label) if isinstance(label, str) and label else None,
                    )
                )
            prev_side[drawing_id] = side_curr

    return markers
