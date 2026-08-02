"""Q2.6 FA copiloto guardrails."""

from bolsa_analytics.knowledge.fundamental_copilot import (
    sanitize_copilot_query,
    validate_copilot_does_not_invent_roe,
)


def test_sanitize_copilot_query_trims() -> None:
    assert sanitize_copilot_query("  hola   mundo  ") == "hola mundo"


def test_validate_roe_guardrail() -> None:
    card = {"facts": {"roe": 0.15}}
    assert validate_copilot_does_not_invent_roe("ROE 15.0% sólido", card) == []
    assert validate_copilot_does_not_invent_roe("ROE 40% excepcional", card)
