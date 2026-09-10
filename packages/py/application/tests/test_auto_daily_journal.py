"""V2.22 / A9 (M7) — Journal/diario AUTO SIM-ONLY: invariantes del día.

Unit tests del *builder* puro (auto_daily_journal): conteo de un recorrido de día
autónomo y evaluación de los invariantes orders>0/fills>0/positions>0/exits>0/
ledger_balanced/no_duplicate_execution_events/all_venues in {paper,simulated}/
no_live_bridge_posts.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_application.auto_daily_journal import (
    SimJournalRow,
    build_auto_daily_report,
    execution_events_are_unique,
    ledger_balanced,
    no_live_bridge_posts,
    venues_are_auto_sim,
)


def _row(kind: str, *, venue: str = "simulated", exec_id: str = "e1") -> SimJournalRow:
    side = "sell" if kind == "position_close" else "buy"
    return SimJournalRow(
        kind=kind,
        venue=venue,
        execution_id=exec_id,
        side=side,
        qty=Decimal("1"),
    )


def _healthy_rows() -> list[SimJournalRow]:
    # Ciclo completo SIM-ONLY: buy (order->fill->open) + sell (order->fill->close).
    return [
        _row("order", exec_id="o-buy"),  # orden buy (side=buy).
        _row("fill", exec_id="fill-1"),
        _row("position_open", exec_id="pos-1"),
        SimJournalRow(
            kind="order",
            venue="simulated",
            execution_id="o-sell",
            side="sell",
            qty=Decimal("1"),
        ),
        _row("fill", exec_id="fill-2"),
        _row("position_close", exec_id="pos-1"),
    ]


def test_healthy_full_day() -> None:
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert rep.orders == 2
    assert rep.fills == 2
    assert rep.positions_created == 1
    assert rep.exits == 1
    assert rep.all_venues_in_auto_sim
    assert rep.no_live_bridge_posts
    assert rep.no_duplicate_execution_events
    assert rep.ledger_balanced
    assert rep.healthy


def test_live_venue_breaks_sim_only_invariants() -> None:
    rows = _healthy_rows()
    rows.append(_row("order", venue="LIVE", exec_id="viol"))
    rep = build_auto_daily_report(
        rows=rows,
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert rep.all_venues_in_auto_sim is False
    assert rep.no_live_bridge_posts is False
    assert rep.healthy is False


def test_duplicate_execution_events_breaks_no_double() -> None:
    rows = _healthy_rows()
    # Un segundo fill con el MISMO execution_id (idempotencia rota).
    rows.append(_row("fill", exec_id="fill-1"))
    rep = build_auto_daily_report(
        rows=rows,
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert rep.no_duplicate_execution_events is False


def test_empty_day_is_not_healthy() -> None:
    rep = build_auto_daily_report(rows=[])
    assert rep.healthy is False  # orders==0, fills==0, … sin día autónomo.


def test_venues_are_auto_sim_predicate() -> None:
    assert venues_are_auto_sim(["paper", "simulated", "PAPER"])
    assert not venues_are_auto_sim(["paper", "xtb"])


def test_no_live_bridge_predicate() -> None:
    assert no_live_bridge_posts(["paper", "simulated"])
    assert not no_live_bridge_posts(["simulated", "broker_live"])


def test_execution_events_unique_predicate() -> None:
    assert execution_events_are_unique(["a", "b", "c"])
    assert not execution_events_are_unique(["a", "b", "a"])


def test_ledger_balanced_numeric() -> None:
    assert ledger_balanced(net_cash_delta=Decimal("0"), ledger_remainder=Decimal("0"))
    assert ledger_balanced(net_cash_delta=Decimal("100.0"), ledger_remainder=Decimal("100.00"))
    assert not ledger_balanced(net_cash_delta=Decimal("100"), ledger_remainder=Decimal("99"))


def test_ledger_not_checked_is_not_balanced() -> None:
    """V2.23/A9 (Bloque 6): sin datos de balance ⇒ NOT_CHECKED, nunca PASS."""
    from bolsa_application.auto_daily_journal import (
        LEDGER_BALANCED,
        LEDGER_NOT_CHECKED,
        LEDGER_UNBALANCED,
        ledger_balance_status,
    )

    assert ledger_balance_status() == LEDGER_NOT_CHECKED
    assert not ledger_balanced()
    assert (
        ledger_balance_status(net_cash_delta=Decimal("0"), ledger_remainder=Decimal("0"))
        == LEDGER_BALANCED
    )
    assert (
        ledger_balance_status(
            net_cash_delta=Decimal("100"), ledger_remainder=Decimal("99")
        )
        == LEDGER_UNBALANCED
    )


def test_report_not_checked_ledger_is_unhealthy() -> None:
    """Un día con fills/posiciones pero sin balance comprobado NO es certificable."""
    rep = build_auto_daily_report(rows=_healthy_rows())  # sin args de ledger
    assert rep.ledger_balance_status == "NOT_CHECKED"
    assert rep.ledger_balanced is False
    assert rep.healthy is False
    assert "ledger_balance_not_checked" in rep.errors

