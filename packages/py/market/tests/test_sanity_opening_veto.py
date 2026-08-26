"""F5 — sanity_opening_veto_reason → check_opening DS-05."""

from __future__ import annotations

from datetime import UTC, datetime

from bolsa_application.risk_engine import check_opening
from bolsa_market.sanity import sanity_opening_veto_reason


def test_sanity_opening_veto_reason_detects_split_move() -> None:
    warning = "movimiento 62.50% en 2024-06-01 — revisar split/dividendo"
    reason = sanity_opening_veto_reason((warning,))
    assert reason is not None
    assert reason.startswith("data_freshness:sanity_anomaly:")


def test_sanity_opening_veto_ignores_gap_only() -> None:
    assert sanity_opening_veto_reason(("gap de 12 días entre 2024-01-01 y 2024-01-13",)) is None


def test_check_opening_ds05_sanity_anomaly_denies() -> None:
    now = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)
    warning = "movimiento 55.00% en 2026-08-20 — revisar split/dividendo"
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="entry_long",
        last_bar_timestamp="2026-08-24",
        require_fresh_data=True,
        freshness_now=now,
        sanity_warnings=(warning,),
    )
    assert d.verdict == "DENY"
    assert d.reasons[0].startswith("data_freshness:sanity_anomaly:")
    assert d.guard is None


def test_check_opening_exit_skips_sanity_veto() -> None:
    now = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)
    warning = "movimiento 55.00% en 2026-08-20 — revisar split/dividendo"
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="sell",
        quantity=1,
        price=10,
        signal_kind="exit",
        last_bar_timestamp="2020-01-01",
        require_fresh_data=True,
        freshness_now=now,
        sanity_warnings=(warning,),
    )
    assert d.verdict == "ALLOW"
