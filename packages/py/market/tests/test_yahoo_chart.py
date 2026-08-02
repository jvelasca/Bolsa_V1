from datetime import date, datetime, timezone

from bolsa_market.yahoo_chart import parse_chart_payload, parse_intraday_chart_payload
from bolsa_market.yahoo_client import normalize_yahoo_error


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
    ts = int(datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc).timestamp())
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
    ts = int(datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc).timestamp())
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


def test_normalize_yahoo_error_rate_limit() -> None:
    message = normalize_yahoo_error(RuntimeError("429 Too Many Requests"))
    assert "429" in message
    assert "Espera" in message
