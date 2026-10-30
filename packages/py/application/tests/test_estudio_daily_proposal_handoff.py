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

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

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
    PersistEstudioDailyProposals,
    proposal_candidate_from_value,
    proposal_identity_matches,
    proposal_price_conflict,
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


def _signal(
    *,
    signal_id: str | None = None,
    target_price: float | None = 110.0,
    price: float = 100.0,
    execution_price: float | None = None,
) -> V2Signal:
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
        price=price,
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
        execution_price=execution_price,
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


class _ProposalStore:
    """Store en memoria: el handoff solo necesita ``upsert_pending``."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def upsert_pending(self, **kwargs: Any) -> Any:
        self.rows.append(kwargs)
        return SimpleNamespace(id=f"prop-{len(self.rows)}")


def _value_ok() -> dict[str, Any]:
    return {
        "instrumentId": "AAA",
        "symbol": "AAA",
        "status": "ok",
        "asOfBarDate": "2026-10-05",
        "plan": {
            "decisionId": "tp-AAA-2026-10-05",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 97.0,
            "target1": 103.0,
        },
        "strategy": {"signalId": "edo-AAA-2026-10-05", "strategyVersion": 42},
    }


@pytest.mark.asyncio
async def test_a_partial_report_marks_the_proposal_and_auto_does_not_adopt_it() -> None:
    """D-2 — la marca de parte parcial viaja con la propuesta y bloquea la adopción.

    Antes, ``PersistEstudioDailyProposals`` corría antes de mirar ``status == partial`` y
    la propuesta se persistía sin marca: ni AUTO ni la cadena podían distinguir un plan
    medido con la cartera completa de uno medido con ``positions_unavailable``.
    """
    store = _ProposalStore()
    summary = await PersistEstudioDailyProposals(store).execute(
        account_id="acc-1",
        report={
            "asOf": "2026-10-05",
            "status": "partial",
            "degradedReasons": ["positions_unavailable"],
            "values": [_value_ok()],
        },
    )

    assert summary.proposed == 1
    assert store.rows[0]["plan"]["degradedReasons"] == ["positions_unavailable"]
    # La geometría publicada no se pierde: se adopta... salvo por la degradación.
    assert store.rows[0]["plan"]["entry"] == 100.0

    persisted = EstudioDailyProposal(
        id="prop-1",
        account_id="acc-1",
        day="2026-10-05",
        instrument_id="AAA",
        symbol="AAA",
        decision_id="tp-AAA-2026-10-05",
        signal_id="edo-AAA-2026-10-05",
        bar_date="2026-10-05",
        plan=store.rows[0]["plan"],
    )
    assert persisted.degraded_reasons == ("positions_unavailable",)

    result = select_adoptable(
        [persisted], instruments=["AAA"], decision_bar_day="2026-10-05"
    )
    assert result.by_instrument() == {}
    assert result.skipped == (
        {
            "instrumentId": "AAA",
            "reason": "proposal_degraded:positions_unavailable",
        },
    )


def test_an_ok_report_does_not_mark_the_proposal() -> None:
    """D-2 — sin degradaciones la propuesta conserva el camino histórico (Δ = 0)."""
    candidate, reason = proposal_candidate_from_value(_value_ok())

    assert reason is None
    assert candidate is not None
    assert "degradedReasons" not in candidate["plan"]
    assert not _proposal(plan=candidate["plan"]).degraded_reasons


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


def _entry_decisions(plan: Any) -> list[Any]:
    return [
        entry
        for entry in plan.journal_entries
        if (entry.payload or {}).get("event") == "auto_entry_decision"
    ]


def _vetoed_handoff(
    price: float,
    plan: dict[str, Any] | None = None,
    *,
    execution_price: float | None = None,
) -> Any:
    return plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal(price=price, execution_price=execution_price)],
        regime="BULL_TREND",
        as_of="2026-10-05T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
        daily_proposals=select_adoptable(
            [_proposal(plan=plan)],
            instruments=["AAA"],
            decision_bar_day="2026-10-05",
        ).by_instrument(),
    )


def test_a_proposal_below_the_live_price_is_vetoed_whole() -> None:
    """D-1 — mercado 92 con entrada 100/stop 95: el plan del parte NO es ejecutable.

    Sin el contraste, el motor dimensionaba sobre 100, la orden se ejecutaba al precio vivo
    (92) y la posición nacía con el stop por ENCIMA del mercado (cierre en el primer tick).
    El veto debe ser total: ni paquete, ni reserva, ni plan en el journal.
    """
    plan = _vetoed_handoff(
        price=92.0,
        plan={
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 103.0,
            "target2": 106.0,
        },
    )

    decisions = _entry_decisions(plan)
    assert len(decisions) == 1
    payload = decisions[0].payload
    assert payload["approved"] is False
    assert payload["reasonCodes"] == ["proposal_price_invalid"]
    assert payload["tradePlan"] is None
    # El journal declara QUÉ propuesta se descartó y con qué números.
    assert payload["proposalPriceConflict"] == {
        "code": "at_or_below_stop",
        "marketPrice": 92.0,
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 103.0,
        "tolerancePct": 0.02,
    }
    assert payload["dailyProposal"]["proposalId"] == "prop-1"
    # Nada se comprometió: ni propuesta de ejecución ni reserva.
    assert plan.entry_packages == {}
    assert plan.reservations == ()


@pytest.mark.parametrize(
    ("price", "code"),
    [
        (97.5, "diverged:0.0250"),
        (103.0, "target_reached"),
    ],
)
def test_a_proposal_out_of_tolerance_or_already_targeted_is_vetoed(
    price: float, code: str
) -> None:
    """D-1 — divergencia > 2 % o objetivo ya alcanzado: la geometría ya no es la vigente."""
    plan = _vetoed_handoff(price=price)

    decisions = _entry_decisions(plan)
    assert len(decisions) == 1
    payload = decisions[0].payload
    assert payload["approved"] is False
    assert payload["reasonCodes"] == ["proposal_price_invalid"]
    assert payload["proposalPriceConflict"]["code"] == code
    assert plan.entry_packages == {}


def test_a_proposal_within_tolerance_keeps_the_published_geometry() -> None:
    """D-1 — dentro de tolerancia (1 %) la propuesta se adopta: el guard no es un veto ciego."""
    plan = _vetoed_handoff(price=99.0)

    entries = _approved(plan)
    assert len(entries) == 1
    payload = entries[0].payload
    assert "proposalPriceConflict" not in payload
    assert payload["tradePlan"]["decisionId"] == "tp-AAA-2026-10-05"
    assert payload["tradePlan"]["structuralStop"] == 97.0
    assert payload["tradePlan"]["target1"] == 103.0


def test_the_contrast_uses_the_execution_price_and_vetoes_the_fill_below_the_stop() -> None:
    """D-1 — decisión 100 (``close(B-1)``) y fill 96 (``open(B)``) con stop 97: se veta.

    El contraste histórico miraba SOLO el precio de DECISIÓN: con 100 la geometría cuadraba
    y la orden se liquidaba a 96, es decir con el stop publicado POR ENCIMA del fill — el
    «cierre en el primer tick» que D-1 existe para evitar.
    """
    plan = _vetoed_handoff(price=100.0, execution_price=96.0)

    payload = _entry_decisions(plan)[0].payload
    assert payload["approved"] is False
    assert payload["reasonCodes"] == ["proposal_price_invalid"]
    assert payload["proposalPriceConflict"] == {
        "code": "at_or_below_stop",
        "marketPrice": 100.0,
        "entry": 100.0,
        "structuralStop": 97.0,
        "target1": 103.0,
        "tolerancePct": 0.02,
        # El número que produjo el veto viaja declarado: no se confunde con la decisión.
        "executionPrice": 96.0,
    }
    assert plan.entry_packages == {}
    assert plan.reservations == ()


def test_the_execution_price_out_of_tolerance_is_vetoed_whole() -> None:
    """D-1 — el precio de FILL también gobierna la divergencia contra la entrada publicada."""
    plan = _vetoed_handoff(price=100.0, execution_price=102.5)

    payload = _entry_decisions(plan)[0].payload
    assert payload["approved"] is False
    assert payload["proposalPriceConflict"]["code"] == "diverged:0.0250"
    assert payload["proposalPriceConflict"]["executionPrice"] == 102.5
    assert plan.entry_packages == {}


def test_an_execution_price_inside_the_geometry_keeps_the_proposal() -> None:
    """D-1 — contraprueba: el fill dentro del stop/objetivo y de la tolerancia se adopta."""
    plan = _vetoed_handoff(price=100.0, execution_price=99.0)

    entries = _approved(plan)
    assert len(entries) == 1
    assert "proposalPriceConflict" not in entries[0].payload
    assert entries[0].payload["tradePlan"]["structuralStop"] == 97.0


def test_the_two_percent_boundary_is_inclusive() -> None:
    """D-1 — exactamente ±2 % NO veta: la resta en coma flotante no puede mover el límite.

    ``98/100 - 1`` es ``0.020000000000000018``; comparado con ``> 0.02`` convertía el borde
    declarado («veto SOLO por encima») en veto. El primer precio por encima sigue vetando.
    """
    proposal = {"entry": 100.0, "structuralStop": 95.0, "target1": 110.0}

    assert proposal_price_conflict(proposal, market_price=98.0) is None
    assert proposal_price_conflict(proposal, market_price=102.0) is None
    assert (
        proposal_price_conflict(proposal, market_price=97.99) == "diverged:0.0201"
    )


def test_a_non_finite_stop_or_target_is_vetoed_as_incomplete_geometry() -> None:
    """D-1 — un stop/objetivo no finito no es «sin dato»: es geometría inutilizable."""
    for level in (float("nan"), float("inf"), float("-inf")):
        assert (
            proposal_price_conflict(
                {"entry": 100.0, "structuralStop": level, "target1": 103.0},
                market_price=100.0,
            )
            == "geometry_not_finite"
        )
        assert (
            proposal_price_conflict(
                {"entry": 100.0, "structuralStop": 97.0, "target1": level},
                market_price=100.0,
            )
            == "geometry_not_finite"
        )


def test_a_non_finite_level_never_reaches_the_journal_payload() -> None:
    """D-1 — el detalle del veto es JSON estricto: un ``NaN``/``inf`` viaja como ``None``.

    El journal se sella en ``JSONB``; ``json.dumps`` escribiría ``NaN``/``Infinity`` y
    PostgreSQL lo rechazaría como JSON inválido. El MOTIVO declara el problema y el número
    no representable no se cuela en el payload.
    """
    plan = _vetoed_handoff(
        price=100.0,
        plan={"entry": 100.0, "structuralStop": float("nan"), "target1": 103.0},
    )

    payload = _entry_decisions(plan)[0].payload
    assert payload["approved"] is False
    assert payload["proposalPriceConflict"]["code"] == "geometry_not_finite"
    assert payload["proposalPriceConflict"]["structuralStop"] is None
    json.dumps(payload, allow_nan=False)  # no lanza: el payload es JSON estricto


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
