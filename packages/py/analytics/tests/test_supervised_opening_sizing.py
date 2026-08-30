"""V1.33 — resolve_supervised_opening_quantity (paridad TS T-SIZE-01/06)."""

from __future__ import annotations

from bolsa_analytics.cognitive.supervised_opening_sizing import (
    AUTO_OPENING_SOURCES,
    extract_hit_auto_source,
    extract_hit_trade_plan,
    is_allowed_auto_opening_source,
    resolve_supervised_opening_quantity,
)


def _triggered(qty: float = 42.0) -> dict:
    return {
        "status": "TRIGGERED",
        "quantity": qty,
        "direction": "long",
        "structuralStop": 95.0,
        "entry": 100.0,
    }


def test_resolve_supervised_opening_quantity_triggered() -> None:
    assert resolve_supervised_opening_quantity(_triggered(42)) == 42.0


def test_resolve_supervised_opening_quantity_ignores_server_suggested() -> None:
    assert (
        resolve_supervised_opening_quantity(
            _triggered(42),
            server_suggested_quantity=99.0,
        )
        == 42.0
    )


def test_resolve_supervised_opening_quantity_watch_is_none() -> None:
    plan = _triggered(42)
    plan["status"] = "WATCH"
    assert resolve_supervised_opening_quantity(plan) is None
    assert resolve_supervised_opening_quantity(None) is None


def test_extract_hit_trade_plan_and_source() -> None:
    hit = {
        "autoSource": "estudio_dictamen",
        "tradePlan": _triggered(10),
    }
    assert extract_hit_trade_plan(hit) == _triggered(10)
    assert extract_hit_auto_source(hit) == "estudio_dictamen"
    assert is_allowed_auto_opening_source("estudio_dictamen")
    assert is_allowed_auto_opening_source("estudio_alarma")
    assert not is_allowed_auto_opening_source("paper_d")
    assert not is_allowed_auto_opening_source(None)
    assert "estudio_dictamen" in AUTO_OPENING_SOURCES
