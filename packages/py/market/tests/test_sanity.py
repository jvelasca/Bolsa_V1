from datetime import date
from decimal import Decimal

import pytest

from bolsa_market.ingest import OhlcvBarIngest
from bolsa_market.sanity import run_sanity_checks


def _bar(day: int, close: str = "10.0") -> OhlcvBarIngest:
    return OhlcvBarIngest(
        timestamp=date(2024, 1, day),
        open=Decimal("10.0"),
        high=Decimal("10.5"),
        low=Decimal("9.5"),
        close=Decimal(close),
        volume=1_000_000,
    )


def test_sanity_accepts_valid_series() -> None:
    report = run_sanity_checks([_bar(2), _bar(3), _bar(4)])
    assert report.valid is True
    assert report.bar_count == 3


def test_sanity_rejects_duplicate_timestamp() -> None:
    report = run_sanity_checks([_bar(2), _bar(2)])
    assert report.valid is False
    assert any("duplicado" in e for e in report.errors)


def test_ingest_rejects_invalid_ohlc() -> None:
    with pytest.raises(ValueError, match="high"):
        OhlcvBarIngest(
            timestamp=date(2024, 1, 2),
            open=Decimal(10),
            high=Decimal(9),
            low=Decimal(8),
            close=Decimal(10),
            volume=100,
        )
