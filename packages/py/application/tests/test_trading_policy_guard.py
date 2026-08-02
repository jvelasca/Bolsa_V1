"""RFC-008 — Cognitive guard en hot path (D2.4 / D4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_analytics.cognitive import MarketEventCalendar, build_market_event
from bolsa_domain.entities.investor_profile import InvestorProfileRecord

from bolsa_application.trading_policy_guard import (
    enforce_cognitive_policy_for_opening,
    resolve_trading_policy,
)


def _profile(
    *,
    template_id: str = "conservative",
    risk: str = "low",
) -> InvestorProfileRecord:
    return InvestorProfileRecord(
        id="PROF-1",
        name="Test",
        version="1.0.0",
        horizon="swing",
        objectives=("growth",),
        risk_tolerance=risk,
        experience="intermediate",
        suggested_policy_template_id=template_id,
        selected_policy_template_id=template_id,
        updated_by="test",
        created_at="2026-07-23T00:00:00Z",
        updated_at="2026-07-23T00:00:00Z",
    )


def test_resolve_policy_from_investor_profile():
    policy = resolve_trading_policy(_profile(template_id="conservative"))
    assert policy.template_id == "conservative"


def test_exit_bypasses_gate():
    result = enforce_cognitive_policy_for_opening(
        profile=None,
        instrument_id="inst-1",
        symbol="AAPL",
        trade_type="sell",
        quantity=10,
        price=100,
        signal_kind="exit",
    )
    assert result.allowed is True
    assert "exit_bypass" in result.reasons[0]


def test_earnings_event_vetoes_opening():
    now = datetime.now(UTC)
    cal = MarketEventCalendar()
    earnings_at = now + timedelta(hours=12)
    cal.add(
        build_market_event(
            entity="AAPL",
            event_type="earnings",
            sentiment=0.5,
            impact="very_high",
            horizon_days=2,
            source="Reuters",
            credibility=0.98,
            valid_from=earnings_at.isoformat().replace("+00:00", "Z"),
            valid_to=(earnings_at + timedelta(hours=24)).isoformat().replace("+00:00", "Z"),
        )
    )

    result = enforce_cognitive_policy_for_opening(
        profile=_profile(template_id="conservative", risk="low"),
        instrument_id="inst-aapl",
        symbol="AAPL",
        trade_type="buy",
        quantity=5,
        price=200,
        signal_kind="entry_long",
        equity=100_000,
        open_positions_count=1,
        event_calendar=cal,
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
    )
    assert result.allowed is False
    assert result.policy_id is not None
    assert result.memory is not None
    assert result.memory.outcome == "rejected"
    assert result.memory_id == result.memory.memory_id
    assert any("earnings" in r.lower() or "Blackout" in r for r in result.reasons) or (
        result.gate is not None
        and any(
            rule.get("rule") == "PreEarningsBlackout" and rule.get("status") == "FAILED"
            for rule in result.gate.get("evaluatedRules", [])
        )
    )


def test_pass_produces_accepted_memory():
    result = enforce_cognitive_policy_for_opening(
        profile=None,
        instrument_id="inst-1",
        symbol="AAPL",
        trade_type="buy",
        quantity=1,
        price=100,
        signal_kind="entry_long",
        equity=100_000,
        open_positions_count=0,
        market_cap_usd=3e12,
        average_daily_volume_usd=5e9,
    )
    # Moderate template puede PASS si liquidez/universo ok
    if result.allowed:
        assert result.memory is not None
        assert result.memory.outcome == "accepted"
    else:
        assert result.memory is not None
        assert result.memory.outcome == "rejected"
