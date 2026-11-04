from datetime import UTC, date, datetime

from bolsa_market.yahoo_chart import (
    dedupe_intraday_bars,
    parse_chart_payload,
    parse_intraday_chart_payload,
    strip_live_bar_from_payload,
)
from bolsa_market.yahoo_client import YahooSymbolNotFoundError, normalize_yahoo_error


def test_parse_chart_payload_maps_daily_bars() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704067200, 1704153600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 10.5],
                                "high": [10.8, 11.0],
                                "low": [9.8, 10.2],
                                "close": [10.4, 10.9],
                                "volume": [1000, 1100],
                            }
                        ],
                        "adjclose": [{"adjclose": [10.4, 10.9]}],
                    },
                }
            ]
        }
    }

    bars = parse_chart_payload(payload, "AENA.MC")
    assert len(bars) == 2
    assert bars[0].timestamp == date(2024, 1, 1)
    assert float(bars[1].close) == 10.9


def test_parse_intraday_chart_payload_maps_iso_timestamps() -> None:
    ts = int(datetime(2024, 6, 15, 14, 30, tzinfo=UTC).timestamp())
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [ts],
                    "indicators": {
                        "quote": [
                            {
                                "open": [150.0],
                                "high": [151.0],
                                "low": [149.5],
                                "close": [150.5],
                                "volume": [50000],
                            }
                        ],
                    },
                }
            ]
        }
    }

    bars = parse_intraday_chart_payload(payload, "AAPL")
    assert len(bars) == 1
    assert bars[0].timestamp.endswith("Z")
    assert float(bars[0].close) == 150.5
    assert bars[0].volume == 50000


def test_parse_intraday_rejects_incoherent_ohlc() -> None:
    from bolsa_market.ohlcv_quarantine import get_ohlcv_quarantine_stats

    stats = get_ohlcv_quarantine_stats()
    stats.reset()
    ts = int(datetime(2024, 6, 15, 14, 30, tzinfo=UTC).timestamp())
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [ts, ts + 60],
                    "indicators": {
                        "quote": [
                            {
                                "open": [150.0, 10.0],
                                "high": [149.0, 11.0],  # first bar high < open/close
                                "low": [148.0, 9.5],
                                "close": [150.5, 10.5],
                                "volume": [1, 2],
                            }
                        ],
                    },
                }
            ]
        }
    }
    bars = parse_intraday_chart_payload(payload, "AAPL")
    assert len(bars) == 1
    assert float(bars[0].open) == 10.0
    snap = stats.snapshot()
    assert snap["intradaily_rejected"] >= 1
    assert snap["by_reason"].get("ohlc_invalid", 0) >= 1


def test_parse_daily_quarantines_incoherent_ohlc() -> None:
    from bolsa_market.ohlcv_quarantine import get_ohlcv_quarantine_stats

    stats = get_ohlcv_quarantine_stats()
    stats.reset()
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704067200, 1704153600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 10.5],
                                "high": [9.0, 11.0],  # first bar high < open
                                "low": [8.0, 10.2],
                                "close": [10.4, 10.9],
                                "volume": [1000, 1100],
                            }
                        ],
                        "adjclose": [{"adjclose": [10.4, 10.9]}],
                    },
                }
            ]
        }
    }
    bars = parse_chart_payload(payload, "AENA.MC")
    assert len(bars) == 1
    assert float(bars[0].close) == 10.9
    assert stats.snapshot()["daily_rejected"] >= 1


def _intraday_payload(timestamps: list[int], regular_market_time: int | None) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "meta": (
                        {} if regular_market_time is None else {"regularMarketTime": regular_market_time}
                    ),
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0 for _ in timestamps],
                                "high": [101.0 for _ in timestamps],
                                "low": [99.0 for _ in timestamps],
                                "close": [100.5 for _ in timestamps],
                                "volume": [1000 for _ in timestamps],
                            }
                        ],
                    },
                }
            ]
        }
    }


def test_strip_live_bar_drops_yahoo_partial_candle() -> None:
    first = int(datetime(2026, 11, 2, 17, 30, tzinfo=UTC).timestamp())
    live = int(datetime(2026, 11, 2, 18, 27, 25, tzinfo=UTC).timestamp())
    payload = _intraday_payload([first, live], live)

    bars = parse_intraday_chart_payload(payload, "AAPL")
    assert len(bars) == 2

    kept = strip_live_bar_from_payload(payload, bars)
    assert len(kept) == 1
    assert kept[0].timestamp.startswith("2026-11-02T17:30")


def test_strip_live_bar_keeps_weekly_period_start() -> None:
    week_start = int(datetime(2026, 11, 2, 6, 0, tzinfo=UTC).timestamp())
    live = int(datetime(2026, 11, 2, 18, 27, 25, tzinfo=UTC).timestamp())
    payload = _intraday_payload([week_start], live)

    bars = parse_intraday_chart_payload(payload, "AAPL")
    kept = strip_live_bar_from_payload(payload, bars)
    assert len(kept) == 1
    assert kept[0].timestamp.startswith("2026-11-02T06:00")


def test_strip_live_bar_without_meta_is_noop() -> None:
    first = int(datetime(2026, 11, 2, 17, 30, tzinfo=UTC).timestamp())
    payload = _intraday_payload([first], None)
    bars = parse_intraday_chart_payload(payload, "AAPL")
    assert len(strip_live_bar_from_payload(payload, bars)) == 1


def test_dedupe_intraday_bars_keeps_last_reading() -> None:
    from bolsa_market.yahoo_chart import IntradayOhlcvBar

    bars = [
        IntradayOhlcvBar(timestamp="2026-11-02T17:30:00Z", open=1, high=2, low=1, close=1.5, volume=10),
        IntradayOhlcvBar(timestamp="2026-11-02T17:30:00Z", open=1, high=3, low=1, close=2.5, volume=20),
    ]
    deduped = dedupe_intraday_bars(bars)
    assert len(deduped) == 1
    assert deduped[0].close == 2.5
    assert deduped[0].volume == 20


def test_normalize_yahoo_error_rate_limit() -> None:
    message = normalize_yahoo_error(RuntimeError("429 Too Many Requests"))
    assert "429" in message
    assert "Espera" in message


def test_normalize_yahoo_error_symbol_not_found() -> None:
    message = normalize_yahoo_error(YahooSymbolNotFoundError("BP/.L (404)"))
    assert "no encontró histórico" in message
    assert "AENA.MC" in message


def test_normalize_yahoo_error_circuit_open() -> None:
    from bolsa_market.yahoo_circuit_breaker import YahooCircuitOpenError

    message = normalize_yahoo_error(YahooCircuitOpenError("Yahoo circuit OPEN"))
    assert "cooldown" in message.lower() or "circuit" in message.lower()
