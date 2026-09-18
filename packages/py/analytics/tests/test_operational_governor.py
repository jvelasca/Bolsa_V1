"""OperationalGovernor — tabla de decisión pura (AUTO-3 · V2.43).

Certifica las tres propiedades que el slice declara del gobernador: **totalidad**,
**monotonía** (más riesgo nunca es más permisivo) y **fail-closed** (un eje ``UNKNOWN``
nunca es "libre"). Son propiedades de la tabla, no del cableado: aquí no hay worker,
ni snapshot, ni journal.
"""

import pytest

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.operational_governor import (
    ENCODED_DRAWDOWN_BANDS,
    ENCODED_LIQUIDITY_BANDS,
    ENCODED_MARKET_REGIMES,
    ENCODED_RISK_REGIMES,
    ENCODED_VOLATILITY_BANDS,
    GOVERNOR_VERSION,
    RISK_SCALE_BY_STATE,
    DrawdownPolicy,
    GovernorPolicy,
    assess_from_measurements,
    assess_operational_state,
    coerce_drawdown_band,
    coerce_liquidity_band,
    coerce_market_regime,
    coerce_operational_state,
    coerce_risk_regime,
    coerce_volatility_band,
    drawdown_cap,
    liquidity_band_for,
    liquidity_cap,
    market_cap,
    resolve_operational_state,
    risk_cap,
    risk_regime_from,
    risk_scale_for_state,
    state_severity,
    strictest_state,
    to_market_regime,
    volatility_band_for,
    volatility_cap,
)

_ALL_STATES = (
    "ENTRY_ALLOWED",
    "ENTRY_REDUCED",
    "ENTRY_RESTRICTED",
    "EXIT_ONLY",
    "HALTED",
)

# Ejes en el MISMO orden que la tabla. Cada valor aporta su techo declarado, y el
# nombre del ``kwarg`` de ``resolve_operational_state`` es el contrato con el journal.
_AXES = (
    ("market_regime", ENCODED_MARKET_REGIMES, market_cap),
    ("risk_regime", ENCODED_RISK_REGIMES, risk_cap),
    ("drawdown_band", ENCODED_DRAWDOWN_BANDS, drawdown_cap),
    ("volatility_band", ENCODED_VOLATILITY_BANDS, volatility_cap),
    ("liquidity_band", ENCODED_LIQUIDITY_BANDS, liquidity_cap),
)


def _combinations() -> list[dict[str, str]]:
    """Producto cartesiano de los cinco ejes (1 728 combinaciones)."""
    out: list[dict[str, str]] = [{}]
    for name, values, _cap in _AXES:
        out = [{**combo, name: value} for combo in out for value in values]
    return out


# ── Techos declarados por eje ─────────────────────────────────────────────────


def test_declared_caps_are_the_roadmap_policy() -> None:
    assert market_cap("TREND_UP") == "ENTRY_ALLOWED"
    assert market_cap("RANGE") == "ENTRY_ALLOWED"
    assert market_cap("LOW_VOL") == "ENTRY_ALLOWED"
    assert market_cap("HIGH_VOL") == "ENTRY_REDUCED"
    assert market_cap("TREND_DOWN") == "ENTRY_RESTRICTED"
    assert market_cap("UNKNOWN") == "EXIT_ONLY"

    assert risk_cap("RISK_ON") == "ENTRY_ALLOWED"
    assert risk_cap("RISK_REDUCING") == "ENTRY_REDUCED"
    assert risk_cap("RISK_OFF") == "EXIT_ONLY"
    assert risk_cap("UNKNOWN") == "EXIT_ONLY"

    # Drawdown: 100 % → 75 % → 50 % → NO ENTRY → EXIT_ONLY (1:1 con los cinco estados).
    assert [drawdown_cap(band) for band in ENCODED_DRAWDOWN_BANDS] == [
        "ENTRY_ALLOWED",
        "ENTRY_REDUCED",
        "ENTRY_RESTRICTED",
        "EXIT_ONLY",
        "HALTED",
        "EXIT_ONLY",
    ]

    assert volatility_cap("LOW") == "ENTRY_ALLOWED"
    assert volatility_cap("NORMAL") == "ENTRY_ALLOWED"
    assert volatility_cap("HIGH") == "ENTRY_REDUCED"
    assert volatility_cap("UNKNOWN") == "ENTRY_RESTRICTED"

    assert liquidity_cap("OK") == "ENTRY_ALLOWED"
    assert liquidity_cap("THIN") == "ENTRY_RESTRICTED"
    assert liquidity_cap("UNKNOWN") == "ENTRY_RESTRICTED"


def test_state_severity_is_strictly_ordered() -> None:
    severities = [state_severity(state) for state in _ALL_STATES]
    assert severities == sorted(severities)
    assert len(set(severities)) == len(_ALL_STATES)
    assert severities[0] == 0


def test_risk_scale_never_exceeds_one_and_never_grows_with_severity() -> None:
    for state in _ALL_STATES:
        scale = RISK_SCALE_BY_STATE[state]
        assert risk_scale_for_state(state) == scale
        assert 0.0 <= scale <= 1.0
    assert RISK_SCALE_BY_STATE["ENTRY_ALLOWED"] == 1.0
    assert RISK_SCALE_BY_STATE["EXIT_ONLY"] == 0.0
    assert RISK_SCALE_BY_STATE["HALTED"] == 0.0
    ordered = [RISK_SCALE_BY_STATE[state] for state in _ALL_STATES]
    assert ordered == sorted(ordered, reverse=True)


# ── Totalidad ────────────────────────────────────────────────────────────────


def test_resolution_is_total_over_the_cartesian_product() -> None:
    combos = _combinations()
    assert len(combos) == 1728
    for combo in combos:
        state = resolve_operational_state(**combo)
        assert state in _ALL_STATES, combo
        # La tabla es exactamente el MÁXIMO de los techos por eje: ni relaja ni endurece.
        worst = max(state_severity(cap(combo[name])) for name, _values, cap in _AXES)
        assert state_severity(state) == worst, combo


def test_omitted_axis_is_never_permissive() -> None:
    """Omitir un eje ⇒ ``UNKNOWN`` ⇒ techo fail-closed (no hay default implícito)."""
    with_no_axes = resolve_operational_state()
    assert with_no_axes == "EXIT_ONLY"  # el eje de mercado sin dato ya veta la entrada.


def test_kill_switch_forces_halted_over_everything() -> None:
    perfect = {
        "market_regime": "TREND_UP",
        "risk_regime": "RISK_ON",
        "drawdown_band": "FULL",
        "volatility_band": "LOW",
        "liquidity_band": "OK",
    }
    assert resolve_operational_state(**perfect) == "ENTRY_ALLOWED"
    assert resolve_operational_state(**perfect, halted=True) == "HALTED"


# ── Monotonía ────────────────────────────────────────────────────────────────


def test_more_risk_never_yields_a_more_permissive_state() -> None:
    """Endurecer un eje (más severidad de techo) no puede relajar el estado resuelto.

    Se comparan todos los pares de vectores de techo distintos: si un vector domina a
    otro componente a componente (≥ severidad en TODOS los ejes), su estado resuelto
    tampoco puede ser más permisivo.
    """
    vectors: dict[tuple[int, ...], int] = {}
    for combo in _combinations():
        vector = tuple(state_severity(cap(combo[name])) for name, _values, cap in _AXES)
        resolved = state_severity(resolve_operational_state(**combo))
        assert vectors.setdefault(vector, resolved) == resolved, combo

    keys = sorted(vectors)
    for stricter in keys:
        for laxer in keys:
            if all(a >= b for a, b in zip(stricter, laxer, strict=True)):
                assert vectors[stricter] >= vectors[laxer], (stricter, laxer)


def test_drawdown_policy_band_is_monotone() -> None:
    policy = DrawdownPolicy(reduced_pct=5.0, half_pct=10.0, no_entry_pct=15.0, exit_only_pct=20.0)
    bands = [
        policy.band(pct) for pct in (0.0, 4.99, 5.0, 9.99, 10.0, 14.99, 15.0, 19.99, 20.0, 100.0)
    ]
    assert bands == [
        "FULL",
        "FULL",
        "REDUCED",
        "REDUCED",
        "HALF",
        "HALF",
        "NO_ENTRY",
        "NO_ENTRY",
        "EXIT_ONLY",
        "EXIT_ONLY",
    ]
    severities = [state_severity(drawdown_cap(band)) for band in bands]
    assert severities == sorted(severities)


def test_drawdown_policy_rejects_non_monotone_cuts() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        DrawdownPolicy(reduced_pct=10.0, half_pct=5.0)
    with pytest.raises(ValueError, match="strictly increasing"):
        DrawdownPolicy(reduced_pct=5.0, half_pct=5.0)


def test_governor_policy_never_relaxes() -> None:
    with pytest.raises(ValueError, match="never relax"):
        GovernorPolicy(restricted_edge_factor=0.5)
    with pytest.raises(ValueError, match="min_liquidity_notional"):
        GovernorPolicy(min_liquidity_notional=-1.0)
    assert GovernorPolicy().restricted_edge_factor >= 1.0


# ── Fail-closed: UNKNOWN nunca es "libre" ────────────────────────────────────


@pytest.mark.parametrize("axis", [name for name, _values, _cap in _AXES])
def test_unknown_axis_never_allows_entry(axis: str) -> None:
    """Con TODOS los demás ejes en su valor más permisivo, un ``UNKNOWN`` no es libre."""
    combo = {
        "market_regime": "TREND_UP",
        "risk_regime": "RISK_ON",
        "drawdown_band": "FULL",
        "volatility_band": "LOW",
        "liquidity_band": "OK",
    }
    assert resolve_operational_state(**combo) == "ENTRY_ALLOWED"
    combo[axis] = "UNKNOWN"
    state = resolve_operational_state(**combo)
    assert state != "ENTRY_ALLOWED", axis
    assert state_severity(state) >= state_severity("ENTRY_RESTRICTED"), axis


def test_unrecognized_labels_are_unknown_and_fail_closed() -> None:
    for junk in (None, "", "  ", "trend_up", "BULL_TREND", "RISK_ON!", 42, ["TREND_UP"]):
        assert coerce_market_regime(junk) == "UNKNOWN"
        assert coerce_risk_regime(junk) == "UNKNOWN"
        assert coerce_drawdown_band(junk) == "UNKNOWN"
        assert coerce_volatility_band(junk) == "UNKNOWN"
        assert coerce_liquidity_band(junk) == "UNKNOWN"
    # Un valor no canónico en cualquier eje se resuelve como el estado MÁS estricto.
    assert resolve_operational_state(market_regime="BULL_TREND") == "EXIT_ONLY"
    assert state_severity("no-existe") == state_severity("HALTED")
    assert strictest_state("ENTRY_ALLOWED", "nope") == "HALTED"
    assert risk_scale_for_state("no-existe") == 0.0
    assert coerce_operational_state("entry_allowed") == "ENTRY_ALLOWED"
    assert coerce_operational_state("ENTRY_ALLOWED ") == "ENTRY_ALLOWED"
    assert coerce_operational_state("nope") is None
    assert coerce_operational_state(None) is None


def test_strictest_state_keeps_the_worst() -> None:
    assert strictest_state("ENTRY_ALLOWED", "ENTRY_REDUCED") == "ENTRY_REDUCED"
    assert strictest_state("ENTRY_REDUCED", "EXIT_ONLY", "ENTRY_RESTRICTED") == "EXIT_ONLY"
    assert strictest_state() == "ENTRY_ALLOWED"


# ── Derivación de bandas desde medidas ───────────────────────────────────────


def test_drawdown_band_requires_complete_measurement() -> None:
    policy = DrawdownPolicy()
    assert policy.band(0.0, measurement=MEASUREMENT_COMPLETE) == "FULL"
    for measurement in (MEASUREMENT_PARTIAL, MEASUREMENT_UNKNOWN, None, "basura"):
        assert policy.band(0.0, measurement=measurement) == "UNKNOWN"
    for bad in (None, float("nan"), float("inf"), float("-inf"), "no-numero", True):
        assert policy.band(bad, measurement=MEASUREMENT_COMPLETE) == "UNKNOWN"  # type: ignore[arg-type]
    # Una caída negativa (equity por encima de la marca) es 0 % de drawdown.
    assert policy.band(-3.0) == "FULL"
    # El estado de medición es un contrato duro: sin dato no se degrada a "FULL".
    assert policy.band(0.0, measurement="cualquiera") == "UNKNOWN"


def test_risk_regime_from_drawdown_band() -> None:
    assert risk_regime_from(drawdown_band="FULL") == "RISK_ON"
    assert risk_regime_from(drawdown_band="REDUCED") == "RISK_REDUCING"
    assert risk_regime_from(drawdown_band="HALF") == "RISK_REDUCING"
    assert risk_regime_from(drawdown_band="NO_ENTRY") == "RISK_OFF"
    assert risk_regime_from(drawdown_band="EXIT_ONLY") == "RISK_OFF"
    assert risk_regime_from(drawdown_band="UNKNOWN") == "UNKNOWN"
    # La medición manda: un número sin medición COMPLETA no es un estado de riesgo.
    assert risk_regime_from(drawdown_band="FULL", measurement=MEASUREMENT_PARTIAL) == "UNKNOWN"


def test_volatility_band_from_market_regime_and_atr() -> None:
    assert volatility_band_for(market_regime="HIGH_VOL", atr_known=True) == "HIGH"
    assert volatility_band_for(market_regime="LOW_VOL", atr_known=True) == "LOW"
    assert volatility_band_for(market_regime="TREND_UP", atr_known=True) == "NORMAL"
    assert volatility_band_for(market_regime="TREND_UP", atr_known=False) == "UNKNOWN"
    assert volatility_band_for(market_regime="UNKNOWN", atr_known=True) == "UNKNOWN"
    # Los regímenes extremos MANDAN sobre la disponibilidad del ATR (son su medida).
    assert volatility_band_for(market_regime="HIGH_VOL", atr_known=False) == "HIGH"


def test_liquidity_band_from_measurement_and_threshold() -> None:
    assert liquidity_band_for(known=True, notional=1_000.0) == "OK"
    assert liquidity_band_for(known=True, notional=0.0) == "THIN"
    assert liquidity_band_for(known=True, notional=1_000.0, min_notional=1_000.0) == "THIN"
    assert liquidity_band_for(known=True, notional=1_001.0, min_notional=1_000.0) == "OK"
    assert liquidity_band_for(known=False, notional=1_000_000.0) == "UNKNOWN"
    assert liquidity_band_for(known=True, notional=None) == "UNKNOWN"
    assert liquidity_band_for(known=True, notional=float("nan")) == "UNKNOWN"


def test_to_market_regime_translates_the_operational_axis() -> None:
    assert to_market_regime("BULL_TREND") == "TREND_UP"
    assert to_market_regime("BEAR_TREND") == "TREND_DOWN"
    assert to_market_regime("SIDEWAYS") == "RANGE"
    assert to_market_regime("HIGH_VOLATILITY") == "HIGH_VOL"
    assert to_market_regime("LOW_VOLATILITY") == "LOW_VOL"
    # ``RISK_OFF`` es un hecho de RIESGO, no de mercado: no se traduce.
    assert to_market_regime("RISK_OFF") == "UNKNOWN"
    assert to_market_regime("UNKNOWN") == "UNKNOWN"
    assert to_market_regime(None) == "UNKNOWN"
    # El adaptador normaliza la caja (su fuente es un enum interno), pero NO sinónimos:
    # una etiqueta que no esté en el eje se lee como UNKNOWN (fail-closed).
    assert to_market_regime(" bull_trend ") == "TREND_UP"
    assert to_market_regime("BULLISH") == "UNKNOWN"
    assert to_market_regime("") == "UNKNOWN"


# ── Lectura completa (assess) ────────────────────────────────────────────────


def test_assessment_publishes_facts_permission_and_binding_axis() -> None:
    reading = assess_operational_state(
        market_regime="TREND_UP",
        risk_regime="RISK_ON",
        drawdown_band="FULL",
        volatility_band="LOW",
        liquidity_band="OK",
    )
    assert reading.state == "ENTRY_ALLOWED"
    assert reading.risk_scale == 1.0
    assert reading.binding_axis == "none"
    assert reading.allows_new_entry is True
    assert reading.blocks_new_entry is False
    payload = reading.to_dict()
    assert payload["governorVersion"] == GOVERNOR_VERSION
    assert payload["marketRegime"] == "TREND_UP"
    assert payload["riskRegime"] == "RISK_ON"
    assert payload["operationalState"] == "ENTRY_ALLOWED"
    assert payload["bindingAxis"] == "none"
    assert set(payload) == {
        "governorVersion",
        "marketRegime",
        "riskRegime",
        "drawdownBand",
        "volatilityBand",
        "liquidityBand",
        "operationalState",
        "riskScale",
        "bindingAxis",
    }


def test_binding_axis_names_the_axis_that_imposed_the_cap() -> None:
    # Ganador único por severidad.
    assert (
        assess_operational_state(
            market_regime="TREND_DOWN",
            risk_regime="RISK_ON",
            drawdown_band="FULL",
            volatility_band="LOW",
            liquidity_band="OK",
        ).binding_axis
        == "market"
    )
    assert (
        assess_operational_state(
            market_regime="TREND_UP",
            risk_regime="RISK_ON",
            drawdown_band="HALF",
            volatility_band="LOW",
            liquidity_band="OK",
        ).binding_axis
        == "drawdown"
    )
    assert (
        assess_operational_state(
            market_regime="TREND_UP",
            risk_regime="RISK_ON",
            drawdown_band="FULL",
            volatility_band="LOW",
            liquidity_band="THIN",
        ).binding_axis
        == "liquidity"
    )
    assert (
        assess_operational_state(
            market_regime="TREND_UP",
            risk_regime="RISK_ON",
            drawdown_band="FULL",
            volatility_band="HIGH",
            liquidity_band="OK",
        ).binding_axis
        == "volatility"
    )
    # Empate: gana el eje declarado ANTES en ``_AXIS_ORDER`` (determinista y auditable).
    assert (
        assess_operational_state(
            market_regime="TREND_UP",
            risk_regime="RISK_ON",
            drawdown_band="EXIT_ONLY",  # HALTED
            volatility_band="UNKNOWN",  # ENTRY_RESTRICTED
            liquidity_band="OK",
        ).binding_axis
        == "drawdown"
    )
    # El kill switch es el techo absoluto y se declara como tal.
    assert (
        assess_operational_state(
            market_regime="TREND_UP",
            risk_regime="RISK_ON",
            drawdown_band="FULL",
            volatility_band="LOW",
            liquidity_band="OK",
            halted=True,
        ).binding_axis
        == "halted"
    )


def test_assess_from_measurements_end_to_end() -> None:
    policy = GovernorPolicy()
    healthy = assess_from_measurements(
        operational_regime="BULL_TREND",
        drawdown_pct=0.5,
        drawdown_measurement=MEASUREMENT_COMPLETE,
        atr_known=True,
        liquidity_known=True,
        liquidity_notional=1_000_000.0,
        policy=policy,
    )
    assert healthy.state == "ENTRY_ALLOWED"
    assert healthy.market_regime == "TREND_UP"
    assert healthy.risk_regime == "RISK_ON"
    assert healthy.drawdown_band == "FULL"

    # Drawdown del 12 %: riesgo en reducción, tamaño al 75 %.
    reducing = assess_from_measurements(
        operational_regime="BULL_TREND",
        drawdown_pct=12.0,
        drawdown_measurement=MEASUREMENT_COMPLETE,
        atr_known=True,
        liquidity_known=True,
        liquidity_notional=1_000_000.0,
        policy=policy,
    )
    assert reducing.drawdown_band == "HALF"
    assert reducing.risk_regime == "RISK_REDUCING"
    assert reducing.state == "ENTRY_RESTRICTED"
    assert reducing.risk_scale == 0.5

    # Drawdown del 22 %: sin entradas nuevas (EXIT_ONLY).
    blocked = assess_from_measurements(
        operational_regime="BULL_TREND",
        drawdown_pct=22.0,
        drawdown_measurement=MEASUREMENT_COMPLETE,
        atr_known=True,
        liquidity_known=True,
        liquidity_notional=1_000_000.0,
        policy=policy,
    )
    assert blocked.drawdown_band == "EXIT_ONLY"
    assert blocked.state == "HALTED"  # EXIT_ONLY de drawdown ⇒ HALTED por tabla.

    # Sin medición del dinero: el eje de riesgo es UNKNOWN y no se abre nada.
    unmeasured = assess_from_measurements(
        operational_regime="BULL_TREND",
        drawdown_pct=None,
        drawdown_measurement=MEASUREMENT_UNKNOWN,
        atr_known=True,
        liquidity_known=True,
        liquidity_notional=1_000_000.0,
        policy=policy,
    )
    assert unmeasured.drawdown_band == "UNKNOWN"
    assert unmeasured.risk_regime == "UNKNOWN"
    assert unmeasured.state == "EXIT_ONLY"

    # Sin liquidez conocida: la banda es UNKNOWN ⇒ al menos ENTRY_RESTRICTED.
    illiquid = assess_from_measurements(
        operational_regime="BULL_TREND",
        drawdown_pct=0.0,
        drawdown_measurement=MEASUREMENT_COMPLETE,
        atr_known=True,
        liquidity_known=False,
        liquidity_notional=None,
        policy=policy,
    )
    assert illiquid.liquidity_band == "UNKNOWN"
    assert illiquid.state == "ENTRY_RESTRICTED"

    # El umbral de liquidez declarado manda: 5 000 con umbral 10 000 ⇒ THIN.
    thin = assess_from_measurements(
        operational_regime="BULL_TREND",
        drawdown_pct=0.0,
        drawdown_measurement=MEASUREMENT_COMPLETE,
        atr_known=True,
        liquidity_known=True,
        liquidity_notional=5_000.0,
        policy=GovernorPolicy(min_liquidity_notional=10_000.0),
    )
    assert thin.liquidity_band == "THIN"
    assert thin.state == "ENTRY_RESTRICTED"
