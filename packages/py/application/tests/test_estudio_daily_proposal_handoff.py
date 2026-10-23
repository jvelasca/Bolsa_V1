"""Handoff ESTUDIO → AUTO — adopción por IDENTIDAD y Δ = 0 cuando no hay propuesta.

La cadena ``parte diario → señal → ciclo`` solo es demostrable si el productor **adopta**
la identidad durable que el parte publicó (``planId``/``signalId``) y la geometría que el
usuario vio en pantalla. Estos tests fijan dos propiedades que el E2E no puede aislar:

* con propuesta, el plan hereda ``decisionId`` y geometría del parte, y el journal sella
  la propuesta que lo originó (``dailyProposal``);
* **sin** propuesta, el tick es el histórico: ``target_price`` de la señal NO se cuela
  como ``target1`` del plan (un ``target1`` por encima de ``target2`` convertiría en
  ``plan_invalid`` decisiones que nada tienen que ver con el parte).

Módulo puro: sin I/O, sin reloj real, sin PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
)
from bolsa_application.estudio_daily_proposals import (
    ADOPTION_ABSENT_UNMEASURED,
    ADOPTION_EXACT,
    ADOPTION_MISMATCH,
    EstudioDailyProposal,
    proposal_identity_matches,
    select_adoptable,
)

_MOMENT = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


def _snapshot() -> Any:
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )


def _signal(*, signal_id: str | None = None, target_price: float | None = 110.0) -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="v42",
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    return V2Signal(
        "AAA",
        "BUY",
        price=100.0,
        atr=2.0,
        edge=0.9,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=signal_id or identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
        p_win=0.5,
        avg_loss_r=-1.0,
        target_price=target_price,
    )


def _approved(plan: Any) -> list[Any]:
    return [
        entry
        for entry in plan.journal_entries
        if (entry.payload or {}).get("event") == "auto_entry_decision"
        and (entry.payload or {}).get("approved") is True
    ]


def _proposal(
    *,
    proposal_id: str = "prop-1",
    instrument_id: str = "AAA",
    symbol: str | None = "AAA",
    day: str = "2026-10-04",
    bar_date: str = "2026-10-05",
    status: str = "proposed",
    decision_id: str | None = "tp-AAA-2026-10-05",
    signal_id: str | None = "edo-AAA-2026-10-05",
    plan: dict[str, Any] | None = None,
) -> EstudioDailyProposal:
    return EstudioDailyProposal(
        id=proposal_id,
        account_id="acc-1",
        day=day,
        instrument_id=instrument_id,
        status=status,
        symbol=symbol,
        decision_id=decision_id,
        signal_id=signal_id,
        bar_date=bar_date,
        plan=plan
        or {
            "entry": 100.0,
            "structuralStop": 97.0,
            "target1": 103.0,
            "target2": 106.0,
        },
    )


def test_select_adoptable_binds_the_identity_and_declares_the_rest() -> None:
    """Se adopta la propuesta vigente; caducada y futura se DECLARAN, no se descartan."""
    result = select_adoptable(
        [
            _proposal(),
            _proposal(
                proposal_id="prop-stale",
                instrument_id="BBB",
                symbol="BBB",
                bar_date="2026-09-01",
                decision_id="tp-BBB",
                signal_id="edo-BBB",
            ),
            _proposal(
                proposal_id="prop-future",
                instrument_id="CCC",
                symbol="CCC",
                bar_date="2026-10-06",
                decision_id="tp-CCC",
                signal_id="edo-CCC",
            ),
            _proposal(
                proposal_id="prop-done",
                instrument_id="DDD",
                symbol="DDD",
                status="consumed",
                decision_id="tp-DDD",
                signal_id="edo-DDD",
            ),
        ],
        instruments=["AAA", "BBB", "CCC", "DDD"],
        decision_bar_day="2026-10-05",
        max_lag_days=5,
    )

    handoff = result.by_instrument()
    # La identidad adoptable se indexa por instrumento Y por símbolo (la MISMA propuesta).
    assert handoff["AAA"]["proposalId"] == "prop-1"
    assert handoff["AAA"]["planId"] == "tp-AAA-2026-10-05"
    assert handoff["AAA"]["signalId"] == "edo-AAA-2026-10-05"
    assert handoff["AAA"]["barLagDays"] == 0
    assert handoff["AAA"]["entry"] == 100.0
    assert handoff["AAA"]["target1"] == 103.0
    # Caducada: se declara con motivo (no se atribuye un plan viejo a un ciclo nuevo).
    assert [pid for pid, _ in result.expired] == ["prop-stale"]
    assert "proposal_stale" in result.expired[0][1]
    # Futura (lookahead): se aplaza con motivo estable.
    reasons = {row["instrumentId"]: row["reason"] for row in result.skipped}
    assert reasons["CCC"].startswith("proposal_bar_in_future")
    # Consumida: no vuelve a ofrecerse ni se declara error.
    assert "DDD" not in handoff


def test_attribution_is_equality_of_durable_ids_not_the_symbol() -> None:
    """``exact`` exige la MISMA pareja de ids; un hueco es ``unmeasured``, nunca ``exact``."""
    assert (
        proposal_identity_matches(
            proposal_plan_id="tp-1",
            proposal_signal_id="sig-1",
            cycle_plan_id="tp-1",
            cycle_signal_id="sig-1",
        )
        == ADOPTION_EXACT
    )
    assert (
        proposal_identity_matches(
            proposal_plan_id="tp-1",
            proposal_signal_id="sig-1",
            cycle_plan_id="tp-1",
            cycle_signal_id="sig-OTRA",
        )
        == ADOPTION_MISMATCH
    )
    assert (
        proposal_identity_matches(
            proposal_plan_id=None,
            proposal_signal_id="sig-1",
            cycle_plan_id="tp-1",
            cycle_signal_id="sig-1",
        )
        == ADOPTION_ABSENT_UNMEASURED
    )


def test_plan_adopts_the_published_identity_and_geometry() -> None:
    """Con propuesta: el plan hereda ``planId``/geometría y el journal sella el origen."""
    part_signal_id = "edo-AAA-2026-10-05"
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal(signal_id=part_signal_id)],
        regime="BULL_TREND",
        as_of="2026-10-05T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
        daily_proposals=select_adoptable(
            [_proposal()], instruments=["AAA"], decision_bar_day="2026-10-05"
        ).by_instrument(),
    )

    entries = _approved(plan)
    assert len(entries) == 1
    payload = entries[0].payload
    # La identidad del PLAN es la del parte; la señal del ciclo es la del parte.
    assert payload["tradePlan"]["decisionId"] == "tp-AAA-2026-10-05"
    assert payload["signalId"] == part_signal_id
    # La geometría publicada viaja tal cual (no se re-deriva del ATR local).
    assert payload["tradePlan"]["structuralStop"] == 97.0
    assert payload["tradePlan"]["target1"] == 103.0
    # El journal declara QUÉ propuesta originó el plan: es el eslabón demostrable.
    assert payload["dailyProposal"]["proposalId"] == "prop-1"
    assert payload["dailyProposal"]["planId"] == "tp-AAA-2026-10-05"
    assert payload["dailyProposal"]["signalId"] == part_signal_id


def test_without_proposal_the_tick_is_the_historical_one() -> None:
    """Δ = 0 sin propuesta: ``target1`` sale del ATR, no del ``target_price`` de la señal.

    Regresión: pasar siempre ``target_price`` como ``target1`` producía
    ``target1 > target2`` ⇒ ``plan_invalid`` en decisiones ajenas al parte.
    """
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal(target_price=110.0)],
        regime="BULL_TREND",
        as_of="2026-10-05T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
        daily_proposals=None,
    )

    entries = _approved(plan)
    assert len(entries) == 1
    payload = entries[0].payload
    # entry 100 · stop = 100 - 1.5·ATR(2) = 97 ⇒ riesgo 3 ⇒ T1 = 1R y T2 = 2R.
    assert payload["tradePlan"]["structuralStop"] == 97.0
    assert payload["tradePlan"]["target1"] == 103.0
    assert payload["tradePlan"]["target2"] == 106.0
    # La identidad del plan sigue siendo la del claim (no hay propuesta que adoptar).
    assert str(payload["tradePlan"]["decisionId"]).startswith("dec-")
    # Sin propuesta no se sella una propuesta inventada.
    assert "dailyProposal" not in payload
