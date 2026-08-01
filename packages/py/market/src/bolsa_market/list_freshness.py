"""Frescura diaria ligera para filas de lista (sin gap scan completo)."""

from __future__ import annotations

from typing import Literal

from bolsa_market.market_calendar import expected_last_daily_bar

ListFreshnessStatus = Literal["current", "stale", "empty", "error"]


def resolve_list_freshness(
    *,
    bar_count: int,
    last_bar_date: str | None,
    last_sync_status: str | None,
    exchange: str,
    country: str,
) -> tuple[ListFreshnessStatus, str]:
    """Devuelve (estado, fecha esperada ISO YYYY-MM-DD)."""
    expected = expected_last_daily_bar(exchange=exchange, country=country).isoformat()
    if bar_count <= 0 or not last_bar_date:
        return "empty", expected
    last = last_bar_date[:10]
    if last < expected:
        if last_sync_status == "failed":
            return "error", expected
        return "stale", expected
    if last_sync_status == "failed":
        return "error", expected
    return "current", expected
