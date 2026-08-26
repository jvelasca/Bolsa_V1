"""ExecutionRecord OI-3 — UNKNOWN ≠ ERROR (ADR-034)."""

from bolsa_analytics.cognitive.execution_record import (
    build_execution_record,
    execution_outcome_copy,
)


def test_filled_is_executed_even_with_exception() -> None:
    rec = build_execution_record(
        filled=True,
        send_attempted=True,
        transaction_id="tx-1",
        exception="persist boom",
    )
    assert rec.outcome == "executed"
    assert rec.transaction_id == "tx-1"
    assert rec.send_attempted is True
    assert rec.reason is None
    assert rec.to_dict()["outcome"] == "executed"


def test_send_without_fill_is_unknown_never_error() -> None:
    rec = build_execution_record(send_attempted=True, exception="ledger timeout")
    assert rec.outcome == "unknown"
    assert rec.reason == "ledger timeout"
    assert rec.send_attempted is True
    assert rec.transaction_id is None
    assert rec.outcome != "error"
    assert rec.outcome != "not_executed"


def test_send_silence_is_unknown() -> None:
    rec = build_execution_record(send_attempted=True)
    assert rec.outcome == "unknown"
    assert rec.reason == "execute_exception"


def test_pre_send_exception_is_error() -> None:
    rec = build_execution_record(exception="journal boom")
    assert rec.outcome == "error"
    assert rec.send_attempted is False


def test_gate_before_send_is_not_executed() -> None:
    rec = build_execution_record(not_executed_reason="risk_signature")
    assert rec.outcome == "not_executed"
    assert rec.reason == "risk_signature"
    assert rec.send_attempted is False


def test_unknown_copy_does_not_claim_not_executed() -> None:
    assert "desconocido" in execution_outcome_copy("unknown").lower()
    assert "no asumir" in execution_outcome_copy("unknown").lower()
    assert "no ejecutado" in execution_outcome_copy("error").lower()
    assert execution_outcome_copy("not_executed") == "No se envió"
    assert execution_outcome_copy("executed") == "Ejecutado"
