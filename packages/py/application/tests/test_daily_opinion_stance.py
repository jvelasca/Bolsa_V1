"""Invariantes StanceEngine v0 (ADR-022 / triage R3 §5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_application.daily_opinion_stance import (
    StanceInput,
    compute_stance,
    is_top_stale,
    map_io_to_stars,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def _base(**overrides: object) -> StanceInput:
    data: dict[str, object] = {
        "has_eod_bar": True,
        "allow_trading": True,
        "has_top": True,
        "top_updated_at": NOW - timedelta(days=1),
        "top_stars": 4.0,
        "io_score": 70.0,
        "fa_distress": False,
        "position_open": False,
    }
    data.update(overrides)
    return StanceInput(**data)  # type: ignore[arg-type]


def test_gate_veto_forces_no_trade() -> None:
    r = compute_stance(_base(allow_trading=False), now=NOW)
    assert r.stance == "no_trade"
    assert r.gate_status == "VETO"
    assert "gate_veto" in r.reasons
    assert r.dictamen_stars == 1


def test_eod_stale_fail_closed() -> None:
    r = compute_stance(_base(has_eod_bar=False), now=NOW)
    assert r.stance == "no_trade"
    assert "eod_data_stale" in r.reasons
    assert r.gate_status == "VETO"


def test_top_stale_review_strategy() -> None:
    stale = NOW - timedelta(days=31)
    assert is_top_stale(stale, now=NOW) is True
    r = compute_stance(_base(top_updated_at=stale), now=NOW)
    assert r.stance == "review_strategy"
    assert "stale_top" in r.reasons


def test_no_top_review_strategy() -> None:
    r = compute_stance(_base(has_top=False, top_updated_at=None), now=NOW)
    assert r.stance == "review_strategy"
    assert "no_valid_top" in r.reasons


def test_fa_distress_never_buy_and_stars_capped() -> None:
    r = compute_stance(
        _base(fa_distress=True, io_score=90.0, position_open=False),
        now=NOW,
    )
    assert r.stance == "no_trade"
    assert r.stance != "buy"
    assert r.dictamen_stars <= 3
    assert "fa_distress" in r.reasons


def test_fa_distress_with_position_reduces() -> None:
    r = compute_stance(
        _base(fa_distress=True, io_score=50.0, position_open=True),
        now=NOW,
    )
    assert r.stance == "reduce"
    assert r.dictamen_stars <= 3


def test_sell_exit_only_with_open_long() -> None:
    closed = compute_stance(_base(io_score=20.0, position_open=False), now=NOW)
    assert closed.stance not in ("sell_exit", "reduce")

    open_pos = compute_stance(_base(io_score=20.0, position_open=True), now=NOW)
    assert open_pos.stance == "sell_exit"


def test_reduce_only_with_open_long() -> None:
    closed = compute_stance(_base(io_score=40.0, position_open=False), now=NOW)
    assert closed.stance not in ("sell_exit", "reduce")

    open_pos = compute_stance(_base(io_score=40.0, position_open=True), now=NOW)
    assert open_pos.stance == "reduce"


def test_strong_buy_requires_io_and_top() -> None:
    r = compute_stance(
        _base(io_score=85.0, top_stars=4.0, position_open=False),
        now=NOW,
    )
    assert r.stance == "buy"
    assert r.dictamen_stars >= 4


def test_stance_never_null_and_stars_range() -> None:
    r = compute_stance(_base(), now=NOW)
    assert r.stance is not None
    assert 1 <= r.dictamen_stars <= 5


def test_unmeasured_position_never_recommends_and_declares_the_gap() -> None:
    """R-1/H-156-1 — con la cartera sin medir NO se emite dictamen de entrada/salida."""
    # Incluso con señal de compra fuerte: el hueco de cartera manda.
    r = compute_stance(_base(position_open=None, io_score=90.0, top_stars=5.0), now=NOW)
    assert r.stance == "no_trade"
    assert r.stance != "buy"
    assert "position_unmeasured" in r.reasons
    assert r.gate_status == "WARNING"

    # Tampoco se inventa una salida (no se sabe si hay posición).
    r_low = compute_stance(_base(position_open=None, io_score=20.0), now=NOW)
    assert r_low.stance == "no_trade"
    assert r_low.stance not in ("sell_exit", "reduce")


def test_unmeasured_io_is_declared_without_changing_the_star_rule() -> None:
    """El IO ausente sigue valiendo 3★ (Δ decisión = 0) pero el motivo se declara."""
    r = compute_stance(_base(io_score=None), now=NOW)
    assert r.dictamen_stars == 3
    assert "io_unmeasured" in r.reasons


def test_map_io_to_stars_boundaries() -> None:
    assert map_io_to_stars(None) == 3
    assert map_io_to_stars(80) == 5
    assert map_io_to_stars(65) == 4
    assert map_io_to_stars(45) == 3
    assert map_io_to_stars(30) == 2
    assert map_io_to_stars(10) == 1
