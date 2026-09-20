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


# ── V2.24.2 (P2-A): reconstrucción contable REAL (invariante NO tautológica) ──────


def test_reconstruct_accounting_is_not_tautological() -> None:
    """La contabilidad reconstruida tiene market_value/unrealized NO nulos."""
    from bolsa_application.auto_daily_journal import (
        LedgerCashMovement,
        reconstruct_accounting_from_state,
    )
    from bolsa_domain.lifecycle import assert_equity_invariant

    # Depósito 10.000, compra 100 @ 100 (=-10.000 cash), fee 5, precio sube a 110.
    movements = [
        LedgerCashMovement(category="deposit", amount=Decimal("10000")),
        LedgerCashMovement(category="buy", amount=Decimal("-10000")),
        LedgerCashMovement(category="fee", amount=Decimal("-5")),
    ]
    acct = reconstruct_accounting_from_state(
        movements=movements,
        remaining=Decimal("100"),
        avg_cost=Decimal("100"),
        last_price=Decimal("110"),
    )
    # No degenerado: hay valor de mercado y P&L no realizado reales.
    assert acct.market_value == Decimal("11000.000000")
    assert acct.unrealized_pnl == Decimal("1000.000000")
    assert acct.realized_pnl == Decimal("-5.000000")
    assert acct.cash == Decimal("-5.000000")
    assert acct.initial_equity == Decimal("10000.000000")
    # 9995 equity total; 10000 - 5 + 1000 == 9995 ⇒ invariante se cumple de verdad.
    assert_equity_invariant(acct)


def test_reconstruct_accounting_detects_incoherent_cash() -> None:
    """Si el cash no cuadra con initial+p&l, el invariante DEBE fallar."""
    import pytest

    from bolsa_application.auto_daily_journal import (
        LedgerCashMovement,
        reconstruct_accounting_from_state,
    )
    from bolsa_domain.lifecycle import assert_equity_invariant

    movements = [
        LedgerCashMovement(category="deposit", amount=Decimal("10000")),
        LedgerCashMovement(category="buy", amount=Decimal("-9900")),  # cash incoherente
    ]
    acct = reconstruct_accounting_from_state(
        movements=movements,
        remaining=Decimal("100"),
        avg_cost=Decimal("100"),
        last_price=Decimal("110"),
    )
    with pytest.raises(AssertionError):
        assert_equity_invariant(acct)


def test_reconstruct_accounting_with_closed_pnl() -> None:
    """P&L cerrado se incorpora al realizado y mantiene la invariante.

    Round-trip coherente: depósito 10.000, compra 100 @ 50 (−5.000), venta 100 @ 55
    (+5.500) ⇒ el P&L cerrado (500) YA está dentro del cash; la invariante cuadra.
    """
    from bolsa_application.auto_daily_journal import (
        LedgerCashMovement,
        reconstruct_accounting_from_state,
    )
    from bolsa_domain.lifecycle import assert_equity_invariant

    movements = [
        LedgerCashMovement(category="deposit", amount=Decimal("10000")),
        LedgerCashMovement(category="buy", amount=Decimal("-5000")),
        LedgerCashMovement(category="sell", amount=Decimal("5500")),
    ]
    acct = reconstruct_accounting_from_state(
        movements=movements,
        remaining=Decimal("0"),
        avg_cost=Decimal("0"),
        last_price=Decimal("0"),
        closed_pnl=Decimal("500"),
    )
    # remaining=0 ⇒ market_value=0; pero realized_pnl=500 real (no 0).
    assert acct.realized_pnl == Decimal("500.000000")
    assert acct.market_value == Decimal("0.000000")
    assert acct.cash == Decimal("10500.000000")
    assert_equity_invariant(acct)


# ── V2.42 slice 2c: el día sabe POR QUÉ cerró (criterio de salida de AUTO-2) ──────────


def _close_row(reason: str, exec_id: str) -> SimJournalRow:
    return SimJournalRow(
        kind="position_close",
        venue="simulated",
        execution_id=exec_id,
        side="sell",
        qty=Decimal("1"),
        reason=reason,
    )


def test_day_counts_exit_reasons_from_close_rows() -> None:
    """``time_exit``/``thesis_exit`` se cuentan en el día (evidencia, no impresión)."""
    rows = [
        *_healthy_rows(),
        _close_row("time_exit", "c-time"),
        _close_row("thesis_exit", "c-thesis"),
        _close_row("structural_stop", "c-stop"),
    ]
    rep = build_auto_daily_report(
        rows=rows,
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    counts = dict(rep.exit_reasons)
    assert counts == {
        "time_exit": 1,
        "thesis_exit": 1,
        "structural_stop": 1,
        # ``_healthy_rows()`` cierra sin motivo de protección (lo cierra el decider):
        # se declara como ``undeclared``, no se le atribuye un motivo que no dio.
        "undeclared": 1,
    }, counts
    # Todo cierre está explicado: la suma de motivos es EXACTAMENTE el conteo de salidas.
    assert sum(counts.values()) == rep.exits == 4  # 1 de _healthy_rows + 3 nuevos.
    assert rep.as_dict()["exit_reasons"] == counts


def test_day_exit_without_declared_reason_is_undeclared_not_attributed() -> None:
    """Un cierre sin motivo declarado se cuenta como ``undeclared`` (nunca se disfraza)."""
    rows = [*_healthy_rows(), _close_row("", "c-nodecl")]
    rep = build_auto_daily_report(
        rows=rows,
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    counts = dict(rep.exit_reasons)
    assert counts == {"undeclared": 2}, counts
    assert "time_exit" not in counts and "thesis_exit" not in counts
    assert sum(counts.values()) == rep.exits


def test_day_exit_reasons_order_is_deterministic() -> None:
    """Orden estable (conteo desc, etiqueta asc): el reporte se puede comparar entre días."""
    rows = [
        *_healthy_rows(),
        _close_row("trail", "c-1"),
        _close_row("time_exit", "c-2"),
        _close_row("time_exit", "c-3"),
    ]
    rep = build_auto_daily_report(
        rows=rows,
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert rep.exit_reasons == (("time_exit", 2), ("trail", 1), ("undeclared", 1))


def test_day_reports_atr_provenance_measured_by_caller() -> None:
    """La procedencia del ATR del día entra al reporte tal cual la midió el worker."""
    from bolsa_application.auto_reason_codes import (
        ATR_SOURCE_FALLBACK,
        ATR_SOURCE_REAL,
        day_exit_reason,
    )

    assert day_exit_reason("TIME_STOP") == "time_exit"
    assert day_exit_reason("THESIS_INVALIDATION") == "thesis_exit"
    assert day_exit_reason("STRUCTURAL_STOP") == "structural_stop"
    assert day_exit_reason("TRAIL") == "trail"
    assert day_exit_reason(None) == ""
    assert day_exit_reason("  ") == ""
    assert day_exit_reason("algo_no_catalogado") == "algo_no_catalogado"

    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        atr_sources={ATR_SOURCE_REAL: 7, ATR_SOURCE_FALLBACK: 3},
    )
    assert dict(rep.atr_sources) == {"real": 7, "fallback": 3}
    assert rep.as_dict()["atr_sources"] == {"real": 7, "fallback": 3}


def test_day_without_atr_measurement_reports_empty_not_invented() -> None:
    """Sin medición de ATR el día declara vacío: jamás se asume procedencia."""
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert rep.atr_sources == ()
    assert rep.as_dict()["atr_sources"] == {}


# ── V2.45/AUTO-5 (Golden Day 2.0): embudo + atribución + MAE/MFE + coste ──────────────


def _opportunity(
    instrument: str,
    status: str,
    *,
    reason: str = "",
    version: str = "",
    reference: str | None = None,
    subsequent: str | None = None,
):
    from bolsa_application.auto_daily_journal import OpportunityRow

    return OpportunityRow(
        instrument_id=instrument,
        status=status,
        reason=reason,
        strategy_version=version,
        reference_price=Decimal(reference) if reference is not None else None,
        subsequent_price=Decimal(subsequent) if subsequent is not None else None,
    )


def test_day_without_opportunities_declares_funnel_unknown_not_zero() -> None:
    """Sin oportunidades aportadas el embudo es UNKNOWN: no medir NO es un 0 medido."""
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    day = rep.as_dict()
    assert rep.funnel_measurement == "UNKNOWN"
    assert rep.funnel_closed is False
    assert (rep.seen, rep.traded, rep.rejected, rep.expired, rep.missed) == (0, 0, 0, 0, 0)
    assert rep.rejection_reasons == ()
    assert rep.opportunity_cost == ()
    assert rep.opportunity_cost_measurement == "UNKNOWN"
    assert rep.mae_mfe_measurement == "UNKNOWN"
    assert day["funnel_measurement"] == "UNKNOWN"
    # Sin oportunidades la ausencia NO ensucia el día vigente (aditivo, no rompe).
    assert "funnel_unbalanced" not in rep.errors
    assert rep.healthy


def test_day_funnel_covers_every_opportunity_exactly_once() -> None:
    """``seen == traded + rejected + expired + missed`` con motivo en cada no-operada."""
    from bolsa_application.auto_reason_codes import (
        OPPORTUNITY_EXPIRED,
        OPPORTUNITY_MISSED,
        OPPORTUNITY_REJECTED,
        OPPORTUNITY_TRADED,
    )

    opportunities = [
        _opportunity("AAA", OPPORTUNITY_TRADED, version="v1"),
        _opportunity("BBB", OPPORTUNITY_REJECTED, reason="top_n_excluded", version="v2"),
        _opportunity("CCC", OPPORTUNITY_EXPIRED, reason="signal_stale", version="v1"),
        _opportunity("DDD", OPPORTUNITY_MISSED, reason="not_evaluated", version="v2"),
    ]
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        opportunities=opportunities,
    )
    assert rep.funnel_measurement == "COMPLETE"
    assert rep.funnel_closed is True
    assert (rep.seen, rep.traded, rep.rejected, rep.expired, rep.missed) == (4, 1, 1, 1, 1)
    assert rep.seen == rep.traded + rep.rejected + rep.expired + rep.missed
    assert dict(rep.rejection_reasons) == {"top_n_excluded": 1}
    # La atribución por estrategia sale del estado de la oportunidad (no se inventa).
    assert dict(rep.strategy_traded) == {"v1": 1}
    assert "funnel_unbalanced" not in rep.errors


def test_day_funnel_declares_seen_mismatch_when_an_opportunity_is_dropped() -> None:
    """Si el productor vio MÁS oportunidades que filas construyó, el día lo declara."""
    from bolsa_application.auto_reason_codes import OPPORTUNITY_TRADED

    opportunities = [_opportunity("AAA", OPPORTUNITY_TRADED, version="v1")]
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        opportunities=opportunities,
        seen=3,  # el productor vio 3; solo 1 terminó en un estado ⇒ faltan 2.
    )
    assert rep.funnel_measurement == "PARTIAL"
    assert rep.funnel_closed is False
    assert "funnel_seen_mismatch" in rep.errors
    assert "funnel_unbalanced" in rep.errors
    assert rep.healthy is False


def test_day_rejection_without_reason_is_declared_not_dressed() -> None:
    """Una rechazada sin motivo tipificado es una decisión en silencio: el día la declara."""
    from bolsa_application.auto_reason_codes import OPPORTUNITY_REJECTED

    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        opportunities=[_opportunity("BBB", OPPORTUNITY_REJECTED)],  # sin motivo
    )
    assert "rejection_without_reason" in rep.errors
    assert rep.funnel_measurement == "PARTIAL"
    assert rep.funnel_closed is False


def test_day_unknown_opportunity_status_keeps_funnel_open() -> None:
    """Un estado no catalogado no cae en ningún cajón: el embudo queda abierto."""
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        opportunities=[_opportunity("XYZ", "maybe", reason="?")],
    )
    assert "opportunity_status_unknown" in rep.errors
    assert "funnel_unbalanced" in rep.errors
    assert rep.funnel_closed is False


def test_day_opportunity_cost_measured_and_declared_when_missing() -> None:
    """El coste de oportunidad se mide con el precio posterior; sin él, se declara."""
    from bolsa_application.auto_reason_codes import (
        OPPORTUNITY_COST_UNMEASURED,
        OPPORTUNITY_REJECTED,
    )

    opportunities = [
        _opportunity(
            "BBB",
            OPPORTUNITY_REJECTED,
            reason="top_n_excluded",
            version="v2",
            reference="100",
            subsequent="110",
        ),
        _opportunity(
            "CCC",
            OPPORTUNITY_REJECTED,
            reason="top_n_excluded",
            version="v2",
            reference="100",  # sin precio posterior ⇒ no se inventa.
        ),
    ]
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        opportunities=opportunities,
    )
    assert rep.opportunity_cost_measurement == "PARTIAL"
    assert OPPORTUNITY_COST_UNMEASURED in rep.notes
    by_id = {c.instrument_id: c for c in rep.opportunity_cost}
    assert by_id["BBB"].missed_return == Decimal("0.100000")
    assert by_id["BBB"].measurement == "COMPLETE"
    assert by_id["CCC"].missed_return is None
    assert by_id["CCC"].measurement == "UNKNOWN"
    assert by_id["CCC"].notes == (OPPORTUNITY_COST_UNMEASURED,)
    assert rep.as_dict()["opportunity_cost"][0]["measurement"] == "COMPLETE"


def test_day_mae_mfe_aggregate_declares_partial_when_a_leg_is_missing() -> None:
    """MAE/MFE se RECOGE: con una pata ausente el agregado se declara PARTIAL."""
    from bolsa_application.auto_daily_journal import OperationMeasurement
    from bolsa_application.auto_reason_codes import MAE_MFE_UNMEASURED

    measurements = [
        OperationMeasurement(
            instrument_id="AAA",
            strategy_version="v1",
            mfe=Decimal("1.5"),
            mae=Decimal("-0.5"),
        ),
        OperationMeasurement(
            instrument_id="BBB",
            strategy_version="v2",
            mfe=None,
            mae=Decimal("-1.0"),
        ),
    ]
    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        measurements=measurements,
    )
    assert rep.mae_mfe_measurement == "PARTIAL"
    assert MAE_MFE_UNMEASURED in rep.notes
    assert len(rep.mae_mfe) == 2
    day = rep.as_dict()
    assert day["mae_mfe"][0]["instrumentId"] == "AAA"
    assert day["mae_mfe"][0]["mfe"] == "1.5"


def test_day_mae_mfe_complete_when_both_legs_present() -> None:
    from bolsa_application.auto_daily_journal import OperationMeasurement

    rep = build_auto_daily_report(
        rows=_healthy_rows(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        measurements=[
            OperationMeasurement(
                instrument_id="AAA", strategy_version="v1", mfe=Decimal("1.5"), mae=Decimal("-0.5")
            )
        ],
    )
    assert rep.mae_mfe_measurement == "COMPLETE"
    assert rep.notes == ()


def test_day_strategy_exits_attributed_from_close_rows() -> None:
    """La salida se atribuye a la estrategia que la declaró en la fila de cierre."""
    rows = [
        *_healthy_rows(),
        SimJournalRow(
            kind="position_close",
            venue="simulated",
            execution_id="c-v1",
            side="sell",
            qty=Decimal("1"),
            reason="time_exit",
            strategy_version="v1",
        ),
        SimJournalRow(
            kind="position_close",
            venue="simulated",
            execution_id="c-v2",
            side="sell",
            qty=Decimal("1"),
            reason="thesis_exit",
            strategy_version="v2",
        ),
        SimJournalRow(
            kind="position_close",
            venue="simulated",
            execution_id="c-none",
            side="sell",
            qty=Decimal("1"),
            reason="structural_stop",
            strategy_version="",  # sin versión: NO se reparte, se declara ausente.
        ),
    ]
    rep = build_auto_daily_report(
        rows=rows,
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert dict(rep.strategy_exits) == {"v1": 1, "v2": 1}
    assert rep.as_dict()["strategy_exits"] == {"v1": 1, "v2": 1}

