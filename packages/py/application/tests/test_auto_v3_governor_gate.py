"""AUTO-3 (V2.43) — gate del gobernador en el pipeline V2 de ENTRADAS.

Certifica el cableado, no la tabla (esa vive en
``packages/py/analytics/tests/test_operational_governor.py``):

1. Con ``AUTO_ENGINE_SIM_V2_GOVERNOR`` OFF (default) el tick es **byte-idéntico** al
   histórico aunque el snapshot traiga drawdown.
2. Con el flag ON, el PERMISO del gobernador veta (``EXIT_ONLY``/``HALTED``), escala el
   tamaño (``ENTRY_REDUCED``/``ENTRY_RESTRICTED``) y sube el listón de edge.
3. Toda decisión no-trade publica ``marketRegime``/``riskRegime``/``operationalState``.
"""

import json
import re
from datetime import UTC, datetime

import pytest

from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    tunables_from_env,
)
from bolsa_application.discovery_market_regime import (
    MATH_VERSION_MARKET_REGIME_V1,
    REGIME_LOW_VOL,
    classify_market_regime,
    is_valid_regime,
)
from bolsa_application.portfolio_decision_engine import PortfolioDecisionConfig, decide_portfolio

_AS_OF = "2026-09-18T09:00:00Z"


def _snapshot(*, drawdown_pct: float | None = None):
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
        drawdown_pct=drawdown_pct,
    )


def _signal(
    symbol: str = "AAA",
    *,
    edge: float = 0.9,
    price: float = 100.0,
    atr: float | None = 2.0,
    liquidity: float | None = 1_000_000.0,
) -> V2Signal:
    moment = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
    return V2Signal(
        symbol,
        "BUY",
        price=price,
        atr=atr,
        edge=edge,
        sector="tech",
        liquidity_notional=liquidity,
        strategy_version="v43",
        signal_id=f"sig-{symbol}-{edge}-{moment.date().isoformat()}",
        bar_timestamp=moment.isoformat().replace("+00:00", "Z"),
        valid_until="2026-09-19T09:00:00Z",
    )


def _governor(**overrides: object) -> V2Tunables:
    """Tunables con el gobernador ON (el resto, los defaults de la casa)."""
    base: dict[str, object] = {
        "governor_enabled": True,
        # Posición al 100 % para que el escalado de riesgo sea OBSERVABLE (con el 20 %
        # de la casa el tope de posición manda y dos escalas distintas darían la misma
        # cantidad: el test no certificaría nada).
        "max_position_pct": 100.0,
    }
    base.update(overrides)
    return V2Tunables(**base)  # type: ignore[arg-type]


def _payloads(plan) -> list[dict]:
    return [dict(entry.payload) for entry in plan.journal_entries]


def _normalized(plan) -> list[str]:
    """Payloads serializados con los identificadores aleatorios neutralizados."""
    return [
        re.sub(r"dec-[0-9a-f]+", "dec-X", json.dumps(payload, sort_keys=True))
        for payload in _payloads(plan)
    ]


# ── 1. Flag OFF: byte-idéntico ───────────────────────────────────────────────


def test_governor_off_ignores_drawdown_and_publishes_no_dimensions() -> None:
    with_drawdown = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=25.0),
        signals=[_signal()],
        regime="BULL_TREND",
        as_of=_AS_OF,
    )
    without_drawdown = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal()],
        regime="BULL_TREND",
        as_of=_AS_OF,
    )
    # El camino por defecto ni mira el drawdown: misma decisión y mismo journal.
    assert with_drawdown.approved_symbols == without_drawdown.approved_symbols == ("AAA",)
    assert with_drawdown.governor_states == ()
    assert _normalized(with_drawdown) == _normalized(without_drawdown)
    assert all("operationalState" not in payload for payload in _payloads(with_drawdown))
    for decision in with_drawdown.decisions:
        assert decision.operational_state is None
        assert "operationalState" not in decision.to_dict()


def test_governor_default_flag_is_off() -> None:
    assert V2Tunables().governor_enabled is False
    assert V2Tunables().regime_math_version == "discovery_market_regime_v0"
    assert _snapshot().drawdown_pct is None


def test_decision_config_without_governor_is_the_historical_one() -> None:
    cfg = V2Tunables()
    plain = cfg.decision_config()
    # Sin lectura del gobernador (flag OFF) nada se escala: min_edge y riesgo históricos.
    assert plain.min_edge == cfg.min_edge
    assert plain.allocator.max_risk_per_trade_pct == cfg.max_risk_per_trade_pct
    assert plain.governor is None


# ── 2. Gate por PERMISO ──────────────────────────────────────────────────────


def test_exit_only_vetoes_with_its_own_reason_code() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=17.0),  # NO_ENTRY ⇒ EXIT_ONLY
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=_governor(),
        as_of=_AS_OF,
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("governor_exit_only",)
    assert plan.governor_states == (("AAA", "EXIT_ONLY"),)


def test_halted_vetoes_with_its_own_reason_code() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=25.0),  # EXIT_ONLY de drawdown ⇒ HALTED
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=_governor(),
        as_of=_AS_OF,
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("governor_halted",)
    assert plan.governor_states == (("AAA", "HALTED"),)


def test_governor_only_hardens_the_directional_rule() -> None:
    """El gobernador no RELAJA la regla direccional: en bajista el motivo es el régimen."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal()],
        regime="BEAR_TREND",  # un LONG no entra en tendencia bajista.
        tunables=_governor(),
        as_of=_AS_OF,
    )
    assert plan.decisions[0].reason_codes == ("regime_invalid",)


def test_unmeasured_drawdown_is_exit_only_not_free() -> None:
    """Sin medición de drawdown (``None``) el eje de riesgo es UNKNOWN ⇒ no se abre."""
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=None),
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=_governor(),
        as_of=_AS_OF,
    )
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("governor_exit_only",)


# ── 3. Escalado de tamaño y de listón de edge ────────────────────────────────


def test_reduced_state_scales_risk_down() -> None:
    off = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=6.0),  # REDUCED ⇒ ENTRY_REDUCED
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=V2Tunables(max_position_pct=100.0),
        as_of=_AS_OF,
    )
    on = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=6.0),
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=_governor(),
        as_of=_AS_OF,
    )
    assert on.governor_states == (("AAA", "ENTRY_REDUCED"),)
    assert on.approved_symbols == ("AAA",)
    # El estado REDUCED escala el riesgo al 75 %: la cantidad baja en esa misma proporción
    # (el coste por acción es el mismo con los dos flags, así que la razón es exacta).
    assert on.entry_packages["AAA"].quantity == pytest.approx(
        off.entry_packages["AAA"].quantity * 0.75, rel=1e-3
    )


def test_restricted_state_scales_risk_and_raises_the_edge_bar() -> None:
    # El score de una señal es ``edge × 0.30 + liquidez × 0.10``: con edge 0.9 ⇒ 0.37 y
    # con edge 0.5 ⇒ 0.25. Un factor 1.2 deja el listón en 0.36, que separa ambos casos.
    steady = _governor(governor_restricted_edge_factor=1.2)
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=12.0),  # HALF ⇒ ENTRY_RESTRICTED
        signals=[_signal(edge=0.5)],
        regime="BULL_TREND",
        tunables=steady,
        as_of=_AS_OF,
    )
    assert plan.governor_states == (("AAA", "ENTRY_RESTRICTED"),)
    assert plan.approved_symbols == ()
    assert plan.decisions[0].reason_codes == ("edge_below_threshold",)
    # Y el tamaño también baja (0.5) para quien sí pasa el listón.
    off = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=12.0),
        signals=[_signal(edge=0.9)],
        regime="BULL_TREND",
        tunables=V2Tunables(max_position_pct=100.0),
        as_of=_AS_OF,
    )
    strong = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=12.0),
        signals=[_signal(edge=0.9)],
        regime="BULL_TREND",
        tunables=steady,
        as_of=_AS_OF,
    )
    assert strong.approved_symbols == ("AAA",)
    assert strong.entry_packages["AAA"].quantity == pytest.approx(
        off.entry_packages["AAA"].quantity * 0.5, rel=1e-3
    )


def test_governor_policy_tunables_are_calibrable() -> None:
    # Con el listón de drawdown relajado, el mismo 6 % ya no reduce nada.
    relaxed = _governor(
        governor_drawdown_reduced_pct=10.0,
        governor_drawdown_half_pct=20.0,
        governor_drawdown_no_entry_pct=30.0,
        governor_drawdown_exit_only_pct=40.0,
    )
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=6.0),
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=relaxed,
        as_of=_AS_OF,
    )
    assert plan.governor_states == (("AAA", "ENTRY_ALLOWED"),)


def test_liquidity_threshold_can_restrict_an_entry() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=0.0),
        signals=[_signal(liquidity=5_000.0)],
        regime="BULL_TREND",
        tunables=_governor(governor_min_liquidity_notional=10_000.0),
        as_of=_AS_OF,
    )
    assert plan.governor_states == (("AAA", "ENTRY_RESTRICTED"),)
    assert plan.approved_symbols == ()


# ── 4. Journal: las tres dimensiones en toda decisión no-trade ───────────────


def test_non_trade_decision_publishes_the_three_dimensions() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=17.0),
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=_governor(),
        as_of=_AS_OF,
    )
    payload = _payloads(plan)[0]
    assert payload["reasonCodes"] == ["governor_exit_only"]
    assert payload["marketRegime"] == "TREND_UP"
    assert payload["riskRegime"] == "RISK_OFF"  # NO_ENTRY ⇒ RISK_OFF
    assert payload["operationalState"] == "EXIT_ONLY"
    # El hecho de mercado y el permiso viajan SEPARADOS: el mercado no culpó al régimen.
    assert payload["regime"] == "BULL_TREND"
    assert plan.decisions[0].to_dict()["operationalState"] == "EXIT_ONLY"


def test_dimensions_travel_also_on_decisions_that_did_not_read_the_governor() -> None:
    """Un descarte por identidad (antes de decidir) NO inventa dimensiones del gobernador."""
    plan = plan_v2_tick(
        snapshot=_snapshot(drawdown_pct=17.0),
        signals=[_signal()],
        regime="BULL_TREND",
        tunables=_governor(),
        as_of=_AS_OF,
        consumed_signal_ids=[_signal().signal_id],
    )
    payload = _payloads(plan)[0]
    assert payload["reasonCodes"] == ["signal_duplicate"]
    assert "operationalState" not in payload
    assert "marketRegime" not in payload
    assert "riskRegime" not in payload


def test_decide_portfolio_reads_the_permission_from_the_assessment() -> None:
    from bolsa_analytics.cognitive.operational_governor import assess_operational_state

    reading = assess_operational_state(
        market_regime="TREND_UP",
        risk_regime="RISK_OFF",
        drawdown_band="NO_ENTRY",
        volatility_band="NORMAL",
        liquidity_band="OK",
    )
    decision = decide_portfolio(
        instrument_id="AAA",
        direction="long",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=None,
        snapshot=_snapshot(drawdown_pct=17.0),
        regime="BULL_TREND",
        sector="tech",
        liquidity_notional=1_000_000.0,
        config=PortfolioDecisionConfig(governor=reading),
    )
    assert decision.action == "HOLD"
    assert decision.reason_codes == ("governor_exit_only",)
    assert decision.operational_state == "EXIT_ONLY"
    assert decision.market_regime == "TREND_UP"
    assert decision.risk_regime == "RISK_OFF"
    assert decision.to_dict()["operationalState"] == "EXIT_ONLY"


# ── 5. Tunables por env ──────────────────────────────────────────────────────


def test_governor_env_flag_and_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_GOVERNOR", raising=False)
    assert tunables_from_env().governor_enabled is False
    for value in ("0", "false", "off", "", "no"):
        monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", value)
        assert tunables_from_env().governor_enabled is False
    for value in ("1", "true", "yes", "on"):
        monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", value)
        assert tunables_from_env().governor_enabled is True

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_REDUCED_PCT", "3")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_HALF_PCT", "7")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_NO_ENTRY_PCT", "11")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_EXIT_ONLY_PCT", "13")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_MIN_LIQUIDITY", "250000")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_RESTRICTED_EDGE_FACTOR", "1.5")
    cfg = tunables_from_env()
    policy = cfg.governor_policy()
    assert policy.drawdown.reduced_pct == 3.0
    assert policy.drawdown.half_pct == 7.0
    assert policy.drawdown.no_entry_pct == 11.0
    assert policy.drawdown.exit_only_pct == 13.0
    assert policy.min_liquidity_notional == 250_000.0
    assert policy.restricted_edge_factor == 1.5
    # Los cortes siguen siendo estrictamente crecientes: la política es válida.
    assert policy.drawdown.band(13.0) == "EXIT_ONLY"


def test_governor_env_invalid_values_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_REDUCED_PCT", "basura")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_MIN_LIQUIDITY", "no-numero")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_RESTRICTED_EDGE_FACTOR", "0.1")
    cfg = tunables_from_env()
    assert cfg.governor_drawdown_reduced_pct == V2Tunables().governor_drawdown_reduced_pct
    assert cfg.governor_min_liquidity_notional == 0.0
    # Un factor que RELAJARÍA el listón no se acepta: se queda el de la casa (2.0).
    assert cfg.governor_restricted_edge_factor == 2.0
    # La política se construye sin excepción: un env mal puesto NO puede tumbar el tick.
    assert cfg.governor_policy().drawdown.half_pct == 10.0


def test_governor_env_non_monotone_cuts_fall_back_as_a_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un corte incoherente descarta el bloque ENTERO (nunca se aplica a medias)."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_REDUCED_PCT", "30")  # > half (10)
    cfg = tunables_from_env()
    assert cfg.governor_drawdown_reduced_pct == 5.0
    assert cfg.governor_policy().drawdown.band(6.0) == "REDUCED"

    # Un valor no finito tampoco entra (``nan``/``inf`` son "número" para ``float``).
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOV_DD_EXIT_ONLY_PCT", "inf")
    cfg = tunables_from_env()
    assert cfg.governor_drawdown_exit_only_pct == 20.0


def test_regime_math_version_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_REGIME_MATH", raising=False)
    assert tunables_from_env().regime_math_version == "discovery_market_regime_v0"
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME_MATH", "v1")
    assert tunables_from_env().regime_math_version == MATH_VERSION_MARKET_REGIME_V1
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME_MATH", "v99")
    assert tunables_from_env().regime_math_version == "discovery_market_regime_v0"


# ── 6. Math version v1 de régimen: LOW_VOL sin tocar v0 ──────────────────────


def _calm_bars(count: int = 80) -> list[dict[str, float]]:
    """Serie sin dirección y muy calmada: rango intradía del 0,2 % (por debajo del 0,5 %)."""
    return [
        {"high": 100.2 + i * 0.0001, "low": 100.0 + i * 0.0001, "close": 100.1 + i * 0.0001}
        for i in range(count)
    ]


def _volatile_bars(count: int = 80) -> list[dict[str, float]]:
    return [{"high": 106.0 + i, "low": 100.0 + i, "close": 103.0 + i} for i in range(count)]


def test_math_v1_adds_low_vol_without_changing_v0() -> None:
    calm = _calm_bars()
    assert classify_market_regime(calm) == "range"  # v0 (default): el eje de siempre.
    assert classify_market_regime(calm, math_version=MATH_VERSION_MARKET_REGIME_V1) == (
        REGIME_LOW_VOL
    )
    # v0 NO admite ``low_vol`` como etiqueta válida (su eje es inmutable).
    assert is_valid_regime(REGIME_LOW_VOL) is False
    assert is_valid_regime(REGIME_LOW_VOL, math_version=MATH_VERSION_MARKET_REGIME_V1) is True
    # Una versión desconocida no clasifica ni valida nada (fail-closed).
    assert classify_market_regime(calm, math_version="v99") == ""
    assert is_valid_regime("range", math_version="v99") is False


def test_math_v1_keeps_the_priority_of_v0() -> None:
    volatile = _volatile_bars()
    assert classify_market_regime(volatile, math_version=MATH_VERSION_MARKET_REGIME_V1) == (
        classify_market_regime(volatile)
    )
