"""Calidad de datos v1 — score ligero para scan híbrido (sin XTB)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

DATA_QUALITY_V1_VERSION = "1.0.0"
MODEL_ID = "data_quality_v1"

IDEAL_BAR_DEPTH = 500
MIN_USABLE_BARS = 50


@dataclass(frozen=True, slots=True)
class DataQualityBreakdown:
    freshness: float
    bar_depth: float
    sync: float
    gaps: float
    fundamentals: float
    total: float
    model_id: str = MODEL_ID
    model_version: str = DATA_QUALITY_V1_VERSION

    def to_dict(self) -> dict[str, float | str]:
        return {
            "freshness": round(self.freshness, 2),
            "barDepth": round(self.bar_depth, 2),
            "sync": round(self.sync, 2),
            "gaps": round(self.gaps, 2),
            "fundamentals": round(self.fundamentals, 2),
            "total": round(self.total, 2),
            "modelId": self.model_id,
            "modelVersion": self.model_version,
        }


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _business_days_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def count_recent_weekday_gaps(timestamps: list[str], *, max_bars: int = 90) -> int:
    """Cuenta huecos de días hábiles entre barras recientes."""
    dates = sorted({_parse_date(ts) for ts in timestamps[-max_bars:] if _parse_date(ts) is not None})
    if len(dates) < 2:
        return 0

    gap_count = 0
    for index in range(1, len(dates)):
        missing = _business_days_between(dates[index - 1], dates[index]) - 1
        if missing > 0:
            gap_count += missing
    return gap_count


def _score_freshness(last_bar: date | None, expected_last_bar: date | None) -> float:
    if last_bar is None:
        return 0.0
    if expected_last_bar is None:
        return 70.0

    lag_days = _business_days_between(last_bar, expected_last_bar)
    if last_bar >= expected_last_bar:
        return 100.0
    if lag_days <= 1:
        return 85.0
    if lag_days <= 3:
        return 60.0
    if lag_days <= 5:
        return 35.0
    return 10.0


def _score_bar_depth(bar_count: int) -> float:
    if bar_count >= IDEAL_BAR_DEPTH:
        return 100.0
    if bar_count >= 200:
        return 85.0
    if bar_count >= MIN_USABLE_BARS:
        return 65.0 + (bar_count - MIN_USABLE_BARS) / (200 - MIN_USABLE_BARS) * 20.0
    return _clamp(bar_count / MIN_USABLE_BARS * 50.0)


def _score_sync(last_sync_status: str | None, last_sync_error: str | None) -> float:
    if last_sync_status is None:
        return 60.0
    normalized = last_sync_status.lower()
    if normalized in {"ok", "success", "completed"}:
        return 100.0 if not last_sync_error else 80.0
    if normalized in {"pending", "running", "syncing"}:
        return 70.0
    if normalized in {"failed", "error"}:
        return 15.0
    return 55.0


def _score_gaps(gap_count: int) -> float:
    if gap_count <= 0:
        return 100.0
    if gap_count == 1:
        return 75.0
    if gap_count <= 3:
        return 45.0
    return 15.0


def _score_fundamentals(*, has_fundamental_gate: bool, fundamentals_ok: bool) -> float:
    if not has_fundamental_gate:
        return 100.0
    return 100.0 if fundamentals_ok else 25.0


def compute_data_quality_v1(
    *,
    bar_count: int,
    last_bar_timestamp: str | None,
    expected_last_bar_date: str | None = None,
    last_sync_status: str | None = None,
    last_sync_error: str | None = None,
    recent_timestamps: list[str] | None = None,
    has_fundamental_gate: bool = False,
    fundamentals_ok: bool = True,
) -> DataQualityBreakdown:
    last_bar = _parse_date(last_bar_timestamp)
    expected = _parse_date(expected_last_bar_date)
    gap_count = count_recent_weekday_gaps(recent_timestamps or [])

    freshness = _score_freshness(last_bar, expected)
    bar_depth = _score_bar_depth(bar_count)
    sync = _score_sync(last_sync_status, last_sync_error)
    gaps = _score_gaps(gap_count)
    fundamentals = _score_fundamentals(
        has_fundamental_gate=has_fundamental_gate,
        fundamentals_ok=fundamentals_ok,
    )

    total = _clamp(
        freshness * 0.35
        + bar_depth * 0.25
        + sync * 0.20
        + gaps * 0.10
        + fundamentals * 0.10,
    )

    return DataQualityBreakdown(
        freshness=freshness,
        bar_depth=bar_depth,
        sync=sync,
        gaps=gaps,
        fundamentals=fundamentals,
        total=total,
    )


def compute_global_score(setup_score: float, data_quality_score: float) -> float:
    return round(_clamp(0.7 * setup_score + 0.3 * data_quality_score), 2)


def compute_bar_data_quality_at_index(
    bars: list,
    index: int,
    *,
    gap_lookback: int = 90,
) -> float | None:
    if index < 0:
        return None
    timestamps = [bar.timestamp for bar in bars[: index + 1][-gap_lookback:]]
    bar_depth = _score_bar_depth(index + 1)
    gaps = _score_gaps(count_recent_weekday_gaps(timestamps))
    return _clamp(bar_depth * 0.6 + gaps * 0.4)


def compute_bar_data_quality_series_v1(
    bars: list,
    *,
    gap_lookback: int = 90,
) -> list[float | None]:
    return [
        compute_bar_data_quality_at_index(bars, index, gap_lookback=gap_lookback)
        for index in range(len(bars))
    ]
