from bolsa_domain.platform_kernel import validate_execution_mode

from bolsa_application.execution_router import signal_kind_to_trade_type


def test_signal_kind_to_trade_type() -> None:
    assert signal_kind_to_trade_type("entry_long") == "buy"
    assert signal_kind_to_trade_type("exit") == "sell"
    assert signal_kind_to_trade_type("watch") is None


def test_validate_execution_mode() -> None:
    assert validate_execution_mode("paper_auto") == "paper_auto"
    try:
        validate_execution_mode("invalid")
    except ValueError as exc:
        assert "mode debe ser" in str(exc)
    else:
        raise AssertionError("expected ValueError")
