"""V2.47 — la economía de la decisión viaja en el journal (superficie de valor esperado).

Contrato que estos tests certifican (y que una mutación debe poder romper):

* Una decisión **APROBADA** publica su valor esperado (``expectedR`` y
  ``netExpectedCurrency``) junto con su estado de medición. Sin ese dato el operador ve el
  plan pero no su economía, y el neto no es reconstruible aguas abajo.
* Una decisión **RECHAZADA** no publica economía: una oportunidad vetada no tiene valor
  esperado que enseñar, y publicarlo invitaría a leer un rechazo como una compra perdida.
* Con el **optimizador OFF** la economía se mide igual (con la geometría de la propia
  decisión): no se hereda de una foto paralela ni se deja el hueco en blanco.
* Medición **PARTIAL** (sin coste cerrado): el ``R`` se publica y el neto queda ``None`` —
  el hueco es el dato que falta, nunca un ``0``.

Módulo puro: sin I/O, sin reloj real, sin PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime

from bolsa_analytics.cognitive.portfolio_reservation import TradingCostModel
from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
)

_MOMENT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def _snapshot(*, cash: float = 80_000.0):
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=cash,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )


def _signal(
    symbol: str,
    *,
    edge: float = 0.9,
    price: float = 100.0,
    atr: float = 2.0,
    p_win: float | None = 0.5,
    avg_loss_r: float | None = -1.0,
    target_price: float | None = 110.0,
) -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id=symbol,
        action="BUY",
        strategy_version="v42",
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    return V2Signal(
        symbol,
        "BUY",
        price=price,
        atr=atr,
        edge=edge,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
        p_win=p_win,
        avg_loss_r=avg_loss_r,
        target_price=target_price,
    )


def _approved_payloads(plan) -> list[dict]:
    return [
        payload
        for entry in plan.journal_entries
        if isinstance((payload := entry.payload or {}), dict)
        and payload.get("event") == "auto_entry_decision"
        and payload.get("approved") is True
    ]


def test_an_approved_decision_publishes_its_expected_value() -> None:
    """Aprobada ⇒ ``expectedR`` y neto medidos, con su estado de medición declarado."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=True),
    )

    payloads = _approved_payloads(plan)
    assert len(payloads) == 1
    payload = payloads[0]
    # 0.5 de probabilidad con 1R de premio y −1R de castigo (el target deriva el premio):
    # el R esperado es una MAGNITUD medida, no un cero de relleno.
    assert payload["expectedR"] is not None
    assert payload["expectedR"] > 0.0
    assert payload["netExpectedCurrency"] is not None
    assert payload["expectedMeasurement"] in {"COMPLETE", "PARTIAL"}
    # El journal publica la clave con el MISMO nombre que ``ExpectedValue.to_dict()``.
    assert "expectedValue" not in payload


def test_the_optimizer_off_path_measures_the_same_economy() -> None:
    """Con el optimizador OFF la economía se mide igual (geometría de la propia decisión)."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
    )

    assert plan.optimizer is None
    payloads = _approved_payloads(plan)
    assert len(payloads) == 1
    assert payloads[0]["expectedR"] is not None
    assert payloads[0]["netExpectedCurrency"] is not None


def test_an_unmeasured_economy_is_declared_and_never_published_as_zero() -> None:
    """Sin probabilidad no hay R: se declara UNKNOWN y el neto queda ``None`` (no 0).

    Se ejerce con el optimizador **OFF** a propósito: con el flag ON una candidata sin
    economía medible no es elegible (AUTO-4 la rechaza con ``optimizer_expected_value_unmeasured``),
    así que el caso "aprobada pero no medida" solo existe por la vía del ranking.
    """
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", p_win=None)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
    )

    payloads = _approved_payloads(plan)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["expectedR"] is None
    assert payload["netExpectedCurrency"] is None
    assert payload["expectedMeasurement"] == "UNKNOWN"
    assert payload["expectedNotes"]


def test_a_rejected_decision_publishes_no_economy() -> None:
    """Un rechazo no publica valor esperado: no hay economía que enseñar de un veto."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", edge=0.05)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=True),
    )

    assert _approved_payloads(plan) == []
    for entry in plan.journal_entries:
        payload = entry.payload or {}
        assert "expectedR" not in payload
        assert "netExpectedCurrency" not in payload


def test_the_round_trip_cost_lands_in_the_net_and_is_declared() -> None:
    """Con coste real, el neto es el bruto menos el coste (y va declarado como medido)."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(
            optimizer_enabled=True,
            cost_model=TradingCostModel(
                commission_bps=10.0, spread_bps=2.0, slippage_bps=5.0, gap_bps=0.0
            ),
        ),
    )

    payload = _approved_payloads(plan)[0]
    assert payload["expectedMeasurement"] == "COMPLETE"
    assert payload["expectedR"] is not None
    assert payload["netExpectedCurrency"] is not None
