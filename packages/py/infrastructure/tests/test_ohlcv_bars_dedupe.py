"""Dedupe defensivo antes del bulk upsert de OHLCV (gráfico MERCADO).

PostgreSQL aborta ``INSERT ... ON CONFLICT DO UPDATE`` cuando la misma fila
aparece dos veces en el VALUES. El parser de Yahoo puede repetir timestamps,
así que la frontera de persistencia los colapsa.
"""

from __future__ import annotations

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_infrastructure.database.repositories.ohlcv_repository import (
    dedupe_bars_by_timestamp,
)


def _bar(ts: str, close: float, volume: int = 10) -> OhlcvBar:
    return OhlcvBar(
        timestamp=ts,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=volume,
    )


def test_dedupe_keeps_last_reading_and_order() -> None:
    bars = [
        _bar("2026-11-02T17:30:00Z", 10, volume=1),
        _bar("2026-11-02T16:30:00Z", 9, volume=2),
        _bar("2026-11-02T17:30:00Z", 11, volume=3),
    ]

    deduped = dedupe_bars_by_timestamp(bars)

    assert len(deduped) == 2
    assert [ts.isoformat() for ts, _ in deduped] == [
        "2026-11-02T17:30:00+00:00",
        "2026-11-02T16:30:00+00:00",
    ]
    assert [bar.close for _, bar in deduped] == [11, 9]
    assert [bar.volume for _, bar in deduped] == [3, 2]


def test_dedupe_accepts_date_and_iso_for_same_day() -> None:
    bars = [
        _bar("2026-11-02", 10),
        _bar("2026-11-02T00:00:00Z", 12),
    ]

    deduped = dedupe_bars_by_timestamp(bars)

    assert len(deduped) == 1
    assert deduped[0][1].close == 12


def test_dedupe_empty_list() -> None:
    assert dedupe_bars_by_timestamp([]) == []
