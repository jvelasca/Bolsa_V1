"""Outcome / Learning v1.1 para DecisionSession."""

from bolsa_analytics.cognitive.decision_outcome import (
    attach_outcome_to_payload,
    build_manual_outcome,
    build_outcome_from_prices,
    resolve_eval_price_from_bars,
    summarize_session_outcomes,
    verdict_from_return,
)


def test_verdict_long_hit():
    v, hit = verdict_from_return(action="recommend_long", return_pct=2.0)
    assert v == "hit" and hit is True


def test_verdict_short_hit():
    v, hit = verdict_from_return(action="recommend_short", return_pct=-1.5)
    assert v == "hit" and hit is True


def test_verdict_neutral_band():
    v, hit = verdict_from_return(action="recommend_long", return_pct=0.2)
    assert v == "neutral" and hit is None


def test_verdict_wait_skipped():
    v, hit = verdict_from_return(action="wait", return_pct=3.0)
    assert v == "skipped" and hit is None


def test_build_outcome_from_prices():
    o = build_outcome_from_prices(
        action="recommend_long",
        horizon="swing",
        price_at_decision=100.0,
        price_at_eval=103.0,
    )
    assert o.verdict == "hit"
    assert o.eval_bars == 5
    assert o.return_pct == 3.0
    d = o.to_dict()
    assert d["criteriaVersion"] == "1.1.0"
    assert d["source"] == "auto_mark"
    assert d["mature"] is True


def test_attach_closes_session():
    payload = {"sessionId": "DSS-1", "status": "open", "recommendation": {"action": "wait"}}
    o = build_manual_outcome(action="wait", horizon="swing", verdict="skipped")
    next_p = attach_outcome_to_payload(payload, o)
    assert next_p["status"] == "closed"
    assert next_p["outcome"]["verdict"] == "skipped"


def test_summarize_hit_rate():
    payloads = [
        {"outcome": {"verdict": "hit", "horizon": "swing"}},
        {"outcome": {"verdict": "miss", "horizon": "swing"}},
        {"outcome": {"verdict": "neutral", "horizon": "swing"}},
        {"outcome": {"verdict": "skipped", "horizon": "intraday"}},
        {},
    ]
    s = summarize_session_outcomes(payloads)
    assert s["scored"] == 2
    assert s["hits"] == 1
    assert s["hitRate"] == 0.5
    assert s["byHorizon"]["swing"]["hit"] == 1


def test_summarize_separates_mature():
    payloads = [
        {"outcome": {"verdict": "hit", "horizon": "swing", "mature": True}},
        {"outcome": {"verdict": "miss", "horizon": "swing", "mature": True}},
        {
            "outcome": {
                "verdict": "hit",
                "horizon": "swing",
                "mature": False,
                "notes": "premature_mtm:1/5",
            }
        },
    ]
    s = summarize_session_outcomes(payloads)
    assert s["scored"] == 3
    assert s["matureScored"] == 2
    assert s["matureHitRate"] == 0.5
    assert s["prematureScored"] == 1
    assert s["hitRate"] == round(2 / 3, 4)


def test_resolve_eval_price_exact_plus_n():
    bars = [{"timestamp": f"2026-01-{i:02d}", "close": 100.0 + i} for i in range(1, 12)]
    # decisión el día 3 (close 103), swing → +5 → día 8 (close 108)
    r = resolve_eval_price_from_bars(
        bars,
        horizon="swing",
        decision_at="2026-01-03T15:00:00Z",
        price_at_decision=103.0,
    )
    assert r["mature"] is True
    assert r["barsElapsed"] == 5
    assert r["price"] == 108.0


def test_resolve_eval_price_premature():
    bars = [
        {"timestamp": "2026-01-01", "close": 100.0},
        {"timestamp": "2026-01-02", "close": 101.0},
        {"timestamp": "2026-01-03", "close": 102.0},
    ]
    r = resolve_eval_price_from_bars(
        bars,
        horizon="swing",
        decision_at="2026-01-02T12:00:00Z",
        price_at_decision=101.0,
    )
    assert r["mature"] is False
    assert r["barsElapsed"] == 1
    assert r["price"] == 102.0
    assert "premature_mtm" in str(r["notes"])
