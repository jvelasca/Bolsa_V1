"""AUTO-4 / V2.44 — cableado del optimizador de cartera en `plan_v2_tick`.

Dos contratos que estos tests defienden:

1. **OFF por defecto ⇒ byte-identidad.** Con ``AUTO_ENGINE_SIM_V2_OPTIMIZER`` sin poner, el
   tick no construye ninguna candidata, no llama al optimizador y el journal no gana ni una
   clave: el camino es el de siempre.
2. **ON ⇒ el ranking deja de ser la decisión.** El TOP N pasa a ser el CONJUNTO CANDIDATO y
   las que no entran en la combinación se declaran con su motivo REAL (nunca
   ``edge_below_threshold``, que sería falso).
"""

from datetime import UTC, datetime

from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
    tunables_from_env,
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
    atr: float | None = 2.0,
    sector: str = "tech",
    liquidity: float = 1_000_000.0,
    p_win: float | None = None,
    avg_win_r: float | None = None,
    avg_loss_r: float | None = None,
    target_price: float | None = None,
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
        sector=sector,
        liquidity_notional=liquidity,
        strategy_version="v42",
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
        p_win=p_win,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        target_price=target_price,
    )


def _reasons(plan) -> list[str]:
    return [
        reason
        for entry in plan.journal_entries
        for reason in entry.payload.get("reasonCodes", [])
    ]


# ── Flag OFF: byte-identidad ──────────────────────────────────────────────────


def test_the_optimizer_is_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_OPTIMIZER", raising=False)
    cfg = tunables_from_env()
    assert cfg.optimizer_enabled is False
    assert cfg.optimizer_max_combinations > 0


def test_the_flag_can_be_turned_on_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_OPTIMIZER", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_OPT_MAX_COMBINATIONS", "64")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_OPT_MAX_POSITIONS", "2")
    cfg = tunables_from_env()
    assert cfg.optimizer_enabled is True
    assert cfg.optimizer_max_combinations == 64
    assert cfg.optimizer_max_positions == 2


def test_invalid_optimizer_env_falls_back_to_the_declared_default(monkeypatch) -> None:
    """Un tope de combinatoria ilegible no se "sana a medias": queda el default."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_OPT_MAX_COMBINATIONS", "basura")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_OPT_MAX_POSITIONS", "-3")
    cfg = tunables_from_env()
    assert cfg.optimizer_max_combinations == V2Tunables().optimizer_max_combinations
    assert cfg.optimizer_max_positions is None


def test_with_the_flag_off_no_optimizer_key_or_reason_is_emitted() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", edge=0.9), _signal("BBB", edge=0.8, price=200.0)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    assert plan.optimizer is None
    assert set(plan.approved_symbols) == {"AAA", "BBB"}
    assert not any(reason.startswith("optimizer") for reason in _reasons(plan))


def test_with_the_flag_off_the_tick_is_reproducible() -> None:
    signals = [_signal("AAA", edge=0.9), _signal("BBB", edge=0.8, price=200.0)]
    kwargs = dict(regime="BULL_TREND", as_of="2026-09-15T09:00:00Z")

    first = plan_v2_tick(snapshot=_snapshot(), signals=signals, **kwargs)
    second = plan_v2_tick(snapshot=_snapshot(), signals=signals, **kwargs)

    assert first.entry_packages.keys() == second.entry_packages.keys()
    assert first.optimizer == second.optimizer


# ── Flag ON: el ranking deja de ser la decisión ───────────────────────────────


def test_with_the_flag_on_the_unmeasurable_top_of_the_ranking_is_not_evaluated() -> None:
    """El nº1 del ranking no trae economía ⇒ la cartera lo declara y opera con el nº2."""
    signals = [
        # Nº1 del ranking por edge, pero SIN p_win ni medias: no es comparable.
        _signal("AAA", edge=0.95),
        # Nº2 del ranking, CON economía declarada (net = 0.8R − coste > 0).
        _signal(
            "BBB",
            edge=0.9,
            price=200.0,
            atr=4.0,
            p_win=0.6,
            avg_win_r=2.0,
            avg_loss_r=-1.0,
            target_price=220.0,
        ),
    ]
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=True),
    )

    assert plan.optimizer is not None
    assert plan.optimizer.decided is True
    assert plan.optimizer.selected == ("BBB",)
    assert plan.ranked[0].instrument_id == "AAA", "el ranking no cambia; la decisión sí"
    assert set(plan.approved_symbols) == {"BBB"}
    assert [d.instrument_id for d in plan.decisions] == ["BBB"]
    assert "optimizer_expected_value_unmeasured" in _reasons(plan)
    assert "edge_below_threshold" not in _reasons(plan)


def test_with_the_flag_on_the_rejected_candidate_publishes_its_real_score() -> None:
    signals = [
        _signal("AAA", edge=0.95),
        _signal(
            "BBB",
            edge=0.9,
            price=200.0,
            atr=4.0,
            p_win=0.6,
            avg_win_r=2.0,
            avg_loss_r=-1.0,
            target_price=220.0,
        ),
    ]
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=True),
    )

    rejected = [
        entry
        for entry in plan.journal_entries
        if entry.instrument_id == "AAA"
        and "optimizer_expected_value_unmeasured" in entry.payload["reasonCodes"]
    ]
    assert len(rejected) == 1
    assert rejected[0].payload["opportunityScore"] is not None


def test_with_the_flag_on_the_approved_set_never_exceeds_the_top_n() -> None:
    signals = [
        _signal(
            f"S{i}",
            edge=0.9 - i * 0.05,
            price=100.0 + i * 10.0,
            sector=f"sector-{i}",
            p_win=0.6,
            avg_win_r=2.0,
            avg_loss_r=-1.0,
        )
        for i in range(5)
    ]
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(top_n=3, optimizer_enabled=True),
    )

    assert plan.optimizer is not None
    assert len(plan.approved_symbols) <= 3
    # El conjunto candidato (el TOP N del ranking) se reparte EXACTAMENTE entre la
    # combinación elegida y los motivos declarados: ninguna candidata queda en silencio.
    candidates = {s.instrument_id for s in plan.ranked[:3]}
    assert set(plan.optimizer.selected) | set(plan.optimizer.reasons_by_instrument()) == candidates
    assert not any(reason.startswith("edge_below") for reason in _reasons(plan))
