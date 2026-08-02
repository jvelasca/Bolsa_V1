"""Utilidades de timestamp para barras OHLCV (diario e intradía)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from bolsa_domain.value_objects.timeframe import TimeFrame


def parse_bar_timestamp(raw: str) -> datetime:
    """Convierte timestamp de dominio/API a datetime UTC."""
    if len(raw) == 10 and raw[4] == "-":
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_bar_timestamp(moment: datetime, timeframe: TimeFrame) -> str:
    """Serializa timestamp para DTOs según timeframe."""
    utc = moment.astimezone(UTC)
    if timeframe == TimeFrame.D1:
        return utc.date().isoformat()
    return utc.isoformat().replace("+00:00", "Z")


def bar_timestamp_from_date(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


REFRESH_TTL_SECONDS: dict[TimeFrame, int] = {
    TimeFrame.M1: 2 * 60,
    TimeFrame.M5: 10 * 60,
    TimeFrame.M15: 20 * 60,
    TimeFrame.M30: 30 * 60,
    TimeFrame.H1: 60 * 60,
    TimeFrame.H4: 4 * 60 * 60,
    TimeFrame.D1: 24 * 60 * 60,
    TimeFrame.W1: 7 * 24 * 60 * 60,
    TimeFrame.MO1: 30 * 24 * 60 * 60,
}


def is_cache_stale(timeframe: TimeFrame, latest_timestamp: str | None) -> bool:
    if latest_timestamp is None:
        return True
    latest = parse_bar_timestamp(latest_timestamp)
    age = (datetime.now(UTC) - latest).total_seconds()
    return age > REFRESH_TTL_SECONDS.get(timeframe, 60 * 60)
