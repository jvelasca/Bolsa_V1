"""V2.33 / A13 — fase PAPER FORWARD: forward paper de la ACTIVE (puro, sin DB).

Certifica que la evidencia forward se **ejecuta** sobre mercado nuevo posterior a la
promoción (no es una re-etiqueta del shadow), que es determinista y que es fail-closed
ante falta de definición, falta de barras nuevas o muestra insuficiente.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from bolsa_application.discovery_catalog import DISCOVERY_FAMILIES
from bolsa_application.paper_forward_phase import (
    PaperForwardConfig,
    extract_active_executable,
    run_paper_forward,
    split_forward,
)
from bolsa_domain.entities.strategy_lifecycle import (
    ActiveStrategy,
    PaperForwardPolicy,
)


def _executable_definition() -> dict[str, Any]:
    """Materializa una definición ejecutable real (plantilla del catálogo)."""
    family = next(f for f in DISCOVERY_FAMILIES if f.name == "ema_crossover")
    definition = family.template({"fastPeriod": 5, "slowPeriod": 20})
    assert definition is not None
    return definition


def _active(
    definition: dict[str, Any],
    version_id: str = "ver-forward-1",
) -> ActiveStrategy:
    return ActiveStrategy(
        version_id=version_id,
        candidate_id="cand-1",
        instrument_id="AAA",
        name="forward-test",
        definition=definition,
    )


def _bars(count: int = 200) -> list[Any]:
    from bolsa_analytics.backtest import BacktestBarInput

    out = []
    for index in range(count):
        price = 100.0 + 12.0 * math.sin(index / 6.0) + index * 0.05
        out.append(
            BacktestBarInput(
                timestamp=f"2026-01-{index % 28 + 1:02d}",
                close=price,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                volume=1000.0,
            )
        )
    return out


def _dated_bars(count: int = 400, start_day: int = 0) -> list[Any]:
    """Barras con timestamps reales y crecientes (2026-01-01 + N días)."""
    from datetime import date, timedelta

    from bolsa_analytics.backtest import BacktestBarInput

    base = date(2026, 1, 1)
    out = []
    for index in range(count):
        price = 100.0 + 12.0 * math.sin(index / 6.0) + index * 0.05
        ts = base + timedelta(days=start_day + index)
        out.append(
            BacktestBarInput(
                timestamp=ts.isoformat(),
                close=price,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                volume=1000.0,
            )
        )
    return out


# ── Extracción / partición ───────────────────────────────────────────────────────


def test_extract_active_executable_none_when_missing() -> None:
    assert extract_active_executable(_active({})) is None
    assert extract_active_executable(_active({"executable": None})) is None
    assert extract_active_executable(_active({"executable": {"id": "x"}})) == {"id": "x"}


def test_split_forward_keeps_only_bars_after_promotion() -> None:
    bars = _dated_bars(100)
    promoted_at = bars[60].timestamp
    forward = split_forward(bars, promoted_at=promoted_at)
    assert len(forward) == 39
    assert all(_ts(b) > promoted_at for b in forward)


def test_split_forward_without_promoted_at_returns_all() -> None:
    bars = _dated_bars(10)
    assert split_forward(bars, promoted_at=None) == list(bars)


# ── Fail-closed ──────────────────────────────────────────────────────────────────


def test_paper_forward_without_definition_is_fail_closed() -> None:
    result = run_paper_forward(active=_active({}), bars=_bars())
    assert result.passed is False
    assert "forward_sin_definicion_ejecutable" in result.reasons
    assert result.trades == 0


def test_paper_forward_without_new_bars_is_fail_closed() -> None:
    """Sin barras posteriores a la promoción no hay evidencia forward."""
    active = _active({"executable": _executable_definition()})
    bars = _dated_bars(100)
    promoted_at = bars[-1].timestamp
    result = run_paper_forward(
        active=active,
        bars=bars,
        config=PaperForwardConfig(promoted_at=promoted_at),
    )
    assert result.passed is False
    assert "forward_sin_barras" in result.reasons


def test_paper_forward_insufficient_sample_fails() -> None:
    active = _active({"executable": _executable_definition()})
    policy = PaperForwardPolicy(min_closed_round_trips=10_000, min_bars=1, min_return_pct=-1e9)
    result = run_paper_forward(active=active, bars=_bars(), policy=policy)
    assert result.passed is False
    assert "forward_muestra_insuficiente" in result.reasons


# ── Evidencia forward ────────────────────────────────────────────────────────────


def test_paper_forward_produces_contable_evidence() -> None:
    active = _active({"executable": _executable_definition()})
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=10, min_return_pct=-1e9)
    result = run_paper_forward(
        active=active,
        bars=_bars(),
        policy=policy,
        as_of="2026-09-30",
    )
    assert result.trades > 0, "la plantilla debe ejecutar operaciones reales"
    assert result.as_of == "2026-09-30"
    assert result.bars_used == 200
    assert result.return_pct is not None
    assert result.passed is True
    assert result.reasons == ()
    assert result.instrument_id == "AAA"


def test_paper_forward_is_deterministic() -> None:
    active = _active({"executable": _executable_definition()})
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=1, min_return_pct=-1e9)
    first = run_paper_forward(active=active, bars=_bars(), policy=policy)
    second = run_paper_forward(active=active, bars=_bars(), policy=policy)
    assert first == second


def test_paper_forward_only_uses_bars_after_promotion() -> None:
    """La ventana forward debe empezar DESPUÉS de la promoción (mercado nuevo)."""
    active = _active({"executable": _executable_definition()})
    bars = _dated_bars(400)
    promoted_at = bars[299].timestamp
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=10, min_return_pct=-1e9)
    result = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=PaperForwardConfig(promoted_at=promoted_at, window_bars=99, min_bars=10),
    )
    assert result.bars_used == 99
    assert result.forward_start is not None and result.forward_start > promoted_at
    assert result.promoted_at == promoted_at
    assert result.bars_hash is not None


def test_paper_forward_fingerprint_is_reproducible() -> None:
    active = _active({"executable": _executable_definition()})
    bars = _dated_bars(400)
    promoted_at = bars[299].timestamp
    config = PaperForwardConfig(promoted_at=promoted_at, window_bars=99, min_bars=10)
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=10, min_return_pct=-1e9)
    first = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=config,
        data_snapshot_id="snap-1",
    )
    second = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=config,
        data_snapshot_id="snap-1",
    )
    assert first == second
    assert first.bars_hash == second.bars_hash
    assert first.data_snapshot_id == "snap-1"
    assert first.strategy_definition_hash is not None
    assert first.engine_version is not None


def test_paper_forward_bars_hash_includes_dataset_identity() -> None:
    """H2: mismo OHLCV con distinto instrument_id/timeframe ⇒ identidad distinta."""
    active = _active({"executable": _executable_definition()})
    bars = _dated_bars(400)
    promoted_at = bars[299].timestamp
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=10, min_return_pct=-1e9)
    base = PaperForwardConfig(promoted_at=promoted_at, window_bars=99, min_bars=10)

    daily = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=replace(base, instrument_id="AAA", timeframe="D1"),
    )
    hourly = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=replace(base, instrument_id="AAA", timeframe="H1"),
    )
    other_instrument = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=replace(base, instrument_id="BBB", timeframe="D1"),
    )

    assert daily.bars_hash is not None
    assert daily.bars_hash != hourly.bars_hash
    assert daily.bars_hash != other_instrument.bars_hash


def test_paper_forward_identity_falls_back_to_active_instrument() -> None:
    """H2: sin instrument_id en config, la identidad usa el de la ACTIVE."""
    active = _active({"executable": _executable_definition()})
    bars = _dated_bars(400)
    promoted_at = bars[299].timestamp
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=10, min_return_pct=-1e9)
    base = PaperForwardConfig(promoted_at=promoted_at, window_bars=99, min_bars=10)

    from_active = run_paper_forward(active=active, bars=bars, policy=policy, config=base)
    explicit = run_paper_forward(
        active=active,
        bars=bars,
        policy=policy,
        config=replace(base, instrument_id="AAA"),
    )

    assert from_active.bars_hash == explicit.bars_hash


def test_paper_forward_records_vetoes() -> None:
    active = _active({"executable": _executable_definition()})
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=1, min_return_pct=-1e9)
    result = run_paper_forward(
        active=active,
        bars=_bars(),
        policy=policy,
        vetoes=("risk_gate:concentracion",),
    )
    assert result.vetoes == ("risk_gate:concentracion",)


def _ts(bar: Any) -> str:
    ts = getattr(bar, "timestamp", None)
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
