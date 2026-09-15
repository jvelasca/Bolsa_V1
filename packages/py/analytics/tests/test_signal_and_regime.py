"""SignalIdentity + MarketRegimeGate (AUTO 2.0 · P1)."""

from bolsa_analytics.cognitive.market_regime_gate import (
    map_macro_regime,
    map_trial_regime,
    regime_allows_entry_for,
    regime_allows_new_entry,
    regime_blocks_new_long,
    regime_blocks_new_short,
    resolve_operational_regime,
)
from bolsa_analytics.cognitive.signal_identity import (
    SignalIdentity,
    build_signal_identity,
    compute_signal_hash,
)

# ── SignalIdentity ──────────────────────────────────────────────────────────────


def test_build_signal_identity() -> None:
    sig = build_signal_identity(
        instrument_id="AAPL",
        strategy_version="v42",
        timeframe="D1",
        bar_timestamp="2026-09-15T00:00:00Z",
        action="entry_long",
        generated_at="2026-09-15T09:00:00Z",
        valid_until="2026-09-15T23:59:59Z",
    )
    assert sig is not None
    assert sig.instrument_id == "AAPL"
    assert sig.is_fresh("2026-09-15T10:00:00Z") is True
    assert sig.is_fresh("2026-09-16T00:00:00Z") is False


def test_same_signal_dedup() -> None:
    a = build_signal_identity(
        instrument_id="AAPL", strategy_version="v42", timeframe="D1",
        bar_timestamp="2026-09-15", action="entry_long",
    )
    b = build_signal_identity(
        instrument_id="AAPL", strategy_version="v42", timeframe="D1",
        bar_timestamp="2026-09-15", action="entry_long",
    )
    c = build_signal_identity(
        instrument_id="AAPL", strategy_version="v42", timeframe="D1",
        bar_timestamp="2026-09-15", action="exit",
    )
    d = build_signal_identity(
        instrument_id="AAPL", strategy_version="v42", timeframe="D1",
        bar_timestamp="2026-09-16", action="entry_long",
    )
    assert a is not None and b is not None and c is not None and d is not None
    assert a.same_signal_as(b) is True
    assert a.same_signal_as(c) is False  # misma barra, distinta acción
    assert a.same_signal_as(d) is False  # distinta barra


def test_missing_fields_fail_closed() -> None:
    assert build_signal_identity(
        instrument_id="", strategy_version="v42", timeframe="D1",
        bar_timestamp="t", action="entry_long",
    ) is None
    assert build_signal_identity(
        instrument_id="AAPL", strategy_version="v42", timeframe="D1",
        bar_timestamp="t", action="",
    ) is None


def test_hash_deterministic_and_distinct() -> None:
    h1 = compute_signal_hash("entry_long", "p1", "p2")
    h2 = compute_signal_hash("entry_long", "p1", "p2")
    h3 = compute_signal_hash("exit", "p1", "p2")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


def test_no_valid_until_not_fresh() -> None:
    sig = SignalIdentity(
        instrument_id="AAPL", strategy_version="v42", timeframe="D1",
        bar_timestamp="t", signal_hash="h",
    )
    assert sig.is_fresh("2099-01-01T00:00:00Z") is False


def test_bar_window_aligns_same_bar_for_different_moments() -> None:
    """Dos instantes de la MISMA barra D1 ⇒ mismo inicio/cierre (misma identidad)."""
    from datetime import UTC, datetime

    from bolsa_analytics.cognitive.signal_identity import bar_window

    morning = bar_window(datetime(2026, 9, 15, 9, 5, tzinfo=UTC), "1d")
    midday = bar_window(datetime(2026, 9, 15, 14, 30, tzinfo=UTC), "1d")
    assert morning == midday
    assert morning == (
        "2026-09-15T00:00:00+00:00",
        "2026-09-16T00:00:00+00:00",
    )
    # Instantes de barras distintas NO colisionan.
    next_day = bar_window(datetime(2026, 9, 16, 9, 0, tzinfo=UTC), "1d")
    assert next_day != morning


def test_bar_window_intraday_and_fail_closed() -> None:
    from datetime import UTC, datetime

    from bolsa_analytics.cognitive.signal_identity import (
        bar_window,
        timeframe_seconds,
    )

    assert bar_window(datetime(2026, 9, 15, 9, 7, 30, tzinfo=UTC), "5m") == (
        "2026-09-15T09:05:00+00:00",
        "2026-09-15T09:10:00+00:00",
    )
    assert timeframe_seconds("15m") == 900
    assert timeframe_seconds("4h") == 14400
    # Fail-closed: timeframe ilegible o instante sin zona ⇒ sin ventana (sin identidad).
    assert timeframe_seconds("diario") is None
    assert timeframe_seconds("0m") is None
    assert bar_window(datetime(2026, 9, 15, 9, 5), "1d") is None
    assert bar_window(datetime(2026, 9, 15, 9, 5, tzinfo=UTC), "basura") is None


# ── MarketRegimeGate ────────────────────────────────────────────────────────────


def test_map_trial_regime() -> None:
    assert map_trial_regime("trend_up") == "BULL_TREND"
    assert map_trial_regime("trend_down") == "BEAR_TREND"
    assert map_trial_regime("range") == "SIDEWAYS"
    assert map_trial_regime("high_vol") == "HIGH_VOLATILITY"
    assert map_trial_regime("") == "UNKNOWN"
    assert map_trial_regime("whatever") == "UNKNOWN"
    assert map_trial_regime(None) == "UNKNOWN"


def test_map_macro_regime() -> None:
    assert map_macro_regime("risk_off") == "RISK_OFF"
    assert map_macro_regime("crisis") == "RISK_OFF"
    assert map_macro_regime("uncertain") == "UNKNOWN"
    assert map_macro_regime("risk_on") == "BULL_TREND"
    assert map_macro_regime("neutral") == "SIDEWAYS"


def test_resolve_prefers_trial() -> None:
    assert resolve_operational_regime(trial_regime="range", macro_regime="crisis") == "SIDEWAYS"
    # trial UNKNOWN cae al macro.
    assert resolve_operational_regime(trial_regime="", macro_regime="crisis") == "RISK_OFF"
    assert resolve_operational_regime() == "UNKNOWN"


def test_regime_gating() -> None:
    assert regime_allows_new_entry("BULL_TREND") is True
    assert regime_allows_new_entry("SIDEWAYS") is True
    assert regime_allows_new_entry("UNKNOWN") is False
    assert regime_allows_new_entry("RISK_OFF") is False
    assert regime_allows_new_entry(None) is False


def test_regime_blocks_new_long() -> None:
    assert regime_blocks_new_long("BEAR_TREND") is True
    assert regime_blocks_new_long("BULL_TREND") is False


def test_regime_allows_entry_for_is_direction_aware() -> None:
    """El gate direccional es el que debe usar el hot path (no el genérico)."""
    # Un LONG no se abre en tendencia bajista, aunque el gate genérico lo permita.
    assert regime_allows_new_entry("BEAR_TREND") is True
    assert regime_allows_entry_for("BEAR_TREND", "long") is False
    assert regime_allows_entry_for("BULL_TREND", "long") is True
    assert regime_allows_entry_for("SIDEWAYS", "long") is True
    # Simetría para el eje corto.
    assert regime_blocks_new_short("BULL_TREND") is True
    assert regime_allows_entry_for("BULL_TREND", "short") is False
    assert regime_allows_entry_for("BEAR_TREND", "short") is True
    # UNKNOWN/RISK_OFF bloquean cualquier dirección (fail-closed).
    for regime in ("UNKNOWN", "RISK_OFF", None, ""):
        assert regime_allows_entry_for(regime, "long") is False
        assert regime_allows_entry_for(regime, "short") is False
