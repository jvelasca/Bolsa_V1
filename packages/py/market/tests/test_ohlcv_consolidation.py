from datetime import date

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_market.ohlcv_consolidation import plan_daily_consolidation


def _bar(day: str, close: float) -> OhlcvBar:
    return OhlcvBar(
        timestamp=f"{day}T00:00:00+00:00",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        source="yahoo",
    )


def test_plan_inserts_new_bars() -> None:
    incoming = [_bar("2026-06-20", 10.0), _bar("2026-06-21", 10.5)]
    plan = plan_daily_consolidation({}, incoming)
    assert plan.inserted == 2
    assert plan.updated == 0
    assert plan.skipped == 0
    assert len(plan.to_write) == 2


def test_plan_updates_small_revision() -> None:
    existing = {"2026-06-20": _bar("2026-06-20", 10.0)}
    incoming = [_bar("2026-06-20", 10.05)]
    plan = plan_daily_consolidation(existing, incoming)
    assert plan.updated == 1
    assert plan.skipped == 0
    assert len(plan.to_write) == 1


def test_plan_skips_large_deviation() -> None:
    existing = {"2026-06-20": _bar("2026-06-20", 10.0)}
    incoming = [_bar("2026-06-20", 10.5)]
    plan = plan_daily_consolidation(existing, incoming, max_close_deviation_pct=2.0)
    assert plan.skipped == 1
    assert len(plan.to_write) == 0
    assert plan.skip_reasons
