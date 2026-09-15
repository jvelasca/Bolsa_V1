"""AUTO 2.0 — capa de decisión V2 del worker SIM (env-gated, default OFF)."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.auto_v2_entry import (
    V2_ENGINE_ENV,
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_position_decision,
    plan_v2_tick,
    position_manager_package,
    regime_exit_only,
    sector_from_package,
    tunables_from_env,
    v2_engine_enabled,
)
from bolsa_application.decision_contract import DecisionPackage

# ── Gate de entorno ───────────────────────────────────────────────────────────


def test_v2_engine_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(V2_ENGINE_ENV, raising=False)
    assert v2_engine_enabled() is False
    for value in ("0", "false", "off", "", "no"):
        monkeypatch.setenv(V2_ENGINE_ENV, value)
        assert v2_engine_enabled() is False
    for value in ("1", "true", "yes", "on"):
        monkeypatch.setenv(V2_ENGINE_ENV, value)
        assert v2_engine_enabled() is True


def test_tunables_defaults_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_TOP_N", raising=False)
    base = tunables_from_env()
    assert base.top_n == 5
    assert base.min_edge == 0.30

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_TOP_N", "2")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_MIN_EDGE", "0.7")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    cfg = tunables_from_env()
    assert cfg.top_n == 2
    assert cfg.min_edge == 0.7
    assert cfg.regime_override == "BULL_TREND"


def test_tunables_invalid_env_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_TOP_N", "basura")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_MIN_EDGE", "no-numero")
    cfg = tunables_from_env()
    assert cfg.top_n == 5
    assert cfg.min_edge == 0.30


def test_tunables_have_no_default_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    """V2.40.1: el env del edge de reserva es historia; no existe canal de relleno."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_DEFAULT_EDGE", "0.9")
    cfg = tunables_from_env()
    assert not hasattr(cfg, "default_edge")


# ── Snapshot desde el libro del worker ────────────────────────────────────────


def test_build_worker_snapshot() -> None:
    snap = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={"AAA": 100.0},
        entry_prices={"AAA": 100.0},
        marks={"AAA": 105.0},
        strategies=("v42",),
        regime="BULL_TREND",
    )
    assert snap.account_id == "acc-1"
    assert len(snap.positions) == 1
    assert snap.positions[0].market_value == pytest.approx(10_500.0)
    assert snap.positions[0].unrealized_pnl == pytest.approx(500.0)
    assert snap.data_is_fresh is True
    assert snap.active_strategies == ("v42",)
    assert snap.risk_budget is None, "sin presupuesto declarado la foto no lo inventa"


def test_build_worker_snapshot_derives_risk_used_and_budget() -> None:
    """El riesgo consumido sale del stop vivo y el presupuesto del % de equity."""
    snap = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={"AAA": 200.0},
        entry_prices={"AAA": 100.0},
        marks={"AAA": 100.0},
        stops={"AAA": 97.0},
        risk_budget_pct=6.0,
    )
    # 200 uds × (100 − 97) = 600 de riesgo consumido; presupuesto 6% de 100k = 6000.
    assert snap.risk_used == pytest.approx(600.0)
    assert snap.risk_budget == pytest.approx(6000.0)
    assert snap.risk_remaining == pytest.approx(5400.0)


# ── Pipeline de entradas ──────────────────────────────────────────────────────


def _snapshot(*, risk_budget_pct: float | None = 6.0):
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=risk_budget_pct,
    )


def _signal(
    symbol: str,
    *,
    edge: float | None = 0.9,
    price: float = 100.0,
    atr: float | None = 2.0,
    sector: str | None = "tech",
    liquidity: float | None = 1_000_000.0,
    action: str = "BUY",
    moment: datetime | None = None,
    signal_id: str | None = None,
    bar_timestamp: str | None = None,
    valid_until: str | None = None,
    **extra,
) -> V2Signal:
    """Señal COMPLETA del tick.

    V2.40.1: identidad, sector y liquidez son obligatorios y explícitos; una señal a la
    que le falte cualquiera de los tres ya no entra (fail-closed), así que los tests que
    quieren certificar el camino FELIZ deben aportarlos. ``signal_id``/``bar_timestamp``/
    ``valid_until`` se pueden sobreescribir para casos de dedupe/frescura.
    """
    identity = _signal_identity(symbol, action=action, moment=moment)
    return V2Signal(
        symbol,
        action,
        price=price,
        atr=atr,
        edge=edge,
        sector=sector,
        liquidity_notional=liquidity,
        strategy_version="v42",
        signal_id=signal_id if signal_id is not None else identity.signal_id,
        bar_timestamp=bar_timestamp if bar_timestamp is not None else identity.bar_timestamp,
        valid_until=valid_until if valid_until is not None else identity.valid_until,
        **extra,
    )


def test_plan_v2_tick_approves_best() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            _signal("AAA", edge=0.9),
            _signal("BBB", price=200.0, atr=4.0, edge=0.8),
        ],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )
    assert plan.regime == "BULL_TREND"
    assert set(plan.approved_symbols) == {"AAA", "BBB"}
    assert plan.ranked[0].instrument_id == "AAA"  # mayor edge ⇒ rank 1
    assert len(plan.journal_entries) == 2
    pkg = plan.entry_packages["AAA"]
    assert pkg.action == "BUY"
    assert pkg.quantity > 0
    assert pkg.is_execution_intent is False


def test_plan_v2_tick_top_n_limits_entries() -> None:
    signals = [
        _signal(f"S{i}", edge=0.9 - i * 0.05, sector=f"sector-{i}") for i in range(5)
    ]
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        tunables=V2Tunables(top_n=2),
    )
    # Solo TOP 2 tienen score ⇒ los otros 3 quedan vetados por edge_below_threshold.
    assert len(plan.approved_symbols) == 2


def test_plan_v2_tick_regime_unknown_blocks_all() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="",  # UNKNOWN ⇒ exit-only
    )
    assert plan.regime == "UNKNOWN"
    assert plan.approved_symbols == ()
    assert plan.journal_entries[0].payload["reasonCodes"] == ["regime_invalid"]


def test_plan_v2_tick_low_edge_blocks() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", edge=0.1)],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert "edge_below_threshold" in plan.journal_entries[0].payload["reasonCodes"]


def test_plan_v2_tick_ignores_sell_signals_for_entry() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            V2Signal("AAA", "SELL", price=100.0, atr=2.0, edge=0.9),
            _signal("BBB"),
        ],
        regime="BULL_TREND",
    )
    assert set(plan.approved_symbols) == {"BBB"}


def test_plan_v2_tick_existing_position_holds() -> None:
    snap = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=90_000.0,
        open_positions={"AAA": 100.0},
        entry_prices={"AAA": 100.0},
        marks={"AAA": 100.0},
        regime="BULL_TREND",
        sectors={"AAA": "tech"},
    )
    plan = plan_v2_tick(
        snapshot=snap,
        signals=[_signal("AAA")],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert plan.journal_entries[0].payload["reasonCodes"] == ["position_exists"]


def test_plan_v2_tick_atr_fallback_when_absent() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", atr=None)],
        regime="BULL_TREND",
    )
    # atr = 100 * 0.02 = 2 ⇒ stop = 100 - 1.5*2 = 97.
    assert plan.approved_symbols == ("AAA",)
    trade_plan = plan.decisions[0].trade_plan
    assert trade_plan is not None
    assert trade_plan.structural_stop == 97.0


# ── V2.40.1 (P0): gates fail-closed de la cartera ──────────────────────────────


def test_plan_v2_tick_unknown_sector_is_rejected() -> None:
    """Sin sector NO se entra: antes caía al cajón ``<unknown>`` y pasaba."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", sector=None)],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("sector_unknown",)


def test_plan_v2_tick_unknown_liquidity_is_rejected() -> None:
    """Liquidez desconocida NO es "liquidez perfecta": veta con motivo auditable."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", liquidity=None)],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("liquidity_unknown",)


def test_plan_v2_tick_sector_conflict_with_catalog_is_rejected() -> None:
    """``memo sector=`` en conflicto con el catálogo ⇒ CONFLICTING ⇒ no se entra."""
    from bolsa_analytics.cognitive.trade_context import TradeContext

    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            _signal(
                "AAA",
                trade_context=TradeContext.from_observation(
                    sector_declared="tech",
                    sector_catalog="energy",
                    adv_usd=1_000_000.0,
                ),
            )
        ],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("sector_conflicting",)


def test_plan_v2_tick_stale_observation_is_rejected() -> None:
    """Una observación caducada (``fetchedAt`` viejo) NO es ``KNOWN`` ⇒ veta.

    El mismo bloque de fundamentales alimenta el sector Y el ADV, así que un dato viejo
    deja ambos en ``STALE``; el gate de liquidez se evalúa antes y es el que reporta el
    motivo. El mapeo de cada estado a su propio código se certifica por separado en
    ``test_portfolio_decision_engine.py``.
    """
    from bolsa_analytics.cognitive.trade_context import TradeContext

    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            _signal(
                "AAA",
                trade_context=TradeContext.from_observation(
                    sector_catalog="tech",
                    adv_usd=1_000_000.0,
                    observed_at="2026-06-01T00:00:00Z",
                    as_of="2026-09-15T09:00:00Z",
                ),
            )
        ],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("liquidity_unknown",)


def test_plan_v2_tick_unknown_correlation_blocks_when_gate_on() -> None:
    """Con tope de correlación activo, "no la conozco" ⇒ veta (antes pasaba)."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        tunables=V2Tunables(max_correlation=0.8),
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("correlation_unknown",)


def test_plan_v2_tick_open_position_without_sector_blocks_new_entries() -> None:
    """Cesta con sector opaco ⇒ la concentración NO es verificable ⇒ no se aumenta."""
    snap = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={"ZZZ": 100.0},
        entry_prices={"ZZZ": 100.0},
        marks={"ZZZ": 100.0},
        regime="BULL_TREND",
        # Sin ``sectors``: la posición abierta queda sin sector (opaca).
    )
    plan = plan_v2_tick(
        snapshot=snap,
        signals=[_signal("AAA")],
        regime="BULL_TREND",
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("sector_exposure_unverifiable",)


def test_build_worker_snapshot_carries_open_position_sectors() -> None:
    """``sectors`` transmite el sector real (y no un cajón ``<unknown>``)."""
    snap = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={"AAA": 100.0},
        entry_prices={"AAA": 100.0},
        marks={"AAA": 100.0},
        sectors={"AAA": "tech"},
    )
    assert snap.positions[0].sector == "tech"


# ── V2.40.1 (P0): reserva intra-tick de riesgo y exposición ───────────────────


def test_plan_v2_tick_reserves_risk_intra_tick() -> None:
    """6 candidatas de 1% de riesgo con presupuesto 6% ⇒ 6 aprobadas y la 7ª vetada.

    Es el invariante central del hallazgo más grave de v2.40-beta: sin reserva intra-tick
    cada candidato decidía contra una foto con ``risk_used = 0``, así que el presupuesto
    se podía multiplicar por el número de candidatos del mismo tick.
    """
    signals = [_signal(f"S{i}", sector=f"sector-{i}") for i in range(7)]
    plan = plan_v2_tick(
        snapshot=_snapshot(risk_budget_pct=6.0),
        signals=signals,
        regime="BULL_TREND",
        tunables=V2Tunables(top_n=10, risk_budget_pct=6.0),
    )
    assert len(plan.approved_symbols) == 6
    rejected = [d for d in plan.decisions if not d.approved]
    assert len(rejected) == 1
    assert rejected[0].reason_codes == ("risk_budget_exceeded",)
    # El presupuesto queda EXACTAMENTE agotado (``risk_remaining == 0``): lo que se
    # reservó intra-tick es la suma de los riesgos comprometidos, no un contador suelto.
    committed = sum(
        float(d.allocation["riskAmount"]) for d in plan.decisions if d.approved and d.allocation
    )
    assert committed == pytest.approx(6000.0)


def test_plan_v2_tick_reserves_sector_exposure_intra_tick() -> None:
    """La exposición sectorial se recalcula con lo ya aprobado en el mismo tick."""
    signals = [
        _signal("AAA", sector="tech"),
        _signal("BBB", sector="tech"),
        _signal("CCC", sector="tech"),
    ]
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        tunables=V2Tunables(max_sector_pct=50.0),
    )
    # 20% + 20% = 40% (≤ 50%) pasa; la 3ª entrada tech llevaría el sector a 60% ⇒ veta.
    assert plan.approved_symbols == ("AAA", "BBB")
    vetoed = [d for d in plan.decisions if d.instrument_id == "CCC"]
    assert vetoed and vetoed[0].reason_codes == ("concentration_exceeded",)


# ── V2.40.1 (P0): deduplicación determinista ──────────────────────────────────


def test_plan_v2_tick_dedupe_is_order_independent() -> None:
    """El mismo conjunto de señales debe aprobar lo mismo en cualquier orden."""
    weak = _signal("AAA", edge=0.5)
    strong = _signal("AAA", edge=0.95)
    forward = plan_v2_tick(
        snapshot=_snapshot(), signals=[weak, strong], regime="BULL_TREND"
    )
    reverse = plan_v2_tick(
        snapshot=_snapshot(), signals=[strong, weak], regime="BULL_TREND"
    )
    assert forward.approved_symbols == reverse.approved_symbols == ("AAA",)
    assert forward.decisions[0].opportunity_score == reverse.decisions[0].opportunity_score
    assert forward.decisions[0].opportunity_score == pytest.approx(0.95 * 0.30 + 0.10)


def test_canonical_candidate_key_prefers_higher_edge() -> None:
    from bolsa_application.auto_v2_entry import canonical_candidate_key

    weak = _signal("AAA", edge=0.4)
    strong = _signal("AAA", edge=0.9)
    assert canonical_candidate_key(strong) < canonical_candidate_key(weak)


def test_edge_from_package_has_no_default() -> None:
    """Sin ``memo edge=`` el edge es ``None`` (no un valor de relleno)."""
    from bolsa_application.auto_v2_entry import edge_from_package

    assert edge_from_package(DecisionPackage(action="BUY", instrument_id="AAA", quantity=1)) is None
    assert edge_from_package(
        DecisionPackage(action="BUY", instrument_id="AAA", quantity=1, memo="sector=tech")
    ) is None
    assert edge_from_package(
        DecisionPackage(action="BUY", instrument_id="AAA", quantity=1, memo="edge=0.85")
    ) == pytest.approx(0.85)
    assert edge_from_package(
        DecisionPackage(action="BUY", instrument_id="AAA", quantity=1, memo="edge=basura")
    ) is None


# ── Gestión de posiciones ─────────────────────────────────────────────────────


def _open_long():
    return build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAA",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 105.0,
            "target2": 110.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )


def test_position_decision_protective_stop_to_package() -> None:
    result = plan_v2_position_decision(_open_long(), mark_price=95.0, regime="BULL_TREND")
    assert result is not None
    assert result.order_action == "sell"
    pkg = position_manager_package(result)
    assert pkg is not None
    assert pkg.action == "SELL"
    assert pkg.quantity == 10.0
    assert "structural_stop" in pkg.source


def test_position_decision_hold_yields_no_package() -> None:
    result = plan_v2_position_decision(_open_long(), mark_price=101.0, regime="BULL_TREND")
    assert result is not None
    assert result.order_action == "hold"
    assert position_manager_package(result) is None


def test_position_decision_regime_exit_only() -> None:
    result = plan_v2_position_decision(_open_long(), mark_price=101.0, regime="UNKNOWN")
    assert result is not None
    assert result.order_action == "sell"
    pkg = position_manager_package(result)
    assert pkg is not None
    assert "regime_exit" in pkg.source


def test_position_decision_none_position() -> None:
    assert plan_v2_position_decision(None, mark_price=100.0) is None
    assert position_manager_package(None) is None


def test_regime_exit_only_helper() -> None:
    assert regime_exit_only("UNKNOWN") is True
    assert regime_exit_only("RISK_OFF") is True
    assert regime_exit_only("BULL_TREND") is False
    assert regime_exit_only("trend_up") is False
    assert regime_exit_only("") is True


# ── Sector (canal memo) ───────────────────────────────────────────────────────


def test_sector_from_package_reads_memo() -> None:
    pkg = DecisionPackage(
        action="BUY", instrument_id="AAA", quantity=1, memo="edge=0.8 sector=tech"
    )
    assert sector_from_package(pkg) == "tech"


def test_sector_from_package_absent_is_none() -> None:
    assert (
        sector_from_package(DecisionPackage(action="BUY", instrument_id="AAA", quantity=1))
        is None
    )
    assert (
        sector_from_package(
            DecisionPackage(action="BUY", instrument_id="AAA", quantity=1, memo="edge=0.9")
        )
        is None
    )
    assert (
        sector_from_package(
            DecisionPackage(action="BUY", instrument_id="AAA", quantity=1, memo="sector=")
        )
        is None
    )


def test_sector_concentration_blocks_second_entry_same_sector() -> None:
    """Con sector declarado, dos entradas del mismo sector no pueden pasar juntas."""
    snap = _snapshot()
    plan = plan_v2_tick(
        snapshot=snap,
        signals=[
            _signal("AAA", sector="tech"),
            _signal("BBB", sector="tech"),
        ],
        regime="BULL_TREND",
        tunables=V2Tunables(max_sector_pct=25.0),
    )
    # Cada entrada aprobada es 20% del equity; la segunda llevaría el sector a 40% > 25%.
    assert plan.approved_symbols == ("AAA",)
    blocked = [d for d in plan.decisions if d.instrument_id == "BBB"]
    assert blocked and "concentration_exceeded" in blocked[0].reason_codes


# ── Régimen real desde barras (discovery_market_regime_v0) ─────────────────────


def test_aggregate_trial_regime_prefers_conservative() -> None:
    from bolsa_application.auto_v2_entry import aggregate_trial_regime

    assert aggregate_trial_regime(["trend_up", "range"]) == "range"
    assert aggregate_trial_regime(["trend_up", "trend_down"]) == "trend_down"
    assert aggregate_trial_regime(["trend_up", "high_vol"]) == "high_vol"
    assert aggregate_trial_regime(["trend_up", "trend_up"]) == "trend_up"
    assert aggregate_trial_regime([]) == ""
    assert aggregate_trial_regime(["", "inventado"]) == ""


def _bars(close_step: float, length: int = 120) -> list[dict[str, float]]:
    bars = []
    for i in range(length):
        close = 100.0 + close_step * i
        bars.append({"close": close, "high": close * 1.004, "low": close * 0.996})
    return bars


@pytest.mark.asyncio
async def test_discovery_regime_source_reads_bars() -> None:
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    async def provider() -> dict[str, list[dict[str, float]]]:
        return {"AAA": _bars(0.6)}

    source = DiscoveryRegimeSource(bars_provider=provider)
    assert source() == "UNKNOWN", "antes del refresco no hay régimen (fail-closed)"
    assert await source.refresh() == "trend_up"
    assert source.trial_regime() == "trend_up"
    assert source() == "BULL_TREND"


@pytest.mark.asyncio
async def test_discovery_regime_source_failclosed_without_bars() -> None:
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    async def empty() -> dict[str, list[dict[str, float]]]:
        return {}

    source = DiscoveryRegimeSource(bars_provider=empty)
    assert await source.refresh() == ""
    assert source() == "UNKNOWN", "sin barras no se inventa un mercado operable"


@pytest.mark.asyncio
async def test_discovery_regime_source_failclosed_on_provider_error() -> None:
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    async def boom() -> dict[str, list[dict[str, float]]]:
        raise RuntimeError("sin datos")

    source = DiscoveryRegimeSource(bars_provider=boom)
    assert await source.refresh() == ""
    assert source() == "UNKNOWN"
    assert regime_exit_only(source()) is True


@pytest.mark.asyncio
async def test_discovery_regime_source_downtrend_is_exit_only() -> None:
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    async def provider() -> dict[str, list[dict[str, float]]]:
        return {"AAA": _bars(-0.6)}

    source = DiscoveryRegimeSource(bars_provider=provider)
    assert await source.refresh() == "trend_down"
    assert source() == "BEAR_TREND"
    assert regime_exit_only(source()) is False, "bear trend permite gestionar, no bloquea cierres"


# ── Identidad y frescura de señal (anti-repetición sobre la misma barra) ──────


def _signal_identity(
    symbol: str = "AAA",
    *,
    action: str = "BUY",
    moment: datetime | None = None,
):
    from bolsa_application.auto_v2_entry import signal_identity_for_bar

    identity = signal_identity_for_bar(
        instrument_id=symbol,
        action=action,
        strategy_version="v42",
        timeframe="1d",
        moment=moment or datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
    )
    assert identity is not None
    return identity


def test_signal_identity_same_bar_is_stable_across_ticks() -> None:
    """Dos turnos dentro de la misma barra ⇒ MISMA identidad (base del dedupe)."""
    from bolsa_application.auto_v2_entry import signal_identity_for_bar

    first = signal_identity_for_bar(
        instrument_id="AAA", action="BUY", strategy_version="v42", timeframe="1d",
        moment=datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
    )
    second = signal_identity_for_bar(
        instrument_id="AAA", action="BUY", strategy_version="v42", timeframe="1d",
        moment=datetime(2026, 9, 15, 15, 30, tzinfo=UTC),
    )
    assert first is not None and second is not None
    assert first.signal_id == second.signal_id
    assert first.valid_until == "2026-09-16T00:00:00+00:00"


def test_signal_identity_fail_closed_without_timeframe() -> None:
    from bolsa_application.auto_v2_entry import signal_identity_for_bar

    assert (
        signal_identity_for_bar(
            instrument_id="AAA", action="BUY", strategy_version="v42", timeframe="basura",
            moment=datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
        )
        is None
    )


def _signals_with_identity(*symbols: str) -> list[V2Signal]:
    return [_signal(symbol) for symbol in symbols]


def test_plan_v2_tick_blocks_consumed_signal() -> None:
    """La MISMA señal sobre la MISMA barra ya tomada no genera otra oportunidad."""
    signals = _signals_with_identity("AAA")
    consumed = signals[0].signal_id
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        as_of="2026-09-15T09:05:00Z",
        consumed_signal_ids={consumed},
    )
    assert plan.approved_symbols == ()
    assert plan.decisions == ()
    entry = plan.journal_entries[0]
    assert entry.payload is not None
    assert entry.payload["reasonCodes"] == ["signal_duplicate"]
    assert entry.payload["approved"] is False
    assert entry.payload["signalId"] == consumed


def test_plan_v2_tick_blocks_stale_signal() -> None:
    """Señal cuya barra caducó ⇒ no alimenta una decisión nueva (fail-closed)."""
    identity = _signal_identity("AAA")
    stale = replace(identity, valid_until="2026-09-15T08:00:00Z")
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            V2Signal(
                "AAA",
                "BUY",
                price=100.0,
                atr=2.0,
                edge=0.9,
                signal_id=stale.signal_id,
                bar_timestamp=stale.bar_timestamp,
                valid_until=stale.valid_until,
            )
        ],
        regime="BULL_TREND",
        as_of="2026-09-15T09:05:00Z",
    )
    assert plan.approved_symbols == ()
    assert plan.journal_entries[0].payload["reasonCodes"] == ["signal_stale"]


def test_plan_v2_tick_without_identity_is_rejected() -> None:
    """V2.40.1 invierte la regla: sin identidad NO hay entrada (fail-closed).

    Antes se decidía igual ("el dedupe no es un gate de riesgo"). Pero sin identidad no
    hay idempotencia (no re-operar la misma barra), ni deduplicación, ni auditoría, ni
    replay: en un sistema autónomo eso es un gate de riesgo, no una degradación.
    """
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            V2Signal(
                "AAA",
                "BUY",
                price=100.0,
                atr=2.0,
                edge=0.9,
                sector="tech",
                liquidity_notional=1_000_000.0,
                signal_id="",
            )
        ],
        regime="BULL_TREND",
        as_of="2026-09-15T09:05:00Z",
        consumed_signal_ids={"AAA|v42|1d|2026-09-15|irrelevante"},
    )
    assert plan.approved_symbols == ()
    assert plan.decisions == ()
    assert plan.journal_entries[0].payload["reasonCodes"] == ["signal_identity_missing"]


def test_plan_v2_tick_consumed_signal_of_other_bar_still_decides() -> None:
    """La barra SIGUIENTE sí puede volver a proponer la misma idea (nueva identidad)."""
    previous_bar = _signal_identity("AAA")  # barra del 15
    next_bar = _signal_identity("AAA", moment=datetime(2026, 9, 16, 9, 0, tzinfo=UTC))
    assert previous_bar.signal_id != next_bar.signal_id
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[
            _signal(
                "AAA",
                signal_id=next_bar.signal_id,
                bar_timestamp=next_bar.bar_timestamp,
                valid_until=next_bar.valid_until,
            )
        ],
        regime="BULL_TREND",
        as_of="2026-09-16T09:05:00Z",
        consumed_signal_ids={previous_bar.signal_id},
    )
    assert plan.approved_symbols == ("AAA",)
