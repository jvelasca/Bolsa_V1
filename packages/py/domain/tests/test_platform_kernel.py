import pytest

from bolsa_domain.platform_kernel import (
    MAX_SCAN_INSTRUMENTS_ASYNC,
    MAX_SCAN_INSTRUMENTS_SYNC,
    validate_kernel_timeframe,
    validate_scan_bar_limit,
    validate_scan_max_results,
    validate_scan_universe_size,
)


def test_validate_kernel_timeframe_accepts_1d_and_1wk() -> None:
    assert validate_kernel_timeframe("1d") == "1d"
    assert validate_kernel_timeframe("1wk") == "1wk"


def test_validate_kernel_timeframe_rejects_intraday() -> None:
    with pytest.raises(ValueError, match="1d"):
        validate_kernel_timeframe("1h")


def test_validate_scan_universe_sync_vs_async() -> None:
    validate_scan_universe_size(MAX_SCAN_INSTRUMENTS_SYNC, async_job=False)
    validate_scan_universe_size(MAX_SCAN_INSTRUMENTS_ASYNC, async_job=True)

    with pytest.raises(ValueError, match="sync"):
        validate_scan_universe_size(MAX_SCAN_INSTRUMENTS_SYNC + 1, async_job=False)

    with pytest.raises(ValueError, match="scans/jobs"):
        validate_scan_universe_size(501, async_job=False)

    with pytest.raises(ValueError, match="async"):
        validate_scan_universe_size(MAX_SCAN_INSTRUMENTS_ASYNC + 1, async_job=True)


def test_validate_scan_limits() -> None:
    validate_scan_bar_limit(50)
    validate_scan_max_results(100)
    with pytest.raises(ValueError):
        validate_scan_bar_limit(10)
