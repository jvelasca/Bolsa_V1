"""Tests A0 — telemetría dictamen (funciones puras)."""

from datetime import date

from bolsa_application.daily_opinion_telemetry import forward_return_pct, score_buy_alarma


def test_forward_return_needs_n_bars() -> None:
    closes = {
        date(2026, 8, 3): 100.0,
        date(2026, 8, 4): 101.0,
        date(2026, 8, 5): 102.0,
    }
    assert forward_return_pct(closes, date(2026, 8, 3), forward_bars=5) is None


def test_forward_return_5_bars() -> None:
    closes = {
        date(2026, 8, 3): 100.0,
        date(2026, 8, 4): 100.0,
        date(2026, 8, 5): 100.0,
        date(2026, 8, 6): 100.0,
        date(2026, 8, 7): 100.0,
        date(2026, 8, 10): 110.0,
    }
    ret = forward_return_pct(closes, date(2026, 8, 3), forward_bars=5)
    assert ret is not None
    assert abs(ret - 10.0) < 1e-6


def test_score_buy_alarma_hit_miss() -> None:
    v, hit = score_buy_alarma(2.0)
    assert v == "hit" and hit is True
    v2, hit2 = score_buy_alarma(-2.0)
    assert v2 == "miss" and hit2 is False
    v3, hit3 = score_buy_alarma(0.1)
    assert v3 == "neutral" and hit3 is None
