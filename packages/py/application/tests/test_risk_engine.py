"""OR-RE — Risk Engine façade tests."""

from datetime import UTC, datetime, timedelta

from bolsa_application.risk_engine import (
    DATA_FRESHNESS_MAX_AGE_SECONDS,
    RISK_ENGINE_VERSION,
    check_opening,
    data_freshness_veto_reason,
)
from bolsa_application.account_mandate_gate import account_mandate_veto_reason


def test_kill_switch_denies_before_gate() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="entry_long",
        kill_switch=True,
    )
    assert d.verdict == "DENY"
    assert d.allowed is False
    assert d.reasons == ("kill_switch_active",)
    assert d.guard is None
    assert d.engine_version == RISK_ENGINE_VERSION


def test_book_max_open_denies() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="entry_long",
        open_positions_count=10,
        book_max_open_positions=10,
    )
    assert d.verdict == "DENY"
    assert "book_max_open_positions" in d.reasons[0]
    assert d.guard is None


def test_exit_still_allowed_via_gate_bypass() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="sell",
        quantity=1,
        price=10,
        signal_kind="exit",
        kill_switch=False,
        open_positions_count=99,
        book_max_open_positions=1,
    )
    # book max only applies to buy; exit goes to gate bypass
    assert d.verdict == "ALLOW"
    assert d.guard is not None
    assert d.guard.allowed is True


def test_ds05_fresh_bar_allows() -> None:
    from bolsa_analytics.cognitive.portfolio_fit import BasketPosition

    now = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)
    d = check_opening(
        profile=None,
        instrument_id="i-new",
        symbol="SAN",
        trade_type="buy",
        quantity=4.0,
        price=1.0,
        signal_kind="entry_long",
        equity=200.0,
        open_positions_count=4,
        portfolio_positions=[
            BasketPosition("a", 4.0, "tech"),
            BasketPosition("b", 4.0, "health"),
            BasketPosition("c", 4.0, "energy"),
            BasketPosition("d", 4.0, "cons"),
        ],
        proposal_sector="industrials",
        last_bar_timestamp="2026-08-24",
        require_fresh_data=True,
        freshness_now=now,
    )
    assert d.verdict == "ALLOW"
    assert d.allowed is True
    assert not any(r.startswith("data_freshness:") for r in d.reasons)


def test_ds05_stale_bar_denies() -> None:
    now = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)
    stale = (now - timedelta(seconds=DATA_FRESHNESS_MAX_AGE_SECONDS + 3600)).date().isoformat()
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="entry_long",
        last_bar_timestamp=stale,
        require_fresh_data=True,
        freshness_now=now,
    )
    assert d.verdict == "DENY"
    assert d.reasons[0].startswith("data_freshness:stale:")
    assert d.guard is None


def test_ds05_missing_bar_require_denies() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="recommend_long",
        last_bar_timestamp=None,
        require_fresh_data=True,
    )
    assert d.verdict == "DENY"
    assert d.reasons == ("data_freshness:missing",)


def test_ds05_exit_skips_freshness_gate() -> None:
    """Cierres no quedan atrapados por datos stale."""
    now = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)
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
    )
    assert d.verdict == "ALLOW"


def test_data_freshness_veto_reason_helper() -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    assert data_freshness_veto_reason(None, require=False) is None
    assert data_freshness_veto_reason(None, require=True) == "data_freshness:missing"
    assert (
        data_freshness_veto_reason("2026-08-24T11:00:00Z", now=now, max_age_seconds=7200)
        is None
    )
    reason = data_freshness_veto_reason(
        "2026-08-20T00:00:00Z", now=now, max_age_seconds=86_400
    )
    assert reason is not None
    assert reason.startswith("data_freshness:stale:")


def test_ds03_no_open_tenure_denies() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="recommend_long",
        has_open_mandate=False,
        require_account_mandate=True,
    )
    assert d.verdict == "DENY"
    assert d.reasons == ("account_mandate:no_open_tenure",)
    assert d.guard is None


def test_ds03_open_tenure_allows() -> None:
    from bolsa_analytics.cognitive.portfolio_fit import BasketPosition

    d = check_opening(
        profile=None,
        instrument_id="i-new",
        symbol="SAN",
        trade_type="buy",
        quantity=4.0,
        price=1.0,
        signal_kind="entry_long",
        equity=200.0,
        open_positions_count=4,
        portfolio_positions=[
            BasketPosition("a", 4.0, "tech"),
            BasketPosition("b", 4.0, "health"),
            BasketPosition("c", 4.0, "energy"),
            BasketPosition("d", 4.0, "cons"),
        ],
        proposal_sector="industrials",
        has_open_mandate=True,
        mandate_strategy_id="st-mandate",
        require_account_mandate=True,
        proposal_strategy_id="st-mandate",
    )
    assert d.verdict == "ALLOW"


def test_ds03_strategy_mismatch_denies() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="entry_long",
        has_open_mandate=True,
        mandate_strategy_id="st-a",
        require_account_mandate=True,
        proposal_strategy_id="st-b",
    )
    assert d.verdict == "DENY"
    assert d.reasons[0].startswith("account_mandate:strategy_mismatch:")


def test_ds03_exit_skips_mandate_gate() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="sell",
        quantity=1,
        price=10,
        signal_kind="exit",
        has_open_mandate=False,
        require_account_mandate=True,
    )
    assert d.verdict == "ALLOW"


def test_account_mandate_veto_reason_helper() -> None:
    assert account_mandate_veto_reason(has_open_tenure=False, require=False) is None
    assert (
        account_mandate_veto_reason(has_open_tenure=False, require=True)
        == "account_mandate:no_open_tenure"
    )
    assert account_mandate_veto_reason(
        has_open_tenure=True,
        require=True,
        mandate_strategy_id="a",
        proposal_strategy_id="b",
    ).startswith("account_mandate:strategy_mismatch:")
