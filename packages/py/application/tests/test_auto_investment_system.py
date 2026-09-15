"""AutoInvestmentSystem — composición del hot path + journal reason_codes (P0/P3)."""

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    build_auto_portfolio_snapshot,
)
from bolsa_analytics.cognitive.opportunity_ranker import score_opportunity
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.auto_investment_system import (
    EntryCandidate,
    is_research_only,
    run_auto_cycle,
)


def _snapshot() -> object:
    return build_auto_portfolio_snapshot(
        account_id="acct-1",
        capital=100_000.0,
        cash=80_000.0,
        equity=100_000.0,
        buying_power=80_000.0,
        risk_used=500.0,
        risk_budget=2_000.0,
        data_freshness=DATA_FRESH,
    )


def _score(instrument_id: str, combined: float) -> object:
    return score_opportunity(
        instrument_id,
        edge=combined,
        robustness=combined,
        regime_fit=combined,
        momentum=combined,
        liquidity=combined,
        risk_reward=combined,
        execution_quality=combined,
    )


def _candidate(symbol: str, *, source: str = "active") -> EntryCandidate:
    """Candidato con cartera CONOCIDA (V2.40.1: sin sector/liquidez no hay entrada)."""
    return EntryCandidate(
        instrument_id=symbol,
        entry_price=100.0,
        atr=2.0,
        sector="tech",
        liquidity_notional=1_000_000.0,
        source=source,
    )


def test_is_research_only() -> None:
    assert is_research_only("active") is False
    assert is_research_only("discovery") is True
    assert is_research_only("adaptive") is True
    assert is_research_only("param_region") is True
    assert is_research_only("regime_learning") is True


def test_full_cycle_entry_and_journal() -> None:
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[_score("AAPL", 0.8)],
        candidates={"AAPL": _candidate("AAPL")},
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )
    assert report.regime == "BULL_TREND"
    assert len(report.decisions) == 1
    assert report.decisions[0].approved is True
    assert report.trade_plans[0].instrument_id == "AAPL"
    assert len(report.journal_entries) == 1
    payload = report.journal_entries[0].payload
    assert payload["reasonCodes"] == ["approved"]
    assert payload["tradePlan"]["status"] == "TRIGGERED"


def test_research_candidates_never_trade() -> None:
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[_score("AAPL", 0.9)],
        candidates={"AAPL": _candidate("AAPL", source="adaptive")},
        regime="BULL_TREND",
    )
    assert report.decisions == ()
    assert report.research_allocations == ("AAPL",)
    assert report.journal_entries == ()


def test_no_trade_journal_reason_codes() -> None:
    # edge 0.2 < 0.5 ⇒ rechazo edge_below_threshold, journal con reason_code.
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[_score("AAPL", 0.2)],
        candidates={"AAPL": _candidate("AAPL")},
        regime="BULL_TREND",
    )
    assert len(report.decisions) == 1
    assert report.decisions[0].approved is False
    assert report.decisions[0].is_no_trade is True
    payload = report.journal_entries[0].payload
    assert "edge_below_threshold" in payload["reasonCodes"]
    assert payload["approved"] is False


def test_position_management_and_journal() -> None:
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAPL",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 105.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[],
        candidates={},
        regime="BULL_TREND",
        open_positions=[pos],
        marks={"AAPL": 95.0},
        as_of="2026-09-15T09:00:00Z",
    )
    assert len(report.position_results) == 1
    assert report.position_results[0].order_action == "sell"
    assert len(report.journal_entries) == 1
    payload = report.journal_entries[0].payload
    assert "structural_stop" in payload["exitReasons"]


def test_regime_exit_only_full_report() -> None:
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAPL",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[],
        candidates={},
        regime="",  # UNKNOWN ⇒ exit-only
        open_positions=[pos],
        marks={"AAPL": 101.0},
    )
    assert report.regime == "UNKNOWN"
    assert report.position_results[0].order_action == "sell"
    assert "regime_exit" in report.journal_entries[0].payload["exitReasons"]


def test_top_n_limits_trading_universe() -> None:
    candidates = {s: _candidate(s) for s in ("A", "B", "C", "D", "E", "F")}
    opportunities = [
        _score("F", 0.95),
        _score("E", 0.9),
        _score("D", 0.85),
        _score("C", 0.8),
        _score("B", 0.7),
        _score("A", 0.6),
    ]
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=opportunities,
        candidates=candidates,
        regime="BULL_TREND",
        top_n=3,
    )
    # Solo TOP 3 tienen score y por tanto entran al pipeline; el resto no tiene score
    # ⇒ score None ⇒ edge_below_threshold (no operan).
    traded = [d.instrument_id for d in report.decisions if d.approved]
    assert set(traded) == {"F", "E", "D"}


def test_report_to_dict() -> None:
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[_score("AAPL", 0.8)],
        candidates={"AAPL": _candidate("AAPL")},
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )
    d = report.to_dict()
    assert d["regime"] == "BULL_TREND"
    assert len(d["decisions"]) == 1
    assert len(d["journalEntries"]) == 1


def test_candidate_without_trade_context_is_not_traded() -> None:
    """V2.40.1: un candidato sin sector/liquidez conocidos NO opera (fail-closed)."""
    report = run_auto_cycle(
        snapshot=_snapshot(),
        opportunities=[_score("AAPL", 0.8)],
        candidates={
            "AAPL": EntryCandidate(
                instrument_id="AAPL", entry_price=100.0, atr=2.0, source="active"
            )
        },
        regime="BULL_TREND",
    )
    assert report.decisions[0].approved is False
    assert report.decisions[0].reason_codes == ("liquidity_unknown",)
