"""OR-RE — Risk Engine façade tests."""

from bolsa_application.risk_engine import RISK_ENGINE_VERSION, check_opening


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
