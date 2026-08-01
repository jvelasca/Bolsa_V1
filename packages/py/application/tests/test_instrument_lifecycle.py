"""Reglas de purga / huérfanos (sin BD)."""

from __future__ import annotations

from bolsa_application.instrument_lifecycle import InstrumentRemovalPreview, ListMembershipRef


def _preview(
    *,
    remaining: int,
    positions: int = 0,
    pending: int = 0,
    ohlcv: int = 10,
) -> InstrumentRemovalPreview:
    would_be_orphan = remaining == 0
    blocked: list[str] = []
    if not would_be_orphan:
        blocked.append("El valor sigue en otras listas; no se purga de BD.")
    if positions > 0:
        blocked.append(f"Tiene {positions} posición(es) abierta(s).")
    if pending > 0:
        blocked.append(f"Tiene {pending} orden(es) pendiente(s).")
    return InstrumentRemovalPreview(
        instrument_id="i1",
        symbol="TST",
        name="Test",
        list_memberships=tuple(
            ListMembershipRef(list_id=f"l{n}", list_name=f"L{n}", source="custom")
            for n in range(remaining)
        ),
        remaining_list_count=remaining,
        trackers_by_instrument=(),
        trackers_by_list=(),
        price_alerts_active=0,
        price_alerts_total=0,
        signal_alerts_active=0,
        signal_alerts_total=0,
        positions=positions,
        pending_orders=pending,
        transactions=0,
        backtest_runs=0,
        ledger_entries=0,
        ohlcv_bar_count=ohlcv,
        would_be_orphan=would_be_orphan,
        can_purge=would_be_orphan and len(blocked) == 0,
        purge_blocked_reasons=tuple(blocked),
        purge_warnings=(f"Se eliminarán {ohlcv} velas OHLCV.",) if ohlcv else (),
    )


def test_orphan_without_positions_can_purge() -> None:
    p = _preview(remaining=0)
    assert p.would_be_orphan
    assert p.can_purge
    assert p.purge_blocked_reasons == ()


def test_still_in_lists_cannot_purge() -> None:
    p = _preview(remaining=2)
    assert not p.would_be_orphan
    assert not p.can_purge
    assert any("otras listas" in r for r in p.purge_blocked_reasons)


def test_orphan_with_position_blocked() -> None:
    p = _preview(remaining=0, positions=1)
    assert p.would_be_orphan
    assert not p.can_purge
    assert any("posición" in r for r in p.purge_blocked_reasons)


def test_orphan_with_pending_order_blocked() -> None:
    p = _preview(remaining=0, pending=2)
    assert not p.can_purge
    assert any("orden" in r for r in p.purge_blocked_reasons)
